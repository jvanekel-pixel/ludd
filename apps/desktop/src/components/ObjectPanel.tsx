/** The right panel for a drawn shape. Its fill patterns and line styles come from the
 *  descriptors in design/fillPatterns.ts and design/lineStyles.ts. */
import { useState } from "react";
import { command, convertObject, hasOwnDefaults, resetDefaults, saveAppliqueSvg, setObjectParams, setObjectThread, setSatinWidth } from "../actions";
import { FILL_PATTERN_DEFS, fillPatternDef, type Field } from "../design/fillPatterns";
import { LINE_STYLE_DEFS, MOTIF_DEFS, MOTIF_FIELDS } from "../design/lineStyles";
import { isRibbon, type LayoutItemInfo, type ObjectItem, type Thread } from "../design/types";
import { useStore } from "../store";
import { Row, Section, Sub, type SelKind } from "./Accordion";
import { Check, Cmd, DensitySlider, fmtLen, SizeFields, Stepper, UnderlayButtons } from "./controls";
import { ThreadPicker } from "./ThreadDialogs";

const DENSITY = [
  { label: "Light", satin: 0.5, fill: 0.5 },
  { label: "Normal", satin: 0.4, fill: 0.4 },
  { label: "Dense", satin: 0.32, fill: 0.33 },
];

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

export const KIND_TITLE = { run: "Line", satin: "Satin", fill: "Fill", applique: "Applique" } as const;

/** The steppers a descriptor lists (a pattern's own settings, a motif's size). */
function FieldSteppers({ fields, p, set }: { fields: Field[]; p: Record<string, unknown>; set: (patch: Record<string, unknown>) => void }) {
  return (
    <>
      {fields.map((f) => (
        <Stepper key={f.key} label={f.label} value={(p[f.key] as number | undefined) ?? f.def} step={f.step} min={f.min} max={f.max} digits={f.digits} suffix={f.suffix} onCommit={(v) => set({ [f.key]: v })} title={f.title} />
      ))}
    </>
  );
}

/** A fill's pattern, and the one or two settings that pattern has. */
function PatternRows({ p, set }: { p: Record<string, unknown>; set: (patch: Record<string, unknown>) => void }) {
  const pattern = (p.pattern as string | undefined) ?? "tatami";
  const def = fillPatternDef(pattern);
  return (
    <>
      <Row label="Pattern" hint={FILL_PATTERN_DEFS.find((x) => x.id === pattern)?.title}>
        <select value={pattern} onChange={(e) => set({ pattern: e.target.value })} aria-label="Fill pattern">
          {FILL_PATTERN_DEFS.map((x) => (
            <option key={x.id} value={x.id} title={x.title}>
              {x.label}
            </option>
          ))}
        </select>
      </Row>
      <FieldSteppers fields={def.fields} p={p} set={set} />
      {def.hint && <p className="hint">{def.hint}</p>}
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
    { id: "center", label: "Center", title: "A run down the middle: for narrow columns" },
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
    const { summary, label } = fillPatternDef(p.pattern as string | undefined);
    if (summary) return summary === "label+density" ? `${label} · ${dens}` : label;
    return `${dens} · ${Math.round((p.angle_deg as number | undefined) ?? 45)}°`;
  }
  if (item.kind === "applique") return `${(p.cover_width_mm as number | undefined) ?? 3} mm border`;
  if (isRibbon(item)) return `${item.geometry.width_mm} mm wide · ${dens}`;
  return dens;
}

/** A drawn shape: its stitches (with Underlay and Advanced inside), then its size and points. */
export function ObjectSections({ item, info, sel }: { item: ObjectItem; info: LayoutItemInfo; sel: SelKind }) {
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
  const fillDef = item.kind === "fill" ? fillPatternDef(p.pattern as string | undefined) : undefined;
  const open = !!fillDef?.open; // rows settings do nothing for these
  const noRows = !!fillDef?.noSpacing; // ...and these ignore the spacing too
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
              {LINE_STYLE_DEFS.map((st) => (
                <button key={st.id} aria-pressed={(p.style ?? "single") === st.id} onClick={() => set({ style: st.id })} title={st.title}>
                  {st.label}
                </button>
              ))}
            </div>
          </Row>
        )}
        {item.kind === "run" && p.style === "motif" && (
          <>
            <Row label="Motif">
              <select value={(p.motif as string | undefined) ?? "wave"} onChange={(e) => set({ motif: e.target.value })} aria-label="Motif">
                {MOTIF_DEFS.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Row>
            <FieldSteppers fields={MOTIF_FIELDS} p={p} set={set} />
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
          {(item.kind === "run" || (item.kind === "fill" && !fillDef?.noLength)) && (
            <Stepper
              label="Length"
              value={(p.stitch_mm as number | undefined) ?? (item.kind === "fill" ? 3.5 : 2.5)}
              step={0.1}
              min={item.kind === "fill" ? 1 : 0.5}
              max={item.kind === "fill" ? (fillDef?.maxStitch ?? 7) : 12}
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
