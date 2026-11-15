import { useEffect, useMemo, useRef, useState } from "react";
import { addDesign, openDesign } from "../actions";
import { defaultFormat } from "../design/machine";
import { MM_PER_IN } from "../design/grid";
import { addOffset, exportNames, pickFolder, type OffsetSpec } from "../features";
import { engine as engineCall } from "../actions";
import { loadPrefs, savePrefs } from "../prefs";
import { selectMachine, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

/** Outlines & offsets: a ring around the selection, a set distance out. */
export function OffsetDialog() {
  const open = useStore((s) => s.dialog === "offset");
  const setDialog = useStore((s) => s.setDialog);
  const units = useStore((s) => s.units);
  const satinWidth = useStore((s) => s.satinWidth);
  const ref = useModal(open);
  const [spec, setSpec] = useState<OffsetSpec>({ distance_mm: 2, as: "satin", width_mm: satinWidth, holes: false });
  const k = units === "in" ? MM_PER_IN : 1;
  const close = () => setDialog(null);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="offset-title">
      <h2 id="offset-title">Outline / offset</h2>
      <p className="hint">A ring around what's selected, following its stitches: a border round lettering, a patch edge, an outline for a design.</p>
      <label className="field">
        Distance out from the stitches
        <span className="row">
          <input type="number" step={units === "in" ? 0.02 : 0.5} value={Number((spec.distance_mm / k).toFixed(2))} onChange={(e) => setSpec({ ...spec, distance_mm: Number(e.target.value) * k })} />
          <small>{units}</small>
        </span>
      </label>
      <div className="seg" role="radiogroup" aria-label="Sew it as">
        {(
          [
            ["satin", "Satin border"],
            ["run", "Line"],
            ["triple", "Triple line"],
          ] as const
        ).map(([id, label]) => (
          <button key={id} role="radio" aria-checked={spec.as === id} aria-pressed={spec.as === id} onClick={() => setSpec({ ...spec, as: id })}>
            {label}
          </button>
        ))}
      </div>
      {spec.as === "satin" && (
        <label className="field">
          Satin width
          <span className="row">
            <input type="number" step={0.25} min={0.5} max={12} value={spec.width_mm} onChange={(e) => setSpec({ ...spec, width_mm: Number(e.target.value) })} />
            <small>mm</small>
          </span>
        </label>
      )}
      <label className="check">
        <input type="checkbox" checked={spec.holes} onChange={(e) => setSpec({ ...spec, holes: e.target.checked })} /> Also around the inside of holes (the middle of an O)
      </label>
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button
          className="primary"
          onClick={() => {
            close();
            void addOffset(spec);
          }}
        >
          Add outline
        </button>
      </div>
    </dialog>
  );
}

type Entry = { path: string; name: string; format: string; ok: boolean; error?: string; width_mm?: number; height_mm?: number; stitches?: number; colors?: number; thumb?: string };

