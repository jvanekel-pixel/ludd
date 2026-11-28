/**
 * Branches (shapes sewn as one path, P7-B2) in the layout: keeping them whole through every edit
 * and copy, and listing their shapes in the order they sew.
 */
import { newId } from "./ids";
import type { BranchInfo, Layout, LayoutItem } from "./types";

/** An item's branch id (drawn shapes and lettering can carry one; stitch files can't). */
export const branchOf = (it: LayoutItem): string | undefined => (it as { branch?: string }).branch;

/** The item in the branch `b`, or in none. */
export function inBranch(it: LayoutItem, b: string | undefined): LayoutItem {
  const { branch: _old, ...rest } = it as LayoutItem & { branch?: string };
  return (b ? { ...rest, branch: b } : rest) as LayoutItem;
}

const membersPerBranch = (items: readonly LayoutItem[]) => {
  const count = new Map<string, number>();
  for (const it of items) {
    const b = branchOf(it);
    if (b) count.set(b, (count.get(b) ?? 0) + 1);
  }
  return count;
};

/** A branch left with one shape (or none) is no branch: that shape loses the id and the branch its
 *  dots. The same layout when there's nothing to dissolve. Every edit goes through this. */
export function dissolveSingles(layout: Layout): Layout {
  const count = membersPerBranch(layout.items);
  const gone = (b: string | undefined) => !!b && (count.get(b) ?? 0) < 2;
  const dots = Object.entries(layout.branches ?? {});
  if (!layout.items.some((it) => gone(branchOf(it))) && !dots.some(([b]) => gone(b))) return layout;
  const items = layout.items.map((it) => (gone(branchOf(it)) ? inBranch(it, undefined) : it));
  const kept = dots.filter(([b]) => !gone(b));
  const { branches: _old, ...rest } = layout;
  return kept.length ? { ...rest, items, branches: Object.fromEntries(kept) } : { ...rest, items };
}

/** A copy to add: what it copies, and where it would go by itself (after that item, or at the end). */
export type NewCopy = { item: LayoutItem; source: string; after: string | null };

/**
 * The layout with these copies added (Paste, Duplicate and Repeat), keeping branches whole:
 * - one shape of a branch copied: the copy (Repeat: every copy) joins that branch, sewn right
 *   after its last shape; into a design without that branch, the copy is an ordinary shape;
 * - two or more shapes of one branch copied: their copies make a new branch of their own, without
 *   the dots set by hand, sewn together (never in the middle of the original);
 * - anything else goes where it would by itself.
 */
export function addCopies(layout: Layout, copies: readonly NewCopy[]): Layout {
  const sources = new Map<string, Set<string>>();
  for (const c of copies) {
    const b = branchOf(c.item);
    if (b) sources.set(b, (sources.get(b) ?? new Set()).add(c.source));
  }
  const lastMember = (b: string) => [...layout.items].reverse().find((it) => branchOf(it) === b)?.id ?? null;
  const isMember = (id: string | null, b: string) => layout.items.some((it) => it.id === id && branchOf(it) === b);
  const own = new Map<string, { id: string; after: string | null }>();
  const placed = copies.map((c) => {
    const b = branchOf(c.item);
    if (!b) return { item: c.item, after: c.after };
    if (sources.get(b)!.size > 1) {
      let mine = own.get(b);
      if (!mine) own.set(b, (mine = { id: `b${newId()}`, after: isMember(c.after, b) ? lastMember(b) : c.after }));
      return { item: inBranch(c.item, mine.id), after: mine.after };
    }
    const last = lastMember(b);
    return last ? { item: c.item, after: last } : { item: inBranch(c.item, undefined), after: c.after };
  });
  const known = new Set(layout.items.map((it) => it.id));
  const items = layout.items.flatMap((it) => [it, ...placed.filter((p) => p.after === it.id).map((p) => p.item)]);
  items.push(...placed.filter((p) => p.after === null || !known.has(p.after)).map((p) => p.item));
  return { ...layout, items };
}

