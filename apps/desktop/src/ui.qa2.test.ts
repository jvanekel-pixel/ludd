/** QA pass 2, area 5 (UI state and interaction model): U1, U2, U4-U7, U9 stay fixed. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import * as F from "./features";
import * as T from "./autoTrace";
import { newDoc } from "./design/layout";
import type { Doc, LayoutItem, ObjectItem, PathNode, RefImage } from "./design/types";
import { heldCount, letGoNewest } from "./escape";
import { onKeyDown } from "./keys";
import { useStore } from "./store";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const sq = (x: number, y: number, w: number): PathNode[] => [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]];

/** A fake engine: each method can wait a while, answer something fixed, or fail. */
function fakeEngine(delays: Record<string, number> = {}) {
  const sent: Record<string, unknown[]> = {};
  const answers: Record<string, unknown> = {};
  const failing = new Set<string>();
  return {
    sent,
    answers,
    failing,
    async call<R>(method: string, params: Record<string, unknown> = {}): Promise<R> {
      (sent[method] ??= []).push(structuredClone(params));
      if (delays[method]) await sleep(delays[method]);
      if (failing.has(method)) throw new Error(`${method} failed`);
      if (method === "layout.render") {
        const layout = params.layout as { items: LayoutItem[] };
        return {
          path: "", name: "x", format: "layout",
          info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
          threads: [], blocks: [], records: { x: [], y: [], kind: [] },
          items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })),
        } as R;
      }
      return (answers[method] ?? null) as R;
    },
  };
}

const fill = (id: string, x = 0): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: sq(x, 0, 10) }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as ObjectItem;
const file = (id: string): LayoutItem =>
  ({ id, kind: "file", path: "C:/d/x.pes", transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as unknown as LayoutItem;
const pic = (id: string): RefImage => ({ id, name: id, path: "C:/p.png", data_url: "", x: 0, y: 0, width_mm: 100, height_mm: 100, rotate: 0, opacity: 1, locked: false, visible: true });

function setDoc(engine: ReturnType<typeof fakeEngine>, items: LayoutItem[], images: RefImage[] = []) {
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, items }, images };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc,
    selectedId: null, extraIds: [], selectedNode: null, notice: null, projectPath: null, tool: "select", pen: null,
    knife: null, stitchEdit: null, ruler: null, angleFor: null, autoTrace: null, autoAll: null,
    design: { items: [], threads: [], blocks: [], records: { x: [], y: [], kind: [] } } as never,
  });
}
const items = () => useStore.getState().history.present!.layout.items;
const ids = () => items().map((i) => i.id);
const run = (id: string) => A.COMMANDS.find((c) => c.id === id)!.run();
const notice = () => useStore.getState().notice?.text ?? "";
const key = (k: string, mods: Partial<KeyboardEvent> = {}) =>
  ({ key: k, code: "", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, repeat: false, target: null, preventDefault() {}, ...mods }) as unknown as KeyboardEvent;

beforeEach(async () => {
  await A.whenIdle();
  while (letGoNewest());
});

describe("U1: one of knife, stitch editing, ruler and angle line at a time", () => {
  it("M while the knife is armed puts the knife away; Esc then puts the ruler away", () => {
    setDoc(fakeEngine(), [fill("a")]);
    useStore.getState().select("a");
    F.startKnife();
    run("view.measure");
    expect(useStore.getState().ruler).toEqual([]);
    expect(useStore.getState().knife).toBeNull();
    expect(heldCount()).toBe(0);
    onKeyDown(key("Escape"));
    expect(useStore.getState().ruler).toBeNull();
  });

  it("the knife after M puts the ruler away", () => {
    setDoc(fakeEngine(), [fill("a")]);
    useStore.getState().select("a");
    run("view.measure");
    F.startKnife();
    expect(useStore.getState().ruler).toBeNull();
    expect(useStore.getState().knife?.id).toBe("a");
  });

  it("M during stitch editing ends stitch editing (and its Esc hold)", () => {
    setDoc(fakeEngine(), [file("f")]);
    useStore.getState().select("f");
    F.startStitchEdit();
    expect(heldCount()).toBe(1);
    run("view.measure");
    expect(useStore.getState().stitchEdit).toBeNull();
    expect(useStore.getState().ruler).toEqual([]);
    expect(heldCount()).toBe(0);
  });

  it("I (angle line) ends the knife and the ruler", () => {
    setDoc(fakeEngine(), [fill("a")]);
    useStore.getState().select("a");
    F.startKnife();
    useStore.getState().setRuler([]);
    run("object.angle");
    const s = useStore.getState();
    expect(s.angleFor?.id).toBe("a");
    expect(s.knife).toBeNull();
    expect(s.ruler).toBeNull();
  });
});

