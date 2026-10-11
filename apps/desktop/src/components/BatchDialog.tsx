import { useEffect, useRef, useState } from "react";
import { basename, convertFolder, pickFolder, sortFormats } from "../actions";
import { DEFAULT_CUT_STOPS, defaultFormat } from "../design/machine";
import type { ConvertResult } from "../design/types";
import { selectMachine, useStore } from "../store";

const join = (dir: string, name: string) => `${dir.replace(/[\\/]+$/, "")}${dir.includes("\\") ? "\\" : "/"}${name}`;

export function BatchDialog() {
  const open = useStore((s) => s.batchOpen);
  const formats = useStore((s) => s.formats);
  const setOpen = useStore((s) => s.setBatchOpen);
  const machine = useStore(selectMachine);
  const ref = useRef<HTMLDialogElement>(null);

  const [src, setSrc] = useState("");
  const [dest, setDest] = useState("");
  const [destTouched, setDestTouched] = useState(false);
  const [ext, setExt] = useState("pes");
  const [recursive, setRecursive] = useState(false);
  const [cutStops, setCutStops] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ConvertResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current!;
    if (open && !d.open) {
      setResult(null);
      setError(null);
      setExt(defaultFormat(machine));
      setCutStops(machine?.cuts === "color_change");
      d.showModal();
    } else if (!open && d.open) d.close();
  }, [open, machine]);

  const chooseSrc = async () => {
    const dir = await pickFolder("Folder of designs to convert");
    if (!dir) return;
    setSrc(dir);
    if (!destTouched) setDest(join(dir, "converted"));
  };
  const chooseDest = async () => {
    const dir = await pickFolder("Save converted designs to");
    if (dir) {
      setDest(dir);
      setDestTouched(true);
    }
  };
  const run = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const options = machine
        ? { machine: machine.id, cut_stops: { ...DEFAULT_CUT_STOPS, enabled: cutStops } }
        : null;
      setResult(await convertFolder(src, dest, ext, recursive, options));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const writable = sortFormats(formats?.write ?? [{ ext: "pes", description: "" }, { ext: "jef", description: "" }]);

  return (
    <dialog ref={ref} className="modal batch" onClose={() => setOpen(false)} onCancel={(e) => busy && e.preventDefault()}>
      <h2>Batch convert</h2>
      <p className="hint">Converts every design in a folder. Originals are never changed or overwritten.</p>
      <label>
        From folder
        <div className="row">
          <input value={src} readOnly placeholder="Choose a folder…" />
          <button onClick={chooseSrc} disabled={busy}>
            Browse
          </button>
        </div>
      </label>
      <label>
        To folder
        <div className="row">
          <input value={dest} readOnly placeholder="Choose a folder…" />
          <button onClick={chooseDest} disabled={busy}>
            Browse
          </button>
        </div>
      </label>
      <div className="row">
        <label>
          Format{" "}
          <select value={ext} onChange={(e) => setExt(e.target.value)} disabled={busy}>
            {writable.map((f) => (
              <option key={f.ext} value={f.ext}>
                {f.ext.toUpperCase()}
                {f.description ? ` – ${f.description}` : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={recursive} onChange={(e) => setRecursive(e.target.checked)} disabled={busy} />
          Include subfolders
        </label>
      </div>
      {machine?.cuts === "color_change" && (
        <label className="check">
          <input type="checkbox" checked={cutStops} onChange={(e) => setCutStops(e.target.checked)} disabled={busy} />
          Cut jump threads with stops for the {machine.name} (trims over {DEFAULT_CUT_STOPS.min_jump_mm} mm)
        </label>
      )}

      {error && <p className="error">{error}</p>}
      {result && (
        <div className="result">
          <p>
            <strong>{result.converted.length}</strong> converted
            {result.failed.length > 0 && (
              <>
                , <strong>{result.failed.length}</strong> failed
              </>
            )}
            {result.skipped.length > 0 && <>, {result.skipped.length} other files skipped</>}.
          </p>
          {result.failed.length > 0 && (
            <ul>
              {result.failed.map((f) => (
                <li key={f.src}>
                  {basename(f.src)}: {f.error}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="actions">
        <button onClick={() => setOpen(false)} disabled={busy}>
          Close
        </button>
        <button className="primary" onClick={run} disabled={busy || !src || !dest}>
          {busy ? "Converting…" : "Convert"}
        </button>
      </div>
    </dialog>
  );
}
