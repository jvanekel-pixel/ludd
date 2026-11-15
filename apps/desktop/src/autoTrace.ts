/**
 * Auto-trace: with the Auto-trace tool, click inside a shape on a picture (or on one of its
 * lines). The engine guesses its outline; the guess is shown as a preview with its points, Tab
 * shows the next guess, and nothing is added until you accept it. Accepted shapes are ordinary
 * fills and satins: drag their points to fix what the guess got wrong.
 */

import { addTraced, info } from "./actions";
import { holdEscape } from "./escape";
import type { PathNode } from "./design/types";
import { loadPrefs, savePrefs } from "./prefs";
import { useStore, type TraceGuess } from "./store";
import { pictureUnder } from "./traceAssist";

export const SPACING_MIN_MM = 1;
export const SPACING_MAX_MM = 10;

let release: (() => void) | null = null;
let seq = 0;

// Esc lets go of a guess (one press), however the guess went away.
useStore.subscribe((s, prev) => {
  if (s.autoTrace && !prev.autoTrace) release ??= holdEscape(dismissAutoTrace);
  if (!s.autoTrace && prev.autoTrace) {
    release?.();
    release = null;
  }
});

export type ClickMode = "new" | "add" | "subtract";

/**
 * A click with Auto-trace: a new guess, or (Shift+click) add that area to the guess on screen,
 * or (Alt+click) cut that area out of it.
 */
export async function autoTraceAt(x: number, y: number, mode: ClickMode = "new") {
  const s = useStore.getState();
  const doc = s.history.present;
  if (!s.engine || !doc) return;
  const img = pictureUnder(doc.images, x, y);
  if (!img) {
    info("Click on a picture: Auto-trace finds the shapes and lines in a picture you've added (Ctrl+I).");
    return;
  }
  const cur = s.autoTrace;
  if (mode !== "new" && (!cur || cur.imageId !== img.id)) mode = "new";
  const pt: [number, number] = [x, y];
  const next =
    mode === "new" || !cur
      ? { imageId: img.id, at: pt, add: [], subtract: [], guesses: [], index: 0, busy: true }
      : mode === "add"
        ? { ...cur, add: [...cur.add, pt], busy: true }
        : { ...cur, subtract: [...cur.subtract, pt], busy: true };
  s.setAutoTrace(next);
  await ask();
}

/** Ask the engine for guesses for what's on screen (after a click, or a new spacing or spread). */
async function ask() {
  const s = useStore.getState();
  const a = s.autoTrace;
  const img = s.history.present?.images.find((im) => im.id === a?.imageId);
  if (!a || !img || !s.engine) return;
  const my = ++seq;
  if (!a.busy) s.setAutoTrace({ ...a, busy: true });
  const shown = a.guesses[a.index]?.id;
  try {
    const r = await s.engine.call<{ candidates: TraceGuess[]; ai_error?: string }>(
      "trace.region",
      {
        path: img.path,
        placement: { x: img.x, y: img.y, width_mm: img.width_mm, height_mm: img.height_mm, rotate: img.rotate },
        at: a.at,
        add: a.add,
        subtract: a.subtract,
        spacing_mm: s.autoSpacing,
        spread: s.autoSpread,
        use_ai: s.traceAI && !!s.traceModel?.installed && s.traceModel.runtime,
        // The shapes already drawn: guesses come fitted around them, and the AI leaves them out.
        taken: drawnShapes(),
      },
      // The AI model reads a new picture first (a second or two, longer on slow computers).
      60_000,
    );
    if (my !== seq) return;
    const now = useStore.getState().autoTrace;
    if (!now) return;
    // The AI couldn't run (say, a damaged model file): the usual guesses still came.
    if (r.ai_error) info(r.ai_error);
    if (!r.candidates.length) {
      if (now.add.length || now.subtract.length) {
        // Keep what was there; the last click just didn't find anything.
        useStore.getState().setAutoTrace({ ...now, busy: false });
        info("Nothing found at that click; the guess is as it was.");
        return;
      }
      useStore.getState().setAutoTrace(null);
      info("Couldn't find a shape there. Try clicking nearer the middle of a shape, or on one of its lines.");
      return;
    }
    const guesses = yourUsualFirst(r.candidates);
    // Keep showing the same kind of guess after a Shift/Alt+click or a new spacing.
    const same = shown ? guesses.findIndex((g) => g.id === shown) : -1;
    useStore.getState().setAutoTrace({ ...now, guesses, index: same >= 0 ? same : 0, busy: false });
  } catch (err) {
    if (my !== seq) return;
    useStore.getState().setAutoTrace(null);
    info(`Auto-trace couldn't read that picture: ${err instanceof Error ? err.message : String(err)}`);
  }
}

