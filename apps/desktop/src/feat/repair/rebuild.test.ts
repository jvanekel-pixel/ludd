/** When the Repair dialog offers Rebuild and the density limit, and ticks them. */
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import type { FileItem, LayoutItemInfo } from "../../design/types";
import "./density";
import "./rebuild";
import { repairStep, type Stats } from "./steps";

const item = (scale_x: number, scale_y = scale_x): FileItem => ({
  id: "f", kind: "file", path: "C:/d/x.pes", threads: [], ops: [],
  transform: { x: 0, y: 0, rotate: 0, scale_x, scale_y, flip_x: false, flip_y: false },
});
const shown = {} as LayoutItemInfo;
const stats: Stats = { stitches: 1000, trims: 0, jumps: 0, tiny: 0, longest_mm: 4, densest: 8.24, hits_max: 3 };

describe("the Rebuild step", () => {
  const step = () => repairStep("rebuild")!;

  it("shows from 10% bigger or smaller, on either side", () => {
    expect([1, 1.09, 0.91].map((s) => step().visible(item(s), shown))).toEqual([false, false, false]);
    expect([item(1.1), item(0.9), item(1, 1.3)].map((i) => step().visible(i, shown))).toEqual([true, true, true]);
  });

  it("is ticked past 20%, where the resize warning starts", () => {
    expect([1.2, 0.8].map((s) => step().preset(item(s), shown))).toEqual([false, false]);
    expect([item(1.21), item(0.79), item(1.5, 1)].map((i) => step().preset(i, shown))).toEqual([true, true, true]);
  });

  it("makes the rebuild op and says what changed", () => {
    expect(step().make({})).toEqual({ op: "rebuild" });
    expect(step().summary({ ...stats, stitches: 2250 }, stats)).toBe("Rebuilt at this size: 1,000 stitches became 2,250.");
  });
});

describe("the density limit step", () => {
  const step = () => repairStep("density_limit")!;

  it("is always offered and never ticked for you", () => {
    expect(step().visible(item(1), shown)).toBe(true);
    expect(step().preset(item(1.5), shown)).toBe(false);
    expect(step().make({})).toEqual({ op: "density_limit" });
  });

  it("says how the thickest spot changed, or that nothing was too dense", () => {
    expect(step().summary({ ...stats, densest: 5.06 }, stats)).toBe("Thickest spot: 8.2 down to 5.1 mm of thread per mm².");
    expect(step().summary(stats, stats)).toBe("Nothing here is denser than this fabric takes.");
  });
});
