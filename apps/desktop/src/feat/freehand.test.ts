// @vitest-environment jsdom
/** Freehand drawing (P7-C1), through pointer events on the real design canvas and the app's own
 *  keyboard handler (a fake drawing library and a fake engine). */
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));
vi.mock("pixi.js", () => import("../canvas/fakePixi"));

import { COMMANDS, currentLayout, whenIdle } from "../actions";
import "../cmd";
import { mountCanvas, type TestCanvas } from "../canvas/testCanvas";
import { drawOverlays } from "../canvas/hooks";
import { strokeBeingDrawn } from "../canvas/freehandTool";
import { newDoc } from "../design/layout";
import { distToSegment, flatten, type Pt } from "../design/paths";
import type { LayoutItem, ObjectItem, PathNode } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { startSatinFit } from "../satinFit";
import { useStore } from "../store";
import { startTraceAssist } from "../traceAssist";
import { startCarve } from "./carve";
import { setSmoothing, useFreehand } from "./freehand";

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const THREAD = { color: "#1f3a93", name: "Navy", brand: "", catalog: "" };

const calls: string[] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    calls.push(method);
    if (method === "trace.suggest") return { ghost: [60, 60], confidence: 0.9, corner: false, alternatives: [], close: false, mode: "auto" } as T;
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return {
      path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [], item: [], src: [] },
      info: { stitches: 0, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 0, width_mm: 0, height_mm: 0, bounds_mm: [0, 0, 0, 0] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: null, source_size_mm: null })),
    } as T;
  },
};

const square: ObjectItem = {
  id: "sq", kind: "fill", geometry: { outline: [[30, -20, "c"], [50, -20, "c"], [50, 0, "c"], [30, 0, "c"]] }, params: {},
  thread: THREAD, transform: IDENT, threads: [], ops: [],
} as ObjectItem;

let canvas: TestCanvas;

async function setUp(...items: LayoutItem[]) {
  await whenIdle();
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items } };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], pen: null,
    tool: "select", realistic: false, design: null, notice: null, drawThread: THREAD, units: "mm", snapGrid: false, traceAssist: false,
    ghost: null, edgeFit: null,
  });
  calls.length = 0;
  canvas = await mountCanvas();
}

const pen = () => useStore.getState().pen;
const items = () => currentLayout()!.items as ObjectItem[];
const press = (key: string) => canvas.key(key);
const drawWith = async (tool: "run" | "satin" | "fill", on = true) => {
  await act(async () => COMMANDS.find((c) => c.id === `tool.${tool}`)!.run());
  act(() => useFreehand.setState({ on }));
};
const settle = async () => {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
    await whenIdle();
  });
};

/** `n` points along f(0..1). */
const along = (f: (t: number) => Pt, n: number) => Array.from({ length: n }, (_, i) => f(i / (n - 1)));
const sStroke = (x: number, y: number, n = 120) => along((t) => [x + 40 * t, y + 9 * Math.sin(2 * Math.PI * t)], n);
const circle = (cx: number, cy: number, r: number, turn = 1, n = 140) => along((t) => [cx + r * Math.cos(2 * Math.PI * turn * t), cy + r * Math.sin(2 * Math.PI * turn * t)], n);

const toLine = (p: Pt, line: readonly Pt[]) => Math.min(...line.slice(1).map((b, i) => distToSegment(p, line[i], b)));
/** How far the stroke (as the pointer reported it) is from the curve of these pen points. */
const strokeToCurve = (pts: readonly Pt[], nodes: readonly PathNode[], closed = false) => {
  const curve = flatten(nodes, closed);
  return Math.max(...pts.map((p) => toLine(canvas.onScreen(p), curve)));
};

beforeEach(() => {
  setSmoothing(3);
  useFreehand.setState({ on: false });
});
afterEach(async () => {
  await settle();
  canvas.unmount();
  useStore.setState({ pen: null, tool: "select", ghost: null, edgeFit: null, traceAssist: false });
  while (heldCount()) letGoNewest();
});

