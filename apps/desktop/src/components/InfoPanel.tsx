import { useEffect, useRef, useState } from "react";
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
} from "../actions";
import { formatShortcut } from "../commands";
import { MM_PER_IN, type Units } from "../design/grid";
import { hasRecolors, reorder, scaleBy, scaleImageByMeasure, updateTransform } from "../design/layout";
import { hoopFit } from "../design/machine";
import { blockAt, visibleRecords } from "../design/player";
import { isObject, isText, type FileItem, type LayoutItemInfo, type ObjectItem, type RefImage, type Thread } from "../design/types";
import { selectHoop, selectImages, selectLayout, useStore } from "../store";
import { FoldTitle, useFold } from "./Fold";
import { Menu } from "./Menu";
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
    if (Number.isFinite(v) && text.trim() !== value.toFixed(digits)) onCommit(v);
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
          if (e.key === "Escape") {
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
        title={lock ? "Keeping proportions" : "Width and height change separately"}
      >
        {lock ? "🔒" : "🔓"}
      </button>
      <NumberField label="H" value={toUnits(h, units)} onCommit={(v) => resize("h", v)} suffix={units} />
    </div>
  );
}

/** A stitch file placed in the layout. */
function SelectedFile({ item, info }: { item: FileItem; info: LayoutItemInfo }) {
  const units = useStore((s) => s.units);
  const t = item.transform;
  // Same rule as the engine's warning: either axis more than 20% from the original.
  const tooFar = Math.max(Math.abs(t.scale_x - 1), Math.abs(t.scale_y - 1)) > 0.2 + 1e-9;
  const pct = Math.round(Math.sqrt(t.scale_x * t.scale_y) * 100);
  return (
    <section className="selected">
      <h3 title={item.path}>{info.name}</h3>
      <div className="btn-row">
        <Cmd id="arrange.rotateCcw" label="⟲ 90°" />
        <Cmd id="arrange.rotateCw" label="⟳ 90°" />
        <Cmd id="arrange.mirrorX" label="⇋" />
        <Cmd id="arrange.mirrorY" label="⇵" />
        <Cmd id="arrange.duplicate" label="Duplicate" />
        <Cmd id="arrange.repeat" label="Repeat…" />
      </div>
      <SizeFields id={item.id} info={info} scale={{ x: t.scale_x, y: t.scale_y, rotate: t.rotate }} />
      <p className={`scale-note${tooFar ? " warn" : ""}`}>
        {pct === 100 && !tooFar ? "Original size" : `${pct}% of original`}
        {tooFar && " · may stitch too dense or too sparse"}
      </p>
      <details className="more">
        <summary>More options</summary>
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
        <div className="btn-row">
          <button
            onClick={() => {
              const l = currentLayout();
              if (l) void commit(updateTransform(l, item.id, { rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }));
            }}
          >
            Reset size and rotation
          </button>
          <Cmd id="arrange.delete" label="Remove" />
        </div>
      </details>
    </section>
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

/** Several things selected (Shift+click, Ctrl+A, a group): what you can do to them together. */
function SelectionBar() {
  const extra = useStore((s) => s.extraIds.length);
  const layout = useStore(selectLayout);
  const selectedId = useStore((s) => s.selectedId);
  if (!extra || !layout) return null;
  const ids = [selectedId, ...useStore.getState().extraIds];
  const grouped = ids.every((id) => {
    const it = layout.items.find((x) => x.id === id);
    return it?.group && it.group === layout.items.find((x) => x.id === ids[0])?.group;
  });
  return (
    <section className="selection-bar">
      <h3>
        {extra + 1} selected{grouped ? " (a group)" : ""}
      </h3>
      <p className="hint">They move, turn, resize, mirror, copy and delete together. Shift+click adds or removes one.</p>
      <div className="btn-row">
        {grouped ? <Cmd id="arrange.ungroup" label="Ungroup" /> : <Cmd id="arrange.group" label="Group" />}
        <Cmd id="arrange.rotateCw" label="⟳ 90°" />
        <Cmd id="arrange.mirrorX" label="⇋" />
        <Cmd id="arrange.delete" label="Remove" />
      </div>
    </section>
  );
}

/** Which tab the shape panel shows; kept while you click from shape to shape. */
let lastObjectTab: "thread" | "stitches" | "shape" = "stitches";

/** A number with − and + buttons beside it (like Embrilliance's spinners). */
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
    <div className="stepper" title={title}>
      <span className="stepper-label">{label}</span>
      <button className="step" onClick={() => onCommit(clampTo(value - step))} disabled={value <= min} aria-label={`Less ${label.toLowerCase()}`}>
        −
      </button>
      <NumberField label="" value={value} step={step} digits={digits} onCommit={(v) => onCommit(Math.min(max, Math.max(min, v)))} />
      <button className="step" onClick={() => onCommit(clampTo(value + step))} disabled={value >= max} aria-label={`More ${label.toLowerCase()}`}>
        +
      </button>
      {suffix && <small>{suffix}</small>}
    </div>
  );
}

