/** Adjusting single letters (text.letters): the dots on the letters, picking, dragging and
 *  nudging one, and what a color chosen in Order & colors does to a text's color runs.
 *
 *  actions.ts calls nudgeLetter, recolorRuns and pruneLetterEdits; the canvas hides a text's
 *  start and end dots, and redraws, when useLetterMode changes. Nothing here may call actions.ts
 *  while the module loads (the two import each other). */
import { create } from "zustand";
import { commit, currentLayout, engine, info, targetId } from "../actions";
import { registerCanvasTool, registerOverlay, type CanvasCtx } from "../canvas/hooks";
import { recolor } from "../design/layout";
import type { Design, Layout, LetterEdit, LetterPart, TextItem, TextRun, Thread, Transform } from "../design/types";
import { holdEscape } from "../escape";
import { selectCanvasDark, useStore } from "../store";

/** Single-letter mode: the text whose letters are being adjusted and the letter picked. */
export type LetterMode = { id: string | null; letter: number | null };
export const useLetterMode = create<LetterMode>(() => ({ id: null, letter: null }));

type Point = [number, number];
type Sources = { item: number; block: number }[];

const DOT_PX = 5; // a letter's dot (radius, screen pixels)
const REACH_PX = 9; // how near a dot a click picks its letter
const DRAG_PX = 3; // how far the pointer goes before a letter moves
const NUDGE_RUN_MS = 800; // arrow keys tapped this close together are one undo step
const MIN_SCALE = 0.5;
const MAX_SCALE = 2;
const INK = 0x121114;
const BONE = 0xeee9df;
const YELLOW = 0xc8ff2e;

// ---------------------------------------------------------------- the text and its letters

function textById(id: string): TextItem | null {
  const it = currentLayout()?.items.find((x) => x.id === id);
  return it?.kind === "text" ? it : null;
}

function selectedText(): TextItem | null {
  if (useStore.getState().extraIds.length) return null;
  const id = targetId();
  return id ? textById(id) : null;
}

export function canAdjustLetters(): boolean {
  const text = selectedText();
  return !!text && !text.locked && useStore.getState().engine !== null;
}

export const hasLetterEdits = (): boolean => Object.keys(selectedText()?.letter_edits ?? {}).length > 0;

/** A text's letter parts as the design shows them. */
function shownParts(id: string): LetterPart[] {
  return useStore.getState().design?.items?.find((it) => it.id === id)?.letters ?? [];
}

/** The part numbers of one letter (what its chosen start and end dots are kept by). */
const partsOf = (id: string, letter: number): number[] =>
  shownParts(id)
    .filter((p) => p.letter === letter)
    .map((p) => p.index);

// ---------------------------------------------------------------- single-letter mode

let releaseEsc: (() => void) | null = null;
let unwatch: (() => void) | null = null;

/** The mode lasts while its text, and nothing else, is selected with the Select tool. */
function stillOn(id: string): boolean {
  const s = useStore.getState();
  const it = s.history.present?.layout.items.find((x) => x.id === id);
  return it?.kind === "text" && !it.locked && s.selectedId === id && !s.extraIds.length && s.tool === "select" && !s.stitchEdit;
}

function enterLetterMode(id: string): void {
  leaveLetterMode();
  if (useStore.getState().tool !== "select") useStore.getState().setTool("select"); // (the selection stays)
  if (useStore.getState().selectedId !== id) useStore.getState().select(id);
  useLetterMode.setState({ id, letter: null });
  releaseEsc = holdEscape(leaveLetterMode);
  unwatch = useStore.subscribe(() => {
    if (!stillOn(id)) leaveLetterMode();
  });
  info("Click a letter's dot, then drag it or use the arrow keys. Press Esc when you're done.");
}

export function leaveLetterMode(): void {
  stopDrag();
  released = null;
  unwatch?.();
  unwatch = null;
  const release = releaseEsc;
  releaseEsc = null;
  release?.();
  if (useLetterMode.getState().id !== null) useLetterMode.setState({ id: null, letter: null });
}

