/**
 * The handles you drag along a shape's edge, as in Embrilliance: the start and end dots (green and
 * red) and the stitch-direction dots (purple). Each slides round the inside of the outline,
 * following the point of the edge nearest the mouse. Pure, for tests.
 */
import { flatten, type Pt } from "./paths";
import type { ObjectItem, PathNode } from "./types";

/** The point of a closed or open polyline nearest `p`. */
export function nearestOnLine(pts: readonly Pt[], p: Pt, closed: boolean): Pt {
  if (pts.length === 1) return pts[0];
  let best: Pt = pts[0];
  let bestD = Infinity;
  const n = closed ? pts.length : pts.length - 1;
  for (let i = 0; i < n; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const len2 = dx * dx + dy * dy;
    const t = len2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2)) : 0;
    const q: Pt = [a[0] + t * dx, a[1] + t * dy];
    const d = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (d < bestD) {
      bestD = d;
      best = q;
    }
  }
  return best;
}

/** The point nearest `p` on any of several outlines (a fill's outside and its holes). */
export function nearestOnRings(rings: readonly (readonly Pt[])[], p: Pt): Pt {
  let best: Pt = p;
  let bestD = Infinity;
  for (const r of rings) {
    if (r.length < 2) continue;
    const q = nearestOnLine(r, p, true);
    const d = Math.hypot(q[0] - p[0], q[1] - p[1]);
    if (d < bestD) {
      bestD = d;
      best = q;
    }
  }
  return best;
}

/** The middle of a polygon (its area centroid; the average of its points if it has no area). */
export function centroid(ring: readonly Pt[]): Pt {
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x0, y0] = ring[i];
    const [x1, y1] = ring[(i + 1) % ring.length];
    const c = x0 * y1 - x1 * y0;
    a += c;
    cx += (x0 + x1) * c;
    cy += (y0 + y1) * c;
  }
  if (Math.abs(a) < 1e-9) return [ring.reduce((s, q) => s + q[0], 0) / ring.length, ring.reduce((s, q) => s + q[1], 0) / ring.length];
  return [cx / (3 * a), cy / (3 * a)];
}

/** Where a line through `c` at `angleDeg` crosses the ring: the nearest crossing each way. */
export function chord(ring: readonly Pt[], c: Pt, angleDeg: number): [Pt, Pt] | null {
  const a = (angleDeg * Math.PI) / 180;
  const u: Pt = [Math.cos(a), Math.sin(a)];
  let fwd = Infinity;
  let back = -Infinity;
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i];
    const q = ring[(i + 1) % ring.length];
    const e: Pt = [q[0] - p[0], q[1] - p[1]];
    const den = u[0] * e[1] - u[1] * e[0];
    if (Math.abs(den) < 1e-12) continue;
    const w: Pt = [p[0] - c[0], p[1] - c[1]];
    const t = (w[0] * e[1] - w[1] * e[0]) / den; // along the line
    const s = (w[0] * u[1] - w[1] * u[0]) / den; // along the edge
    if (s < 0 || s > 1) continue;
    if (t >= 0 && t < fwd) fwd = t;
    if (t <= 0 && t > back) back = t;
  }
  if (!isFinite(fwd) || !isFinite(back)) return null;
  return [
    [c[0] + u[0] * back, c[1] + u[1] * back],
    [c[0] + u[0] * fwd, c[1] + u[1] * fwd],
  ];
}

/** A line's direction as a fill angle: degrees 0–180, as the Angle setting shows it. */
export function angleOf(a: Pt, b: Pt): number {
  const d = (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI;
  return Math.round((((d % 180) + 180) % 180) * 10) / 10;
}

/** The outline a fill's direction dots slide along. */
export function fillRing(o: ObjectItem): Pt[] {
  return flatten((o.geometry as { outline: PathNode[] }).outline, true);
}

/** Patterns whose rows don't follow an angle (no direction dots for them). */
const NO_ANGLE = ["contour", "stipple"];

/** A fill's two purple direction dots: where you left them, or across its middle at its angle. */
export function fillDirection(o: ObjectItem): [Pt, Pt] | null {
  if (o.kind !== "fill") return null;
  const p = o.params as { angle_deg?: number; angle_line?: [Pt, Pt]; pattern?: string };
  if (p.pattern && NO_ANGLE.includes(p.pattern)) return null;
  const angle = p.angle_deg ?? 45;
  const line = p.angle_line;
  // The dots you placed, as long as the angle is still theirs (typed in the panel, it's not).
  const ring = fillRing(o);
  // Still on the outline (a reshaped outline puts them back across the middle).
  const onEdge = (q: Pt) => {
    const e = nearestOnLine(ring, q, true);
    return Math.hypot(e[0] - q[0], e[1] - q[1]) < 1;
  };
  if (line && Math.abs(angleOf(line[0], line[1]) - (((angle % 180) + 180) % 180)) < 0.6 && onEdge(line[0]) && onEdge(line[1])) return line;
  return ring.length >= 3 ? chord(ring, centroid(ring), angle) : null;
}

/** A satin column's outline (side a, then side b back), which its tips slide along. */
export function columnRing(g: { rail_a: PathNode[]; rail_b: PathNode[] }): Pt[] {
  const a = flatten(g.rail_a);
  const b = flatten(g.rail_b).reverse();
  return [...a, ...b];
}

/** A satin column's two tips (the middles of its first and last stitches). `out` (mm) moves each
 *  one that far out past the end of the column, so a purple dot doesn't sit on the start or end dot. */
export function columnTips(o: ObjectItem, out = 0): [Pt, Pt] | null {
  if (o.kind !== "satin" || !("rail_a" in o.geometry)) return null;
  const { rail_a: a, rail_b: b } = o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] };
  if (a.length < 2 || b.length < 2) return null;
  const mid = (k: number): Pt => [(a[k][0] + b[k][0]) / 2, (a[k][1] + b[k][1]) / 2];
  const last = Math.min(a.length, b.length) - 1;
  const beyond = (tip: Pt, inner: Pt): Pt => {
    const l = Math.hypot(tip[0] - inner[0], tip[1] - inner[1]) || 1;
    return [tip[0] + ((tip[0] - inner[0]) / l) * out, tip[1] + ((tip[1] - inner[1]) / l) * out];
  };
  // Outward: away from the middle of the shape (the tips are on its edge).
  const c = centroid(columnRing(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] }));
  return [beyond(mid(0), c), beyond(mid(last), c)];
}
