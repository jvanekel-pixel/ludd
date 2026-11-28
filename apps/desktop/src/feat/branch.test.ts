/** P7-B2: the Branch and Take out commands, and a branch's dots. The engine is a fake here; the
 *  whole way through the real engine is in branch.engine.test.ts. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "../actions";
import { runCanvasTool, type CanvasCtx } from "../canvas/hooks";
import "../cmd";
import { newDoc } from "../design/layout";
import type { BranchInfo, Doc, Layout, LayoutItem, ObjectItem, PathNode } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { useStore } from "../store";
import { branchedLayout, unbranchedLayout } from "./branch";

const sq = (x: number, w = 10): PathNode[] => [[x, 0, "c"], [x + w, 0, "c"], [x + w, w, "c"], [x, w, "c"]];
const RED = { color: "#cc2222", name: "Red", brand: "", catalog: "" };
const fill = (id: string, x: number, extra: Partial<ObjectItem> = {}): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: sq(x) }, params: {}, thread: RED,
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [], ...extra }) as ObjectItem;

function fakeEngine(answers: Record<string, unknown> = {}) {
  const sent: Record<string, unknown[]> = {};
  return {
    sent,
    async call<R>(method: string, params: Record<string, unknown> = {}): Promise<R> {
      (sent[method] ??= []).push(structuredClone(params));
      if (method === "layout.render") {
        const layout = params.layout as Layout;
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

function setDoc(engine: ReturnType<typeof fakeEngine>, layout: Partial<Layout>, selected: string[], branches?: BranchInfo[]) {
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, ...layout }, images: [] };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc,
    selectedId: selected[0] ?? null, extraIds: selected.slice(1), selectedNode: null, notice: null, tool: "select", pen: null,
    knife: null, stitchEdit: null, ruler: null, angleFor: null,
    design: { items: [], threads: [], blocks: [], records: { x: [], y: [], kind: [] }, branches } as never,
  });
}

const layout = () => useStore.getState().history.present!.layout;
const steps = () => useStore.getState().history.past.length;
const notice = () => useStore.getState().notice?.text ?? "";
const run = (id: string) => A.COMMANDS.find((c) => c.id === id)!.run();

beforeEach(async () => {
  await A.whenIdle();
  while (letGoNewest());
});

describe("the Branch command", () => {
  it("Branch needs two shapes in one thread", async () => {
    const reason = "These shapes are sewn in more than one thread (Fill 1 and Fill 2 differ). A branch sews in one thread: give them the same thread first.";
    const e = fakeEngine({ "layout.branch_plan": { ok: false, reason, order: [] } });
    setDoc(e, { items: [fill("a", 0), fill("b", 10, { thread: { ...RED, color: "#0000ff" } })] }, ["a", "b"]);
    const before = layout();
    await run("layout.branch");
    await A.whenIdle();
    expect(e.sent["layout.branch_plan"]).toEqual([{ layout: before, ids: ["a", "b"] }]);
    expect(layout()).toBe(before);
    expect(steps()).toBe(0);
    expect(notice()).toBe(reason);
  });

  it("applies the engine's order and gives the members a new branch id, in one undo step", async () => {
    const e = fakeEngine({ "layout.branch_plan": { ok: true, reason: "", order: ["a", "c", "b"] } });
    setDoc(e, { items: [fill("a", 0), fill("b", 40), fill("c", 10)] }, ["c", "a"]);
    await run("layout.branch");
    await A.whenIdle();
    const items = layout().items as ObjectItem[];
    expect(items.map((it) => it.id)).toEqual(["a", "c", "b"]);
    expect(items[0].branch).toBeTruthy();
    expect(items[1].branch).toBe(items[0].branch);
    expect(items[2].branch).toBeUndefined();
    expect(steps()).toBe(1);
  });

  it("a shape taken from another branch leaves that one dissolved if it had two", () => {
    const l = { ...newDoc().layout, items: [fill("a", 0, { branch: "old" }), fill("b", 10, { branch: "old" }), fill("c", 20)] as LayoutItem[],
                branches: { old: { start_mm: [0, 0] as [number, number] } } };
    const out = branchedLayout(l, ["a", "c", "b"], ["b", "c"], "new");
    expect((out.items as ObjectItem[]).map((it) => [it.id, it.branch])).toEqual([["a", undefined], ["c", "new"], ["b", "new"]]);
    expect(out.branches).toBeUndefined();
  });
});

describe("Take out of the branch", () => {
  it("Take out dissolves a branch of one", async () => {
    const e = fakeEngine();
    const dots = { b1: { start_mm: [0, 5] as [number, number] }, b2: { end_mm: [1, 1] as [number, number] } };
    setDoc(e, { items: [fill("a", 0, { branch: "b1" }), fill("b", 10, { branch: "b1" }), fill("c", 30, { branch: "b2" }),
                        fill("d", 40, { branch: "b2" }), fill("e", 50, { branch: "b2" })], branches: dots }, ["b"]);
    run("layout.unbranch");
    await A.whenIdle();
    expect((layout().items as ObjectItem[]).map((it) => it.branch)).toEqual([undefined, undefined, "b2", "b2", "b2"]);
    expect(layout().branches).toEqual({ b2: { end_mm: [1, 1] } });
    expect(steps()).toBe(1);
    // A branch that keeps two or more members keeps its dots.
    expect(unbranchedLayout(layout(), ["e"]).branches).toEqual({ b2: { end_mm: [1, 1] } });
    // Nothing selected in a branch: nothing changes, and it says so.
    useStore.setState({ selectedId: "a", extraIds: [] });
    run("layout.unbranch");
    await A.whenIdle();
    expect(steps()).toBe(1);
    expect(notice()).toMatch(/None of the selected shapes is in a branch/);
  });
});

describe("the branch's dots", () => {
  const ctx: CanvasCtx = { toMm: (e) => [e.clientX, e.clientY], pxMm: () => 0.1, redraw: () => undefined };
  const pointer = (x: number, y: number, button = 0) => ({ clientX: x, clientY: y, button, pointerId: 1, target: null }) as unknown as PointerEvent;
  const info: BranchInfo = { id: "b1", items: ["a", "b"], start: [0.5, 0.5], end: [19.5, 9.5], hidden_mm: 1, cuts: 0 };

  it("a dragged dot is stored", async () => {
    setDoc(fakeEngine(), { items: [fill("a", 0, { branch: "b1" }), fill("b", 10, { branch: "b1" })] }, ["b"], [info]);
    expect(runCanvasTool("down", pointer(5, 5), ctx)).toBe(false); // away from the dots: the canvas's own click
    expect(runCanvasTool("down", pointer(19.6, 9.4), ctx)).toBe(true); // the red dot
    expect(heldCount()).toBe(1); // Esc lets go of the drag first
    runCanvasTool("move", pointer(15, 2), ctx);
    expect(runCanvasTool("up", pointer(15, 2), ctx)).toBe(true);
    expect(heldCount()).toBe(0);
    await A.whenIdle();
    expect(layout().branches).toEqual({ b1: { end_mm: [15, 2] } });
    expect(steps()).toBe(1);
  });

  it("Esc while dragging puts the dot back; a shape in no branch shows none", async () => {
    setDoc(fakeEngine(), { items: [fill("a", 0, { branch: "b1" }), fill("b", 10, { branch: "b1" }), fill("c", 30)] }, ["a"], [info]);
    expect(runCanvasTool("down", pointer(0.5, 0.5), ctx)).toBe(true); // the green dot
    expect(letGoNewest()).toBe(true);
    expect(runCanvasTool("up", pointer(8, 8), ctx)).toBe(false);
    await A.whenIdle();
    expect(layout().branches).toBeUndefined();
    useStore.setState({ selectedId: "c" });
    expect(runCanvasTool("down", pointer(0.5, 0.5), ctx)).toBe(false);
  });
});