export function toggleLetterMode(): void {
  const on = useLetterMode.getState().id;
  const text = selectedText();
  if (on !== null && (!text || text.id === on)) return leaveLetterMode();
  if (!text || !canAdjustLetters()) return info("Select some lettering first (not pinned).");
  enterLetterMode(text.id);
}

export const pickLetter = (letter: number | null): void => useLetterMode.setState({ letter });

// ---------------------------------------------------------------- changing letters

const round = (v: number, places: number) => Math.round(v * 10 ** places) / 10 ** places + 0; // (+ 0: never -0)
const numberOr = (v: number | undefined, otherwise: number) => (typeof v === "number" && Number.isFinite(v) ? v : otherwise);

/** A letter's changes kept within their limits, without the ones that change nothing. */
function tidyEdit(e: LetterEdit): LetterEdit {
  const out: LetterEdit = {};
  const dx = round(numberOr(e.dx_mm, 0), 3);
  const dy = round(numberOr(e.dy_mm, 0), 3);
  if (dx) out.dx_mm = dx;
  if (dy) out.dy_mm = dy;
  let turn = numberOr(e.rotate, 0) % 360;
  if (turn > 180) turn -= 360;
  if (turn < -180) turn += 360;
  if (round(turn, 2)) out.rotate = round(turn, 2);
  const scale = round(Math.min(MAX_SCALE, Math.max(MIN_SCALE, numberOr(e.scale, 1))), 4);
  if (scale !== 1) out.scale = scale;
  if (typeof e.angle_deg === "number" && Number.isFinite(e.angle_deg)) out.angle_deg = round(((e.angle_deg % 180) + 180) % 180, 1);
  if (e.thread) out.thread = e.thread;
  return out;
}

/** A text with these single-letter changes (none: without the setting at all). */
function withEdits(item: TextItem, edits: Record<string, LetterEdit>): TextItem {
  const { letter_edits: _old, ...rest } = item;
  return Object.keys(edits).length ? { ...rest, letter_edits: edits } : rest;
}

/** `item` with the changes to `letter` set to `edit` (null: none). Its chosen start and end dots
 *  (`parts` are its parts' numbers) move along with a move; a turn or resize leaves them to LUDD
 *  again, as they'd no longer be where you put them on the letter. The same item if nothing
 *  changes. */
function withLetterEdit(item: TextItem, letter: number, edit: LetterEdit | null, parts: number[]): TextItem {
  const old = tidyEdit(item.letter_edits?.[letter] ?? {});
  const next = tidyEdit(edit ?? {});
  if (JSON.stringify(old) === JSON.stringify(next)) return item;
  const edits = { ...(item.letter_edits ?? {}) };
  if (Object.keys(next).length) edits[letter] = next;
  else delete edits[letter];
  const out = withEdits(item, edits);
  if (!parts.some((p) => item.letters?.[p])) return out;
  const dx = (next.dx_mm ?? 0) - (old.dx_mm ?? 0);
  const dy = (next.dy_mm ?? 0) - (old.dy_mm ?? 0);
  const movedOnly = (next.rotate ?? 0) === (old.rotate ?? 0) && (next.scale ?? 1) === (old.scale ?? 1);
  const letters = { ...item.letters };
  for (const p of parts) {
    const dots = letters[p];
    if (!dots) continue;
    if (!movedOnly) delete letters[p];
    else
      letters[p] = Object.fromEntries(
        Object.entries(dots).map(([which, at]) => [which, [round(at[0] + dx, 3), round(at[1] + dy, 3)]]),
      );
  }
  return { ...out, letters };
}

const replaceText = (layout: Layout, next: TextItem): Layout => ({ ...layout, items: layout.items.map((x) => (x.id === next.id ? next : x)) });

/** The last arrow-key move, so the next one within a moment joins its undo step. */
let nudges: { key: string; layout: Layout; until: number } | null = null;

