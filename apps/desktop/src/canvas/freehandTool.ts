/**
 * The canvas side of freehand drawing (feat/freehand.ts): while it's on with a drawing tool, a
 * press and drag is followed as a stroke. The press itself is left to the canvas, so it places its
 * point just as a click does (snapped to guides, the grid or other shapes); only once the pointer
 * moves is the rest followed here. Let go, and the stroke becomes pen points. Esc, a second finger
 * or pen, or the window losing the pointer drops the stroke and leaves the shape as it was.
 */
import type { Pt } from "../design/paths";
import { holdEscape } from "../escape";
import { addStroke, CLOSE_PX, isDrawingTool, useFreehand } from "../feat/freehand";
import { useStore, type Pen } from "../store";
import { registerCanvasTool, registerOverlay, type CanvasCtx } from "./hooks";

// The canvas's own measures, px (components/StitchCanvas.tsx): its ruler strip, how far the
// pointer moves before a press becomes a drag, how near an edge it scrolls by itself while you
// draw, and how near a click snaps.
const RULER_PX = 18;
const DRAG_PX = 3;
const EDGE_PX = 28;
const SNAP_PX = 7;
/** The pen takes a click this near its last point as the same point (mm). */
const SAME_POINT_MM = 0.3;

type Drawing = {
  pointerId: number;
  screen: [number, number];
  press: Pt;
  /** The pen before the press. */
  before: Pen | null;
  /** The pen once the press had placed its point (undefined until looked at). */
  pen?: Pen;
  samples: Pt[];
  moved: boolean;
  nearEdge: boolean;
  ctx: CanvasCtx;
  release: () => void;
};

let drawing: Drawing | null = null;

/** The stroke being drawn, if one is. */
export const strokeBeingDrawn = (): readonly Pt[] | null => (drawing?.moved ? drawing.samples : null);

function canDraw(): boolean {
  const s = useStore.getState();
  return useFreehand.getState().on && isDrawingTool(s.tool) && !s.knife && !s.stitchEdit && !s.ruler && !s.angleFor && !s.measure;
}

/** The design area as the event saw it, if it can tell. */
function area(e: Event): DOMRect | null {
  const el = e.currentTarget as Partial<Element> | null;
  const r = el?.getBoundingClientRect?.();
  return r && r.width > 0 ? r : null;
}

/** On a ruler strip the canvas pulls out a guide instead of drawing. */
function onRuler(e: PointerEvent): boolean {
  const r = area(e);
  return !!r && useStore.getState().showRulers && (e.clientX - r.left < RULER_PX || e.clientY - r.top < RULER_PX);
}

function nearEdge(e: PointerEvent): boolean {
  const r = area(e);
  if (!r) return false;
  return Math.min(e.clientX - r.left, e.clientY - r.top, r.right - e.clientX, r.bottom - e.clientY) < EDGE_PX;
}

/** Whether the pen now has the point this press placed: one more than before, or (a press right
 *  on the pen's last point) the same pen. */
function placedBy(d: Drawing, now: Pen | null): now is Pen {
  if (!now?.a.length || now.kind !== useStore.getState().tool) return false;
  if (now !== d.before) return now.a.length === (d.before?.a.length ?? 0) + 1;
  const last = now.a[now.a.length - 1];
  return Math.hypot(last[0] - d.press[0], last[1] - d.press[1]) <= SNAP_PX * d.ctx.pxMm() + SAME_POINT_MM;
}

/** Whether the pen is still the one the press made (anything else, like Enter, ends the stroke). */
function stillOurs(d: Drawing): boolean {
  const now = useStore.getState().pen;
  if (d.pen) return now === d.pen;
  if (!placedBy(d, now)) return false;
  d.pen = now;
  return true;
}

/** The stroke is over, however it ended. */
function end(): void {
  const d = drawing;
  drawing = null;
  d?.release();
}

/** Esc and the like: the shape goes back to how it was before the press. */
function drop(): void {
  const d = drawing;
  if (!d) return;
  const ours = stillOurs(d);
  end();
  if (ours && d.pen !== d.before) useStore.getState().setPen(d.before);
  d.ctx.redraw();
}

