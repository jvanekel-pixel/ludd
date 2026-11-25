/** The right panel for a stitch file placed in the layout. */
import { commit, currentLayout } from "../actions";
import { updateTransform } from "../design/layout";
import type { FileItem, LayoutItemInfo } from "../design/types";
import { useStore } from "../store";
import { Row, Section, Sub, type SelKind } from "./Accordion";
import { Cmd, fromUnits, NumberField, SizeFields, toUnits } from "./controls";

/** A stitch file placed in the layout: its size, then rotation and position tucked inside. */
export function FileSections({ item, info, sel }: { item: FileItem; info: LayoutItemInfo; sel: SelKind }) {
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
