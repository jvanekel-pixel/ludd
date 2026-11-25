/** Picking stitches while editing a stitch file (components/StitchCanvas.tsx). Only a stitch with
 *  a number can be picked: edits name stitches by number, and the stitches Rebuild, the density
 *  limit and jump locks add are all numbered -1. */
import { Kind, type Design } from "./types";

type Records = Design["records"];

/** Record i is one of item `owner`'s stitches that an edit can name. */
export const pickable = (r: Records, owner: number, i: number): boolean =>
  r.item?.[i] === owner && r.kind[i] === Kind.Stitch && (r.src?.[i] ?? -1) >= 0;

/** The number of item `owner`'s stitch nearest (x, y) mm, closer than `reach`; null if none.
 *  Of two equally near, the one sewn first. */
export function nearestStitch(r: Records, owner: number, x: number, y: number, reach: number): number | null {
  let best: number | null = null;
  let bestD = reach;
  for (let i = 0; i < r.kind.length; i++) {
    if (!pickable(r, owner, i)) continue;
    const d = Math.hypot(r.x[i] - x, r.y[i] - y);
    if (d < bestD) {
      bestD = d;
      best = r.src![i];
    }
  }
  return best;
}

/** The numbers of item `owner`'s stitches inside the box (mm). */
export function stitchesInBox(r: Records, owner: number, x0: number, y0: number, x1: number, y1: number): number[] {
  const out: number[] = [];
  for (let i = 0; i < r.kind.length; i++) {
    if (pickable(r, owner, i) && r.x[i] >= x0 && r.x[i] <= x1 && r.y[i] >= y0 && r.y[i] <= y1) out.push(r.src![i]);
  }
  return out;
}
