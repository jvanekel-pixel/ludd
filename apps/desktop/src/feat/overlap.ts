/** "Don't sew what's hidden under shapes on top" (P4-A2): the switch for the whole design, and how
 *  far under the edge of a shape on top the fill below keeps sewing. The engine does the work
 *  (repair/overlap.py); the setting is shown by components/OverlapOptions.tsx. */
import { commit, currentLayout, info } from "../actions";
import type { Layout } from "../design/types";

/** "Keep under the edge" (mm). The engine holds a project file to the same range. */
export const KEEP_MM = { standard: 1, min: 0.5, max: 3 };

export const keepInRange = (mm: number) => Math.min(KEEP_MM.max, Math.max(KEEP_MM.min, mm));

/** The margin the engine uses for this design: the standard one unless set, kept in range. */
export function keepUnderEdge(layout: Layout): number {
  const mm = layout.remove_overlap?.keep_mm;
  return typeof mm === "number" && Number.isFinite(mm) ? keepInRange(mm) : KEEP_MM.standard;
}

/** Turn it on or off, keeping the margin chosen. One undo step. */
export async function toggleRemoveOverlap(): Promise<void> {
  const l = currentLayout();
  if (!l) return;
  const enabled = !l.remove_overlap?.enabled;
  const keep_mm = l.remove_overlap?.keep_mm ?? KEEP_MM.standard;
  if (await commit({ ...l, remove_overlap: { enabled, keep_mm } })) {
    const now = enabled ? "on. Fills leave out what the shapes on top of them cover" : "off. Fills are sewn whole again, under shapes on top too";
    info(`Don't sew what's hidden: ${now}. Ctrl+Z undoes it.`);
  }
}

/** A new "Keep under the edge", brought into range. One undo step. */
export async function setKeepUnderEdge(mm: number): Promise<void> {
  const l = currentLayout();
  if (!l?.remove_overlap) return;
  const keep_mm = Math.round(keepInRange(mm) * 100) / 100;
  await commit({ ...l, remove_overlap: { ...l.remove_overlap, keep_mm } });
}