/** Change one letter: one undo step, or part of a run of arrow-key moves (`run`). */
function applyEdit(id: string, letter: number, edit: LetterEdit | null, run?: string): Promise<boolean> {
  const layout = currentLayout();
  const item = textById(id);
  if (!layout || !item) return Promise.resolve(false);
  const next = withLetterEdit(item, letter, edit, partsOf(id, letter));
  if (next === item) return Promise.resolve(true);
  const out = replaceText(layout, next);
  let merge = false;
  if (run) {
    const now = Date.now();
    merge = !!nudges && nudges.key === run && now < nudges.until && nudges.layout === layout;
    nudges = { key: run, layout: out, until: now + NUDGE_RUN_MS };
  }
  return commit(out, merge);
}

export function setLetterEdit(id: string, letter: number, patch: Partial<LetterEdit>): Promise<boolean> {
  return applyEdit(id, letter, { ...textById(id)?.letter_edits?.[letter], ...patch });
}

/** "Put this letter back". */
export const resetLetter = (id: string, letter: number): Promise<boolean> => applyEdit(id, letter, null);

/** "Put the letters back": every letter of the selected text. */
export function resetLetters(): void {
  const layout = currentLayout();
  const item = selectedText();
  if (!layout || !item?.letter_edits) return;
  let next = item;
  for (const key of Object.keys(item.letter_edits)) next = withLetterEdit(next, Number(key), null, partsOf(item.id, Number(key)));
  void commit(replaceText(layout, withEdits(next, {})));
}

const frameOf = (t: Transform) => [t.rotate, t.scale_x, t.scale_y, t.flip_x, t.flip_y].join();

/** Move a letter by (dx, dy) mm as it shows on the design, turned into the text's own frame. */
async function moveLetter(id: string, letter: number, dx: number, dy: number, run?: string): Promise<void> {
  const item = textById(id);
  if (!item) return;
  try {
    const t = item.transform;
    const [lx, ly] = await engine().call<Point>("text.letter_frame", { item, at: [t.x + dx, t.y + dy] });
    const now = textById(id);
    // Turned, resized or mirrored meanwhile: the move no longer fits it.
    if (!now || frameOf(now.transform) !== frameOf(t)) return;
    const edit = now.letter_edits?.[letter] ?? {};
    await applyEdit(id, letter, { ...edit, dx_mm: (edit.dx_mm ?? 0) + lx, dy_mm: (edit.dy_mm ?? 0) + ly }, run);
  } catch (err) {
    info(err instanceof Error ? err.message : String(err));
  }
}

/** An arrow key while a letter is picked: true if the letter took it. */
export function nudgeLetter(dx: number, dy: number): boolean {
  const { id, letter } = useLetterMode.getState();
  if (id === null || letter === null || !stillOn(id) || !partsOf(id, letter).length) return false;
  void moveLetter(id, letter, dx, dy, `${id}:${letter}`);
  return true;
}

// ---------------------------------------------------------------- the dots on the design

type Dot = { letter: number; at: Point; rings: Point[][] };

/** Each letter's dot (the middle of the box round its parts) and outlines, as the design shows
 *  them, first letter first. */
function dotsOf(parts: LetterPart[]): Dot[] {
  const rings = new Map<number, Point[][]>();
  for (const p of parts) if (p.ring.length) rings.set(p.letter, [...(rings.get(p.letter) ?? []), p.ring]);
  return [...rings.entries()]
    .sort(([a], [b]) => a - b)
    .map(([letter, mine]) => {
      const xs = mine.flatMap((r) => r.map((q) => q[0]));
      const ys = mine.flatMap((r) => r.map((q) => q[1]));
      return { letter, at: [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2], rings: mine };
    });
}

/** Even-odd: is `p` inside the closed outline `ring`? */
function inside([x, y]: Point, ring: Point[]): boolean {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[i];
    const [bx, by] = ring[j];
    if (ay > y !== by > y && x < ((bx - ax) * (y - ay)) / (by - ay) + ax) hit = !hit;
  }
  return hit;
}

