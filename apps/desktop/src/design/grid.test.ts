import { describe, expect, it } from "vitest";
import { MIN_MINOR_PX, PX_PER_MM_ACTUAL, gridLines, gridSpacing, zoomPercent } from "./grid";

describe("gridSpacing", () => {
  it("uses 1-inch major squares at normal zoom", () => {
    const sp = gridSpacing(4, "in"); // 4 px/mm: 1/8" = 12.7 px
    expect(sp.majorMm).toBeCloseTo(25.4);
    expect(sp.minorMm).toBeCloseTo(25.4 / 8);
    expect(sp.ratio).toBe(8);
  });

  it("gets finer when zoomed in and coarser when zoomed out", () => {
    expect(gridSpacing(40, "in").minorMm).toBeCloseTo(25.4 / 32);
    expect(gridSpacing(0.5, "in").minorMm).toBeCloseTo(25.4);
    expect(gridSpacing(0.05, "in").minorMm).toBeCloseTo(25.4 * 12);
  });

  it("never puts minor lines closer than the minimum, except at the coarsest step", () => {
    for (const units of ["in", "mm"] as const) {
      for (let s = 0.2; s < 500; s *= 1.3) {
        expect(gridSpacing(s, units).minorMm * s).toBeGreaterThanOrEqual(MIN_MINOR_PX);
      }
    }
  });

  it("works in millimetres", () => {
    const sp = gridSpacing(10, "mm");
    expect([sp.minorMm, sp.majorMm, sp.ratio]).toEqual([1, 10, 10]);
  });
});

describe("gridLines", () => {
  it("aligns to the origin and flags majors, on both sides of it", () => {
    const sp = { minorMm: 5, majorMm: 20, ratio: 4 };
    const lines = gridLines(-12, 22, 2, sp);
    expect(lines.map((l) => l.mm)).toEqual([-13, -8, -3, 2, 7, 12, 17, 22]);
    expect(lines.filter((l) => l.major).map((l) => l.mm)).toEqual([2, 22]);
  });

  it("puts a 4-inch hoop's edges on major lines when centred on the origin", () => {
    const sp = gridSpacing(4, "in");
    const majors = gridLines(-60, 60, 0, sp).filter((l) => l.major).map((l) => l.mm);
    expect(majors).toContain(-50.8);
    expect(majors).toContain(50.8);
  });
});

describe("zoomPercent", () => {
  it("is 100% at real size", () => {
    expect(zoomPercent(PX_PER_MM_ACTUAL)).toBe(100);
    expect(zoomPercent(PX_PER_MM_ACTUAL * 2)).toBe(200);
  });
});
