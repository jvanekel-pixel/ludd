import { describe, expect, it } from "vitest";
import {
  addImage,
  addObject,
  itemLabel,
  mapObjectNodes,
  newItem,
  objectCenter,
  removeImage,
  scaleImageByMeasure,
  shapeNodes,
  updateImage,
  addItem,
  clearRecolors,
  deleteColor,
  duplicateItem,
  hasRecolors,
  hitTest,
  insertAt,
  jumpsToTrims,
  jumpsToTrimsSetting,
  mirror,
  moveBy,
  newLayout,
  pushHistory,
  recolor,
  redo,
  removeItem,
  reorder,
  rotateBy,
  scaleBy,
  undo,
  type History,
} from "./layout";
import { Kind, type Design, type Doc, type FileItem, type LayoutItem, type ObjectItem } from "./types";

const navy = { color: "#000080", name: "Navy", catalog: "9", brand: "X" };

describe("layout edits", () => {
  it("adds designs offset so they don't overlap exactly", () => {
    const l = addItem(addItem(newLayout("a.pes"), "b.pes"), "c.pes");
    expect(l.items.map((i) => [(i as FileItem).path, i.transform.x])).toEqual([
      ["a.pes", 0],
      ["b.pes", 10],
      ["c.pes", 20],
    ]);
    expect(new Set(l.items.map((i) => i.id)).size).toBe(3);
  });

  it("moves, rotates, scales without touching other items", () => {
    let l = addItem(newLayout("a.pes"), "b.pes");
    const [a, b] = l.items.map((i) => i.id);
    l = moveBy(l, a, 1.234, -2);
    l = rotateBy(rotateBy(l, a, 270), a, 0);
    l = scaleBy(l, a, 1.1);
    expect(l.items[0].transform).toMatchObject({ x: 1.23, y: -2, rotate: -90, scale_x: 1.1, scale_y: 1.1 });
    expect(l.items[1].transform).toMatchObject({ x: 10, y: 10, rotate: 0, scale_x: 1 });
    expect(rotateBy(l, b, 540).items[1].transform.rotate).toBe(180);
  });

  it("mirrors as seen on screen, even after rotating", () => {
    let l = newLayout("a.pes");
    const id = l.items[0].id;
    l = rotateBy(l, id, 30);
    l = mirror(l, id, "x");
    expect(l.items[0].transform).toMatchObject({ flip_x: true, rotate: -30 });
    l = mirror(l, id, "x");
    expect(l.items[0].transform).toMatchObject({ flip_x: false, rotate: 30 });
  });

  it("duplicates next to the original and removes", () => {
    const l = newLayout("a.pes");
    const { layout: d, id } = duplicateItem(l, l.items[0].id);
    expect(d.items).toHaveLength(2);
    expect(d.items[1].id).toBe(id);
    expect(d.items[1].transform.x).toBe(10);
    expect(removeItem(d, id).items).toHaveLength(1);
  });

  it("reorders within bounds", () => {
    const l = addItem(newLayout("a.pes"), "b.pes");
    const a = l.items[0].id;
    expect(reorder(l, a, 1).items.map((i) => (i as FileItem).path)).toEqual(["b.pes", "a.pes"]);
    expect(reorder(l, a, -1)).toBe(l);
  });

  it("recolors every source behind a combined color, and clears", () => {
    const l = addItem(newLayout("a.pes"), "b.pes");
    const r = recolor(l, [
      { item: 0, block: 2 },
      { item: 1, block: 0 },
    ], navy);
    expect(r.items[0].threads).toEqual([null, null, navy]);
    expect(r.items[1].threads).toEqual([navy]);
    expect(hasRecolors(r)).toBe(true);
    expect(hasRecolors(clearRecolors(r))).toBe(false);
  });

  it("deletes colors as ops on the right items", () => {
    const l = addItem(newLayout("a.pes"), "b.pes");
    const d = deleteColor(l, [{ item: 1, block: 3 }]);
    expect(d.items[0].ops).toEqual([]);
    expect(d.items[1].ops).toEqual([{ op: "delete_block", block: 3 }]);
  });

  it("jumps-to-trims is one setting across designs", () => {
    let l = addItem(newLayout("a.pes"), "b.pes");
    l = jumpsToTrims(jumpsToTrims(l, 3), 5);
    expect(l.items.map((i) => i.ops)).toEqual([
      [{ op: "jumps_to_trims", min_mm: 5 }],
      [{ op: "jumps_to_trims", min_mm: 5 }],
    ]);
    expect(jumpsToTrimsSetting(l)).toBe(5);
    expect(jumpsToTrimsSetting(jumpsToTrims(l, null))).toBe(null);
  });
});

function rendered(kinds: number[], item: number[], src: number[], items: Design["items"] = []): Design {
  return {
    path: "a.pes",
    name: "a.pes",
    format: "pes",
    info: { stitches: 0, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 0, height_mm: 0, bounds_mm: [0, 0, 0, 0] },
    threads: [],
    blocks: [],
    records: { x: kinds.map(() => 0), y: kinds.map(() => 0), kind: kinds as Kind[], item, src },
    items,
  };
}

describe("insertAt", () => {
  it("inserts after the source stitch at the player position, skipping added records", () => {
    const d = rendered([Kind.Stitch, Kind.Stitch, Kind.Stitch, Kind.Stitch], [0, 0, -1, 0], [5, 6, -1, 9]);
    const l = newLayout("a.pes");
    expect(insertAt(l, d, 2, "stop")!.items[0].ops).toEqual([{ op: "insert", after: 6, command: "stop" }]);
    expect(insertAt(l, d, 3, "trim")!.items[0].ops).toEqual([{ op: "insert", after: 9, command: "trim" }]);
    expect(insertAt(l, rendered([Kind.Stitch], [-1], [-1]), 0, "stop")).toBe(null);
  });
});

