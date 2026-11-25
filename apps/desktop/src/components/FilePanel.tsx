/** The right panel for a stitch file placed in the layout. */
import { useEffect, useState } from "react";
import { commit, currentLayout } from "../actions";
import { updateTransform } from "../design/layout";
import type { FileItem, Layout, LayoutItemInfo, LayoutOp } from "../design/types";
import { isStitchFile, previewRepairs, removeRepair, repairLabel, repairOps, type RepairResults } from "../feat/repair/steps";
import { selectLayout, useStore } from "../store";
import { Row, Section, Sub, type SelKind } from "./Accordion";
import { Cmd, fromUnits, NumberField, SizeFields, toUnits } from "./controls";

/** Each repair that's on, by op name, and what it does: worked out a moment after the design
 *  changes (only while the list is on screen, as the engine draws the design to count). */
function useRepairLines(id: string): RepairResults["lines"] {
  const layout = useStore(selectLayout);
  const [done, setDone] = useState<{ layout: Layout; lines: RepairResults["lines"] } | null>(null);
  useEffect(() => {
    if (!layout) return;
    let stale = false;
    const timer = setTimeout(async () => {
      const item = layout.items.find((it) => it.id === id);
      if (!item || !isStitchFile(item)) return;
      try {
        const r = await previewRepairs(layout, id, repairOps(item), () => stale);
        if (r && !stale) setDone({ layout, lines: r.lines });
      } catch {
        // The repairs' names are shown without their results.
      }
    }, 300);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [layout, id]);
  return done && done.layout === layout ? done.lines : {};
}

/** The repairs that are on, each with what it does and ✕ to take it off. */
function ActiveRepairs({ id, ops }: { id: string; ops: LayoutOp[] }) {
  const lines = useRepairLines(id);
  return (
    <ul className="repair-list">
      {ops.map((o) => {
        const off = `Turn off ${repairLabel(o.op)}`;
        return (
          <li key={o.op}>
            <span title={repairLabel(o.op)}>{lines[o.op] || repairLabel(o.op)}</span>
            <button type="button" aria-label={off} title={off} onClick={() => void removeRepair(id, o.op)}>
              ✕
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** A stitch file placed in the layout: its size, then repairs, rotation and position tucked inside. */
export function FileSections({ item, info, sel }: { item: FileItem; info: LayoutItemInfo; sel: SelKind }) {
  const units = useStore((s) => s.units);
  const t = item.transform;
  const repairs = repairOps(item);
  // Same rule as the engine's warning: either axis more than 20% from the original, unless the
  // stitches are rebuilt at the new size.
  const tooFar = Math.max(Math.abs(t.scale_x - 1), Math.abs(t.scale_y - 1)) > 0.2 + 1e-9 && !repairs.some((o) => o.op === "rebuild");
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
      <Sub id="file-repair" title="Repair" summary={repairs.length ? `${repairs.length} on` : undefined}>
        <Row label="">
          <Cmd id="stitch.repair" label="Repair this design…" />
        </Row>
        {repairs.length > 0 && <ActiveRepairs id={item.id} ops={repairs} />}
      </Sub>
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
