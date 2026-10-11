import { describe, expect, it } from "vitest";
import { defaultCutStops, defaultFormat, hasTrims, hoopFit } from "./machine";
import { Kind, type Design, type Machine } from "./types";

const hoop = { id: "a", name: "A", width_mm: 126, height_mm: 110 };

const pe550d: Machine = {
  id: "brother-pe550d",
  name: "Brother PE550D",
  brand: "Brother",
  formats: ["pes"],
  needles: 1,
  hoops: [{ id: "4x4", name: "4x4", width_mm: 100, height_mm: 100 }],
  cuts: "color_change",
  max_stitch_mm: null,
  max_stitches: null,
  max_colors: null,
  notes: "",
  builtin: true,
};

function design(kind: Kind[]): Design {
  return {
    path: "x.pes",
    name: "x.pes",
    format: "pes",
    info: {
      stitches: 0,
      jumps: 0,
      trims: 0,
      stops: 0,
      color_changes: 0,
      colors: 1,
      width_mm: 10,
      height_mm: 10,
      bounds_mm: [0, 0, 10, 10],
    },
    threads: [
      { color: "#ff0000", name: "Red", catalog: "1", brand: "A" },
      { color: "#00ff00", name: "Green", catalog: "2", brand: "A" },
    ],
    blocks: [],
    records: { x: kind.map(() => 0), y: kind.map(() => 0), kind },
  };
}

const S = Kind.Stitch;
const T = Kind.Trim;
const J = Kind.Jump;
const C = Kind.ColorChange;

describe("hoopFit", () => {
  it("fits, fits rotated, or doesn't", () => {
    expect(hoopFit({ width_mm: 126, height_mm: 110 }, hoop)).toBe("fits");
    expect(hoopFit({ width_mm: 100, height_mm: 120 }, hoop)).toBe("rotate");
    expect(hoopFit({ width_mm: 130, height_mm: 100 }, hoop)).toBe("too_big");
  });
});

describe("cut-stop defaults", () => {
  it("only counts trims inside a color", () => {
    expect(hasTrims(design([S, S, T, J, S]))).toBe(true);
    expect(hasTrims(design([S, C, T, J, S]))).toBe(false);
    expect(hasTrims(design([T, J, S, S]))).toBe(false);
  });

  it("turns on for color-change-only machines with trims", () => {
    expect(defaultCutStops(pe550d, design([S, T, J, S])).enabled).toBe(true);
    expect(defaultCutStops(pe550d, design([S, S])).enabled).toBe(false);
    expect(defaultCutStops({ ...pe550d, cuts: "trim" }, design([S, T, J, S])).enabled).toBe(false);
    expect(defaultCutStops(null, design([S, T, J, S])).enabled).toBe(false);
    expect(defaultCutStops(pe550d, design([S, T, J, S])).min_jump_mm).toBe(3);
  });

  it("exports in the machine's format", () => {
    expect(defaultFormat(pe550d)).toBe("pes");
    expect(defaultFormat({ ...pe550d, formats: ["jef"] })).toBe("jef");
    expect(defaultFormat(null)).toBe("pes");
  });
});
