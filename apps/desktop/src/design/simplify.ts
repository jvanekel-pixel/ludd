/**
 * Freehand drawing's smoothing (P7-C1) and turning pen paths round (P7-C2). Pure functions on
 * pointer samples and pen points, drawn with the pen's own curve rule (paths.ts, the engine's too).
 *
 * A stroke becomes pen points in steps: samples closer than 0.15 mm to the last one are dropped as
 * places for a point; Ramer-Douglas-Peucker keeps the ones the shape needs; a kept point where the
 * stroke turns more than 50 degrees (over 1 mm either side) is a sharp corner, the rest curve
 * points. A smooth curve through points can bow further from them than straight lines do, so
 * points are then added where the drawn curve strays, and curve points are dropped while it stays
 * close. "Close" is both ways, within the tolerance: every sample to the curve, and every point of
 * the curve to the stroke.
 */
import { distToSegment, flatten, type Pt } from "./paths";
import type { NodeKind, PathNode } from "./types";

/** How close the curve stays to the stroke, mm, by the Smoothing setting 1 to 5. */
export const SMOOTHING_MM = [0.15, 0.25, 0.4, 0.6, 0.9] as const;
export const DEFAULT_SMOOTHING = 3;
/** A shorter stroke is one click. */
export const MIN_STROKE_MM = 2;
/** The tolerance is never finer than this many screen pixels. */
const LEAST_PX = 1.5;
/** A point can't go closer than this to the sample before it. */
const SAME_SAMPLE_MM = 0.15;
/** Stretches longer than this are spread a piece at a time. */
const SPREAD_PIECE_MM = 100;
const CORNER_DEG = 50;
const CORNER_REACH_MM = 1;
/** A closed stroke gets no point this near where it closes (a tiny stretch bends the curve). */
const BY_THE_CLOSING_MM = 0.5;
/** Samples further apart than this (a quick flick) get points along the way, so a pen point can
 *  go between them. */
const FILL_IN_MM = 0.5;
/** The curve is never checked finer than this. */
const FINEST_MM = 0.02;
/** Checked a hair tighter than asked: the pen's points are rounded to 0.01 mm. */
const MARGIN_MM = 0.01;

export function strokeTolerance(smooth: number, pxMm: number): number {
  const i = Math.min(SMOOTHING_MM.length, Math.max(1, Math.round(smooth) || DEFAULT_SMOOTHING)) - 1;
  return Math.max(SMOOTHING_MM[i], LEAST_PX * pxMm);
}

const dist = (a: Pt, b: Pt) => Math.hypot(b[0] - a[0], b[1] - a[1]);

export function strokeLength(pts: readonly Pt[]): number {
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += dist(pts[i - 1], pts[i]);
  return total;
}

/** A loop drawn a little past where it began: it ends at its sample nearest `loopEnd` within its
 *  last `windowMm` (never looking back further than half the stroke). */
export function trimOvershoot(samples: readonly Pt[], loopEnd: Pt, windowMm: number): Pt[] {
  const limit = Math.min(windowMm, strokeLength(samples) / 2);
  let best = samples.length - 1;
  let travelled = 0;
  for (let i = samples.length - 2; i >= 0; i--) {
    travelled += dist(samples[i], samples[i + 1]);
    if (travelled > limit) break;
    if (dist(samples[i], loopEnd) < dist(samples[best], loopEnd) - 1e-9) best = i;
  }
  return samples.slice(0, best + 1) as Pt[];
}

export type SimplifyOptions = {
  /** The pen's points before the stroke starts (the point it starts at not included). */
  before?: readonly PathNode[];
  /** The kind the press gave the stroke's first point ("s" unless Ctrl or Shift was held). */
  startKind?: NodeKind;
  /** The stroke closes a fill: it goes on to the outline's first point. */
  closed?: boolean;
};

export type Stroke = {
  /** The stroke's pen points: its first is the one it starts at. */
  nodes: PathNode[];
  /** For a closing stroke after earlier points: the kind the outline's first point must have now
   *  (sharp where the shape turns sharply there, or where a smooth point would swing the curve). */
  closingKind?: NodeKind;
};

