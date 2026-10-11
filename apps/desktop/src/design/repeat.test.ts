import { describe, expect, it } from "vitest";
import { addObject, newLayout, objectCenter, repeatItem } from "./layout";
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
