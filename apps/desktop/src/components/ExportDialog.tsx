import { useEffect, useRef, useState } from "react";
import { basename, exportOptions, previewExport, saveExport, sortFormats, splitPlan, type SplitPlan } from "../actions";
import { defaultCutStops, defaultFormat, hoopFit } from "../design/machine";
import type { CutStops, ExportReport } from "../design/types";
import { hasRecolors } from "../design/layout";
import type { Layout } from "../design/types";
import { selectHoop, selectLayout, selectMachine, useStore } from "../store";

/** Plain-words list of what's different from the original file(s). */
function describeEdits(l: Layout): string[] {
  const out: string[] = [];
  if (l.items.length > 1) out.push(`${l.items.length} designs combined`);
  if (l.items.some((it) => it.transform.x || it.transform.y)) out.push("moved");
  if (l.items.some((it) => it.transform.rotate || it.transform.flip_x || it.transform.flip_y)) out.push("turned");
  if (l.items.some((it) => it.transform.scale_x !== 1 || it.transform.scale_y !== 1)) out.push("resized");
  if (hasRecolors(l)) out.push("new thread colors");
  if (l.items.some((it) => it.ops.length)) out.push("stitch edits");
  if (l.merge_colors || l.color_sort) out.push("colors combined");
  if (l.basting.enabled) out.push("basting box");
  return out;
}

const LEVEL_ICON = { error: "⛔", warning: "⚠️", info: "ℹ️" } as const;
const SPLIT_COLORS = ["#2b7bd6", "#e0218a", "#2f8f4e", "#e08a00"];

/** A small map of the hoopings: each sewing window, numbered, the design's outline and the pink crosses. */
function SplitMap({ plan, bounds }: { plan: SplitPlan; bounds: [number, number, number, number] | null }) {
  const ws = plan.sections.map((s) => s.window_mm);
  const x0 = Math.min(...ws.map((w) => w[0]));
  const y0 = Math.min(...ws.map((w) => w[1]));
  const x1 = Math.max(...ws.map((w) => w[2]));
  const y1 = Math.max(...ws.map((w) => w[3]));
  const pad = 4;
  return (
    <svg className="split-map" viewBox={`${x0 - pad} ${y0 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`} role="img" aria-label={`${plan.sections.length} hoopings`}>
      {bounds && <rect x={bounds[0]} y={bounds[1]} width={bounds[2] - bounds[0]} height={bounds[3] - bounds[1]} className="design" />}
      {plan.sections.map((s, i) => {
        const [a, b, c, d] = s.window_mm;
        const color = SPLIT_COLORS[i % SPLIT_COLORS.length];
        return (
          <g key={i}>
            <rect x={a} y={b} width={c - a} height={d - b} fill={color} fillOpacity={0.08} stroke={color} strokeWidth={1.2} />
            <text x={a + 4} y={b + 14} fill={color} fontSize={13} fontWeight={700}>
              {i + 1}
            </text>
          </g>
        );
      })}
      {plan.sections.flatMap((s) => s.marks).map(([x, y], i) => (
        <path key={i} d={`M${x - 3} ${y}H${x + 3}M${x} ${y - 3}V${y + 3}`} stroke="#e0218a" strokeWidth={1.5} />
      ))}
    </svg>
  );
}

