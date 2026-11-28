/** Branches through edits, copies and the order list (Phase 7 audit, finding 4). */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "../actions";
import { withOrder } from "../ai";
import "../cmd";
import { addOffset, mergeSelected } from "../features";
import { useStore } from "../store";
import { branchOf, dissolveSingles, inSewingOrder, moveShown } from "./branches";
import { duplicateItems, newDoc, repeatItem } from "./layout";
import type { BranchInfo, Doc, Layout, LayoutItem, ObjectItem, PathNode } from "./types";

const RED = { color: "#cc2222", name: "Red", brand: "", catalog: "" };
const sq = (x: number): PathNode[] => [[x, 0, "c"], [x + 10, 0, "c"], [x + 10, 10, "c"], [x, 10, "c"]];
const fill = (id: string, branch?: string, x = 0): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: sq(x) }, params: {}, thread: RED, ...(branch ? { branch } : {}),
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as ObjectItem;
const lay = (items: LayoutItem[], dots?: Layout["branches"]): Layout => ({ ...newDoc().layout, items, ...(dots ? { branches: dots } : {}) });
/** The items' ids and branches, as "a:B b c:C". */
const shape = (items: readonly LayoutItem[]) => items.map((it) => (branchOf(it) ? `${it.id}:${branchOf(it)}` : it.id)).join(" ");
const B_DOTS = { B: { start_mm: [0, 0] as [number, number] } };

describe("keeping branches whole", () => {
  it("a branch of one is dissolved with its dots; anything else is left as it is", () => {
    const l = lay([fill("a", "B"), fill("b"), fill("c", "C"), fill("d", "C")], { B: { end_mm: [1, 1] }, C: { end_mm: [2, 2] } });
    const done = dissolveSingles(l);
    expect(shape(done.items)).toBe("a b c:C d:C");
    expect(done.branches).toEqual({ C: { end_mm: [2, 2] } });
    expect(dissolveSingles(done)).toBe(done);
    expect(dissolveSingles(lay([fill("a", "B")], B_DOTS))).not.toHaveProperty("branches");
  });

  it("one duplicated shape of a branch joins it, after its last shape; others go after themselves", () => {
    const l = lay([fill("a", "B"), fill("b", "B"), fill("x"), fill("y", "C"), fill("z", "C")], B_DOTS);
    const r = duplicateItems(l, ["a", "x"]);
    const [a2, x2] = r.ids;
    expect(shape(r.layout.items)).toBe(`a:B b:B ${a2}:B x ${x2} y:C z:C`);
    expect(r.layout.branches).toEqual(B_DOTS);
  });

  it("two duplicated shapes of a branch make a branch of their own, without its dots", () => {
    const l = lay([fill("a", "B"), fill("b", "B"), fill("c", "B"), fill("x")], B_DOTS);
    const r = duplicateItems(l, ["c", "a"]); // whichever was picked first, they stay in sewing order
    const [c2, a2] = r.ids;
    const own = branchOf(r.layout.items.find((it) => it.id === a2)!)!;
    expect(own).toBeTruthy();
    expect(own).not.toBe("B");
    expect(shape(r.layout.items)).toBe(`a:B b:B c:B ${a2}:${own} ${c2}:${own} x`);
    expect(r.layout.branches).toEqual(B_DOTS);
  });

  it("Repeat's copies of a branch shape join the branch, after its last shape, in the pattern's order", () => {
    const l = lay([fill("a", "B"), fill("b", "B"), fill("x")]);
    const r = repeatItem(l, "a", [5, 5], [10, 10], { kind: "row", columns: 3, rows: 1, step_x: 20, step_y: 0 });
    expect(shape(r.layout.items)).toBe(`a:B b:B ${r.ids[0]}:B ${r.ids[1]}:B x`);
  });
});

function fakeEngine(branches: () => BranchInfo[] | undefined = () => undefined, answers: Record<string, unknown> = {}) {
  return {
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      if (method !== "layout.render") return (answers[method] ?? null) as T;
      const layout = params.layout as Layout;
      return {
        path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [] }, branches: branches(),
        info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
        items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })),
      } as T;
    },
  };
}

function setDoc(layout: Layout, selected: string[], branches?: () => BranchInfo[] | undefined, answers?: Record<string, unknown>) {
  const doc: Doc = { layout, images: [] };
  useStore.setState({
    engine: fakeEngine(branches, answers) as never, history: { past: [], present: doc, future: [] }, savedDoc: doc,
    selectedId: selected[0] ?? null, extraIds: selected.slice(1), selectedNode: null, notice: null, tool: "select", pen: null,
    design: { items: [], threads: [], blocks: [], records: { x: [], y: [], kind: [] }, branches: branches?.() } as never,
  });
}

