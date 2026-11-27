/**
 * A branch's dots (P7-B2): while a shape in a branch is selected, one green dot where the branch
 * starts and one red dot where it ends (as the engine last sewed it). Dragging one keeps the drop
 * point in `layout.branches`; Esc while dragging puts it back. Registered when the app loads
 * (cmd/branch.ts imports this file).
 */
import { holdEscape } from "../escape";
import { selectedBranch, setBranchDot } from "../feat/branch";
import { useStore } from "../store";
import { registerCanvasTool, registerOverlay, type CanvasCtx } from "./hooks";

type Pt = [number, number];

const DOT_PX = 5; // as a shape's own start and end dots (StitchCanvas.tsx)
const START_COLOR = 0x2f8f4e;
const END_COLOR = 0xd9381e;

type Drag = { id: string; which: "start" | "end"; at: Pt; pointerId: number; stop: () => void; ctx: CanvasCtx };
let drag: Drag | null = null;

/** The branch whose dots show: the selected shape's, while the canvas is just selecting. */
function shown(): ReturnType<typeof selectedBranch> {
  const s = useStore.getState();
  if (s.tool !== "select" || s.knife || s.pen || s.measure || s.ruler || s.angleFor || s.stitchEdit) return null;
  return selectedBranch();
}

/** The dot under `p`: the end wins where both sit together. */
export function branchDotAt(p: Pt, px: number): { id: string; which: "start" | "end"; at: Pt } | null {
  const b = shown();
  if (!b) return null;
  for (const which of ["end", "start"] as const) {
    const at = b[which];
    if (Math.hypot(at[0] - p[0], at[1] - p[1]) <= (DOT_PX + 3) * px) return { id: b.id, which, at };
  }
  return null;
}

function cancelDrag(): void {
  const d = drag;
  drag = null;
  d?.stop();
  d?.ctx.redraw();
}

registerCanvasTool({
  id: "branch-dots",
  active: () => drag !== null || shown() !== null,
  down(p, e, ctx) {
    if (drag) {
      cancelDrag(); // a second finger: the dot goes back
      return true;
    }
    const hit = e.button === 0 ? branchDotAt(p, ctx.pxMm()) : null;
    if (!hit) return false; // the canvas's own clicks
    try {
      (e.target as Element | null)?.setPointerCapture?.(e.pointerId);
    } catch {
      // A pointer that's already gone.
    }
    drag = { id: hit.id, which: hit.which, at: hit.at, pointerId: e.pointerId, stop: holdEscape(cancelDrag), ctx };
    ctx.redraw();
    return true;
  },
  move(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    drag.at = p;
    ctx.redraw();
    return true;
  },
  up(p, e, ctx) {
    if (!drag || e.pointerId !== drag.pointerId) return false;
    const d = drag;
    drag = null;
    d.stop();
    void setBranchDot(d.id, d.which, p);
    ctx.redraw();
    return true;
  },
});

registerOverlay({
  id: "branch-dots",
  draw(g, px) {
    const b = shown();
    if (!b) return;
    for (const which of ["start", "end"] as const) {
      const at = drag && drag.id === b.id && drag.which === which ? drag.at : b[which];
      g.circle(at[0], at[1], DOT_PX * px).fill(which === "start" ? START_COLOR : END_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
    }
  },
});