/** A row of toggle buttons for underlay kinds, plus Automatic. */
function UnderlayButtons({ kinds, value, set }: { kinds: { id: string; label: string; title: string }[]; value: string[] | undefined; set: (v: string[] | undefined) => void }) {
  const auto = value == null;
  return (
    <div className="toggle-row" role="group" aria-label="Underlay">
      <span className="stepper-label">Underlay</span>
      <button aria-pressed={auto} onClick={() => set(auto ? kinds.slice(0, 1).map((k) => k.id) : undefined)} title="Chosen for you from the fabric and the shape's width">
        Auto
      </button>
      {kinds.map((k) => (
        <button
          key={k.id}
          aria-pressed={!auto && value!.includes(k.id)}
          disabled={auto}
          onClick={() => set(toggled(value, k.id, !value!.includes(k.id)))}
          title={k.title}
        >
          {k.label}
        </button>
      ))}
    </div>
  );
}

/** A drawn object: Thread, Stitches and Shape tabs, every setting in view. */
function SelectedObject({ item, info }: { item: ObjectItem; info: LayoutItemInfo }) {
  const [picking, setPicking] = useState(false);
  const [tab, setTabState] = useState(lastObjectTab);
  const setTab = (t: typeof tab) => {
    lastObjectTab = t;
    setTabState(t);
  };
  const p = item.params as Record<string, unknown>;
  const set = (patch: Record<string, unknown>) => setObjectParams(item.id, patch);
  const spacing = (p.spacing_mm as number | undefined) ?? 0.4;
  const density = DENSITY.reduce((best, d) =>
    Math.abs((item.kind === "fill" ? d.fill : d.satin) - spacing) < Math.abs((item.kind === "fill" ? best.fill : best.satin) - spacing) ? d : best,
  );
  const pinned = !!item.locked;
  return (
    <section className="selected">
      <h3>
        {info.name} {pinned && <span title="Pinned: it can't be moved by dragging">📌</span>}
      </h3>
      <div className="tabs object-tabs" role="tablist">
        {(["thread", "stitches", "shape"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {t === "thread" ? "Thread" : t === "stitches" ? "Stitches" : "Shape"}
          </button>
        ))}
      </div>

      {tab === "thread" && (
        <>
          <button className="thread-button" onClick={() => setPicking(true)} title="Change thread">
            <span className="swatch" style={{ background: item.thread.color }} />
            <span className="tname">
              {item.thread.name || item.thread.color}
              <small>{[item.thread.brand, item.thread.catalog].filter(Boolean).join(" ") || "Click to choose a thread"}</small>
            </span>
          </button>
          <AdvisorButton />
        </>
      )}

      {tab === "stitches" && (
        <>
          {item.kind !== "satin" && (
            <div className="seg" role="group" aria-label="Stitch type">
              {(["run", "fill", "applique"] as const).map((k) => (
                <button key={k} aria-pressed={item.kind === k} onClick={() => convertObject(item.id, k)} title={k === "applique" ? "Sew a piece of fabric on, edged with satin" : undefined}>
                  {k === "run" ? "Line" : k === "fill" ? "Fill" : "Applique"}
                </button>
              ))}
            </div>
          )}

          {item.kind === "run" && (
            <>
              <div className="seg" role="group" aria-label="Line style">
                {(["single", "triple", "bean"] as const).map((st) => (
                  <button
                    key={st}
                    aria-pressed={(p.style ?? "single") === st}
                    onClick={() => set({ style: st })}
                    title={st === "single" ? "One pass" : st === "triple" ? "Sewn three times end to end: bolder" : "Each stitch sewn three times: boldest"}
                  >
                    {st === "single" ? "Single" : st === "triple" ? "Triple" : "Bean"}
                  </button>
                ))}
              </div>
              <Stepper label="Length" value={(p.stitch_mm as number | undefined) ?? 2.5} step={0.1} min={0.5} max={12} digits={1} suffix="mm" onCommit={(v) => set({ stitch_mm: v })} title="Stitch length" />
            </>
          )}

          {(item.kind === "satin" || item.kind === "fill") && (
            <>
              <UnderlayButtons
                kinds={
                  item.kind === "fill"
                    ? [
                        { id: "edge", label: "Edge", title: "A running stitch just inside the edge: crisp outline" },
                        { id: "tatami", label: "Cross-hatch", title: "A light fill across the top stitches: holds the fabric flat" },
                      ]
                    : [
                        { id: "center", label: "Centre", title: "A run down the middle: for narrow columns" },
                        { id: "edge", label: "Edge", title: "Runs along both sides: crisp edges" },
                        { id: "zigzag", label: "Zigzag", title: "A loose zigzag: lifts wide columns" },
                      ]
                }
                value={p.underlay as string[] | undefined}
                set={(v) => set({ underlay: v })}
              />
              <Stepper label="Density" value={spacing} step={0.05} min={0.2} max={item.kind === "fill" ? 2 : 1.5} suffix="mm" onCommit={(v) => set({ spacing_mm: v })} title="Distance between rows: smaller is denser" />
              <div className="seg chips" role="group" aria-label="Density presets">
                {DENSITY.map((d) => (
                  <button key={d.label} aria-pressed={density === d} onClick={() => set({ spacing_mm: item.kind === "fill" ? d.fill : d.satin })}>
                    {d.label}
                  </button>
                ))}
              </div>
            </>
          )}

          {item.kind === "fill" && (
            <>
              <Stepper label="Angle" value={Math.round((p.angle_deg as number | undefined) ?? 45)} step={5} min={0} max={179} digits={0} suffix="°" onCommit={(v) => set({ angle_deg: v })} title="Direction of the rows" />
              <div className="btn-row">
                <Cmd id="object.angle" label="Draw the angle (I)" />
              </div>
              <Stepper label="Length" value={(p.stitch_mm as number | undefined) ?? 3.5} step={0.1} min={1} max={8} digits={1} suffix="mm" onCommit={(v) => set({ stitch_mm: v })} title="Stitch length along each row" />
              <Stepper label="Random" value={(p.random_pct as number | undefined) ?? 0} step={5} min={0} max={50} digits={0} suffix="%" onCommit={(v) => set({ random_pct: v })} title="Moves the needle points a little at random, so no lines show across the fill" />
            </>
          )}

          {(item.kind === "satin" || item.kind === "fill") &&
            (p.pull_comp_mm == null ? (
              <div className="toggle-row">
                <span className="stepper-label">Edge pad</span>
                <button aria-pressed onClick={() => set({ pull_comp_mm: 0.2 })} title="Pull compensation, chosen from the fabric and width. Click to set it yourself.">
                  Auto
                </button>
              </div>
            ) : (
              <div className="toggle-row">
                <Stepper label="Edge pad" value={p.pull_comp_mm as number} step={0.05} min={0} max={2} suffix="mm" onCommit={(v) => set({ pull_comp_mm: v })} title="Pull compensation: widens the shape because stitches pull the fabric in" />
                <button onClick={() => set({ pull_comp_mm: undefined })} title="Let LUDD choose from the fabric and width">
                  Auto
                </button>
              </div>
            ))}

          {item.kind === "fill" && <Check label="Sew from the other end (reverse)" checked={!!p.reverse} onChange={(v) => set({ reverse: v })} />}
          {item.kind === "satin" && (
            <>
              <Check label="Split long stitches" checked={!!p.split_mm} onChange={(v) => set({ split_mm: v ? 7 : 0 })} hint="Wide satins get stitches that can snag; this splits them into shorter ones" />
              {!!p.split_mm && <Stepper label="Longest" value={p.split_mm as number} step={0.5} min={2} max={12} digits={1} suffix="mm" onCommit={(v) => set({ split_mm: v })} />}
            </>
          )}

          {item.kind === "applique" && (
            <>
              <ol className="applique-steps">
                <li>Placement line, then the machine stops: lay your fabric over it.</li>
                <li>Tack-down, then it stops: trim the fabric close to the stitching.</li>
                <li>A satin border covers the edge.</li>
              </ol>
              <Stepper label="Border" value={(p.cover_width_mm as number | undefined) ?? 3} step={0.5} min={1} max={8} digits={1} suffix="mm" onCommit={(v) => set({ cover_width_mm: v })} title="Width of the satin border" />
              <Stepper label="Density" value={spacing} step={0.05} min={0.2} max={1.5} suffix="mm" onCommit={(v) => set({ spacing_mm: v })} />
              <div className="seg" role="group" aria-label="Tack-down">
                {(["zigzag", "run"] as const).map((t) => (
                  <button key={t} aria-pressed={(p.tack ?? "zigzag") === t} onClick={() => set({ tack: t })} title={t === "zigzag" ? "A narrow zigzag holds the edge firmly" : "A straight line: quicker, for felt and other fabrics that don't fray"}>
                    {t === "zigzag" ? "Zigzag tack-down" : "Straight tack-down"}
                  </button>
                ))}
              </div>
              <Check label="Sew a placement line first" checked={(p.placement as boolean | undefined) ?? true} onChange={(v) => set({ placement: v })} hint="Untick for pieces cut beforehand and placed by eye" />
              <button className="wide" onClick={() => void saveAppliqueSvg()} title="The piece's outline at real size, for a cutting machine or to print and cut">
                Save cut file (SVG)…
              </button>
            </>
          )}

          <div className="toggle-row">
            <Check label="Lock stitches at start" checked={(p.tie_in as boolean | undefined) ?? true} onChange={(v) => set({ tie_in: v })} />
            <Check label="at end" checked={(p.tie_off as boolean | undefined) ?? true} onChange={(v) => set({ tie_off: v })} />
          </div>
        </>
      )}

      {tab === "shape" && (
        <>
          <SizeFields id={item.id} info={info} />
          <div className="btn-row">
            <Cmd id="arrange.rotateCcw" label="⟲ 90°" />
            <Cmd id="arrange.rotateCw" label="⟳ 90°" />
            <Cmd id="arrange.mirrorX" label="⇋ Mirror" />
            <Cmd id="arrange.mirrorY" label="⇵ Flip" />
          </div>
          <div className="btn-row">
            <Cmd id="arrange.duplicate" label="Duplicate" />
            <Cmd id="arrange.repeat" label="Repeat…" />
            <Cmd id="draw.continue" label="Add points (K)" />
            {(item.kind === "fill" || item.kind === "applique") && <Cmd id="object.hole" label="Add a hole (O)" />}
          </div>
          <div className="btn-row">
            <button aria-pressed={pinned} onClick={() => setItemPinned(item.id, !pinned)} title="A pinned shape can't be moved by dragging (its settings still change)">
              📌 {pinned ? "Pinned" : "Pin in place"}
            </button>
            <Cmd id="arrange.delete" label="Remove" />
          </div>
          <p className="hint">Drag a point to reshape; right-click a point to switch it between curve, straight and sharp corner; double-click the outline to add a point.</p>
        </>
      )}
      <ThreadPickerFor open={picking} current={item.thread} onPick={(t) => setObjectThread(item.id, t)} onClose={() => setPicking(false)} />
    </section>
  );
}