describe("hitTest", () => {
  const d = rendered([], [], [], [
    { id: "a", name: "a", kind: "file", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: [10, 10] },
    { id: "b", name: "b", kind: "file", center_mm: [10, 10], bounds_mm: [5, 5, 15, 15], source_size_mm: [10, 10] },
  ]);
  it("prefers the topmost (last) design", () => {
    expect(hitTest(d, 7, 7)).toBe(1);
    expect(hitTest(d, 2, 2)).toBe(0);
    expect(hitTest(d, 20, 20)).toBe(null);
    expect(hitTest(d, 16, 16, 2)).toBe(1);
  });
});

describe("history", () => {
  it("undoes and redoes, and a new edit drops the redo stack", () => {
    const la = newLayout("a.pes");
    const lb = moveBy(la, la.items[0].id, 1, 0);
    const a: Doc = { layout: la, images: [] };
    const b: Doc = { layout: lb, images: [] };
    const c: Doc = { layout: moveBy(lb, la.items[0].id, 1, 0), images: [] };
    let h: History = { past: [], present: a, future: [] };
    h = pushHistory(pushHistory(h, b), c);
    h = undo(h);
    expect(h.present).toBe(b);
    h = undo(h);
    expect(h.present).toBe(a);
    expect(undo(h)).toBe(h);
    h = redo(h);
    expect(h.present).toBe(b);
    h = pushHistory(h, c);
    expect(h.future).toEqual([]);
    expect(redo(h)).toBe(h);
  });
});

describe("drawn objects", () => {
  const thread = { color: "#ff0000", name: "Red", catalog: "", brand: "" };
  const square = () =>
    addObject(newLayout(), {
      kind: "fill",
      geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"], [0, 10, "c"]] },
      params: {},
      thread,
    });

  it("adds objects and labels them", () => {
    const { layout, id } = square();
    expect(layout.items).toHaveLength(1);
    expect(layout.items[0].id).toBe(id);
    expect(itemLabel(layout.items[0], 0)).toBe("Fill 1");
  });

  it("moves, rotates, resizes and mirrors the points themselves", () => {
    const { layout, id } = square();
    const outline = (l: typeof layout) => (l.items[0] as Extract<LayoutItem, { kind: "fill" }>).geometry.outline;
    expect(outline(moveBy(layout, id, 5, -1))[0]).toEqual([5, -1, "c"]);
    expect(outline(rotateBy(layout, id, 90))[0]).toEqual([10, 0, "c"]); // clockwise about the centre
    expect(outline(scaleBy(layout, id, 2))[2]).toEqual([15, 15, "c"]);
    expect(outline(mirror(layout, id, "x"))[0]).toEqual([10, 0, "c"]);
    // The transform stays untouched: what you see is the points.
    expect(rotateBy(layout, id, 90).items[0].transform).toEqual(newItem("x").transform);
  });

  it("maps every list of points, including holes and both satin rails", () => {
    const o = {
      id: "s",
      kind: "satin",
      geometry: { rail_a: [[0, 0, "c"], [10, 0, "s"]], rail_b: [[0, 4, "c"], [10, 4, "c"]] },
      params: {},
      thread,
      transform: newItem("x").transform,
      threads: [],
      ops: [],
    } as ObjectItem;
    const moved = mapObjectNodes(o, (x, y) => [x + 1, y + 1]) as Extract<ObjectItem, { kind: "satin" }>;
    expect(moved.geometry.rail_a[1]).toEqual([11, 1, "s"]); // curve flags survive
    expect(moved.geometry.rail_b[0]).toEqual([1, 5, "c"]);
    expect(objectCenter(o)).toEqual([5, 2]);
  });
});

describe("pictures", () => {
  const img = {
    name: "a.png", path: "a.png", data_url: "", x: 0, y: 0, width_mm: 50, height_mm: 25, rotate: 0, opacity: 0.5, locked: false, visible: true,
  };
  it("adds, updates, removes and scales by measurement", () => {
    const { images, id } = addImage([], img);
    const moved = updateImage(images, id, { x: 3, locked: true });
    expect(moved[0]).toMatchObject({ x: 3, locked: true, width_mm: 50 });
    expect(removeImage(moved, id)).toEqual([]);
    // Two points measured 20 mm apart on screen are really 1 inch (25.4 mm) apart.
    expect(scaleImageByMeasure(moved[0], 20, 25.4)).toMatchObject({ width_mm: 63.5, height_mm: 31.75 });
    expect(scaleImageByMeasure(moved[0], 0, 10)).toBe(moved[0]);
  });
});

describe("ready-made shapes", () => {
  it("rectangle, circle and star around the centre", () => {
    const rect = shapeNodes("rectangle", 0, 0, 60);
    expect(rect).toEqual([[-30, -21, "c"], [30, -21, "c"], [30, 21, "c"], [-30, 21, "c"]]);
    const circle = shapeNodes("circle", 5, 5, 20);
    expect(circle).toHaveLength(8);
    expect(circle.every((n) => n[2] === "s" && Math.abs(Math.hypot(n[0] - 5, n[1] - 5) - 10) < 0.01)).toBe(true);
    const star = shapeNodes("star", 0, 0, 40);
    expect(star).toHaveLength(10);
    expect(star[0]).toEqual([0, -20, "c"]); // first point straight up
  });
});
