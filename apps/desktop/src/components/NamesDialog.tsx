/** "One file per name…" (text.names): names typed in or loaded from a list fill the lettering,
 *  with each row previewed on the design, and each saved as its own machine file. Also name
 *  templates: start from a saved one, or save this layout as one (the "saveTemplate" dialog). */
import { useEffect, useMemo, useState } from "react";
import { getChart } from "../actions";
import { MM_PER_IN } from "../design/grid";
import { defaultFormat } from "../design/machine";
import { isText, type Chart, type ChartSummary, type TextItem } from "../design/types";
import { registerDialog } from "../dialogs";
import {
  bindOf,
  columnFor,
  endPreview,
  exportList,
  listProblem,
  listTemplates,
  loadList,
  openTemplate,
  saveTemplateAs,
  setBind,
  setFitWidth,
  setPlaceholder,
  showRow,
  snippet,
  SPECIAL_COLUMNS,
  textTargets,
  typedList,
  type NameList,
  type Template,
} from "../feat/names";
import { pickFolder } from "../features";
import { selectLayout, selectMachine, useStore } from "../store";
import { NumberField } from "./controls";
import { useModal } from "./ThreadDialogs";

const PREVIEW_ROWS = 5;

/** The chart color numbers are most likely from: your spools, else an imported chart. */
const firstChart = (charts: ChartSummary[]) =>
  (charts.find((c) => c.mine && c.count > 0) ?? charts.find((c) => !c.builtin && !c.mine) ?? charts.find((c) => c.builtin) ?? null)?.id ?? null;

