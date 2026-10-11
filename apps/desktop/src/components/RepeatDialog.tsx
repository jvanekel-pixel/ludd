import { useState } from "react";
import { repeatSelected } from "../actions";
import { MM_PER_IN } from "../design/grid";
import type { RepeatSpec } from "../design/layout";
import { selectLayout, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

type Mode = RepeatSpec["kind"];

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "row", label: "Row", hint: "Copies side by side, in a row or a grid." },
  { id: "circle", label: "Circle", hint: "Copies round a circle, like a wreath or a carousel." },
  { id: "mirror4", label: "Mirror ×4", hint: "Mirrored left–right and top–bottom: a four-way pattern, like a quilt block." },
];

/** Repeat the selected design: a row or grid, round a circle, or mirrored four ways. */
export function RepeatDialog() {
  const open = useStore((s) => s.repeatOpen);
  const setOpen = useStore((s) => s.setRepeatOpen);
  const units = useStore((s) => s.units);
  const layout = useStore(selectLayout);
  const design = useStore((s) => s.design);
  const selectedId = useStore((s) => s.selectedId);
  const ref = useModal(open);
  const [mode, setMode] = useState<Mode>("row");
  const [count, setCount] = useState(3);
  const [rows, setRows] = useState(1);
  const [gap, setGap] = useState(5);
  const [radius, setRadius] = useState(30);
  const [turn, setTurn] = useState(true);

  // The design being repeated, and its size (for spacing copies edge to edge).
  const index = layout ? (selectedId ? layout.items.findIndex((it) => it.id === selectedId) : layout.items.length === 1 ? 0 : -1) : -1;
  const b = index >= 0 ? design?.items?.[index]?.bounds_mm : undefined;
  const w = b ? b[2] - b[0] : 0;
  const h = b ? b[3] - b[1] : 0;

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

  const apply = () => {
    const spec: RepeatSpec =
      mode === "row"
        ? { kind: "row", columns: count, rows, step_x: w + gap, step_y: h + gap }
        : mode === "circle"
          ? { kind: "circle", count, radius, turn }
          : { kind: "mirror4", gap };
    repeatSelected(spec);
    setOpen(false);
  };
  const total = mode === "row" ? count * rows : mode === "circle" ? count : 4;

  return (
    <dialog ref={ref} className="modal repeat" onClose={() => setOpen(false)} aria-labelledby="repeat-title">
      <h2 id="repeat-title">Repeat</h2>
      <div className="seg" role="radiogroup" aria-label="Pattern">
        {MODES.map((m) => (
          <button key={m.id} role="radio" aria-checked={mode === m.id} aria-pressed={mode === m.id} onClick={() => setMode(m.id)}>
            {m.label}
          </button>
        ))}
      </div>
      <p className="hint">{MODES.find((m) => m.id === mode)!.hint}</p>

      {mode === "row" && (
        <div className="size-row">
          <label className="field">
            Across
            <input type="number" min={1} max={20} value={count} onChange={(e) => setCount(Math.max(1, Math.round(Number(e.target.value))))} />
          </label>
          <label className="field">
            Down
            <input type="number" min={1} max={20} value={rows} onChange={(e) => setRows(Math.max(1, Math.round(Number(e.target.value))))} />
          </label>
          {num("Space between", gap, setGap)}
        </div>
      )}
      {mode === "circle" && (
        <>
          <div className="size-row">
            <label className="field">
              How many
              <input type="number" min={2} max={36} value={count} onChange={(e) => setCount(Math.max(2, Math.round(Number(e.target.value))))} />
            </label>
            {num("Circle size (radius)", radius, setRadius)}
          </div>
          <label className="check">
            <input type="checkbox" checked={turn} onChange={(e) => setTurn(e.target.checked)} /> Turn each copy to follow the circle
          </label>
        </>
      )}
      {mode === "mirror4" && <div className="size-row">{num("Space between", gap, setGap)}</div>}

      <p className="hint">
        Makes {total} in all (the original plus {total - 1} {total - 1 === 1 ? "copy" : "copies"}). Ctrl+Z takes them out again.
      </p>
      <div className="actions">
        <button onClick={() => setOpen(false)}>Cancel</button>
        <button className="primary" onClick={apply} disabled={!b || total < 2}>
          Repeat
        </button>
      </div>
    </dialog>
  );
}