/** The letter at `p`: the one whose dot is within reach, else one `p` is inside. Of several, the
 *  nearest dot wins (to 0.001 mm), then the earlier letter. */
function letterAt(dots: Dot[], p: Point, px: number): number | null {
  const away = (d: Dot) => Math.round(Math.hypot(d.at[0] - p[0], d.at[1] - p[1]) * 1000);
  const nearest = (list: Dot[]) => list.sort((a, b) => away(a) - away(b) || a.letter - b.letter)[0];
  const hit = nearest(dots.filter((d) => away(d) <= REACH_PX * px * 1000)) ?? nearest(dots.filter((d) => d.rings.some((r) => inside(p, r))));
  return hit ? hit.letter : null;
}

type LetterDrag = { pointerId: number; id: string; letter: number; from: Point; to: Point; moved: boolean; ctx: CanvasCtx; stop: () => void };
let drag: LetterDrag | null = null;
/** A letter just let go, drawn where it was let go until the design shows it there. */
let released: { design: Design | null; id: string; letter: number; by: Point } | null = null;

function stopDrag(): void {
  const d = drag;
  drag = null;
  d?.stop();
}

/** Esc, a second finger or the window losing the pointer: the letter goes back. */
function cancelDrag(): void {
  const ctx = drag?.ctx;
  stopDrag();
  ctx?.redraw();
}

function startDrag(id: string, letter: number, p: Point, e: PointerEvent, ctx: CanvasCtx): void {
  try {
    (e.target as Element | null)?.setPointerCapture?.(e.pointerId);
  } catch {
    // A pointer that's already gone: the window still hears it.
  }
  const release = holdEscape(cancelDrag);
  const lost = (ev: Event) => {
    if (!("pointerId" in ev) || (ev as PointerEvent).pointerId === e.pointerId) cancelDrag();
  };
  const win = typeof window === "undefined" ? null : window;
  win?.addEventListener("pointercancel", lost);
  win?.addEventListener("blur", lost);
  const stop = () => {
    release();
    win?.removeEventListener("pointercancel", lost);
    win?.removeEventListener("blur", lost);
  };
  drag = { pointerId: e.pointerId, id, letter, from: p, to: p, moved: false, ctx, stop };
}

const past = (a: Point, b: Point, px: number) => Math.hypot(b[0] - a[0], b[1] - a[1]) >= DRAG_PX * px;

registerCanvasTool({
  id: "letters",
  active: () => {
    const { id } = useLetterMode.getState();
    const s = useStore.getState();
    return id !== null && stillOn(id) && !s.knife && !s.pen && !s.measure && !s.ruler && !s.angleFor;
  },
  down(p, e, ctx) {
    if (drag) {
      cancelDrag(); // a second finger: the letter goes back, and this one does nothing
      return true;
    }
    const id = useLetterMode.getState().id!;
    const letter = e.button === 0 ? letterAt(dotsOf(shownParts(id)), p, ctx.pxMm()) : null;
    if (letter === null) return false; // the canvas's own clicks (pan, pick something else)
    startDrag(id, letter, p, e, ctx);
    pickLetter(letter);
    ctx.redraw();
    return true;
  },
  move(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    drag.moved ||= past(drag.from, p, ctx.pxMm());
    if (drag.moved) {
      drag.to = p;
      ctx.redraw();
    }
    return true;
  },
  up(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    const d = drag;
    stopDrag();
    if (d.moved || past(d.from, p, ctx.pxMm())) {
      const shown = { design: useStore.getState().design, id: d.id, letter: d.letter, by: [p[0] - d.from[0], p[1] - d.from[1]] as Point };
      released = shown;
      void moveLetter(d.id, d.letter, ...shown.by).finally(() => {
        if (released === shown) released = null;
        ctx.redraw();
      });
    }
    ctx.redraw();
    return true;
  },
});

