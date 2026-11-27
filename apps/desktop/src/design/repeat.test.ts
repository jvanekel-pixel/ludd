import { describe, expect, it } from "vitest";
import { addObject, mirror, newLayout, objectCenter, repeatItem, rotateBy, setGroup, transformTogether, type RepeatSpec } from "./layout";
import type { ObjectItem } from "./types";

const square = () => {
  const { layout, id } = addObject(newLayout(), {
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"], [0, 10, "c"]] },
    params: {},
    thread: { color: "#000", name: "", catalog: "", brand: "" },
  });
  return { layout, id };
};
const centers = (items: unknown[]) => (items as ObjectItem[]).map((o) => objectCenter(o).map((v) => Math.round(v * 100) / 100));

describe("repeat", () => {
  it("lays out a grid of copies after the original", () => {
    const { layout, id } = square();
    const r = repeatItem(layout, id, [5, 5], [10, 10], { kind: "row", columns: 3, rows: 2, step_x: 15, step_y: 12 });
    expect(r.ids).toHaveLength(5);
    expect(centers(r.layout.items)).toEqual([[5, 5], [20, 5], [35, 5], [5, 17], [20, 17], [35, 17]]);
  });

  it("puts copies round a circle below the original", () => {
    const { layout, id } = square();
    const r = repeatItem(layout, id, [5, 5], [10, 10], { kind: "circle", count: 4, radius: 20, turn: true });
    // Clockwise on screen, like turning a design: right, bottom, left.
    expect(centers(r.layout.items)).toEqual([[5, 5], [25, 25], [5, 45], [-15, 25]]);
  });

  it("mirrors four ways about the corner past the original", () => {
    const { layout, id } = square();
    const r = repeatItem(layout, id, [5, 5], [10, 10], { kind: "mirror4", gap: 2 });
    expect(centers(r.layout.items)).toEqual([[5, 5], [17, 5], [5, 17], [17, 17]]);
    // The copy on the right is a mirror image: its first point is now on the right.
    const right = r.layout.items[1] as ObjectItem;
    expect((right as Extract<ObjectItem, { kind: "fill" }>).geometry.outline[0][0]).toBeCloseTo(22);
  });
});

/** A fill with line, curve and corner points, to repeat. Its middle and size as the canvas
 *  would report them. */
const wing = () =>
  addObject(newLayout(), {
    kind: "fill",
    geometry: { outline: [[2, 1, "c"], [12, 1, "l"], [14, 6, "s"], [9, 11, "s"], [2, 9, "c"]] },
    params: { angle_deg: 30 },
    thread: { color: "#000", name: "", catalog: "", brand: "" },
  });
const WING_AT: [number, number] = [8, 6];
const WING_SIZE: [number, number] = [12, 10];
type Fill = Extract<ObjectItem, { kind: "fill" }>;
const copies = (spec: RepeatSpec) => {
  const { layout, id } = wing();
  return (repeatItem(layout, id, WING_AT, WING_SIZE, spec).layout.items.slice(1) as Fill[]).map((o) => [o.geometry.outline, o.params.angle_deg]);
};

