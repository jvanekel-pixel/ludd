import { describe, expect, it } from "vitest";
import { edgeFitsFor, edgesOf, fitsAlong, followedEdge } from "./edgeFit";
import { addObject, newLayout } from "./layout";
import type { PathNode } from "./types";

const thread = { color: "#000", name: "", catalog: "", brand: "" };
const square = (x: number, y: number, w: number): PathNode[] => [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]];

function layoutWithFill(outline: PathNode[], holes?: PathNode[][]) {
  return addObject(newLayout(), { kind: "fill", geometry: { outline, ...(holes ? { holes } : {}) }, params: {}, thread } as never).layout;
}

describe("satin edge fit", () => {
  const l = layoutWithFill(square(0, 0, 40));

  it("notices clicks along a shape's edge, and not clicks elsewhere", () => {
    expect(edgeFitsFor(l, [[1, 0.4], [20, -0.6]], 3).length).toBe(3);
    expect(edgeFitsFor(l, [[10, 10], [20, 12]], 3)).toEqual([]); // in the middle of the fill
    expect(edgeFitsFor(l, [[5, 0.2]], 3)).toEqual([]); // one point isn't enough
    expect(edgeFitsFor(l, [[5, 0.2], [5.5, 0.3]], 3)).toEqual([]); // nor two on the same spot
  });

  it("first fits the satin all the way round, centred on the edge and starting where you started", () => {
    const [round] = edgeFitsFor(l, [[39, 1], [39.5, 20]], 3);
    expect(round.closed).toBe(true);
    expect(round.nodes).toHaveLength(4);
    expect(round.nodes[0].slice(0, 2)).toEqual([40, 0]);
    // Going down the right side: the next corner is the bottom right.
    expect(round.nodes[1].slice(0, 2)).toEqual([40, 40]);
    expect(round.nodes.every((n) => n[2] === "c")).toBe(true);
  });

  it("then just outside the edge: the satin covers the edge from outside, overlapping a little", () => {
    const [, outside] = edgeFitsFor(l, [[1, 0], [20, 0]], 3);
    const xs = outside.nodes.map((n) => n[0]);
    const ys = outside.nodes.map((n) => n[1]);
    // 3 mm wide, overlapping 0.4 mm: the centre line is 1.1 mm outside the square.
    expect(Math.min(...xs)).toBeCloseTo(-1.1);
    expect(Math.max(...xs)).toBeCloseTo(41.1);
    expect(Math.min(...ys)).toBeCloseTo(-1.1);
  });

  it("goes into a hole for a hole's edge", () => {
    const withHole = layoutWithFill(square(0, 0, 40), [square(10, 10, 20)]);
    const [, outside] = edgeFitsFor(withHole, [[11, 10.2], [20, 9.8]], 3);
    const xs = outside.nodes.map((n) => n[0]);
    expect(Math.min(...xs)).toBeCloseTo(11.1); // inside the hole, away from the fill
    expect(Math.max(...xs)).toBeCloseTo(28.9);
  });

  it("can follow just the part you traced, round the corner, in your direction", () => {
    const fits = edgeFitsFor(l, [[30, 0], [40, 5], [40.3, 20]], 3);
    const part = fits[2];
    expect(part.closed).toBe(false);
    expect(part.nodes[0].slice(0, 2).map((v) => Math.round(v as number))).toEqual([30, 0]);
    expect(part.nodes.some((n) => n[0] === 40 && n[1] === 0 && n[2] === "c")).toBe(true); // the corner
    expect(part.nodes[part.nodes.length - 1].slice(0, 2).map((v) => Math.round(v as number))).toEqual([40, 20]);
    // The other way round the square.
    const back = edgeFitsFor(l, [[10, 0], [0.2, 5], [0, 20]], 3)[2];
    expect(back.nodes.some((n) => n[0] === 0 && n[1] === 0)).toBe(true);
    expect(back.nodes[back.nodes.length - 1].slice(0, 2).map((v) => Math.round(v as number))).toEqual([0, 20]);
  });

  it("follows a moved shape where it's shown, and an open line its whole length", () => {
    const moved = { ...l, items: l.items.map((it) => ({ ...it, transform: { ...it.transform, x: 100 } })) };
    expect(edgeFitsFor(moved, [[101, 0], [120, 0]], 3).length).toBe(3);
    const line = addObject(newLayout(), { kind: "run", geometry: { nodes: [[0, 0, "c"], [50, 0, "s"], [80, 20, "s"]] }, params: {}, thread } as never).layout;
    const edges = edgesOf(line);
    const e = followedEdge([[30, 0.5], [10, 0.4]], edges, 3)!;
    const [whole] = fitsAlong(e, [[30, 0.5], [10, 0.4]], 3);
    expect(whole.closed).toBe(false);
    expect(whole.nodes[0].slice(0, 2)).toEqual([80, 20]); // your way round: from the far end
  });
});