const now = () => useStore.getState().history.present!.layout;
const run = async (id: string) => {
  await A.COMMANDS.find((c) => c.id === id)!.run();
  await A.whenIdle();
};
const select = (...ids: string[]) => useStore.getState().setSelection(ids[0], ids.slice(1));

beforeEach(async () => {
  await A.whenIdle();
});

describe("branches through the app's own commands", () => {
  it("deleting a branch's other shape leaves no branch of one behind", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B"), fill("x")], B_DOTS), ["b"]);
    await run("arrange.delete");
    expect(shape(now().items)).toBe("a x");
    expect(now()).not.toHaveProperty("branches");
  });

  it("cutting a shape out of a branch of two dissolves it, and pasting it back gives an ordinary shape", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B")], B_DOTS), ["b"]);
    await run("edit.cut");
    expect(shape(now().items)).toBe("a");
    expect(now()).not.toHaveProperty("branches");
    await run("edit.paste");
    expect(now().items.map(branchOf)).toEqual([undefined, undefined]);
  });

  it("one pasted shape joins its branch, right after the branch's last shape", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B"), fill("c", "B"), fill("x")]), ["a"]);
    await run("edit.copy");
    await run("edit.paste");
    const added = now().items[3].id;
    expect(shape(now().items)).toBe(`a:B b:B c:B ${added}:B x`);
  });

  it("two pasted shapes of a branch make their own branch, at the end", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B"), fill("x")], B_DOTS), ["a", "b"]);
    await run("edit.copy");
    await run("edit.paste");
    const [p, q] = now().items.slice(3);
    expect(branchOf(p)).toBeTruthy();
    expect([branchOf(q), branchOf(p) === "B"]).toEqual([branchOf(p), false]);
    expect(shape(now().items.slice(0, 3))).toBe("a:B b:B x");
    expect(now().branches).toEqual(B_DOTS);
  });

  it("a shape pasted into a design without its branch is an ordinary shape", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B")]), ["a"]);
    await run("edit.copy");
    setDoc(lay([fill("x")]), []);
    await run("edit.paste");
    expect(now().items.map(branchOf)).toEqual([undefined, undefined]);
  });

  it("duplicating with Ctrl+D follows the same rule", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B"), fill("x")]), []);
    select("a", "b");
    await run("arrange.duplicate");
    const [, , p, q] = now().items;
    expect([branchOf(p) === "B", branchOf(p) === branchOf(q)]).toEqual([false, true]);
  });
});

/** The second audit's sweep: every command that reorders shapes or makes new ones out of existing
 *  ones leaves a branch's shapes together; pieces of a shape stay in it, and new shapes that are
 *  neither pieces nor copies go after the branch, as ordinary shapes. (The knife, cut-out and Sew in
 *  the shortest order are tested with the real engine in feat/branch.engine.test.ts; Sort and
 *  Combine colors, which reorder what the engine sews, in engine/tests/test_branch.py.) */
describe("new shapes and reorders keep branches whole", () => {
  const ABC_X = () => lay([fill("a", "B"), fill("b", "B"), fill("c", "B"), fill("x", undefined, 40)], B_DOTS);
  const ring: PathNode[] = sq(-2);

  it("a satin border round a branch's shape is sewn after the branch, as an ordinary shape", async () => {
    setDoc(ABC_X(), ["a"]);
    await run("object.border");
    const added = now().items[3];
    expect(added.kind).toBe("satin");
    expect(shape(now().items)).toBe(`a:B b:B c:B ${added.id} x`);
  });

  it("an outline round a branch's shape is sewn after the branch, as an ordinary shape", async () => {
    setDoc(ABC_X(), ["b"], undefined, { "shape.offset": { rings: [ring] } });
    await addOffset({ distance_mm: 2, as: "run", width_mm: 2, holes: false });
    await A.whenIdle();
    const added = now().items[3];
    expect(shape(now().items)).toBe(`a:B b:B c:B ${added.id} x`);
  });

  const merge = async (layout: Layout, selected: string[]) => {
    setDoc(layout, selected, undefined, { "shape.merge": { geometry: { outline: sq(0) } } });
    await mergeSelected();
    await A.whenIdle();
  };

  it("shapes merged from one branch stay in it", async () => {
    await merge(ABC_X(), ["a", "c"]);
    expect(shape(now().items)).toBe("a:B b:B x");
    expect(now().branches).toEqual(B_DOTS);
  });

  it("a shape merged with one outside its branch is ordinary, sewn after the branch", async () => {
    await merge(ABC_X(), ["a", "x"]);
    expect(shape(now().items)).toBe("b:B c:B a");
    await merge(ABC_X(), ["x", "b"]); // (and where the first one picked is outside it, it stays there)
    expect(shape(now().items)).toBe("a:B c:B x");
    await merge(lay([fill("a", "B"), fill("b", "B"), fill("y", "C"), fill("z", "C")]), ["a", "y"]);
    expect(shape(now().items)).toBe("b a z"); // both branches left with one shape: dissolved
    await merge(lay([fill("a", "B"), fill("b", "B"), fill("x")], B_DOTS), ["a", "x"]);
    expect(shape(now().items)).toBe("b a");
    expect(now()).not.toHaveProperty("branches");
  });

  it("lettering broken into shapes keeps its branch", async () => {
    const text = { ...fill("t", "B"), kind: "text", text: "Hi" } as unknown as LayoutItem;
    const letter = { kind: "fill", geometry: { outline: sq(0) }, params: {}, thread: RED };
    setDoc(lay([fill("a", "B"), text, fill("c", "B")]), ["t"], undefined, { "text.to_shapes": { objects: [letter, letter] } });
    await run("text.toShapes");
    const [, p, q] = now().items;
    expect(shape(now().items)).toBe(`a:B ${p.id}:B ${q.id}:B c:B`);
  });

  it("a shape turned into an applique leaves its branch in the same step", async () => {
    setDoc(lay([fill("a", "B"), fill("b", "B"), fill("c", "B")], B_DOTS), ["b"]);
    await A.convertObject("b", "applique");
    await A.whenIdle();
    expect(shape(now().items)).toBe("a:B b c:B");
    expect(useStore.getState().history.past).toHaveLength(1);
    setDoc(lay([fill("a", "B"), fill("b", "B")], B_DOTS), ["b"]);
    await A.convertObject("b", "applique");
    await A.whenIdle();
    expect(shape(now().items)).toBe("a b");
    expect(now()).not.toHaveProperty("branches");
    expect(useStore.getState().history.past).toHaveLength(1);
  });

  it("an accepted AI sewing order keeps each branch's shapes together", () => {
    const l = lay([fill("a", "B"), fill("b", "B"), fill("x"), fill("y", "C"), fill("z", "C")]);
    expect(shape(withOrder(l, ["y", "x", "a", "z", "b"]).items)).toBe("y:C z:C x a:B b:B");
  });
});

