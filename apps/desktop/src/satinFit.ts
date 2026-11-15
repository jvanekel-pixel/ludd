/**
 * Satin edge fit in the app (the geometry is in design/edgeFit.ts): while you draw a satin, watch
 * whether your points follow the edge of a shape you've made; if they do, offer to fit the satin
 * along it. Tab applies the first way, Tab again the next (Shift+Tab goes back), Enter finishes as
 * usual, and Esc puts your own points back. Nothing changes without a key press.
 */
import { edgeFitsFor } from "./design/edgeFit";
import { holdEscape } from "./escape";
import { useStore, type Pen } from "./store";

/** The pen as a fit left it: any other change to the pen (a click, Backspace, finishing) ends the fit. */
let applied: Pen | null = null;
let releaseEsc: (() => void) | null = null;

function letGoOfEsc() {
  releaseEsc?.();
  releaseEsc = null;
}

function refresh() {
  const s = useStore.getState();
  const pen = s.pen;
  if (applied && pen === applied) return; // a fit is showing
  if (applied) {
    // The pen moved on from the fit (another click, or it was finished): it's yours now.
    applied = null;
    letGoOfEsc();
  }
  const layout = s.history.present?.layout;
  if (!pen || pen.kind !== "satin" || pen.a.length < 2 || pen.closed || !layout) {
    if (s.edgeFit) s.setEdgeFit(null);
    return;
  }
  const options = edgeFitsFor(layout, pen.a.map((n) => [n[0], n[1]] as [number, number]), s.satinWidth, pen.replaceId);
  s.setEdgeFit(options.length ? { options, index: 0, original: null } : null);
}

/** Watch the pen (and what it could follow) for the life of the app. */
export function startSatinFit() {
  return useStore.subscribe((s, prev) => {
    if (s.pen !== prev.pen || s.satinWidth !== prev.satinWidth || s.history.present?.layout !== prev.history.present?.layout) refresh();
  });
}

/** A fit is on offer, or showing. */
export const canFit = () => {
  const s = useStore.getState();
  return !!s.edgeFit?.options.length && s.pen?.kind === "satin";
};

/** Tab: apply the first way to fit, or move to the next (`step` -1: the one before). */
export function nextFit(step: 1 | -1 = 1) {
  const s = useStore.getState();
  const f = s.edgeFit;
  const pen = s.pen;
  if (!f || !pen || !f.options.length) return;
  const n = f.options.length;
  const original = f.original ?? pen;
  const index = f.original ? (f.index + step + n) % n : 0;
  const opt = f.options[index];
  const next: Pen = { ...original, a: opt.nodes, closed: opt.closed };
  applied = next;
  s.setEdgeFit({ ...f, index, original });
  s.setPen(next);
  releaseEsc ??= holdEscape(putBack);
}

/** Esc: back to the points you clicked (the fit is offered again). */
export function putBack() {
  const s = useStore.getState();
  const f = s.edgeFit;
  letGoOfEsc();
  if (!f?.original) return;
  applied = null;
  s.setPen(f.original);
}
