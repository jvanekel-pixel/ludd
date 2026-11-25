/** Stitch editing's Insert, Insert a jump and Lock this jump (P4-B4): the edits they add. A fake
 *  engine draws a small stitch file, turned and resized. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../actions";
import { newDoc } from "../design/layout";
import { Kind, type Design, type FileItem, type Layout, type LayoutOp } from "../design/types";
import { useStore } from "../store";
import { insertJumpNow, insertStitchNow, lockJumpNow } from "./stitchInsert";

/** Turned a quarter and twice the size, 10 mm to the right. */
const T = { x: 10, y: 0, rotate: 90, scale_x: 2, scale_y: 2, flip_x: false, flip_y: false };
const file = (ops: LayoutOp[] = [], threads: FileItem["threads"] = []): FileItem => ({ id: "f", kind: "file", path: "C:/d/f.pes", transform: T, threads, ops });

/** The file: four stitches 2 mm apart, a trim and a jump, two more; a second color with two. */
const FILE: [number, number][] = [
  [0, 0], [2, 0], [4, 0], [6, 0], [-1, Kind.Trim], [-1, Kind.Jump], [30, 0], [32, 0],
  [40, 0], [42, 0],
];
const CENTER = 21; // the middle of the file's stitches, across

/** Where the engine puts a point of the file: about its middle, resized, turned, moved. */
const onHoop = (x: number, y: number): [number, number] => [CENTER - 2 * y + T.x, 2 * (x - CENTER)];

const drawn: Layout[] = [];
let whileDrawing: (() => void) | null = null;

function render(layout: Layout): Design {
  const rec = { x: [] as number[], y: [] as number[], kind: [] as number[], item: [] as number[], src: [] as number[] };
  const push = (x: number, y: number, kind: number, item: number, src: number) => {
    const [hx, hy] = onHoop(x, y);
    rec.x.push(hx);
    rec.y.push(hy);
    rec.kind.push(kind);
    rec.item.push(item);
    rec.src.push(src);
  };
  layout.items.forEach((it, owner) => {
    const ops = (it as FileItem).ops;
    const gone = new Set(ops.flatMap((o) => (o.op === "delete_stitches" ? o.indices : [])));
    const blocks = [FILE.slice(0, 8), FILE.slice(8)];
    let n = 0;
    blocks.forEach((block, b) => {
      const dropped = ops.some((o) => o.op === "delete_block" && o.block === b);
      if (b && !dropped) push(0, 0, Kind.ColorChange, -1, -1);
      for (const [x, other] of block) {
        const src = n++;
        if (dropped) continue;
        const rebuilt = ops.some((o) => o.op === "rebuild") && src >= 6;
        if (x < 0) push(6, 0, other, owner, src);
        else if (!gone.has(src)) push(x, 0, Kind.Stitch, owner, rebuilt ? -1 : src);
        // A lock: three added stitches, the third back on the stitch (after 3, the jump's, then 6).
        if (ops.some((o) => o.op === "lock_jump" && (o.after === src || (o.after === 3 && src === 6))))
          for (const d of [0.35, 0.175, 0]) push(x + d, 0, Kind.Stitch, owner, -1);
        for (const o of ops) if (o.op === "insert_stitch" && o.after === src && !gone.has(o.index)) push(o.x_mm!, o.y_mm!, Kind.Stitch, owner, o.index);
      }
    });
  });
  const [cx, cy] = [CENTER + T.x, 0];
  return {
    path: "", name: "x", format: "layout", info: {} as Design["info"], threads: [], blocks: [], records: rec as Design["records"],
    items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "file", center_mm: [cx, cy], bounds_mm: [0, 0, 1, 1], source_size_mm: [42, 0] })),
  };
}

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const layout = params.layout as Layout;
    drawn.push(layout);
    whileDrawing?.();
    return render(layout) as T;
  },
};

function setDoc(item: FileItem, selected: number[]) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [item] } };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: render(doc.layout),
    selectedId: "f", extraIds: [], notice: null, stitchEdit: { id: "f", selected },
  });
}

const ops = () => (currentLayout()!.items[0] as FileItem).ops;
const past = () => useStore.getState().history.past.length;
const notice = () => useStore.getState().notice?.text ?? "";
const select = (...selected: number[]) => useStore.getState().setStitchEdit({ id: "f", selected });

beforeEach(async () => {
  await whenIdle();
  drawn.length = 0;
  whileDrawing = null;
});

