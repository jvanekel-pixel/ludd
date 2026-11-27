/** "Add a buttonhole" and "Add an eyelet": a few sizes, kept from last time. The engine makes
 *  ordinary shapes from them (feat/smallObjects.ts); if it refuses a size it says why here, and the
 *  dialog stays open to fix it. */
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from "react";
import { holdEscape, letGoNewest } from "../escape";
import { addSmallObject, BUTTONHOLE, EYELET, lastSizes, type ButtonholeSizes, type EyeletSizes, type SmallDialog } from "../feat/smallObjects";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

/** A number to ask for, with the engine's limits (the arrows keep to them; typed numbers outside
 *  them are refused by the engine, which says the range). */
type NumberBox = { key: string; label: string; min: number; max: number; step: number; note?: string };

const SIZES: Record<SmallDialog, NumberBox[]> = {
  buttonhole: [
    { key: "length_mm", label: "Length", min: 8, max: 40, step: 0.5 },
    { key: "width_mm", label: "Width", min: 3, max: 8, step: 0.5 },
  ],
  eyelet: [
    { key: "hole_mm", label: "Hole", min: 2, max: 12, step: 0.5 },
    { key: "ring_mm", label: "Ring", min: 1, max: 3, step: 0.1 },
  ],
};
const MORE: NumberBox[] = [
  { key: "cut_gap_mm", label: "Cut gap", min: 0.6, max: 2, step: 0.1 },
  { key: "angle_deg", label: "Angle", min: -180, max: 180, step: 15, note: "degrees: 0 lies level" },
];
const STYLES = [
  { id: "bar", label: "Bar tacks", title: "Two satin sides with a bar tack across each end" },
  { id: "round", label: "Rounded ends", title: "One satin ribbon round a slot with round ends" },
];
const TITLES: Record<SmallDialog, string> = { buttonhole: "Add a buttonhole", eyelet: "Add an eyelet" };

function SmallObjectDialog({ kind }: { kind: SmallDialog }) {
  const ref = useModal(true);
  const first = useRef<HTMLInputElement>(null);
  const shown = useRef(true);
  const [start] = useState((): Record<string, number | string> => (kind === "buttonhole" ? lastSizes(kind, BUTTONHOLE) : lastSizes(kind, EYELET)));
  const [style, setStyle] = useState(start.style === "round" ? "round" : "bar");
  const boxes = kind === "buttonhole" ? [...SIZES.buttonhole, ...MORE] : SIZES.eyelet;
  const [text, setText] = useState<Record<string, string>>(() => Object.fromEntries(boxes.map((b) => [b.key, String(start[b.key])])));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Esc closes it through the app's one list of things Esc lets go of.
  useEffect(() => holdEscape(close), []);
  // The first number is selected, ready to be typed over.
  useEffect(() => {
    first.current?.focus();
    first.current?.select();
  }, []);
  useEffect(() => {
    shown.current = true;
    return () => void (shown.current = false);
  }, []);

  /** A box's number; an empty box means the number it started with. */
  const value = (key: string) => (text[key].trim() ? Number(text[key]) : (start[key] as number));
  /** A change puts away what was refused: it was about the numbers before. */
  const change = (patch: () => void) => {
    patch();
    setError(null);
  };

  const add = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    const sizes =
      kind === "buttonhole"
        ? ({ style, length_mm: value("length_mm"), width_mm: value("width_mm"), cut_gap_mm: value("cut_gap_mm"), angle_deg: value("angle_deg") } as ButtonholeSizes)
        : ({ hole_mm: value("hole_mm"), ring_mm: value("ring_mm") } as EyeletSizes);
    try {
      await addSmallObject(kind, sizes, () => shown.current);
      if (shown.current) close();
    } catch (err) {
      if (!shown.current) return;
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  // The app's keyboard handler leaves open dialogs alone, so Esc and Enter are handled here, and
  // go no further, so nothing else acts on them as well.
  const onKeyDown = (e: KeyboardEvent) => {
    const esc = e.key === "Escape";
    // On a button, or the More options heading, Enter presses it (the browser's own click).
    if (!esc && (e.key !== "Enter" || e.target instanceof HTMLButtonElement || (e.target as HTMLElement).tagName === "SUMMARY")) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.repeat) return;
    if (esc) letGoNewest();
    else void add();
  };

  const field = (b: NumberBox, at?: RefObject<HTMLInputElement | null>) => (
    <label className="field" key={b.key}>
      {b.label}
      <span className="row">
        <input ref={at} type="number" min={b.min} max={b.max} step={b.step} value={text[b.key]} onChange={(e) => change(() => setText((t) => ({ ...t, [b.key]: e.target.value })))} />
        <small>{b.note ?? `${b.min} to ${b.max} mm`}</small>
      </span>
    </label>
  );

  /** The slit must be as long as the button's width and thickness together. A bar buttonhole's slit
   *  is its length less the two 1.5 mm tacks; a rounded one's, less its width less the cut gap. */
  const lengthTip = () => {
    const spare = value("width_mm") - value("cut_gap_mm");
    const extra = style === "bar" ? 3 : spare > 0 ? Math.round(spare * 10) / 10 : 4;
    return `Length = the button's width + its thickness + ${extra} mm`;
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} onKeyDown={onKeyDown} aria-labelledby="small-object-title">
      <h2 id="small-object-title">{TITLES[kind]}</h2>
      {kind === "buttonhole" && (
        <div className="field">
          Style
          <div className="seg" role="group" aria-label="Buttonhole style">
            {STYLES.map((s) => (
              <button key={s.id} type="button" aria-pressed={style === s.id} onClick={() => change(() => setStyle(s.id))} title={s.title}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {SIZES[kind].map((b, i) => field(b, i === 0 ? first : undefined))}
      <p className="hint">{kind === "buttonhole" ? lengthTip() : "After sewing, punch or cut out the hole inside the ring."}</p>
      {kind === "buttonhole" && (
        <details>
          <summary>More options</summary>
          {MORE.map((b) => field(b))}
        </details>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button className="primary" disabled={busy} onClick={() => void add()}>
          Add
        </button>
      </div>
    </dialog>
  );
}

export const ButtonholeDialog = () => <SmallObjectDialog kind="buttonhole" />;
export const EyeletDialog = () => <SmallObjectDialog kind="eyelet" />;
