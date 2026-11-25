/**
 * Stitch editing: insert a stitch, insert a jump, lock both sides of a jump (P4-B4). Each adds an
 * edit to the stitch file, which the engine makes before the other edits (layout/files.py), so
 * later moves and deletes can name an inserted stitch by its number.
 */
import { commit, currentLayout, engine, fail, info, whenIdle } from "../actions";
import { Kind, type Design, type FileItem, type Layout, type LayoutItemInfo, type LayoutOp } from "../design/types";
import { toDesignFrame } from "../features";
import { useStore } from "../store";
import { isRepairOp, isStitchFile } from "./repair/steps";

/** The one stitch picked while editing stitches, as it is on screen. */
type Picked = { layout: Layout; item: FileItem; shown: LayoutItemInfo; design: Design; owner: number; number: number; at: number };

function say(text: string): null {
  info(text);
  return null;
}

function picked(): Picked | null {
  const s = useStore.getState();
  const layout = s.history.present?.layout;
  const design = s.design;
  const owner = layout?.items.findIndex((it) => it.id === s.stitchEdit?.id) ?? -1;
  const item = layout?.items[owner];
  const shown = design?.items?.[owner];
  const owners = design?.records.item;
  const numbers = design?.records.src;
  if (!s.stitchEdit || !layout || !design || !owners || !numbers || !item || !isStitchFile(item) || !shown) return null;
  // Stitches a repair or a lock added have no number (-1): a box round a locked stitch takes some in.
  const chosen = new Set(s.stitchEdit.selected.filter((n) => n >= 0));
  if (!chosen.size && s.stitchEdit.selected.length) return say("A repair or a lock made that stitch, so it can't be edited. Pick one of the file's stitches.");
  if (chosen.size !== 1) return say("Select one stitch first: click it.");
  const [number] = chosen;
  const at = design.records.kind.findIndex((k, i) => k === Kind.Stitch && owners[i] === owner && numbers[i] === number);
  return at < 0 ? say("That stitch isn't on the design any more: select it again.") : { layout, item, shown, design, owner, number, at };
}

/** The record after which the picked stitch is done with: past its lock stitches, if it's locked.
 *  A lock is three added stitches, the third back on the stitch (layout/files.py). */
function pastLock({ design, owner, at }: Picked): number {
  const { x, y, kind, item, src } = design.records;
  const added = (i: number) => kind[i] === Kind.Stitch && item![i] === owner && src![i] < 0;
  const back = (i: number) => Math.abs(x[i] - x[at]) < 0.015 && Math.abs(y[i] - y[at]) < 0.015;
  let end = at;
  while (added(end + 1) && added(end + 2) && added(end + 3) && back(end + 3)) end += 3;
  return end;
}

/** The next stitch on screen after the picked one (and its lock) in its color, and whether the
 *  needle jumps on the way (even if no stitch comes after the jump). */
function ahead(p: Picked): { next: number | null; jumps: boolean } {
  const { design, owner } = p;
  const { kind, item } = design.records;
  let jumps = false;
  for (let i = pastLock(p) + 1; i < kind.length && kind[i] !== Kind.ColorChange && kind[i] !== Kind.End && item![i] === owner; i++) {
    if (kind[i] === Kind.Stitch) return { next: i, jumps };
    jumps ||= kind[i] === Kind.Jump;
  }
  return { next: null, jumps };
}

/** A point on the design (mm) in the stitch file's own frame, where stitch edits are kept. */
function inFile({ item, shown }: Picked, x: number, y: number): [number, number] {
  const t = item.transform;
  const [cx, cy] = shown.center_mm; // where the file's middle is on the hoop: its own middle, moved by (t.x, t.y)
  const [dx, dy] = toDesignFrame(t, x - cx, y - cy);
  const round = (v: number) => Math.round(v * 1000) / 1000 || 0; // (never -0)
  return [round(cx - t.x + dx), round(cy - t.y + dy)];
}

// ---------------------------------------------------------------- a new stitch's number

const highestShown = (design: Design, owner: number): number =>
  (design.records.src ?? []).reduce((top, n, i) => (design.records.item![i] === owner && n > top ? n : top), -1);

/** The stitch numbers an edit names (their stitches may not be on screen any more). */
function namedBy(o: LayoutOp): number[] {
  switch (o.op) {
    case "delete_stitches":
    case "move_stitches":
      return o.indices;
    case "move_stitch":
      return [o.index];
    case "insert_stitch":
      return [o.after, o.index];
    case "insert":
    case "insert_jump":
    case "lock_jump":
      return [o.after];
    default:
      return [];
  }
}

/** Edits that can take stitches off the screen without naming them. */
const hidesStitches = (o: LayoutOp) => o.op === "delete_block" || o.op === "rebuild" || o.op === "density_limit" || o.op === "remove_hidden";