/** A freehand stroke as pen points, from its first sample (the pen point it starts at) to its
 *  last; a closing stroke's way back to the outline's first point needs no point of its own.
 *  Under 2 mm long it's one click: just the first point. */
export function fitStroke(samples: readonly Pt[], tolerance: number, opts: SimplifyOptions = {}): Stroke {
  const start = samples[0];
  const startKind = opts.startKind ?? "s";
  const before = opts.before ?? [];
  if (samples.length < 2 || strokeLength(samples) < MIN_STROKE_MM) return { nodes: [[start[0], start[1], startKind]], closingKind: opts.closed ? before[0]?.[2] : undefined };
  return new Fit(samples, Math.max(0.02, tolerance - MARGIN_MM), before, startKind, !!opts.closed).run();
}

/** The stroke's pen points alone (see fitStroke). */
export const simplifyStroke = (samples: readonly Pt[], tolerance: number, opts: SimplifyOptions = {}): PathNode[] =>
  fitStroke(samples, tolerance, opts).nodes;

// ---------------------------------------------------------------- fitting

type Interior = { at: number; kind: "s" | "c" };
type Spans = { err: number; at: number };

class Fit {
  /** The stroke as drawn (a closing one back to the outline's first point), filled in. */
  private ref: Pt[];
  private cum: number[];
  /** Where a point may go (samples at least 0.15 mm apart). */
  private spot: boolean[];
  private interior: Interior[] = [];
  private startKind: NodeKind;
  private seen = new Map<string, Spans>();
  private skipped = new Set<string>();
  /** The earlier points; a closing stroke may sharpen the first of them. */
  private before: PathNode[];

  constructor(
    samples: readonly Pt[],
    private limit: number,
    before: readonly PathNode[],
    startKind: NodeKind,
    private closed: boolean,
  ) {
    this.before = [...before];
    const loopEnd: Pt = before.length ? [before[0][0], before[0][1]] : samples[0];
    this.ref = fillIn(closed ? [...samples, loopEnd] : samples, FILL_IN_MM);
    this.cum = [0];
    for (let i = 1; i < this.ref.length; i++) this.cum.push(this.cum[i - 1] + dist(this.ref[i - 1], this.ref[i]));
    const last = this.ref.length - 1;
    const endGap = closed ? Math.max(this.limit, BY_THE_CLOSING_MM) : SAME_SAMPLE_MM;
    this.spot = this.ref.map(() => false);
    let kept = 0;
    for (let i = 1; i < last; i++) {
      if (dist(this.ref[i], this.ref[kept]) < SAME_SAMPLE_MM) continue;
      if (this.cum[last] - this.cum[i] < endGap || dist(this.ref[i], this.ref[last]) < SAME_SAMPLE_MM) continue;
      this.spot[i] = true;
      kept = i;
    }
    this.startKind = startKind === "s" && this.startTurnsSharply() ? "c" : startKind;
    if (closed && this.before[0]?.[2] === "s" && this.closingTurnsSharply()) this.sharpenClosing();
  }

  run(): Stroke {
    const spots = this.spot.map((ok, i) => (ok ? i : -1)).filter((i) => i >= 0);
    const all = [0, ...spots, this.ref.length - 1];
    const kept = rdp(all.map((i) => this.ref[i]), this.limit).map((k) => all[k]);
    this.interior = this.cornered(kept.slice(1, -1));
    this.spreadEvenly();
    this.addWhereItStrays();
    this.dropWhileItStaysClose();
    this.keepAnArea();
    return { nodes: this.strokeNodes(this.interior), closingKind: this.closed ? this.before[0]?.[2] : undefined };
  }

  // ---- even spreading

