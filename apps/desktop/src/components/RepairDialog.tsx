/**
 * "Repair this design" (P4-B1), the dialog registered as "repair": the repairs this stitch file can
 * have (feat/repair/steps.ts), each with a tick box, its setting and what it would do, and the
 * design's numbers before and after. Nothing changes until Accept. "Show on the design" moves the
 * dialog aside and marks in red the stitches that would come out.
 */
import type { Graphics } from "pixi.js";
import { useEffect, useState, type KeyboardEvent } from "react";
import { create } from "zustand";
import { commit, currentLayout, info, targetId } from "../actions";
import { registerOverlay } from "../canvas/hooks";
import type { Field } from "../design/fillPatterns";
import type { Units } from "../design/grid";
import { Kind, type FileItem, type Layout, type LayoutItemInfo, type LayoutOp } from "../design/types";
import { holdEscape, letGoNewest } from "../escape";
import { isStitchFile, previewRepairs, repairOps, repairRequest, repairSteps, setItemRepairs, withRepairs, type RepairResults, type RepairStep, type Stats } from "../feat/repair/steps";
import { selectLayout, useStore } from "../store";
import { fmtLen } from "./controls";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);
/** Wait for the ticks and settings to settle before asking the engine. */
const DEBOUNCE_MS = 300;

// ---------------------------------------------------------------- "Show on the design"

/** What "Show on the design" marks: stitches of one item, by number, as [from, to) ranges. */
export const useRepairHighlight = create<{ shown: { id: string; ranges: [number, number][] } | null }>(() => ({ shown: null }));

const RED = 0xe0102a;

/** The marked stitches in red over the design: their thread, edged in white so it shows on any
 *  color, with a dot where the needle went down. */
function drawRemoved(g: Graphics, px: number) {
  const shown = useRepairHighlight.getState().shown;
  if (!shown?.ranges.length) return;
  const s = useStore.getState();
  const records = s.design?.records;
  const owner = s.history.present?.layout.items.findIndex((it) => it.id === shown.id) ?? -1;
  if (!records?.item || !records.src || owner < 0) return;
  const { x, y, kind, item, src } = records;
  const numbers = new Set<number>();
  for (const [from, to] of shown.ranges) for (let n = from; n < to; n++) numbers.add(n);
  const stitch = (i: number) => i >= 0 && i < kind.length && item[i] === owner && kind[i] === Kind.Stitch;
  const marked: number[] = [];
  for (let i = 0; i < kind.length; i++) if (stitch(i) && numbers.has(src[i])) marked.push(i);
  if (!marked.length) return;
  const isMarked = new Set(marked);
  const thread = () => {
    for (const i of marked) {
      if (stitch(i - 1)) g.moveTo(x[i - 1], y[i - 1]).lineTo(x[i], y[i]);
      if (stitch(i + 1) && !isMarked.has(i + 1)) g.moveTo(x[i], y[i]).lineTo(x[i + 1], y[i + 1]);
    }
  };
  thread();
  g.stroke({ width: 4.5 * px, color: 0xffffff, alpha: 0.9, cap: "round", join: "round" });
  thread();
  g.stroke({ width: 2.2 * px, color: RED, cap: "round", join: "round" });
  const seen = new Set<string>();
  for (const i of marked) {
    // One dot per couple of screen pixels: a big file stays quick to draw.
    const key = `${Math.round(x[i] / (2 * px))},${Math.round(y[i] / (2 * px))}`;
    if (seen.has(key)) continue;
    seen.add(key);
    g.circle(x[i], y[i], 3 * px);
  }
  g.fill({ color: RED }).stroke({ width: px, color: 0xffffff });
}

// Registered once; it draws only while the dialog marks something.
registerOverlay({ id: "repair-removed", draw: drawRemoved });

/** The design's box with room on the right, where the dialog sits while showing. */
const clearOfDialog = ([x0, y0, x1, y1]: [number, number, number, number]): [number, number, number, number] => [x0, y0, x1 + (x1 - x0) * 0.25, y1];

// ---------------------------------------------------------------- settings

const fieldKey = (step: RepairStep, f: Field) => `${step.id}.${f.key}`;
const fieldText = (f: Field, v: number) => v.toFixed(f.digits ?? 2);

/** What a setting's box means: its number held to its range (and its digits), or the standard one
 *  if it's empty. */
function fieldValue(f: Field, text: string | undefined): number {
  const v = Number(text);
  return text?.trim() && Number.isFinite(v) ? Number(fieldText(f, Math.min(f.max, Math.max(f.min, v)))) : f.def;
}