/** Design browser: every design in a folder as a picture, to open or add. */
export function BrowseDialog() {
  const open = useStore((s) => s.dialog === "browse");
  const setDialog = useStore((s) => s.setDialog);
  const units = useStore((s) => s.units);
  const hasDoc = useStore((s) => !!s.history.present);
  const ref = useModal(open);
  const [folder, setFolder] = useState<string>(() => loadPrefs().browseFolder ?? "");
  const [query, setQuery] = useState("");
  const [designs, setDesigns] = useState<Entry[] | null>(null);
  // A folder with more designs than one look shows: a name typed in searches the whole folder again.
  const [more, setMore] = useState(false);
  const [found, setFound] = useState<{ query: string; designs: Entry[]; more: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const close = () => setDialog(null);

  // Only the newest folder's answer counts: a slow earlier folder can't replace it.
  const scanSeq = useRef(0);
  const scan = async (dir: string) => {
    if (!dir) return;
    const my = ++scanSeq.current;
    setBusy(true);
    setErr(null);
    setFound(null);
    try {
      const r = await engineCall().call<{ designs: Entry[]; more: boolean }>("library.scan", { folder: dir, recursive: true }, 300_000);
      if (my !== scanSeq.current) return;
      setDesigns(r.designs);
      setMore(r.more);
      if (r.more) setErr("Showing the newest 600; type part of a name to find older ones.");
      savePrefs({ browseFolder: dir });
    } catch (e) {
      if (my !== scanSeq.current) return;
      setErr(e instanceof Error ? e.message : String(e));
      setDesigns(null);
    } finally {
      if (my === scanSeq.current) setBusy(false);
    }
  };
  useEffect(() => {
    if (!open) return;
    // The last folder you browsed (it may have been set since this dialog was first shown).
    const dir = folder || loadPrefs().browseFolder || "";
    if (dir && dir !== folder) setFolder(dir);
    if (dir && !designs) void scan(dir);
    // Only when opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Typing a name in a big folder: look through the whole folder for it (a moment after typing stops).
  const findSeq = useRef(0);
  useEffect(() => {
    const q = query.trim();
    if (!open || !more || !q || !folder) return;
    const my = ++findSeq.current;
    const timer = setTimeout(() => {
      setBusy(true);
      void engineCall()
        .call<{ designs: Entry[]; more: boolean }>("library.scan", { folder, recursive: true, query: q }, 300_000)
        .then((r) => my === findSeq.current && setFound({ query: q, designs: r.designs, more: r.more }))
        .catch((e) => my === findSeq.current && setErr(e instanceof Error ? e.message : String(e)))
        .finally(() => my === findSeq.current && setBusy(false));
    }, 400);
    return () => clearTimeout(timer);
  }, [open, more, query, folder]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    // The folder-wide search for this name, once it's back; until then, the matches already shown.
    const list = found && found.query.toLowerCase() === q ? found.designs : (designs ?? []);
    return list.filter((d) => !q || d.name.toLowerCase().includes(q));
  }, [designs, found, query]);
  const size = (d: Entry) => {
    if (!d.width_mm || !d.height_mm) return "";
    const k = units === "in" ? MM_PER_IN : 1;
    return `${(d.width_mm / k).toFixed(units === "in" ? 2 : 0)} × ${(d.height_mm / k).toFixed(units === "in" ? 2 : 0)} ${units}`;
  };

  return (
    <dialog ref={ref} className="modal browse" onClose={close} aria-labelledby="browse-title">
      <h2 id="browse-title">Browse designs</h2>
      <div className="browse-bar">
        <button
          onClick={async () => {
            const dir = await pickFolder("Choose a folder of designs");
            if (dir) {
              setFolder(dir);
              setDesigns(null);
              void scan(dir);
            }
          }}
        >
          Choose folder…
        </button>
        <span className="browse-folder" title={folder}>
          {folder || "No folder chosen yet"}
        </span>
        <button disabled={!folder || busy} onClick={() => void scan(folder)} title="Look through the folder again (new, changed or removed designs)">
          Refresh
        </button>
        <input placeholder="Find by name" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Find by name" />
      </div>
      {busy && <p className="hint">Looking through the folder… (the first time, each design is read once)</p>}
      {found && found.query.toLowerCase() === query.trim().toLowerCase() ? (
        found.more && <p className="hint">Showing the newest 600 with that name; type more of it to find older ones.</p>
      ) : (
        err && <p className="hint">{err}</p>
      )}
      <ul className="browse-grid">
        {shown.map((d) => (
          <li key={d.path} className={d.ok ? undefined : "bad"} title={d.ok ? d.path : d.error}>
            <button
              className="browse-card"
              disabled={!d.ok}
              onClick={() => {
                close();
                void openDesign(d.path);
              }}
              onDoubleClick={() => undefined}
            >
              {d.thumb ? <img src={d.thumb} alt="" width={120} height={120} /> : <span className="browse-none">Can't read</span>}
              <span className="browse-name">{d.name}</span>
              <small>{d.ok ? `${size(d)} · ${d.stitches?.toLocaleString()} st · ${d.colors} colors` : d.error}</small>
            </button>
            {d.ok && hasDoc && (
              <button
                className="browse-add"
                title="Add to the design you have open"
                onClick={() => {
                  close();
                  void addDesign(d.path);
                }}
              >
                + Add
              </button>
            )}
          </li>
        ))}
      </ul>
      {designs && !shown.length && <p className="hint">No designs here{query ? " with that name" : ""}.</p>}
      <div className="actions">
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}

/** One machine file per name: the selected lettering with each name in turn. */
export function NamesDialog() {
  const open = useStore((s) => s.dialog === "names");
  const setDialog = useStore((s) => s.setDialog);
  const machine = useStore(selectMachine);
  const formats = useStore((s) => s.formats);
  const ref = useModal(open);
  const [names, setNames] = useState("");
  const [ext, setExt] = useState(() => defaultFormat(machine));
  // Your machine's format each time it opens (the machine may have changed since).
  useEffect(() => {
    if (open) setExt(defaultFormat(machine));
  }, [open, machine]);
  const close = () => setDialog(null);
  const list = names.split("\n").map((n) => n.trim()).filter(Boolean);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="names-title">
      <h2 id="names-title">One file per name</h2>
      <p className="hint">The selected lettering is changed to each name in turn, and each is saved as its own machine file (Emma.pes, Jack.pes…), with the rest of the design as it is.</p>
      <label className="field">
        Names, one per line
        <textarea rows={8} value={names} onChange={(e) => setNames(e.target.value)} placeholder={"Emma\nJack\nOlivia"} />
      </label>
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
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button
          className="primary"
          disabled={!list.length}
          onClick={async () => {
            const folder = await pickFolder("Save the files in…");
            if (!folder) return;
            close();
            await exportNames(list, folder, ext);
          }}
        >
          Save {list.length || ""} files…
        </button>
      </div>
    </dialog>
  );
}