/** The drawn shapes on the canvas (fills, satins, closed lines), as auto-trace takes them into account. */
function drawnShapes() {
  const items = useStore.getState().history.present?.layout.items ?? [];
  return items.filter((it) => it.kind === "fill" || it.kind === "applique" || it.kind === "satin" || it.kind === "run");
}

/** Guesses in the engine's order, but the kinds you pick most often first (the background stays last). */
export function yourUsualFirst(guesses: TraceGuess[], picks: Record<string, number> = loadPrefs().guessPicks ?? {}): TraceGuess[] {
  const bg = (g: TraceGuess) => (g.kind === "fill" && g.background ? 1 : 0);
  return guesses
    .map((g, i) => ({ g, i }))
    .sort((p, q) => bg(p.g) - bg(q.g) || (picks[q.g.id] ?? 0) - (picks[p.g.id] ?? 0) || p.i - q.i)
    .map((x) => x.g);
}

/** Remember which kind of guess was used, so it comes first next time. */
function notePick(id: string) {
  const picks = { ...(loadPrefs().guessPicks ?? {}) };
  picks[id] = (picks[id] ?? 0) + 1;
  savePrefs({ guessPicks: picks });
}

/** Forget which guesses you usually pick. */
export function resetPicks() {
  savePrefs({ guessPicks: {} });
  info("Auto-trace will show its guesses in its own order again.");
}

/** Tab / Shift+Tab: the next or previous guess. */
export function nextGuess(step: 1 | -1) {
  const s = useStore.getState();
  const a = s.autoTrace;
  if (!a || !a.guesses.length) return;
  s.setAutoTrace({ ...a, index: (a.index + step + a.guesses.length) % a.guesses.length });
}

/** [ / ]: points closer together or further apart (asks again). */
export function setSpacing(mm: number) {
  const v = Math.min(SPACING_MAX_MM, Math.max(SPACING_MIN_MM, Math.round(mm * 2) / 2));
  savePrefs({ traceSpacing: v });
  const s = useStore.getState();
  s.setAutoSpacing(v);
  if (s.autoTrace) void ask();
}

export const SPREAD_MIN = 1;
export const SPREAD_MAX = 10;

/** How readily a guess spreads into similar colors (asks again). */
export function setSpread(n: number) {
  const v = Math.min(SPREAD_MAX, Math.max(SPREAD_MIN, Math.round(n)));
  savePrefs({ traceSpread: v });
  const s = useStore.getState();
  s.setAutoSpread(v);
  if (s.autoTrace) void ask();
}

/** Use the AI model's guesses (when it's downloaded) or not. */
export function setTraceAI(on: boolean) {
  savePrefs({ traceAI: on });
  useStore.getState().setTraceAI(on);
  if (useStore.getState().autoTrace) void ask();
}

// ---------------------------------------------------------------- the optional AI model

type ModelStatus = { installed: boolean; runtime: boolean; size_mb: number; source: string; license: string };

export async function loadTraceModel() {
  const e = useStore.getState().engine;
  if (!e) return;
  try {
    useStore.getState().setTraceModel(await e.call<ModelStatus>("ai.trace_model"));
  } catch {
    useStore.getState().setTraceModel(null);
  }
}

/** Download the model (the user pressed Download; can take a few minutes on a slow connection). */
export async function downloadTraceModel() {
  const e = useStore.getState().engine;
  if (!e) return;
  useStore.getState().setTraceModel(await e.call<ModelStatus>("ai.trace_model_download", {}, 15 * 60_000));
  info("AI tracing is ready: Auto-trace now offers the AI's guesses first.");
}

