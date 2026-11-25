import { describe, expect, it } from "vitest";
import { fillPatternDef } from "./fillPatterns";

describe("fill pattern descriptors", () => {
  it("fillPatternDef falls back to tatami", () => {
    expect(fillPatternDef("nope").id).toBe("tatami");
    expect(fillPatternDef(undefined).id).toBe("tatami");
    expect(fillPatternDef("wave").id).toBe("wave");
  });
});
