import { Fragment, useEffect, useRef, useState } from "react";
import {
  command,
  commit,
  convertObject,
  currentLayout,
  deleteColorBlock,
  itemLabel,
  setObjectParams,
  setObjectThread,
  setPicture,
  saveAppliqueSvg,
  setItemPinned,
  hasOwnDefaults,
  pickItem,
  recolorBlocks,
  recolorSources,
  renameThing,
  setItemsThread,
  moveItemTo,
  reorderItem,
  resetDefaults,
  setSatinWidth,
  setText,
} from "../actions";
import { applyColorway, deleteColorway, saveColorway, toggleTravelUnder } from "../features";
import { GARMENTS } from "../design/garments";
import type { Garment } from "../store";
import { formatShortcut } from "../commands";
import { heldCount, holdEscape } from "../escape";
import { MM_PER_IN, type Units } from "../design/grid";
import { hasRecolors, scaleBy, scaleImageByMeasure, updateTransform } from "../design/layout";
import { hoopFit } from "../design/machine";
import { blockAt, visibleRecords } from "../design/player";
import { isObject, isRibbon, isText, type FileItem, type Layout, type LayoutItem, type LayoutItemInfo, type ObjectItem, type RefImage, type Thread } from "../design/types";
import { selectHoop, selectImages, selectLayout, useStore } from "../store";
import { Section, Sub, Row, type SelKind } from "./Accordion";
import { Menu } from "./Menu";
import { itemMenu, openContextMenu, pictureMenu } from "../contextMenu";
import { AdvisorPanel } from "./AIPanels";
import { Checks, FabricPicker } from "./QualityPanel";
import { SelectedText } from "./TextPanel";
import { MatchAllDialog, ThreadPicker } from "./ThreadDialogs";

const FIT_TEXT = {
  fits: (hoop: string) => `Fits the ${hoop} hoop`,
  rotate: (hoop: string) => `Rotate 90° to fit the ${hoop} hoop`,
  too_big: (hoop: string) => `Too big for the ${hoop} hoop`,
};

export function fmtLen(mm: number, units: Units, digits?: number) {
  return units === "in" ? `${(mm / MM_PER_IN).toFixed(digits ?? 2)} in` : `${mm.toFixed(digits ?? 1)} mm`;
}

/** Tabbing onto the slider (or letting go without moving it) changes nothing, so it's no undo step. */
function setOpacity(img: RefImage, opacity: number) {
  if (Math.abs(opacity - img.opacity) > 1e-9) setPicture(img.id, { opacity });
}

const toUnits = (mm: number, units: Units) => (units === "in" ? mm / MM_PER_IN : mm);
const fromUnits = (v: number, units: Units) => (units === "in" ? v * MM_PER_IN : v);

function Cmd({ id, label }: { id: string; label: string }) {
  const c = command(id);
  return (
    <button onClick={c.run} title={`${c.title} (${formatShortcut(c.shortcut)})`} aria-label={c.title}>
      {label}
    </button>
  );
}

