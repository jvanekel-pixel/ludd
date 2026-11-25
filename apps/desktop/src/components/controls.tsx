/**
 * The right panel's building blocks, shared by its sections and by feature panels: command
 * buttons, number fields and steppers, the density slider, underlay buttons and the size fields.
 */
import { useEffect, useRef, useState } from "react";
import { command, commit, currentLayout } from "../actions";
import { formatShortcut } from "../commands";
import { MM_PER_IN, type Units } from "../design/grid";
import { scaleBy } from "../design/layout";
import type { LayoutItemInfo } from "../design/types";
import { heldCount } from "../escape";
import { useStore } from "../store";
import { Row } from "./Accordion";

export function fmtLen(mm: number, units: Units, digits?: number) {
  return units === "in" ? `${(mm / MM_PER_IN).toFixed(digits ?? 2)} in` : `${mm.toFixed(digits ?? 1)} mm`;
}

export const toUnits = (mm: number, units: Units) => (units === "in" ? mm / MM_PER_IN : mm);
export const fromUnits = (v: number, units: Units) => (units === "in" ? v * MM_PER_IN : v);

export function Cmd({ id, label }: { id: string; label: string }) {
  const c = command(id);
  return (
    <button onClick={c.run} title={`${c.title} (${formatShortcut(c.shortcut)})`} aria-label={c.title}>
      {label}
    </button>
  );
}

/** A number field that commits on Enter or blur, not on every keystroke. */
export function NumberField({
  value,
  onCommit,
  label,
  suffix,
  step = 0.01,
  digits = 2,
}: {
  value: number;
  onCommit: (v: number) => void;
  label: string;
  suffix?: string;
  step?: number;
  digits?: number;
}) {
  const [text, setText] = useState(value.toFixed(digits));
  useEffect(() => setText(value.toFixed(digits)), [value, digits]);
  const reverting = useRef(false);
  const done = () => {
    if (reverting.current) {
      reverting.current = false;
      return;
    }
    const v = Number(text);
    // Compare with what was shown, not the exact value: clicking in and out changes nothing.
    // An emptied box puts the old value back (it doesn't mean 0).
    if (text.trim() !== "" && Number.isFinite(v) && text.trim() !== value.toFixed(digits)) onCommit(v);
    else setText(value.toFixed(digits));
  };
  return (
    <label className="num-field">
      <span>{label}</span>
      <input
        type="number"
        step={step}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={done}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          // (While something is held, such as stitch editing, Esc lets go of that first.)
          if (e.key === "Escape" && !heldCount()) {
            // Esc lets go of the edit: the old value comes back and nothing changes.
            reverting.current = true;
            setText(value.toFixed(digits));
            (e.target as HTMLInputElement).blur();
          }
        }}
      />
      {suffix && <small>{suffix}</small>}
    </label>
  );
}

export function SizeFields({ id, info, scale }: { id: string; info: LayoutItemInfo; scale?: { x: number; y: number; rotate: number } }) {
  const units = useStore((s) => s.units);
  const [lock, setLock] = useState(true);
  const b = info.bounds_mm;
  if (!b) return null;
  const w = b[2] - b[0];
  const h = b[3] - b[1];
  const quarterTurn = scale ? Math.abs(Math.abs(scale.rotate) - 90) < 0.01 : false;
  const resize = (axis: "w" | "h", v: number) => {
    const l = currentLayout();
    if (!l || v <= 0) return;
    const f = fromUnits(v, units) / (axis === "w" ? w : h);
    if (lock || (scale && scale.rotate % 90 !== 0 && !quarterTurn)) return void commit(scaleBy(l, id, f));
    // For a stitch file turned a quarter, width on screen is the file's height.
    const onX = (axis === "w") !== quarterTurn;
    void commit(scaleBy(l, id, onX ? f : 1, onX ? 1 : f));
  };
  return (
    <div className="size-row">
      <NumberField label="W" value={toUnits(w, units)} onCommit={(v) => resize("w", v)} suffix={units} />
      <button
        className={`lock${lock ? " on" : ""}`}
        onClick={() => setLock(!lock)}
        aria-pressed={lock}
        aria-label="Keep proportions"
        title={lock ? "Keeping proportions" : "Width and height change separately"}
      >
        {lock ? "🔒" : "🔓"}
      </button>
      <NumberField label="H" value={toUnits(h, units)} onCommit={(v) => resize("h", v)} suffix={units} />
    </div>
  );
}

