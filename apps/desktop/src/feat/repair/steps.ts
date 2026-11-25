/**
 * The repairs a placed stitch file can have, as the "Repair this design" dialog shows them. A
 * repair is an edit (an op) on the item, applied when the design is drawn or saved: the file on
 * disk is never changed. An item holds at most one op of each repair, always written in
 * REPAIR_ORDER, so what is sewn never depends on which was ticked first.
 *
 * Each repair registers its step from its own file in feat/repair; cmd/repair.ts imports them all.
 */
import { commit, currentLayout, engine, info, targetId } from "../../actions";
import type { Field } from "../../design/fillPatterns";
import type { Design, FileItem, Layout, LayoutItem, LayoutItemInfo, LayoutOp, QualityCheck } from "../../design/types";
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

/** The step that writes this repair op (each step's id is its op's name). */
const stepFor = (op: string): RepairStep | undefined => steps.get(op) ?? [...steps.values()].find((s) => s.op === op);

/** For a repair with no step registered, its command's title. */
const NAMES: Record<string, string> = {
  rebuild: "Rebuild stitches at this size",
  filter_small: "Remove tiny stitches",
  declump: "Thin out dense spots",
  density_limit: "Limit density for this fabric",
  remove_hidden: "Remove stitches hidden under what's on top",
};

export const repairLabel = (op: string): string => stepFor(op)?.label ?? NAMES[op] ?? op;

export const isStitchFile = (it: LayoutItem): it is FileItem => it.kind === undefined || it.kind === "file";

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
  if (!layout || !item || !isStitchFile(item)) {
    info("Select a placed stitch file first: repairs work on stitch files, not on shapes or lettering.");
    return null;
  }
  return { layout, item, shown: useStore.getState().design?.items?.find((i) => i.id === id) };
}

// ---------------------------------------------------------------- what repairs would do

const PREVIEW_MS = 120_000;

/** repair.preview: the design as it is, and with item `id`'s repairs replaced by `ops`. */
export const previewCall = (layout: Layout, id: string, ops: LayoutOp[]): Promise<RepairPreview> =>
  engine().call<RepairPreview>("repair.preview", { layout, item_id: id, ops }, PREVIEW_MS);

export type RepairResults = {
  /** The design as it is, and with all of `ops`. */
  preview: RepairPreview;
  /** Each repair's own result line, by op name. */
  lines: Partial<Record<LayoutOp["op"], string>>;
};

/**
 * What the repairs `ops` would do to item `id`, one at a time in REPAIR_ORDER, so each one's line
 * counts only its own change; the first is counted from the file without any repairs. Null if
 * `stale()` says the answer isn't wanted any more.
 */
export async function previewRepairs(layout: Layout, id: string, ops: LayoutOp[], stale: () => boolean = () => false): Promise<RepairResults | null> {
  const item = layout.items.find((it) => it.id === id);
  const chosen = withRepairs([], ops);
  let bare: Stats | null = null;
  if (chosen.length && item && isStitchFile(item) && repairOps(item).length) {
    bare = (await previewCall(layout, id, [])).after;
    if (stale()) return null;
  }
  const lines: RepairResults["lines"] = {};
  let last: RepairPreview | null = null;
  for (let k = 1; k <= chosen.length; k++) {
    const r: RepairPreview = await previewCall(layout, id, chosen.slice(0, k));
    if (stale()) return null;
    const op = chosen[k - 1].op;
    const line = stepFor(op)?.summary(r.after, last ? last.after : (bare ?? r.before));
    if (line) lines[op] = line;
    last = r;
  }
  last ??= await previewCall(layout, id, []);
  return stale() ? null : { preview: last, lines };
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
  if (!(await commit(setItemRepairs(layout, item.id, next)))) return;
  const said = `${step.label}: ${on ? "off" : "on"}. Ctrl+Z undoes it.`;
  info(said);
  if (on) return;
  // Then what it did, counted as the dialog counts it.
  try {
    const r = await previewCall(layout, item.id, next);
    if (!r || useStore.getState().notice?.text !== said) return;
    const did = step.summary(r.after, r.before);
    if (did || r.notes.length) info([`${step.label}: on${did ? `, ${did}` : ""}.`, ...r.notes, "Ctrl+Z undoes it."].join(" "));
  } catch {
    // The repair is on all the same.
  }
}

/** Take one of item `id`'s repairs off (the ✕ in the stitch file panel): one undo step. */
export async function removeRepair(id: string, op: LayoutOp["op"]): Promise<void> {
  const layout = currentLayout();
  const item = layout?.items.find((it) => it.id === id);
  if (!layout || !item || !isStitchFile(item) || !item.ops.some((o) => o.op === op)) return;
  if (await commit(setItemRepairs(layout, id, repairOps(item).filter((o) => o.op !== op)))) {
    info(`${repairLabel(op)}: off. Ctrl+Z undoes it.`);
  }
}

// ---------------------------------------------------------------- the dialog

/** What "Repair this design" was opened for: the stitch file, and a step to tick. */
let request: { id: string; tick?: string } | null = null;
export const repairRequest = () => request;

/** Open "Repair this design" for the selected stitch file (stitch.repair, and Fix it on a check,
 *  which passes the step to tick). */
export const openRepair = (tick?: string): void => {
  const target = selectedStitchFile();
  if (!target) return;
  if (!target.shown) return info("Wait for the design to be drawn, then try again.");
  request = { id: target.item.id, tick };
  useStore.getState().setDialog("repair");
};

// ---------------------------------------------------------------- Fix it on a check

/** The checks a repair can fix, and which repair. */
const FIXES: Record<string, string> = { short: "filter_small", needle_hits: "declump", dense: "density_limit" };
/** A check's spot is the middle of a 1 mm square, which can sit just outside a design's box. */
const SPOT_MM = 0.6;

export type CheckFix = { step: string; item: string };

/**
 * What "Fix it" on a check would open, or null if there's nothing to offer: a repair that can be
 * used, and a stitch file for it. That's the one whose box holds the check's spot (the one sewn
 * last, if several do), or else the only stitch file. Thick spots only count when they're in stitch
 * files alone (a note, not a warning).
 */
export function fixFor(check: QualityCheck, layout: Layout | null, design: Design | null): CheckFix | null {
  const step = FIXES[check.code] ? repairStep(FIXES[check.code]) : undefined;
  if (!step || !layout || !design || (check.code === "dense" && check.level !== "info")) return null;
  const files = layout.items.flatMap((item) => {
    const shown = isStitchFile(item) ? design.items?.find((i) => i.id === item.id) : undefined;
    return shown && step.visible(item as FileItem, shown) ? [{ id: item.id, box: shown.bounds_mm }] : [];
  });
  const at = check.at;
  const under = at
    ? files.filter(({ box }) => box && at[0] >= box[0] - SPOT_MM && at[0] <= box[2] + SPOT_MM && at[1] >= box[1] - SPOT_MM && at[1] <= box[3] + SPOT_MM)
    : [];
  const pick = under.length ? under[under.length - 1] : files.length === 1 ? files[0] : null;
  return pick ? { step: step.id, item: pick.id } : null;
}

export function openFix(fix: CheckFix): void {
  useStore.getState().select(fix.item);
  openRepair(fix.step);
}
