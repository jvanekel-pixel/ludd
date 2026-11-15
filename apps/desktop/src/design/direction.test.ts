import { describe, expect, it } from "vitest";
import { angleOf, centroid, chord, fillDirection, nearestOnLine, nearestOnRings } from "./direction";
import type { Pt } from "./paths";
import type { ObjectItem } from "./types";

const square: Pt[] = [[0, 0], [20, 0], [20, 10], [0, 10]];

describe("dots that slide along the edge", () => {
  it("follow the point of the edge nearest the mouse, inside or outside the shape", () => {
    expect(nearestOnLine(square, [7, -4], true)).toEqual([7, 0]);
    expect(nearestOnLine(square, [18, 5], true)).toEqual([20, 5]);
    expect(nearestOnLine(square, [-3, 12], true)).toEqual([0, 10]);
    // A hole is an edge too.
    const hole: Pt[] = [[8, 4], [12, 4], [12, 6], [8, 6]];
    expect(nearestOnRings([square, hole], [10, 5.5])).toEqual([10, 6]);
  });

  it("show a fill's direction across its middle, at its angle", () => {
    expect(centroid(square)).toEqual([10, 5]);
    expect(chord(square, [10, 5], 0)).toEqual([[0, 5], [20, 5]]);
    const diag = chord(square, [10, 5], 45)!;
    expect(angleOf(diag[0], diag[1])).toBe(45);
    expect(angleOf([0, 0], [-10, 0])).toBe(0);
    expect(angleOf([0, 0], [0, -10])).toBe(90);
  });

  it("stay where they were put while the angle is theirs", () => {
    const fill = (params: object) =>
      ({ id: "f", kind: "fill", geometry: { outline: square.map(([x, y]) => [x, y, "l"]) }, params, thread: { color: "#000" } }) as unknown as ObjectItem;
    const line: [Pt, Pt] = [[2, 0], [20, 6]];
    expect(fillDirection(fill({ angle_deg: angleOf(...line), angle_line: line }))).toEqual(line);
    // Typed another angle in the panel: back across the middle.
    expect(fillDirection(fill({ angle_deg: 90, angle_line: line }))).toEqual([[10, 0], [10, 10]]);
    expect(fillDirection(fill({ pattern: "stipple" }))).toBeNull();
  });
});
