/**
 * Trace Assist in the UI: while drawing over a picture, ask the engine for the next point after
 * every click and show it as a ghost. Tab accepts; nothing is ever added without a key press.
 */

import { penAdd, penFinish } from "./actions";
import type { PathNode, RefImage } from "./design/types";
import { savePrefs } from "./prefs";
import { useStore, type Ghost, type Pen } from "./store";

export const STEP_MIN_MM = 1;
export const STEP_MAX_MM = 12;
const KEEP_GOING_MAX = 400;

type Suggestion = {
  ghost: [number, number] | null;
  confidence: number;
  corner: boolean;
  alternatives: [number, number][];
  close: boolean;
  rails?: [[number, number], [number, number]];
  mode: string;
};

/** The topmost visible picture under a point (mm), if any. */
export function pictureUnder(images: readonly RefImage[], x: number, y: number): RefImage | null {
  for (let i = images.length - 1; i >= 0; i--) {
    const im = images[i];
    if (!im.visible) continue;
    const a = (-im.rotate * Math.PI) / 180;
    const dx = x - im.x;
    const dy = y - im.y;
    const lx = dx * Math.cos(a) - dy * Math.sin(a);
    const ly = dx * Math.sin(a) + dy * Math.cos(a);
    if (Math.abs(lx) <= im.width_mm / 2 && Math.abs(ly) <= im.height_mm / 2) return im;
  }
  return null;
}

/** The points the engine should continue from: the shape's points, or a satin's rung centres. */
export function tracePoints(pen: Pen): [number, number][] | null {
  if (pen.kind !== "satin") return pen.a.map((n) => [n[0], n[1]]);
  // Only between complete pairs: the next suggestion is a whole rung.
  if (pen.a.length !== pen.b.length || !pen.a.length) return null;
  return pen.a.map((n, i) => [(n[0] + pen.b[i][0]) / 2, (n[1] + pen.b[i][1]) / 2]);
}

let seq = 0;

async function refresh() {
  const s = useStore.getState();
  const { pen, engine, traceAssist } = s;
  const doc = s.history.present;
  const pts = pen ? tracePoints(pen) : null;
  if (!traceAssist || !engine || !doc || !pen || !pts?.length) {
    if (s.ghost) s.setGhost(null);
    return;
  }
  const last = pts[pts.length - 1];
  const img = pictureUnder(doc.images, last[0], last[1]);
  if (!img) {
    if (s.ghost) s.setGhost(null);
    return;
  }
  const my = ++seq;
  try {
    const r = await engine.call<Suggestion>("trace.suggest", {
      path: img.path,
      placement: { x: img.x, y: img.y, width_mm: img.width_mm, height_mm: img.height_mm, rotate: img.rotate },
      points: pts,
      step_mm: s.traceStep,
      closed: pen.kind === "fill",
      satin: pen.kind === "satin",
    });
    if (my !== seq || useStore.getState().pen !== pen) return;
    s.setGhost(
      r.ghost
        ? { point: r.ghost, alternatives: r.alternatives, confidence: r.confidence, corner: r.corner, close: r.close, rails: r.rails ?? null }
        : null,
    );
  } catch {
    // Trace Assist is a helper; if it can't answer, drawing carries on without it.
    if (my === seq) s.setGhost(null);
  }
}

/** Ask for a new suggestion whenever the pen, pictures, step or setting changes. */
export function startTraceAssist() {
  return useStore.subscribe((s, prev) => {
    if (s.pen !== prev.pen || s.traceStep !== prev.traceStep || s.traceAssist !== prev.traceAssist || s.history.present?.images !== prev.history.present?.images) {
      void refresh();
    }
  });
}

