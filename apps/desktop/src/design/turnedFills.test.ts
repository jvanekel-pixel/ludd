/** Phase 6 shapes as they're moved, turned and mirrored: carved and angle lines go with them
 *  without changing their size, and a feathered side and a blend's colors stay where they were on
 *  the shape. */
import { describe, expect, it } from "vitest";
import { mirror, moveBy, objectCenter, objectNodeLists, rotateBy, shapeNodeLists } from "./layout";
import type { FillParams, Layout, ObjectItem, PathNode } from "./types";

const c = (x: number, y: number): PathNode => [x, y, "c"];

function fill(params: FillParams, extra: { carve?: PathNode[][] } = {}): ObjectItem {
  return {
    id: "f",
    kind: "fill",
    geometry: { outline: [c(0, 0), c(20, 0), c(20, 10), c(0, 10)], ...extra },
    params,
    thread: { color: "#cc0000", name: "Red", catalog: "", brand: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  };
}

const layout = (o: ObjectItem): Layout => ({ items: [o], merge_colors: false, color_sort: false, basting: { enabled: false, margin_mm: 5 } });
const first = (l: Layout) => l.items[0] as ObjectItem & { kind: "fill" };

describe("carved lines", () => {
  // A carved line may reach past the outline; it never changes the shape's size or middle.
  const carved = fill({}, { carve: [[c(-30, 5), c(40, 6)]] });

  it("are among a shape's point lists, but don't give it its size", () => {
    expect(objectNodeLists(carved)).toHaveLength(2);
    expect(shapeNodeLists(carved)).toHaveLength(1);
    expect(objectCenter(carved)).toEqual([10, 5]);
  });

  it("move and resize with the shape", () => {
    expect(first(moveBy(layout(carved), "f", 3, 4)).geometry.carve).toEqual([[c(-27, 9), c(43, 10)]]);
    // Turned half round about the outline's middle, (10, 5).
    expect(first(rotateBy(layout(carved), "f", 180)).geometry.carve).toEqual([[c(50, 5), c(-20, 4)]]);
  });
});

describe("angle lines and a ripple's middle", () => {
  it("move with the shape", () => {
    const o = fill({ angle_lines: [[[2, 2], [4, 2]], [[10, 8], [12, 8]]], ripple_center: [5, 5] });
    const p = first(moveBy(layout(o), "f", 1, -1)).params;
    expect(p.angle_lines).toEqual([[[3, 1], [5, 1]], [[11, 7], [13, 7]]]);
    expect(p.ripple_center).toEqual([6, 4]);
  });
});

/** Where a point of the screen goes: turned `deg` (as rotateBy turns, y down) or mirrored. */
type Turn = { name: string; apply: (l: Layout) => Layout; vector: (x: number, y: number) => [number, number] };
const turns: Turn[] = [
  ...[45, 90, -90, 135, -135, 180, 270, 360].map((deg) => ({
    name: `turned ${deg}`,
    apply: (l: Layout) => rotateBy(l, "f", deg),
    vector: (x: number, y: number): [number, number] => {
      const a = (deg * Math.PI) / 180;
      return [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
    },
  })),
  { name: "mirrored left to right", apply: (l) => mirror(l, "f", "x"), vector: (x, y) => [-x, y] },
  { name: "mirrored top to bottom", apply: (l) => mirror(l, "f", "y"), vector: (x, y) => [x, -y] },
];

/** In screen directions: the feathered side of the rows, and the end a blend's last color is at. */
function sides(p: FillParams): { feather: [number, number]; blend: [number, number] } {
  const a = ((p.angle_deg ?? 45) * Math.PI) / 180;
  const row: [number, number] = [Math.cos(a), Math.sin(a)]; // towards the rows' right-hand ends
  const stack: [number, number] = [-Math.sin(a), Math.cos(a)]; // towards the last row
  const f = p.feather === "left" ? -1 : 1;
  const b = p.blend_flip ? -1 : 1;
  return { feather: [f * row[0], f * row[1]], blend: [b * stack[0], b * stack[1]] };
}

describe("a feathered side and a blend's colors stay where they were on the shape", () => {
  for (const angle of [0, 1, 45, 89, 90, 91, 135, 179])
    for (const turn of turns)
      it(`rows at ${angle} degrees, ${turn.name}`, () => {
        for (const feather of ["left", "right"] as const)
          for (const blend_flip of [false, true]) {
            const before = sides({ angle_deg: angle, feather, blend_flip, pattern: "blend" });
            const after = sides(first(turn.apply(layout(fill({ angle_deg: angle, feather, blend_flip, pattern: "blend" })))).params);
            for (const key of ["feather", "blend"] as const) {
              const want = turn.vector(...before[key]);
              expect(after[key][0] * want[0] + after[key][1] * want[1]).toBeCloseTo(1, 3);
            }
          }
      });

  it("leaves other fills' settings alone", () => {
    const p = first(rotateBy(layout(fill({ angle_deg: 135, feather: "both", pattern: "tatami" })), "f", 90)).params;
    expect(p.feather).toBe("both");
    expect(p.blend_flip).toBeUndefined();
  });
});
