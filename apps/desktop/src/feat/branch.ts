/**
 * Branching (P7-B2): the Branch command sews the selected shapes as one path (the engine's
 * `layout.branch_plan` says whether it can, and in what order the items go), Take out removes
 * shapes from their branch, and a branch's green and red dots, dragged, are kept in
 * `layout.branches`. The dots themselves are drawn by canvas/branchOverlay.ts.
 */
import { commit, currentLayout, engine, fail, info } from "../actions";
import { branchOf, dissolveSingles, inBranch } from "../design/branches";
import { newId } from "../design/layout";
import type { BranchInfo, Layout, LayoutItem } from "../design/types";
import { useStore } from "../store";

type Plan = { ok: boolean; reason: string; order: string[] };

const round3 = (v: number) => Math.round(v * 1000) / 1000;

/** The selected items' ids, the first one picked first. */
function selectionIds(): string[] {
  const s = useStore.getState();
  return s.selectedId ? [s.selectedId, ...s.extraIds] : [];
}

/** The layout with the items in `order` (every item's id, from `layout.branch_plan`), the
 *  shapes `ids` given the branch id `bid`, and any branch this leaves with one member dissolved. */
export function branchedLayout(layout: Layout, order: string[], ids: string[], bid: string): Layout {
  const byId = new Map(layout.items.map((it) => [it.id, it]));
  const chosen = new Set(ids);
  const sorted = order.map((id) => byId.get(id)).filter((it): it is LayoutItem => !!it);
  // Anything the plan didn't name (it can't happen) keeps its place at the end, never lost.
  const named = new Set(order);
  const items = [...sorted, ...layout.items.filter((it) => !named.has(it.id))].map((it) => (chosen.has(it.id) ? inBranch(it, bid) : it));
  return dissolveSingles({ ...layout, items });
}

/** The layout with the shapes `ids` taken out of their branches (a branch left with one member
 *  is dissolved, and its dots with it). The same layout if none of them is in a branch. */
export function unbranchedLayout(layout: Layout, ids: string[]): Layout {
  const out = new Set(ids);
  if (!layout.items.some((it) => out.has(it.id) && branchOf(it))) return layout;
  const items = layout.items.map((it) => (out.has(it.id) && branchOf(it) ? inBranch(it, undefined) : it));
  return dissolveSingles({ ...layout, items });
}

/** The layout with a branch's green ("start") or red ("end") dot put at `at` (mm on the hoop). */
export function withBranchDot(layout: Layout, bid: string, which: "start" | "end", at: [number, number]): Layout {
  const old = layout.branches?.[bid] ?? {};
  const key = which === "start" ? "start_mm" : "end_mm";
  return { ...layout, branches: { ...(layout.branches ?? {}), [bid]: { ...old, [key]: [round3(at[0]), round3(at[1])] } } };
}

/** Branch (Alt+Shift+B): sew the selected shapes as one path, in one undo step. */
export async function branchSelected(): Promise<void> {
  const layout = currentLayout();
  if (!layout) return;
  const ids = selectionIds();
  try {
    const plan = await engine().call<Plan>("layout.branch_plan", { layout, ids });
    if (currentLayout() !== layout) return info("The design changed while the branch was planned: try again.");
    if (!plan.ok) return info(plan.reason);
    await commit(branchedLayout(layout, plan.order, ids, `b${newId()}`));
  } catch (err) {
    fail(err);
  }
}

/** Take out of the branch (Alt+Shift+U): the selected shapes are sewn on their own again. */
export function unbranchSelected(): void {
  const layout = currentLayout();
  if (!layout) return;
  const ids = selectionIds();
  const next = unbranchedLayout(layout, ids);
  if (next === layout) return info("None of the selected shapes is in a branch.");
  void commit(next);
}

/** Keep a dragged dot: the branch starts (or ends) at the member, and the point, nearest `at`. */
export function setBranchDot(bid: string, which: "start" | "end", at: [number, number]): Promise<boolean> {
  const layout = currentLayout();
  if (!layout || !layout.items.some((it) => branchOf(it) === bid)) return Promise.resolve(false);
  return commit(withBranchDot(layout, bid, which, at));
}

/** The branch the selected shape is sewn in, as the engine last drew it (null: none, or it isn't
 *  sewn as a branch, such as a branch of one). */
export function selectedBranch(): BranchInfo | null {
  const s = useStore.getState();
  if (!s.selectedId) return null;
  return s.design?.branches?.find((b) => b.items.includes(s.selectedId!)) ?? null;
}
