/**
 * "Import artwork" (P7-D1), the dialog registered as "importArt". It sits to the right of the
 * design area, where the shapes show as outlines on the hoop: what they'd be and how big, Width
 * (keeping the proportions), how lines come in, a tick for each color (the background unticked),
 * matching colors to your own threads, and what was left out and why. Nothing is added until Add.
 */
import { useEffect, useState, type KeyboardEvent } from "react";
import { holdEscape, letGoNewest } from "../escape";
import { addImported, canAdd, chosenShapes, countWords, mySpools, previewColors, setArtOptions, setMatch, toggleColor, useImportArt, type StrokeMode } from "../feat/importArt";
import type { Units } from "../design/grid";
import { selectHoop, useStore } from "../store";
import { Check, fmtLen, fromUnits, toUnits } from "./controls";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

/** The most pages offered: the engine refuses a PDF with more, and a longer list (a file can claim
 *  a million pages) would freeze the window. */
const MAX_PAGES = 2000;

const LINES_AS: { id: StrokeMode; label: string; title: string }[] = [
  { id: "auto", label: "Automatic", title: "Under 1 mm wide: running stitch. 1 to 12 mm: satin of that width. Wider: a filled shape." },
  { id: "lines", label: "Running stitch", title: "Every line as a running stitch along its middle" },
  { id: "satins", label: "Satin", title: "Every line as a satin (at least 1 mm wide)" },
];

/** Its own place: docked right, with nothing dimmed, so the outlines show. */
const STYLE = `
dialog.modal.import-art { width: min(360px, calc(100vw - 32px)); margin-left: auto; margin-right: 8px; }
dialog.modal.import-art::backdrop { background: transparent; }
dialog.modal.import-art .art-size { font-weight: 600; margin: 0 0 0.6rem; }
dialog.modal.import-art .art-width { display: flex; align-items: center; flex-wrap: wrap; gap: 0.4rem; }
dialog.modal.import-art .art-width input { width: 6rem; padding: 0.2rem 0.35rem; border: 1px solid var(--line); border-radius: 5px; background: var(--bg); }
dialog.modal.import-art .art-colors { list-style: none; margin: 0 0 0.6rem; padding: 0; max-height: 150px; overflow-y: auto; }
dialog.modal.import-art .art-colors label.check { margin: 0.15rem 0; }
dialog.modal.import-art .art-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 1px solid var(--line); align-self: center; }
dialog.modal.import-art .art-left-out { margin: 0 0 0.75rem; padding-left: 1.1rem; font-size: 12px; color: var(--muted); max-height: 130px; overflow-y: auto; }
`;

const fileName = (path: string) => path.split(/[\\/]/).pop() ?? path;

/** Width, kept in proportion; empty means the drawing's own size. Committed on Enter or on
 *  leaving the box, so each key doesn't read the file again. */
function WidthField({ shownMm, set }: { shownMm: number | null; set: (mm: number | null) => void }) {
  const units: Units = useStore((s) => s.units);
  const shown = shownMm === null ? "" : toUnits(shownMm, units).toFixed(units === "in" ? 2 : 1);
  const [text, setText] = useState(shown);
  useEffect(() => setText(shown), [shown]);
  const done = () => {
    if (text.trim() === shown) return;
    const v = Number(text);
    if (text.trim() && Number.isFinite(v)) set(Math.round(fromUnits(v, units) * 100) / 100);
    else setText(shown);
  };
  return (
    <input
      type="number"
      aria-label="Width"
      min={0}
      step="any"
      placeholder="real size"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={done}
      onKeyDown={(e) => {
        // Enter here only sets the width (a second one adds).
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          done();
        }
      }}
    />
  );
}

