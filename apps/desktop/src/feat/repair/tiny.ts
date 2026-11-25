/** Remove tiny stitches (P4-B2): the dialog's step and the direct command. */
import { registerRepairStep, toggleRepair } from "./steps";

registerRepairStep({
  id: "filter_small",
  op: "filter_small",
  label: "Remove tiny stitches",
  hint: "Takes out stitches too short to matter, which can make the machine nest thread. The lock stitches at each end of a thread stay.",
  visible: () => true,
  preset: () => false,
  make: (v) => ({ op: "filter_small", min_mm: v.min_mm }),
  fields: [{ key: "min_mm", label: "Shorter than", def: 0.4, min: 0.2, max: 1, step: 0.05, digits: 2, suffix: "mm", title: "A stitch closer than this to the one before it is taken out" }],
  summary: (after, before) => {
    const n = before.stitches - after.stitches;
    return n > 0 ? `${n} tiny stitch${n === 1 ? "" : "es"} removed` : "No stitches that short";
  },
});

export const filterSmall = (): void => void toggleRepair("filter_small");
