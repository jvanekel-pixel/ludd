import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineStatus } from "./sidecar";

type Listener = (arg: never) => void;

/** A fake sidecar process that answers ping and engine.info like the real engine. */
class FakeCommand {
  static instances: FakeCommand[] = [];
  private listeners: Record<string, Listener[]> = {};
  stdout = { on: (_: string, fn: Listener) => this.add("stdout", fn) };
  stderr = { on: (_: string, fn: Listener) => this.add("stderr", fn) };

  constructor() {
    FakeCommand.instances.push(this);
  }
  static sidecar() {
    return new FakeCommand();
  }
  on(event: string, fn: Listener) {
    this.add(event, fn);
  }
  private add(event: string, fn: Listener) {
    (this.listeners[event] ??= []).push(fn);
  }
  emit(event: string, arg: unknown) {
    for (const fn of this.listeners[event] ?? []) (fn as (a: unknown) => void)(arg);
  }
  async spawn() {
    return {
      write: async (line: string) => {
        const req = JSON.parse(line);
        const result =
          req.method === "ping" ? "pong" : { version: "0.0.1", python: "3.12.10", platform: "win32" };
        queueMicrotask(() => this.emit("stdout", JSON.stringify({ jsonrpc: "2.0", id: req.id, result })));
      },
      kill: async () => {
        queueMicrotask(() => this.emit("close", { code: 1 }));
      },
    };
  }
}

vi.mock("@tauri-apps/plugin-shell", () => ({ Command: FakeCommand }));

describe("startEngine", () => {
  beforeEach(() => {
    FakeCommand.instances = [];
    vi.stubGlobal("window", { __TAURI_INTERNALS__: {} });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("connects and reports the engine version", async () => {
    const { startEngine } = await import("./sidecar");
    const statuses: EngineStatus[] = [];
    await startEngine((s) => void statuses.push(s));
    expect(statuses.at(-1)).toEqual({ state: "connected", version: "0.0.1", python: "3.12.10" });
  });

  it("a stopped engine's exit doesn't overwrite the live engine's status (StrictMode double mount)", async () => {
    const { startEngine } = await import("./sidecar");
    let status: EngineStatus | undefined;
    const set = (s: EngineStatus) => (status = s);

    const first = startEngine(set);
    const second = startEngine(set);
    (await first).stop(); // the first mount is torn down
    await second;
    await new Promise((r) => setTimeout(r, 0)); // let the killed engine's close event fire

    expect(FakeCommand.instances).toHaveLength(2);
    expect(status).toEqual({ state: "connected", version: "0.0.1", python: "3.12.10" });
  });

  it("still reports a crash of a running engine", async () => {
    const { startEngine } = await import("./sidecar");
    let status: EngineStatus | undefined;
    await startEngine((s) => (status = s));
    FakeCommand.instances[0].emit("close", { code: 3 });
    expect(status).toEqual({ state: "disconnected", reason: "Engine exited (code 3)" });
  });
});
