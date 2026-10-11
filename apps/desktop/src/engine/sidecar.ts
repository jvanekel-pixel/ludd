import { Command, type Child } from "@tauri-apps/plugin-shell";
import { RpcClient } from "./rpc";

export type EngineStatus =
  | { state: "starting" }
  | { state: "connected"; version: string; python: string }
  | { state: "disconnected"; reason: string }
  | { state: "unavailable"; reason: string };

export type EngineInfo = { version: string; python: string; platform: string };

export type EngineHandle = { client: RpcClient | null; stop: () => void };

export const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/**
 * Spawn the bundled Python engine and connect a JSON-RPC client to its stdio.
 * After `stop` is called this engine reports no further status, so a deliberately
 * stopped engine (e.g. React StrictMode's double mount) can't overwrite the status
 * of the one that replaced it. `client` is null if the engine never connected.
 */
export async function startEngine(report: (s: EngineStatus) => void): Promise<EngineHandle> {
  let stopped = false;
  const onStatus = (s: EngineStatus) => {
    if (!stopped) report(s);
  };

  if (!isTauri()) {
    const dev = import.meta.env.DEV ? await devBridge(onStatus) : null;
    if (dev) return { client: dev, stop: () => void (stopped = true) };
    onStatus({ state: "unavailable", reason: "Browser preview: run the desktop app for the engine" });
    return { client: null, stop: () => void (stopped = true) };
  }

  onStatus({ state: "starting" });
  let child: Child | undefined;
  const client = new RpcClient((line) => child!.write(line));

  // The shell plugin emits stdout line by line with the newline stripped.
  const command = Command.sidecar("binaries/threadline-engine");
  command.stdout.on("data", (line) => client.feed(line.endsWith("\n") ? line : line + "\n"));
  command.stderr.on("data", (line) => console.debug("[engine]", line));
  command.on("close", ({ code }) => {
    client.close(`Engine exited (code ${code})`);
    onStatus({ state: "disconnected", reason: `Engine exited (code ${code})` });
  });
  command.on("error", (err) => onStatus({ state: "disconnected", reason: String(err) }));

  const stop = () => {
    stopped = true;
    client.close("Engine stopped");
    void child?.kill();
  };

  try {
    child = await command.spawn();
    const pong = await client.call<string>("ping");
    if (pong !== "pong") throw new Error(`Unexpected ping reply: ${JSON.stringify(pong)}`);
    const info = await client.call<EngineInfo>("engine.info");
    onStatus({ state: "connected", version: info.version, python: info.python });
    return { client, stop };
  } catch (err) {
    onStatus({ state: "disconnected", reason: err instanceof Error ? err.message : String(err) });
    return { client: null, stop };
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