describe("freehand drawing", () => {
  it("Y picks Line when no drawing tool is chosen", async () => {
    await setUp();
    await act(async () => press("y"));
    expect(useStore.getState().tool).toBe("run");
    expect(useFreehand.getState().on).toBe(true);
    await act(async () => press("y"));
    expect(useStore.getState().tool).toBe("run");
    expect(useFreehand.getState().on).toBe(false);
    // With a drawing tool chosen it only switches freehand, mid-shape too.
    await drawWith("fill", false);
    canvas.click([0, 0]);
    await act(async () => press("y"));
    expect([useStore.getState().tool, useFreehand.getState().on, pen()?.a.length]).toEqual(["fill", true, 1]);
    // Left on, then put away with Select: Y picks Line again and keeps it on.
    act(() => useStore.getState().setTool("select"));
    await act(async () => press("y"));
    expect([useStore.getState().tool, useFreehand.getState().on]).toEqual(["run", true]);
  });

  it("a stroke is added to the pen's points", async () => {
    await setUp();
    await drawWith("run");
    canvas.click([-30, -10]);
    canvas.click([-20, 5]);
    const clicked = pen()!.a;
    expect(clicked).toHaveLength(2);
    const drawn = sStroke(-10, 10);
    canvas.stroke(drawn);
    const after = pen()!;
    expect(after.a.slice(0, 2)).toEqual(clicked);
    expect(after.a.length).toBeGreaterThan(3);
    expect(after.a.length).toBeLessThanOrEqual(2 + 12);
    expect(strokeToCurve(drawn, after.a)).toBeLessThanOrEqual(0.4);
    expect(items()).toHaveLength(0); // still in the pen
    // Clicks and another stroke go on from it; Enter finishes as usual.
    canvas.click([36, 12]);
    await act(async () => press("Enter"));
    await settle();
    expect(pen()).toBeNull();
    expect(items()).toHaveLength(1);
    expect(items()[0].kind).toBe("run");
    expect((items()[0] as Extract<ObjectItem, { kind: "run" }>).geometry.nodes).toEqual([...after.a, expect.anything()]);
  });

  it("a fill stroke let go at its start finishes the shape", async () => {
    await setUp();
    await drawWith("fill");
    const loop = circle(0, 0, 18, 0.975); // let go 2.8 mm short of the start: within 12 pixels
    canvas.stroke(loop);
    await settle();
    expect(pen()).toBeNull();
    expect(items()).toHaveLength(1);
    const outline = (items()[0] as Extract<ObjectItem, { kind: "fill" }>).geometry.outline;
    expect(outline.length).toBeLessThanOrEqual(12);
    expect(strokeToCurve(loop, outline, true)).toBeLessThanOrEqual(0.4);
    expect(useStore.getState().selectedId).toBe(items()[0].id);
    // Let go further away, it stays in the pen.
    await drawWith("fill");
    canvas.stroke(circle(0, 40, 15, 0.85));
    await settle();
    expect(items()).toHaveLength(1);
    expect(pen()!.a.length).toBeGreaterThan(3);
  });

  it("Esc drops the stroke before the shape", async () => {
    await setUp();
    await drawWith("run");
    for (const p of [[-20, 0], [-10, 8], [0, 0]] as Pt[]) canvas.click(p);
    const clicked = pen()!.a;
    const drawn = sStroke(5, 5);
    canvas.down(drawn[0]);
    for (const p of drawn.slice(1, 60)) canvas.move(p);
    expect(strokeBeingDrawn()).not.toBeNull();
    press("Escape");
    expect(pen()!.a).toEqual(clicked);
    expect(strokeBeingDrawn()).toBeNull();
    for (const p of drawn.slice(60)) canvas.move(p);
    canvas.up(drawn[drawn.length - 1]);
    await settle();
    expect(pen()!.a).toEqual(clicked);
    // The next Esc drops the shape, and the one after goes back to Select.
    press("Escape");
    expect(pen()).toBeNull();
    press("Escape");
    expect(useStore.getState().tool).toBe("select");
    expect(heldCount()).toBe(0);
  });

  it("a stroke continues a line from its first point, keeping its direction", async () => {
    const line = { ...square, id: "ln", kind: "run", geometry: { nodes: [[0, 0, "s"], [10, 4, "s"], [20, 0, "s"]] } } as unknown as ObjectItem;
    await setUp(line);
    act(() => {
      useStore.getState().select("ln");
      useStore.getState().selectNode({ id: "ln", list: "nodes", index: 0 });
    });
    press("k");
    expect(pen()!.prepend).toBe(true);
    act(() => useFreehand.setState({ on: true }));
    // Pressed just off the old start (it snaps onto it) and drawn away to the left.
    const drawn = along((t) => [-0.4 - 26 * t, 0.2 - 7 * Math.sin(Math.PI * t)], 100);
    canvas.stroke(drawn);
    await act(async () => press("Enter"));
    await settle();
    const nodes = (items()[0] as Extract<ObjectItem, { kind: "run" }>).geometry.nodes;
    // It starts where the stroke ended, goes on through the old line and still ends at its end.
    expect(nodes.slice(-3)).toEqual([[0, 0, "s"], [10, 4, "s"], [20, 0, "s"]]);
    const start = canvas.onScreen(drawn[drawn.length - 1]);
    expect(Math.hypot(nodes[0][0] - start[0], nodes[0][1] - start[1])).toBeLessThan(0.05);
    expect(strokeToCurve(drawn.slice(8), nodes)).toBeLessThanOrEqual(0.4);
    expect(items()).toHaveLength(1);
  });

  it("a click stays a click: it snaps and takes its kind from the keys as before", async () => {
    await setUp(square);
    await drawWith("run");
    canvas.click([29.6, -19.7]); // right by the square's corner
    expect(pen()!.a).toEqual([[30, -20, "s"]]);
    canvas.click([20, 10], { ctrlKey: true });
    canvas.click([10, 10], { shiftKey: true });
    expect(pen()!.a.map((n) => n[2])).toEqual(["s", "l", "c"]);
    // A tiny wiggle (past the drag's 3 pixels, but under 2 mm) while the button is down is
    // still one click.
    canvas.stroke([[0, 0], [1.1, 0], [0.9, 0.2], [0.7, 0.2]]);
    expect(pen()!.a).toHaveLength(4);
    expect(heldCount()).toBe(0);
  });

  it("a stroke starting on another shape's point begins exactly there", async () => {
    await setUp(square);
    await drawWith("run");
    const drawn = along((t) => [29.2 - 30 * t, -19.4 + 6 * t], 90); // pressed 1 mm off the corner
    canvas.stroke(drawn);
    expect(pen()!.a[0]).toEqual([30, -20, "s"]);
    expect(pen()!.a.length).toBeLessThanOrEqual(4);
    // After the first few millimeters the curve is on the stroke as drawn.
    expect(strokeToCurve(drawn.slice(20), pen()!.a)).toBeLessThanOrEqual(0.4);
  });

  it("with freehand off, dragging places just the point pressed, as before", async () => {
    await setUp();
    await drawWith("run", false);
    canvas.stroke(sStroke(0, 0));
    expect(pen()!.a).toHaveLength(1);
    expect(heldCount()).toBe(0);
  });

  it("right-click and double-click still finish", async () => {
    await setUp();
    await drawWith("run");
    canvas.stroke(sStroke(-30, 0));
    canvas.down([20, 20], { button: 2, buttons: 2 });
    await settle();
    expect(items()).toHaveLength(1);
    await drawWith("run");
    canvas.stroke(sStroke(-30, 20));
    canvas.click([20, 30]);
    canvas.click([20, 30]);
    await act(async () => void canvas.host.dispatchEvent(new MouseEvent("dblclick", { bubbles: true, ...canvas.at([20, 30]) })));
    await settle();
    expect(items()).toHaveLength(2);
  });

  it("holding Space or the middle button pans instead of drawing", async () => {
    await setUp();
    await drawWith("run");
    canvas.click([0, 0]);
    act(() => useStore.getState().setSpaceDown(true));
    canvas.stroke(sStroke(-20, 10));
    act(() => useStore.getState().setSpaceDown(false));
    canvas.down([-20, -10], { button: 1, buttons: 4 });
    canvas.move([-10, -10], { buttons: 4 });
    canvas.up([-10, -10], { button: 1 });
    expect(pen()!.a).toEqual([[0, 0, "s"]]);
    expect(heldCount()).toBe(0);
    // The view moved: the same screen spot is a different design point now.
    canvas.click([0, 0]);
    const clicked = pen()!.a[pen()!.a.length - 1];
    expect(Math.hypot(clicked[0], clicked[1])).toBeGreaterThan(5);
  });

  it("a second finger or a lost window drops the stroke, leaving the shape", async () => {
    await setUp();
    await drawWith("run");
    canvas.click([0, 0]);
    canvas.down([10, 10]);
    for (const p of sStroke(10, 10).slice(1, 50)) canvas.move(p);
    canvas.down([30, 30], { pointerId: 7 });
    canvas.up([30, 30], { pointerId: 7 });
    canvas.up([20, 20]);
    expect(pen()!.a).toHaveLength(1);
    canvas.down([10, 10]);
    for (const p of sStroke(10, 10).slice(1, 50)) canvas.move(p);
    act(() => void window.dispatchEvent(new Event("blur")));
    canvas.up([20, 20]);
    expect(pen()!.a).toHaveLength(1);
    expect(heldCount()).toBe(0);
  });

  it("carves a freehand line into a fill, without closing it", async () => {
    await setUp({ ...square, geometry: { outline: [[-20, -20, "c"], [20, -20, "c"], [20, 20, "c"], [-20, 20, "c"]] } } as ObjectItem);
    act(() => useStore.getState().select("sq"));
    act(() => startCarve());
    act(() => useFreehand.setState({ on: true }));
    const loop = circle(0, 0, 8, 0.98, 100);
    canvas.stroke(loop);
    expect(pen()!.carveFor).toBe("sq");
    expect(pen()!.a.length).toBeGreaterThan(5);
    await act(async () => press("Enter"));
    await settle();
    const carve = (items()[0] as Extract<ObjectItem, { kind: "fill" }>).geometry.carve!;
    expect(carve).toHaveLength(1);
    expect(strokeToCurve(loop, carve[0])).toBeLessThanOrEqual(0.4);
  });

  it("draws a hole with one stroke let go at its start", async () => {
    await setUp({ ...square, geometry: { outline: [[-25, -25, "c"], [25, -25, "c"], [25, 25, "c"], [-25, 25, "c"]] } } as ObjectItem);
    act(() => useStore.getState().select("sq"));
    await act(async () => press("o"));
    act(() => useFreehand.setState({ on: true }));
    canvas.stroke(circle(0, 0, 10, 0.97, 110));
    await settle();
    const g = (items()[0] as Extract<ObjectItem, { kind: "fill" }>).geometry;
    expect(g.holes).toHaveLength(1);
    expect(items()).toHaveLength(1);
    expect(useStore.getState().selectedId).toBe("sq");
  });

  it("Trace Assist and the satin edge fit work after a stroke", async () => {
    const stopFit = startSatinFit();
    const stopTrace = startTraceAssist();
    try {
      await setUp(square);
      const d = newDoc();
      act(() =>
        useStore.setState({
          history: { past: [], present: { ...d, layout: { ...d.layout, items: [square] }, images: [{ id: "im", name: "p", path: "", data_url: "data:image/png;base64,x", x: 40, y: 10, width_mm: 100, height_mm: 100, rotate: 0, opacity: 0.5, locked: true, visible: true }] }, future: [] },
          traceAssist: true,
        }),
      );
      await drawWith("satin");
      // Along the square's top edge, 1 mm above it.
      canvas.stroke(along((t) => [31 + 18 * t, -21], 60));
      await settle();
      expect(calls).toContain("trace.suggest");
      expect(useStore.getState().ghost).not.toBeNull();
      expect(useStore.getState().edgeFit?.options.length ?? 0).toBeGreaterThan(0);
      press("Tab");
      expect(useStore.getState().edgeFit?.original).not.toBeNull();
    } finally {
      stopFit();
      stopTrace();
    }
  });

  it("shows the stroke while it's drawn", async () => {
    await setUp();
    await drawWith("satin");
    const drawn = sStroke(-20, 0);
    canvas.down(drawn[0]);
    for (const p of drawn.slice(1, 40)) canvas.move(p);
    const lines: { width: number; points: Pt[] }[] = [];
    let path: Pt[] = [];
    const g = {
      moveTo(x: number, y: number) { path = [[x, y]]; return g; },
      lineTo(x: number, y: number) { path.push([x, y]); return g; },
      stroke(s: { width: number }) { lines.push({ width: s.width, points: [...path] }); return g; },
      circle() { return g; }, fill() { return g; }, closePath() { return g; }, rect() { return g; }, poly() { return g; },
    };
    drawOverlays(g as never, canvas.pxMm, { toMm: () => [0, 0], pxMm: () => canvas.pxMm, redraw: () => {} });
    const mine = lines.filter((l) => l.points.length > 20);
    expect(mine.map((l) => l.width)).toEqual([useStore.getState().satinWidth, 1.5 * canvas.pxMm]);
    canvas.up(drawn[39]);
  });

  it("is registered as Y, with Smoothing remembered", async () => {
    await setUp();
    expect(COMMANDS.find((c) => c.id === "tool.freehand")?.shortcut).toBe("Y");
    setSmoothing(9);
    expect(useFreehand.getState().smooth).toBe(5);
    setSmoothing(0);
    expect(useFreehand.getState().smooth).toBe(1);
    expect(JSON.parse(localStorage.getItem("ludd.prefs")!).freehandSmooth).toBe(1);
  });
});