/** Ticked when it opens: what's on already, what the repair suggests, and what Fix it asked for. */
function startTicks(item: FileItem, shown: LayoutItemInfo, steps: RepairStep[], tick: string | undefined): Record<string, boolean> {
  return Object.fromEntries(steps.map((s) => [s.id, item.ops.some((o) => o.op === s.op) || s.preset(item, shown) || s.id === tick]));
}

function startTexts(item: FileItem, steps: RepairStep[]): Record<string, string> {
  return Object.fromEntries(
    steps.flatMap((s) => {
      const on = item.ops.find((o) => o.op === s.op) as Record<string, unknown> | undefined;
      return s.fields.map((f) => [fieldKey(s, f), fieldText(f, typeof on?.[f.key] === "number" ? (on[f.key] as number) : f.def)]);
    }),
  );
}

/** What Accept would write: the ticked repairs, and any on already that aren't listed. */
function chosenOps(item: FileItem, steps: RepairStep[], ticks: Record<string, boolean>, texts: Record<string, string>): LayoutOp[] {
  const unlisted = repairOps(item).filter((o) => !steps.some((s) => s.op === o.op));
  const ticked = steps
    .filter((s) => ticks[s.id])
    .map((s) => s.make(Object.fromEntries(s.fields.map((f) => [f.key, fieldValue(f, texts[fieldKey(s, f)])]))));
  return withRepairs([], [...unlisted, ...ticked]);
}

// ---------------------------------------------------------------- the preview

type Shown = { key: string; layout: Layout; results?: RepairResults; error?: string };

/** The preview of `ops`, worked out a moment after they (or the design) last changed. `fresh` is
 *  false while it's being worked out; the last results stay meanwhile. */
