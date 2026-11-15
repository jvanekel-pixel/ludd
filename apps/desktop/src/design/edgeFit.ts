/**
 * Satin edge fit: while you draw a satin along the edge of a shape you've already made (a fill's
 * outline or one of its holes, or a line), LUDD notices and offers to lay the satin exactly along
 * that edge, round its corners and curves. Tab applies it; Tab again tries the next way; Esc puts
 * your clicked points back. Nothing changes without a key press.
 *
 * The ways, in order:
 * 1. all the way round, centred on the edge (the classic satin border over a fill's edge);
 * 2. all the way round, just outside the edge (it covers the fill's edge and frames it);
 * 3. only from your first point to your last, along the edge, in the direction you were going.
 * A line that isn't closed has 1 (the whole line, your way round) and 3.
 * Pure (no app state), for tests.
 */
import { flatten, nearestSegment, nodeBounds, type Pt } from "./paths";
import { isObject, type Layout, type ObjectItem, type PathNode, type Transform } from "./types";

/** One edge you could be following: points on the design (mm). */
export type Edge = { id: string; nodes: PathNode[]; closed: boolean; /** The edge of a hole (its outside is inside the ring). */ hole: boolean };

export type EdgeFit = { label: string; nodes: PathNode[]; closed: boolean };

/** Your points must all be this close to the edge (mm), past the satin's half width. */
const NEAR_MM = 1.5;
/** And span at least this much of it before a fit is offered. */
const MIN_SPAN_MM = 3;
/** How far the satin overlaps the shape when it sits "just outside" (mm). */
const OVERLAP_MM = 0.4;

/** Move nodes by an item's transform, as the engine does (about the middle of its points). */
function placed(lists: PathNode[][], t: Transform | undefined): PathNode[][] {
  if (!t || (t.x === 0 && t.y === 0 && t.rotate === 0 && t.scale_x === 1 && t.scale_y === 1 && !t.flip_x && !t.flip_y)) return lists;
  const b = nodeBounds(lists);
  if (!b) return lists;
  const cx = (b[0] + b[2]) / 2;
  const cy = (b[1] + b[3]) / 2;
  const a = (t.rotate * Math.PI) / 180;
  const [ca, sa] = [Math.cos(a), Math.sin(a)];
  const fx = t.flip_x ? -1 : 1;
  const fy = t.flip_y ? -1 : 1;
  return lists.map((l) =>
    l.map((n) => {
      const px = (n[0] - cx) * fx * t.scale_x;
      const py = (n[1] - cy) * fy * t.scale_y;
      return [px * ca - py * sa + cx + t.x, px * sa + py * ca + cy + t.y, n[2]] as PathNode;
    }),
  );
}

/** Every edge in the layout a satin could follow (fills' and appliques' outlines and holes, lines). */
export function edgesOf(layout: Layout, skipId?: string): Edge[] {
  const out: Edge[] = [];
  for (const it of layout.items) {
    if (!isObject(it) || it.id === skipId) continue;
    const o = it as ObjectItem;
    if (o.kind === "fill" || o.kind === "applique") {
      const [outline, ...holes] = placed([o.geometry.outline, ...(o.geometry.holes ?? [])], o.transform);
      if (outline.length >= 3) out.push({ id: o.id, nodes: outline, closed: true, hole: false });
      for (const h of holes) if (h.length >= 3) out.push({ id: o.id, nodes: h, closed: true, hole: true });
    } else if (o.kind === "run") {
      const [nodes] = placed([o.geometry.nodes], o.transform);
      if (nodes.length >= 2) out.push({ id: o.id, nodes, closed: !!o.geometry.closed, hole: false });
    }
  }
  return out;
}

/** A dense polyline along an edge, with the distance along it of every point. */
function along(edge: Edge): { pts: Pt[]; cum: number[]; length: number } {
  const pts = flatten(edge.nodes, edge.closed);
  if (edge.closed && pts.length) pts.push(pts[0]);
  const cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  return { pts, cum, length: cum[cum.length - 1] };
}

