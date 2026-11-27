/** The Motifs window (Alt+Shift+M): your own motifs and the built-in ones, each drawn as two
 *  repeats. Save the selected line as a motif; import, export and delete yours. */
import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { holdEscape, letGoNewest } from "../escape";
import { deleteMotif, exportMotif, importMotif, loadMotifs, saveLineMotif, selectedLine, useMotifs, type MotifEntry } from "../feat/motifs";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

/** A new line's motif is 2.5 mm wide for each 4 mm repeat: built-ins are drawn that way. */
const BUILTIN_ACROSS = 2.5 / 4;

/** Two repeats of a motif as it sews: yours as you drew it, up the screen up. */
export function MotifPreview({ motif }: { motif: MotifEntry }) {
  const across = motif.builtin ? BUILTIN_ACROSS : 1;
  const points = [0, 1].flatMap((k) => motif.unit.map(([u, v]) => [k + u, v * across] as const));
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const [x0, x1] = [Math.min(0, ...xs), Math.max(2, ...xs)];
  const middle = (Math.min(...ys) + Math.max(...ys)) / 2;
  const tall = Math.max(Math.max(...ys) - Math.min(...ys), 0.5); // a flat one still has room to show
  return (
    <svg viewBox={`${x0 - 0.05} ${middle - tall / 2 - 0.05} ${x1 - x0 + 0.1} ${tall + 0.1}`} width="100%" height="32" aria-hidden>
      <polyline points={points.map((p) => p.join(",")).join(" ")} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const grid: CSSProperties = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "0.4rem" };
const card: CSSProperties = { display: "flex", flexDirection: "column", alignItems: "center", gap: "0.2rem", padding: "0.4rem", fontSize: 12, minWidth: 0 };

function MotifList({ title, motifs, picked, onPick }: { title: string; motifs: MotifEntry[]; picked: string | null; onPick: (id: string) => void }) {
  return (
    <div role="group" aria-label={title} style={grid}>
      {motifs.map((m) => (
        <button key={m.id} type="button" aria-pressed={picked === m.id} onClick={() => onPick(m.id)} style={card}>
          <MotifPreview motif={m} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%" }}>{m.name}</span>
        </button>
      ))}
    </div>
  );
}

type Said = { text: string; error?: boolean };

export function MotifDialog() {
  const ref = useModal(true);
  const list = useMotifs((s) => s.list);
  const line = useStore((s) => selectedLine(s));
  const connected = useStore((s) => s.engine !== null);
  const [picked, setPicked] = useState<string | null>(null);
  const [naming, setNaming] = useState<string | null>(null); // the new motif's name, as it's typed
  const [asking, setAsking] = useState<MotifEntry | null>(null); // the motif to delete, once you say so
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

  // Esc closes it through the app's one list of things Esc lets go of; typing a name and the
  // delete question come off first, as the newest things held.
  useEffect(() => holdEscape(close), []);
  const isNaming = naming !== null;
  useEffect(() => (isNaming ? holdEscape(() => setNaming(null)) : undefined), [isNaming]);
  useEffect(() => (asking ? holdEscape(() => setAsking(null)) : undefined), [asking]);
  useEffect(() => {
    void attempt(async () => {
      await loadMotifs();
      return null;
    });
    // Once, as the window opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // The name is selected, ready to be typed over.
  useEffect(() => {
    if (isNaming) {
      nameBox.current?.focus();
      nameBox.current?.select();
    }
  }, [isNaming]);

  const mine = list?.filter((m) => !m.builtin) ?? [];
  const builtins = list?.filter((m) => m.builtin) ?? [];
  const chosen = list?.find((m) => m.id === picked) ?? null;

  const save = () =>
    attempt(async () => {
      if (!line || naming === null) return null;
      const saved = await saveLineMotif(line, naming);
      setNaming(null);
      setPicked(saved.id);
      return { text: `Saved “${saved.name}” to My motifs. Choose it under Motif for a motif line or a motif fill.` };
    });

  const bringIn = () =>
    attempt(async () => {
      const added = await importMotif();
      if (!added) return null;
      setPicked(added.id);
      return { text: `Added “${added.name}” to My motifs.` };
    });

  const sendOut = (motif: MotifEntry) =>
    attempt(async () => {
      const path = await exportMotif(motif);
      return path ? { text: `Saved “${motif.name}” as ${path}.` } : null;
    });

  const remove = (motif: MotifEntry) =>
    attempt(async () => {
      await deleteMotif(motif.id);
      setAsking(null);
      setPicked(null);
      return { text: `Deleted “${motif.name}”. Shapes that use it keep their own copy.` };
    });

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
    else if (isNaming) void save();
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} onKeyDown={onKeyDown} aria-labelledby="motifs-title">
      <h2 id="motifs-title">Motifs</h2>
      <p className="hint">A motif is a small shape repeated along a line, or in rows across a motif fill. A shape that uses one of yours keeps its own copy, so it sews the same on any computer.</p>
      <div style={{ maxHeight: "45vh", overflowY: "auto", marginBottom: "0.75rem" }}>
        <h3>My motifs</h3>
        {mine.length > 0 ? (
          <MotifList title="My motifs" motifs={mine} picked={picked} onPick={setPicked} />
        ) : (
          <p className="hint">None yet. Draw one repeat as a line from left to right, select it, then save it here.</p>
        )}
        <h3>Built in</h3>
        <MotifList title="Built in" motifs={builtins} picked={picked} onPick={setPicked} />
      </div>

      {isNaming ? (
        <>
          <label className="field">
            Name for the new motif
            <input ref={nameBox} type="text" maxLength={80} value={naming} onChange={(e) => setNaming(e.target.value)} />
          </label>
          <div className="actions" style={{ marginBottom: "0.75rem" }}>
            <button onClick={() => setNaming(null)}>Cancel</button>
            <button className="primary" onClick={() => void save()} disabled={busy}>
              Save motif
            </button>
          </div>
        </>
      ) : (
        <p>
          <button
            className="primary"
            onClick={() => setNaming(line?.name ?? "My motif")}
            disabled={!line || !connected || busy}
            title={line ? "Keep the selected line as one repeat of a motif" : "Close this window, select one line you drew from left to right, then open it again"}
          >
            Save the selected line as a motif…
          </button>
        </p>
      )}

      {asking && (
        <div className="result" role="alertdialog" aria-label="Delete the motif?">
          <p>
            Delete “{asking.name}” from My motifs? Shapes that use it keep their own copy.
          </p>
          <div className="actions">
            <button onClick={() => setAsking(null)}>Keep it</button>
            <button onClick={() => void remove(asking)} disabled={busy}>
              Delete motif
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
        <button onClick={() => void bringIn()} disabled={!connected || busy} title="Add a motif from a file">
          Import…
        </button>
        <button onClick={() => chosen && void sendOut(chosen)} disabled={!chosen || busy} title={chosen ? "Save this motif as a file to share" : "Choose a motif first"}>
          Export…
        </button>
        <button
          onClick={() => chosen && !chosen.builtin && setAsking(chosen)}
          disabled={!chosen || chosen.builtin || busy || !!asking}
          title={chosen?.builtin ? "The built-in motifs can't be deleted" : chosen ? "Delete this motif from My motifs" : "Choose one of your motifs first"}
        >
          Delete
        </button>
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
