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
});
