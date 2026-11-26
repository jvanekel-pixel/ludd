/**
 * Turning fills: a fill with two or more angle lines, which its rows turn to follow (the engine:
 * digitize/fills/turning.py). Shift+I draws another line; each shows its purple dots, which can be
 * dragged; right-click a line to remove it. Down to one line, the fill goes back to one angle.
 * The edits are pure functions (for tests); the canvas drawing and dragging register below.
 */
import { currentLayout, editObject, info } from "../actions";
import { registerCanvasTool, registerOverlay, type CanvasCtx } from "../canvas/hooks";
import { angleOf, centroid, chord, fillDirection, fillRing } from "../design/direction";
import { hasDirectionDots } from "../design/fillPatterns";
import type { ObjectItem } from "../design/types";
import { holdEscape } from "../escape";
import { endOtherModes } from "../features";
import { useStore } from "../store";

export type Pt = [number, number];
export type AngleLine = [Pt, Pt];

/** Lines shorter than this give no direction (the engine leaves them out too). */
export const MIN_LINE_MM = 0.5;
const DIRECTION_COLOR = 0x8b5cf6;
const DOT_PX = 5;
const GRAB_PX = 8; // a dot this near the pointer (screen pixels) is picked up
const LINE_PX = 6; // a right-click this near a line removes it

const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
const r2 = (p: Pt): Pt => [round2(p[0]), round2(p[1])];
const long = (l: AngleLine) => Math.hypot(l[1][0] - l[0][0], l[1][1] - l[0][1]) >= MIN_LINE_MM;

/** A fill's angle lines (none unless it has two or more: one line is just its angle). */
export function angleLines(o: ObjectItem | undefined | null): AngleLine[] {
  if (!o || o.kind !== "fill") return [];
  const lines = (o.params as { angle_lines?: AngleLine[] }).angle_lines;
  return Array.isArray(lines) && lines.length >= 2 ? lines : [];
}

/** Whether a fill's rows can turn to follow several lines: Tatami's can. */
export const canTurn = (o: ObjectItem): boolean =>
  o.kind === "fill" && ((o.params as { pattern?: string }).pattern ?? "tatami") === "tatami";

/** The direction a fill sews in now, as a line: its purple dots, or a line through its middle
 *  at its angle. */
export function currentLine(o: ObjectItem): AngleLine {
  const stored = (o.params as { angle_lines?: AngleLine[] }).angle_lines;
  if (Array.isArray(stored) && stored.length === 1) return stored[0];
  const shown = fillDirection(o);
  if (shown) return shown;
  const angle = (o.params as { angle_deg?: number }).angle_deg ?? 45;
  const ring = fillRing(o);
  const c: Pt = ring.length ? centroid(ring) : [0, 0];
  const across = ring.length >= 3 ? chord(ring, c, angle) : null;
  if (across) return across;
  const a = (angle * Math.PI) / 180;
  return [
    [c[0] - 5 * Math.cos(a), c[1] - 5 * Math.sin(a)],
    [c[0] + 5 * Math.cos(a), c[1] + 5 * Math.sin(a)],
  ];
}

function withLines(o: ObjectItem, lines: AngleLine[]): ObjectItem {
  const params = { ...(o.params as Record<string, unknown>) };
  if (lines.length >= 2) {
    params.angle_lines = lines.map(([a, b]) => [r2(a), r2(b)]);
  } else {
    // Back to one angle: the remaining line's.
    delete params.angle_lines;
    if (lines.length === 1) {
      params.angle_deg = angleOf(lines[0][0], lines[0][1]);
      params.angle_line = [r2(lines[0][0]), r2(lines[0][1])];
    }
  }
  return { ...o, params } as ObjectItem;
}

/** Another line (Shift+I). The first extra line on a fill with one angle makes its current
 *  direction line 1. */
export function addLine(o: ObjectItem, line: AngleLine): ObjectItem {
  const lines = angleLines(o);
  return withLines(o, [...(lines.length ? lines : [currentLine(o)]), line]);
}

/** I on a fill with several lines: the new line takes the first's place. */
export function replaceFirstLine(o: ObjectItem, line: AngleLine): ObjectItem {
  const lines = angleLines(o);
  return lines.length ? withLines(o, [line, ...lines.slice(1)]) : o;
}

/** One end (0 or 1) of line `i` dragged to `p`. */
export function moveLineEnd(o: ObjectItem, i: number, which: 0 | 1, p: Pt): ObjectItem {
  const lines = angleLines(o);
  if (!lines[i]) return o;
  const moved: AngleLine = which === 0 ? [p, lines[i][1]] : [lines[i][0], p];
  return withLines(o, lines.map((l, k) => (k === i ? moved : l)));
}

/** Line `i` taken away; down to one, the fill goes back to that line's angle. */
export function removeLine(o: ObjectItem, i: number): ObjectItem {
  const lines = angleLines(o);
  return lines[i] ? withLines(o, lines.filter((_, k) => k !== i)) : o;
}

/** "Back to one angle": the first line's angle, and no more lines. */
export function backToOneAngle(o: ObjectItem): ObjectItem {
  const lines = angleLines(o);
  return lines.length ? withLines(o, [lines[0]]) : o;
}

// ---------------------------------------------------------------- commands

const objectById = (id: string): ObjectItem | undefined => {
  const it = currentLayout()?.items.find((x) => x.id === id);
  return it && it.kind === "fill" ? (it as ObjectItem) : undefined;
};