/** The item a new shape that is neither a piece nor a copy of a branch's shape is sewn after, so it
 *  doesn't land between a branch's shapes: `id`, or, when `id` is a shape of a branch with more of
 *  it sewn later, the branch's last shape. */
export function afterBranch(items: readonly LayoutItem[], id: string): string {
  const at = items.findIndex((it) => it.id === id);
  const b = at < 0 ? undefined : branchOf(items[at]);
  if (!b) return id;
  for (let k = items.length - 1; k > at; k--) if (branchOf(items[k]) === b) return items[k].id;
  return id;
}

/** `after` (the same items in a new order) with each branch whose shapes sat together in `before`
 *  sitting together again, in the order they had, where the first of them comes in `after`. */
export function keepBranchesTogether(before: readonly LayoutItem[], after: readonly LayoutItem[]): LayoutItem[] {
  const together = new Map<string, LayoutItem[]>();
  for (const b of new Set(before.map(branchOf))) {
    const spots = before.flatMap((it, i) => (b && branchOf(it) === b ? [i] : []));
    if (b && spots[spots.length - 1] - spots[0] === spots.length - 1) together.set(b, spots.map((i) => before[i]));
  }
  const done = new Set<string>();
  return after.flatMap((it) => {
    const b = branchOf(it);
    const members = b ? together.get(b) : undefined;
    if (!members) return [it];
    if (done.has(b!)) return [];
    done.add(b!);
    return members.map((m) => after.find((x) => x.id === m.id) ?? m);
  });
}

/** The items as the list shows them: each branch's shapes in the order the last render sewed
 *  them (the engine chooses it), everything else as in the layout. */
export function inSewingOrder(items: readonly LayoutItem[], branches: readonly BranchInfo[] | undefined): LayoutItem[] {
  const out = [...items];
  for (const b of branches ?? []) {
    const rank = new Map(b.items.map((id, k) => [id, k]));
    const spots = out.flatMap((it, i) => (rank.has(it.id) ? [i] : []));
    const members = spots.map((i) => out[i]).sort((x, y) => rank.get(x.id)! - rank.get(y.id)!);
    spots.forEach((i, k) => (out[i] = members[k]));
  }
  return out;
}

/**
 * The layout after a row is dragged or stepped to place `to` of the list as shown (`rows`, from
 * inSewingOrder). Outside branches that is its place in the layout too. A branch the shape stays
 * in, or lands in the middle of, takes the order shown, so what the user put before and after it
 * stays before and after it; other branches keep the layout's order.
 */
export function moveShown(layout: Layout, rows: readonly LayoutItem[], id: string, to: number): Layout {
  const from = rows.findIndex((it) => it.id === id);
  const at = Math.max(0, Math.min(rows.length - 1, Math.round(to)));
  if (from < 0 || at === from) return layout;
  const moved = rows.filter((it) => it.id !== id);
  moved.splice(at, 0, rows[from]);
  const shownOrder = new Set<string>();
  const mine = branchOf(rows[from]);
  const beside = [moved[at - 1], moved[at + 1]].map((it) => it && branchOf(it));
  if (mine && beside.includes(mine)) shownOrder.add(mine); // still among its own branch
  if (beside[0] && beside[0] === beside[1]) shownOrder.add(beside[0]); // in the middle of one
  // Every other branch's shapes go back to the layout's order, in the places the rows give them.
  const queue = new Map<string, LayoutItem[]>();
  for (const it of layout.items) {
    const b = branchOf(it);
    if (b && !shownOrder.has(b) && it.id !== id) queue.set(b, [...(queue.get(b) ?? []), it]);
  }
  const items = moved.map((it) => {
    const b = branchOf(it);
    return b && it.id !== id && queue.get(b)?.length ? queue.get(b)!.shift()! : it;
  });
  return items.every((it, k) => it === layout.items[k]) ? layout : { ...layout, items };
}
