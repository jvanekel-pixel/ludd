/** The Stitch presets window (Alt+P): the built-in presets and yours, for the selected shape's
 *  kind (every kind with nothing selected). Apply one to the selection, use one for new shapes,
 *  save the selected shape's settings as one, and import, export and delete yours. */
import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { holdEscape, letGoNewest } from "../escape";
import {
  applyPreset, currentShape, deletePreset, exportPreset, importPreset, KIND_PLURAL, loadPresets, savePreset, summary, targetsOf, usePresets,
  useForNewShapes, type Preset,
} from "../feat/presets";
import { isObject, type ObjectKind } from "../design/types";
import { selectedIds, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);
const ONE: Record<ObjectKind, string> = { run: "line", satin: "satin", fill: "fill", applique: "applique" };
const count = (n: number, kind: ObjectKind) => `${n} ${n === 1 ? ONE[kind] : KIND_PLURAL[kind]}`;

const list: CSSProperties = { display: "flex", flexDirection: "column", gap: "0.25rem", maxHeight: "38vh", overflowY: "auto", marginBottom: "0.5rem" };
const entry: CSSProperties = { display: "flex", flexDirection: "column", alignItems: "flex-start", textAlign: "left", padding: "0.3rem 0.5rem" };

type Said = { text: string; error?: boolean };
type Asking = { what: "delete" | "replace"; preset: Preset };

