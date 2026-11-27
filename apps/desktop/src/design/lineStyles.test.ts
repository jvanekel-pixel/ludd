import { describe, expect, it } from "vitest";
import { fillPatternDef, fixedFillEnd, hasDirectionDots } from "./fillPatterns";
import { LINE_STYLE_DEFS, lineStyleDef, MOTIF_FIELDS } from "./lineStyles";

/** A style's settings as [key, label, default, lowest, highest]. */
const settings = (id: string) => lineStyleDef(id).fields.map((f) => [f.key, f.label, f.def, f.min, f.max]);

describe("line style descriptors", () => {
  it("five more styles sit behind More styles", () => {
    expect(LINE_STYLE_DEFS.filter((d) => !d.more).map((d) => d.id)).toEqual(["single", "triple", "bean", "motif"]);
    expect(LINE_STYLE_DEFS.filter((d) => d.more).map((d) => [d.id, d.label])).toEqual([
      ["backstitch", "Backstitch"],
      ["stem", "Stem stitch"],
      ["candlewick", "Candlewicking"],
      ["redwork", "Redwork"],
      ["knots", "French knots"],
    ]);
  });

  it("each style has only its own settings, with the engine's defaults and ranges", () => {
    for (const id of ["single", "triple", "bean", "backstitch", "redwork"]) expect(settings(id), id).toEqual([]);
    expect(lineStyleDef("motif").fields).toBe(MOTIF_FIELDS);
    expect(settings("stem")).toEqual([["stem_width_mm", "Width", 0.8, 0.3, 2.5]]);
    expect(settings("candlewick")).toEqual([
      ["knot_mm", "Knot size", 1.6, 1, 3],
      ["knot_gap_mm", "Between knots", 4, 2, 15],
    ]);
    expect(settings("knots")).toEqual([["knot_mm", "Knot size", 1.6, 1, 3]]);
    // French knots are knots only: a stitch length would change nothing.
    expect(LINE_STYLE_DEFS.filter((d) => d.noLength).map((d) => d.id)).toEqual(["knots"]);
  });

  it("a missing or unknown style is treated as Single", () => {
    expect(lineStyleDef(undefined).id).toBe("single");
    expect(lineStyleDef("zigzag").id).toBe("single");
  });

  it("blackwork is an open fill with a lattice and a cell size", () => {
    const def = fillPatternDef("blackwork");
    expect(def).toMatchObject({ id: "blackwork", label: "Blackwork", open: true, noSpacing: true, summary: "label" });
    expect(def.noLength).toBeFalsy();
    expect(def.choices?.map((c) => [c.key, c.label, c.def, c.options.map((o) => o.id)])).toEqual([
      ["blackwork_lattice", "Lattice", "diamonds", ["diamonds", "grid", "honeycomb", "crossed"]],
    ]);
    expect(def.fields.map((f) => [f.key, f.label, f.def, f.min, f.max])).toEqual([["blackwork_mm", "Cell size", 5, 3, 12]]);
    expect(fixedFillEnd("blackwork")).toBe(true);
    expect(hasDirectionDots("blackwork")).toBe(false);
  });
});