describe("U2: a tool key during stitch editing", () => {
  it("ends stitch editing and lets go of its Esc hold", () => {
    setDoc(fakeEngine(), [file("f")]);
    useStore.getState().select("f");
    F.startStitchEdit();
    run("tool.fill");
    expect(useStore.getState().tool).toBe("fill");
    expect(useStore.getState().stitchEdit).toBeNull();
    expect(heldCount()).toBe(0);
  });
});

describe("U4: engine answers for a design that changed meanwhile are dropped", () => {
  it("merge: a nudge made while merging is kept, and the merge is dropped with a note", async () => {
    const e = fakeEngine({ "shape.merge": 40 });
    e.answers["shape.merge"] = { geometry: { outline: sq(0, 0, 20) } };
    setDoc(e, [fill("a"), fill("b", 10)]);
    useStore.getState().setSelection("a", ["b"]);
    const p = F.mergeSelected();
    await sleep(5);
    run("arrange.right");
    await A.whenIdle();
    const nudged = structuredClone(items());
    await p;
    await A.whenIdle();
    expect(items()).toEqual(nudged);
    expect(notice()).toMatch(/changed while merging/);
  });

  it("knife: a shape undone while cutting stays undone", async () => {
    const e = fakeEngine({ "shape.split": 40 });
    e.answers["shape.split"] = { geometries: [{ outline: sq(0, 0, 5) }, { outline: sq(5, 0, 5) }] };
    setDoc(e, [fill("z", 50)]);
    await A.commit({ ...useStore.getState().history.present!.layout, items: [...items(), fill("a")] });
    useStore.getState().select("a");
    F.startKnife();
    const p = F.finishKnife([5, -5], [5, 15]);
    await sleep(5);
    A.undoEdit();
    await A.whenIdle();
    await p;
    await A.whenIdle();
    expect(ids()).toEqual(["z"]);
    expect(notice()).toMatch(/changed while cutting/);
  });

  it("outline: a shape nudged meanwhile gets no rings round its old place", async () => {
    const e = fakeEngine({ "shape.offset": 40 });
    e.answers["shape.offset"] = { rings: [sq(-2, -2, 14)] };
    setDoc(e, [fill("a"), fill("b", 30)]);
    useStore.getState().select("a");
    const p = F.addOffset({ distance_mm: 2, as: "run", width_mm: 1, holes: false });
    await sleep(5);
    run("arrange.right");
    await A.whenIdle();
    await p;
    await A.whenIdle();
    expect(ids()).toEqual(["a", "b"]);
    expect(notice()).toMatch(/changed while adding the outline/);
  });

  it("optimize jumps: an edit made meanwhile isn't overwritten", async () => {
    const e = fakeEngine({ "layout.optimize_jumps": 40 });
    e.answers["layout.optimize_jumps"] = { changes: { a: { params: { start_mm: [0, 0] } } }, before_mm: 50, after_mm: 10 };
    setDoc(e, [fill("a"), fill("b", 30)]);
    const p = F.optimizeJumps();
    await sleep(5);
    useStore.getState().select("a");
    run("arrange.right");
    await A.whenIdle();
    const nudged = structuredClone(items());
    await p;
    await A.whenIdle();
    expect(items()).toEqual(nudged);
    expect(notice()).toMatch(/changed while optimizing jumps/);
  });

  it("merge with nothing changed still merges (one shape)", async () => {
    const e = fakeEngine();
    e.answers["shape.merge"] = { geometry: { outline: sq(0, 0, 20) } };
    setDoc(e, [fill("a"), fill("b", 10)]);
    useStore.getState().setSelection("a", ["b"]);
    await F.mergeSelected();
    await A.whenIdle();
    expect(ids()).toEqual(["a"]);
  });
});

