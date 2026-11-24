/**
 * Dev-only: lets the plain browser preview (`pnpm dev`, no Tauri) talk to the real engine.
 * The engine is started on the first request and answers JSON-RPC posted to /__engine.
 * Never part of a build; the desktop app always uses the bundled sidecar.
 */
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import type { Plugin } from "vite";

const ENGINE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../engine");

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Only this machine's own preview page may use the engine: another web site open in the same
 *  browser could otherwise post to it (it can write files), and so could a site that points its
 *  own name at 127.0.0.1. */
export function allowedRequest(headers: { host?: string; origin?: string }): boolean {
  const hostOf = (h: string) => h.replace(/:\d+$/, "").toLowerCase();
  if (!headers.host || !LOCAL_HOSTS.has(hostOf(headers.host))) return false;
  if (headers.origin === undefined) return true; // not from a web page (curl, scripts)
  try {
    const o = new URL(headers.origin);
    return LOCAL_HOSTS.has(o.hostname.toLowerCase()) && o.host.toLowerCase() === headers.host.toLowerCase();
  } catch {
    return false;
  }
}

/** Largest request the bridge reads. Projects carry their pictures, so this is generous, but a
 *  runaway or hostile post can't fill memory. */
export const MAX_BODY_BYTES = 1024 * 1024 * 1024;

/** What to do with a posted body: refuse it, pass a notification (no id, so no answer will come)
 *  straight through, or make a call and wait for its answer. */
export function planRequest(body: string): { kind: "bad" } | { kind: "notify"; msg: object } | { kind: "call"; msg: { id: unknown } } {
  let msg: unknown;
  try {
    msg = JSON.parse(body);
  } catch {
    return { kind: "bad" };
  }
  if (!msg || typeof msg !== "object" || Array.isArray(msg)) return { kind: "bad" };
  if (!("id" in msg) || (msg as { id?: unknown }).id === undefined || (msg as { id?: unknown }).id === null) return { kind: "notify", msg };
  return { kind: "call", msg: msg as { id: unknown } };
}

export function engineBridge(): Plugin {
  let child: ChildProcessWithoutNullStreams | null = null;
  let buffer = "";
  const pending = new Map<number, (line: string) => void>();
  let nextId = 1;

  const engine = () => {
    if (child && child.exitCode === null) return child;
    // No shell: the repo path may contain spaces.
    child = spawn("uv", ["run", "python", "-m", "threadline_engine"], { cwd: ENGINE_DIR });
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      buffer += chunk;
      let nl: number;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl);
        buffer = buffer.slice(nl + 1);
        try {
          const id = JSON.parse(line).id as number;
          pending.get(id)?.(line);
          pending.delete(id);
        } catch {
          // not a response line
        }
      }
    });
    child.stderr.on("data", (d) => process.stderr.write(`[engine] ${d}`));
    child.on("exit", () => {
      child = null;
      for (const [id, done] of pending) done(JSON.stringify({ jsonrpc: "2.0", id, error: { code: -32603, message: "Engine exited" } }));
      pending.clear();
    });
    return child;
  };

  return {
    name: "threadline-engine-bridge",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use("/__engine", (req, res) => {
        if (req.method !== "POST") {
          res.statusCode = 405;
          return res.end();
        }
        if (!allowedRequest(req.headers)) {
          res.statusCode = 403;
          return res.end();
        }
        let body = "";
        let size = 0;
        let tooBig = false;
        req.setEncoding("utf8");
        req.on("data", (c: string) => {
          if (tooBig) return;
          size += Buffer.byteLength(c);
          if (size > MAX_BODY_BYTES) {
            tooBig = true;
            body = "";
            res.statusCode = 413;
            res.end();
            req.destroy();
            return;
          }
          body += c;
        });
        req.on("end", () => {
          if (tooBig) return;
          const plan = planRequest(body);
          if (plan.kind === "bad") {
            res.statusCode = 400;
            return res.end();
          }
          if (plan.kind === "notify") {
            // No id: the engine sends no answer, so nothing waits for one.
            engine().stdin.write(JSON.stringify(plan.msg) + "\n");
            res.statusCode = 204;
            return res.end();
          }
          const msg = plan.msg;
          // Re-number so concurrent browser tabs can't collide.
          const theirs = msg.id;
          const ours = nextId++;
          pending.set(ours, (line) => {
            const out = JSON.parse(line);
            out.id = theirs;
            res.setHeader("content-type", "application/json");
            res.end(JSON.stringify(out));
          });
          engine().stdin.write(JSON.stringify({ ...msg, id: ours }) + "\n");
        });
      });
      server.httpServer?.on("close", () => child?.kill());
      // Restart the engine when its code changes, so the preview never runs stale engine code.
      const engineSrc = path.join(ENGINE_DIR, "threadline_engine");
      server.watcher.add(engineSrc);
      server.watcher.on("change", (file) => {
        if (path.resolve(file).startsWith(engineSrc) && file.endsWith(".py") && child) {
          process.stderr.write("[engine] code changed; restarting\n");
          child.kill();
          child = null;
        }
      });
    },
  };
}