export function Check({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <label className="check" title={hint}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

/** Toggle one entry of a list-valued setting (e.g. underlay kinds). */
export const toggled = <T,>(list: readonly T[] | undefined, v: T, on: boolean): T[] => {
  const s = new Set(list ?? []);
  if (on) s.add(v);
  else s.delete(v);
  return [...s];
};

/** Density as a slider (right is denser): row spacing from `max` down to `min` mm, with the number
 *  under it while you drag (mm between rows, and rows per mm or per inch). It takes effect when let
 *  go (or after the arrow keys), so dragging doesn't redraw the design at every step. */
export function DensitySlider({ spacing, min, max, onCommit }: { spacing: number; min: number; max: number; onCommit: (mm: number) => void }) {
  const units = useStore((s) => s.units);
  const [shown, setShown] = useState(spacing);
  useEffect(() => setShown(spacing), [spacing]);
  const read = (el: HTMLInputElement) => Math.round(-Number(el.value) * 100) / 100;
  const commit = (e: { currentTarget: HTMLInputElement }) => {
    const mm = read(e.currentTarget);
    if (Math.abs(mm - spacing) >= 0.005) onCommit(mm);
  };
  const perUnit = units === "in" ? `${Math.round(25.4 / shown)} rows per inch` : `${(1 / shown).toFixed(1)} rows per mm`;
  return (
    <div className="density-slider">
      <span aria-hidden>Lighter</span>
      <input
        type="range"
        min={-max}
        max={-min}
        step={0.01}
        value={-shown}
        aria-label="Density (row spacing)"
        aria-valuetext={`${shown.toFixed(2)} mm between rows, ${perUnit}`}
        onChange={(e) => setShown(read(e.currentTarget))}
        onPointerUp={commit}
        onKeyUp={commit}
      />
      <span aria-hidden>Denser</span>
      <output className="density-value">
        <b>{shown.toFixed(2)} mm</b> between rows · {perUnit}
      </output>
    </div>
  );
}

/** A number with − and + buttons beside it (like Embrilliance's spinners). */
export function Stepper({
  label,
  value,
  step,
  min,
  max,
  digits = 2,
  suffix,
  onCommit,
  title,
}: {
  label: string;
  value: number;
  step: number;
  min: number;
  max: number;
  digits?: number;
  suffix?: string;
  onCommit: (v: number) => void;
  title?: string;
}) {
  const clampTo = (v: number) => Math.min(max, Math.max(min, Math.round(v / step) * step));
  return (
    <Row label={label} hint={title}>
      <div className="stepper">
        <button className="step" onClick={() => onCommit(clampTo(value - step))} disabled={value <= min} aria-label={`Less ${label.toLowerCase()}`}>
          −
        </button>
        <NumberField label="" value={value} step={step} digits={digits} onCommit={(v) => onCommit(Math.min(max, Math.max(min, v)))} />
        <button className="step" onClick={() => onCommit(clampTo(value + step))} disabled={value >= max} aria-label={`More ${label.toLowerCase()}`}>
          +
        </button>
        {suffix && <small>{suffix}</small>}
      </div>
    </Row>
  );
}

/** Underlay as a segmented control: Auto, or the kinds you pick. */
export function UnderlayButtons({ kinds, value, set }: { kinds: { id: string; label: string; title: string }[]; value: string[] | undefined; set: (v: string[] | undefined) => void }) {
  const auto = value == null;
  return (
    <div className="seg wrap" role="group" aria-label="Underlay">
      <button aria-pressed={auto} onClick={() => set(auto ? kinds.slice(0, 1).map((k) => k.id) : undefined)} title="Chosen for you from the fabric and the shape's width">
        Auto
      </button>
      {kinds.map((k) => (
        <button key={k.id} aria-pressed={!auto && value!.includes(k.id)} disabled={auto} onClick={() => set(toggled(value, k.id, !value!.includes(k.id)))} title={k.title}>
          {k.label}
        </button>
      ))}
    </div>
  );
}