export function PresetsDialog() {
  const ref = useModal(true);
  const presets = usePresets((s) => s.list);
  const connected = useStore((s) => s.engine !== null);
  const shape = useStore((s) => currentShape(s));
  // The kind shown: the selected shape's, or every kind with no drawn shape selected.
  const kind = shape?.kind ?? null;
  useStore((s) => [selectedIds(s), s.history.present?.layout.items.filter(isObject).map((o) => o.kind)].join());
  const [picked, setPicked] = useState<string | null>(null);
  const [naming, setNaming] = useState<string | null>(null); // the new preset's name, as it's typed
  const [asking, setAsking] = useState<Asking | null>(null);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<Said | null>(null);
  const nameBox = useRef<HTMLInputElement>(null);

  const attempt = async (job: () => Promise<Said | null>) => {
    if (busy) return;
    setBusy(true);
    setSaid(null);
    try {
      setSaid(await job());
    } catch (err) {
      setSaid({ text: err instanceof Error ? err.message : String(err), error: true });
    } finally {
      setBusy(false);
    }
  };

  // Esc closes it through the app's one list of things Esc lets go of; typing a name and a
  // question come off first, as the newest things held.
  useEffect(() => holdEscape(close), []);
  const isNaming = naming !== null;
  useEffect(() => (isNaming ? holdEscape(() => setNaming(null)) : undefined), [isNaming]);
  useEffect(() => (asking ? holdEscape(() => setAsking(null)) : undefined), [asking]);
  useEffect(() => {
    void attempt(async () => {
      await loadPresets();
      return null;
    });
    // Once, as the window opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (isNaming) {
      nameBox.current?.focus();
      nameBox.current?.select();
    }
  }, [isNaming]);

  const shown = presets?.filter((p) => !kind || p.kind === kind) ?? [];
  const chosen = shown.find((p) => p.id === picked) ?? null;
  const targets = chosen ? targetsOf(chosen).length : 0;

  const apply = (preset: Preset) =>
    attempt(async () => {
      const n = await applyPreset(preset);
      return n ? { text: `Applied “${preset.name}” to ${count(n, preset.kind)}.` } : { text: `Select one or more ${KIND_PLURAL[preset.kind]} first.`, error: true };
    });

  const forNew = (preset: Preset) => {
    useForNewShapes(preset);
    setSaid({ text: `New ${KIND_PLURAL[preset.kind]} start with “${preset.name}”.` });
  };

  const save = (replacing = false) =>
    attempt(async () => {
      if (!shape || naming === null) return null;
      const name = naming.trim();
      if (!name) return { text: "Give the preset a name.", error: true };
      const same = presets?.find((p) => !p.builtin && p.kind === shape.kind && p.name.toLowerCase() === name.toLowerCase());
      if (same && !replacing) {
        setAsking({ what: "replace", preset: same });
        return null;
      }
      const id = await savePreset(shape, name, replacing);
      setNaming(null);
      setAsking(null);
      setPicked(id);
      return { text: `Saved “${name}” with your presets for ${KIND_PLURAL[shape.kind]}.` };
    });

  const remove = (preset: Preset) =>
    attempt(async () => {
      await deletePreset(preset.id);
      setAsking(null);
      setPicked(null);
      return { text: `Deleted “${preset.name}”. Shapes keep their settings.` };
    });

  const bringIn = () =>
    attempt(async () => {
      const added = await importPreset();
      if (!added) return null;
      setPicked(added.id);
      const elsewhere = kind && added.kind !== kind ? ` It's for ${KIND_PLURAL[added.kind]}: select one (or nothing) to see it.` : "";
      return { text: `Added “${added.name}” to your presets.${elsewhere}` };
    });

  const sendOut = (preset: Preset) =>
    attempt(async () => {
      const path = await exportPreset(preset);
      return path ? { text: `Saved “${preset.name}” as ${path}.` } : null;
    });

  // The app's keyboard handler leaves open dialogs alone, so Esc and Enter are handled here, and
  // go no further, so nothing else acts on them as well.
  const onKeyDown = (e: KeyboardEvent) => {
    const esc = e.key === "Escape";
    // On a button, Enter presses that button (the browser's own click).
    if (!esc && (e.key !== "Enter" || e.target instanceof HTMLButtonElement)) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.repeat) return;
    if (esc) letGoNewest();
    else if (isNaming && !asking) void save();
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} onKeyDown={onKeyDown} aria-labelledby="presets-title">
      <h2 id="presets-title">Stitch presets</h2>
      <p className="hint">
        A preset is a shape's stitch settings under a name. What belongs to one shape, like its stitch direction or where it starts, stays the shape's own.{" "}
        {kind ? `Showing presets for ${KIND_PLURAL[kind]}.` : "Showing every preset: select a shape to see just the ones for its kind."}
      </p>
      <div role="group" aria-label="Presets" style={list}>
        {shown.map((p) => (
          <button key={p.id} type="button" aria-pressed={picked === p.id} onClick={() => setPicked(p.id)} style={entry}>
            <span>{p.name}</span>
            <small>
              {summary(p)}
              {p.builtin ? " · built in" : ""}
            </small>
          </button>
        ))}
        {!shown.length && (
          <p className="hint">{presets ? `No presets for ${kind ? KIND_PLURAL[kind] : "shapes"} yet.` : connected ? "Reading your presets…" : "The stitch engine isn't connected."}</p>
        )}
      </div>
      {chosen?.note && <p className="hint">{chosen.note}</p>}
      <div className="actions" style={{ marginBottom: "0.75rem" }}>
        <button
          onClick={() => chosen && forNew(chosen)}
          disabled={!chosen || busy}
          title={chosen ? `New ${KIND_PLURAL[chosen.kind]} start with these settings` : "Choose a preset first"}
        >
          Use for new shapes
        </button>
        <button
          className="primary"
          onClick={() => chosen && void apply(chosen)}
          disabled={!chosen || !targets || busy}
          title={!chosen ? "Choose a preset first" : targets ? `Give ${count(targets, chosen.kind)} these settings` : `Select one or more ${KIND_PLURAL[chosen.kind]} first`}
        >
          Apply to selection
        </button>
      </div>

      {isNaming ? (
        <>
          <label className="field">
            Name for the preset
            <input
              ref={nameBox}
              type="text"
              maxLength={80}
              value={naming}
              onChange={(e) => {
                setNaming(e.target.value);
                setAsking(null);
              }}
            />
          </label>
          <div className="actions" style={{ marginBottom: "0.75rem" }}>
            <button onClick={() => setNaming(null)}>Cancel</button>
            <button className="primary" onClick={() => void save()} disabled={busy || !shape || !!asking}>
              Save preset
            </button>
          </div>
        </>
      ) : (
        <p>
          <button
            onClick={() => setNaming(shape?.name ?? (shape ? `My ${ONE[shape.kind]}` : ""))}
            disabled={!shape || !connected || busy}
            title={shape ? "Keep the selected shape's settings under a name" : "Close this window, select a shape set up the way you like, then open it again"}
          >
            Save current as…
          </button>
        </p>
      )}

      {asking && (
        <div className="result" role="alertdialog" aria-label={asking.what === "delete" ? "Delete the preset?" : "Replace the preset?"}>
          <p>
            {asking.what === "delete"
              ? `Delete “${asking.preset.name}” from your presets? This can't be undone. Shapes keep their settings.`
              : `You already have a preset called “${asking.preset.name}” for ${KIND_PLURAL[asking.preset.kind]}. Replace it?`}
          </p>
          <div className="actions">
            <button onClick={() => setAsking(null)}>Keep it</button>
            <button onClick={() => void (asking.what === "delete" ? remove(asking.preset) : save(true))} disabled={busy}>
              {asking.what === "delete" ? "Delete preset" : "Replace it"}
            </button>
          </div>
        </div>
      )}
      {said && (
        <p className={said.error ? "error" : "hint"} role={said.error ? "alert" : "status"}>
          {said.text}
        </p>
      )}

      <div className="actions">
        <button onClick={() => void bringIn()} disabled={!connected || busy} title="Add a preset from a .luddpreset file">
          Import…
        </button>
        <button onClick={() => chosen && void sendOut(chosen)} disabled={!chosen || busy} title={chosen ? "Save this preset as a file to share" : "Choose a preset first"}>
          Export…
        </button>
        <button
          onClick={() => chosen && !chosen.builtin && setAsking({ what: "delete", preset: chosen })}
          disabled={!chosen || chosen.builtin || busy || !!asking}
          title={chosen?.builtin ? "The built-in presets can't be deleted" : chosen ? "Delete this preset" : "Choose one of your presets first"}
        >
          Delete
        </button>
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