/** Thread picker for a drawn object (reuses the panel's picker by pointing it at the object's color block). */
function ThreadPickerFor({ open, onClose, onPick, current }: { open: boolean; onClose: () => void; onPick: (t: Thread) => void; current: Thread }) {
  return <ThreadPicker index={open ? -1 : null} onClose={onClose} onPick={onPick} current={current} />;
}

/** A reference picture: opacity, lock, real-size measurement. */
function SelectedPicture({ img }: { img: RefImage }) {
  const units = useStore((s) => s.units);
  const measure = useStore((s) => s.measure);
  const setMeasure = useStore((s) => s.setMeasure);
  const measuring = measure?.imageId === img.id;
  const pts = measuring ? measure.points : [];
  const measured = pts.length === 2 ? Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]) : 0;
  return (
    <section className="selected">
      <h3>{img.name}</h3>
      <label className="slider">
        See-through <strong>{Math.round((1 - img.opacity) * 100)}%</strong>
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.05}
          defaultValue={img.opacity}
          key={`${img.id}-${img.opacity}`}
          onPointerUp={(e) => setPicture(img.id, { opacity: Number((e.target as HTMLInputElement).value) })}
          onKeyUp={(e) => setPicture(img.id, { opacity: Number((e.target as HTMLInputElement).value) })}
        />
      </label>
      <div className="btn-row">
        <button onClick={() => setPicture(img.id, { locked: !img.locked })} aria-pressed={img.locked}>
          📌 {img.locked ? "Pinned to the board" : "Pin to the board"}
        </button>
        <button onClick={() => setPicture(img.id, { visible: !img.visible })}>{img.visible ? "Hide" : "Show"}</button>
      </div>
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
          ? "Pinned: it can't move, and clicks go through it so you can draw over it. Unpin it here or with 📌 in the Pictures list."
          : "Drag to move; drag a corner to resize. Pin it once it's where you want it."}{" "}
        Saved inside your project.
      </p>
      <div className="btn-row">
        <Cmd id="arrange.delete" label="Remove picture" />
      </div>
    </section>
  );
}

