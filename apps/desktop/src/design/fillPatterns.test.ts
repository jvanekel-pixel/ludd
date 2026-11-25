import { describe, expect, it } from "vitest";
import { fillPatternDef, fixedFillEnd, hasDirectionDots } from "./fillPatterns";

/** The six patterns of 1.0.1: what the canvas does for them must not change. */
const SIX = ["tatami", "gradient", "wave", "contour", "stipple", "cross"];

describe("fill pattern descriptors", () => {
  it("fillPatternDef falls back to tatami", () => {
    expect(fillPatternDef("nope").id).toBe("tatami");
    expect(fillPatternDef(undefined).id).toBe("tatami");
    expect(fillPatternDef("wave").id).toBe("wave");
  });

  it("contour, stipple and cross-stitch end where their pattern does", () => {
    expect(SIX.filter(fixedFillEnd)).toEqual(["contour", "stipple", "cross"]);
    expect(fixedFillEnd(undefined)).toBe(false);
  });

  it("direction dots show for the same patterns as before", () => {
    expect(SIX.filter(hasDirectionDots)).toEqual(["tatami", "gradient", "wave", "cross"]);
    expect(hasDirectionDots(undefined)).toBe(true);
    expect(hasDirectionDots("nope")).toBe(true);
  });

  it("spiral has Ring spacing 1.5 (0.4 to 6)", () => {
    const spiral = fillPatternDef("spiral");
    expect(spiral).toMatchObject({ id: "spiral", label: "Spiral", open: true, noSpacing: true, maxStitch: 4, summary: "label" });
    expect(spiral.noLength).toBeFalsy();
    expect(spiral.fields).toHaveLength(1);
    expect(spiral.fields[0]).toMatchObject({ key: "spiral_mm", label: "Ring spacing", def: 1.5, min: 0.4, max: 6, step: 0.1, digits: 1, suffix: "mm" });
    // An open pattern: its end can't be moved, and it has no rows to point the direction dots along.
    expect(fixedFillEnd("spiral")).toBe(true);
    expect(hasDirectionDots("spiral")).toBe(false);
  });
});
