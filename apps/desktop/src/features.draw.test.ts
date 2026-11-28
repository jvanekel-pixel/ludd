/** Continuing a shape from either end (P7-C2): with an open line's or ribbon's first point
 *  selected, K goes on from its start and the shape keeps its direction. Through the real pen
 *  routing in actions.ts and the K command, with a fake engine. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { COMMANDS, currentLayout, penAdd, penFinish, penUndoPoint, whenIdle } from "./actions";
import { dispatchKey } from "./commands";
import { newDoc } from "./design/layout";
import { flatten, type Pt } from "./design/paths";
import type { LayoutItem, ObjectItem, PathNode } from "./design/types";
import { useStore } from "./store";

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return {
      path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null })),
    } as T;
  },
};

/** Curve, corner and straight points together. */
const MIXED: PathNode[] = [[0, 0, "s"], [10, 4, "s"], [20, 0, "c"], [30, 6, "s"], [38, 2, "s"], [45, 2, "l"]];
const shape = (kind: "run" | "satin" | "fill", geometry: object): ObjectItem =>
  ({
    id: "a", kind, geometry, params: {}, thread: { color: "#cc0000", name: "Red", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [],
  }) as unknown as ObjectItem;

function setDoc(item: ObjectItem, node: number | null = null, list: "nodes" | "outline" = "nodes") {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [item] } };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a", extraIds: [], notice: null,
    pen: null, tool: "select", selectedNode: node === null ? null : { id: "a", list, index: node },
  });
}

/** Press K, as the keyboard handler does. */
const pressK = () => expect(dispatchKey({ key: "k", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false }, COMMANDS)).toBe(true);
const pen = () => useStore.getState().pen!;
const nodes = () => (currentLayout()!.items[0] as ObjectItem).geometry as { nodes: PathNode[]; width_mm?: number; closed?: boolean };
const ends = (path: readonly PathNode[]) => [path[0].slice(0, 2), path[path.length - 1].slice(0, 2)];

beforeEach(async () => {
  await whenIdle();
});

describe("continuing a shape", () => {
  it("continuing from the first point adds at the start and keeps the direction", async () => {
    setDoc(shape("run", { nodes: MIXED }), 0);
    pressK();
    expect(useStore.getState().tool).toBe("run");
    expect(pen()).toMatchObject({ kind: "run", replaceId: "a", prepend: true });
    // The pen holds the line from its far end back to its start, drawing the same curve.
    expect(pen().a.map((n) => n.slice(0, 2))).toEqual([...MIXED].reverse().map((n) => n.slice(0, 2)));
    penAdd([-8, 6, "s"]);
    penAdd([-15, 0, "c"]);
    await penFinish();
    // The new points come before the old start, in sewing order; the old line is as it was.
    expect(nodes().nodes).toEqual([[-15, 0, "c"], [-8, 6, "s"], ...MIXED]);
    expect(ends(nodes().nodes)).toEqual([[-15, 0], [45, 2]]);
    expect(useStore.getState().history.past).toHaveLength(1);
    expect(useStore.getState().selectedId).toBe("a");
  });

  it("continuing from the first point and adding nothing gives the line back exactly", async () => {
    for (const path of [MIXED, [[0, 0, "s"], [10, 6, "s"], [20, 0, "l"]] as PathNode[], [[0, 0, "l"], [10, 6, "c"], [20, 0, "s"]] as PathNode[]]) {
      setDoc(shape("run", { nodes: path }), 0);
      pressK();
      await penFinish();
      expect(nodes().nodes).toEqual(path);
      expect(useStore.getState().history.past).toHaveLength(0); // nothing changed
    }
  });

  it("keeps a straight stretch added at the start straight, and a ribbon's width", async () => {
    setDoc(shape("satin", { nodes: [[0, 0, "s"], [10, 5, "s"], [20, 0, "s"]], width_mm: 4 }), 0);
    pressK();
    penAdd([-10, 0, "l"]); // Ctrl+click: straight from the old start
    await penFinish();
    expect(nodes()).toEqual({ nodes: [[-10, 0, "c"], [0, 0, "l"], [10, 5, "s"], [20, 0, "s"]], width_mm: 4 });
    // The new stretch is straight, as it was drawn.
    expect(flatten(nodes().nodes.slice(0, 2))).toEqual([[-10, 0], [0, 0]] as Pt[]);
    // Backspace while continuing takes the newest point (at the start end) back.
    setDoc(shape("run", { nodes: MIXED }), 0);
    pressK();
    penAdd([-8, 6, "s"]);
    penAdd([-15, 0, "s"]);
    penUndoPoint();
    await penFinish();
    expect(nodes().nodes).toEqual([[-8, 6, "s"], ...MIXED]);
  });

  it("continuing from the end is unchanged", async () => {
    for (const node of [null, 3, MIXED.length - 1]) {
      setDoc(shape("run", { nodes: MIXED }), node);
      pressK();
      expect(pen().prepend).toBeUndefined();
      expect(pen().a).toEqual(MIXED);
      penAdd([55, 0, "s"]);
      await penFinish();
      expect(nodes().nodes).toEqual([...MIXED, [55, 0, "s"]]);
    }
    // A closed line, a fill and an applique go on from their last point, whatever is selected.
    setDoc(shape("run", { nodes: MIXED, closed: true }), 0);
    pressK();
    expect([pen().prepend, pen().a]).toEqual([undefined, MIXED]);
    setDoc(shape("fill", { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }), 0, "outline");
    pressK();
    expect([pen().prepend, pen().a[0]]).toEqual([undefined, [0, 0, "c"]]);
    expect(useStore.getState().tool).toBe("fill");
  });

  it("says which end it goes on from", () => {
    setDoc(shape("run", { nodes: MIXED }), 0);
    pressK();
    expect(useStore.getState().notice?.text).toBe("Keep clicking to add points before this shape's start; Enter when done.");
    setDoc(shape("run", { nodes: MIXED }));
    pressK();
    expect(useStore.getState().notice?.text).toBe("Keep clicking to add points to this shape; Enter when done.");
  });

  it("a shape that's gone is drawn anew the right way round", async () => {
    setDoc(shape("run", { nodes: MIXED }), 0);
    pressK();
    penAdd([-8, 6, "s"]);
    const d = useStore.getState().history.present!;
    useStore.setState({ history: { past: [], present: { ...d, layout: { ...d.layout, items: [] } }, future: [] } });
    await penFinish();
    expect(ends(nodes().nodes)).toEqual([[-8, 6], [45, 2]]);
  });
});
