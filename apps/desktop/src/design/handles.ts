/**
 * The selection frame's handles: four corners resize evenly (about the middle), four side handles
 * stretch one way only (the opposite side stays put), and the knob above turns. Pure, for tests.
 */
import type { Pt } from "./paths";

/** Corner (0 top-left, clockwise) or side ("n", "e", "s", "w") of a frame. */
export type Handle = { kind: "corner"; index: number } | { kind: "side"; side: "n" | "e" | "s" | "w" };

/** The middles of a frame's sides, from its four corners (clockwise from top-left): n, e, s, w. */
export function sideMids(corners: readonly Pt[]): Record<"n" | "e" | "s" | "w", Pt> {
  const mid = (a: Pt, b: Pt): Pt => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  return { n: mid(corners[0], corners[1]), e: mid(corners[1], corners[2]), s: mid(corners[2], corners[3]), w: mid(corners[3], corners[0]) };
}

/** The opposite side to a side. */
export const OPPOSITE = { n: "s", e: "w", s: "n", w: "e" } as const;

/** The mouse pointer for a handle at `at` on a frame centred at `center`: the double arrow that
 *  points the way it drags (so it's right on a turned picture too). */
export function resizeCursorFor(at: Pt, center: Pt): "resize" | "resize-nesw" | "stretch-x" | "stretch-y" {
  // Angle of the handle from the centre, 0..180 (y grows downward).
  let a = (Math.atan2(at[1] - center[1], at[0] - center[0]) * 180) / Math.PI;
  a = ((a % 180) + 180) % 180;
  if (a < 22.5 || a >= 157.5) return "stretch-x";
  if (a < 67.5) return "resize"; // down-right / up-left
  if (a < 112.5) return "stretch-y";
  return "resize-nesw"; // down-left / up-right
}

/** How much a side drag stretches: the distance from the opposite side, now over when grabbed,
 *  measured across the frame (never below 5%, never flipped). */
export function stretchFactor(anchor: Pt, grabbed: Pt, now: Pt, axis: Pt): number {
  const along = (p: Pt) => (p[0] - anchor[0]) * axis[0] + (p[1] - anchor[1]) * axis[1];
  const from = along(grabbed);
  if (Math.abs(from) < 1e-6) return 1;
  return Math.max(0.05, along(now) / from);
}

/** The unit direction across the frame for a side (from its opposite side towards it). */
export function sideAxis(corners: readonly Pt[], side: "n" | "e" | "s" | "w"): Pt {
  const m = sideMids(corners);
  const a = m[OPPOSITE[side]];
  const b = m[side];
  const l = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  return [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
}
