/** Freehand smoothing (P7-C1): a stroke of pointer samples becomes a few pen points whose curve
 *  stays within the Smoothing setting of the stroke, both ways. Also turning a path round (K). */
import { describe, expect, it } from "vitest";
import { distToSegment, flatten, type Pt } from "./paths";
import { MIN_STROKE_MM, reversePath, SMOOTHING_MM, simplifyStroke, strokeTolerance, trimOvershoot } from "./simplify";
import type { PathNode } from "./types";

/** An ordinary zoom: 4 screen pixels to the mm. */
const PX_MM = 1 / 4;
const TOL = strokeTolerance(3, PX_MM);

// ---------------------------------------------------------------- strokes as a pointer makes them

/** A repeatable scatter in -1..1. */
function noise(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) % 2147483648;
    return (s / 2147483648) * 2 - 1;
  };
}

/** `n` samples along f(0..1), the hand speeding up and slowing down, each rounded to the screen
 *  pixel it lands on (4 to the mm), with `jitter` mm of hand shake. */
function stroke(f: (t: number) => Pt, n = 300, jitter = 0, seed = 7): Pt[] {
  const rnd = noise(seed);
  return Array.from({ length: n }, (_, i) => {
    const t = i / (n - 1);
    const uneven = t + 0.06 * Math.sin(5 * Math.PI * t) / (5 * Math.PI);
    const [x, y] = f(Math.min(1, Math.max(0, uneven)));
    return [Math.round((x + jitter * rnd()) * 4) / 4, Math.round((y + jitter * rnd()) * 4) / 4] as Pt;
  });
}

const sCurve = stroke((t) => [10 + 60 * t, 30 + 14 * Math.sin(2 * Math.PI * t)]);
const circle = stroke((t) => [20 * Math.cos(2 * Math.PI * t), 20 * Math.sin(2 * Math.PI * t)]);
const spiral = stroke((t) => {
  const [r, a] = [3 + 15 * t, 5 * Math.PI * t];
  return [r * Math.cos(a), r * Math.sin(a)];
});
const wobble = stroke((t) => [80 * t, 9 * Math.sin((80 * t) / 13) + 0.18 * Math.sin(80 * t * 2.1)], 300, 0.08, 11);
/** A 30 mm square drawn edge by edge, `from` mm along its first side. */
const square = (from = 0, n = 300) =>
  stroke((t) => {
    const d = (from + 120 * t) % 120;
    const side = Math.floor(d / 30);
    const u = d - side * 30;
    return ([[u, 0], [30, u], [30 - u, 30], [0, 30 - u]] as Pt[])[side];
  }, n);

// ---------------------------------------------------------------- how far apart they are

const toLine = (p: Pt, line: readonly Pt[]) => Math.min(...line.slice(0, -1).map((a, i) => distToSegment(p, a, line[i + 1])));

/** Points every 0.1 mm or closer along a polyline. */
function dense(line: readonly Pt[]): Pt[] {
  const out: Pt[] = [line[0]];
  for (let i = 1; i < line.length; i++) {
    const [a, b] = [line[i - 1], line[i]];
    const k = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1));
    for (let j = 1; j <= k; j++) out.push([a[0] + ((b[0] - a[0]) * j) / k, a[1] + ((b[1] - a[1]) * j) / k]);
  }
  return out;
}

/** The furthest a sample is from the drawn curve, and the furthest the drawn curve is from the
 *  stroke (a closed shape's stroke goes back to its first point). */