function start(p: Pt, e: PointerEvent, ctx: CanvasCtx): void {
  const lost = (ev: PointerEvent) => ev.pointerId === drawing?.pointerId && drop();
  const blurred = () => drop();
  const releaseEsc = holdEscape(drop);
  window.addEventListener("pointercancel", lost);
  window.addEventListener("blur", blurred);
  drawing = {
    pointerId: e.pointerId, screen: [e.clientX, e.clientY], press: p, before: useStore.getState().pen, samples: [p], moved: false, nearEdge: false, ctx,
    release: () => {
      releaseEsc();
      window.removeEventListener("pointercancel", lost);
      window.removeEventListener("blur", blurred);
    },
  };
  try {
    // Letting go outside the design area still ends the stroke here.
    (e.currentTarget as Element | null)?.setPointerCapture?.(e.pointerId);
  } catch {
    // A pointer that's already gone: the window still hears it.
  }
}

registerCanvasTool({
  id: "freehand",
  active: () => drawing !== null || canDraw(),
  down(p, e, ctx) {
    if (drawing) {
      // A second finger or pen: the stroke goes back, and the new one does nothing (as the canvas
      // does with its own drags). The same pointer again: its release was missed.
      if (e.pointerId !== drawing.pointerId) {
        drop();
        return true;
      }
      end();
    }
    if (e.button === 0 && canDraw() && !onRuler(e)) start(p, e, ctx);
    return false; // the canvas places the press's point, as for any click
  },
  move(p, e, ctx) {
    const d = drawing;
    if (!d) return false;
    if (e.pointerId !== d.pointerId) return true;
    if (!stillOurs(d)) {
      end();
      return false;
    }
    // A pen tablet or a fast mouse reports points between frames: every one counts.
    const all = typeof e.getCoalescedEvents === "function" ? e.getCoalescedEvents() : [];
    for (const one of all.length ? all : [e]) d.samples.push(all.length ? ctx.toMm(one) : p);
    const first = !d.moved && Math.hypot(e.clientX - d.screen[0], e.clientY - d.screen[1]) >= DRAG_PX;
    if (first) d.moved = true;
    if (!d.moved) return false;
    if (nearEdge(e)) d.nearEdge = true;
    // The canvas follows along at first (its stretch to the pointer then stays tiny, by the
    // start) and near an edge (it scrolls by itself there); otherwise only the stroke shows.
    if (first || d.nearEdge) return false;
    ctx.redraw();
    return true;
  },
  up(p, e, ctx) {
    const d = drawing;
    if (!d) return false;
    if (e.pointerId !== d.pointerId) return true;
    const ours = stillOurs(d);
    end();
    if (ours && d.moved) {
      d.samples.push(p);
      void addStroke(d.samples, ctx.pxMm());
    }
    return false;
  },
});

registerOverlay({
  id: "freehand-stroke",
  draw(g, px) {
    const pen = drawing?.pen;
    if (!drawing?.moved || !pen) return;
    const s = useStore.getState();
    const from = pen.a[pen.a.length - 1];
    const points: Pt[] = [[from[0], from[1]], ...drawing.samples.slice(1)];
    const color = parseInt(s.drawThread.color.slice(1), 16);
    const path = () => {
      g.moveTo(points[0][0], points[0][1]);
      for (const [x, y] of points.slice(1)) g.lineTo(x, y);
    };
    if (pen.kind === "satin") {
      path();
      g.stroke({ width: s.satinWidth, color, alpha: 0.3, join: "round", cap: "round" });
    }
    path();
    g.stroke({ width: 1.5 * px, color, alpha: 1, join: "round", cap: "round" });
    if (pen.kind !== "fill" || pen.carveFor) return;
    // A fill let go in this ring closes.
    const [ox, oy] = pen.a[0];
    const end = points[points.length - 1];
    const close = Math.hypot(end[0] - ox, end[1] - oy) <= CLOSE_PX * px;
    g.circle(ox, oy, CLOSE_PX * px).stroke({ width: (close ? 2 : 1) * px, color, alpha: close ? 1 : 0.5 });
  },
});
