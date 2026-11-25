/** Limit density for this fabric (P4-C3): the dialog's step and the direct command. Fills and
 *  satins denser than the design's "Stitching on" fabric takes are remade at its normal spacing
 *  (engine/threadline_engine/repair/density.py; the limits are in fabrics.py). */
import { registerRepairStep, toggleRepair, type Stats } from "./steps";

const one = (n: number) => (Math.round(n * 10) / 10).toFixed(1);

registerRepairStep({
  id: "density_limit",
  op: "density_limit",
  label: "Limit density for this fabric",
  hint:
    "Fills and satins sewn closer than the fabric you're stitching on takes are remade at its normal spacing " +
    "(the fabric is set under Stitching on). Less thread, less puckering.",
  visible: () => true,
  preset: () => false,
  make: () => ({ op: "density_limit" }),
  fields: [],
  summary: (after: Stats, before: Stats) =>
    after.stitches === before.stitches && after.densest === before.densest
      ? "Nothing here is denser than this fabric takes."
      : `Thickest spot: ${one(before.densest)} down to ${one(after.densest)} mm of thread per mm².`,
});

export const densityLimit = (): Promise<void> => toggleRepair("density_limit");
