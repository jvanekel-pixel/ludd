import { describe, expect, it } from "vitest";
import { DEFAULT_SPEED_SPM, estimate, fmtMinutes, fmtThread, PER_STITCH_MM, speedOf } from "./estimate";
import { Kind, type Design } from "./types";

const S = Kind.Stitch;
const J = Kind.Jump;
const T = Kind.Trim;
const C = Kind.ColorChange;
const E = Kind.End;

/** Thread 0: three stitches 10 mm apart, a trim, a jump, one stitch. Thread 1: two stitches 5 mm apart. */
function design(): Pick<Design, "info" | "blocks" | "records"> {
  const kind = [S, S, S, T, J, S, C, S, S, E];
  const x = [0, 10, 20, 20, 50, 50, 50, 0, 5, 5];
  const y = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  return {
    info: { stitches: 6, jumps: 1, trims: 1, stops: 0, color_changes: 1, colors: 2, width_mm: 50, height_mm: 0, bounds_mm: [0, 0, 50, 0] },
    blocks: [
      { thread: 0, start: 0, end: 6 },
      { thread: 1, start: 7, end: 9 },
    ],
    records: { x, y, kind },
  };
}

describe("sewing time and thread estimate", () => {
  it("times the stitches at the machine's speed, or 600 a minute when it doesn't say", () => {
    expect(estimate(design(), { speed_spm: 650 }).minutes).toBeCloseTo(6 / 650);
    expect(estimate(design(), { speed_spm: null }).speedSpm).toBe(DEFAULT_SPEED_SPM);
    expect(estimate(design()).speedSpm).toBe(DEFAULT_SPEED_SPM);
    expect(speedOf({ speed_spm: -5 })).toBe(DEFAULT_SPEED_SPM);
  });

  it("counts thread changes as color changes plus stops", () => {
    const d = design();
    expect(estimate(d).threadChanges).toBe(1);
    d.info.stops = 2;
    expect(estimate(d).threadChanges).toBe(3);
  });

  it("adds stitch lengths and the per-stitch allowance, and uses no thread across a trim", () => {
    const e = estimate(design());
    // Thread 0: 10 + 10 between the first three stitches; the trim cuts, so the jump to x=50 and the
    // stitch on it are free of travel; 4 stitches get the allowance.
    expect(e.perThread[0]).toEqual({ thread: 0, meters: (20 + 4 * PER_STITCH_MM) / 1000 });
    // Thread 1: 5 mm, 2 stitches.
    expect(e.perThread[1]).toEqual({ thread: 1, meters: (5 + 2 * PER_STITCH_MM) / 1000 });
    expect(e.topMeters).toBeCloseTo(0.031);
    expect(e.bobbinMeters).toBeCloseTo(0.031 / 3);
  });

  it("counts a jump's thread when nothing cuts it", () => {
    const d = design();
    d.records.kind[3] = S; // no trim: the jump drags thread 30 mm across
    const e = estimate(d);
    expect(e.perThread[0].meters).toBeCloseTo((10 + 10 + 0 + 30 + 0 + 5 * PER_STITCH_MM) / 1000);
  });

  it("adds up a thread sewn in two separate blocks", () => {
    const d = design();
    d.blocks[1] = { ...d.blocks[1], thread: 0 };
    const e = estimate(d);
    expect(e.perThread).toHaveLength(1);
    expect(e.perThread[0].meters).toBeCloseTo(0.031);
  });

  it("says times and lengths plainly", () => {
    expect(fmtMinutes(0.01)).toBe("about 1 min");
    expect(fmtMinutes(14.4)).toBe("about 14 min");
    expect(fmtMinutes(65)).toBe("about 1 h 05 min");
    expect(fmtThread(0.4)).toBe("under 1 m");
    expect(fmtThread(4.3)).toBe("about 4.5 m");
    expect(fmtThread(38.2)).toBe("about 38 m");
    expect(fmtThread(9.144, "in")).toBe("about 10 yd");
  });
});
