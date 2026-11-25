import { describe, expect, it } from "vitest";
import { shapeNodes as fromLayout } from "./layout";
import { dist, distToSegment, flatten, nearestSegment, type Pt } from "./paths";
import { shapeNodes, type ShapeId } from "./shapes";
import type { PathNode } from "./types";

const SHAPES: ShapeId[] = ["rectangle", "circle", "star", "roundedRect", "ellipse", "triangle", "polygon", "heart"];
const SIDES = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
/** [cx, cy, size]: the app's own size, one off the middle and off whole numbers, and a bigger one. */
const PLACES: [number, number, number][] = [
  [0, 0, 60],
  [12.5, -7.3, 33.3],
  [-20.25, 15.75, 90],
];

/** Every shape, the polygon with each number of sides. */
function every(cx: number, cy: number, size: number): { name: string; nodes: PathNode[] }[] {
  return [
    ...SHAPES.map((s) => ({ name: s, nodes: shapeNodes(s, cx, cy, size) })),
    ...SIDES.map((sides) => ({ name: `polygon, ${sides} sides`, nodes: shapeNodes("polygon", cx, cy, size, { sides }) })),
  ];
}

function box(pts: readonly (readonly unknown[])[]) {
  const xs = pts.map((p) => p[0] as number);
  const ys = pts.map((p) => p[1] as number);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, width: x1 - x0, height: y1 - y0 };
}

/** Points no more than `step` mm apart all along a polyline. */
function along(poly: readonly Pt[], step = 0.05): Pt[] {
  const out: Pt[] = [];
  for (let i = 0; i + 1 < poly.length; i++) {
    const [a, b] = [poly[i], poly[i + 1]];
    const k = Math.max(1, Math.ceil(dist(a, b) / step));
    for (let s = 0; s < k; s++) out.push([a[0] + ((b[0] - a[0]) * s) / k, a[1] + ((b[1] - a[1]) * s) / k]);
  }
  out.push(poly[poly.length - 1]);
  return out;
}