/** How far a letter being dragged (or just let go) is drawn from where the design has it. */
function offsetOf(id: string, letter: number): Point {
  if (drag?.moved && drag.id === id && drag.letter === letter) return [drag.to[0] - drag.from[0], drag.to[1] - drag.from[1]];
  const r = released;
  return r && r.id === id && r.letter === letter && r.design === useStore.getState().design ? r.by : [0, 0];
}

registerOverlay({
  id: "letters",
  draw(g, px) {
    const { id, letter } = useLetterMode.getState();
    if (id === null || !stillOn(id)) return;
    const line = selectCanvasDark(useStore.getState()) ? BONE : INK;
    for (const dot of dotsOf(shownParts(id))) {
      const [ox, oy] = offsetOf(id, dot.letter);
      const picked = dot.letter === letter;
      if (picked) {
        // The picked letter's outline lights up.
        const trace = () => {
          for (const [first, ...rest] of dot.rings) {
            g.moveTo(first[0] + ox, first[1] + oy);
            for (const q of rest) g.lineTo(q[0] + ox, q[1] + oy);
            g.closePath();
          }
        };
        trace();
        g.stroke({ width: 4 * px, color: YELLOW, alpha: 0.9, join: "round" });
        trace();
        g.stroke({ width: 1.25 * px, color: line });
      }
      g.circle(dot.at[0] + ox, dot.at[1] + oy, DOT_PX * px)
        .fill(picked ? YELLOW : 0xffffff)
        .stroke({ width: 1.5 * px, color: INK });
    }
  },
});

// ---------------------------------------------------------------- colors and words

function recolorRun(layout: Layout, at: number, run: TextRun, thread: Thread | null): Layout {
  const text = layout.items[at] as TextItem;
  // A run holding every letter of the text's color (or of a stitched font's color) is that color.
  if (run.what === "letters" && run.slots.length) return recolor(layout, run.slots.map((block) => ({ item: at, block })), thread);
  let next = text;
  if (run.what === "letters") {
    const edits = { ...(text.letter_edits ?? {}) };
    for (const letter of run.letters) {
      const { thread: _old, ...rest } = edits[letter] ?? {};
      const edit: LetterEdit = thread ? { ...rest, thread } : rest;
      if (Object.keys(edit).length) edits[letter] = edit;
      else delete edits[letter];
    }
    next = withEdits(text, edits);
  } else if (thread) {
    const key = run.what === "frame" ? "ornament" : run.what;
    if (text[key]) next = { ...text, [key]: { ...text[key], thread } } as TextItem;
  }
  return next === text ? layout : replaceText(layout, next);
}

/** The layout with `thread` chosen in Order & colors (null: back to as it was) for the color
 *  blocks `sources`. `design` is the design as drawn, whose items say what each run holds. */
export function recolorRuns(layout: Layout, sources: Sources, thread: Thread | null, design: Design | null): Layout {
  let next = layout;
  const others: Sources = [];
  for (const source of sources) {
    const it = next.items[source.item];
    const shown = design?.items?.[source.item];
    const run = it?.kind === "text" && shown?.id === it.id ? shown.runs?.find((r) => r.run === source.block) : undefined;
    if (run) next = recolorRun(next, source.item, run, thread);
    else others.push(source);
  }
  return others.length ? recolor(next, others, thread) : next;
}

/** One letter for each character that could draw something (a monogram has up to three). */
function mostLetters(item: TextItem): number {
  const drawn = Array.from(item.text.normalize("NFC")).filter((c) => !/[\s\p{Cf}]/u.test(c)).length;
  return item.monogram ? Math.min(drawn, 3) : drawn;
}

/** A text whose words changed, without the changes to letters it no longer has. */
export function pruneLetterEdits(item: TextItem): TextItem {
  const edits = item.letter_edits;
  if (!edits) return item;
  const most = mostLetters(item);
  const kept = Object.entries(edits).filter(([key]) => Number(key) < most);
  return kept.length === Object.keys(edits).length ? item : withEdits(item, Object.fromEntries(kept));
}