// The audit's case: items d, a, c, b of one branch sew d, c, a, b.
const SEWN: BranchInfo[] = [{ id: "B", items: ["d", "c", "a", "b"], start: [0, 0], end: [1, 1], hidden_mm: 0, cuts: 0 }];
const FOUR = () => lay([fill("d", "B"), fill("a", "B"), fill("c", "B"), fill("b", "B")]);
const ids = (items: readonly LayoutItem[]) => items.map((it) => it.id).join("");

describe("the order shown", () => {
  it("lists a branch's shapes in the order they sew, everything else where it is", () => {
    const l = lay([fill("x"), ...FOUR().items, fill("y")]);
    expect(ids(inSewingOrder(l.items, SEWN))).toBe("xdcaby");
    expect(ids(inSewingOrder(l.items, undefined))).toBe("xdacby");
  });

  it("a shape moved past a branch leaves the branch's own order alone", () => {
    const l = lay([fill("x"), ...FOUR().items]);
    const moved = moveShown(l, inSewingOrder(l.items, SEWN), "x", 4);
    expect(ids(moved.items)).toBe("dacbx");
  });

  it("a shape moved into a branch lands between the shapes shown around it", () => {
    const l = lay([fill("x"), ...FOUR().items]);
    expect(ids(moveShown(l, inSewingOrder(l.items, SEWN), "x", 2).items)).toBe("dcxab");
  });

  it("a branch's shape moved among its own takes the order shown", () => {
    const l = FOUR();
    expect(ids(moveShown(l, inSewingOrder(l.items, SEWN), "b", 1).items)).toBe("dbca");
    expect(ids(moveShown(l, inSewingOrder(l.items, SEWN), "d", 3).items)).toBe("cabd");
  });

  it("a move the branch takes back says why", async () => {
    setDoc(FOUR(), ["c"], () => SEWN); // the engine keeps choosing d, c, a, b
    await A.moveItemTo("c", 2);
    await A.whenIdle();
    expect(useStore.getState().notice?.text).toContain("A branch sews its shapes in the order LUDD picks");
  });

  it("a move the branch answers with another order of its own says so too", async () => {
    // Seen in the app: c moved up, and the branch then sewed a, b, c, d.
    let picked: BranchInfo[] = SEWN;
    setDoc(FOUR(), ["c"], () => picked);
    picked = [{ ...SEWN[0], items: ["a", "b", "c", "d"] }];
    await A.moveItemTo("c", 0);
    await A.whenIdle();
    expect(useStore.getState().notice?.text).toContain("A branch sews its shapes in the order LUDD picks");
  });

  it("an ordinary move says nothing", async () => {
    setDoc(lay([fill("x"), fill("y")]), ["x"]);
    await A.moveItemTo("x", 1);
    await A.whenIdle();
    expect(ids(now().items)).toBe("yx");
    expect(useStore.getState().notice).toBeNull();
  });
});
