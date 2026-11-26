/**
 * Turning fills: a fill with two or more angle lines, which its rows turn to follow (the engine:
 * digitize/fills/turning.py). Shift+I draws another line; each shows its purple dots.
 */
import { info } from "../actions";

/** Shift+I: draw another angle line on the selected fill. */
export function startAddAngle(): void {
  info("Turning fills aren't built yet.");
}

/** An angle line just drawn (I, or Shift+I when `add`): true if it was taken as one of a turning
 *  fill's lines; false leaves it to set the fill's single angle, as always. */
export function finishAngleLine(_id: string, _a: [number, number], _b: [number, number], _add: boolean): boolean {
  return false;
}
