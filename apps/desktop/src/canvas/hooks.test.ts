import type { Graphics } from "pixi.js";
import { describe, expect, it, vi } from "vitest";
import { activeCanvasTool, drawOverlays, registerCanvasTool, registerOverlay, registerSnap, runCanvasTool, snapToSources, type CanvasCtx } from "./hooks";

const ctx: CanvasCtx = { toMm: (e) => [e.clientX / 10, e.clientY / 10], pxMm: () => 0.1, redraw: () => {} };
const at = (clientX: number, clientY: number) => ({ clientX, clientY }) as PointerEvent;
const g = {} as Graphics;

describe("canvas hooks", () => {
  it("hooks register and unregister", () => {
    // Nothing registered: nothing happens.
    expect(activeCanvasTool()).toBeUndefined();
    expect(runCanvasTool("down", at(10, 20), ctx)).toBe(false);
    expect(snapToSources([1, 2], 1)).toBeNull();

    const draw = vi.fn();
    const down = vi.fn(() => true);
    let on = false;
    const offs = [
      registerOverlay({ id: "test.overlay", draw }),
      registerCanvasTool({ id: "test.tool", active: () => on, down }),
      registerSnap({ id: "test.snap", snap: (p, r) => (Math.hypot(p[0] - 5, p[1] - 5) <= r ? [5, 5] : null) }),
    ];

    drawOverlays(g, 0.1, ctx);
    expect(draw).toHaveBeenCalledExactlyOnceWith(g, 0.1, ctx);

    // A tool only gets the pointer while it says it's active, in mm.
    expect(runCanvasTool("down", at(10, 20), ctx)).toBe(false);
    expect(down).not.toHaveBeenCalled();
    on = true;
    expect(activeCanvasTool()?.id).toBe("test.tool");
    expect(runCanvasTool("down", at(10, 20), ctx)).toBe(true);
    expect(down).toHaveBeenCalledExactlyOnceWith([1, 2], at(10, 20), ctx);
    // No handler for it: not handled.
    expect(runCanvasTool("move", at(0, 0), ctx)).toBe(false);
    expect(runCanvasTool("up", at(0, 0), ctx)).toBe(false);

    expect(snapToSources([5.5, 5], 1)).toEqual([5, 5]);
    expect(snapToSources([9, 9], 1)).toBeNull();

    // Unregistered (twice is harmless): nothing happens again.
    for (const off of [...offs, ...offs]) off();
    draw.mockClear();
    down.mockClear();
    drawOverlays(g, 0.1, ctx);
    expect(draw).not.toHaveBeenCalled();
    expect(activeCanvasTool()).toBeUndefined();
    expect(runCanvasTool("down", at(10, 20), ctx)).toBe(false);
    expect(down).not.toHaveBeenCalled();
    expect(snapToSources([5, 5], 1)).toBeNull();
  });
});
