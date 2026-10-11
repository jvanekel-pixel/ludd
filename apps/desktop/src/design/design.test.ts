import { describe, expect, it } from "vitest";
import {
  blockAt,
  blockStartStitches,
  chunkBlocks,
  stitchRecordIndex,
  visibleRecords,
} from "./player";
import { Kind, type Design } from "./types";
import { fitView, zoomAt } from "./view";

const S = Kind.Stitch;
const J = Kind.Jump;
const T = Kind.Trim;
const C = Kind.ColorChange;
const E = Kind.End;

// Two blocks: records 0-5 (thread 0), color change at 6, records 7-10 (thread 1), end at 11.
const kinds = [S, S, S, T, J, S, C, S, S, S, S, E];
const design: Design = {
  path: "x.pes",
  name: "x.pes",
  format: "pes",
  info: {
    stitches: 8,
    jumps: 1,
    trims: 1,
    stops: 0,
    color_changes: 1,
    colors: 2,
    width_mm: 10,
    height_mm: 5,
    bounds_mm: [0, 0, 10, 5],
  },
  threads: [
    { color: "#ff0000", name: "Red", catalog: "", brand: "" },
    { color: "#0000ff", name: "Blue", catalog: "", brand: "" },
  ],
  blocks: [
    { thread: 0, start: 0, end: 6 },
    { thread: 1, start: 7, end: 12 },
  ],
  records: { x: kinds.map((_, i) => i), y: kinds.map(() => 0), kind: kinds },
};

describe("player", () => {
  const idx = stitchRecordIndex(design);

  it("indexes stitches only", () => {
    expect(Array.from(idx)).toEqual([0, 1, 2, 5, 7, 8, 9, 10]);
  });

  it("maps sewn stitch counts to visible records", () => {
    expect(visibleRecords(idx, 0, kinds.length)).toBe(0);
    expect(visibleRecords(idx, 1, kinds.length)).toBe(1);
    expect(visibleRecords(idx, 4, kinds.length)).toBe(6); // includes the trim and jump before stitch 4
    expect(visibleRecords(idx, 8, kinds.length)).toBe(kinds.length);
    expect(visibleRecords(idx, 99, kinds.length)).toBe(kinds.length);
  });

  it("finds the block under a record", () => {
    expect(blockAt(design, 0)).toBe(0);
    expect(blockAt(design, 6)).toBe(0); // the color change itself
    expect(blockAt(design, 7)).toBe(1);
    expect(blockAt(design, 11)).toBe(1);
  });

  it("knows where each color starts in stitches", () => {
    expect(blockStartStitches(design, idx)).toEqual([0, 4]);
  });

  it("chunks blocks without crossing color boundaries", () => {
    expect(chunkBlocks(design, 4)).toEqual([
      { thread: 0, block: 0, start: 0, end: 4 },
      { thread: 0, block: 0, start: 4, end: 6 },
      { thread: 1, block: 1, start: 7, end: 11 },
      { thread: 1, block: 1, start: 11, end: 12 },
    ]);
  });
});

describe("view", () => {
  it("fits and centres a design", () => {
    const v = fitView([0, 0, 100, 50], 1000, 600, 0, 1000);
    expect(v.scale).toBe(10);
    expect(v.x).toBe(0);
    expect(v.y).toBe(50);
  });

  it("caps the fit scale for tiny designs", () => {
    expect(fitView([0, 0, 1, 1], 1000, 1000, 0, 40).scale).toBe(40);
  });

  it("zooms around the cursor", () => {
    const v = { scale: 2, x: 10, y: 20 };
    const z = zoomAt(v, 2, 110, 120);
    // The world point under (110, 120) stays under it.
    const before = [(110 - v.x) / v.scale, (120 - v.y) / v.scale];
    const after = [(110 - z.x) / z.scale, (120 - z.y) / z.scale];
    expect(after).toEqual(before);
    expect(z.scale).toBe(4);
  });
});