  /** Each stretch between corners gets the fewest curve points, spread along it more densely
   *  where it bends, that hold the curve close (a curve through evenly spread points strays far
   *  less than one through unevenly spread ones). A stretch no spread fits keeps the points RDP
   *  found, for the next steps to add to. */
  private spreadEvenly(): void {
    const corners = [0, ...this.interior.filter((p) => p.kind === "c").map((p) => p.at), this.ref.length - 1];
    // A long stretch is spread a piece at a time: the time a spread takes grows with its length.
    const breaks = [0];
    for (let b = 0; b + 1 < corners.length; b++) {
      const [lo, hi] = [corners[b], corners[b + 1]];
      const pieces = Math.ceil((this.cum[hi] - this.cum[lo]) / SPREAD_PIECE_MM);
      for (let j = 1; j < pieces; j++) {
        const at = this.spotNear(lo, hi, this.cum[lo] + ((this.cum[hi] - this.cum[lo]) * j) / pieces);
        if (at <= breaks[breaks.length - 1]) continue;
        if (!this.interior.some((p) => p.at === at)) this.addAt(at);
        breaks.push(at);
      }
      breaks.push(hi);
    }
    const weights = this.bendWeights();
    for (let b = 0; b + 1 < breaks.length; b++) this.spreadSection(breaks[b], breaks[b + 1], weights);
  }

  /** How much of a point's share each sample's stretch of stroke deserves: a little everywhere,
   *  more where it bends (as a curve's distance from the stroke grows with its bend). */
  private bendWeights(): number[] {
    const out = [0];
    for (let i = 1; i < this.ref.length; i++) {
      const s = (this.cum[i - 1] + this.cum[i]) / 2;
      const bend = (turnBetween(this.along(s - 3), this.along(s), this.along(s + 3)) * Math.PI) / 180 / 3; // radians a mm
      out.push(out[i - 1] + (this.cum[i] - this.cum[i - 1]) * (0.02 + Math.pow(bend, 0.75)));
    }
    return out;
  }

  private spreadSection(lo: number, hi: number, weights: number[]): void {
    const inside = (p: Interior) => p.at > lo && p.at < hi;
    const others = this.interior.filter((p) => !inside(p));
    const original = this.interior;
    const spots: number[] = [];
    for (let i = lo + 1; i < hi; i++) if (this.spot[i]) spots.push(i);
    const total = weights[hi] - weights[lo];
    let best: Interior[] | null = null;
    /** Spread `k` points along the stretch; true if they hold it, with a point or two added. */
    const spread = (k: number): boolean => {
      const chosen: Interior[] = [];
      let next = 0;
      for (let j = 1; j <= k; j++) {
        const want = weights[lo] + (total * j) / (k + 1);
        while (next + 1 < spots.length && Math.abs(weights[spots[next + 1]] - want) <= Math.abs(weights[spots[next]] - want)) next++;
        const at = spots[next];
        if (at !== undefined && chosen[chosen.length - 1]?.at !== at) chosen.push({ at, kind: "s" });
      }
      this.interior = [...others, ...chosen].sort((a, b) => a.at - b.at);
      // A point or two more may be all a good spread needs (the ends often do).
      if (!this.fitSection(lo, hi, 2)) return false;
      if (!best || this.interior.length < best.length) best = this.interior;
      return true;
    };
    // Counts in growing jumps until one holds, then the ones jumped over, fewest first.
    const most = Math.min(spots.length, 60);
    let failed = -1;
    let k = 0;
    while (k <= most && !spread(k)) {
      failed = k;
      k += Math.max(1, k >> 2);
    }
    if (best) {
      for (let j = failed + 1; j < k; j++) if (spread(j)) break;
      spread(k + 1);
    }
    this.interior = best ?? original;
  }

  /** Whether the stretches from sample `lo` to `hi` stay close, adding up to `spare` points
   *  where they stray. */
  private fitSection(lo: number, hi: number, spare: number): boolean {
    for (let out = this.straying(lo, hi); out; out = this.straying(lo, hi)) {
      if (!spare--) return false;
      const pos = this.pos(this.interior);
      const here = this.spotToAdd(pos[out.k], pos[out.k + 1], out.at);
      if (here < 0) return false;
      this.addAt(here);
    }
    return true;
  }

