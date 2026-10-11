/**
 * Pen-tool paths in the UI: the same curve rule as the engine (engine/threadline_engine/digitize/paths.py)
 * so what you see while drawing matches the stitches. Corner nodes stay sharp; curve nodes get
 * Catmull-Rom tangents (cubic Hermite segments).
 */

import type { PathNode } from "./types";

export type Pt = [number, number];

const STEP_MM = 0.25;
const MAX_SAMPLES = 96;

export function flatten(nodes: readonly PathNode[], closed = false): Pt[] {
  const n = nodes.length;
  if (n === 0) return [];
  const p = nodes.map((nd) => [nd[0], nd[1]] as Pt);
  if (n === 1) return [p[0]];
  const tangent = (i: number): Pt => {
    if (nodes[i][2] !== "s") return [0, 0];
    const prev = closed ? p[(i - 1 + n) % n] : p[Math.max(0, i - 1)];
    const next = closed ? p[(i + 1) % n] : p[Math.min(n - 1, i + 1)];
    return [(next[0] - prev[0]) / 2, (next[1] - prev[1]) / 2];
  };
  const out: Pt[] = [p[0]];
  const segs = closed ? n : n - 1;
  for (let i = 0; i < segs; i++) {
    const j = (i + 1) % n;
    const [p0, p1] = [p[i], p[j]];
    const [t0, t1] = [tangent(i), tangent(j)];
    if (!t0[0] && !t0[1] && !t1[0] && !t1[1]) {
      out.push(p1);
      continue;
    }
    const c1: Pt = [p0[0] + t0[0] / 3, p0[1] + t0[1] / 3];
    const c2: Pt = [p1[0] - t1[0] / 3, p1[1] - t1[1] / 3];
    const approx = dist(p0, c1) + dist(c1, c2) + dist(c2, p1);
    const k = Math.max(2, Math.min(MAX_SAMPLES, Math.ceil(approx / STEP_MM)));
    for (let s = 1; s <= k; s++) {
      const t = s / k;
      const u = 1 - t;
      out.push([
        u * u * u * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p1[0],
        u * u * u * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p1[1],
      ]);
    }
  }
  return out;
}

export function dist(a: Pt, b: Pt) {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

/** Bounds of the nodes themselves (what the engine pivots transforms on). */
export function nodeBounds(lists: readonly (readonly PathNode[])[]): [number, number, number, number] | null {
  const all = lists.flat();
  if (!all.length) return null;
  const xs = all.map((n) => n[0]);
  const ys = all.map((n) => n[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

/** Index of the segment of `poly` nearest the point, and the distance to it. */
export function nearestSegment(poly: readonly Pt[], p: Pt): { index: number; distance: number } {
  let best = { index: -1, distance: Infinity };
  for (let i = 0; i + 1 < poly.length; i++) {
    const d = distToSegment(p, poly[i], poly[i + 1]);
    if (d < best.distance) best = { index: i, distance: d };
  }
  return best;
}

export function distToSegment(p: Pt, a: Pt, b: Pt): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2)) : 0;
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

/** Which node-to-node span of the original nodes a point falls on (for inserting a node). */
export function spanAt(nodes: readonly PathNode[], closed: boolean, p: Pt, tolerance: number): number | null {
  let best: { span: number; d: number } | null = null;
  const spans = closed ? nodes.length : nodes.length - 1;
  for (let i = 0; i < spans; i++) {
    const seg = flatten([nodes[i], nodes[(i + 1) % nodes.length]]);
    // Curved spans depend on neighbours; flatten the local window for an accurate test.
    const window = closed
      ? [nodes[(i - 1 + nodes.length) % nodes.length], nodes[i], nodes[(i + 1) % nodes.length], nodes[(i + 2) % nodes.length]]
      : nodes.slice(Math.max(0, i - 1), Math.min(nodes.length, i + 3));
    const poly = nodes[i][2] === "s" || nodes[(i + 1) % nodes.length][2] === "s" ? flatten(window as PathNode[]) : seg;
    const d = nearestSegment(poly, p).distance;
    if (d <= tolerance && (!best || d < best.d)) best = { span: i, d };
  }
  return best?.span ?? null;
}
