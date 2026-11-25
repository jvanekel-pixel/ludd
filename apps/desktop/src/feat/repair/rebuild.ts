/** Rebuild a resized stitch file's stitches at its new size (P4-C2): the dialog's step and the
 *  direct command. The engine remakes its fills, satins and lines at the new size with their
 *  original spacing and stitch length (engine/threadline_engine/repair/rebuild.py). */
import type { FileItem } from "../../design/types";
import { registerRepairStep, toggleRepair, type Stats } from "./steps";

/** How far the item is resized, on its most resized side (0.5 = 50% bigger or smaller). */
const resized = (item: FileItem): number =>
  Math.max(Math.abs((item.transform?.scale_x ?? 1) - 1), Math.abs((item.transform?.scale_y ?? 1) - 1));

const count = (n: number) => Math.round(n).toLocaleString("en-US");

registerRepairStep({
  id: "rebuild",
  op: "rebuild",
  label: "Rebuild stitches at this size",
  hint:
    "Remakes the fills, satins and lines at the new size with their original spacing and stitch length, so they " +
    "are neither too dense nor too sparse. Anything else is resized as it is.",
  // Shown from 10% bigger or smaller; ticked from past 20%, where the resize warning starts.
  visible: (item) => resized(item) >= 0.1 - 1e-9,
  preset: (item) => resized(item) > 0.2 + 1e-9,
  make: () => ({ op: "rebuild" }),
  fields: [],
  summary: (after: Stats, before: Stats) => `Rebuilt at this size: ${count(before.stitches)} stitches became ${count(after.stitches)}.`,
});

export const rebuild = (): Promise<void> => toggleRepair("rebuild");