  /** A spot for a point in a stretch that strays at sample `at`: in the stretch's middle three
   *  fifths (points bunched at one end bend the curve), or -1. */
  private spotToAdd(lo: number, hi: number, at: number): number {
    const length = this.cum[hi] - this.cum[lo];
    return this.spotNear(lo, hi, Math.min(this.cum[hi] - 0.2 * length, Math.max(this.cum[lo] + 0.2 * length, this.cum[at])));
  }

  // ---- the stroke

  /** The point `s` mm along the stroke (a self-closing loop goes round). */
  private along(s: number): Pt {
    const total = this.cum[this.cum.length - 1];
    const d = this.loops() ? ((s % total) + total) % total : Math.min(total, Math.max(0, s));
    let lo = 0;
    let hi = this.cum.length - 1;
    while (lo < hi - 1) {
      const mid = (lo + hi) >> 1;
      if (this.cum[mid] <= d) lo = mid;
      else hi = mid;
    }
    const seg = this.cum[hi] - this.cum[lo];
    const t = seg ? (d - this.cum[lo]) / seg : 0;
    const [a, b] = [this.ref[lo], this.ref[hi]];
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  }

  private loops(): boolean {
    return this.closed && !this.before.length;
  }

  /** How sharply the stroke turns at sample `i`, measured over 1 mm either side. */
  private turnAt(i: number): number {
    return turnBetween(this.along(this.cum[i] - CORNER_REACH_MM), this.ref[i], this.along(this.cum[i] + CORNER_REACH_MM));
  }

  private sharpenClosing(): void {
    this.before[0] = [this.before[0][0], this.before[0][1], "c"];
  }

  /** Whether the shape turns sharply at the outline's first point, where a closing stroke ends:
   *  from the stroke's last millimeter on towards the outline's second point. */
  private closingTurnsSharply(): boolean {
    const last = this.ref.length - 1;
    const next: Pt = this.before.length > 1 ? [this.before[1][0], this.before[1][1]] : this.ref[0];
    return turnBetween(this.along(this.cum[last] - CORNER_REACH_MM), this.ref[last], next) > CORNER_DEG;
  }

  /** A first point where the stroke turns sharply: from the pen's earlier points into the stroke,
   *  or where a loop that begins here comes back round. */
  private startTurnsSharply(): boolean {
    const start = this.ref[0];
    if (this.loops()) return this.turnAt(0) > CORNER_DEG;
    if (!this.before.length) return false;
    const lead = flatten([...this.before.slice(-2), [start[0], start[1], "s"]]);
    return turnBetween(pointBack(lead, CORNER_REACH_MM), start, this.along(CORNER_REACH_MM)) > CORNER_DEG;
  }

  // ---- steps

  /** The kept points with their kinds: a corner moves to the sharpest spot within 1 mm, and two
   *  corners within 1 mm of each other are one (the sharper). */
  private cornered(kept: number[]): Interior[] {
    const corners: { at: number; turn: number }[] = [];
    const curves: number[] = [];
    for (const i of kept) {
      if (this.turnAt(i) <= CORNER_DEG) {
        curves.push(i);
        continue;
      }
      let best = { at: i, turn: this.turnAt(i) };
      for (let j = i - 1; j > 0 && this.cum[i] - this.cum[j] <= CORNER_REACH_MM; j--) if (this.spot[j] && this.turnAt(j) > best.turn + 1e-9) best = { at: j, turn: this.turnAt(j) };
      for (let j = i + 1; j < this.ref.length - 1 && this.cum[j] - this.cum[i] <= CORNER_REACH_MM; j++) if (this.spot[j] && this.turnAt(j) > best.turn + 1e-9) best = { at: j, turn: this.turnAt(j) };
      corners.push(best);
    }
    corners.sort((a, b) => b.turn - a.turn || a.at - b.at);
    const chosen: number[] = [];
    // A loop's first point, when sharp, is a corner too.
    const total = this.cum[this.cum.length - 1];
    const taken = this.loops() && this.startKind !== "s" ? [0, total] : [];
    for (const c of corners) if (![...taken, ...chosen.map((j) => this.cum[j])].some((s) => Math.abs(this.cum[c.at] - s) < CORNER_REACH_MM)) chosen.push(c.at);
    const out: Interior[] = chosen.map((at) => ({ at, kind: "c" as const }));
    // Curve points right on top of a corner add nothing.
    for (const i of curves) if (!chosen.some((j) => Math.abs(this.cum[i] - this.cum[j]) < CORNER_REACH_MM / 2)) out.push({ at: i, kind: "s" });
    return out.sort((a, b) => a.at - b.at);
  }

