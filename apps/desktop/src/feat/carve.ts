/**
 * Carved lines (Shift+C): lines drawn with the pen over a fill and kept in its geometry.carve.
 * Every row drops a needle where it crosses one, so the line shows as a groove (the engine:
 * digitize/rows/carve.py). actions.ts sends a finished or cancelled pen line here.
 */
import { info } from "../actions";
import type { Pen } from "../store";

/** Shift+C: start carving lines into the selected fill. */
export function startCarve(): void {
  info("Carved lines aren't built yet.");
}

/** Enter (or a double-click) while carving: the line goes into the fill. */
export async function finishCarve(_pen: Pen): Promise<void> {}

/** Esc while carving. */
export function cancelCarve(_pen: Pen): void {}

/** "Remove carved lines" in the shape's menus. */
export function removeCarves(_id: string): void {}
