// @vitest-environment jsdom
/** Continuing a line from its first point (K): the pen's preview line is the line Enter saves
 *  (Phase 7 audit, finding 3), through the real canvas and keyboard (a fake drawing library). */
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));
vi.mock("pixi.js", () => import("../canvas/fakePixi"));

import { currentLayout, whenIdle } from "../actions";
import "../cmd";
import { Graphics } from "pixi.js"; // the fake one, mocked above
import { mountCanvas, type TestCanvas } from "../canvas/testCanvas";
import { useStore } from "../store";
import { newDoc } from "./layout";
import { distToSegment, flatten, type Pt } from "./paths";
import type { LayoutItem, ObjectItem, PathNode } from "./types";

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const THREAD = { color: "#1f3a93", name: "Navy", brand: "", catalog: "" };

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return {
      path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [], item: [], src: [] },
      info: { stitches: 0, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 0, width_mm: 0, height_mm: 0, bounds_mm: [0, 0, 0, 0] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: null, source_size_mm: null })),
    } as T;
  },
};

let canvas: TestCanvas;
const settle = async () => {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
    await whenIdle();
  });
};

afterEach(async () => {
  await settle();
  canvas.unmount();
  useStore.setState({ pen: null, tool: "select" });
});

async function pickUpFromStart(nodes: PathNode[], kind: "run" | "satin") {
  await whenIdle();
  const line = {
    id: "a", kind, geometry: kind === "satin" ? { nodes, width_mm: 3 } : { nodes }, params: {}, thread: THREAD, transform: IDENT, threads: [], ops: [],
  } as unknown as ObjectItem;
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [line] } };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a", extraIds: [], pen: null,
    tool: "select", design: null, notice: null, drawThread: THREAD, snapGrid: false, traceAssist: false, ghost: null, edgeFit: null,
  });
  canvas = await mountCanvas();
  act(() => useStore.setState({ selectedId: "a", selectedNode: { id: "a", list: "nodes", index: 0 } }));
  await act(async () => canvas.key("k"));
  expect(useStore.getState().pen?.prepend).toBe(true);
}

/** The paths the canvas draws while `act`ing: each moveTo starts one. */
function recordPaths() {
  const paths: Pt[][] = [];
  const moved = vi.spyOn(Graphics.prototype, "moveTo").mockImplementation(function (this: Graphics, ...p: unknown[]) {
    paths.push([[p[0] as number, p[1] as number]]);
    return this;
  });
  const lined = vi.spyOn(Graphics.prototype, "lineTo").mockImplementation(function (this: Graphics, ...p: unknown[]) {
    paths.at(-1)?.push([p[0] as number, p[1] as number]);
    return this;
  });
  return { paths, stop: () => (moved.mockRestore(), lined.mockRestore()) };
}

const toLine = (p: Pt, line: readonly Pt[]) => Math.min(...line.slice(1).map((b, i) => distToSegment(p, line[i], b)));
/** How far two curves are apart, both ways (mm). */
const apart = (a: readonly Pt[], b: readonly Pt[]) => Math.max(...a.map((p) => toLine(p, b)), ...b.map((p) => toLine(p, a)));

// The audit's cases: the old line, then the point added before its start, with the key held.
const CASES: [string, PathNode[], { ctrlKey?: boolean; shiftKey?: boolean }][] = [
  ["a straight stretch onto a smooth start", [[0, 0, "s"], [10, 8, "s"], [20, 0, "s"]], { ctrlKey: true }],
  ["a curve onto a smooth start", [[0, 0, "s"], [10, 8, "s"], [20, 0, "s"]], {}],
  ["a straight stretch onto a sharp start", [[0, 0, "c"], [10, 8, "s"], [20, 0, "s"]], { ctrlKey: true }],
  ["a line with a straight stretch of its own", [[0, 0, "c"], [10, 8, "s"], [20, 0, "l"]], { shiftKey: true }],
];

describe("continuing a line from its first point", () => {
  for (const [what, nodes, keys] of CASES) {
    for (const kind of ["run", "satin"] as const) {
      it(`the preview is the line saved: ${what} (${kind})`, async () => {
        await pickUpFromStart(nodes, kind);
        const at: Pt = [-10, 0];
        const drawing = recordPaths();
        await act(async () => canvas.move(at, keys));
        // The pen line is drawn from the new point's end of the line.
        const preview = drawing.paths.filter((path) => path.length > 10).at(-1)!;
        drawing.stop();
        await act(async () => canvas.click(at, keys));
        await act(async () => canvas.key("Enter"));
        await settle();
        const saved = (currentLayout()!.items[0] as ObjectItem).geometry as { nodes: PathNode[] };
        expect(saved.nodes).toHaveLength(nodes.length + 1);
        expect(saved.nodes.slice(1).map(([x, y]) => [x, y])).toEqual(nodes.map(([x, y]) => [x, y])); // its direction is kept
        expect(apart(preview, flatten(saved.nodes))).toBeLessThan(0.05);
      });
    }
  }
});
