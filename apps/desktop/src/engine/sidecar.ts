import { Command, type Child } from "@tauri-apps/plugin-shell";
import { RpcClient } from "./rpc";

export type EngineStatus =
  | { state: "starting" }
  | { state: "connected"; version: string; python: string }
  | { state: "disconnected"; reason: string }
  | { state: "unavailable"; reason: string };

export type EngineInfo = { version: string; python: string; platform: string };

export type EngineHandle = {
  client: RpcClient | null;
  /** Stop at once (the process is killed). */
  stop: () => void;
  /** Ask the engine to stop and wait (up to `ms`) for it to exit by itself; killed if it doesn't.
   *  The packaged engine deletes its unpacked files (about 180 MB) only when it exits by itself. */
  shutdown: (ms?: number) => Promise<void>;
};

/** How long the first answer may take: the packaged engine unpacks itself first (slow on a busy disk). */
const FIRST_PING_MS = 60_000;

export const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/**
 * Spawn the bundled Python engine and connect a JSON-RPC client to its stdio.
 * After `stop` is called this engine reports no further status, so a deliberately
 * stopped engine (e.g. React StrictMode's double mount) can't overwrite the status
 * of the one that replaced it. `client` is null if the engine never connected (the process
 * is then killed). `onExit` hears about a connected engine that stopped by itself (a crash).
 */
export async function startEngine(report: (s: EngineStatus) => void, onExit?: () => void): Promise<EngineHandle> {
  let stopped = false;
  let failed = false;
  let exited = false;
  let onClosed: (() => void) | undefined;
  const onStatus = (s: EngineStatus) => {
    if (!stopped) report(s);
  };

  if (!isTauri()) {
    const dev = import.meta.env.DEV ? await devBridge(onStatus) : null;
    const stopDev = () => void (stopped = true);
    if (dev) return { client: dev, stop: stopDev, shutdown: async () => stopDev() };
    onStatus({ state: "unavailable", reason: "Browser preview: run the desktop app for the engine" });
    return { client: null, stop: stopDev, shutdown: async () => stopDev() };
  }

  onStatus({ state: "starting" });
  let child: Child | undefined;
  const client = new RpcClient((line) => child!.write(line));

  // The shell plugin emits stdout line by line with the newline stripped.
  const command = Command.sidecar("binaries/threadline-engine");
  command.stdout.on("data", (line) => client.feed(line.endsWith("\n") ? line : line + "\n"));
  command.stderr.on("data", (line) => console.debug("[engine]", line));
  command.on("close", ({ code }) => {
    exited = true;
    onClosed?.();
    client.close(`Engine exited (code ${code})`);
    if (failed) return; // already reported why it never connected
    onStatus({ state: "disconnected", reason: `Engine exited (code ${code})` });
    if (!stopped) onExit?.();
  });
  command.on("error", (err) => onStatus({ state: "disconnected", reason: String(err) }));

  const stop = () => {
    stopped = true;
    client.close("Engine stopped");
    if (!exited) void child?.kill().catch(() => {});
  };

  const shutdown = async (ms = 3000) => {
    if (!child || exited) return stop();
    stopped = true;
    const gone = new Promise<void>((r) => (onClosed = r));
    try {
      await client.call("engine.shutdown", undefined, 1000);
      await Promise.race([gone, new Promise((r) => setTimeout(r, ms))]);
    } catch {
      // Not answering: it's killed below.
    }
    stop();
  };

  try {
    child = await command.spawn();
    const pong = await client.call<string>("ping", undefined, FIRST_PING_MS);
    if (pong !== "pong") throw new Error(`Unexpected ping reply: ${JSON.stringify(pong)}`);
    const info = await client.call<EngineInfo>("engine.info");
    onStatus({ state: "connected", version: info.version, python: info.python });
    return { client, stop, shutdown };
  } catch (err) {
    onStatus({ state: "disconnected", reason: err instanceof Error ? err.message : String(err) });
    // Never connected: don't leave the process running.
    failed = true;
    client.close("Engine stopped");
    if (!exited) void child?.kill().catch(() => {});
    return { client: null, stop, shutdown: async () => stop() };
  }
}

/** Dev only: the Vite dev server runs the engine for the plain browser preview (see vite-engine-bridge.ts). */
async function devBridge(onStatus: (s: EngineStatus) => void): Promise<RpcClient | null> {
  const client: RpcClient = new RpcClient(async (line) => {
    const res = await fetch("/__engine", { method: "POST", body: line });
    client.feed((await res.text()) + "\n");
  }, 60_000);
  try {
    if ((await client.call<string>("ping")) !== "pong") return null;
    const info = await client.call<EngineInfo>("engine.info");
    onStatus({ state: "connected", version: `${info.version} (dev bridge)`, python: info.python });
    return client;
  } catch {
    return null;
  }
}