function apart(nodes: readonly PathNode[], drawn: readonly Pt[], closed = false): { samples: number; curve: number } {
  const curve = flatten(nodes, closed);
  const path = closed ? [...drawn, [nodes[0][0], nodes[0][1]] as Pt] : [...drawn];
  return {
    samples: Math.max(...drawn.map((p) => toLine(p, curve))),
    curve: Math.max(...dense(curve).map((p) => toLine(p, path))),
  };
}
const within = (nodes: readonly PathNode[], drawn: readonly Pt[], tol: number, closed = false) => {
  const d = apart(nodes, drawn, closed);
  expect(d.samples).toBeLessThanOrEqual(tol);
  expect(d.curve).toBeLessThanOrEqual(tol);
};
const corners = (nodes: readonly PathNode[]) => nodes.filter((n) => n[2] === "c");
const near = (nodes: readonly PathNode[], p: Pt, r = 0.75) => nodes.some((n) => Math.hypot(n[0] - p[0], n[1] - p[1]) <= r);

describe("smoothing a freehand stroke", () => {
  it("the tolerance is the Smoothing setting, never under 1.5 screen pixels", () => {
    expect(SMOOTHING_MM).toEqual([0.15, 0.25, 0.4, 0.6, 0.9]);
    expect(TOL).toBeCloseTo(0.4);
    expect(strokeTolerance(1, PX_MM)).toBeCloseTo(0.375); // 1.5 pixels at 4 px/mm
    expect(strokeTolerance(5, PX_MM)).toBeCloseTo(0.9);
    expect(strokeTolerance(3, 1)).toBeCloseTo(1.5); // zoomed far out: the pixels rule
  });

  it("a wobbly straight stroke becomes two points", () => {
    // 60 mm along, shaking up to a quarter millimeter (a pixel) to either side.
    const s = stroke((t) => [60 * t, 0.15 * Math.sin(2 * Math.PI * 17 * t)], 240, 0.05);
    const nodes = simplifyStroke(s, TOL);
    expect(nodes).toHaveLength(2);
    expect(nodes[0].slice(0, 2)).toEqual(s[0]);
    expect(nodes[1].slice(0, 2)).toEqual(s[s.length - 1]);
    within(nodes, s, 0.4);
  });

  it("a square keeps four corners", () => {
    // Started at a corner, closed as a fill: exactly the four corners.
    const closed = square(0);
    const fill = simplifyStroke(closed, TOL, { closed: true });
    expect(fill).toHaveLength(4);
    expect(corners(fill)).toHaveLength(4);
    for (const p of [[0, 0], [30, 0], [30, 30], [0, 30]] as Pt[]) expect(near(fill, p)).toBe(true);
    within(fill, closed, 0.4, true);
    // Started in the middle of a side, drawn as a line: the four corners and its two ends.
    const open = square(12);
    const line = simplifyStroke(open, TOL);
    expect(corners(line)).toHaveLength(4);
    for (const p of [[30, 0], [30, 30], [0, 30], [0, 0]] as Pt[]) expect(near(corners(line), p)).toBe(true);
    expect(line).toHaveLength(6);
    within(line, open, 0.4);
  });

  it("a circle becomes at most 12 curve points within 0.4 mm", () => {
    const fill = simplifyStroke(circle, TOL, { closed: true });
    expect(fill.length).toBeLessThanOrEqual(12);
    expect(fill.every((n) => n[2] === "s")).toBe(true);
    within(fill, circle, 0.4, true);
  });

  it("300 samples become at most 25 points", () => {
    const strokes: [string, Pt[]][] = [
      ["S curve", sCurve],
      ["circle", circle],
      ["spiral", spiral],
      ["wobble", wobble],
      ["square", square(12)],
    ];
    for (const [name, s] of strokes) {
      expect(s).toHaveLength(300);
      const nodes = simplifyStroke(s, TOL);
      expect(nodes.length, name).toBeLessThanOrEqual(25);
      const d = apart(nodes, s);
      expect(d.samples, `${name}: samples to curve`).toBeLessThanOrEqual(0.4);
      expect(d.curve, `${name}: curve to stroke`).toBeLessThanOrEqual(0.4);
      // It starts and ends exactly where the stroke did.
      expect(nodes[0].slice(0, 2), name).toEqual(s[0]);
      expect(nodes[nodes.length - 1].slice(0, 2), name).toEqual(s[s.length - 1]);
    }
  });

  it("stays within the tolerance at any Smoothing and zoom", () => {
    for (const smooth of [1, 2, 3, 4, 5]) {
      for (const pxMm of [1 / 12, PX_MM, 1 / 2]) {
        const tol = strokeTolerance(smooth, pxMm);
        for (const s of [sCurve, spiral, wobble, square(12)]) within(simplifyStroke(s, tol), s, tol);
      }
    }
  }, 60_000); // 60 strokes: a few seconds on a slow machine


  it("smoothing 1 keeps more points than 5", () => {
    for (const s of [sCurve, spiral, wobble]) {
      const fine = simplifyStroke(s, strokeTolerance(1, 1 / 12));
      const rough = simplifyStroke(s, strokeTolerance(5, 1 / 12));
      expect(fine.length).toBeGreaterThan(rough.length);
    }
  });

  it("a tiny stroke is one click", () => {
    const tiny: Pt[] = [[5, 5], [5.5, 5.2], [6, 5.6], [6.2, 6]];
    expect(MIN_STROKE_MM).toBe(2);
    expect(simplifyStroke(tiny, TOL)).toEqual([[5, 5, "s"]]);
    expect(simplifyStroke([[5, 5]], TOL, { startKind: "l" })).toEqual([[5, 5, "l"]]);
    // A little longer, it's a line.
    expect(simplifyStroke([[5, 5], [8, 5]], TOL)).toHaveLength(2);
  });

  it("is the same every time, and keeps a given start kind", () => {
    expect(simplifyStroke(spiral, TOL)).toEqual(simplifyStroke(spiral, TOL));
    expect(simplifyStroke(sCurve, TOL, { startKind: "c" })[0][2]).toBe("c");
  });

  it("fast, sparse samples stay within the tolerance too", () => {
    // A quick zigzag: only a handful of samples, far apart.
    const zig: Pt[] = [[0, 0], [12, 7], [14, -6], [26, 5], [41, 4], [43, -9], [52, -2]];
    within(simplifyStroke(zig, TOL), zig, 0.4);
  });

  it("goes on smoothly from the pen's earlier points, or turns sharply there", () => {
    // After a long straight run of clicks, a stroke that goes on in the same direction, then one
    // that turns back: neither may swing away from the stroke.
    const before: PathNode[] = [[-60, 0, "s"]];
    const on = stroke((t) => [20 * t, 3 * Math.sin(Math.PI * t)], 120);
    const back = stroke((t) => [-4 * t, 14 * t], 80);
    for (const s of [on, back]) {
      const nodes = simplifyStroke(s, TOL, { before });
      const curve = flatten([...before, ...nodes]);
      expect(Math.max(...s.map((p) => toLine(p, curve)))).toBeLessThanOrEqual(0.4);
      // The stroke's own part of the curve stays by the stroke.
      const own = dense(curve).filter((p) => Math.hypot(p[0] - s[0][0], p[1] - s[0][1]) > 0.5 && toLine(p, [[-60, 0], [s[0][0], s[0][1]]]) > 0.5);
      expect(Math.max(0, ...own.map((p) => toLine(p, s)))).toBeLessThanOrEqual(0.4);
    }
    expect(simplifyStroke(back, TOL, { before })[0][2]).toBe("c");
  });

  it("cuts off a loop's overshoot past its first point", () => {
    // A circle drawn on 4 mm past where it began.
    const over = stroke((t) => [10 * Math.cos(2.13 * Math.PI * t), 10 * Math.sin(2.13 * Math.PI * t)], 160);
    const cut = trimOvershoot(over, [10, 0], 6);
    expect(cut.length).toBeLessThan(over.length);
    const last = cut[cut.length - 1];
    expect(Math.hypot(last[0] - 10, last[1])).toBeLessThan(0.5);
    const nodes = simplifyStroke(cut, TOL, { closed: true });
    expect(nodes.length).toBeLessThanOrEqual(12);
    within(nodes, cut, 0.4, true);
    // A stroke that stops short is left whole.
    const short = stroke((t) => [10 * Math.cos(1.95 * Math.PI * t), 10 * Math.sin(1.95 * Math.PI * t)], 150);
    expect(trimOvershoot(short, [10, 0], 6)).toEqual(short);
  });
});