/** One lettering: whether the list fills it, from which column, and shrinking long names. */
function FillChoice({ item, on, only, list }: { item: TextItem; on: boolean; only: boolean; list: NameList }) {
  const units = useStore((s) => s.units);
  const options = list.columns.filter((c) => !SPECIAL_COLUMNS.includes(c));
  const found = columnFor(list, bindOf(item));
  const chosen = found >= 0 ? list.columns[found] : bindOf(item);
  const toUnits = (mm: number) => (units === "in" ? mm / MM_PER_IN : mm);
  return (
    <div role="group" aria-label={`Lettering “${snippet(item)}”`}>
      <label className="check">
        <input
          type="checkbox"
          checked={on}
          disabled={on && only}
          title={on && only ? "At least one lettering is filled" : undefined}
          onChange={(e) => void setPlaceholder(item.id, e.target.checked, list.columns)}
        />
        Fill “{snippet(item)}” from the list
      </label>
      {on && (
        <div className="row" style={{ marginLeft: "2rem", flexWrap: "wrap", marginBottom: "0.5rem" }}>
          <label>
            Column{" "}
            <select value={chosen} onChange={(e) => void setBind(item.id, e.target.value)}>
              {!options.includes(chosen) && <option value={chosen}>{chosen} (not in this list)</option>}
              {options.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="check" title="A name wider than this is made smaller, letters and spacing together">
            <input type="checkbox" checked={!!item.fit_width_mm} onChange={(e) => void setFitWidth(item.id, e.target.checked)} />
            Shrink long names to fit
          </label>
          {!!item.fit_width_mm && (
            <NumberField
              label="Widest"
              value={toUnits(item.fit_width_mm)}
              suffix={units}
              step={units === "in" ? 0.1 : 1}
              digits={units === "in" ? 2 : 0}
              onCommit={(v) => v > 0 && void setFitWidth(item.id, Math.round((units === "in" ? v * MM_PER_IN : v) * 10) / 10)}
            />
          )}
        </div>
      )}
    </div>
  );
}

/** One machine file per name: the filled lettering with each row of the list in turn. */
export function NamesDialog() {
  const open = useStore((s) => s.dialog === "names");
  const setDialog = useStore((s) => s.setDialog);
  const machine = useStore(selectMachine);
  const formats = useStore((s) => s.formats);
  const layout = useStore(selectLayout);
  const selectedId = useStore((s) => s.selectedId);
  const charts = useStore((s) => s.charts);
  const ref = useModal(open);
  const [names, setNames] = useState("");
  const [loaded, setLoaded] = useState<(NameList & { file: string }) | null>(null);
  const [ext, setExt] = useState(() => defaultFormat(machine));
  const [chartId, setChartId] = useState<string | null>(null);
  const [chart, setChart] = useState<Chart | null>(null);
  const [row, setRow] = useState<number | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const list = useMemo(() => loaded ?? typedList(names), [loaded, names]);
  const colored = list.columns.includes("color");
  const count = list.rows.length;

  // Your machine's format each time it opens (the machine may have changed since).
  useEffect(() => {
    if (open) setExt(defaultFormat(machine));
  }, [open, machine]);
  useEffect(() => {
    if (!open) return;
    setRow(null);
    setError(null);
    if (!useStore.getState().engine) return;
    listTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, [open]);
  const wanted = chartId && charts.some((c) => c.id === chartId) ? chartId : firstChart(charts);
  useEffect(() => {
    if (!open || !colored || !wanted) return setChart(null);
    let stale = false;
    getChart(wanted)
      .then((c) => !stale && setChart(c))
      .catch(() => !stale && setChart(null));
    return () => {
      stale = true;
    };
  }, [open, colored, wanted]);
  // The preview follows the row, the list and the design; closing puts the design back.
  useEffect(() => {
    if (!open || row === null || !count) {
      endPreview();
      setNotes([]);
      return;
    }
    let stale = false;
    void showRow(list, Math.min(row, count - 1), chart).then((n) => {
      if (!stale && n) setNotes(n);
    });
    return () => {
      stale = true;
    };
  }, [open, row, count, list, chart, layout]);
  useEffect(() => endPreview, []);

  const close = () => {
    endPreview();
    setRow(null);
    // Only its own closing: switching to another dialog mustn't close that one.
    if (useStore.getState().dialog === "names") setDialog(null);
  };
  const letterings = (layout?.items.filter(isText) ?? []) as TextItem[];
  const targets = layout ? textTargets(layout, selectedId) : [];
  const problem = count ? listProblem(list, targets) : null;
  const shown = row === null ? null : Math.min(row, count - 1);
  const choose = async () => {
    setError(null);
    try {
      const picked = await loadList();
      if (picked) {
        setLoaded(picked);
        setRow(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="names-title" style={shown === null ? undefined : { marginRight: "1rem" }}>
      <h2 id="names-title">One file per name</h2>
      <p className="hint">
        The lettering is filled with each name in turn, and each is saved as its own machine file (Emma.pes, Jack.pes…), with the rest of the
        design as it is.
      </p>
      {templates.length > 0 && (
        <label className="field">
          Start from a template
          <select
            value=""
            onChange={(e) => {
              if (!e.target.value) return;
              setRow(null);
              void openTemplate(e.target.value);
            }}
          >
            <option value="">Choose a saved template…</option>
            {templates.map((t) => (
              <option key={t.path} value={t.path}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {loaded ? (
        <div className="result">
          <p>
            <b>{loaded.file}</b>: {count} row{count === 1 ? "" : "s"}. Columns: {loaded.columns.join(", ")}.
          </p>
          {loaded.skipped > 0 && (
            <p>
              Only the first {count.toLocaleString()} rows are used: {loaded.skipped.toLocaleString()} more are left out.
            </p>
          )}
          <ul aria-label="The first rows">
            {loaded.rows.slice(0, PREVIEW_ROWS).map((r, i) => (
              <li key={i}>{r.filter(Boolean).join(" · ")}</li>
            ))}
            {count > PREVIEW_ROWS && <li>…</li>}
          </ul>
          <button className="link" onClick={() => setLoaded(null)}>
            Type names instead
          </button>
        </div>
      ) : (
        <label className="field">
          Names, one per line
          <textarea rows={6} value={names} onChange={(e) => setNames(e.target.value)} placeholder={"Emma\nJack\nOlivia"} />
        </label>
      )}
      <div className="row" style={{ marginBottom: "0.75rem" }}>
        <button onClick={() => void choose()} title="A CSV or text file: one name per line, or columns such as name, number, color and file">
          Load a list…
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      <h3>Lettering to fill</h3>
      {letterings.map((t) => (
        <FillChoice key={t.id} item={t} list={list} on={targets.some((x) => x.id === t.id)} only={targets.length === 1} />
      ))}
      {!targets.length && <p className="hint">Tick the lettering to fill.</p>}
      {problem && <p className="error">{problem}</p>}
      {colored && charts.length > 0 && (
        <label className="field">
          Thread numbers in the color column are from
          <select value={wanted ?? ""} onChange={(e) => setChartId(e.target.value)}>
            {charts
              .filter((c) => !c.mine || c.count > 0)
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.mine ? "My threads" : c.name}
                </option>
              ))}
          </select>
        </label>
      )}

      <div className="row" style={{ margin: "0.75rem 0" }}>
        <span>Preview on the design</span>
        <button aria-label="Previous name" disabled={shown === null || shown === 0} onClick={() => setRow(Math.max(0, (shown ?? 0) - 1))}>
          ◀
        </button>
        <span aria-live="polite">{shown === null ? "off" : `${shown + 1} of ${count}`}</span>
        <button
          aria-label="Next name"
          disabled={!count || !!problem || (shown !== null && shown >= count - 1)}
          onClick={() => setRow(shown === null ? 0 : shown + 1)}
        >
          ▶
        </button>
        {shown !== null && (
          <button className="link" onClick={() => setRow(null)}>
            Stop previewing
          </button>
        )}
      </div>
      {shown !== null && <p className="hint">Showing row {shown + 1} on the design, without changing it. Drag this window by its title to see more.</p>}
      {notes.map((n) => (
        <p key={n} className="hint" role="status">
          {n}
        </p>
      ))}

      <label className="field">
        File type
        <select value={ext} onChange={(e) => setExt(e.target.value)}>
          {(formats?.write ?? [{ ext: "pes", description: "Brother" }]).map((f) => (
            <option key={f.ext} value={f.ext}>
              {f.ext.toUpperCase()} {f.description ? `– ${f.description}` : ""}
            </option>
          ))}
        </select>
      </label>
      <p className="hint">
        <button
          className="link"
          disabled={!letterings.length}
          onClick={() => {
            endPreview();
            setRow(null);
            setDialog("saveTemplate");
          }}
        >
          Save this layout as a name template…
        </button>
      </p>
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button
          className="primary"
          disabled={!count || !targets.length || !!problem}
          onClick={async () => {
            const folder = await pickFolder("Save the files in…");
            if (!folder) return;
            const from = colored && wanted ? await getChart(wanted).catch(() => null) : null;
            close();
            await exportList(list, folder, ext, from);
          }}
        >
          Save {count || ""} file{count === 1 ? "" : "s"}…
        </button>
      </div>
    </dialog>
  );
}

/** "Save this layout as a name template…": its name, then into LUDD's data folder. */
function SaveTemplateDialog() {
  const ref = useModal(true);
  const layout = useStore(selectLayout);
  const [name, setName] = useState(() => layout?.title || "Name template");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (useStore.getState().engine) listTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, []);
  const close = () => {
    if (useStore.getState().dialog === "saveTemplate") useStore.getState().setDialog(null);
  };
  const replacing = templates.some((t) => t.name.toLowerCase() === name.trim().toLowerCase());
  const marked = !!layout?.items.some((it) => isText(it) && it.placeholder);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="template-title">
      <h2 id="template-title">Save as a name template</h2>
      <p className="hint">Keeps this whole design, to start from later in One file per name (“Start from a template”).</p>
      {!marked && (
        <p className="hint">No lettering is marked to be filled yet. If more than one should take names, tick it in One file per name first.</p>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!name.trim() || saving) return;
          setSaving(true);
          const problem = await saveTemplateAs(name.trim(), replacing);
          setSaving(false);
          if (problem) setError(problem);
          else close();
        }}
      >
        <label className="field">
          Template name
          <input
            autoFocus
            value={name}
            maxLength={80}
            onChange={(e) => {
              setName(e.target.value);
              setError(null);
            }}
          />
        </label>
        {replacing && <p className="hint">A template with this name exists: saving replaces it.</p>}
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" onClick={close}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!name.trim() || saving}>
            {replacing ? "Replace" : "Save"}
          </button>
        </div>
      </form>
    </dialog>
  );
}

registerDialog("saveTemplate", SaveTemplateDialog);