function usePreview(layout: Layout | undefined, id: string | undefined, ops: LayoutOp[]) {
  const key = JSON.stringify(ops);
  const [shown, setShown] = useState<Shown | null>(null);
  useEffect(() => {
    if (!layout || !id) return;
    let stale = false;
    const timer = setTimeout(async () => {
      try {
        const results = await previewRepairs(layout, id, JSON.parse(key) as LayoutOp[], () => stale);
        if (results && !stale) setShown({ key, layout, results });
      } catch (err) {
        if (!stale) setShown((last) => ({ key, layout, results: last?.results, error: err instanceof Error ? err.message : String(err) }));
      }
    }, DEBOUNCE_MS);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [layout, id, key]);
  const fresh = !!shown && shown.key === key && shown.layout === layout;
  return { fresh, results: shown?.results, error: fresh ? shown.error : undefined };
}

const ROWS: { name: string; show: (s: Stats, units: Units) => string; over?: (s: Stats, limit: number) => boolean }[] = [
  { name: "Stitches", show: (s) => s.stitches.toLocaleString() },
  { name: "Trims", show: (s) => s.trims.toLocaleString() },
  { name: "Tiny stitches", show: (s) => s.tiny.toLocaleString() },
  { name: "Longest stitch", show: (s, units) => fmtLen(s.longest_mm, units) },
  { name: "Densest spot", show: (s) => s.densest.toFixed(1), over: (s, limit) => s.densest > limit },
];

// ---------------------------------------------------------------- the dialog

export function RepairDialog() {
  const ref = useModal(true);
  const units = useStore((s) => s.units);
  const layout = useStore(selectLayout) ?? undefined;
  const design = useStore((s) => s.design);
  const [request] = useState(() => repairRequest() ?? { id: targetId() ?? "", tick: undefined });
  const found = layout?.items.find((it) => it.id === request.id);
  const item = found && isStitchFile(found) ? found : undefined;
  const drawn = design?.items?.find((i) => i.id === request.id);
  const steps = item && drawn ? repairSteps().filter((s) => s.visible(item, drawn)) : [];
  const [ticks, setTicks] = useState(() => (item && drawn ? startTicks(item, drawn, steps, request.tick) : {}));
  const [texts, setTexts] = useState(() => (item ? startTexts(item, steps) : {}));
  const ops = item ? chosenOps(item, steps, ticks, texts) : [];
  const { fresh, results, error } = usePreview(layout, item?.id, ops);
  const [showing, setShowing] = useState(false);
  const removed = results?.preview.removed;

  // Esc closes it through the app's one list of things Esc lets go of.
  useEffect(() => holdEscape(close), []);
  // The design it's for is gone (a background edit finished, say): nothing left to repair.
  const gone = !item || !drawn;
  useEffect(() => {
    if (gone) close();
  }, [gone]);
  const markId = showing ? item?.id : undefined;
  useEffect(() => {
    useRepairHighlight.setState({ shown: markId && removed ? { id: markId, ranges: removed } : null });
  }, [markId, removed]);
  useEffect(() => () => useRepairHighlight.setState({ shown: null }), []);

  if (!item || !drawn) return null;

  const toggleShowing = () => {
    setShowing(!showing);
    // Frame the design, so the red can be seen (the view can't be moved while the dialog is open).
    if (!showing && drawn.bounds_mm) useStore.getState().requestZoom("box", { box: clearOfDialog(drawn.bounds_mm) });
  };

  const accept = () => {
    if (error) return;
    close();
    const now = currentLayout();
    if (!now) return;
    const changed = JSON.stringify(ops) !== JSON.stringify(withRepairs([], repairOps(item)));
    void commit(setItemRepairs(now, item.id, ops)).then((ok) => {
      if (ok && changed) info("Repairs saved on this design; your stitch file isn't changed. Ctrl+Z undoes it.");
    });
  };

  // The app's keyboard handler leaves open dialogs alone, so Esc and Enter are handled here, and
  // go no further, so nothing else acts on them as well.
  const onKeyDown = (e: KeyboardEvent) => {
    const esc = e.key === "Escape";
    // On a button, Enter presses that button (the browser's own click).
    if (!esc && (e.key !== "Enter" || e.target instanceof HTMLButtonElement)) return;
    e.preventDefault(); // (nor does the browser close the dialog a second way)
    e.stopPropagation();
    if (e.repeat) return;
    if (esc) letGoNewest();
    else accept();
  };

  const limit = results?.preview.limit;
  const anyRemoved = !!removed?.length;
  // Rebuild and the density limit replace stitches rather than just taking them out.
  const remade = ops.some((o) => o.op === "rebuild" || o.op === "density_limit");
  const inRed = remade ? "In red: the stitches that would be taken out or made again." : "In red: the stitches that would come out.";
  return (
    <dialog ref={ref} className={`modal repair-dialog${showing ? " peek" : ""}`} onClose={close} onKeyDown={onKeyDown} aria-labelledby="repair-title">
      <h2 id="repair-title">Repair this design</h2>
      <p className="hint">
        <b>{drawn.name}</b>: your stitch file isn't changed. Repairs happen as the design is drawn and saved.
      </p>
      <ul className="repair-steps">
        {steps.map((step) => {
          const on = !!ticks[step.id];
          return (
            <li key={step.id}>
              <label className="check">
                <input type="checkbox" checked={on} onChange={(e) => setTicks({ ...ticks, [step.id]: e.target.checked })} />
                <span>{step.label}</span>
              </label>
              {step.fields.map((f) => {
                const k = fieldKey(step, f);
                return (
                  <label key={f.key} className="repair-field" title={f.title}>
                    <span>{f.label}</span>
                    <input
                      type="number"
                      min={f.min}
                      max={f.max}
                      step={f.step}
                      value={texts[k] ?? ""}
                      disabled={!on}
                      onChange={(e) => setTexts({ ...texts, [k]: e.target.value })}
                      onBlur={() => setTexts({ ...texts, [k]: fieldText(f, fieldValue(f, texts[k])) })}
                    />
                    {f.suffix && <small>{f.suffix}</small>}
                  </label>
                );
              })}
              <p className={`repair-line${on ? " on" : ""}`}>{!on ? step.hint : fresh && results ? (results.lines[step.op] ?? "") : error ? "" : "Working it out…"}</p>
            </li>
          );
        })}
      </ul>
      {steps.length === 0 && <p className="hint">No repairs fit this design.</p>}
      <table className={`repair-table${fresh ? "" : " stale"}`}>
        <thead>
          <tr>
            <td />
            <th scope="col">Before</th>
            <th scope="col">After</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.name}>
              <th scope="row">
                {row.name}
                {row.over && limit !== undefined && <small title="Thread in the fullest square millimeter, in mm per mm²"> (too dense over {limit})</small>}
              </th>
              {[results?.preview.before, results?.preview.after].map((s, i) => (
                <td key={i} className={s && limit !== undefined && row.over?.(s, limit) ? "over" : undefined}>
                  {s ? row.show(s, units) : "–"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {fresh && results?.preview.notes.map((n) => (
        <p key={n} className="hint repair-note">
          {n}
        </p>
      ))}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="repair-show">
        <button type="button" aria-pressed={showing} onClick={toggleShowing} disabled={!showing && !anyRemoved}>
          Show on the design
        </button>
        <small>{showing && anyRemoved ? inRed : fresh && results && !anyRemoved ? "Nothing would come out." : ""}</small>
      </div>
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button className="primary" onClick={accept} disabled={!!error}>
          Accept
        </button>
      </div>
    </dialog>
  );
}
