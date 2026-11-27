import { useEffect, useState } from "react";
import { repeatSelected } from "../actions";
import { repeatBoxes, showRepeatPreview } from "../canvas/repeatOverlay";
import { MM_PER_IN } from "../design/grid";
import { repeatPlaces, stitchesAfterRepeat, type RepeatSpec } from "../design/layout";
import { selectLayout, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

type Mode = "row" | "wreath" | "kaleidoscope" | "mirror";
type Center = "below" | "hoop";
type Mirrors = "x" | "y" | "both";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "row", label: "Row", hint: "Copies side by side, in a row or a grid." },
  { id: "wreath", label: "Wreath", hint: "Copies round a circle, like a wreath or a carousel." },
  { id: "kaleidoscope", label: "Kaleidoscope", hint: "A wreath with every other copy mirrored, so each one faces its neighbors, like a snowflake." },
  { id: "mirror", label: "Mirror", hint: "A mirror image beside the design or below it, or all four ways, like a quilt block." },
];
const MIRRORS: { id: Mirrors; label: string }[] = [
  { id: "x", label: "Left–right" },
  { id: "y", label: "Top–bottom" },
  { id: "both", label: "Both" },
];
/** Repeats that make more stitches than this get a warning, and more than the second are refused
 *  (the engine's own limits for a motif line and for one fill). */
export const WARN_STITCHES = 60_000;
export const REFUSE_STITCHES = 400_000;

/** A whole number typed in a box, kept within lo to hi (an empty box means lo). */
const whole = (text: string, lo: number, hi: number) => Math.min(hi, Math.max(lo, Math.round(Number(text)) || lo));

/** A whole-number box that lets you type freely and tidies the number when you leave it. */
function CountBox({ label, text, setText, lo, hi }: { label: string; text: string; setText: (t: string) => void; lo: number; hi: number }) {
  return (
    <label className="field">
      {label}
      <input type="number" min={lo} max={hi} value={text} onChange={(e) => setText(e.target.value)} onBlur={() => setText(String(whole(text, lo, hi)))} />
    </label>
  );
}

