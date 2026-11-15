/**
 * The one engine the app talks to: started at launch, started again if it stops by itself, and
 * asked to stop cleanly when LUDD quits or installs an update.
 */
import { useStore } from "../store";
import { startEngine, type EngineHandle } from "./sidecar";

let handle: EngineHandle | null = null;
/** Bumped by every start and stop, so a start that's overtaken is thrown away. */
let generation = 0;
let startedAt = 0;
let afterStart: ((first: boolean) => Promise<void>) | null = null;
let starts = 0;
/** An engine that stops within this long of starting isn't restarted by itself (it would loop). */
const STEADY_MS = 30_000;

async function launch() {
  const g = ++generation;
  const { setEngine } = useStore.getState();
  startedAt = Date.now();
  const h = await startEngine(
    (s) => {
      if (g === generation) setEngine(s);
    },
    () => {
      if (g !== generation) return;
      handle = null;
      useStore.getState().setEngine(useStore.getState().engineStatus, null);
      // It stopped by itself: start it again, unless it only just started (then the status bar
      // offers Restart instead of trying over and over).
      if (Date.now() - startedAt > STEADY_MS) void launch();
    },
  );
  if (g !== generation) return h.stop();
  handle = h;
  setEngine(useStore.getState().engineStatus, h.client);
  if (h.client) {
    const first = starts++ === 0;
    if (!first) useStore.getState().notify({ kind: "info", text: "The engine stopped and was started again. Your work is still here." });
    await afterStart?.(first);
  }
}

/** Start the engine. `ready` runs after every successful start (`first` the first time). */
export function connectEngine(ready: (first: boolean) => Promise<void>) {
  afterStart = ready;
  void launch();
}

/** Start the engine again (the status bar's Restart button). */
export function restartEngine() {
  handle?.stop();
  handle = null;
  useStore.getState().setEngine({ state: "starting" }, null);
  void launch();
}

/** Stop at once (the app is being torn down, e.g. React's development double start). */
export function stopEngine() {
  generation++;
  handle?.stop();
  handle = null;
}

/** Ask the engine to stop and wait for it, so it cleans up after itself (LUDD is quitting). */
export async function shutdownEngine() {
  generation++;
  const h = handle;
  handle = null;
  await h?.shutdown();
}