describe("the repeat modes there were before give exactly the same copies", () => {
  it("row, circle and mirror4 give the same copies as before", () => {
    // Recorded from the code before the repeat modes were added: never change these.
    expect(copies({ kind: "row", columns: 3, rows: 2, step_x: 17, step_y: 13 })).toEqual([
      [[[19, 1, "c"], [29, 1, "l"], [31, 6, "s"], [26, 11, "s"], [19, 9, "c"]], 30],
      [[[36, 1, "c"], [46, 1, "l"], [48, 6, "s"], [43, 11, "s"], [36, 9, "c"]], 30],
      [[[2, 14, "c"], [12, 14, "l"], [14, 19, "s"], [9, 24, "s"], [2, 22, "c"]], 30],
      [[[19, 14, "c"], [29, 14, "l"], [31, 19, "s"], [26, 24, "s"], [19, 22, "c"]], 30],
      [[[36, 14, "c"], [46, 14, "l"], [48, 19, "s"], [43, 24, "s"], [36, 22, "c"]], 30],
    ]);
    expect(copies({ kind: "circle", count: 5, radius: 22, turn: true })).toEqual([
      [[[31.82, 13.95, "c"], [34.91, 23.46, "l"], [30.77, 26.91, "s"], [24.47, 23.7, "s"], [24.21, 16.42, "c"]], 102],
      [[[28.72, 46.32, "c"], [20.63, 52.2, "l"], [16.08, 49.33, "s"], [17.18, 42.34, "s"], [24.02, 39.85, "c"]], 174],
      [[[-3.01, 53.37, "c"], [-11.1, 47.49, "l"], [-9.78, 42.27, "s"], [-2.8, 41.17, "s"], [1.69, 46.9, "c"]], 66],
      [[[-19.53, 25.36, "c"], [-16.44, 15.85, "l"], [-11.07, 15.49, "s"], [-7.86, 21.79, "s"], [-11.92, 27.83, "c"]], 138],
    ]);
    expect(copies({ kind: "circle", count: 3, radius: 15, turn: false })).toEqual([
      [[[14.99, 23.5, "c"], [24.99, 23.5, "l"], [26.99, 28.5, "s"], [21.99, 33.5, "s"], [14.99, 31.5, "c"]], 30],
      [[[-10.99, 23.5, "c"], [-0.99, 23.5, "l"], [1.01, 28.5, "s"], [-3.99, 33.5, "s"], [-10.99, 31.5, "c"]], 30],
    ]);
    expect(copies({ kind: "mirror4", gap: 3 })).toEqual([
      [[[29, 1, "c"], [19, 1, "l"], [17, 6, "s"], [22, 11, "s"], [29, 9, "c"]], 150],
      [[[2, 24, "c"], [12, 24, "l"], [14, 19, "s"], [9, 14, "s"], [2, 16, "c"]], 150],
      [[[29, 24, "c"], [19, 24, "l"], [17, 19, "s"], [22, 14, "s"], [29, 16, "c"]], 30],
    ]);
  });

  it("a wreath centered below the design is the old circle, said either way", () => {
    expect(copies({ kind: "circle", count: 5, radius: 22, turn: true, center: "below", mirror: false })).toEqual(
      copies({ kind: "circle", count: 5, radius: 22, turn: true }),
    );
  });
});

type Spot = [number, number];
/** A point mirrored in the line through `c` at `deg` degrees. */
const reflect = ([x, y]: Spot, c: Spot, deg: number): Spot => {
  const a = (2 * deg * Math.PI) / 180;
  const [dx, dy] = [x - c[0], y - c[1]];
  return [c[0] + dx * Math.cos(a) + dy * Math.sin(a), c[1] + dx * Math.sin(a) - dy * Math.cos(a)];
};
/** Every point of every copy, the original first. */
const outlines = (spec: RepeatSpec) => {
  const { layout, id } = wing();
  return (repeatItem(layout, id, WING_AT, WING_SIZE, spec).layout.items as Fill[]).map((o) => o.geometry.outline.map(([x, y]) => [x, y] as Spot));
};
const expectSame = (got: Spot[], want: Spot[]) => {
  expect(got).toHaveLength(want.length);
  want.forEach(([x, y], i) => {
    expect(got[i][0]).toBeCloseTo(x, 1);
    expect(got[i][1]).toBeCloseTo(y, 1);
  });
};