/** A number field that commits on Enter or blur, not on every keystroke. */
function NumberField({
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

function SizeFields({ id, info, scale }: { id: string; info: LayoutItemInfo; scale?: { x: number; y: number; rotate: number } }) {
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

/** A stitch file placed in the layout: its size, then rotation and position tucked inside. */
function FileSections({ item, info, sel }: { item: FileItem; info: LayoutItemInfo; sel: SelKind }) {
  const units = useStore((s) => s.units);
  const t = item.transform;
  // Same rule as the engine's warning: either axis more than 20% from the original.
  const tooFar = Math.max(Math.abs(t.scale_x - 1), Math.abs(t.scale_y - 1)) > 0.2 + 1e-9;
  const pct = Math.round(Math.sqrt(t.scale_x * t.scale_y) * 100);
  return (
    <Section id="file" sel={sel} defaultOpen title="Stitch file" summary={pct === 100 ? "Original size" : `${pct}% of original`}>
      <SizeFields id={item.id} info={info} scale={{ x: t.scale_x, y: t.scale_y, rotate: t.rotate }} />
      <Row label="">
        <Cmd id="edit.stitches" label="Edit stitches" />
      </Row>
      <p className={`scale-note${tooFar ? " warn" : ""}`}>
        {pct === 100 && !tooFar ? "Original size" : `${pct}% of original`}
        {tooFar && " · may stitch too dense or too sparse"}
      </p>
      <Sub id="file-position" title="Rotation and position" summary={t.rotate ? `${Math.round(t.rotate * 10) / 10}°` : undefined}>
        <div className="size-row">
          <NumberField
            label="Rotate"
            value={t.rotate}
            step={1}
            digits={1}
            suffix="°"
            onCommit={(v) => {
              const l = currentLayout();
              if (l) void commit(updateTransform(l, item.id, { rotate: v }));
            }}
          />
        </div>
        <div className="size-row">
          <NumberField
            label="Across"
            value={toUnits(t.x, units)}
            suffix={units}
            onCommit={(v) => {
              const l = currentLayout();
              if (l) void commit(updateTransform(l, item.id, { x: fromUnits(v, units) }));
            }}
          />
          <NumberField
            label="Down"
            value={toUnits(t.y, units)}
            suffix={units}
            onCommit={(v) => {
              const l = currentLayout();
              if (l) void commit(updateTransform(l, item.id, { y: fromUnits(v, units) }));
            }}
          />
        </div>
        <p className="hint">Position is relative to where the design started. Arrow keys nudge 1 mm (Shift: 1 cm).</p>
        <button
          className="wide"
          onClick={() => {
            const l = currentLayout();
            if (l) void commit(updateTransform(l, item.id, { rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }));
          }}
        >
          Reset size and rotation
        </button>
      </Sub>
    </Section>
  );
}

const DENSITY = [
  { label: "Light", satin: 0.5, fill: 0.5 },
  { label: "Normal", satin: 0.4, fill: 0.4 },
  { label: "Dense", satin: 0.32, fill: 0.33 },
];

function Check({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <label className="check" title={hint}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

/** Toggle one entry of a list-valued setting (e.g. underlay kinds). */
const toggled = <T,>(list: readonly T[] | undefined, v: T, on: boolean): T[] => {
  const s = new Set(list ?? []);
  if (on) s.add(v);
  else s.delete(v);
  return [...s];
};

/** Shown only when the AI add-on and the Stitch Advisor are on. */
function AdvisorButton() {
  useStore((s) => s.ai);
  useStore((s) => s.advice);
  const c = command("ai.advisor");
  if (!(c.enabled?.() ?? false)) return null;
  return (
    <button className="wide" onClick={c.run} title="Ask the AI how to stitch this shape; you accept or dismiss each suggestion">
      ✨ Ask the Stitch Advisor
    </button>
  );
}

/** A number with − and + buttons beside it (like Embrilliance's spinners). */
/** Density as a slider (right is denser): row spacing from `max` down to `min` mm, with the number
 *  under it while you drag (mm between rows, and rows per mm or per inch). It takes effect when let
 *  go (or after the arrow keys), so dragging doesn't redraw the design at every step. */
function DensitySlider({ spacing, min, max, onCommit }: { spacing: number; min: number; max: number; onCommit: (mm: number) => void }) {
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

function Stepper({
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
function UnderlayButtons({ kinds, value, set }: { kinds: { id: string; label: string; title: string }[]; value: string[] | undefined; set: (v: string[] | undefined) => void }) {
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

const KIND_TITLE = { run: "Line", satin: "Satin", fill: "Fill", applique: "Applique" } as const;

/** Fill patterns sewn as lines over the shape, not rows: no angle, Random, Edge pad or
 *  Cross-hatch underlay; stipple and cross-stitch also ignore the row spacing. */
const OPEN_PATTERNS = ["contour", "stipple", "cross"];

const PATTERNS: { id: string; label: string; title: string }[] = [
  { id: "tatami", label: "Tatami", title: "Rows of stitches: the standard fill" },
  { id: "gradient", label: "Gradient", title: "Rows that open out from dense to sparse across the shape: shading" },
  { id: "wave", label: "Wave", title: "Rows that ripple like water" },
  { id: "contour", label: "Contour", title: "Rows that follow the outline inwards, ring by ring" },
  { id: "stipple", label: "Stipple", title: "One meandering line over the shape, quilting style" },
  { id: "cross", label: "Cross-stitch", title: "Little Xs on a square grid" },
];

/** A fill's pattern, and the one or two settings that pattern has. */
function PatternRows({ p, set }: { p: Record<string, unknown>; set: (patch: Record<string, unknown>) => void }) {
  const pattern = (p.pattern as string | undefined) ?? "tatami";
  return (
    <>
      <Row label="Pattern" hint={PATTERNS.find((x) => x.id === pattern)?.title}>
        <select value={pattern} onChange={(e) => set({ pattern: e.target.value })} aria-label="Fill pattern">
          {PATTERNS.map((x) => (
            <option key={x.id} value={x.id} title={x.title}>
              {x.label}
            </option>
          ))}
        </select>
      </Row>
      {pattern === "gradient" && (
        <Stepper label="Sparse end" value={(p.gradient_to_mm as number | undefined) ?? 1.6} step={0.1} min={0.3} max={5} digits={1} suffix="mm" onCommit={(v) => set({ gradient_to_mm: v })} title="Row spacing at the light end (the dense end uses the density above)" />
      )}
      {pattern === "wave" && (
        <>
          <Stepper label="Wave height" value={(p.wave_mm as number | undefined) ?? 1.5} step={0.25} min={0.3} max={6} suffix="mm" onCommit={(v) => set({ wave_mm: v })} />
          <Stepper label="Wave length" value={(p.wave_length_mm as number | undefined) ?? 8} step={1} min={2} max={40} digits={0} suffix="mm" onCommit={(v) => set({ wave_length_mm: v })} />
        </>
      )}
      {pattern === "stipple" && (
        <Stepper label="Loop size" value={(p.stipple_mm as number | undefined) ?? 3} step={0.5} min={1} max={10} digits={1} suffix="mm" onCommit={(v) => set({ stipple_mm: v })} title="How far apart the meandering line's turns are" />
      )}
      {pattern === "cross" && (
        <Stepper label="Square" value={(p.cross_mm as number | undefined) ?? 2.5} step={0.5} min={1} max={8} digits={1} suffix="mm" onCommit={(v) => set({ cross_mm: v })} title="Size of one cross-stitch" />
      )}
      {pattern === "contour" && <p className="hint">Row spacing is the density; try Light for an open, ringed look.</p>}
    </>
  );
}
const KIND_PLURAL = { run: "lines", satin: "satins", fill: "fills", applique: "appliques" } as const;

/** New shapes start with the settings you used last on this kind of shape: say so, and offer the standard ones. */
function RememberedNote({ kind }: { kind: ObjectItem["kind"] }) {
  useStore((s) => s.history);
  const own = hasOwnDefaults(kind);
  return (
    <p className="hint remembered">
      New {KIND_PLURAL[kind]} start with the settings you set last{own ? "" : " (now the standard ones)"}.{" "}
      {own && (
        <button className="link" onClick={() => resetDefaults(kind)}>
          Use the standard settings for new {KIND_PLURAL[kind]}
        </button>
      )}
    </p>
  );
}

const UNDERLAY_KINDS = {
  fill: [
    { id: "edge", label: "Edge", title: "A running stitch just inside the edge: crisp outline" },
    { id: "tatami", label: "Cross-hatch", title: "A light fill across the top stitches: holds the fabric flat" },
  ],
  satin: [
    { id: "center", label: "Centre", title: "A run down the middle: for narrow columns" },
    { id: "edge", label: "Edge", title: "Runs along both sides: crisp edges" },
    { id: "zigzag", label: "Zigzag", title: "A loose zigzag: lifts wide columns" },
  ],
};

/** "Fill · Normal · 45°": a drawn shape's settings in a few words, for its folded heading. */
export function objectSummary(item: ObjectItem): string {
  const p = item.params as Record<string, unknown>;
  const spacing = (p.spacing_mm as number | undefined) ?? 0.4;
  const dens = DENSITY.reduce((b, d) => (Math.abs(d.fill - spacing) < Math.abs(b.fill - spacing) ? d : b)).label;
  if (item.kind === "run") return `${((p.style as string) ?? "single").replace(/^./, (c) => c.toUpperCase())} · ${(p.stitch_mm as number | undefined) ?? 2.5} mm`;
  if (item.kind === "fill") {
    const pattern = PATTERNS.find((x) => x.id === p.pattern && OPEN_PATTERNS.includes(x.id));
    if (pattern) return pattern.id === "contour" ? `${pattern.label} · ${dens}` : pattern.label;
    return `${dens} · ${Math.round((p.angle_deg as number | undefined) ?? 45)}°`;
  }
  if (item.kind === "applique") return `${(p.cover_width_mm as number | undefined) ?? 3} mm border`;
  if (isRibbon(item)) return `${item.geometry.width_mm} mm wide · ${dens}`;
  return dens;
}

/** A drawn shape: its stitches (with Underlay and Advanced inside), then its size and points. */
function ObjectSections({ item, info, sel }: { item: ObjectItem; info: LayoutItemInfo; sel: SelKind }) {
  // The thread it's sewn in: a color changed in Order & colors wins over the shape's own.
  const sewn = item.threads?.[0] ?? item.thread;
  const [picking, setPicking] = useState(false);
  const units = useStore((s) => s.units);
  const p = item.params as Record<string, unknown>;
  const set = (patch: Record<string, unknown>) => setObjectParams(item.id, patch);
  const spacing = (p.spacing_mm as number | undefined) ?? 0.4;
  const density = DENSITY.reduce((best, d) =>
    Math.abs((item.kind === "fill" ? d.fill : d.satin) - spacing) < Math.abs((item.kind === "fill" ? best.fill : best.satin) - spacing) ? d : best,
  );
  const b = info.bounds_mm;
  const pattern = item.kind === "fill" ? ((p.pattern as string | undefined) ?? "tatami") : "";
  const open = OPEN_PATTERNS.includes(pattern); // rows settings do nothing for these
  const noRows = pattern === "stipple" || pattern === "cross"; // ...and these ignore the spacing too
  return (
    <>
      <Section id="object" sel={sel} defaultOpen title={KIND_TITLE[item.kind]} summary={objectSummary(item)}>
        <button className="thread-button" onClick={() => setPicking(true)} title="Change thread">
          <span className="swatch" style={{ background: sewn.color }} />
          <span className="tname">
            {sewn.name || sewn.color}
            <small>{[sewn.brand, sewn.catalog].filter(Boolean).join(" ") || "Click to choose a thread"}</small>
          </span>
        </button>
        {(
          <Row label="Stitch as">
            <div className="seg wrap" role="group" aria-label="Stitch type">
              {(["run", "satin", "fill", "applique"] as const).map((k) => (
                <button
                  key={k}
                  aria-pressed={item.kind === k}
                  onClick={() => convertObject(item.id, k)}
                  title={
                    k === "applique"
                      ? "Sew a piece of fabric on, edged with satin"
                      : k === "satin"
                        ? item.kind === "fill" || item.kind === "applique"
                          ? "Fill the shape with one satin that turns and changes width with it"
                          : "A satin ribbon along these points"
                        : undefined
                  }
                >
                  {KIND_TITLE[k]}
                </button>
              ))}
            </div>
          </Row>
        )}
        {(item.kind === "fill" || item.kind === "applique") && (
          <div className="btn-row">
            <Cmd id="object.hole" label="✂ Cut a hole (O)" />
          </div>
        )}
        {item.kind === "satin" && !isRibbon(item) && (
          <div className="btn-row">
            <Cmd id="satin.otherWay" label="↻ Turn the stitches another way (Shift+W)" />
          </div>
        )}
        {item.kind === "run" && (
          <Row label="Style">
            <div className="seg" role="group" aria-label="Line style">
              {(["single", "triple", "bean", "motif"] as const).map((st) => (
                <button
                  key={st}
                  aria-pressed={(p.style ?? "single") === st}
                  onClick={() => set({ style: st })}
                  title={
                    st === "single"
                      ? "One pass"
                      : st === "triple"
                        ? "Sewn three times end to end: bolder"
                        : st === "bean"
                          ? "Each stitch sewn three times: boldest"
                          : "A little pattern repeated along the line: waves, zigzag, scallops, blanket stitch"
                  }
                >
                  {st === "single" ? "Single" : st === "triple" ? "Triple" : st === "bean" ? "Bean" : "Motif"}
                </button>
              ))}
            </div>
          </Row>
        )}
        {item.kind === "run" && p.style === "motif" && (
          <>
            <Row label="Motif">
              <select value={(p.motif as string | undefined) ?? "wave"} onChange={(e) => set({ motif: e.target.value })} aria-label="Motif">
                <option value="wave">Wave</option>
                <option value="zigzag">Zigzag</option>
                <option value="scallop">Scallop</option>
                <option value="blanket">Blanket stitch (applique edge)</option>
              </select>
            </Row>
            <Stepper label="Repeat" value={(p.motif_mm as number | undefined) ?? 4} step={0.5} min={1.5} max={20} digits={1} suffix="mm" onCommit={(v) => set({ motif_mm: v })} title="Length of one repeat" />
            <Stepper label="Width" value={(p.motif_width_mm as number | undefined) ?? 2.5} step={0.5} min={0.5} max={10} digits={1} suffix="mm" onCommit={(v) => set({ motif_width_mm: v })} title="How wide the motif is" />
          </>
        )}
        {isRibbon(item) && (
          <Stepper
            label="Width"
            value={item.geometry.width_mm}
            step={0.25}
            min={1}
            max={12}
            suffix="mm"
            onCommit={(v) => setSatinWidth(item.id, v)}
            title="How wide the satin is. New satins start this wide too."
          />
        )}
        {(item.kind === "satin" || (item.kind === "fill" && !noRows)) && (
          <>
            <Row label="Density" hint="How close the rows are">
              <div className="seg" role="group" aria-label="Density">
                {DENSITY.map((d) => (
                  <button key={d.label} aria-pressed={density === d && Math.abs((item.kind === "fill" ? d.fill : d.satin) - spacing) < 0.005} onClick={() => set({ spacing_mm: item.kind === "fill" ? d.fill : d.satin })}>
                    {d.label}
                  </button>
                ))}
              </div>
            </Row>
            {/* Or set it exactly: a slider and the row spacing in mm (smaller is denser). */}
            <DensitySlider spacing={spacing} min={0.2} max={item.kind === "fill" ? 1.2 : 1} onCommit={(v) => set({ spacing_mm: v })} />
            <Stepper label="Spacing" value={spacing} step={0.05} min={0.2} max={item.kind === "fill" ? 2 : 1.5} suffix="mm" onCommit={(v) => set({ spacing_mm: v })} title="Distance between rows: smaller is denser" />
          </>
        )}
        {item.kind === "fill" && <PatternRows p={p} set={set} />}
        {item.kind === "fill" && !open && (
          <>
            <Stepper label="Angle" value={Math.round((p.angle_deg as number | undefined) ?? 45)} step={5} min={0} max={179} digits={0} suffix="°" onCommit={(v) => set({ angle_deg: v })} title="Direction of the rows" />
            <Row label="">
              <Cmd id="object.angle" label="Draw the angle (I)" />
            </Row>
          </>
        )}
        {(item.kind === "fill" || item.kind === "applique" || (item.kind === "run" && item.geometry.closed)) && (
          <Row label="">
            <Cmd id="object.border" label="Add a satin border (Shift+B)" />
          </Row>
        )}
        {item.kind === "applique" && (
          <>
            <ol className="applique-steps">
              <li>Placement line, then the machine stops: lay your fabric over it.</li>
              <li>Tack-down, then it stops: trim the fabric close to the stitching.</li>
              <li>A satin border covers the edge.</li>
            </ol>
            <Stepper label="Border" value={(p.cover_width_mm as number | undefined) ?? 3} step={0.5} min={1} max={8} digits={1} suffix="mm" onCommit={(v) => set({ cover_width_mm: v })} title="Width of the satin border" />
            <Row label="Tack-down">
              <div className="seg" role="group" aria-label="Tack-down">
                {(["zigzag", "run"] as const).map((t) => (
                  <button key={t} aria-pressed={(p.tack ?? "zigzag") === t} onClick={() => set({ tack: t })} title={t === "zigzag" ? "A narrow zigzag holds the edge firmly" : "A straight line: quicker, for felt and other fabrics that don't fray"}>
                    {t === "zigzag" ? "Zigzag" : "Straight"}
                  </button>
                ))}
              </div>
            </Row>
            <Row label="">
              <button onClick={() => void saveAppliqueSvg()} title="The piece's outline at real size, for a cutting machine or to print and cut">
                Save cut file (SVG)…
              </button>
            </Row>
          </>
        )}

        {(item.kind === "satin" || item.kind === "fill") && (
          <Sub id={`underlay-${item.kind}`} title="Underlay" summary={p.underlay == null ? "Auto" : (p.underlay as string[]).join(", ") || "None"}>
            <UnderlayButtons
              kinds={open ? UNDERLAY_KINDS.fill.filter((k) => k.id !== "tatami") : UNDERLAY_KINDS[item.kind]}
              value={p.underlay as string[] | undefined}
              set={(v) => set({ underlay: v })}
            />
            <p className="hint">The foundation sewn first, so the top stitches sit flat. Auto chooses from the fabric and the shape's width.</p>
          </Sub>
        )}

        <Sub id={`advanced-${item.kind}`} title="Advanced stitch settings">
          {item.kind === "applique" && (
            <Stepper label="Spacing" value={spacing} step={0.05} min={0.2} max={1.5} suffix="mm" onCommit={(v) => set({ spacing_mm: v })} title="Distance between the border's stitches: smaller is denser" />
          )}
          {(item.kind === "run" || (item.kind === "fill" && pattern !== "cross")) && (
            <Stepper
              label="Length"
              value={(p.stitch_mm as number | undefined) ?? (item.kind === "fill" ? 3.5 : 2.5)}
              step={0.1}
              min={item.kind === "fill" ? 1 : 0.5}
              max={item.kind === "fill" ? (pattern === "stipple" ? 2.5 : 7) : 12}
              digits={1}
              suffix="mm"
              onCommit={(v) => set({ stitch_mm: v })}
              title="Stitch length"
            />
          )}
          {item.kind === "fill" && !open && (
            <Stepper label="Random" value={(p.random_pct as number | undefined) ?? 0} step={5} min={0} max={50} digits={0} suffix="%" onCommit={(v) => set({ random_pct: v })} title="Moves the needle points a little at random, so no lines show across the fill" />
          )}
          {(item.kind === "satin" || (item.kind === "fill" && !open)) &&
            (p.pull_comp_mm == null ? (
              <Row label="Edge pad" hint="Pull compensation: widens the shape because stitches pull the fabric in">
                <button aria-pressed onClick={() => set({ pull_comp_mm: 0.2 })} title="Chosen from the fabric and width. Click to set it yourself.">
                  Auto
                </button>
              </Row>
            ) : (
              <>
                <Stepper label="Edge pad" value={p.pull_comp_mm as number} step={0.05} min={0} max={2} suffix="mm" onCommit={(v) => set({ pull_comp_mm: v })} title="Pull compensation: widens the shape because stitches pull the fabric in" />
                <Row label="">
                  <button className="link" onClick={() => set({ pull_comp_mm: undefined })}>
                    Back to Auto
                  </button>
                </Row>
              </>
            ))}
          {item.kind === "fill" && <Check label="Sew from the other end (reverse)" checked={!!p.reverse} onChange={(v) => set({ reverse: v, end_mm: undefined })} hint="Or drag the red dot (where it ends) on the design" />}
          {item.kind === "satin" && (
            <>
              <Check label="Split long stitches" checked={!!p.split_mm} onChange={(v) => set({ split_mm: v ? 7 : 0 })} hint="Wide satins get stitches that can snag; this splits them into shorter ones" />
              {!!p.split_mm && <Stepper label="Longest" value={p.split_mm as number} step={0.5} min={2} max={12} digits={1} suffix="mm" onCommit={(v) => set({ split_mm: v })} />}
            </>
          )}
          {item.kind === "applique" && (
            <Check label="Sew a placement line first" checked={(p.placement as boolean | undefined) ?? true} onChange={(v) => set({ placement: v })} hint="Untick for pieces cut beforehand and placed by eye" />
          )}
          {/* An applique always locks at its stops (the machine cuts the thread there). */}
          {item.kind !== "applique" && (
            <>
              <Check label="Lock stitches at the start" checked={(p.tie_in as boolean | undefined) ?? true} onChange={(v) => set({ tie_in: v })} />
              <Check label="Lock stitches at the end" checked={(p.tie_off as boolean | undefined) ?? true} onChange={(v) => set({ tie_off: v })} />
            </>
          )}
          <AdvisorButton />
          <RememberedNote kind={item.kind} />
        </Sub>
      </Section>

      <Section id="size" sel={sel} title="Size and points" summary={b ? `${fmtLen(b[2] - b[0], units)} × ${fmtLen(b[3] - b[1], units)}` : undefined}>
        <SizeFields id={item.id} info={info} />
        <div className="btn-row">
          <Cmd id="draw.continue" label="Add points (K)" />
          {(item.kind === "fill" || item.kind === "applique") && <Cmd id="object.hole" label="Add a hole (O)" />}
        </div>
        <p className="hint">Drag a point to reshape; right-click a point to switch it between curve, straight and sharp corner; double-click the outline to add a point.</p>
      </Section>
      <ThreadPickerFor open={picking} current={sewn} onPick={(t) => setObjectThread(item.id, t)} onClose={() => setPicking(false)} />
    </>
  );
}

/** Thread picker for a drawn object (reuses the panel's picker by pointing it at the object's color block). */
function ThreadPickerFor({ open, onClose, onPick, current }: { open: boolean; onClose: () => void; onPick: (t: Thread) => void; current: Thread }) {
  return <ThreadPicker index={open ? -1 : null} onClose={onClose} onPick={onPick} current={current} />;
}

/** The selected picture's settings (see-through, real size), shown under its row in Pictures. */
function PictureSettings({ img }: { img: RefImage }) {
  const units = useStore((s) => s.units);
  const measure = useStore((s) => s.measure);
  const setMeasure = useStore((s) => s.setMeasure);
  const measuring = measure?.imageId === img.id;
  const pts = measuring ? measure.points : [];
  const measured = pts.length === 2 ? Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) : 0;
  return (
    <div className="picture-settings">
      <label className="slider">
        See-through <strong>{Math.round((1 - img.opacity) * 100)}%</strong>
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          defaultValue={img.opacity}
          key={`${img.id}-${img.opacity}`}
          onPointerUp={(e) => setOpacity(img, Number((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => setOpacity(img, Number((e.target as HTMLInputElement).value))}
        />
      </label>
      {!measuring ? (
        <button className="wide" onClick={() => setMeasure({ imageId: img.id, points: [] })} title="Click two points on the picture whose real distance you know">
          📏 Set real size…
        </button>
      ) : (
        <div className="measure">
          {pts.length < 2 ? (
            <p className="hint">Click {pts.length === 0 ? "the first" : "the second"} point on the picture.</p>
          ) : (
            <NumberField
              label="Real distance between the points"
              value={toUnits(measured, units)}
              suffix={units}
              onCommit={(v) => {
                setPicture(img.id, scaleImageByMeasure(img, measured, fromUnits(v, units)));
                setMeasure(null);
              }}
            />
          )}
          <button className="link" onClick={() => setMeasure(null)}>
            Cancel
          </button>
        </div>
      )}
      <p className="hint">
        {img.locked
          ? "Pinned: it can't move, and clicks go through it so you can draw over it."
          : "Drag to move; drag a corner to resize, or a side to stretch it. Pin it (📌) once it's where you want it."}{" "}
        Saved inside your project.
      </p>
    </div>
  );
}

/** One color stop as the list shows it: which of the design's colors (in sewing order), its
 *  thread, and the item's own part of it (what changing it here changes). */
type ColorStop = { block: number; thread: Thread; was: Thread | null; sources: { item: number; block: number }[] };

/** What the thread picker is choosing for. */
type Picking =
  | { kind: "item"; id: string }
  | { kind: "stops"; stops: ColorStop[]; title: string }
  | { kind: "palette"; blocks: number[]; thread: Thread }
  | { kind: "knockdown"; thread: Thread };

const threadKey = (t: Thread) => [t.color.toLowerCase(), t.name, t.catalog, t.brand].join("|");

/** The design in sewing order, with each step's colors: drag to reorder, click a swatch or ✎ to
 *  change a thread, and the Palette (the threads in use) to change a thread everywhere at once.
 *  (It used to be two sections, Threads and Sewing order.) */
function OrderSection({ sel }: { sel: SelKind }) {
  const layout = useStore(selectLayout);
  const design = useStore((s) => s.design);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  const setSelection = useStore((s) => s.setSelection);
  const engine = useStore((s) => s.engine);
  const playhead = useStore((s) => s.playhead);
  const stitchIdx = useStore((s) => s.stitchIdx);
  const hasMine = useStore((s) => s.charts.some((c) => c.mine && c.count > 0));
  const list = useRef<HTMLOListElement>(null);
  const clickMods = useRef(false);
  const [picking, setPicking] = useState<Picking | null>(null);
  const [matching, setMatching] = useState(false);
  /** A row being dragged to a new place in the order, and where it would land. */
  const [drag, setDrag] = useState<{ id: string; to: number } | null>(null);
  if (!layout || (!layout.items.length && !design)) return null;

  const selected = new Set([selectedId, ...extraIds].filter((x): x is string => !!x));
  const sewing = !!design && playhead > 0 && playhead < stitchIdx.length;
  const currentBlock = sewing && design ? blockAt(design, visibleRecords(stitchIdx, playhead, design.records.kind.length) - 1) : -1;

  /** Each item's colors, in sewing order. */
  const stopsOf = (i: number): ColorStop[] =>
    (design?.blocks ?? []).flatMap((b, k) => {
      const mine = (b.sources ?? []).filter((src) => src.item === i);
      if (!mine.length || !design) return [];
      const t = design.threads[b.thread];
      const was = b.original && b.original.color.toLowerCase() !== t.color.toLowerCase() ? b.original : null;
      return [{ block: k, thread: t, was, sources: mine }];
    });
  /** Stitching LUDD adds (basting box, knockdown): sewn first, part of no item. */
  const added = (design?.blocks ?? []).flatMap((b, k) => {
    const what = design ? addedStitching(layout, b, k) : null;
    return what && design ? [{ block: k, what, thread: design.threads[b.thread] }] : [];
  });
  /** The palette: every thread in use (once each), with the colors that use it. */
  const palette: { thread: Thread; blocks: number[] }[] = [];
  (design?.blocks ?? []).forEach((b, k) => {
    if (!design || !b.sources?.length) return;
    const t = design.threads[b.thread];
    const hit = palette.find((x) => threadKey(x.thread) === threadKey(t));
    if (hit) hit.blocks.push(k);
    else palette.push({ thread: t, blocks: [k] });
  });

  /** Drag a row by its grip: the rows make room as you go; let go to sew it there. Esc puts it back. */
  const startDrag = (e: React.PointerEvent, id: string) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const from = layout.items.findIndex((it) => it.id === id);
    let to = from;
    setDrag({ id, to });
    const panel = list.current?.closest<HTMLElement>(".info-panel");
    const move = (ev: PointerEvent) => {
      const others = [...(list.current?.querySelectorAll<HTMLElement>("li[data-row]") ?? [])].filter((r) => r.dataset.row !== id);
      to = others.filter((r) => {
        const b = r.getBoundingClientRect();
        return b.top + b.height / 2 < ev.clientY;
      }).length;
      setDrag({ id, to });
      // Near the top or bottom of the panel: scroll, so a long list can be reached.
      if (panel) {
        const b = panel.getBoundingClientRect();
        if (ev.clientY < b.top + 32) panel.scrollTop -= 14;
        else if (ev.clientY > b.bottom - 32) panel.scrollTop += 14;
      }
    };
    const end = (keep: boolean) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", drop);
      window.removeEventListener("pointercancel", putBack);
      window.removeEventListener("blur", putBack);
      release();
      setDrag(null);
      if (keep && to !== from) moveItemTo(id, to);
    };
    const drop = () => end(true);
    const putBack = () => end(false);
    const release = holdEscape(putBack);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", drop);
    window.addEventListener("pointercancel", putBack);
    window.addEventListener("blur", putBack);
  };
  /** The rows as shown: while dragging, the dragged one sits where it would land. */
  const shown = drag
    ? (() => {
        const rest = layout.items.filter((it) => it.id !== drag.id);
        rest.splice(drag.to, 0, layout.items.find((it) => it.id === drag.id)!);
        return rest;
      })()
    : layout.items;

  /** Select from the list without the list jumping: selecting opens that item's section above
   *  it, so scroll by as much as the row moved (and a double-click lands on the same row).
   *  Shift or Ctrl+click adds it to (or takes it from) the selection; a group is picked whole. */
  const selectInPlace = (id: string) => {
    const row = list.current?.querySelector<HTMLElement>(`[data-row="${id}"]`);
    const panel = row?.closest<HTMLElement>(".info-panel");
    const before = row?.getBoundingClientRect().top;
    if (clickMods.current) pickItem(id, true);
    else {
      const g = layout.items.find((it) => it.id === id)?.group;
      const members = g ? layout.items.filter((it) => it.group === g).map((it) => it.id) : [];
      setSelection(id, members.filter((m) => m !== id));
    }
    if (!row || !panel || before === undefined) return;
    // Hold the row still for a few frames while the panel settles.
    let frames = 8;
    const hold = () => {
      panel.scrollTop += row.getBoundingClientRect().top - before;
      if (--frames > 0) requestAnimationFrame(hold);
    };
    requestAnimationFrame(hold);
  };

  /** Change an item's thread: with several selected (and this one among them), all of them. */
  const pickFor = (it: LayoutItem, i: number) => {
    const stops = stopsOf(i);
    if (isObject(it) || isText(it) || selected.size > 1) return setPicking({ kind: "item", id: it.id });
    if (stops.length) setPicking({ kind: "stops", stops, title: itemLabel(it, i) });
  };
  const itemThread = (it: LayoutItem, i: number): Thread | null => stopsOf(i)[0]?.thread ?? (isObject(it) || isText(it) ? (it.threads?.[0] ?? it.thread) : null);

  const pickerCurrent = (): Thread | undefined => {
    if (!picking) return undefined;
    if (picking.kind === "item") {
      const i = layout.items.findIndex((it) => it.id === picking.id);
      return i >= 0 ? (itemThread(layout.items[i], i) ?? undefined) : undefined;
    }
    if (picking.kind === "stops") return picking.stops[0].thread;
    return picking.thread;
  };
  const onPicked = (t: Thread) => {
    if (!picking) return;
    if (picking.kind === "item") {
      const it = layout.items.find((x) => x.id === picking.id);
      if (!it) return;
      if (selected.size > 1 && selected.has(it.id)) setItemsThread([...selected], t);
      else if (isObject(it)) setObjectThread(it.id, t);
      else if (isText(it)) setText(it.id, { thread: t, threads: [] });
      else recolorSources(stopsOf(layout.items.indexOf(it)).flatMap((c) => c.sources), t);
    } else if (picking.kind === "stops") recolorSources(picking.stops.flatMap((c) => c.sources), t);
    else if (picking.kind === "palette") recolorBlocks(picking.blocks.map((block) => ({ block, thread: t })));
    else {
      const l = currentLayout();
      if (l?.knockdown) void commit({ ...l, knockdown: { ...l.knockdown, thread: t } });
    }
  };

  const colorOptions = [
    { id: "colors.merge", checked: layout.merge_colors },
    { id: "colors.sort", checked: layout.color_sort },
    ...(hasRecolors(layout) ? [{ id: "colors.reset" }] : []),
    { id: "threads.charts" },
  ];

  return (
    <Section
      id="order"
      sel={sel}
      shared
      defaultOpen
      title="Order & colors"
      badge={layout.items.length || undefined}
      summary={
        <span className="swatch-strip" aria-hidden>
          {palette.slice(0, 12).map((x, k) => (
            <span key={k} style={{ background: x.thread.color }} />
          ))}
        </span>
      }
      actions={
        <>
          <button onClick={() => setMatching(true)} disabled={!engine || !design} title="Find the closest of your threads (or a brand's) for every color">
            {hasMine ? "Match to mine…" : "Match…"}
          </button>
          <Menu label="Color options" items={colorOptions} />
        </>
      }
    >
      {palette.length > 0 && (
        <div className="palette" role="group" aria-label="Palette">
          <span className="palette-label">Palette</span>
          {palette.map((x) => (
            <button
              key={threadKey(x.thread)}
              className="palette-swatch"
              style={{ background: x.thread.color }}
              disabled={!engine}
              title={`${[x.thread.brand, x.thread.catalog, x.thread.name].filter(Boolean).join(" ") || x.thread.color} · used ${x.blocks.length}× · click to change it everywhere`}
              aria-label={`Change ${x.thread.name || x.thread.color} everywhere`}
              onClick={() => setPicking({ kind: "palette", blocks: x.blocks, thread: x.thread })}
            />
          ))}
        </div>
      )}
      {layout.merge_colors || layout.color_sort ? (
        <p className="hint order-note">{layout.color_sort ? "Sort colors is on: the machine sews same colors together, so its order can differ from this list." : "Same colors next to each other are sewn as one."}</p>
      ) : null}
      <ColorSets />
      <ol className={`design-list${drag ? " reordering" : ""}`} ref={list}>
        {added.map((a) => (
          <li key={`added-${a.block}`} className={`added-row${a.block === currentBlock ? " sewing" : ""}`}>
            <span className="grip" aria-hidden />
            <span className="swatch small" style={{ background: a.thread.color }} />
            <span className="name">
              {a.what === "basting" ? "Basting box" : "Knockdown"}
              <small>{a.what === "basting" ? " · sewn first; remove it afterwards" : " · use a thread that matches the fabric"}</small>
            </span>
            {a.what === "knockdown" && (
              <button className="rename-btn" aria-label="Change the knockdown thread" title="Change thread" disabled={!engine} onClick={() => setPicking({ kind: "knockdown", thread: a.thread })}>
                ✎
              </button>
            )}
          </li>
        ))}
        {shown.map((it, k) => {
          const i = layout.items.indexOf(it);
          const stops = stopsOf(i);
          const t = itemThread(it, i);
          const several = !isObject(it) && !isText(it) && stops.length > 1;
          const isSel = selected.has(it.id);
          const sewingHere = stops.some((c) => c.block === currentBlock);
          const name = design?.items?.[i]?.name ?? itemLabel(it, i);
          return (
            <Fragment key={it.id}>
              <li
                data-row={it.id}
                className={[isSel ? "current" : "", sewingHere ? "sewing" : "", drag?.id === it.id ? "dragging" : ""].join(" ").trim() || undefined}
                onClickCapture={(e) => (clickMods.current = e.shiftKey || e.ctrlKey || e.metaKey)}
                onContextMenu={(e) => {
                  if ((e.target as Element).closest("input")) return; // renaming: the text's own menu
                  clickMods.current = false; // a right-click picks the row alone (not with an old Shift+click)
                  if (!isSel) selectInPlace(it.id);
                  const now = useStore.getState();
                  openContextMenu(e, itemMenu(it, now.extraIds.length > 0), now.extraIds.length ? `${now.extraIds.length + 1} selected` : name);
                }}
              >
                <span className="grip" onPointerDown={(e) => startDrag(e, it.id)} title="Drag up or down to change the sewing order" aria-hidden>
                  ⠿
                </span>
                <button
                  className="swatch small"
                  style={{ background: several ? `linear-gradient(90deg, ${stops.slice(0, 4).map((c) => c.thread.color).join(", ")})` : (t?.color ?? "transparent") }}
                  title={several ? `${stops.length} colors (listed below)` : t ? `${t.name || t.color}: click to change` : undefined}
                  aria-label={several ? `${stops.length} colors` : "Change thread"}
                  disabled={!engine || several || !t}
                  onClick={() => pickFor(it, i)}
                >
                  {isText(it) ? "A" : ""}
                </button>
                <RenameField id={it.id} className="name" prefix={`${k + 1}. `} name={name} onClick={() => selectInPlace(it.id)} />
                {it.group && <span className="group-tag" title="In a group: selects and moves with the others">▣</span>}
                <button
                  className="rename-btn"
                  aria-label="Change thread"
                  title={several ? "Change each color below" : isSel && selected.size > 1 ? `Change the thread of all ${selected.size} selected` : "Change this step's thread"}
                  disabled={!engine || several || !t}
                  onClick={() => pickFor(it, i)}
                >
                  ✎
                </button>
                <button
                  className={`pin${it.locked ? " on" : ""}`}
                  aria-pressed={!!it.locked}
                  aria-label={it.locked ? "Unpin" : "Pin in place"}
                  title={it.locked ? "Pinned: can't be dragged. Click to unpin." : "Pin in place, so it can't be moved by accident"}
                  onClick={() => setItemPinned(it.id, !it.locked)}
                >
                  📌
                </button>
                <button aria-label="Sew earlier" title="Sew earlier" disabled={i === 0} onClick={() => reorderItem(it.id, -1)}>
                  ↑
                </button>
                <button aria-label="Sew later" title="Sew later" disabled={i === layout.items.length - 1} onClick={() => reorderItem(it.id, 1)}>
                  ↓
                </button>
              </li>
              {several &&
                !drag &&
                stops.map((c) => {
                  const sub = [c.thread.brand, c.thread.catalog].filter(Boolean).join(" ");
                  const onlyMine = (design?.blocks[c.block].sources ?? []).every((src) => src.item === i);
                  return (
                    <li
                      key={`${it.id}-${c.block}`}
                      className={`color-row${c.block === currentBlock ? " sewing" : ""}${isSel ? " current" : ""}`}
                      onContextMenu={(e) =>
                        openContextMenu(
                          e,
                          [
                            { label: "Change this color…", run: () => setPicking({ kind: "stops", stops: [c], title: name }), enabled: !!engine },
                            ...(c.was ? [{ label: `Back to ${c.was.name || c.was.color}`, run: () => recolorSources(c.sources, null), enabled: !!engine }] : []),
                            { label: "Remove this color's stitches", run: () => deleteColorBlock(c.block), enabled: !!engine && onlyMine && (design?.blocks.length ?? 0) > 1, hint: "Ctrl+Z undoes it" },
                            "separator",
                            { label: hasMine ? "Match all to my threads…" : "Match all threads…", run: () => setMatching(true), enabled: !!engine },
                            ...colorOptions,
                          ],
                          `Color ${c.block + 1}: ${c.thread.name || c.thread.color}`,
                        )
                      }
                    >
                      <button className="swatch small" style={{ background: c.thread.color }} disabled={!engine} aria-label={`Change color ${c.block + 1}`} title="Click to change" onClick={() => setPicking({ kind: "stops", stops: [c], title: name })} />
                      <span className="num">{c.block + 1}</span>
                      <span className="tname">
                        {c.thread.name || c.thread.color}
                        {sub && <small>{sub}</small>}
                        {c.was && <small className="was">was {c.was.name || c.was.color}</small>}
                      </span>
                      <button className="rename-btn" disabled={!engine} aria-label={`Change color ${c.block + 1}`} title="Change thread" onClick={() => setPicking({ kind: "stops", stops: [c], title: name })}>
                        ✎
                      </button>
                      <button
                        className="rename-btn"
                        onClick={() => deleteColorBlock(c.block)}
                        disabled={!engine || !onlyMine || (design?.blocks.length ?? 0) < 2}
                        aria-label={`Remove color ${c.block + 1}`}
                        title="Remove this color's stitches (Ctrl+Z to undo)"
                      >
                        🗑
                      </button>
                    </li>
                  );
                })}
            </Fragment>
          );
        })}
      </ol>
      <ThreadPicker
        index={picking ? -1 : null}
        onClose={() => setPicking(null)}
        current={pickerCurrent()}
        onPick={onPicked}
        {...(picking?.kind === "stops" && picking.stops.length === 1 && picking.stops[0].was
          ? { onReset: () => recolorSources(picking.stops[0].sources, null), resetLabel: picking.stops[0].was.name || picking.stops[0].was.color }
          : {})}
      />
      <MatchAllDialog open={matching} onClose={() => setMatching(false)} />
    </Section>
  );
}

/** The pictures underneath the design, to trace over: one list, and the selected picture's
 *  settings (see-through, real size) right under its row. */
function PicturesSection({ sel }: { sel: SelKind }) {
  const images = useStore(selectImages);
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  if (!images.length) return null;
  const current = images.find((im) => im.id === selectedId);
  const summary = current ? `${Math.round((1 - current.opacity) * 100)}% see-through${current.locked ? " · pinned" : ""}` : undefined;
  return (
    <Section id="pictures" sel={sel} defaultOpen={!!current} title="Pictures" badge={images.length} summary={summary}>
      <ul className="design-list">
        {images.map((im) => (
          <Fragment key={im.id}>
          <li
            className={im.id === selectedId ? "current" : undefined}
            onContextMenu={(e) => {
              select(im.id);
              openContextMenu(
                e,
                [...pictureMenu(), "separator", { label: im.visible ? "Hide this picture" : "Show this picture", run: () => setPicture(im.id, { visible: !im.visible }) }],
                im.name,
              );
            }}
          >
            <button className="name" onClick={() => select(im.id === selectedId ? null : im.id)}>
              🖼 {im.name}
            </button>
            <button
              className={`pin${im.locked ? " on" : ""}`}
              aria-pressed={im.locked}
              title={im.locked ? "Pinned to the board: clicks go through it. Click to unpin." : "Pin to the board, so it can't be moved by accident"}
              aria-label={im.locked ? "Unpin" : "Pin to the board"}
              onClick={() => setPicture(im.id, { locked: !im.locked })}
            >
              📌
            </button>
            <button title={im.visible ? "Hide" : "Show"} aria-label={im.visible ? "Hide" : "Show"} onClick={() => setPicture(im.id, { visible: !im.visible })}>
              {im.visible ? "👁" : "◌"}
            </button>
          </li>
          {im.id === selectedId && (
            <li className="picture-settings-row">
              <PictureSettings img={im} />
            </li>
          )}
          </Fragment>
        ))}
      </ul>
    </Section>
  );
}

/** The design as a whole: size, stitches, colors, fit in the hoop, and the fabric. */
function DesignSection({ sel }: { sel: SelKind }) {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const hoop = useStore(selectHoop);
  const units = useStore((s) => s.units);
  const preview = useStore((s) => s.preview);
  const setPreview = useStore((s) => s.setPreview);
  if (!layout) return null;
  const fit = design && hoop ? hoopFit(design.info, hoop) : null;
  return (
    <Section
      id="design"
      sel={sel}
      defaultOpen={sel === "none"}
      title="Design"
      badge={fit && fit !== "fits" ? "!" : undefined}
      summary={design ? `${fmtLen(design.info.width_mm, units)} × ${fmtLen(design.info.height_mm, units)} · ${design.info.stitches.toLocaleString()} stitches` : "Nothing stitched yet"}
    >
      {design ? (
        <>
          {fit && hoop && <p className={`fit fit-${fit}`}>{FIT_TEXT[fit](hoop.name)}</p>}
          <dl>
            <div>
              <dt>Size</dt>
              <dd>
                {fmtLen(design.info.width_mm, units)} × {fmtLen(design.info.height_mm, units)}
              </dd>
            </div>
            <div>
              <dt>Stitches</dt>
              <dd>{design.info.stitches.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Colors</dt>
              <dd>{design.info.colors}</dd>
            </div>
          </dl>
        </>
      ) : (
        <p className="hint">
          Pick a tool on the left (Line, Satin or Fill) and click on the canvas to draw. Add a picture to trace with{" "}
          <kbd>{formatShortcut(command("file.picture").shortcut)}</kbd>.
        </p>
      )}
      <FabricPicker />
      <label className="check" title="Moves between shapes in one thread run under stitching that's sewn later, where they can: fewer jumps and trims to snip">
        <input type="checkbox" checked={!!layout.travel_under} onChange={() => toggleTravelUnder()} /> Fewer jumps & trims (hide moves under later stitching)
      </label>
      <div className="btn-row">
        <Cmd id="layout.optimizeJumps" label="Optimize jumps" />
        <Cmd id="layout.shortestOrder" label="Sew in the shortest order" />
      </div>
      <Sub id="design-preview" title="Preview on" summary={GARMENTS.find((g) => g.id === preview.garment)?.label}>
        <Row label="Garment">
          <select value={preview.garment} onChange={(e) => setPreview({ garment: e.target.value as Garment })} aria-label="Preview on">
            {GARMENTS.map((g) => (
              <option key={g.id} value={g.id}>
                {g.label}
              </option>
            ))}
          </select>
        </Row>
        <Row label="Fabric color">
          <input type="color" value={preview.color} onChange={(e) => setPreview({ color: e.target.value })} aria-label="Fabric color" />
        </Row>
        <p className="hint">Just a picture behind the design, to see how it looks: nothing is stitched.</p>
      </Sub>
      {design && (
        <Sub id="design-details" title="File details" summary={design.format.toUpperCase()}>
          <dl>
            {(
              [
                ["File type", design.format.toUpperCase()],
                ["Color changes", String(design.info.color_changes)],
                ["Stops", String(design.info.stops)],
                ["Trims", String(design.info.trims)],
                ["Jumps", String(design.info.jumps)],
              ] as const
            ).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </Sub>
      )}
    </Section>
  );
}

/** Saved sets of colors (colorways): save the colors as they are, switch between sets. */
function ColorSets() {
  const layout = useStore(selectLayout);
  const [name, setName] = useState("");
  const sets = layout?.colorways ?? [];
  return (
    <Sub id="color-sets" title="Color sets" summary={sets.length ? `${sets.length} saved` : undefined}>
      <p className="hint">Save these colors as a set, try others, and switch back in one click (pink version, blue version…).</p>
      {sets.length > 0 && (
        <ul className="color-sets">
          {sets.map((c) => (
            <li key={c.name}>
              <span className="swatch-strip" aria-hidden>
                {Object.values(c.items)
                  .slice(0, 8)
                  .map((v, i) => (
                    <span key={i} style={{ background: (v.threads?.[0] ?? v.thread)?.color ?? "transparent" }} />
                  ))}
              </span>
              <span className="name">{c.name}</span>
              <button onClick={() => void applyColorway(c.name)}>Use</button>
              <button aria-label={`Delete ${c.name}`} title="Delete this set" onClick={() => void deleteColorway(c.name)}>
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="btn-row">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. Pink" aria-label="Color set name" onKeyDown={(e) => e.key === "Enter" && name.trim() && (void saveColorway(name), setName(""))} />
        <button disabled={!name.trim()} onClick={() => (void saveColorway(name), setName(""))}>
          Save colors
        </button>
      </div>
    </Sub>
  );
}

/** Stitching LUDD adds that belongs to no shape: the basting box (sewn first) and knockdown
 *  (sewn first, or straight after the basting box). Null for a design's own colors. */
export function addedStitching(layout: Layout, b: { sources?: unknown[] }, index: number): "basting" | "knockdown" | null {
  if (b.sources?.length) return null;
  if (layout.basting?.enabled && index === 0) return "basting";
  if (layout.knockdown?.enabled) return "knockdown";
  return layout.basting?.enabled ? "basting" : null;
}

/** How long a click waits to see if it's a double-click. */
const DOUBLE_CLICK_MS = 250;

/** A name you can change: double-click it (or press F2). Enter keeps it, Esc puts it back. */
function RenameField({
  id,
  name,
  className,
  prefix,
  onClick,
  listen,
}: {
  id: string;
  name: string;
  className?: string;
  prefix?: string;
  onClick?: () => void;
  /** Start editing when a "ludd:rename" event names this (F2 sends the selected item's id). */
  listen?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const cancelled = useRef(false);
  // A click waits a moment in case it's the first half of a double-click (which renames
  // instead), so the panel doesn't change under the second click.
  const clickTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(clickTimer.current), []);
  useEffect(() => {
    const onRename = (e: Event) => {
      if (listen && (e as CustomEvent).detail === listen) {
        setDraft(name);
        setEditing(true);
      }
    };
    window.addEventListener("ludd:rename", onRename);
    return () => window.removeEventListener("ludd:rename", onRename);
  }, [listen, name]);
  if (!editing)
    return (
      <span
        className={`rename ${className ?? ""}`}
        title={`${name}: ${onClick ? "click to select, " : ""}double-click (or F2) to rename`}
        role={onClick ? "button" : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={
          onClick
            ? (e) => {
                clearTimeout(clickTimer.current);
                if (e.detail > 1) return; // the second click of a double-click
                clickTimer.current = setTimeout(onClick, DOUBLE_CLICK_MS);
              }
            : undefined
        }
        onKeyDown={onClick ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onClick()) : undefined}
        onDoubleClick={(e) => {
          e.stopPropagation();
          clearTimeout(clickTimer.current);
          setDraft(name);
          setEditing(true);
        }}
      >
        {prefix}
        {name}
      </span>
    );
  return (
    <input
      className="rename-input"
      autoFocus
      value={draft}
      maxLength={80}
      aria-label="Name"
      onFocus={(e) => e.target.select()}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape" && !heldCount()) {
          cancelled.current = true;
          (e.target as HTMLInputElement).blur();
        }
      }}
      onBlur={() => {
        if (!cancelled.current && draft.trim() !== name) renameThing(id, draft);
        cancelled.current = false;
        setEditing(false);
      }}
    />
  );
}

/** Small icon buttons for the header, each a command (so it shows its shortcut). */
function Quick({ id, label, icon }: { id: string; label?: string; icon: string }) {
  const c = command(id);
  return (
    <button className="quick" onClick={c.run} disabled={!(c.enabled?.() ?? true)} title={`${label ?? c.title} (${formatShortcut(c.shortcut)})`} aria-label={label ?? c.title}>
      {icon}
    </button>
  );
}

/** What's selected, always in view at the top: its name, and what you do to it most. */
function Inspector({ sel, name, kind, pinned, img }: { sel: SelKind; name: string; kind: string; pinned?: boolean; img?: RefImage }) {
  const layout = useStore(selectLayout);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  useStore((s) => s.history);
  if (sel === "none") return null;
  if (sel === "multi" && layout) {
    const ids = [selectedId, ...extraIds];
    const group = layout.items.find((x) => x.id === ids[0])?.group;
    const grouped = !!group && ids.every((id) => layout.items.find((x) => x.id === id)?.group === group);
    return (
      <div className="inspector">
        <div className="inspector-name">
          <strong>
            {ids.length} selected{grouped ? " (a group)" : ""}
          </strong>
          <small className="multi-note">They move, turn, resize, mirror, copy, recolor and delete together. Shift+click adds or removes one.</small>
        </div>
        <div className="inspector-actions">
          {grouped ? <Quick id="arrange.ungroup" icon="⬚" label="Ungroup" /> : <Quick id="arrange.group" icon="▣" label="Group" />}
          <Quick id="object.thread" icon="🧵" label="Thread" />
          <Quick id="arrange.rotateCw" icon="⟳" />
          <Quick id="arrange.mirrorX" icon="⇋" />
          <Quick id="arrange.duplicate" icon="⧉" />
          <Menu
            label="More actions"
            items={[
              { id: "arrange.repeat" },
              { id: "arrange.mirrorY" },
              { id: "arrange.rotateCcw" },
              "separator",
              { id: "object.offset", label: "Outline / offset around them…" },
              { id: "object.merge", label: "Merge into one shape" },
              { id: "object.cutOut", label: "Cut the shapes on top out of the fill" },
              { id: "text.onLine", label: "Put the text on the line" },
              "separator",
              { id: "arrange.delete" },
            ]}
          />
        </div>
      </div>
    );
  }
  if (img) {
    return (
      <div className="inspector">
        <div className="inspector-name">
          <strong>
            <RenameField id={img.id} name={img.name} className="inspector-title" listen={img.id} />
          </strong>
          <small>Picture{img.locked ? " · pinned" : ""}</small>
        </div>
        <div className="inspector-actions">
          <button className="quick" aria-pressed={img.locked} aria-label={img.locked ? "Unpin" : "Pin to the board"} onClick={() => setPicture(img.id, { locked: !img.locked })} title={img.locked ? "Pinned to the board: click to unpin (Ctrl+L)" : "Pin to the board (Ctrl+L)"}>
            📌
          </button>
          <button className="quick" onClick={() => setPicture(img.id, { visible: !img.visible })} title={img.visible ? "Hide" : "Show"} aria-label={img.visible ? "Hide" : "Show"}>
            {img.visible ? "👁" : "◌"}
          </button>
          <Menu label="More actions" items={[{ id: "arrange.delete", label: "Remove picture" }]} />
        </div>
      </div>
    );
  }
  return (
    <div className="inspector">
      <div className="inspector-name">
        <strong>{selectedId ? <RenameField id={selectedId} name={name} className="inspector-title" listen={selectedId} /> : name}</strong>
        <small>
          {kind}
          {pinned ? " · 📌 pinned" : ""}
        </small>
      </div>
      <div className="inspector-actions">
        <Quick id="arrange.rotateCcw" icon="⟲" />
        <Quick id="arrange.rotateCw" icon="⟳" />
        <Quick id="arrange.mirrorX" icon="⇋" />
        <Quick id="arrange.duplicate" icon="⧉" />
        <Menu
          label="More actions"
          items={[
            ...(sel === "file" ? [] : [{ id: "object.thread" }]),
            ...(sel === "text" ? [{ id: "text.edit" }, { id: "text.toShapes" }] : []),
            { id: "arrange.centre" },
            { id: "arrange.first" },
            { id: "arrange.last" },
            "separator",
            { id: "arrange.repeat" },
            { id: "arrange.mirrorY" },
            { id: "arrange.pin", label: pinned ? "Unpin" : "Pin in place", checked: !!pinned },
            { id: "arrange.rename", label: "Rename…" },
            "separator",
            { id: "object.offset", label: "Outline / offset…" },
            { id: "tool.knife", label: "Knife: cut in two" },
            { id: "object.hole", label: "Cut a hole (draw round it)" },
            { id: "edit.stitches", label: "Edit stitches" },
            "separator",
            { id: "arrange.delete" },
          ]}
        />
      </div>
    </div>
  );
}

export function InfoPanel() {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const images = useStore(selectImages);
  const selectedId = useStore((s) => s.selectedId);
  const extra = useStore((s) => s.extraIds.length);
  if (!layout) return null;

  const picture = images.find((im) => im.id === selectedId);
  const selIndex = layout.items.findIndex((it) => it.id === selectedId);
  const selItem = selIndex >= 0 ? layout.items[selIndex] : null;
  const selInfo = selItem ? design?.items?.[selIndex] : undefined;
  const sel: SelKind = extra
    ? "multi"
    : picture
      ? "picture"
      : !selItem
        ? "none"
        : isObject(selItem)
          ? selItem.kind
          : isText(selItem)
            ? "text"
            : "file";
  const kindName = sel === "text" ? "Lettering" : sel === "file" ? "Stitch file" : selItem && isObject(selItem) ? KIND_TITLE[selItem.kind] : "";

  return (
    <aside className="info-panel">
      <div className="panel-title">
        <h2 title={design?.path}>{design?.name ?? (layout.title || "New design")}</h2>
      </div>
      <Inspector sel={sel} name={selInfo?.name ?? picture?.name ?? ""} kind={kindName} pinned={!!selItem?.locked} img={picture} />
      <AdvisorPanel />

      {picture && <PicturesSection sel={sel} />}
      {sel !== "multi" &&
        selItem &&
        selInfo &&
        (isObject(selItem) ? (
          <ObjectSections item={selItem} info={selInfo} sel={sel} />
        ) : isText(selItem) ? (
          <SelectedText item={selItem} info={selInfo} sel={sel} />
        ) : (
          <FileSections item={selItem as FileItem} info={selInfo} sel={sel} />
        ))}

      <DesignSection sel={sel} />
      <OrderSection sel={sel} />
      <Checks sel={sel} />
      {!picture && <PicturesSection sel={sel} />}
    </aside>
  );
}