  private strokeNodes(interior: Interior[]): PathNode[] {
    const node = (i: number, kind: NodeKind): PathNode => [this.ref[i][0], this.ref[i][1], kind];
    const out = [node(0, this.startKind), ...interior.map((p) => node(p.at, p.kind))];
    if (!this.closed) out.push(node(this.ref.length - 1, "s"));
    return out;
  }

  private pos(interior: Interior[]): number[] {
    return [0, ...interior.map((p) => p.at), this.ref.length - 1];
  }

  /** How far stretch `k` of these points is from the stroke between them. Over the tolerance,
   *  it stops at the first spot that is (`at`, a sample there) unless `exact`, which finds the
   *  furthest; within it, `err` is at most a little more than the furthest it gets. */
  private spanError(interior: Interior[], list: PathNode[], k: number, exact = false): Spans {
    const j = this.before.length + k;
    const around = [-1, 0, 1, 2].map((d) => {
      const m = this.closed ? (j + d + list.length) % list.length : j + d;
      return m < 0 || m >= list.length ? "-" : list[m].join(",");
    });
    const pos = this.pos(interior);
    const [lo, hi] = [pos[k], pos[k + 1]];
    const key = `${exact ? "!" : ""}${lo}:${hi}:${around.join(";")}`;
    const found = this.seen.get(key);
    if (found) return found;
    const curve = segmentCurve(list, j, this.closed);
    const stop = exact ? Infinity : this.limit;
    // Both are looked up near where the last point was found: good enough while it's close, and
    // the whole stretch is searched for any point that looks too far, so "too far" is exact.
    let worst = { err: 0, at: lo };
    let hint = 0;
    for (let r = lo; r <= hi && worst.err <= stop; r++) {
      const found = nearestFrom(this.ref[r], curve, 0, curve.length - 1, hint, this.limit);
      hint = found.segment;
      if (found.d > worst.err) worst = { err: found.d, at: r };
    }
    // And the curve against the stroke, with a millimeter to spare either side.
    let from = lo;
    while (from > 0 && this.cum[lo] - this.cum[from] < CORNER_REACH_MM) from--;
    let to = hi;
    while (to < this.ref.length - 1 && this.cum[to] - this.cum[hi] < CORNER_REACH_MM) to++;
    // Every point of the curve, not just the ones drawn: a stretch of it is sure to be within the
    // limit when its two ends' distances plus its length allow no further; else it's halved.
    hint = from;
    const off = (p: Pt): number => {
      const found = nearestFrom(p, this.ref, from, to, hint, this.limit);
      hint = found.segment;
      if (found.d > worst.err) worst = { err: found.d, at: found.index };
      return found.d;
    };
    const between = (a: Pt, da: number, b: Pt, db: number): void => {
      const length = dist(a, b);
      if (worst.err > stop || (da + db + length) / 2 <= this.limit || length < FINEST_MM) return;
      const mid: Pt = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      const dm = off(mid);
      between(a, da, mid, dm);
      between(mid, dm, b, db);
    };
    if (worst.err <= stop) {
      let last = off(curve[0]);
      for (let c = 1; c < curve.length && worst.err <= stop; c++) {
        const here = off(curve[c]);
        between(curve[c - 1], last, curve[c], here);
        last = here;
      }
    }
    this.seen.set(key, worst);
    return worst;
  }

