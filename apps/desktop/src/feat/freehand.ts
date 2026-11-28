/**
 * Freehand drawing (P7-C1): a switch on the drawing tools, not a tool of its own. With it on and
 * Line, Satin or Fill chosen, press and drag to draw; when you let go the stroke becomes pen
 * points, so the shape can go on with clicks or another stroke. canvas/freehandTool.ts follows the
 * pointer; design/simplify.ts does the smoothing.
 *
 * cmd/draw.ts imports this module: nothing here may call actions.ts while it loads.
 */
import { create } from "zustand";
import { command, info, penFinish } from "../actions";
import type { Pt } from "../design/paths";
import { DEFAULT_SMOOTHING, fitStroke, MIN_STROKE_MM, strokeLength, strokeTolerance, trimOvershoot } from "../design/simplify";
import type { PathNode } from "../design/types";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore, type Tool } from "../store";

/** A Fill stroke let go this near where its outline began, in screen pixels, finishes it. */
export const CLOSE_PX = 12;

const clampSmoothing = (n: number) => Math.min(5, Math.max(1, Math.round(Number.isFinite(n) ? n : DEFAULT_SMOOTHING)));

export const useFreehand = create<{ on: boolean; smooth: number }>(() => ({
  on: false,
  smooth: clampSmoothing(loadPrefs().freehandSmooth ?? DEFAULT_SMOOTHING),
}));

/** Smoothing, 1 (keeps the most of your hand) to 5 (the fewest points). */
export function setSmoothing(n: number): void {
  const smooth = clampSmoothing(n);
  savePrefs({ freehandSmooth: smooth });
  useFreehand.setState({ smooth });
}

export const isDrawingTool = (t: Tool): boolean => t === "run" || t === "satin" || t === "fill";

/** Y: freehand on or off. With no drawing tool chosen, it picks Line and turns freehand on. */
export function toggleFreehand(): void {
  const drawing = isDrawingTool(useStore.getState().tool);
  const on = !drawing || !useFreehand.getState().on;
  useFreehand.setState({ on });
  const say = () => info(on ? "Freehand on: drag to draw, or click point by point. Y turns it off." : "Freehand off: click point by point.");
  // Said once the tool is picked (starting a new design clears the message bar).
  if (drawing) say();
  else void Promise.resolve(command("tool.run").run() as unknown).then(say);
}

const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
const dist = (a: Pt, b: Pt) => Math.hypot(a[0] - b[0], a[1] - b[1]);

/** The stroke from the pen point the press made. That point can sit a little off where the button
 *  went down (snapped to a guide, the grid or another shape), so the stroke's first few
 *  millimeters bend from it into the path the hand took. */
export function joinStart(start: Pt, stroke: readonly Pt[]): Pt[] {
  const [dx, dy] = [start[0] - stroke[0][0], start[1] - stroke[0][1]];
  const reach = Math.max(3, 3 * Math.hypot(dx, dy));
  let along = 0;
  return stroke.map((p, i) => {
    if (i === 0) return start;
    along += dist(stroke[i - 1], p);
    const w = Math.max(0, 1 - along / reach);
    return [p[0] + dx * w, p[1] + dy * w];
  });
}

/** Whether a fill stroke came back: let go within `radius` of where the outline began, having
 *  gone at least twice that far from it. */
function cameBack(stroke: readonly Pt[], origin: Pt, radius: number): boolean {
  return dist(stroke[stroke.length - 1], origin) <= radius && stroke.some((p) => dist(p, origin) > 2 * radius);
}

/** A finished stroke (as the pointer reported it, mm) goes into the pen, from the point the press
 *  put there. A Fill stroke that comes back to where the outline began closes and finishes the
 *  shape. `pxMm`: one screen pixel, mm. */
export async function addStroke(stroke: readonly Pt[], pxMm: number): Promise<void> {
  const pen = useStore.getState().pen;
  // One click: the press has already placed its point.
  if (!pen?.a.length || strokeLength(stroke) < MIN_STROKE_MM) return;
  const last = pen.a[pen.a.length - 1];
  const before = pen.a.slice(0, -1);
  let drawn = joinStart([last[0], last[1]], stroke);
  const origin: Pt = before.length ? [before[0][0], before[0][1]] : drawn[0];
  const closes = pen.kind === "fill" && !pen.carveFor && cameBack(drawn, origin, CLOSE_PX * pxMm);
  if (closes) drawn = trimOvershoot(drawn, origin, 2 * CLOSE_PX * pxMm);
  const fit = fitStroke(drawn, strokeTolerance(useFreehand.getState().smooth, pxMm), { before, startKind: last[2], closed: closes });
  const nodes = fit.nodes.map(([x, y, kind]) => [round2(x), round2(y), kind] as PathNode);
  // The first point is the press's own, as it was, unless the stroke turns sharply there.
  nodes[0] = nodes[0][2] === last[2] ? last : [last[0], last[1], nodes[0][2]];
  const lead =
    closes && before.length && fit.closingKind && fit.closingKind !== before[0][2]
      ? [[before[0][0], before[0][1], fit.closingKind] as PathNode, ...before.slice(1)]
      : before;
  useStore.getState().setPen({ ...pen, a: [...lead, ...nodes] });
  if (closes && lead.length + nodes.length >= 3) await penFinish();
}