/** "Save for machine": the beginner sees what they'll get and one recommended choice; the rest is under More options. */
export function ExportDialog() {
  const open = useStore((s) => s.exportOpen);
  const setOpen = useStore((s) => s.setExportOpen);
  const design = useStore((s) => s.design);
  const machine = useStore(selectMachine);
  const hoop = useStore(selectHoop);
  const formats = useStore((s) => s.formats);
  const layout = useStore(selectLayout);
  const notify = useStore((s) => s.notify);
  const ref = useRef<HTMLDialogElement>(null);

  const [ext, setExt] = useState("pes");
  const [cut, setCut] = useState<CutStops>(defaultCutStops(null, null));
  const [report, setReport] = useState<ExportReport | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [split, setSplit] = useState(true);
  const [overlap, setOverlap] = useState(10);
  const [plan, setPlan] = useState<SplitPlan | null>(null);
  const setSplitPreview = useStore((s) => s.setSplitPreview);

  // Reset to the machine's recommended settings each time the dialog opens.
  useEffect(() => {
    const d = ref.current!;
    if (open && !d.open) {
      setExt(defaultFormat(machine));
      setCut(defaultCutStops(machine, design));
      setReport(null);
      setPreviewError(null);
      d.showModal();
    } else if (!open && d.open) d.close();
  }, [open, machine, design]);

  // Live preview of stops and warnings, debounced while dragging the slider.
  useEffect(() => {
    if (!open || !design) return;
    let stale = false;
    const t = setTimeout(() => {
      previewExport(exportOptions(cut), ext)
        .then((r) => {
          if (stale) return;
          setReport(r);
          setPreviewError(null);
        })
        .catch((err: unknown) => !stale && setPreviewError(err instanceof Error ? err.message : String(err)));
    }, 150);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [open, design, ext, cut, machine, hoop, layout]);

  const tooBig = !!design && !!hoop && hoopFit(design.info, hoop) === "too_big";
  const splitting = tooBig && split;

  // Too big for the hoop: work out the hoopings, and show them on the canvas.
  useEffect(() => {
    if (!open || !splitting) {
      setPlan(null);
      setSplitPreview(null);
      return;
    }
    let stale = false;
    const t = setTimeout(() => {
      splitPlan(overlap)
        .then((p) => {
          if (stale) return;
          setPlan(p);
          setSplitPreview(p.sections.map((s) => ({ window_mm: s.window_mm, marks: s.marks })));
        })
        .catch((err: unknown) => !stale && setPreviewError(err instanceof Error ? err.message : String(err)));
    }, 150);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [open, splitting, overlap, design, hoop, setSplitPreview]);

  const run = async () => {
    setBusy(true);
    try {
      const r = await saveExport(exportOptions(cut), ext, splitting ? { overlap_mm: overlap } : undefined);
      if (r) {
        setOpen(false);
        const stops = r.stops_added ? ` with ${r.stops_added} cut-stops` : "";
        const what = r.paths && r.paths.length > 1 ? `${r.paths.length} files, one per hooping (${basename(r.paths[0])}…)` : basename(r.path);
        notify({ kind: "info", text: `Saved ${what}${stops}` });
      }
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const writable = sortFormats(formats?.write ?? [{ ext: "pes", description: "" }]);
  const machineFormats = new Set(machine?.formats ?? []);
  const problems = report?.warnings.filter((w) => w.level !== "info" && w.code !== "hoop_too_big") ?? [];
  const notes = report?.warnings.filter((w) => w.level === "info" && w.code !== "stops_added") ?? [];
  const hasErrors = report?.warnings.some((w) => w.level === "error" && !(splitting && w.code === "hoop_too_big")) ?? false;
  const fit = design && hoop ? hoopFit(design.info, hoop) : null;
  const edits = layout ? describeEdits(layout) : [];
  const stops = report?.stops_added ?? 0;
  const cutsOnlyAtColors = machine?.cuts === "color_change";

  return (
    <dialog ref={ref} className="modal export" onClose={() => setOpen(false)} onCancel={(e) => busy && e.preventDefault()}>
      <h2>Save for {machine ? `your ${machine.name}` : "your machine"}</h2>

      <ul className="summary">
        <li className={`ok-${fit === "too_big" ? (splitting ? "warn" : "bad") : fit === "rotate" ? "warn" : "good"}`}>
          {fit === "too_big"
            ? splitting && plan
              ? `Bigger than the ${hoop?.name} hoop: sews in ${plan.sections.length} hoopings`
              : `Too big for the ${hoop?.name} hoop`
            : fit === "rotate"
              ? `Fits the ${hoop?.name} hoop if you rotate it 90° on the machine`
              : `Fits the ${hoop?.name ?? ""} hoop`}
        </li>
        <li className="ok-good">
          Saves as {ext.toUpperCase()}
          {machineFormats.has(ext) ? ", which your machine reads" : ""}
        </li>
        {edits.length > 0 && <li className="ok-good">With your changes: {edits.join(", ")}</li>}
      </ul>

      {tooBig && (
        <label className="check big">
          <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} disabled={busy} />
          <span>
            Split it across hoopings{plan ? ` (${plan.cols} × ${plan.rows})` : ""} (recommended)
            {plan && <SplitMap plan={plan} bounds={design ? design.info.bounds_mm : null} />}
            <small>
              One file per hooping, shown numbered on the design. Each ends and the next begins with pink alignment crosses: sew 1, re-hoop so the
              needle lands on the crosses when you start 2, and so on. Pull the pink crosses out afterwards.
            </small>
          </span>
        </label>
      )}

      {(cutsOnlyAtColors || cut.enabled) && (
        <label className="check big">
          <input
            type="checkbox"
            checked={cut.enabled}
            onChange={(e) => setCut({ ...cut, enabled: e.target.checked })}
            disabled={busy}
          />
          <span>
            Have the machine cut jump threads{cutsOnlyAtColors ? " (recommended)" : ""}
            <small>
              {cut.enabled && report
                ? stops
                  ? `Adds ${stops} stop${stops === 1 ? "" : "s"}. At each one the machine ties off and cuts. Just press Start; no thread change.`
                  : "This design has no jump threads long enough to cut."
                : "The machine stops, ties off and cuts at each jump. You press Start to carry on."}
            </small>
          </span>
        </label>
      )}

      {problems.length > 0 && (
        <ul className="warnings">
          {problems.map((w) => (
            <li key={w.code} className={`w-${w.level}`}>
              <span aria-hidden>{LEVEL_ICON[w.level]}</span> {w.message}
              {w.why && <small className="why">{w.why}</small>}
            </li>
          ))}
        </ul>
      )}
      {report?.fabric_advice && <p className="hint fabric-advice">🧵 {report.fabric_advice}</p>}
      {previewError && <p className="error">{previewError}</p>}

      <details className="more">
        <summary>More options</summary>
        <label className="field">
          File format
          <select value={ext} onChange={(e) => setExt(e.target.value)} disabled={busy}>
            {writable.map((f) => (
              <option key={f.ext} value={f.ext}>
                {f.ext.toUpperCase()}
                {f.description ? ` – ${f.description}` : ""}
                {machineFormats.has(f.ext) ? " (your machine)" : ""}
              </option>
            ))}
          </select>
        </label>
        {splitting && (
          <label className="slider">
            Overlap between hoopings <strong>{overlap} mm</strong>
            <input type="range" min={6} max={30} step={1} value={overlap} onChange={(e) => setOverlap(Number(e.target.value))} />
          </label>
        )}
        <fieldset className={`cut-options${cut.enabled ? "" : " disabled"}`} disabled={!cut.enabled || busy}>
          <legend>Cutting jump threads</legend>
          <label className="slider">
            Only cut jumps longer than <strong>{cut.min_jump_mm.toFixed(1)} mm</strong>
            <input
              type="range"
              min={1}
              max={20}
              step={0.5}
              value={cut.min_jump_mm}
              onChange={(e) => setCut({ ...cut, min_jump_mm: Number(e.target.value) })}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={cut.include_untrimmed}
              onChange={(e) => setCut({ ...cut, include_untrimmed: e.target.checked })}
            />
            Also cut jumps the design doesn't mark for trimming
            <small>Usually these are hidden under later stitching.</small>
          </label>
          <label className="check">
            <input type="checkbox" checked={cut.tie} onChange={(e) => setCut({ ...cut, tie: e.target.checked })} />
            Add lock stitches before and after each cut
          </label>
        </fieldset>
        {notes.length > 0 && (
          <ul className="warnings">
            {notes.map((w) => (
              <li key={w.code} className="w-info">
                {w.message}
              </li>
            ))}
          </ul>
        )}
      </details>

      <div className="actions">
        <button onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </button>
        <button className="primary" onClick={run} disabled={busy || !design}>
          {busy ? "Saving…" : hasErrors ? "Save anyway…" : "Save…"}
        </button>
      </div>
    </dialog>
  );
}