  /** The first stretch between samples `lo` and `hi` that is further out than the tolerance,
   *  and its sample furthest out. */
  private straying(lo = 0, hi = this.ref.length - 1): { k: number; at: number } | null {
    const list = [...this.before, ...this.strokeNodes(this.interior)];
    const pos = this.pos(this.interior);
    for (let k = 0; k + 1 < pos.length; k++) {
      if (pos[k] < lo || pos[k + 1] > hi || this.skipped.has(`${pos[k]}:${pos[k + 1]}`)) continue;
      if (this.spanError(this.interior, list, k).err > this.limit) return { k, at: this.spanError(this.interior, list, k, true).at };
    }
    return null;
  }

  private addAt(i: number): void {
    const nearCorner = this.interior.some((p) => p.kind === "c" && Math.abs(this.cum[p.at] - this.cum[i]) < CORNER_REACH_MM);
    const point: Interior = { at: i, kind: !nearCorner && this.turnAt(i) > CORNER_DEG ? "c" : "s" };
    this.interior = [...this.interior, point].sort((a, b) => a.at - b.at);
  }

  /** The spot between samples `lo` and `hi` nearest `s` mm along, or -1. */
  private spotNear(lo: number, hi: number, s: number): number {
    let best = -1;
    for (let i = lo + 1; i < hi; i++) if (this.spot[i] && (best < 0 || Math.abs(this.cum[i] - s) < Math.abs(this.cum[best] - s))) best = i;
    return best;
  }

  private addWhereItStrays(): void {
    for (let worst = this.straying(); worst; worst = this.straying()) {
      const pos = this.pos(this.interior);
      const [lo, hi] = [pos[worst.k], pos[worst.k + 1]];
      const here = this.spotToAdd(lo, hi, worst.at);
      if (here >= 0) {
        this.addAt(here);
        continue;
      }
      // No room in it: a point in a longer stretch beside it changes the curve's slope there.
      const beside = [worst.k - 1, worst.k + 1]
        .filter((k) => k >= 0 && k + 1 < pos.length)
        .sort((a, b) => this.cum[pos[b + 1]] - this.cum[pos[b]] - (this.cum[pos[a + 1]] - this.cum[pos[a]]) || a - b);
      const aside = beside.map((k) => this.spotNear(pos[k], pos[k + 1], (this.cum[pos[k]] + this.cum[pos[k + 1]]) / 2)).find((i) => i >= 0);
      if (aside !== undefined) {
        this.addAt(aside);
        continue;
      }
      if (!this.sharpen(worst.k, worst.at)) this.skipped.add(`${lo}:${hi}`);
    }
  }

  /** Make an end of stretch `k` sharp (the one nearer sample `at`), which stops the curve
   *  swinging there. False when neither can be. */
  private sharpen(k: number, at: number): boolean {
    const pos = this.pos(this.interior);
    const ends = [k, k + 1].sort((a, b) => Math.abs(pos[a] - at) - Math.abs(pos[b] - at) || a - b);
    for (const e of ends) {
      // A closing stroke's last stretch ends on the outline's first point.
      if (this.closed && e === pos.length - 1) {
        if (this.before[0]?.[2] !== "s") continue;
        this.sharpenClosing();
        return true;
      }
      if (e === 0 && this.startKind === "s") {
        this.startKind = "c";
        return true;
      }
      const p = this.interior[e - 1];
      if (e > 0 && p && p.kind === "s") {
        this.interior = this.interior.map((q) => (q === p ? { at: q.at, kind: "c" } : q));
        return true;
      }
    }
    return false;
  }

  /** Drop curve points, the one that matters least first, while the curve stays close. */
  private dropWhileItStaysClose(): void {
    for (;;) {
      let best: { i: number; err: number } | null = null;
      for (let i = 0; i < this.interior.length; i++) {
        if (this.interior[i].kind !== "s") continue;
        if (this.closed && this.before.length + this.interior.length < 3) continue;
        const trial = this.interior.filter((_, k) => k !== i);
        const list = [...this.before, ...this.strokeNodes(trial)];
        // Dropping point i (stretch i ends there) changes that stretch and the ones beside it.
        let err = 0;
        for (let k = Math.max(0, i - 1); k <= Math.min(trial.length, i + 1) && err <= this.limit; k++) err = Math.max(err, this.spanError(trial, list, k).err);
        // A loop's first and last stretches lean on points at the other end too.
        if (this.closed && err <= this.limit) for (const k of [0, trial.length]) err = Math.max(err, this.spanError(trial, list, k).err);
        if (err <= this.limit && (!best || err < best.err - 1e-9)) best = { i, err };
      }
      if (!best) return;
      const drop = best.i;
      this.interior = this.interior.filter((_, k) => k !== drop);
    }
  }

