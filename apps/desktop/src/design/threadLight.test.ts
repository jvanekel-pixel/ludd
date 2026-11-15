import { describe, expect, it } from "vitest";
import { lightOn, pliesFor, shadeAt, tintFor } from "./threadLook";

const deg = (d: number) => (d * Math.PI) / 180;

describe("realistic thread lighting", () => {
  it("lights the side of the thread that faces the light (upper left), whichever way it was sewn", () => {
    // Sewn left to right and right to left: the same stitch, so the same light, one of them flipped.
    const a = lightOn(deg(0));
    const b = lightOn(deg(180));
    expect(a.across).toBeCloseTo(b.across);
    expect(a.flip).not.toBe(b.flip);
    // A stitch pointing along the light gets it end-on; one square across gets it fully across.
    expect(lightOn(deg(45)).across).toBeCloseTo(0);
    expect(lightOn(deg(-45)).across).toBeCloseTo(1);
  });

  it("shades a round thread: lit side brighter, far side and edges darker, a highlight near the top", () => {
    const [top] = shadeAt(-0.5, 1);
    const [bottom] = shadeAt(0.5, 1);
    const [middle, shine] = shadeAt(-0.2, 1);
    const [edge] = shadeAt(0.98, 1);
    expect(top).toBeGreaterThan(bottom);
    expect(middle).toBeGreaterThan(edge);
    expect(shine).toBeGreaterThan(shadeAt(0.6, 1)[1]);
    // Light straight along the stitch: the two sides match.
    expect(shadeAt(-0.4, 0)[0]).toBeCloseTo(shadeAt(0.4, 0)[0]);
  });

  it("picks plies to suit the stitch length, and keeps the thread colour true", () => {
    expect([pliesFor(1), pliesFor(3), pliesFor(7)]).toEqual([0, 1, 2]);
    // White stays white; a mid colour is lifted a little to make up for the shaded edges.
    expect(tintFor([255, 255, 255], deg(-45))).toBe(0xffffff);
    const red = tintFor([200, 40, 40], deg(45)) >> 16;
    expect(red).toBeGreaterThanOrEqual(200);
  });
});
