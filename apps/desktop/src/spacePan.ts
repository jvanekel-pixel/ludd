/**
 * Space, as in Embrilliance: hold it and drag to move around the design without grabbing
 * anything (a hand tool). A quick tap, with no drag, still plays and pauses the stitch-out.
 */
import { useStore } from "./store";

const TAP_MS = 300;
let downAt = 0;
let panned = false;

/** The canvas calls this when a Space drag actually moved the view. */
export function markSpacePanned() {
  panned = true;
}

export function spaceDown() {
  const s = useStore.getState();
  if (s.spaceDown) return; // key repeat
  downAt = performance.now();
  panned = false;
  s.setSpaceDown(true);
}

/** Returns true if this was a tap (play / pause it). */
export function spaceUp(): boolean {
  const s = useStore.getState();
  if (!s.spaceDown) return false;
  s.setSpaceDown(false);
  return !panned && performance.now() - downAt < TAP_MS;
}