/** Shift+I: draw another angle line on the selected fill. */
export function startAddAngle(): void {
  const s = useStore.getState();
  const o = s.selectedId ? objectById(s.selectedId) : undefined;
  if (!o) return info("Select a fill first, then press Shift+I and draw another line for the stitches to follow.");
  if (!canTurn(o)) return info("Only Tatami fills can turn to follow several lines. Choose Tatami under Pattern first.");
  endOtherModes("angle");
  s.setAngleFor({ id: o.id, points: [], add: true });
  info("Draw another line: the rows turn to follow each line where it lies.");
}

/** An angle line just drawn (I, or Shift+I when `add`): true if it was taken as one of a turning
 *  fill's lines; false leaves it to set the fill's single angle, as always. */
export function finishAngleLine(id: string, a: [number, number], b: [number, number], add: boolean): boolean {
  const o = objectById(id);
  if (!o) return false;
  if (!add && angleLines(o).length < 2) return false;
  if (!long([a, b])) {
    info("Draw a longer line: its direction is the way the stitches run.");
    return true;
  }
  void editObject(id, (x) => (add ? addLine(x, [a, b]) : replaceFirstLine(x, [a, b])));
  return true;
}

/** Remove line `i` of a fill (right-click on it). */
export function removeAngleLine(id: string, i: number): void {
  void editObject(id, (x) => removeLine(x, i));
}

/** "Back to one angle" (the Angle box). */
export function oneAngleAgain(id: string): void {
  void editObject(id, backToOneAngle);
}

// ---------------------------------------------------------------- the canvas

/** The selected fill whose lines show, when nothing else has the pointer. */
function shownFill(): { o: ObjectItem; lines: AngleLine[] } | null {
  const s = useStore.getState();
  if (!s.selectedId || s.extraIds.length || s.tool !== "select" || s.pen || s.knife || s.measure || s.ruler || s.angleFor) return null;
  const o = objectById(s.selectedId);
  if (!o || o.locked || !hasDirectionDots((o.params as { pattern?: string }).pattern)) return null;
  const lines = angleLines(o);
  return lines.length ? { o, lines } : null;
}

type Drag = { id: string; line: number; which: 0 | 1; pointerId: number; at: Pt; stop(): void; ctx: CanvasCtx };
let drag: Drag | null = null;

function cancelDrag(): void {
  const d = drag;
  drag = null;
  d?.stop();
  d?.ctx.redraw();
}

/** The dot (line and end) within GRAB_PX of `p`, nearest first. */
export function dotAt(lines: AngleLine[], p: Pt, px: number): { line: number; which: 0 | 1 } | null {
  let best: { line: number; which: 0 | 1; d: number } | null = null;
  lines.forEach((l, line) =>
    ([0, 1] as const).forEach((which) => {
      const d = Math.hypot(l[which][0] - p[0], l[which][1] - p[1]);
      if (d <= GRAB_PX * px && (!best || d < best.d)) best = { line, which, d };
    }),
  );
  const found = best as { line: number; which: 0 | 1 } | null;
  return found ? { line: found.line, which: found.which } : null;
}

/** The line within LINE_PX of `p`, nearest first. */
export function lineAt(lines: AngleLine[], p: Pt, px: number): number | null {
  let best: number | null = null;
  let bestD = LINE_PX * px;
  lines.forEach(([a, b], i) => {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const len2 = dx * dx + dy * dy;
    const t = len2 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2)) : 0;
    const d = Math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]);
    if (d <= bestD) {
      bestD = d;
      best = i;
    }
  });
  return best;
}

registerCanvasTool({
  id: "angle-lines",
  active: () => drag !== null || shownFill() !== null,
  down(p, e, ctx) {
    if (drag) {
      cancelDrag(); // a second finger: the dot goes back
      return true;
    }
    const shown = shownFill();
    const hit = shown && e.button === 0 ? dotAt(shown.lines, p, ctx.pxMm()) : null;
    if (!shown || !hit) return false; // the canvas's own clicks
    try {
      (e.target as Element | null)?.setPointerCapture?.(e.pointerId);
    } catch {
      // A pointer that's already gone.
    }
    const release = holdEscape(cancelDrag);
    drag = { id: shown.o.id, line: hit.line, which: hit.which, pointerId: e.pointerId, at: shown.lines[hit.line][hit.which], stop: release, ctx };
    ctx.redraw();
    return true;
  },
  move(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    drag.at = p;
    ctx.redraw();
    return true;
  },
  up(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    const d = drag;
    drag = null;
    d.stop();
    const o = objectById(d.id);
    const line = o ? angleLines(o)[d.line] : undefined;
    if (o && line) {
      const moved: AngleLine = d.which === 0 ? [p, line[1]] : [line[0], p];
      if (long(moved)) void editObject(d.id, (x) => moveLineEnd(x, d.line, d.which, p));
      else info("Drag the dots further apart: each line's direction is the way the stitches run there.");
    }
    ctx.redraw();
    return true;
  },
  menu(p, _e, ctx) {
    const shown = shownFill();
    const i = shown ? lineAt(shown.lines, p, ctx.pxMm()) : null;
    if (!shown || i === null) return false;
    removeAngleLine(shown.o.id, i);
    return true;
  },
});

registerOverlay({
  id: "angle-lines",
  draw(g, px) {
    const shown = shownFill();
    if (!shown) return;
    shown.lines.forEach((l, i) => {
      const [a, b] = l.map((q, which) => (drag && drag.id === shown.o.id && drag.line === i && drag.which === which ? drag.at : q));
      g.moveTo(a[0], a[1]).lineTo(b[0], b[1]).stroke({ width: 2 * px, color: DIRECTION_COLOR, alpha: 0.95 });
      for (const q of [a, b]) g.circle(q[0], q[1], DOT_PX * px).fill(DIRECTION_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
    });
  },
});
