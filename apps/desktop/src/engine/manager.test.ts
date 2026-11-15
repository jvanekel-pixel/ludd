import { beforeEach, describe, expect, it, vi } from "vitest";

const starts: { onExit?: () => void; shutdown: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn> }[] = [];
vi.mock("./sidecar", () => ({
  isTauri: () => false,
  startEngine: async (report: (s: unknown) => void, onExit?: () => void) => {
    const h = { client: { call: async () => null }, stop: vi.fn(), shutdown: vi.fn(async () => {}), onExit };
    starts.push(h);
    report({ state: "connected", version: "t", python: "3" });
    return h;
  },
}));

import { connectEngine, restartEngine, shutdownEngine } from "./manager";
import { useStore } from "../store";

const tick = () => new Promise((r) => setTimeout(r, 0));

describe("QA C25 and C23: the engine is restarted if it stops, and stopped cleanly on quit", () => {
  beforeEach(() => {
    starts.length = 0;
    vi.useRealTimers();
  });

  it("starts again by itself after running a while, but not in a loop, and Restart always works", async () => {
    const ready = vi.fn(async () => {});
    const t0 = Date.now();
    const now = vi.spyOn(Date, "now").mockReturnValue(t0);
    connectEngine(ready);
    await tick();
    expect(ready).toHaveBeenLastCalledWith(true);
    now.mockReturnValue(t0 + 60_000); // ran a minute, then stopped
    starts[0].onExit!();
    await tick();
    expect(starts).toHaveLength(2);
    expect(ready).toHaveBeenLastCalledWith(false); // formats and machines reloaded
    expect(useStore.getState().engine).not.toBeNull();
    starts[1].onExit!(); // stopped again straight away: no loop
    await tick();
    expect(starts).toHaveLength(2);
    expect(useStore.getState().engine).toBeNull();
    restartEngine();
    await tick();
    expect(starts).toHaveLength(3);
    now.mockRestore();
  });

  it("asks the engine to stop by itself when LUDD quits, and doesn't restart it", async () => {
    connectEngine(async () => {});
    await tick();
    const h = starts[starts.length - 1];
    await shutdownEngine();
    expect(h.shutdown).toHaveBeenCalled();
    h.onExit?.();
    await tick();
    expect(starts[starts.length - 1]).toBe(h);
  });
});