describe("insert a stitch", () => {
  it("adds one halfway to the next, in the file's own frame, and selects it", async () => {
    setDoc(file(), [1]);
    await insertStitchNow();
    // One past the highest number in use (9), halfway between 2 mm and 4 mm along the file.
    expect(ops()).toEqual([{ op: "insert_stitch", after: 1, index: 10, x_mm: 3, y_mm: 0 }]);
    expect(useStore.getState().stitchEdit).toEqual({ id: "f", selected: [10] });
    expect(past()).toBe(1);
    expect(notice()).toMatch(/drag it/);
    expect(drawn).toHaveLength(1); // just the edit's own render
    // Again, from the new one: halfway from it to the next.
    await insertStitchNow();
    expect(ops()[1]).toEqual({ op: "insert_stitch", after: 10, index: 11, x_mm: 3.5, y_mm: 0 });
  });

  it("looks past a stitch's lock for the next one", async () => {
    setDoc(file([{ op: "lock_jump", after: 3 }]), [6]);
    await insertStitchNow();
    // Halfway from 30 mm to 32 mm, not to the lock stitch beside it.
    expect(ops().at(-1)).toMatchObject({ op: "insert_stitch", after: 6, x_mm: 31, y_mm: 0 });
    // A box round a locked stitch takes in its lock stitches, which have no number.
    setDoc(file([{ op: "lock_jump", after: 3 }]), [-1, 6, -1]);
    await insertStitchNow();
    expect(ops().at(-1)).toMatchObject({ after: 6, x_mm: 31 });
    setDoc(file([{ op: "lock_jump", after: 3 }]), [3]);
    await lockJumpNow();
    expect(notice()).toMatch(/locked already/);
    await insertJumpNow();
    expect(notice()).toMatch(/jump already/);
  });

  it("counts every number in use, even ones edits have taken off the screen", async () => {
    setDoc(file([{ op: "delete_stitches", indices: [9] }, { op: "insert_stitch", after: 0, index: 14, x_mm: 1, y_mm: 0 }, { op: "delete_stitches", indices: [14] }]), [1]);
    await insertStitchNow();
    expect(ops().at(-1)).toMatchObject({ index: 15 });
  });

  it("looks at the whole file when a deleted color or a rebuild hides numbers", async () => {
    setDoc(file([{ op: "delete_block", block: 1 }]), [1]);
    await insertStitchNow();
    expect(ops().at(-1)).toMatchObject({ op: "insert_stitch", index: 10 });
    // That look keeps the item sewing from LUDD's own copy of the file, as it did.
    expect((drawn[0].items[0] as FileItem).ops).toEqual([{ op: "delete_stitches", indices: [] }]);

    drawn.length = 0;
    setDoc(file([{ op: "rebuild" }]), [1]);
    await insertStitchNow();
    expect(ops().at(-1)).toMatchObject({ index: 10 });
    expect((drawn[0].items[0] as FileItem).ops).toEqual([]);

    drawn.length = 0;
    setDoc(file([{ op: "rebuild" }], [{ color: "#000000", name: "", brand: "", catalog: "" }]), [1]);
    await insertStitchNow();
    expect((drawn[0].items[0] as FileItem).ops).toEqual([]); // its new colors keep the copy already
  });

  it("needs one stitch with another after it in the same color", async () => {
    for (const [selected, why] of [[[], /one stitch/], [[1, 2], /one stitch/], [[-1], /repair or a lock/], [[9], /last stitch/], [[7], /last stitch/]] as const) {
      setDoc(file(), [...selected]);
      await insertStitchNow();
      expect(notice(), String(selected)).toMatch(why);
      expect(ops(), String(selected)).toEqual([]);
    }
  });

  it("adds nothing if the design changes while it's being worked out", async () => {
    setDoc(file([{ op: "delete_block", block: 1 }]), [1]);
    whileDrawing = () => {
      whileDrawing = null;
      const h = useStore.getState().history;
      const d = h.present!;
      useStore.setState({ history: { ...h, present: { ...d, layout: { ...d.layout, items: [{ ...file(), ops: [] }] } } } });
    };
    await insertStitchNow();
    expect(ops()).toEqual([]);
    expect(notice()).toMatch(/try again/);
  });
});

describe("insert a jump, lock a jump", () => {
  it("turns the move after the stitch into a jump, unless it is one already", async () => {
    setDoc(file(), [1]);
    await insertJumpNow();
    expect(ops()).toEqual([{ op: "insert_jump", after: 1 }]);
    expect(useStore.getState().stitchEdit?.selected).toEqual([1]);
    expect(notice()).toMatch(/lock both sides/i);
    setDoc(file(), [3]);
    await insertJumpNow();
    expect(notice()).toMatch(/jump already/);
    setDoc(file(), [9]);
    await insertJumpNow();
    expect(notice()).toMatch(/last stitch/);
    expect(ops()).toEqual([]);
  });

  it("locks only at a jump, and only once", async () => {
    setDoc(file(), [1]);
    await lockJumpNow();
    expect(notice()).toMatch(/last stitch before a jump/);
    expect(ops()).toEqual([]);
    select(3);
    await lockJumpNow();
    expect(ops()).toEqual([{ op: "lock_jump", after: 3 }]);
    expect(notice()).toMatch(/Locked both sides/);
    await lockJumpNow();
    expect(notice()).toMatch(/locked already/);
    expect(ops()).toHaveLength(1);
  });
});