export function ImportArtDialog() {
  const ref = useModal(true);
  const state = useImportArt();
  const units = useStore((s) => s.units);
  const hoop = useStore(selectHoop);
  const hasSpools = useStore((s) => mySpools(s.charts) !== null);
  const { path, options, preview, busy, error, off, match, pages } = state;

  // Esc closes it through the app's one list of things Esc lets go of.
  useEffect(() => holdEscape(close), []);
  // Nothing to import (the dialog was opened some other way): close it again.
  useEffect(() => {
    if (!useImportArt.getState().path) close();
  }, []);

  if (!path) return null;

  const chosen = chosenShapes(state);
  const colors = previewColors(preview);
  const background = preview?.shapes.find((s) => s.background);
  const size = preview?.size_mm;
  const tooBig = size && hoop && (size[0] > hoop.width_mm + 0.5 || size[1] > hoop.height_mm + 0.5);
  const ready = canAdd(state);

  // The app's keyboard handler leaves open dialogs alone, so Esc and Enter are handled here, and
  // go no further, so nothing else acts on them as well.
  const onKeyDown = (e: KeyboardEvent) => {
    const esc = e.key === "Escape";
    // On a button or a list, Enter works that (the browser's own click or choice).
    if (!esc && (e.key !== "Enter" || e.target instanceof HTMLButtonElement || e.target instanceof HTMLSelectElement)) return;
    e.preventDefault(); // (nor does the browser close the dialog a second way)
    e.stopPropagation();
    if (e.repeat) return;
    if (esc) letGoNewest();
    else void addImported();
  };

  return (
    <dialog ref={ref} className="modal import-art" onClose={close} onKeyDown={onKeyDown} aria-labelledby="import-art-title">
      <style>{STYLE}</style>
      <h2 id="import-art-title">Import artwork</h2>
      <p className="hint">
        <b>{fileName(path)}</b>: nothing is added until you press Add.
      </p>
      {busy && (
        <p className="hint" role="status">
          Reading the drawing…
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {preview && size && (
        <p className="art-size">
          {countWords(chosen)} · {units === "in" ? `${toUnits(size[0], units).toFixed(2)} × ${fmtLen(size[1], units)}` : `${size[0].toFixed(0)} × ${fmtLen(size[1], units, 0)}`}
        </p>
      )}
      {preview?.scale_note && options.width_mm === null && <p className="hint">{preview.scale_note}</p>}
      {tooBig && hoop && (
        <p className="hint">
          Bigger than your hoop ({fmtLen(hoop.width_mm, units, units === "in" ? 1 : 0)} × {fmtLen(hoop.height_mm, units, units === "in" ? 1 : 0)}): set Width to fit it.
        </p>
      )}
      <div className="field">
        Width
        <span className="art-width">
          <WidthField shownMm={options.width_mm ?? size?.[0] ?? null} set={(mm) => setArtOptions({ width_mm: mm })} />
          <small>{units}, keeps the proportions</small>
          {options.width_mm !== null && (
            <button onClick={() => setArtOptions({ width_mm: null })} title="The size the file says">
              Real size
            </button>
          )}
        </span>
      </div>
      <div className="field">
        Lines as
        <div className="seg wrap" role="group" aria-label="Lines as">
          {LINES_AS.map((m) => (
            <button key={m.id} aria-pressed={options.strokes === m.id} title={m.title} onClick={() => setArtOptions({ strokes: m.id })}>
              {m.label}
            </button>
          ))}
        </div>
      </div>
      {/\.dxf$/i.test(path) && (
        <Check label="Fill closed shapes" checked={options.closed_as_fills} onChange={(v) => setArtOptions({ closed_as_fills: v })} hint="Closed outlines come in as fills, and one inside another is its hole" />
      )}
      {pages > 1 && (
        <label className="field">
          Page
          <select value={options.page} onChange={(e) => setArtOptions({ page: Number(e.target.value) })}>
            {Array.from({ length: Math.min(pages, MAX_PAGES) }, (_, i) => (
              <option key={i} value={i}>
                {i + 1} of {pages}
              </option>
            ))}
          </select>
        </label>
      )}
      {(colors.length > 0 || background) && (
        <ul className="art-colors" aria-label="Colors">
          {background && (
            <li>
              <label className="check">
                <input type="checkbox" checked={options.keep_background} onChange={(e) => setArtOptions({ keep_background: e.target.checked })} />
                <span className="art-swatch" style={{ background: background.color }} />
                Background rectangle
              </label>
            </li>
          )}
          {colors.map(({ color, count }) => (
            <li key={color}>
              <label className="check">
                <input type="checkbox" checked={!off.includes(color)} onChange={(e) => toggleColor(color, e.target.checked)} />
                <span className="art-swatch" style={{ background: color }} />
                {color} · {count === 1 ? "1 shape" : `${count} shapes`}
              </label>
            </li>
          ))}
        </ul>
      )}
      <label className="check" title={hasSpools ? "Each color becomes the closest of your own spools" : "Add your spools in My threads & charts to use this"}>
        <input type="checkbox" checked={match && hasSpools} disabled={!hasSpools} onChange={(e) => setMatch(e.target.checked)} />
        Match colors to my threads
        {!hasSpools && <small>My threads has no spools yet.</small>}
      </label>
      {preview && preview.warnings.length > 0 && (
        <ul className="warnings">
          {preview.warnings.map((w) => (
            <li key={w.code} className={`w-${w.level}`}>
              {w.message}
            </li>
          ))}
        </ul>
      )}
      {preview && preview.skipped.length > 0 && (
        <ul className="art-left-out" aria-label="Left out">
          {preview.skipped.map((s) => (
            <li key={s.what}>{s.message}</li>
          ))}
        </ul>
      )}
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button className="primary" disabled={!ready} onClick={() => void addImported()}>
          Add
        </button>
      </div>
    </dialog>
  );
}
