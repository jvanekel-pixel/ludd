/**
 * Where features add to the design canvas (components/StitchCanvas.tsx) without editing it:
 * overlays drawn over the design, tools that get the pointer first while they're active, and
 * places new points snap to. With nothing registered, the canvas behaves as it would without
 * them. Internal: the first feature that uses one may adjust its shape.
 */
import type { Graphics } from "pixi.js";

/** What the canvas gives a hook: a pointer position in mm, one screen pixel in mm, and a redraw. */
export type CanvasCtx = { toMm(e: { clientX: number; clientY: number }): [number, number]; pxMm(): number; redraw(): void };

/** Drawn on top of the canvas's own selection and drawing aids, in mm (`px`: one screen pixel). */
export type Overlay = { id: string; draw(g: Graphics, px: number, ctx: CanvasCtx): void };

export type CanvasTool = {
  id: string;
  active(): boolean;
  cursor?: string;
  /** Pointer handlers, `p` in mm. True: handled, and the canvas does nothing more with it. */
  down?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean;
  move?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean;
  up?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean;
};

/** Somewhere new points snap to: the snapped point within `radiusMm` of `p`, or null. */
export type SnapSource = { id: string; snap(p: [number, number], radiusMm: number): [number, number] | null };

const overlays: Overlay[] = [];
const tools: CanvasTool[] = [];
const snaps: SnapSource[] = [];

/** Add to a list; returns the function that takes it out again. */
function register<T>(list: T[], item: T): () => void {
  list.push(item);
  let registered = true;
  return () => {
    if (!registered) return;
    registered = false;
    list.splice(list.lastIndexOf(item), 1);
  };
}

export const registerOverlay = (o: Overlay): (() => void) => register(overlays, o);
export const registerCanvasTool = (t: CanvasTool): (() => void) => register(tools, t);
export const registerSnap = (s: SnapSource): (() => void) => register(snaps, s);

// ---------------------------------------------------------------- what the canvas calls

export function drawOverlays(g: Graphics, px: number, ctx: CanvasCtx): void {
  for (const o of overlays) o.draw(g, px, ctx);
}

/** The first registered tool that says it's active. */
export function activeCanvasTool(): CanvasTool | undefined {
  return tools.find((t) => t.active());
}

/** Give a pointer event to the active tool; true if it handled it. */
export function runCanvasTool(kind: "down" | "move" | "up", e: PointerEvent, ctx: CanvasCtx): boolean {
  const tool = activeCanvasTool();
  return !!tool?.[kind] && tool[kind](ctx.toMm(e), e, ctx);
}

/** The first snap source with somewhere to snap `p` to. */
export function snapToSources(p: [number, number], radiusMm: number): [number, number] | null {
  for (const s of snaps) {
    const hit = s.snap(p, radiusMm);
    if (hit) return hit;
  }
  return null;
}