export async function removeTraceModel() {
  const e = useStore.getState().engine;
  if (!e) return;
  useStore.getState().setTraceModel(await e.call<ModelStatus>("ai.trace_model_remove"));
}

export function dismissAutoTrace() {
  seq++;
  useStore.getState().setAutoTrace(null);
}

export type AcceptAs = "best" | "fill" | "satin" | "run" | "fillAndBorder";

/** Turn the shown guess into a real shape (or two), select it, and go to Select to adjust it. */
export async function acceptGuess(as: AcceptAs = "best") {
  const s = useStore.getState();
  const g = s.autoTrace?.guesses[s.autoTrace.index];
  if (!g || !s.autoTrace || s.autoTrace.busy) return;
  s.setAutoTrace({ ...s.autoTrace, busy: true }); // a second Enter doesn't add it twice
  const thread = g.color ? { color: g.color, name: "", brand: "", catalog: "" } : s.drawThread;
  let ok: boolean;
  if (g.kind === "satin") {
    const shape = as === "run" ? { kind: "run" as const, nodes: g.nodes, closed: g.closed } : { kind: "satin" as const, nodes: g.nodes, width_mm: g.width_mm, closed: g.closed };
    ok = await addTraced([shape], thread);
  } else if (as === "satin") {
    // Satin: each area filled with one satin that turns with it (as in Embrilliance), in the area's
    // colour. A part with holes can't be one satin: it stays a fill.
    const parts = [{ outline: g.outline, holes: g.holes }, ...(g.parts ?? [])];
    const shapes: Parameters<typeof addTraced>[0] = [];
    let kept = 0;
    for (const part of parts) {
      if (part.holes.length) {
        shapes.push({ kind: "fill", outline: part.outline, holes: part.holes });
        kept++;
        continue;
      }
      try {
        const r = await s.engine!.call<{ rail_a: PathNode[]; rail_b: PathNode[]; widest_mm: number }>("shape.satin_fill", { outline: part.outline, way: 0 });
        shapes.push({ kind: "column", ...r });
      } catch {
        shapes.push({ kind: "fill", outline: part.outline, holes: part.holes });
        kept++;
      }
    }
    ok = await addTraced(shapes, thread);
    if (ok && kept) info(`${kept === parts.length ? "It has" : "Some parts have"} holes, so ${kept === 1 ? "that part stays" : "those stay"} a fill.`);
  } else {
    // Every part (the clicked one, then any added with Shift+click), each with its border if asked.
    const shapes = [{ outline: g.outline, holes: g.holes }, ...(g.parts ?? [])].flatMap((part): Parameters<typeof addTraced>[0] => {
      const ribbon = { kind: "satin" as const, nodes: part.outline, width_mm: g.line_width_mm ?? satinWidthGuess(), closed: true };
      const fill = { kind: "fill" as const, outline: part.outline, holes: part.holes };
      return as === "run" ? [{ kind: "run" as const, nodes: part.outline, closed: true }] : as === "fillAndBorder" ? [fill, ribbon] : [fill];
    });
    // A border is sewn in the line's color (usually black), the fill in the area's.
    ok = await addTraced(shapes, thread, as === "fillAndBorder" ? { color: "#000000", name: "Black", brand: "", catalog: "" } : undefined);
  }
  // Only when it was really added: if the edit failed, the guess stays on screen to try again.
  if (!ok) {
    const now = useStore.getState().autoTrace;
    if (now) useStore.getState().setAutoTrace({ ...now, busy: false });
    return;
  }
  dismissAutoTrace();
  notePick(g.id);
  info("Added. Click the next shape to trace it, or press V to drag its points.");
}

const satinWidthGuess = () => useStore.getState().satinWidth;

/** Points of a guess, for drawing it. */
export function guessLists(g: TraceGuess): { nodes: PathNode[]; closed: boolean }[] {
  if (g.kind === "satin") return [{ nodes: g.nodes, closed: g.closed }];
  return [{ outline: g.outline, holes: g.holes }, ...(g.parts ?? [])].flatMap((p) => [
    { nodes: p.outline, closed: true },
    ...p.holes.map((h) => ({ nodes: h, closed: true })),
  ]);
}
