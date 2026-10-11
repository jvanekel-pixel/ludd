import { describe, expect, it } from "vitest";
import { heatColor } from "./heat";

describe("density map colors", () => {
  it("leaves ordinary stitching clear and grows warmer and stronger toward too dense", () => {
    expect(heatColor(70, 128)[3]).toBe(0); // one layer with underlay is about 64
    const near = heatColor(100, 128);
    const at = heatColor(128, 128);
    const over = heatColor(255, 128);
    expect(near[3]).toBeGreaterThan(0);
    expect(at[3]).toBeGreaterThan(near[3]);
    expect(over[0]).toBe(255);
    expect(over[1]).toBeLessThan(at[1]); // redder
  });
});
