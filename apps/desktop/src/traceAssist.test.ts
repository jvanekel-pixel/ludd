import { describe, expect, it } from "vitest";
import type { RefImage } from "./design/types";
import { pictureUnder, tracePoints } from "./traceAssist";

const img = (id: string, extra: Partial<RefImage> = {}): RefImage => ({
  id, name: id, path: id, data_url: "", x: 0, y: 0, width_mm: 40, height_mm: 20, rotate: 0, opacity: 0.5, locked: false, visible: true, ...extra,
});

describe("pictureUnder", () => {
  it("finds the topmost visible picture, honouring rotation", () => {
    const a = img("a");
    const b = img("b", { x: 10 });
    expect(pictureUnder([a, b], 15, 0)?.id).toBe("b");
    expect(pictureUnder([a, b], -15, 0)?.id).toBe("a");
    expect(pictureUnder([a, { ...b, visible: false }], 15, 0)?.id).toBe("a");
    expect(pictureUnder([a], 0, 15)).toBe(null);
    // Turned 90°, the 40 x 20 picture covers (0, 15).
    expect(pictureUnder([img("r", { rotate: 90 })], 0, 15)?.id).toBe("r");
  });
});

describe("tracePoints", () => {
  it("uses the points of lines and fills, and rung centres of satins", () => {
    expect(tracePoints({ kind: "run", a: [[0, 0, "c"], [3, 4, "s"]], b: [] })).toEqual([[0, 0], [3, 4]]);
    expect(tracePoints({ kind: "satin", a: [[0, 0, "c"], [10, 0, "c"]], b: [[0, 4, "c"], [10, 4, "c"]] })).toEqual([
      [0, 2],
      [10, 2],
    ]);
    // Halfway through a rung: wait until both sides are placed.
    expect(tracePoints({ kind: "satin", a: [[0, 0, "c"]], b: [] })).toBe(null);
  });
});
