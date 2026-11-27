/**
 * Branching with the real engine (done-when 3): three touching shapes in one thread, with another
 * shape listed between them, are selected and branched the way the command does it (the engine's
 * plan, its order applied, one commit); the design that comes back sews them with no jump or trim
 * from one start to one end, and so does the PES file exported from it and read back. The engine
 * is started from engine/ with `uv run`, in a data folder of its own.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { COMMANDS, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import { Kind, type Design, type ObjectItem, type PathNode } from "../design/types";
import { useStore } from "../store";

const ENGINE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../../engine");
const LONG_MS = 300_000; // the first run may have to set up the engine's environment

type Answer = { id: number; result?: unknown; error?: { message: string } };

/** The engine over JSON-RPC on stdio, one request per line, as the desktop app talks to it. */
function startEngine(dataDir: string) {
  const child = spawn("uv", ["run", "--locked", "python", "-m", "threadline_engine"], {
    cwd: ENGINE_DIR,
    env: { ...process.env, THREADLINE_DATA_DIR: dataDir },
  });
  const pending = new Map<number, (a: Answer) => void>();
  let buffer = "";
  let said = "";
  let nextId = 1;
  let gone: string | null = null;
  const exited = new Promise<void>((resolve) => {
    const over = (why: string) => {
      gone = why;
      for (const [id, done] of pending) done({ id, error: { message: why } });
      pending.clear();
      resolve();
    };
    child.on("error", (err) => over(`The engine didn't start (this test needs uv, as the engine tests do): ${err.message}`));
    child.on("exit", (code) => over(`The engine stopped (exit ${code}): ${said.slice(-800)}`));
  });
  child.stderr.on("data", (d) => (said += String(d)));
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    buffer += chunk;
    for (let nl = buffer.indexOf("\n"); nl >= 0; nl = buffer.indexOf("\n")) {
      const line = buffer.slice(0, nl);
      buffer = buffer.slice(nl + 1);
      if (!line.trim()) continue;
      const answer = JSON.parse(line) as Answer;
      pending.get(answer.id)?.(answer);
      pending.delete(answer.id);
    }
  });
  return {
    call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      const id = nextId++;
      return new Promise<T>((resolve, reject) => {
        const done = (a: Answer) => (a.error ? reject(new Error(a.error.message)) : resolve(a.result as T));
        if (gone) return done({ id, error: { message: gone } });
        pending.set(id, done);
        child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
      });
    },
    async stop() {
      child.stdin.end();
      const kill = setTimeout(() => child.kill(), 10_000);
      await exited;
      clearTimeout(kill);
    },
  };
}

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const sq = (x: number, y: number, w: number): PathNode[] => [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]];
const fill = (id: string, x: number, y: number, w: number, color = "#cc2222"): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: sq(x, y, w) }, params: {}, thread: { color, name: "", brand: "", catalog: "" },
     transform: { ...IDENT }, threads: [], ops: [] }) as unknown as ObjectItem;

/** The records from the first stitch of the items `members` (indices) to the last. */
function span(r: { kind: number[]; item?: number[] }, members: Set<number>): number[] {
  const on = r.kind.flatMap((k, i) => (k === Kind.Stitch && members.has(r.item ? r.item[i] : -2) ? [i] : []));
  return r.kind.slice(on[0], on[on.length - 1] + 1);
}

/** The first color's records, from its first stitch to its last. */
function firstColor(r: { kind: number[] }): number[] {
  const end = r.kind.findIndex((k) => k === Kind.ColorChange || k === Kind.Stop || k === Kind.End);
  const block = r.kind.slice(0, end < 0 ? r.kind.length : end);
  const first = block.indexOf(Kind.Stitch);
  return block.slice(first, block.lastIndexOf(Kind.Stitch) + 1);
}

const CASES: Record<string, ObjectItem[]> = {
  "sharing an edge": [fill("a", 0, 0, 10), fill("b", 10, 0, 10), fill("c", 20, 0, 10)],
  overlapping: [fill("a", 0, 0, 12), fill("b", 9, 2, 12), fill("c", 18, 0, 12)],
  "touching at a corner": [fill("a", 0, 0, 10), fill("b", 10, 10, 10), fill("c", 20, 20, 10)],
};

describe("branching, with the real engine", () => {
  let work = "";
  let engine: ReturnType<typeof startEngine>;

  beforeAll(() => {
    work = mkdtempSync(path.join(os.tmpdir(), "ludd-branch-"));
    engine = startEngine(path.join(work, "data"));
  });

  afterAll(async () => {
    await engine?.stop();
    if (work) rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  for (const [name, shapes] of Object.entries(CASES)) {
    it(
      `three shapes ${name}, branched, sew as one path into the PES file`,
      async () => {
        const blank = newDoc();
        const blue = fill("x", 60, 0, 10, "#2222cc"); // between them in the list, overlapping neither
        const doc = { ...blank, layout: { ...blank.layout, items: [shapes[0], blue, shapes[1], shapes[2]] } };
        useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a",
                            extraIds: ["b", "c"], design: null, notice: null, dialog: null, pen: null, tool: "select" });
        await COMMANDS.find((c) => c.id === "layout.branch")!.run();
        await whenIdle();
        const st = useStore.getState();
        expect(st.notice).toBeNull();
        expect(st.history.past).toHaveLength(1); // one undo step
        const items = st.history.present!.layout.items as ObjectItem[];
        expect(items.map((it) => it.id)).toEqual(["a", "b", "c", "x"]);
        const bid = items[0].branch;
        expect(bid).toBeTruthy();
        expect(items.map((it) => it.branch)).toEqual([bid, bid, bid, undefined]);
        const design = st.design as Design;
        expect(design.branches).toEqual([expect.objectContaining({ id: bid, items: ["a", "b", "c"], cuts: 0 })]);
        expect(span(design.records, new Set([0, 1, 2])).filter((k) => k !== Kind.Stitch)).toEqual([]);

        const dest = path.join(work, `${name.replace(/ /g, "-")}.pes`);
        await engine.call("layout.export", { layout: st.history.present!.layout, dest });
        const back = await engine.call<Design>("design.open", { path: dest });
        const sewn = firstColor(back.records);
        expect(sewn.length).toBeGreaterThan(300);
        expect(sewn.filter((k) => k !== Kind.Stitch)).toEqual([]); // no jump or trim from start to end
      },
      LONG_MS,
    );
  }

  it(
    "the Branch command refuses two threads in plain words",
    async () => {
      const blank = newDoc();
      const doc = { ...blank, layout: { ...blank.layout, items: [fill("a", 0, 0, 10), fill("b", 10, 0, 10, "#2222cc")] } };
      useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a",
                          extraIds: ["b"], design: null, notice: null, dialog: null, pen: null, tool: "select" });
      await COMMANDS.find((c) => c.id === "layout.branch")!.run();
      await whenIdle();
      expect(useStore.getState().notice?.text).toBe(
        "These shapes are sewn in more than one thread (Fill 1 and Fill 2 differ). A branch sews in one thread: give them the same thread first.",
      );
      expect(useStore.getState().history.past).toHaveLength(0);
    },
    LONG_MS,
  );
});
