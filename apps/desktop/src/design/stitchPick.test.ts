/** Picking stitches while editing a stitch file: only stitches an edit can name. Rebuild, the
 *  density limit and jump locks add stitches numbered -1, which share one number. */
import { describe, expect, it } from "vitest";
import { nearestStitch, pickable, stitchesInBox } from "./stitchPick";
import { Kind, type Design } from "./types";

/** Item 0: stitch 0 at (0, 0), an added one (-1) at (1, 0), stitch 1 at (2, 0), a jump at (5, 0),
 *  another added one (-1) at (9, 0); item 1: stitch 7 at (1, 0.2). */
const records = {
  x: [0, 1, 2, 5, 9, 1],
  y: [0, 0, 0, 0, 0, 0.2],
  kind: [Kind.Stitch, Kind.Stitch, Kind.Stitch, Kind.Jump, Kind.Stitch, Kind.Stitch],
  item: [0, 0, 0, 0, 0, 1],
  src: [0, -1, 1, -1, -1, 7],
} as Design["records"];

describe("picking stitches", () => {
  it("only the item's own stitches that have a number can be picked", () => {
    expect([0, 1, 2, 3, 4, 5].map((i) => pickable(records, 0, i))).toEqual([true, false, true, false, false, false]);
  });

  it("a click picks the nearest numbered stitch within reach, never an added one", () => {
    expect(nearestStitch(records, 0, 1.1, 0, 2)).toBe(1); // the added stitch at (1, 0) is nearer
    expect(nearestStitch(records, 0, 9, 0, 1)).toBeNull();
    expect(nearestStitch(records, 0, 0.5, 0, 0.4)).toBeNull();
    expect(nearestStitch(records, 1, 1, 0, 1)).toBe(7);
  });

  it("of two equally near, the one sewn first", () => {
    expect(nearestStitch(records, 0, 1, 0, 2)).toBe(0);
  });

  it("a box takes the numbered stitches inside it only", () => {
    expect(stitchesInBox(records, 0, -1, -1, 10, 1)).toEqual([0, 1]);
    expect(stitchesInBox(records, 0, 0.5, -1, 1.5, 1)).toEqual([]);
  });

  it("does nothing without item numbers (a plain stitch file view)", () => {
    const bare = { x: [0], y: [0], kind: [Kind.Stitch] } as Design["records"];
    expect(nearestStitch(bare, 0, 0, 0, 1)).toBeNull();
    expect(stitchesInBox(bare, 0, -1, -1, 1, 1)).toEqual([]);
  });
});