  /** A closed outline needs three points to hold any area. */
  private keepAnArea(): void {
    while (this.closed && this.before.length + 1 + this.interior.length < 3) {
      const pos = this.pos(this.interior);
      const spans = pos.slice(0, -1).map((lo, k) => ({ lo, hi: pos[k + 1], length: this.cum[pos[k + 1]] - this.cum[lo] }));
      const longest = spans.sort((a, b) => b.length - a.length)[0];
      const i = this.spotNear(longest.lo, longest.hi, (this.cum[longest.lo] + this.cum[longest.hi]) / 2);
      if (i < 0) return;
      this.addAt(i);
    }
  }
}

// ---------------------------------------------------------------- geometry

/** Points along the way wherever two are more than `step` apart; every given point is kept. */
function fillIn(pts: readonly Pt[], step: number): Pt[] {
  const out: Pt[] = pts.length ? [pts[0]] : [];
  for (let i = 1; i < pts.length; i++) {
    const [a, b] = [pts[i - 1], pts[i]];
    const k = Math.max(1, Math.ceil(dist(a, b) / step - 1e-9));
    for (let j = 1; j < k; j++) out.push([a[0] + ((b[0] - a[0]) * j) / k, a[1] + ((b[1] - a[1]) * j) / k]);
    out.push(b);
  }
  return out;
}

/** The points kept by Ramer-Douglas-Peucker (indices into `pts`, in order, ends included). */
function rdp(pts: readonly Pt[], tolerance: number): number[] {
  const keep = new Set<number>([0, pts.length - 1]);
  const stack: [number, number][] = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop()!;
    let far = -1;
    let most = tolerance;
    for (let i = a + 1; i < b; i++) {
      const d = distToSegment(pts[i], pts[a], pts[b]);
      if (d > most) [far, most] = [i, d];
    }
    if (far < 0) continue;
    keep.add(far);
    stack.push([a, far], [far, b]);
  }
  return [...keep].sort((x, y) => x - y);
}

/** The drawn curve of the stretch from list[j] to the next point, as paths.ts draws it. */
function segmentCurve(list: readonly PathNode[], j: number, closed: boolean): Pt[] {
  const n = list.length;
  let window: PathNode[];
  let at: number; // where list[j] is in the window
  if (n <= 4) {
    window = closed ? [...list, ...list.slice(0, 1)] : [...list];
    // (The whole path: its curve is split below at each point in turn.)
    const whole = flatten(list, closed);
    return piece(whole, window, j);
  }
  if (closed) {
    window = [-1, 0, 1, 2].map((d) => list[(j + d + n) % n]);
    at = 1;
  } else {
    const from = Math.max(0, j - 1);
    window = list.slice(from, Math.min(n, j + 3));
    at = j - from;
  }
  return piece(flatten(window), window, at);
}

/** The part of a flattened path between its point `at` and the next: each point of the path is in
 *  the flattened line exactly, in order. */
function piece(line: readonly Pt[], nodes: readonly PathNode[], at: number): Pt[] {
  let start = 0;
  for (let k = 1; k <= at; k++) {
    let i = start + 1;
    while (i < line.length - 1 && !(line[i][0] === nodes[k][0] && line[i][1] === nodes[k][1])) i++;
    start = i;
  }
  const end = nodes[at + 1];
  let stop = start + 1;
  while (stop < line.length - 1 && !(line[stop][0] === end[0] && line[stop][1] === end[1])) stop++;
  return line.slice(start, stop + 1) as Pt[];
}