describe("turning a path round (continuing from its first point)", () => {
  /** A node's coordinates and kind only (the pen's own notes left out). */
  const plain = (nodes: readonly PathNode[]) => nodes.map((n) => [n[0], n[1], n[2]]);
  const mixed: PathNode[] = [[0, 0, "s"], [10, 2, "s"], [16, 10, "c"], [26, 9, "s"], [30, 0, "s"], [40, 0, "l"], [40, 12, "l"], [48, 14, "s"], [52, 4, "c"], [60, 6, "s"]];
  const noSmoothIntoLine: PathNode[] = [[0, 0, "s"], [10, 2, "s"], [16, 10, "c"], [26, 9, "s"], [30, 0, "c"], [40, 0, "l"], [40, 12, "l"], [48, 14, "s"], [52, 4, "c"], [60, 6, "s"]];
  const hausdorff = (a: Pt[], b: Pt[]) => Math.max(...dense(a).map((p) => toLine(p, b)), ...dense(b).map((p) => toLine(p, a)));

  it("twice gives the original, whatever the kinds", () => {
    const all: PathNode[][] = [mixed, noSmoothIntoLine, [[0, 0, "c"], [5, 5, "s"]], [[0, 0, "l"], [5, 5, "c"], [9, 0, "l"]]];
    // Every way three or four kinds can follow each other.
    const kinds = ["s", "c", "l"] as const;
    for (const a of kinds) for (const b of kinds) for (const c of kinds) for (const d of kinds) all.push([[0, 0, a], [8, 1, b], [12, 9, c], [20, 7, d]]);
    for (const path of all) expect(plain(reversePath(reversePath(path)))).toEqual(path);
  });

  it("the turned path draws the same curve", () => {
    for (const path of [noSmoothIntoLine, [[0, 0, "s"], [10, 0, "c"], [10, 10, "s"]] as PathNode[], [[0, 0, "c"], [10, 6, "s"], [20, 0, "s"], [30, 9, "c"]] as PathNode[]]) {
      const back = reversePath(path);
      expect(hausdorff(flatten(back).reverse(), flatten(path))).toBeLessThan(0.05);
      expect(back.map((n) => [n[0], n[1]])).toEqual([...path].reverse().map((n) => [n[0], n[1]]));
    }
  });

  it("a smooth point before a straight stretch is sharp while turned, and comes back smooth", () => {
    // Three kinds can't hold "smooth, with a straight stretch coming in" the other way round: the
    // pen shows that point sharp, and keeps what it was.
    const path: PathNode[] = [[0, 0, "s"], [10, 6, "s"], [20, 0, "l"]];
    const back = reversePath(path);
    expect(plain(back)).toEqual([[20, 0, "c"], [10, 6, "l"], [0, 0, "s"]]);
    expect(plain(reversePath(back))).toEqual(path);
    // The straight stretch stays straight while turned round.
    expect(flatten(back.slice(0, 2))).toEqual([[20, 0], [10, 6]]);
  });

  it("a kind chosen for a point while turned round is kept", () => {
    const path: PathNode[] = [[0, 0, "s"], [10, 6, "s"], [20, 0, "l"]];
    const back = reversePath(path);
    // Switching the point's kind (C) makes a new point, so what it was before is forgotten.
    const toggled: PathNode[] = [back[0], [back[1][0], back[1][1], "c"], back[2]];
    expect(plain(reversePath(toggled))).toEqual([[0, 0, "s"], [10, 6, "c"], [20, 0, "c"]]);
  });
});