/** Everything in sewing order: designs and drawn shapes, plus the pictures underneath. */
function Contents() {
  const layout = useStore(selectLayout);
  const images = useStore(selectImages);
  const design = useStore((s) => s.design);
  const selectedId = useStore((s) => s.selectedId);
  const select = useStore((s) => s.select);
  const [orderOpen, toggleOrder] = useFold("order");
  const [picsOpen, togglePics] = useFold("pictures");
  if (!layout) return null;
  const many = layout.items.length > 1 || layout.items.some((it) => isObject(it) || isText(it));
  return (
    <>
      {many && (
        <section>
          <FoldTitle open={orderOpen} onToggle={toggleOrder}>
            Sewing order ({layout.items.length})
          </FoldTitle>
          {orderOpen && (
          <ol className="design-list">
            {layout.items.map((it, i) => (
              <li key={it.id} className={it.id === selectedId ? "current" : undefined}>
                <span className="swatch small" style={{ background: isObject(it) || isText(it) ? it.thread.color : "transparent" }}>
                  {isText(it) ? "A" : isObject(it) ? "" : "🧵"}
                </span>
                <button className="name" onClick={() => select(it.id === selectedId ? null : it.id)}>
                  {i + 1}. {design?.items?.[i]?.name ?? itemLabel(it, i)}
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
                <button aria-label="Sew earlier" title="Sew earlier" disabled={i === 0} onClick={() => void commit(reorder(layout, it.id, -1))}>
                  ↑
                </button>
                <button aria-label="Sew later" title="Sew later" disabled={i === layout.items.length - 1} onClick={() => void commit(reorder(layout, it.id, 1))}>
                  ↓
                </button>
              </li>
            ))}
          </ol>
          )}
        </section>
      )}
      {images.length > 0 && (
        <section>
          <FoldTitle open={picsOpen} onToggle={togglePics}>
            Pictures ({images.length})
          </FoldTitle>
          {picsOpen && (
          <ul className="design-list">
            {images.map((im) => (
              <li key={im.id} className={im.id === selectedId ? "current" : undefined}>
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
            ))}
          </ul>
          )}
        </section>
      )}
    </>
  );
}

