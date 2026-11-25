/** "Don't sew what's hidden under shapes on top" (P4-A2): its setting, shown in the design panel
 *  under "Fewer jumps & trims" while it's on. */
import { useState } from "react";
import { KEEP_MM, keepInRange, keepUnderEdge, setKeepUnderEdge, toggleRemoveOverlap } from "../feat/overlap";
import { selectLayout, useStore } from "../store";
import { Sub } from "./Accordion";
import { Check, fmtLen, fromUnits, NumberField, toUnits } from "./controls";

export function OverlapOptions() {
  const layout = useStore(selectLayout);
  const units = useStore((s) => s.units);
  // Redraws the box when a typed value changes nothing (it was out of range), so it shows what's used.
  const [redraw, setRedraw] = useState(0);
  if (!layout?.remove_overlap?.enabled) return null;
  const keep = keepUnderEdge(layout);
  const set = (v: number) => {
    const mm = keepInRange(fromUnits(v, units));
    if (Math.abs(mm - keep) < 0.005) setRedraw((n) => n + 1);
    else void setKeepUnderEdge(mm);
  };
  return (
    <div className="overlap-options">
      <Check
        label="Don't sew what's hidden under shapes on top"
        checked
        onChange={() => void toggleRemoveOverlap()}
        hint="Fills leave out what shapes sewn later cover, so overlaps don't sew thick and hard"
      />
      <Sub id="design-overlap" title="More options">
        <div className="size-row">
          <NumberField key={redraw} label="Keep under the edge" value={toUnits(keep, units)} suffix={units} digits={units === "in" ? 3 : 2} onCommit={set} />
        </div>
        <p className="hint">
          How far the fill below keeps sewing under the edge of a shape on top ({fmtLen(KEEP_MM.min, units)} to {fmtLen(KEEP_MM.max, units)}). If a gap shows there, raise it.
        </p>
      </Sub>
    </div>
  );
}
