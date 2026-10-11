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
        let body = "";
        req.setEncoding("utf8");
        req.on("data", (c: string) => (body += c));
        req.on("end", () => {
          let msg: { id?: number };
          try {
            msg = JSON.parse(body);
          } catch {
            res.statusCode = 400;
            return res.end();
          }
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
