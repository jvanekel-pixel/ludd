import { describe, expect, it } from "vitest";
import { shade, threadLayers, THREAD_WIDTH_MM } from "./threadLook";

describe("threadLook", () => {
  it("shades toward black and white", () => {
    expect(shade("#808080", -1)).toBe("#000000");
    expect(shade("#808080", 1)).toBe("#ffffff");
    expect(shade("#ff0000", -0.5)).toBe("#800000");
    expect(shade("#f00", 0)).toBe("#ff0000");
  });

  it("flat view is one stroke; realistic is edge, body, sheen", () => {
    expect(threadLayers("#3366cc", false)).toHaveLength(1);
    const [edge, body, sheen] = threadLayers("#3366cc", true);
    expect(edge.width).toBe(THREAD_WIDTH_MM);
    expect(body.color).toBe("#3366cc");
    expect(body.width).toBeLessThan(edge.width);
    expect(sheen.width).toBeLessThan(body.width);
    expect(edge.color).not.toBe(body.color);
  });
});
