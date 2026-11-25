/** Thin out spots the needle hits over and over (P4-B3): the dialog's step and the direct command. */
import { registerRepairStep, toggleRepair } from "./steps";

registerRepairStep({
  id: "declump",
  op: "declump",
  label: "Thin out dense spots",
  hint: "Where the needle goes into one spot over and over, takes out some of those stitches without changing the shape.",
  visible: () => true,
  preset: () => false,
  make: (v) => ({ op: "declump", max_hits: v.max_hits }),
  fields: [{ key: "max_hits", label: "Most needle hits in one spot", def: 5, min: 3, max: 10, step: 1, digits: 0, title: "A spot is a square half a millimeter across" }],
  summary: (after, before) => {
    const n = before.stitches - after.stitches;
    if (n <= 0) return `Nothing to thin out (most needle hits in one spot: ${after.hits_max})`;
    return `${n} stitch${n === 1 ? "" : "es"} taken out of crowded spots (most needle hits in one spot: ${before.hits_max} → ${after.hits_max})`;
  },
});

export const declump = (): void => void toggleRepair("declump");
