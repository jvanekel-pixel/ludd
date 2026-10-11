import { describe, expect, it } from "vitest";
import { Kind, type Design } from "./design/types";
import { blockStitchCounts, printHtml, stitchPaths, templateSvg } from "./print";

const S = Kind.Stitch;
const J = Kind.Jump;
const C = Kind.ColorChange;

const design: Design = {
  path: "x.pes",
  name: "A <b>&",
  format: "pes",
  info: { stitches: 5, jumps: 1, trims: 0, stops: 0, color_changes: 1, colors: 2, width_mm: 30, height_mm: 10, bounds_mm: [0, 0, 30, 10] },
  threads: [
    { color: "#ff0000", name: "Red", catalog: "1", brand: "Madeira" },
    { color: "#0000ff", name: "Blue", catalog: "", brand: "" },
  ],
  blocks: [
    { thread: 0, start: 0, end: 5 },
    { thread: 1, start: 6, end: 8 },
  ],
  records: {
    x: [0, 10, 10, 20, 30, 30, 0, 10],
    y: [0, 0, 0, 0, 0, 0, 10, 10],
    kind: [S, S, J, S, S, C, S, S],
  },
};

describe("print", () => {
  it("draws stitches as paths, lifting the pen at jumps", () => {
    expect(stitchPaths(design)).toEqual([
      { color: "#ff0000", d: "M0.00 0.00L10.00 0.00M20.00 0.00L30.00 0.00" },
      { color: "#0000ff", d: "M0.00 10.00L10.00 10.00" },
    ]);
    expect(blockStitchCounts(design)).toEqual([4, 2]);
  });

  it("sizes the template in real millimetres, including the hoop", () => {
    const svg = templateSvg(design, { id: "h", name: "4x4", width_mm: 100, height_mm: 100 });
    expect(svg).toMatch(/width="108mm" height="108mm"/);
    expect(svg).toContain('class="hoop"');
    expect(templateSvg(design, null)).toMatch(/width="54mm" height="34mm"/);
  });

  it("escapes names and lists every color", () => {
    const html = printHtml(design, null, "Brother PE550D");
    expect(html).toContain("A &lt;b&gt;&amp;");
    expect(html).not.toContain("<b>&");
    expect(html).toContain("Madeira 1");
    expect((html.match(/<tr><td>/g) ?? []).length).toBe(2);
  });
});