describe("U5: auto-trace accept racing a new click or Esc", () => {
  const guess = { id: "g1", kind: "fill", outline: sq(0, 0, 10), holes: [], color: "#ff0000" };

  it("the next shape's guess, clicked while the last one was added, stays on screen", async () => {
    const e = fakeEngine({ "layout.render": 40 });
    e.answers["trace.region"] = { candidates: [guess] };
    setDoc(e, [fill("z", 60)], [pic("im")]);
    useStore.getState().setTool("autotrace");
    await T.autoTraceAt(5, 5);
    const p = T.acceptGuess();
    await sleep(5);
    await T.autoTraceAt(20, 20);
    await p;
    await A.whenIdle();
    expect(useStore.getState().autoTrace?.at).toEqual([20, 20]);
    expect(useStore.getState().autoTrace?.guesses.length).toBe(1);
    expect(items()).toHaveLength(2); // the first one was still added
  });

  it("Esc while satins are worked out adds nothing", async () => {
    const e = fakeEngine({ "shape.satin_fill": 40 });
    e.answers["trace.region"] = { candidates: [guess] };
    e.answers["shape.satin_fill"] = { rail_a: [[0, 0, "c"], [10, 0, "c"]], rail_b: [[0, 5, "c"], [10, 5, "c"]], widest_mm: 5 };
    setDoc(e, [fill("z", 60)], [pic("im")]);
    useStore.getState().setTool("autotrace");
    await T.autoTraceAt(5, 5);
    const p = T.acceptGuess("satin");
    await sleep(5);
    onKeyDown(key("Escape"));
    await p;
    await A.whenIdle();
    expect(useStore.getState().autoTrace).toBeNull();
    expect(ids()).toEqual(["z"]);
  });
});

describe("U6: the angle line ends with its fill", () => {
  it("deleting the fill drops angleFor", async () => {
    setDoc(fakeEngine(), [fill("a"), fill("b", 20)]);
    useStore.getState().select("a");
    run("object.angle");
    expect(useStore.getState().angleFor?.id).toBe("a");
    A.removeSelected();
    await A.whenIdle();
    expect(ids()).toEqual(["b"]);
    expect(useStore.getState().angleFor).toBeNull();
  });
});

describe("U7: Ctrl+X with nothing selected", () => {
  it("cuts the only shape (one undo step brings it back)", async () => {
    setDoc(fakeEngine(), [fill("a")]);
    run("edit.cut");
    await A.whenIdle();
    expect(items()).toHaveLength(0);
    A.undoEdit();
    await A.whenIdle();
    expect(ids()).toEqual(["a"]);
    run("edit.paste"); // and it was copied
    await A.whenIdle();
    expect(items()).toHaveLength(2);
  });
});

describe("U9: a delete that fails keeps the selection", () => {
  it("restores what was selected", async () => {
    const e = fakeEngine();
    setDoc(e, [fill("a"), fill("b", 20), fill("c", 40)]);
    useStore.getState().setSelection("a", ["b"]);
    e.failing.add("layout.render");
    A.removeSelected();
    expect(useStore.getState().selectedId).toBeNull(); // right away: the next Delete can't act on them
    await A.whenIdle();
    await sleep(0);
    expect(ids()).toEqual(["a", "b", "c"]);
    expect(useStore.getState().selectedId).toBe("a");
    expect(useStore.getState().extraIds).toEqual(["b"]);
  });
});

describe("U3 (decision 9): Ctrl+Z while drawing removes the last point", () => {
  const pen = (n: number) => ({ kind: "fill" as const, a: sq(0, 0, 10).slice(0, n), b: [] });

  it("takes off one point at a time and leaves the history alone", async () => {
    setDoc(fakeEngine(), [fill("z")]);
    await A.commit({ ...useStore.getState().history.present!.layout, items: [...items(), fill("a", 20)] });
    expect(ids()).toEqual(["z", "a"]);
    useStore.getState().setPen(pen(3));
    onKeyDown(key("z", { ctrlKey: true }));
    expect(useStore.getState().pen?.a).toHaveLength(2);
    onKeyDown(key("z", { ctrlKey: true }));
    onKeyDown(key("z", { ctrlKey: true }));
    expect(useStore.getState().pen).toBeNull();
    await A.whenIdle();
    expect(ids()).toEqual(["z", "a"]);
    // Drawing is over, so the next Ctrl+Z undoes the last edit as usual.
    onKeyDown(key("z", { ctrlKey: true }));
    await A.whenIdle();
    expect(ids()).toEqual(["z"]);
  });

  it("Ctrl+Y does nothing while drawing", async () => {
    setDoc(fakeEngine(), [fill("z")]);
    await A.commit({ ...useStore.getState().history.present!.layout, items: [...items(), fill("a", 20)] });
    A.undoEdit();
    await A.whenIdle();
    expect(ids()).toEqual(["z"]);
    useStore.getState().setPen(pen(2));
    onKeyDown(key("y", { ctrlKey: true }));
    await A.whenIdle();
    expect(ids()).toEqual(["z"]);
    expect(useStore.getState().pen?.a).toHaveLength(2);
  });
});