describe("ready-made shape outlines", () => {
  it("each shape is centered and the right width", () => {
    for (const [cx, cy, size] of PLACES) {
      for (const { name, nodes } of every(cx, cy, size)) {
        if (name === "star") {
          // The star is the one it always was (see the next test): centered on the circle its five
          // points sit on, so its box is a little high and narrower than `size`.
          for (const i of [0, 2, 4, 6, 8]) expect(Math.hypot(nodes[i][0] - cx, nodes[i][1] - cy), name).toBeCloseTo(size / 2, 1);
          continue;
        }
        // The outline as it's drawn and sewn, curves and all, and the points themselves (what the
        // engine turns and mirrors a shape about).
        for (const [of, b] of [["outline", box(flatten(nodes, true))], ["points", box(nodes)]] as const) {
          const what = `${name} ${of} at ${cx}, ${cy}, ${size}`;
          expect(Math.abs(b.cx - cx), what).toBeLessThanOrEqual(0.01);
          expect(Math.abs(b.cy - cy), what).toBeLessThanOrEqual(0.01);
          expect(Math.abs(b.width - size), what).toBeLessThanOrEqual(0.5);
        }
      }
    }
  });

  it("the three old shapes are unchanged", () => {
    // Copied from what design/layout.ts made before the shapes moved here.
    expect(shapeNodes("rectangle", 0, 0, 60)).toEqual([[-30, -21, "c"], [30, -21, "c"], [30, 21, "c"], [-30, 21, "c"]]);
    expect(shapeNodes("circle", 0, 0, 60)).toEqual([[30, 0, "s"], [21.21, 21.21, "s"], [0, 30, "s"], [-21.21, 21.21, "s"], [-30, 0, "s"], [-21.21, -21.21, "s"], [0, -30, "s"], [21.21, -21.21, "s"]]);
    expect(shapeNodes("star", 0, 0, 60)).toEqual([[0, -30, "c"], [7.94, -10.92, "c"], [28.53, -9.27, "c"], [12.84, 4.17, "c"], [17.63, 24.27, "c"], [0, 13.5, "c"], [-17.63, 24.27, "c"], [-12.84, 4.17, "c"], [-28.53, -9.27, "c"], [-7.94, -10.92, "c"]]);
    expect(shapeNodes("rectangle", 12.5, -7.3, 33.3)).toEqual([[-4.15, -18.95, "c"], [29.15, -18.95, "c"], [29.15, 4.35, "c"], [-4.15, 4.35, "c"]]);
    expect(shapeNodes("circle", 12.5, -7.3, 33.3)).toEqual([[29.15, -7.3, "s"], [24.27, 4.47, "s"], [12.5, 9.35, "s"], [0.73, 4.47, "s"], [-4.15, -7.3, "s"], [0.73, -19.07, "s"], [12.5, -23.95, "s"], [24.27, -19.07, "s"]]);
    expect(shapeNodes("star", 12.5, -7.3, 33.3)).toEqual([[12.5, -23.95, "c"], [16.9, -13.36, "c"], [28.34, -12.45, "c"], [19.63, -4.98, "c"], [22.29, 6.17, "c"], [12.5, 0.19, "c"], [2.71, 6.17, "c"], [5.37, -4.98, "c"], [-3.34, -12.45, "c"], [8.1, -13.36, "c"]]);
    // design/layout.ts still offers it, as before.
    expect(fromLayout).toBe(shapeNodes);
  });

  it("a polygon has n corners, first at the top", () => {
    for (const sides of [3, 6, 12]) {
      const nodes = shapeNodes("polygon", 5, -3, 40, { sides });
      expect(nodes).toHaveLength(sides);
      expect(nodes.every((n) => n[2] === "c")).toBe(true);
      expect(nodes[0][0]).toBeCloseTo(5, 2);
      expect(nodes.slice(1).every((n) => n[1] > nodes[0][1] + 0.5)).toBe(true);
      // Regular: every side the same length, every corner turning the same amount.
      const edge = nodes.map((n, i) => {
        const m = nodes[(i + 1) % sides];
        return [m[0] - n[0], m[1] - n[1]];
      });
      for (const [i, e] of edge.entries()) {
        const next = edge[(i + 1) % sides];
        expect(Math.hypot(e[0], e[1])).toBeCloseTo(Math.hypot(edge[0][0], edge[0][1]), 1);
        const turn = (Math.atan2(e[0] * next[1] - e[1] * next[0], e[0] * next[0] + e[1] * next[1]) * 180) / Math.PI;
        expect(Math.abs(turn - 360 / sides)).toBeLessThan(0.2);
      }
    }
    // Without a number of sides it's a hexagon; an odd number is kept to 3 to 12.
    expect(shapeNodes("polygon", 0, 0, 60)).toHaveLength(6);
    expect(shapeNodes("polygon", 0, 0, 60, { sides: 2 })).toHaveLength(3);
    expect(shapeNodes("polygon", 0, 0, 60, { sides: 40 })).toHaveLength(12);
    expect(shapeNodes("polygon", 0, 0, 60, { sides: 7.4 })).toHaveLength(7);
    expect(shapeNodes("polygon", 0, 0, 60, { sides: Number.NaN })).toHaveLength(6);
  });

  it("the rounded rectangle stays within 0.35 mm of a true one", () => {
    for (const [cx, cy, size] of PLACES) {
      const [hw, hh, r] = [size / 2, (0.7 * size) / 2, 0.15 * size];
      /** How far a point is from the true outline. */
      const off = ([x, y]: Pt) => {
        const [qx, qy] = [Math.abs(x - cx) - (hw - r), Math.abs(y - cy) - (hh - r)];
        return Math.abs(Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - r);
      };
      const nodes = shapeNodes("roundedRect", cx, cy, size);
      const drawn = flatten(nodes, true);
      const samples = along(drawn);
      // Both ways round: nothing drawn strays from the true outline, and none of it is left out.
      expect(Math.max(...samples.map(off))).toBeLessThanOrEqual(0.35);
      const truth: Pt[] = [];
      const corners: [number, number, number][] = [
        [cx + hw - r, cy - hh + r, -90],
        [cx + hw - r, cy + hh - r, 0],
        [cx - hw + r, cy + hh - r, 90],
        [cx - hw + r, cy - hh + r, 180],
      ];
      for (const [ox, oy, from] of corners) {
        for (let a = from; a <= from + 90; a += 0.5) truth.push([ox + r * Math.cos((a * Math.PI) / 180), oy + r * Math.sin((a * Math.PI) / 180)]);
      }
      truth.push(truth[0]);
      expect(Math.max(...along(truth).map((p) => nearestSegment(drawn, p).distance))).toBeLessThanOrEqual(0.35);
      // The sides between the corners are straight.
      for (const [x, y] of samples) {
        if (Math.abs(x - cx) < hw - r - 0.01) expect(Math.abs(Math.abs(y - cy) - hh)).toBeLessThanOrEqual(0.01);
        if (Math.abs(y - cy) < hh - r - 0.01) expect(Math.abs(Math.abs(x - cx) - hw)).toBeLessThanOrEqual(0.01);
      }
      // Three curve points on each corner's arc.
      const curve = nodes.filter((n) => n[2] === "s");
      expect(curve).toHaveLength(12);
      for (const [ox, oy, from] of corners) {
        const mine = curve.filter((n) => Math.abs(Math.hypot(n[0] - ox, n[1] - oy) - r) < 0.01);
        expect(mine, `corner from ${from}°`).toHaveLength(3);
      }
    }
  });

  it("no shape repeats a point", () => {
    for (const [cx, cy, size] of [...PLACES, [0, 0, 5], [0, 0, 240]] as [number, number, number][]) {
      for (const { name, nodes } of every(cx, cy, size)) {
        for (const [i, n] of nodes.entries()) {
          const next = nodes[(i + 1) % nodes.length]; // closed: the last joins the first
          expect(Math.hypot(next[0] - n[0], next[1] - n[1]), `${name} point ${i}, size ${size}`).toBeGreaterThan(0.05);
        }
      }
    }
  });

  it("every outline makes a good fill: it never crosses itself, and goes the same way round", () => {
    const side = (a: Pt, b: Pt, c: Pt) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
    for (const { name, nodes } of every(0, 0, 60)) {
      const ring = flatten(nodes, true).filter((p, i, all) => i === 0 || dist(p, all[i - 1]) > 1e-9);
      if (dist(ring[0], ring[ring.length - 1]) < 1e-9) ring.pop();
      const n = ring.length;
      // Clockwise on screen (y down), like the rectangle.
      const twiceArea = ring.reduce((sum, p, i) => sum + p[0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * p[1], 0);
      expect(twiceArea, name).toBeGreaterThan(0);
      const run = ring.reduce<number[]>((at, p, i) => [...at, at[i] + dist(p, ring[(i + 1) % n])], [0]); // how far round each point is
      const crossings: string[] = [];
      for (let i = 0; i < n; i++) {
        const [a, b] = [ring[i], ring[(i + 1) % n]];
        for (let j = i + 2; j < n; j++) {
          if (i === 0 && j === n - 1) continue; // neighbors round the join
          const [c, d] = [ring[j], ring[(j + 1) % n]];
          const apart = Math.min(run[j] - run[i + 1], run[n] - run[j] + run[i]); // along the outline, from one to the other
          if (side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0) crossings.push(`${i} and ${j}`);
          // Nor may the outline come back and touch itself (points crowd close going into a sharp
          // point, so only parts well apart along the outline count).
          else if (apart > 1 && distToSegment(c, a, b) < 0.05) crossings.push(`${j} touches ${i}`);
        }
      }
      expect(crossings, name).toEqual([]);
    }
  });

  it("the oval, the triangle and the heart are the shapes asked for", () => {
    for (const shape of ["ellipse", "roundedRect"] as const) expect(box(flatten(shapeNodes(shape, 0, 0, 60), true)).height).toBeCloseTo(42, 1);
    const oval = shapeNodes("ellipse", 2, 3, 40);
    expect(oval).toHaveLength(8);
    expect(oval.every((n) => n[2] === "s" && Math.abs(Math.hypot((n[0] - 2) / 20, (n[1] - 3) / 14) - 1) < 0.001)).toBe(true);

    const triangle = shapeNodes("triangle", 0, 0, 60);
    expect(triangle).toHaveLength(3);
    expect(triangle.every((n) => n[2] === "c")).toBe(true);
    expect(triangle[0][0]).toBe(0); // point up
    expect(triangle[0][1]).toBeLessThan(Math.min(triangle[1][1], triangle[2][1]));
    for (const [i, n] of triangle.entries()) expect(dist([n[0], n[1]], [triangle[(i + 1) % 3][0], triangle[(i + 1) % 3][1]])).toBeCloseTo(60, 1);

    const heart = shapeNodes("heart", 5, -4, 60);
    const corners = heart.filter((n) => n[2] === "c");
    expect(corners).toHaveLength(2);
    expect(heart.filter((n) => n[2] === "s")).toHaveLength(heart.length - 2);
    expect(corners.every((n) => n[0] === 5)).toBe(true);
    const [dip, tip] = [...corners].sort((a, b) => a[1] - b[1]);
    expect(tip[1]).toBe(Math.max(...heart.map((n) => n[1]))); // the tip is the bottom
    const top = Math.min(...heart.map((n) => n[1]));
    expect(dip[1] - top).toBeGreaterThan(60 * 0.08); // a dip you can see between the lobes
    expect(dip[1]).toBeLessThan(-4);
    // The same left and right.
    for (const [x, y, kind] of heart) expect(heart.some((m) => Math.abs(m[0] - (10 - x)) < 0.011 && Math.abs(m[1] - y) < 0.011 && m[2] === kind), `${x}, ${y}`).toBe(true);
  });
});
