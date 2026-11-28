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

import { commit, COMMANDS, whenIdle } from "../actions";
import "../cmd";
import { cutOutSelected, finishKnife, shortestOrder } from "../features";
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

  /** A design of branch "b1" (with its start and end dots set by hand) and, listed after it,
   *  `cutters` outside it; rendered, with the shape `target` selected (and the cutters). */
  async function branchOnCanvas(members: ObjectItem[], cutters: ObjectItem[], target: string) {
    const blank = newDoc();
    const dots = { b1: { start_mm: [0, 5] as [number, number], end_mm: [members.length * 10, 5] as [number, number] } };
    const items = [...members.map((m) => ({ ...m, branch: "b1" }) as ObjectItem), ...cutters];
    const doc = { ...blank, layout: { ...blank.layout, items, branches: dots } };
    useStore.setState({ engine: engine as never, history: { past: [], present: blank, future: [] }, savedDoc: blank,
                        selectedId: null, extraIds: [], design: null, notice: null, dialog: null, pen: null, tool: "select" });
    await commit(doc.layout);
    await whenIdle();
    useStore.getState().setSelection(target, cutters.map((c) => c.id));
    expect(useStore.getState().design?.branches?.map((b) => b.items.length)).toEqual([members.length]);
    return { doc: useStore.getState().history.present!, dots };
  }

  /** After a cut of `target`: every piece is in the branch, in the shape's place, the branch keeps
   *  its dots and sews as one path (no shape left out of it), and one undo puts the shape back. */
  async function expectWhole(before: { doc: ReturnType<typeof newDoc>; dots: object }, target: string) {
    const st = useStore.getState();
    const items = st.history.present!.layout.items as ObjectItem[];
    const was = before.doc.layout.items as ObjectItem[];
    const added = items.filter((it) => !was.some((w) => w.id === it.id));
    const at = was.findIndex((it) => it.id === target);
    const pieces = items.slice(at, at + items.length - was.length + 1);
    expect(pieces.filter((it) => added.includes(it)).length).toBe(added.length); // in the shape's place
    expect(added.length).toBeGreaterThan(0);
    const members = items.filter((it) => it.id !== "x");
    expect(members.map((it) => it.branch)).toEqual(members.map(() => "b1"));
    expect(items.find((it) => it.id === "x")?.branch).toBeUndefined();
    expect(st.history.present!.layout.branches).toEqual(before.dots);
    const design = st.design as Design;
    expect(design.branches?.map((b) => [b.id, [...b.items].sort()])).toEqual([["b1", members.map((it) => it.id).sort()]]);
    expect((design.warnings ?? []).filter((w) => /^branch_(apart|thread)/.test(w.code))).toEqual([]);
    expect(st.history.past).toHaveLength(2); // the design as it was, then one step for the cut
    await COMMANDS.find((c) => c.id === "edit.undo")!.run();
    await whenIdle();
    expect(useStore.getState().history.present!.layout).toEqual(before.doc.layout);
    return design;
  }

  const row = (n: number) => ["a", "b", "c"].slice(0, n).map((id, k) => fill(id, 10 * k, 0, 10));
  const CUTS = [
    { what: "a middle member", shapes: 3, target: "b" },
    { what: "the last member", shapes: 3, target: "c" },
    { what: "one of a branch of two", shapes: 2, target: "b" },
  ];

  for (const { what, shapes, target } of CUTS) {
    const middle = (target.charCodeAt(0) - 97) * 10 + 5; // the cut's x: the middle of the shape

    it(
      `the knife through ${what} keeps every piece in the branch`,
      async () => {
        const before = await branchOnCanvas(row(shapes), [], target);
        COMMANDS.find((c) => c.id === "tool.knife")!.run();
        await finishKnife([middle, -5], [middle, 15]);
        await whenIdle();
        expect(useStore.getState().notice?.text).toBe("Cut into 2 pieces.");
        const design = await expectWhole(before, target);
        expect(design.branches![0].cuts).toBe(0); // the pieces touch along the cut
      },
      LONG_MS,
    );

    it(
      `a cut-out across ${what} keeps every piece in the branch`,
      async () => {
        // A 2 mm bar in another thread, sewn after the branch, cuts the shape in two.
        const bar = { ...fill("x", 0, 0, 1, "#2222cc"), geometry: { outline: [[middle - 1, -2, "c"], [middle + 1, -2, "c"],
          [middle + 1, 12, "c"], [middle - 1, 12, "c"]] as PathNode[] } } as ObjectItem;
        const before = await branchOnCanvas(row(shapes), [bar], target);
        await cutOutSelected();
        await whenIdle();
        expect(useStore.getState().notice?.text).toContain("leaving 2 pieces");
        await expectWhole(before, target);
      },
      LONG_MS,
    );
  }

  it(
    "Sew in the shortest order keeps a branch together, in one undo step",
    async () => {
      const blank = newDoc();
      // Three squares 30 mm apart in a branch, a spot near the first and one past the last.
      const spots = [fill("x", 14, 18, 4), fill("y", 100, 18, 6)];
      const items = [...[0, 40, 80].map((at, k) => ({ ...fill("abc"[k], at, 0, 10), branch: "b1" }) as ObjectItem), ...spots];
      useStore.setState({ engine: engine as never, history: { past: [], present: blank, future: [] }, savedDoc: blank,
                          selectedId: null, extraIds: [], design: null, notice: null, dialog: null, pen: null, tool: "select" });
      await commit({ ...blank.layout, items });
      await whenIdle();
      const before = useStore.getState().history.present!.layout;
      await shortestOrder();
      await whenIdle();
      const st = useStore.getState();
      expect(st.notice?.text).toMatch(/^Reordered: about \d+ mm less travel/);
      expect(st.history.present!.layout.items.map((it) => it.id)).toEqual(["a", "b", "c", "y", "x"]);
      const design = st.design as Design;
      expect(design.branches?.map((b) => b.items)).toEqual([["a", "b", "c"]]);
      expect((design.warnings ?? []).filter((w) => w.code.startsWith("branch_apart"))).toEqual([]);
      expect(st.history.past).toHaveLength(2);
      await COMMANDS.find((c) => c.id === "edit.undo")!.run();
      await whenIdle();
      expect(useStore.getState().history.present!.layout).toEqual(before);
    },
    LONG_MS,
  );

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
