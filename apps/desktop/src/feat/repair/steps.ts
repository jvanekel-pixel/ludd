/**
 * The repairs a placed stitch file can have, as the "Repair this design" dialog shows them. A
 * repair is an edit (an op) on the item, applied when the design is drawn or saved: the file on
 * disk is never changed. An item holds at most one op of each repair, always written in
 * REPAIR_ORDER, so what is sewn never depends on which was ticked first.
 *
 * Each repair registers its step from its own file in feat/repair; cmd/repair.ts imports them all.
 */
import { commit, currentLayout, info, targetId } from "../../actions";
import type { Field } from "../../design/fillPatterns";
import type { FileItem, Layout, LayoutItemInfo, LayoutOp } from "../../design/types";
import { useStore } from "../../store";

/** What repair.preview counts (engine/threadline_engine/methods/repair.py), before or after. */
export type Stats = {
  stitches: number;
  trims: number;
  jumps: number;
  /** Very short stitches. */
  tiny: number;
  longest_mm: number;
  /** Thread (mm) per mm² in the worst 1 mm cell, as the quality checks measure it. */
  densest: number;
  /** The most needle hits in one spot. */
  hits_max: number;
};

export type RepairPreview = {
  before: Stats;
  after: Stats;
  /** The stitches taken out, as ranges of the item's stitch numbers (`src`), [from, to). */
  removed: [number, number][];
  added: number;
  /** The densest a spot should be, in the units of `densest`. */
  limit: number;
  notes: string[];
};

/** The order repair ops are written in (and the dialog lists them). */
export const REPAIR_ORDER = ["rebuild", "filter_small", "declump", "density_limit", "remove_hidden"] as const;

export type RepairStep = {
  /** The op's name ("rebuild", "density_limit"...): Fix it on a check names a step by it. */
  id: string;
  op: LayoutOp["op"];
  label: string;
  hint: string;
  visible(item: FileItem, info: LayoutItemInfo): boolean;
  /** Ticked when the dialog opens? */
  preset(item: FileItem, info: LayoutItemInfo): boolean;
  make(values: Record<string, number>): LayoutOp;
  fields: Field[];
  /** The result line, e.g. "212 tiny stitches removed". */
  summary(after: Stats, before: Stats): string;
};

const steps = new Map<string, RepairStep>();

/** Add a step (one with the same id is replaced); returns the function that takes it out again. */
export function registerRepairStep(step: RepairStep): () => void {
  steps.set(step.id, step);
  return () => {
    if (steps.get(step.id) === step) steps.delete(step.id);
  };
}

const rank = (name: string) => (REPAIR_ORDER as readonly string[]).indexOf(name);
export const isRepairOp = (o: LayoutOp) => rank(o.op) >= 0;

/** Every step, in REPAIR_ORDER. */
export function repairSteps(): RepairStep[] {
  return [...steps.values()].sort((a, b) => rank(a.op) - rank(b.op));
}

export const repairStep = (id: string): RepairStep | undefined => steps.get(id);

/** An item's repair ops. */
export const repairOps = (item: FileItem): LayoutOp[] => item.ops.filter(isRepairOp);

/** `ops` with their repairs replaced by `repairs`: the other edits keep their order, then the
 *  repairs, one of each (the last one given wins), in REPAIR_ORDER. */
export function withRepairs(ops: LayoutOp[], repairs: LayoutOp[]): LayoutOp[] {
  const byName = new Map(repairs.filter(isRepairOp).map((o) => [o.op, o]));
  return [...ops.filter((o) => !isRepairOp(o)), ...[...byName.values()].sort((a, b) => rank(a.op) - rank(b.op))];
}

/** `layout` with one item's repairs set to `repairs`. */
export function setItemRepairs(layout: Layout, id: string, repairs: LayoutOp[]): Layout {
  return { ...layout, items: layout.items.map((it) => (it.id === id ? { ...it, ops: withRepairs(it.ops, repairs) } : it)) };
}

/** The selected placed stitch file (or the only item, if it is one) and what the engine said about
 *  it. Null, with a notice saying why, if there's none. */
export function selectedStitchFile(): { layout: Layout; item: FileItem; shown: LayoutItemInfo | undefined } | null {
  const layout = currentLayout();
  const id = targetId();
  const item = layout?.items.find((it) => it.id === id);
  if (!layout || !item || (item.kind !== undefined && item.kind !== "file")) {
    info("Select a placed stitch file first: repairs work on stitch files, not on shapes or lettering.");
    return null;
  }
  return { layout, item: item as FileItem, shown: useStore.getState().design?.items?.find((i) => i.id === id) };
}

/** A direct repair command (Alt+Shift+S and the like): turn one repair on for the selected stitch
 *  file with its standard settings, or off if it's on. One undo step; the notice bar says what
 *  happened. */
export async function toggleRepair(stepId: string): Promise<void> {
  const step = steps.get(stepId);
  if (!step) return;
  const target = selectedStitchFile();
  if (!target) return;
  const { layout, item } = target;
  const mine = repairOps(item);
  const on = mine.some((o) => o.op === step.op);
  const standard = Object.fromEntries(step.fields.map((f) => [f.key, f.def]));
  const next = on ? mine.filter((o) => o.op !== step.op) : [...mine, step.make(standard)];
  if (await commit(setItemRepairs(layout, item.id, next))) {
    info(`${step.label}: ${on ? "off" : "on"}. Ctrl+Z undoes it.`);
  }
}

/** Open "Repair this design" for the selected stitch file (stitch.repair, and Fix it on a check,
 *  which passes the step to tick). */
export const openRepair = (_tick?: string): void => info("Not built yet");