export function InfoPanel() {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const images = useStore(selectImages);
  const playhead = useStore((s) => s.playhead);
  const stitchIdx = useStore((s) => s.stitchIdx);
  const selectedId = useStore((s) => s.selectedId);
  const hoop = useStore(selectHoop);
  const engine = useStore((s) => s.engine);
  const units = useStore((s) => s.units);
  const hasMine = useStore((s) => s.charts.some((c) => c.mine && c.count > 0));
  const [picking, setPicking] = useState<number | null>(null);
  const [matching, setMatching] = useState(false);
  const [threadsOpen, toggleThreads] = useFold("threads");
  if (!layout) return null;

  const picture = images.find((im) => im.id === selectedId);
  const selIndex = layout.items.findIndex((it) => it.id === selectedId);
  const selItem = selIndex >= 0 ? layout.items[selIndex] : layout.items.length === 1 && !picture ? layout.items[0] : null;
  const selInfo = selItem ? design?.items?.[layout.items.indexOf(selItem)] : undefined;

  const header = design ? (
    <>
      <h2 title={design.path}>{design.name}</h2>
      {hoop && <p className={`fit fit-${hoopFit(design.info, hoop)}`}>{FIT_TEXT[hoopFit(design.info, hoop)](hoop.name)}</p>}
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
      <details className="more">
        <summary>More details</summary>
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
      </details>
    </>
  ) : (
    <>
      <h2>{layout.title || "New design"}</h2>
      <p className="hint">
        Nothing stitched yet. Pick a tool on the left (Line, Satin or Fill) and click on the canvas to draw. Add a picture to trace with{" "}
        <kbd>{formatShortcut(command("file.picture").shortcut)}</kbd>.
      </p>
    </>
  );

  const sewing = playhead > 0 && playhead < stitchIdx.length;
  const currentBlock = design && sewing ? blockAt(design, visibleRecords(stitchIdx, playhead, design.records.kind.length) - 1) : -1;

  return (
    <aside className="info-panel">
      {header}
      <FabricPicker />
      <AdvisorPanel />

      <SelectionBar />
      {picture && <SelectedPicture img={picture} />}
      {selItem && selInfo && (isObject(selItem) ? (
        <SelectedObject item={selItem} info={selInfo} />
      ) : isText(selItem) ? (
        <SelectedText item={selItem} info={selInfo} />
      ) : (
        <SelectedFile item={selItem as FileItem} info={selInfo} />
      ))}
      <Contents />
      <Checks />

      {design && (
        <>
          <div className="threads-head">
            <FoldTitle open={threadsOpen} onToggle={toggleThreads}>
              Threads, in sewing order
            </FoldTitle>
            <button onClick={() => setMatching(true)} disabled={!engine} title="Find the closest of your threads (or a brand's) for every color">
              {hasMine ? "Match to mine…" : "Match…"}
            </button>
            <Menu
              label="Color options"
              items={[
                { id: "colors.merge", checked: layout.merge_colors },
                { id: "colors.sort", checked: layout.color_sort },
                ...(hasRecolors(layout) ? [{ id: "colors.reset" }] : []),
              ]}
            />
          </div>
          {threadsOpen && (
          <ol className="threads">
            {design.blocks.map((b, i) => {
              const t = design.threads[b.thread];
              const was = b.original && b.original.color.toLowerCase() !== t.color.toLowerCase() ? b.original : null;
              const sub = [t.brand, t.catalog].filter(Boolean).join(" ");
              const basting = !b.sources?.length;
              return (
                <li key={i} className={i === currentBlock ? "current" : undefined}>
                  <span className="swatch" style={{ background: t.color }} />
                  <span className="num">{i + 1}</span>
                  <span className="tname">
                    {t.name || t.color}
                    {sub && <small>{sub}</small>}
                    {was && <small className="was">was {was.name || was.color}</small>}
                  </span>
                  {!basting && (
                    <>
                      <button className="edit" onClick={() => setPicking(i)} disabled={!engine} aria-label={`Change thread ${i + 1}`} title="Change thread">
                        ✎
                      </button>
                      <button
                        className="edit"
                        onClick={() => deleteColorBlock(i)}
                        disabled={!engine || design.blocks.length < 2}
                        aria-label={`Remove color ${i + 1}`}
                        title="Remove this color's stitches (Ctrl+Z to undo)"
                      >
                        🗑
                      </button>
                    </>
                  )}
                </li>
              );
            })}
          </ol>
          )}
        </>
      )}
      <ThreadPicker index={picking} onClose={() => setPicking(null)} />
      <MatchAllDialog open={matching} onClose={() => setMatching(false)} />
    </aside>
  );
}