describe("mirror, wreath round the hoop and kaleidoscope", () => {
  it("mirror2 lands across the axis and is flipped", () => {
    // Left-right: across the upright line half the gap past the design's right edge (x = 8 + 6 + 1.5).
    const [orig, right] = outlines({ kind: "mirror2", axis: "x", gap: 3 });
    expectSame(right, orig.map(([x, y]) => [31 - x, y]));
    // Top-bottom: across the level line half the gap below it (y = 6 + 5 + 1.5).
    const [, below] = outlines({ kind: "mirror2", axis: "y", gap: 3 });
    expectSame(below, orig.map(([x, y]) => [x, 25 - y]));
    expect(copies({ kind: "mirror2", axis: "x", gap: 3 }).map(([, angle]) => angle)).toEqual([150]);
    expect(copies({ kind: "mirror2", axis: "y", gap: 3 })).toHaveLength(1);
  });

  it("a wreath round the hoop keeps every copy the same distance from the middle", () => {
    // The wing sits off-center, 10 mm from the middle of the hoop: the copies go round (0, 0).
    const all = outlines({ kind: "circle", count: 6, radius: 99, turn: true, center: "hoop" });
    expect(all).toHaveLength(6);
    all.forEach((copy, k) => {
      copy.forEach(([x, y], i) => expect(Math.hypot(x, y)).toBeCloseTo(Math.hypot(...all[0][i]), 1));
      // Each is the original turned k sixths of the way round the middle.
      const a = (2 * Math.PI * k) / 6;
      expectSame(copy, all[0].map(([x, y]) => [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)]));
    });
    // Without turning, each copy's own middle still goes round the hoop's middle.
    const upright = outlines({ kind: "circle", count: 4, radius: 99, turn: false, center: "hoop" });
    const middle = (pts: Spot[]) => [0, 1].map((j) => (Math.min(...pts.map((p) => p[j])) + Math.max(...pts.map((p) => p[j]))) / 2);
    for (const copy of upright) expect(Math.hypot(...(middle(copy) as Spot))).toBeCloseTo(10, 1);
  });

  it("kaleidoscope neighbors are mirror images", () => {
    for (const center of ["below", "hoop"] as const) {
      const all = outlines({ kind: "circle", count: 6, radius: 20, turn: true, mirror: true, center });
      expect(all).toHaveLength(6);
      const pivot: Spot = center === "hoop" ? [0, 0] : [WING_AT[0], WING_AT[1] + 20];
      const own = (Math.atan2(WING_AT[1] - pivot[1], WING_AT[0] - pivot[0]) * 180) / Math.PI;
      for (let k = 0; k < 6; k++) {
        // The line between copy k and the next, half a step on from copy k.
        const between = own + (k + 0.5) * 60;
        expectSame(all[(k + 1) % 6], all[k].map((p) => reflect(p, pivot, between)));
      }
    }
  });

  it("a kaleidoscope always has an even number of copies, every other one mirrored", () => {
    const { layout, id } = wing();
    expect(repeatItem(layout, id, WING_AT, WING_SIZE, { kind: "circle", count: 5, radius: 20, turn: true, mirror: true }).ids).toHaveLength(5);
    // A mirrored fill's rows lean the other way (150 degrees is 30 mirrored).
    const angles = copies({ kind: "circle", count: 4, radius: 20, turn: true, mirror: true }).map(([, a]) => a);
    expect(angles).toEqual([60, 30, 60]);
  });
});

describe("editing several things together", () => {
  it("turns two shapes about their common centre, keeping their arrangement", () => {
    let l = square().layout;
    const a = l.items[0].id;
    const second = addObject(l, { kind: "fill", geometry: { outline: [[20, 0, "c"], [30, 0, "c"], [30, 10, "c"], [20, 10, "c"]] }, params: {}, thread: { color: "#000", name: "", catalog: "", brand: "" } });
    l = second.layout;
    const b = second.id;
    const out = transformTogether(l, [a, b], { [a]: [5, 5], [b]: [25, 5] }, [15, 5], { rotate: 90 });
    expect(centers(out.items)).toEqual([[15, -5], [15, 15]]);
  });

  it("groups and ungroups", () => {
    const { layout, id } = square();
    expect(setGroup(layout, [id], "g1").items[0].group).toBe("g1");
    expect(setGroup(setGroup(layout, [id], "g1"), [id], null).items[0].group).toBeUndefined();
  });
});

describe("stitch direction follows the shape", () => {
  it("turns and mirrors a fill's angle with it", () => {
    const { layout, id } = square();
    const fillAngle = (l: typeof layout) => (l.items[0] as Extract<ObjectItem, { kind: "fill" }>).params.angle_deg;
    expect(fillAngle(rotateBy(layout, id, 90))).toBe(135);
    expect(fillAngle(mirror(layout, id, "x"))).toBe(135);
    expect(fillAngle(rotateBy(layout, id, 180))).toBe(45);
  });
});
