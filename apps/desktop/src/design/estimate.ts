/**
 * How long a design takes to sew and how much thread it uses, roughly.
 *
 * Time: stitches at the machine's top speed (machines slow down on long stitches, so real sewing
 * is often a little longer), plus nothing for thread changes, which are counted separately
 * because they take as long as the person takes.
 *
 * Thread: the length of every stitch and jump (a jump drags thread across until it's cut), plus
 * an allowance per stitch for the thread that goes down into the fabric and back. The bobbin uses
 * about a third of the top thread on typical designs.
 */
import { Kind, type Design, type Machine } from "./types";

/** Stitches per minute assumed when the machine profile doesn't say. */
export const DEFAULT_SPEED_SPM = 600;
/** Top thread per stitch for going into the fabric and back, in mm. */
export const PER_STITCH_MM = 1;
/** Bobbin thread as a share of the top thread. */
export const BOBBIN_SHARE = 1 / 3;

export type ThreadUse = { thread: number; meters: number };

export type Estimate = {
  /** Machine sewing time at top speed, in minutes. */
  minutes: number;
  speedSpm: number;
  /** Times someone has to change the thread or press start again (color changes and stops). */
  threadChanges: number;
  /** Top thread per thread (in the order each is first sewn). */
  perThread: ThreadUse[];
  topMeters: number;
  bobbinMeters: number;
};

export function speedOf(machine: Pick<Machine, "speed_spm"> | null | undefined): number {
  const v = machine?.speed_spm;
  return typeof v === "number" && Number.isFinite(v) && v > 0 ? v : DEFAULT_SPEED_SPM;
}

export function estimate(design: Pick<Design, "info" | "blocks" | "records">, machine?: Pick<Machine, "speed_spm"> | null): Estimate {
  const { x, y, kind } = design.records;
  const speedSpm = speedOf(machine);
  const mmByThread = new Map<number, number>();
  for (const b of design.blocks) {
    let mm = 0;
    let px = NaN;
    let py = NaN;
    for (let i = b.start; i < b.end && i < kind.length; i++) {
      const k = kind[i];
      if (k === Kind.Stitch || k === Kind.Jump) {
        if (!Number.isNaN(px)) mm += Math.hypot(x[i] - px, y[i] - py);
        if (k === Kind.Stitch) mm += PER_STITCH_MM;
        px = x[i];
        py = y[i];
      } else if (k === Kind.Trim) {
        // The thread is cut: the move to the next stitch uses none.
        px = NaN;
        py = NaN;
      }
    }
    mmByThread.set(b.thread, (mmByThread.get(b.thread) ?? 0) + mm);
  }
  const perThread = [...mmByThread].map(([thread, mm]) => ({ thread, meters: mm / 1000 }));
  const topMeters = perThread.reduce((a, t) => a + t.meters, 0);
  return {
    minutes: design.info.stitches / speedSpm,
    speedSpm,
    threadChanges: Math.max(0, design.info.colors - 1) + design.info.stops,
    perThread,
    topMeters,
    bobbinMeters: topMeters * BOBBIN_SHARE,
  };
}

/** "about 1 min", "about 14 min", "about 1 h 05 min". Never "0 min" for a design with stitches. */
export function fmtMinutes(minutes: number): string {
  const m = Math.max(1, Math.round(minutes));
  if (m < 60) return `about ${m} min`;
  return `about ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

/** Thread length: "under 1 m", "about 4.5 m", "about 38 m" (or yards). */
export function fmtThread(meters: number, units: "mm" | "in" = "mm"): string {
  const inches = units === "in";
  const v = inches ? meters / 0.9144 : meters;
  const unit = inches ? "yd" : "m";
  if (v < 1) return `under 1 ${unit}`;
  return v < 10 ? `about ${(Math.round(v * 2) / 2).toFixed(1)} ${unit}` : `about ${Math.round(v)} ${unit}`;
}
