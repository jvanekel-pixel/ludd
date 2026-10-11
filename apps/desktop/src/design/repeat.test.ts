import { describe, expect, it } from "vitest";
import { addObject, mirror, newLayout, objectCenter, repeatItem, rotateBy, setGroup, transformTogether } from "./layout";
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
