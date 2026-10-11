import { describe, expect, it } from "vitest";
import { distToSegment, flatten, nearestSegment, nodeBounds, spanAt } from "./paths";
import type { PathNode } from "./types";

const c = (x: number, y: number): PathNode => [x, y, "c"];
const s = (x: number, y: number): PathNode => [x, y, "s"];

describe("flatten (same rule as the engine)", () => {
  it("keeps corners as straight lines through the nodes", () => {
    expect(flatten([c(0, 0), c(10, 0), c(10, 10)])).toEqual([
      [0, 0],
      [10, 0],
      [10, 10],
    ]);
  });

  it("curves through curve nodes and stays smooth there", () => {
    const poly = flatten([c(0, 0), s(10, 10), c(20, 0)]);
    expect(poly.length).toBeGreaterThan(10);
    expect(poly).toContainEqual([10, 10]);
    const i = poly.findIndex((p) => p[0] === 10 && p[1] === 10);
    const before = Math.atan2(poly[i][1] - poly[i - 1][1], poly[i][0] - poly[i - 1][0]);
    const after = Math.atan2(poly[i + 1][1] - poly[i][1], poly[i + 1][0] - poly[i][0]);
    expect(Math.abs(before - after)).toBeLessThan(0.15);
  });

  it("closes back to the start", () => {
    const poly = flatten([c(0, 0), c(10, 0), c(10, 10)], true);
    expect(poly[poly.length - 1]).toEqual([0, 0]);
  });
});

describe("geometry helpers", () => {
  it("bounds, distances and nearest segments", () => {
    expect(nodeBounds([[c(1, 2), c(5, -1)], [c(0, 3)]])).toEqual([0, -1, 5, 3]);
    expect(nodeBounds([])).toBe(null);
    expect(distToSegment([5, 3], [0, 0], [10, 0])).toBe(3);
    expect(distToSegment([-4, 3], [0, 0], [10, 0])).toBe(5);
    expect(nearestSegment([[0, 0], [10, 0], [10, 10]], [11, 5])).toEqual({ index: 1, distance: 1 });
  });

  it("finds the span between nodes under the pointer", () => {
    const nodes = [c(0, 0), c(10, 0), c(10, 10), c(0, 10)];
    expect(spanAt(nodes, false, [5, 0.2], 0.5)).toBe(0);
    expect(spanAt(nodes, false, [10.1, 5], 0.5)).toBe(1);
    expect(spanAt(nodes, false, [0, 5], 0.5)).toBe(null); // open path: no closing span
    expect(spanAt(nodes, true, [0, 5], 0.5)).toBe(3);
  });
});