/** Where a point falls along the polyline (distance from its start) and how far off it is. */
function project(line: { pts: Pt[]; cum: number[] }, p: Pt): { s: number; d: number } {
  const { index, distance } = nearestSegment(line.pts, p);
  const a = line.pts[index];
  const b = line.pts[Math.min(index + 1, line.pts.length - 1)];
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2)) : 0;
  return { s: line.cum[index] + t * Math.sqrt(len2), d: distance };
}

/** The edge your points follow, if they all hug the same one (the closest such). */
export function followedEdge(points: Pt[], edges: Edge[], satinWidth: number): Edge | null {
  if (points.length < 2) return null;
  const reach = NEAR_MM + satinWidth / 2;
  let best: { edge: Edge; score: number } | null = null;
  for (const edge of edges) {
    const line = along(edge);
    if (line.pts.length < 2) continue;
    const proj = points.map((p) => project(line, p));
    if (proj.some((q) => q.d > reach)) continue;
    // They must go somewhere along it, not just sit on one spot.
    const span = Math.max(...proj.map((q) => q.s)) - Math.min(...proj.map((q) => q.s));
    if (span < MIN_SPAN_MM && !(edge.closed && line.length - span < MIN_SPAN_MM)) continue;
    const score = proj.reduce((sum, q) => sum + q.d, 0) / proj.length;
    if (!best || score < best.score) best = { edge, score };
  }
  return best?.edge ?? null;
}

const signedArea = (nodes: PathNode[]) => {
  let a = 0;
  for (let i = 0; i < nodes.length; i++) {
    const p = nodes[i];
    const q = nodes[(i + 1) % nodes.length];
    a += p[0] * q[1] - q[0] * p[1];
  }
  return a / 2;
};

/** The ring's nodes, starting at the one nearest `p` (so the satin starts where you started). */
function startingNear(nodes: PathNode[], p: Pt): PathNode[] {
  let k = 0;
  let best = Infinity;
  nodes.forEach((n, i) => {
    const d = Math.hypot(n[0] - p[0], n[1] - p[1]);
    if (d < best) [best, k] = [d, i];
  });
  return [...nodes.slice(k), ...nodes.slice(0, k)];
}

