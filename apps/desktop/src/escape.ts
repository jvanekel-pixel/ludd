/**
 * Esc lets go of whatever you're in the middle of, one thing per press, newest first.
 *
 * Things that are briefly "held" (a drag on the canvas, an open menu or font list) register a
 * let-go here while they last. When nothing is held, Esc falls through to the Escape commands
 * in order: stop drawing, stop measuring, back to Select, let go of a point, deselect, stop playback.
 */

const held: (() => void)[] = [];

/** Register what Esc should do while something is in progress. Returns the release function. */
export function holdEscape(letGo: () => void): () => void {
  held.push(letGo);
  return () => {
    const i = held.lastIndexOf(letGo);
    if (i >= 0) held.splice(i, 1);
  };
}

/** Let go of the newest held thing. Returns false if nothing was held. */
export function letGoNewest(): boolean {
  const letGo = held.pop();
  if (!letGo) return false;
  letGo();
  return true;
}

/** For tests. */
export function heldCount(): number {
  return held.length;
}
