/**
 * Carved lines (Shift+C): lines drawn with the pen over a fill and kept in its geometry.carve.
 * Every row drops a needle where it crosses one, so the line shows as a groove (the engine:
 * digitize/rows/carve.py). actions.ts sends a finished or cancelled pen line here.
 */
import { currentLayout, editObject, info } from "../actions";
import { fillPatternDef } from "../design/fillPatterns";
import type { ObjectItem, PathNode } from "../design/types";
import { useStore, type Pen } from "../store";

/** The patterns sewn in rows, which carved lines work on. */
export const CARVE_PATTERNS = ["tatami", "gradient", "wave", "blend"];

/** Whether a fill with this pattern can have carved lines. */
export const canCarve = (pattern?: string): boolean => CARVE_PATTERNS.includes(pattern ?? "tatami");

/** Shift+C: start carving lines into the selected fill. */
export function startCarve(): void {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || o.kind !== "fill") return info("Select a fill first, then press Shift+C to carve lines into it.");
  if (!canCarve(o.params.pattern)) {
    const name = fillPatternDef(o.params.pattern).label;
    return info(`Carved lines need a fill sewn in rows. ${name} isn't: change the pattern to Tatami, Gradient, Wave or Blend first.`);
  }
  const back = s.tool;
  s.setTool("run"); // (clears the pen, so the pen comes after)
  s.setPen({ kind: "run", a: [], b: [], carveFor: o.id, carveBack: back });
  info("Draw a line over the fill; Enter or a double-click finishes it. Draw another, or press Esc when you're done.");
}

/** Enter (or a double-click) while carving: the line goes into the fill. */
export async function finishCarve(pen: Pen): Promise<void> {
  const id = pen.carveFor;
  if (!id || pen.a.length < 2) return;
  const s = useStore.getState();
  if (!currentLayout()?.items.some((it) => it.id === id && it.kind === "fill")) {
    // The fill was deleted or undone meanwhile: nothing to carve into.
    s.setPen(null);
    s.setTool(pen.carveBack ?? "select");
    return info("The fill is gone, so the line wasn't carved.");
  }
  // A closed line goes all the way round: its first point again at the end.
  const line: PathNode[] = pen.closed && pen.a.length > 2 ? [...pen.a, [...pen.a[0]] as PathNode] : [...pen.a];
  // Keep carving, with a fresh pen, until Esc.
  s.setPen({ kind: "run", a: [], b: [], carveFor: id, carveBack: pen.carveBack });
  const ok = await editObject(id, (o) =>
    o.kind === "fill" ? ({ ...o, geometry: { ...o.geometry, carve: [...(o.geometry.carve ?? []), line] } } as ObjectItem) : o,
  );
  if (ok) info("Line carved. Draw another, or press Esc when you're done.");
}

/** Esc while carving: with points, drops that line (and keeps carving); with none, stops. */
export function cancelCarve(pen: Pen): void {
  const s = useStore.getState();
  if (pen.a.length) {
    s.setPen({ ...pen, a: [], b: [] });
    return info("Line dropped. Draw another, or press Esc again when you're done.");
  }
  s.setPen(null);
  s.setTool(pen.carveBack ?? "select");
  if (pen.carveFor && currentLayout()?.items.some((it) => it.id === pen.carveFor)) s.select(pen.carveFor);
  info("Done carving.");
}

/** "Remove carved lines" in the shape's menus. */
export function removeCarves(id: string): void {
  const o = currentLayout()?.items.find((it) => it.id === id);
  if (o?.kind !== "fill" || !o.geometry.carve?.length) return;
  void editObject(id, (x) => (x.kind === "fill" ? ({ ...x, geometry: { ...x.geometry, carve: undefined } } as ObjectItem) : x)).then(
    (ok) => ok && info("Carved lines removed."),
  );
}
