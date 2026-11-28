/**
 * While the Repeat window is open, an outline box on the design where each copy will land.
 * The window sets the boxes (showRepeatPreview); the canvas draws them with its other aids.
 */
import { repeatPlaces, type RepeatSpec } from "../design/layout";
import type { Pt } from "../design/paths";
import { selectCanvasDark, useStore } from "../store";
import { registerOverlay, type CanvasCtx } from "./hooks";

/** No more boxes than this are drawn: far beyond any repeat that could be sewn. */
const MOST_BOXES = 500;

/** Each copy's outline box where it will land: the design's box (its on-screen bounds),
 *  mirrored, turned and moved as the copy will be. Four corners each. */
export function repeatBoxes(bounds: [number, number, number, number], spec: RepeatSpec): Pt[][] {
  const [x0, y0, x1, y1] = bounds;
  const center: [number, number] = [(x0 + x1) / 2, (y0 + y1) / 2];
  const size: [number, number] = [x1 - x0, y1 - y0];
  return repeatPlaces(center, size, spec)
    .slice(0, MOST_BOXES)
    .map(({ at, turn }) => {
      // Mirroring a box about its middle leaves it where it is, so only the turn shows.
      const a = (turn * Math.PI) / 180;
      const [ca, sa] = [Math.cos(a), Math.sin(a)];
      const [hw, hh] = [size[0] / 2, size[1] / 2];
      return (
        [
          [-hw, -hh],
          [hw, -hh],
          [hw, hh],
          [-hw, hh],
        ] as Pt[]
      ).map(([x, y]) => [at[0] + x * ca - y * sa, at[1] + x * sa + y * ca] as Pt);
    });
}

let shown: Pt[][] | null = null;
/** What the canvas drew with last, to ask it to draw again when the boxes change. */
let canvas: CanvasCtx | null = null;

/** Show these boxes on the design (null: none). */
export function showRepeatPreview(boxes: Pt[][] | null): void {
  if (!boxes && !shown) return;
  shown = boxes;
  canvas?.redraw();
}

/** The boxes on show (for tests). */
export const repeatPreview = (): Pt[][] | null => shown;

registerOverlay({
  id: "repeat-preview",
  draw(g, px, ctx) {
    canvas = ctx;
    if (!shown) return;
    const color = selectCanvasDark(useStore.getState()) ? 0xc8ff2e : 0x4f7300;
    for (const box of shown) {
      g.moveTo(box[0][0], box[0][1]);
      for (const [x, y] of box.slice(1)) g.lineTo(x, y);
      g.closePath().stroke({ width: 1.5 * px, color, alpha: 0.9 });
    }
  },
});