/** How far `p` is from the line's points `from` to `to`, looking first around segment `hint`:
 *  the whole range is searched when nothing there is within `close`. `index`: the nearest end of
 *  the nearest segment. */
function nearestFrom(p: Pt, line: readonly Pt[], from: number, to: number, hint: number, close: number): { d: number; segment: number; index: number } {
  const scan = (a: number, b: number) => {
    let best = { d: Infinity, segment: a };
    for (let i = a; i < b; i++) {
      const d = distToSegment(p, line[i], line[i + 1]);
      if (d < best.d) best = { d, segment: i };
    }
    return best;
  };
  if (to <= from) return { d: dist(p, line[from]), segment: from, index: from };
  const around = Math.min(to - 1, Math.max(from, hint));
  let best = scan(Math.max(from, around - 2), Math.min(to, around + 12));
  if (best.d > close) best = scan(from, to);
  const i = best.segment;
  return { ...best, index: dist(p, line[i]) <= dist(p, line[i + 1]) ? i : i + 1 };
}

/** The point `back` mm back along a line from its end. */
function pointBack(line: readonly Pt[], back: number): Pt {
  let left = back;
  for (let i = line.length - 1; i > 0; i--) {
    const [b, a] = [line[i], line[i - 1]];
    const d = dist(a, b);
    if (d >= left) return [b[0] + ((a[0] - b[0]) * left) / d, b[1] + ((a[1] - b[1]) * left) / d];
    left -= d;
  }
  return line[0];
}

/** How far the path a → b → c turns at b, degrees (0 when either side has no length). */
function turnBetween(a: Pt, b: Pt, c: Pt): number {
  const [ux, uy, vx, vy] = [b[0] - a[0], b[1] - a[1], c[0] - b[0], c[1] - b[1]];
  const long = Math.hypot(ux, uy) * Math.hypot(vx, vy);
  if (long < 1e-9) return 0;
  return (Math.acos(Math.min(1, Math.max(-1, (ux * vx + uy * vy) / long))) * 180) / Math.PI;
}

// ---------------------------------------------------------------- turning a path round

/** A pen point while a path is turned round can carry a note: what its kind alone can't hold the
 *  other way round ("s": smooth, though a straight stretch comes into it; "l": a first point's
 *  "straight", which has no stretch to go with). paths.ts and the canvas read only the kind. */
type Noted = [number, number, NodeKind, ("s" | "l")?];

const smooth = (n: Noted) => n[2] === "s" || n[3] === "s";
const lineIn = (n: Noted) => n[2] === "l" || n[3] === "l";

/**
 * A path the other way round, as the engine turns lines (jumps.py `_reversed_path`) for its
 * straight stretches: a stretch's "straight" goes with the stretch, so it moves to the point at its
 * other end. A point's sharpness stays with the point (the engine moves that too, which bends mixed
 * paths). Turning round twice gives back exactly the same points. The one thing three kinds can't
 * say turned round is a smooth point with a straight stretch coming into it: it shows sharp while
 * turned, and keeps its note.
 */
export function reversePath(nodes: readonly PathNode[]): PathNode[] {
  const path = nodes as readonly Noted[];
  const n = path.length;
  return path.map((_, i) => {
    const node = path[n - 1 - i];
    const [x, y] = node;
    const curve = smooth(node);
    if (i === 0) {
      // The new first point has no stretch coming in: any "straight" the old one had is only noted.
      const own = lineIn(path[0]);
      return (curve ? (own ? [x, y, "s", "l"] : [x, y, "s"]) : [x, y, own ? "l" : "c"]) as unknown as PathNode;
    }
    const straight = lineIn(path[n - i]);
    return (straight ? (curve ? [x, y, "l", "s"] : [x, y, "l"]) : [x, y, curve ? "s" : "c"]) as unknown as PathNode;
  });
}

/** Points without their notes, as they're kept in a shape. */
export const plainNodes = (nodes: readonly PathNode[]): PathNode[] => nodes.map(([x, y, kind]) => [x, y, kind]);