/** Accept the ghost (or alternative `which`, 1-based). Returns false if there was nothing to accept. */
export function acceptGhost(which = 1): boolean {
  const s = useStore.getState();
  const g = s.ghost;
  const pen = s.pen;
  if (!g || !pen) return false;
  const point = which === 1 ? g.point : g.alternatives[which - 2];
  if (!point) return false;
  const kind: PathNode[2] = g.corner ? "c" : "s";
  s.setGhost(null);
  if (pen.kind === "satin" && g.rails) {
    // Keep each side on its own rail: match the proposed pair to the previous rung's sides.
    const [r1, r2] = g.rails;
    const lastA = pen.a[pen.a.length - 1];
    const d = (p: [number, number], q: PathNode) => Math.hypot(p[0] - q[0], p[1] - q[1]);
    const [toA, toB] = d(r1, lastA) <= d(r2, lastA) ? [r1, r2] : [r2, r1];
    penAdd([toA[0], toA[1], kind]);
    penAdd([toB[0], toB[1], kind]);
    return true;
  }
  if (g.close && pen.kind === "fill") {
    void penFinish();
    return true;
  }
  penAdd([point[0], point[1], kind]);
  return true;
}

// Tab presses are queued, so pressing quickly never loses one (or moves keyboard focus):
// each waits for the next suggestion to arrive, then accepts it.
let queue: Promise<unknown> = Promise.resolve();
// Bumped by Esc: presses still waiting in the queue are dropped.
let generation = 0;

export function cancelTraceQueue() {
  generation++;
}

export function queueAccept(which = 1) {
  const gen = generation;
  queue = queue.then(async () => {
    if (gen !== generation || !useStore.getState().pen) return;
    if (!useStore.getState().ghost && !(await waitForGhost())) return;
    if (gen !== generation) return;
    acceptGhost(which);
    // Let the pen update before the next queued press looks for a new suggestion.
    await new Promise((r) => setTimeout(r, 0));
  });
}

export function queueAcceptMany() {
  const gen = generation;
  queue = queue.then(() => acceptMany(gen));
}

/** Shift+Tab: keep accepting until a corner, a junction, an unsure spot or the shape closes. */
export async function acceptMany(gen = generation) {
  for (let i = 0; i < KEEP_GOING_MAX && gen === generation; i++) {
    const g = useStore.getState().ghost;
    if (!g) {
      // Wait briefly for the next suggestion to arrive.
      const got = await waitForGhost();
      if (!got || gen !== generation) return;
      continue;
    }
    const stopAfter = g.corner || g.alternatives.length > 0 || g.close || g.confidence < 0.45;
    if (!acceptGhost()) return;
    if (stopAfter) return;
  }
}

function waitForGhost(): Promise<boolean> {
  return new Promise((resolve) => {
    const t = setTimeout(() => {
      unsub();
      resolve(false);
    }, 600);
    const unsub = useStore.subscribe((s) => {
      if (s.ghost) {
        clearTimeout(t);
        unsub();
        resolve(true);
      }
    });
  });
}

export function setStep(mm: number) {
  const v = Math.round(Math.min(STEP_MAX_MM, Math.max(STEP_MIN_MM, mm)) * 2) / 2;
  savePrefs({ traceStep: v });
  useStore.getState().setTraceStep(v);
}

/** Switch the last placed point between corner and curve. */
export function toggleLastPoint() {
  const s = useStore.getState();
  const pen = s.pen;
  if (!pen) return;
  const flip = (n: PathNode): PathNode => [n[0], n[1], n[2] === "c" ? "s" : "c"];
  if (pen.kind === "satin" && pen.b.length === pen.a.length && pen.b.length) {
    s.setPen({ ...pen, a: [...pen.a.slice(0, -1), flip(pen.a[pen.a.length - 1])], b: [...pen.b.slice(0, -1), flip(pen.b[pen.b.length - 1])] });
  } else if (pen.a.length) {
    s.setPen({ ...pen, a: [...pen.a.slice(0, -1), flip(pen.a[pen.a.length - 1])] });
  }
}

export type { Ghost };
