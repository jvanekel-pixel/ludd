import { describe, expect, it } from "vitest";
import {
  addImage,
  addObject,
  itemLabel,
  mapObjectNodes,
  newItem,
  objectCenter,
  objectNodeLists,
  renameItem,
  removeImage,
  scaleImageByMeasure,
  shapeNodes,
  updateImage,
  addItem,
  clearRecolors,
  deleteColor,
  centreItem,
  moveItem,
  stretchItem,
  transformTogether,
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
  scaleDesign,
  shrinkToFit,
  undo,
  type History,
} from "./layout";
import { Kind, type Design, type Doc, type FileItem, type Layout, type LayoutItem, type ObjectItem, type SatinColumn, type TextItem } from "./types";

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

  it("QA C13: a copy of a drawn shape has its points moved, not a transform", () => {
    const { layout: l, id } = addObject(newLayout(), { kind: "fill", geometry: { outline: [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"]] }, params: {}, thread: navy });
    const { layout: d, id: copy } = duplicateItem(l, id);
    const c = d.items.find((it) => it.id === copy) as ObjectItem;
    expect(c.transform).toMatchObject({ x: 0, y: 0 });
    expect((c.geometry as { outline: number[][] }).outline[0].slice(0, 2)).toEqual([10, 10]);
  });

  it("centres a stitch file on the hoop (many PES files start at a corner)", () => {
    const l = newLayout("a.pes");
    const id = l.items[0].id;
    const c = centreItem(l, id, [44.6, 29.1]);
    expect(c.items[0].transform).toMatchObject({ x: -44.6, y: -29.1 });
    expect(centreItem(l, id, [0.2, -0.1])).toBe(l); // already there
    expect(centreItem(l, id, [44.6, 29.1], [10, 10]).items[0].transform).toMatchObject({ x: -34.6, y: -19.1 });
  });

  it("moves an item to any place in the sewing order (drag and drop)", () => {
    let l = newLayout("a.pes");
    for (const f of ["b.pes", "c.pes", "d.pes"]) l = addItem(l, f);
    const names = (x: typeof l) => x.items.map((i) => (i as FileItem).path[0]).join("");
    const d = l.items[3].id;
    expect(names(moveItem(l, d, 0))).toBe("dabc");
    expect(names(moveItem(l, l.items[0].id, 2))).toBe("bcad");
    expect(names(moveItem(l, d, 99))).toBe("abcd"); // past the end: last, unchanged
    expect(moveItem(l, d, 3)).toBe(l);
  });

  it("stretches from a side: one way only, the opposite side staying put", () => {
    const { layout: l, id } = addObject(newLayout(), { kind: "fill", geometry: { outline: [[0, 0, "c"], [20, 0, "c"], [20, 10, "c"], [0, 10, "c"]] }, params: {}, thread: navy });
    // Pull the right side out to twice as wide; the left side (x = 0) stays.
    const out = transformTogether(l, [id], { [id]: [10, 5] }, [0, 5], { stretch: [2, 1] });
    const xs = ((out.items[0] as ObjectItem).geometry as { outline: number[][] }).outline.map((n) => n[0]);
    expect([Math.min(...xs), Math.max(...xs)]).toEqual([0, 40]);
    // A stitch file turned on its side stretches its own height to get wider on screen.
    const f = { ...newLayout("a.pes"), items: newLayout("a.pes").items.map((it) => ({ ...it, transform: { ...it.transform, rotate: 90 } })) };
    expect(stretchItem(f, f.items[0].id, 2, 1).items[0].transform).toMatchObject({ scale_x: 1, scale_y: 2 });
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
    // One layout-wide setting (QA: it now covers designs added later too); no per-design ops.
    expect(l.jumps_to_trims).toBe(5);
    expect(l.items.map((i) => i.ops)).toEqual([[], []]);
    expect(jumpsToTrimsSetting(addItem(l, "c.pes"))).toBe(5);
    expect(jumpsToTrimsSetting(jumpsToTrims(l, null))).toBe(null);
    // Older projects kept it on each design: still read, and replaced when changed.
    const old = { ...addItem(newLayout("a.pes"), "b.pes") };
    old.items = old.items.map((it) => ({ ...it, ops: [{ op: "jumps_to_trims" as const, min_mm: 4 }] }));
    expect(jumpsToTrimsSetting(old)).toBe(4);
    const off = jumpsToTrims(old, null);
    expect(off.items.every((it) => it.ops.length === 0)).toBe(true);
    expect(jumpsToTrimsSetting(off)).toBe(null);
  });

  it("shrinkToFit offers a small resize only when a design is a little too big", () => {
    expect(shrinkToFit({ width_mm: 99, height_mm: 50 }, { width_mm: 100, height_mm: 100 })).toBe(null);
    const s = shrinkToFit({ width_mm: 100.4, height_mm: 50 }, { width_mm: 100, height_mm: 100 })!;
    expect(s).toBeLessThan(1);
    expect(100.4 * s).toBeLessThanOrEqual(100);
    expect(shrinkToFit({ width_mm: 120, height_mm: 50 }, { width_mm: 100, height_mm: 100 })).toBe(null);
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

describe("lettering", () => {
  const text = (patch: Partial<TextItem>) => ({ id: "t", kind: "text", text: "Happy\nBirthday", threads: [], ...patch }) as unknown as TextItem;
  const layout = (t: TextItem) => ({ items: [t] }) as unknown as Layout;

  it("names two lines on one", () => {
    expect(itemLabel(text({}), 0)).toBe("“Happy Birthday”");
  });

  it("puts back the original colors of single letters too", () => {
    const red = { color: "#ff0000", name: "Red", brand: "", catalog: "" };
    const l = layout(text({ letter_edits: { "1": { thread: red, dx_mm: 2 }, "2": { thread: red } } }));
    expect(hasRecolors(l)).toBe(true);
    const back = clearRecolors(l);
    expect(hasRecolors(back)).toBe(false);
    // The move stays; a letter left with nothing changed has no entry.
    expect((back.items[0] as TextItem).letter_edits).toEqual({ "1": { dx_mm: 2 } });
    expect((clearRecolors(layout(text({ letter_edits: { "2": { thread: red } } }))).items[0] as TextItem).letter_edits).toBeUndefined();
  });
});

describe("insertAt", () => {
  it("inserts after the source stitch at the player position, skipping added records", () => {
    const d = rendered([Kind.Stitch, Kind.Stitch, Kind.Stitch, Kind.Stitch], [0, 0, -1, 0], [5, 6, -1, 9]);
    const l = newLayout("a.pes");
    expect(insertAt(l, d, 2, "stop")!.items[0].ops).toEqual([{ op: "insert", after: 6, command: "stop" }]);
    expect(insertAt(l, d, 3, "trim")!.items[0].ops).toEqual([{ op: "insert", after: 9, command: "trim" }]);
    expect(insertAt(l, rendered([Kind.Stitch], [-1], [-1]), 0, "stop")).toBe(null);
  });

  it("remembers how many records a drawn shape had, so a changed shape drops the stop instead of moving it", () => {
    const { layout } = addObject({ ...newLayout("a.pes"), items: [] }, {
      kind: "run", geometry: { nodes: [[0, 0, "c"], [10, 0, "c"]], closed: false }, params: {}, thread: { color: "#000000", name: "", brand: "", catalog: "" },
    } as never);
    const d = rendered([Kind.Stitch, Kind.Stitch, Kind.Trim, Kind.Stitch], [0, 0, 0, 0], [0, 1, 2, 3]);
    expect(insertAt(layout, d, 1, "stop")!.items[0].ops).toEqual([{ op: "insert", after: 1, command: "stop", n: 4 }]);
  });
});

describe("scaleDesign", () => {
  it("resizes every design about the middle of the whole design", () => {
    const l = addItem(newLayout("a.pes"), "b.pes");
    const d = rendered([], [], [], [
      { id: l.items[0].id, name: "a", kind: "file", center_mm: [0, 0], bounds_mm: [-10, -10, 10, 10], source_size_mm: [20, 20] },
      { id: l.items[1].id, name: "b", kind: "file", center_mm: [80, 0], bounds_mm: [70, -10, 90, 10], source_size_mm: [20, 20] },
    ]);
    d.info.bounds_mm = [-10, -10, 90, 10];
    const s = scaleDesign(l, d, 0.9);
    expect(s.items.map((it) => it.transform.scale_x)).toEqual([0.9, 0.9]);
    // The middle is x = 40: each design moves in towards it by 10%.
    expect(s.items[0].transform.x - l.items[0].transform.x).toBeCloseTo(4, 2);
    expect(s.items[1].transform.x - l.items[1].transform.x).toBeCloseTo(-4, 2);
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
    const moved = mapObjectNodes(o, (x, y) => [x + 1, y + 1]) as Extract<ObjectItem, { kind: "satin" }> & { geometry: SatinColumn };
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

describe("renaming and satin ribbons", () => {
  const ribbon = {
    id: "r",
    kind: "satin",
    geometry: { nodes: [[0, 0, "c"], [20, 0, "s"]], width_mm: 3 },
    params: {},
    thread: { color: "#000000", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  } as unknown as ObjectItem;
  const layout = { version: 1, items: [ribbon] } as unknown as Parameters<typeof renameItem>[0];

  it("renames an item, and an empty name puts the standard one back", () => {
    const named = renameItem(layout, "r", "  Left eye outline ");
    expect(named.items[0]).toMatchObject({ name: "Left eye outline" });
    expect(itemLabel(named.items[0], 0)).toBe("Left eye outline");
    const back = renameItem(named, "r", "   ");
    expect("name" in back.items[0]).toBe(false);
    expect(itemLabel(back.items[0], 0)).toBe("Satin 1");
  });

  it("moves a ribbon's centre line and scales its width with it", () => {
    expect(objectNodeLists(ribbon)).toEqual([[[0, 0, "c"], [20, 0, "s"]]]);
    const big = scaleBy(layout, "r", 2).items[0] as ObjectItem & { geometry: { width_mm: number; nodes: unknown[] } };
    expect(big.geometry.width_mm).toBe(6);
    expect(big.geometry.nodes).toEqual([[-10, 0, "c"], [30, 0, "s"]]);
    const moved = mapObjectNodes(ribbon, (x, y) => [x + 1, y]) as ObjectItem & { geometry: { width_mm: number } };
    expect(moved.geometry.width_mm).toBe(3);
  });
});
