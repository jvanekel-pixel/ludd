import { describe, expect, it } from "vitest";
import { colorDifference, hexQuery, searchThreads } from "./threadSearch";

const chart = [
  { code: "001", name: "White", color: "#FFFFFF" },
  { code: "126", name: "Orange", color: "#FF7A10" },
  { code: "900", name: "Black", color: "#000000" },
  { code: "1126", name: "Deep orange", color: "#E05000" },
];

describe("thread search", () => {
  it("reads color codes, with or without #", () => {
    expect(hexQuery("#FF7A1A")).toBe("#ff7a1a");
    expect(hexQuery("ff7a1a")).toBe("#ff7a1a");
    expect(hexQuery("#f70")).toBe("#ff7700");
    expect(hexQuery("f70")).toBeNull(); // three characters without # stay a search
    expect(hexQuery("Orange")).toBeNull();
    expect(hexQuery("facade")).toBeNull(); // a word, not a color
    expect(hexQuery("#facade")).toBe("#facade");
  });

  it("lists the closest threads first for a color code", () => {
    const r = searchThreads(chart, "#FF7A1A");
    expect(r.hex).toBe("#ff7a1a");
    expect(r.threads[0].code).toBe("126");
    expect(r.threads).toHaveLength(4);
    expect(colorDifference("#ff7a1a", "#ff7a1a")).toBe(0);
  });

  it("puts an exact thread number first; all-digit searches stay numbers", () => {
    expect(searchThreads(chart, "126").threads.map((t) => t.code)).toEqual(["126", "1126"]);
    expect(searchThreads(chart, "900").hex).toBeNull();
    expect(searchThreads(chart, "orange").threads.map((t) => t.code)).toEqual(["126", "1126"]);
  });
});

describe("color difference", () => {
  it("is CIEDE2000, like the engine's thread matching", () => {
    expect(colorDifference("#ff0000", "#ff0000")).toBe(0);
    expect(colorDifference("#000000", "#ffffff")).toBeCloseTo(100, 0);
    expect(colorDifference("#ff7a1a", "#ff7a10")).toBeLessThan(2);
  });
});
