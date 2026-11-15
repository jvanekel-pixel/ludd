import { describe, expect, it } from "vitest";
import { resizeCursorFor, sideAxis, sideMids, stretchFactor } from "./handles";
import type { Pt } from "./paths";

const box: Pt[] = [[0, 0], [40, 0], [40, 20], [0, 20]];
const c: Pt = [20, 10];

describe("selection handles", () => {
  it("points each corner's arrow the way it drags", () => {
    expect(box.map((p) => resizeCursorFor(p, c))).toEqual(["resize", "resize-nesw", "resize", "resize-nesw"]);
  });

  it("gives the side handles a left-right or up-down arrow", () => {
    const m = sideMids(box);
    expect([m.n, m.e, m.s, m.w]).toEqual([[20, 0], [40, 10], [20, 20], [0, 10]]);
    expect([resizeCursorFor(m.n, c), resizeCursorFor(m.e, c), resizeCursorFor(m.s, c), resizeCursorFor(m.w, c)]).toEqual(["stretch-y", "stretch-x", "stretch-y", "stretch-x"]);
  });

  it("turns the arrows with a turned frame", () => {
    // Turned 90°: the top side is now on the right.
    const turned: Pt[] = [[30, 0], [30, 40], [10, 40], [10, 0]];
    expect(resizeCursorFor(sideMids(turned).n, [20, 20])).toBe("stretch-x");
  });

  it("stretches by how far the side moved from the opposite side, never flipping", () => {
    const axis = sideAxis(box, "e");
    expect(axis).toEqual([1, 0]);
    expect(stretchFactor([0, 10], [40, 10], [60, 13], axis)).toBeCloseTo(1.5);
    expect(stretchFactor([0, 10], [40, 10], [20, 10], axis)).toBeCloseTo(0.5);
    expect(stretchFactor([0, 10], [40, 10], [-30, 10], axis)).toBe(0.05);
  });
});