/** Whether LUDD sews the stitch file from its own copy of it (the engine's rule, kept.has_edits). */
const keepsCopy = (item: FileItem) => item.threads.some(Boolean) || item.ops.some((o) => !isRepairOp(o) && o.op !== "jumps_to_trims");

/** The highest number among the file's own stitches: it's drawn with no edit that hides any. */
async function highestInFile({ layout, item }: Picked): Promise<number> {
  const bare: FileItem = { ...item, ops: item.ops.filter((o) => !isRepairOp(o) && o.op !== "delete_block") };
  // Drawn without that copy, a newer file on disk would take its place: an edit that does nothing keeps it.
  if (keepsCopy(item) && !keepsCopy(bare)) bare.ops = [...bare.ops, { op: "delete_stitches", indices: [] }];
  const design = await engine().call<Design>("layout.render", { layout: { ...layout, items: [bare] } }, 60_000);
  return highestShown(design, 0);
}

/** One past the highest stitch number in use on the file, counting inserted stitches. */
async function nextNumber(p: Picked): Promise<number> {
  const named = p.item.ops.flatMap(namedBy).filter(Number.isInteger);
  let top = named.reduce((a, b) => Math.max(a, b), highestShown(p.design, p.owner));
  if (p.item.ops.some(hidesStitches)) top = Math.max(top, await highestInFile(p));
  return top + 1;
}

// ---------------------------------------------------------------- the commands

/** Add an edit to the picked stitch file, unless it changed while the edit was worked out. */
async function addEdit(p: Picked, op: LayoutOp): Promise<boolean> {
  const layout = currentLayout();
  if (!layout || layout.items.find((it) => it.id === p.item.id) !== p.item) {
    info("The design changed meanwhile: try again.");
    return false;
  }
  return commit({ ...layout, items: layout.items.map((it) => (it.id === p.item.id ? { ...p.item, ops: [...p.item.ops, op] } : it)) });
}

let busy = false;
/** One at a time, each on the design as the last one left it (a held key repeats). */
async function oneAtATime(edit: () => Promise<unknown>): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    await whenIdle();
    await edit();
  } catch (err) {
    fail(err);
  } finally {
    busy = false;
  }
}

/** A stitch halfway to the next one, selected, ready to drag. */
export const insertStitchNow = () =>
  oneAtATime(async () => {
    const p = picked();
    if (!p) return;
    const { next } = ahead(p);
    if (next === null) return info("That's the last stitch of its color: select the one before it.");
    const { x, y } = p.design.records;
    const [x_mm, y_mm] = inFile(p, (x[p.at] + x[next]) / 2, (y[p.at] + y[next]) / 2);
    const index = await nextNumber(p);
    if (!(await addEdit(p, { op: "insert_stitch", after: p.number, index, x_mm, y_mm }))) return;
    const s = useStore.getState();
    if (s.stitchEdit?.id !== p.item.id) return; // done editing meanwhile
    s.setStitchEdit({ ...s.stitchEdit, selected: [index] });
    const owner = s.history.present?.layout.items.findIndex((it) => it.id === p.item.id) ?? -1;
    const there = s.design?.records.src?.some((n, i) => n === index && s.design!.records.item![i] === owner);
    info(there ? "Added a stitch halfway to the next one: drag it where you want it. Ctrl+Z undoes it." : "The new stitch doesn't show: a repair on this design takes it out.");
  });

/** The move from the stitch to the next one becomes a jump. */
export const insertJumpNow = () =>
  oneAtATime(async () => {
    const p = picked();
    if (!p) return;
    const { next, jumps } = ahead(p);
    if (jumps) return info("The move after that stitch is a jump already.");
    if (next === null) return info("That's the last stitch of its color: there's no move after it to make a jump.");
    if (await addEdit(p, { op: "insert_jump", after: p.number })) {
      info("The move to the next stitch is now a jump. To cut the thread there safely, lock both sides of it. Ctrl+Z undoes it.");
    }
  });

/** Three short lock stitches before the jump after the stitch, and three after it. */
export const lockJumpNow = () =>
  oneAtATime(async () => {
    const p = picked();
    if (!p) return;
    if (p.item.ops.some((o) => o.op === "lock_jump" && o.after === p.number)) return info("That jump is locked already.");
    if (!ahead(p).jumps) return info("Select the last stitch before a jump, then lock both sides of it.");
    if (await addEdit(p, { op: "lock_jump", after: p.number })) info("Locked both sides of the jump, so the thread can be cut there. Ctrl+Z undoes it.");
  });

export const insertStitch = (): void => void insertStitchNow();
export const insertJump = (): void => void insertJumpNow();
export const lockJump = (): void => void lockJumpNow();