/** Repeat the selected design: a row or grid, a wreath, a kaleidoscope or a mirror image. */
export function RepeatDialog() {
  const open = useStore((s) => s.repeatOpen);
  const setOpen = useStore((s) => s.setRepeatOpen);
  const units = useStore((s) => s.units);
  const layout = useStore(selectLayout);
  const design = useStore((s) => s.design);
  const selectedId = useStore((s) => s.selectedId);
  const ref = useModal(open);
  const [mode, setMode] = useState<Mode>("row");
  const [acrossText, setAcross] = useState("3");
  const [rowsText, setRows] = useState("1");
  const [roundText, setRound] = useState("3");
  const [pairsText, setPairs] = useState("4");
  const [gap, setGap] = useState(5);
  const [radius, setRadius] = useState(30);
  const [turn, setTurn] = useState(true);
  const [center, setCenter] = useState<Center>("below");
  const [mirrors, setMirrors] = useState<Mirrors>("x");

  // The design being repeated, and its size (for spacing copies edge to edge).
  const index = layout ? (selectedId ? layout.items.findIndex((it) => it.id === selectedId) : layout.items.length === 1 ? 0 : -1) : -1;
  const b = index >= 0 ? design?.items?.[index]?.bounds_mm : undefined;
  const w = b ? b[2] - b[0] : 0;
  const h = b ? b[3] - b[1] : 0;
  const middle: [number, number] = b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : [0, 0];

  const around = center === "hoop" ? { center } : {};
  const spec: RepeatSpec =
    mode === "row"
      ? { kind: "row", columns: whole(acrossText, 1, 20), rows: whole(rowsText, 1, 20), step_x: w + gap, step_y: h + gap }
      : mode === "wreath"
        ? { kind: "circle", count: whole(roundText, 2, 36), radius, turn, ...around }
        : mode === "kaleidoscope"
          ? { kind: "circle", count: 2 * whole(pairsText, 2, 12), radius, turn: true, mirror: true, ...around }
          : mirrors === "both"
            ? { kind: "mirror4", gap }
            : { kind: "mirror2", axis: mirrors, gap };
  const total = repeatPlaces(middle, [w, h], spec).length + 1;
  const stitches = design && index >= 0 ? stitchesAfterRepeat(design, index, total - 1) : 0;
  const tooMany = stitches > REFUSE_STITCHES;
  const circle = mode === "wreath" || mode === "kaleidoscope";
  const fromMiddle = Math.hypot(...middle);

  // Where each copy will land, shown on the design while this window is open.
  const preview = JSON.stringify([open, b, spec]);
  useEffect(() => {
    showRepeatPreview(open && b ? repeatBoxes(b, spec) : null);
    // `preview` stands for the open window, the design's place and the pattern.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview]);
  useEffect(() => () => showRepeatPreview(null), []);

  const k = units === "in" ? MM_PER_IN : 1;
  const show = (mm: number) => Number((mm / k).toFixed(units === "in" ? 2 : 1));
  const num = (label: string, mm: number, setMm: (v: number) => void, suffix = units) => (
    <label className="field">
      {label}
      <span className="row">
        <input type="number" step={units === "in" ? 0.1 : 1} value={show(mm)} onChange={(e) => setMm(Number(e.target.value) * k)} />
        <small>{suffix}</small>
      </span>
    </label>
  );
  const choice = <T extends string>(label: string, options: { id: T; label: string }[], value: T, set: (v: T) => void) => (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} role="radio" aria-checked={value === o.id} aria-pressed={value === o.id} onClick={() => set(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );

  const apply = () => {
    repeatSelected(spec);
    setOpen(false);
  };

  return (
    // Docked at the right with nothing dimmed, so the boxes showing where copies land can be seen.
    <dialog ref={ref} className="modal repeat" style={{ marginLeft: "auto", marginRight: 8 }} onClose={() => setOpen(false)} aria-labelledby="repeat-title">
      <style>{"dialog.modal.repeat::backdrop { background: transparent; }"}</style>
      <h2 id="repeat-title">Repeat</h2>
      {choice("Pattern", MODES, mode, setMode)}
      <p className="hint">{MODES.find((m) => m.id === mode)!.hint}</p>

      {mode === "row" && (
        <div className="size-row">
          <CountBox label="Across" text={acrossText} setText={setAcross} lo={1} hi={20} />
          <CountBox label="Down" text={rowsText} setText={setRows} lo={1} hi={20} />
          {num("Space between", gap, setGap)}
        </div>
      )}
      {circle && (
        <>
          {choice("Center of the circle", [{ id: "below", label: "Below the design" }, { id: "hoop", label: "The middle of the hoop" }], center, setCenter)}
          <div className="size-row">
            {mode === "wreath" ? (
              <CountBox label="How many" text={roundText} setText={setRound} lo={2} hi={36} />
            ) : (
              <CountBox label="Pairs" text={pairsText} setText={setPairs} lo={2} hi={12} />
            )}
            {center === "below" && num("Circle size (radius)", radius, setRadius)}
          </div>
          {center === "hoop" && (
            <p className="hint">
              {fromMiddle < 1
                ? "The design is in the middle of the hoop, so the copies would land on top of each other. Move it off the middle first."
                : `The circle goes round the middle of the hoop, as far out as the design is now (${show(fromMiddle)} ${units}).`}
            </p>
          )}
          {mode === "wreath" && (
            <label className="check">
              <input type="checkbox" checked={turn} onChange={(e) => setTurn(e.target.checked)} /> Turn each copy to follow the circle
            </label>
          )}
        </>
      )}
      {mode === "mirror" && (
        <>
          {choice("Mirror", MIRRORS, mirrors, setMirrors)}
          <div className="size-row">{num("Space between", gap, setGap)}</div>
        </>
      )}

      <p className="hint">
        Makes {total} in all (the original plus {total - 1} {total - 1 === 1 ? "copy" : "copies"}). Ctrl+Z takes them out again.
      </p>
      {tooMany ? (
        <p className="error" role="alert">
          That would make about {stitches.toLocaleString()} stitches in all, far more than any design. Make fewer copies.
        </p>
      ) : stitches > WARN_STITCHES ? (
        <p className="hint" role="status">
          ⚠ That makes about {stitches.toLocaleString()} stitches in all: a very long sew-out on a home machine. Fewer copies sew faster.
        </p>
      ) : null}
      <div className="actions">
        <button onClick={() => setOpen(false)}>Cancel</button>
        <button className="primary" onClick={apply} disabled={!b || total < 2 || tooMany}>
          Repeat
        </button>
      </div>
    </dialog>
  );
}