/** Nodes moved sideways by `d` mm (positive: to the left of the direction of travel). */
function offsetNodes(nodes: PathNode[], closed: boolean, d: number): PathNode[] {
  const n = nodes.length;
  return nodes.map((nd, i) => {
    const prev = closed ? nodes[(i - 1 + n) % n] : nodes[Math.max(0, i - 1)];
    const next = closed ? nodes[(i + 1) % n] : nodes[Math.min(n - 1, i + 1)];
    const unit = (a: PathNode, b: PathNode): Pt => {
      const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      return [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
    };
    const din = unit(prev, nd);
    const dout = unit(nd, next);
    // The left-hand normal of the average direction, stretched at corners so the sides stay parallel.
    let tx = din[0] + dout[0];
    let ty = din[1] + dout[1];
    const tl = Math.hypot(tx, ty) || 1;
    tx /= tl;
    ty /= tl;
    const cos = Math.max(0.5, tx * dout[0] + ty * dout[1]);
    const k = d / cos;
    return [nd[0] + ty * k, nd[1] - tx * k, nd[2]] as PathNode;
  });
}

/** Your points' direction along a closed edge: +1 the way its points go, -1 the other way. */
function direction(line: { pts: Pt[]; cum: number[]; length: number }, points: Pt[], closed: boolean): 1 | -1 {
  const s0 = project(line, points[0]).s;
  const s1 = project(line, points[Math.min(1, points.length - 1)]).s;
  if (!closed) return s1 >= s0 ? 1 : -1;
  const ahead = (((s1 - s0) % line.length) + line.length) % line.length;
  return ahead <= line.length / 2 ? 1 : -1;
}

/** The ways to lay a satin `satinWidth` wide along `edge`, for the points you clicked. */
export function fitsAlong(edge: Edge, points: Pt[], satinWidth: number): EdgeFit[] {
  const line = along(edge);
  const dir = direction(line, points, edge.closed);
  const fits: EdgeFit[] = [];
  const ordered = (nodes: PathNode[]) => (dir === 1 ? nodes : reversedPath(nodes, edge.closed));
  if (edge.closed) {
    const ring = startingNear(ordered(edge.nodes), points[0]);
    fits.push({ label: "all the way round, on the edge", nodes: ring, closed: true });
    // "Outside" is away from the shape: outward for its outline, into the hole for a hole.
    const ccw = signedArea(ring) > 0; // on screen (y down) a positive area runs clockwise
    const leftIsOutside = ccw !== edge.hole;
    const d = Math.max(0, satinWidth / 2 - OVERLAP_MM) * (leftIsOutside ? 1 : -1);
    fits.push({ label: "all the way round, just outside the edge", nodes: offsetNodes(ring, true, d), closed: true });
  } else {
    fits.push({ label: "the whole line", nodes: ordered(edge.nodes), closed: false });
  }
  const part = partAlong(edge, line, points, dir);
  if (part && part.length >= 2) fits.push({ label: "from your first point to here, along the edge", nodes: part, closed: false });
  return fits;
}

/** A path's nodes the other way round (a node's kind belongs to the stretch coming into it). */
function reversedPath(nodes: PathNode[], closed: boolean): PathNode[] {
  const n = nodes.length;
  return nodes.map((_, i) => {
    const j = n - 1 - i;
    const kindFrom = closed ? nodes[(j + 1) % n][2] : (nodes[j + 1]?.[2] ?? nodes[j][2]);
    return [nodes[j][0], nodes[j][1], kindFrom] as PathNode;
  });
}

/** The stretch of the edge between your first and last points, going your way. */
function partAlong(edge: Edge, line: { pts: Pt[]; cum: number[]; length: number }, points: Pt[], dir: 1 | -1): PathNode[] | null {
  const s0 = project(line, points[0]).s;
  const s1 = project(line, points[points.length - 1]).s;
  const L = line.length;
  const span = edge.closed ? ((((s1 - s0) * dir) % L) + L) % L : (s1 - s0) * dir;
  if (span < MIN_SPAN_MM || (edge.closed && span > L * 0.9)) return null;
  const at = (s: number): Pt => {
    const v = edge.closed ? ((s % L) + L) % L : Math.max(0, Math.min(L, s));
    let i = line.cum.findIndex((c) => c >= v);
    if (i <= 0) return line.pts[Math.max(0, i)];
    const t = (v - line.cum[i - 1]) / (line.cum[i] - line.cum[i - 1] || 1);
    const a = line.pts[i - 1];
    const b = line.pts[i];
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  };
  // The edge's own points that fall inside the stretch keep their kind (corners stay corners).
  const inner: { u: number; node: PathNode }[] = [];
  for (const nd of edge.nodes) {
    const s = project(line, [nd[0], nd[1]]).s;
    const u = edge.closed ? ((((s - s0) * dir) % L) + L) % L : (s - s0) * dir;
    if (u > 0.3 && u < span - 0.3) inner.push({ u, node: nd });
  }
  inner.sort((a, b) => a.u - b.u);
  const first = at(s0);
  const last = at(s0 + dir * span);
  // Going against the edge's own direction, each kept point's kind is the stretch after it.
  const kinds = new Map<PathNode, PathNode[2]>();
  if (dir === -1) {
    const rev = reversedPath(edge.nodes, edge.closed);
    edge.nodes.forEach((nd, i) => kinds.set(nd, rev[edge.nodes.length - 1 - i][2]));
  }
  return [
    [first[0], first[1], "s"],
    ...inner.map(({ node }) => [node[0], node[1], kinds.get(node) ?? node[2]] as PathNode),
    [last[0], last[1], "s"],
  ];
}

/** Everything at once: the edge your points follow and the ways to fit the satin to it (or none). */
export function edgeFitsFor(layout: Layout, points: Pt[], satinWidth: number, skipId?: string): EdgeFit[] {
  const edge = followedEdge(points, edgesOf(layout, skipId), satinWidth);
  return edge ? fitsAlong(edge, points, satinWidth) : [];
}
