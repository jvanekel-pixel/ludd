/** Carved lines (Shift+C, P6-A3): a finished pen line lands in the fill's geometry.carve. Goes
 *  through the real pen routing in actions.ts (penAdd, penFinish, penCancel), with a fake engine. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import "../cmd/fills"; // registers object.carve
import { COMMANDS, currentLayout, penAdd, penCancel, penFinish, penUndoPoint, whenIdle } from "../actions";
import { newDoc } from "../design/layout";
import type { Doc, FillGeometry, ObjectItem, PathNode } from "../design/types";
import { useStore } from "../store";
import { removeCarves, startCarve } from "./carve";

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: { id: string }[] }).items;
    return {
      path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [10, 10], bounds_mm: [0, 0, 20, 20], source_size_mm: null })),
    } as T;
  },
};

const fill = (pattern?: string): ObjectItem =>
  ({
    id: "f",
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]] },
    params: pattern ? { pattern } : {},
    thread: { color: "#cc0000", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as ObjectItem;

function setDoc(item: ObjectItem) {
  const d = newDoc();
  const doc: Doc = { ...d, layout: { ...d.layout, items: [item] } };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "f", extraIds: [],
    notice: null, pen: null, tool: "select",
  });
}

const carved = () => ((currentLayout()!.items[0] as ObjectItem).geometry as FillGeometry).carve;
const notice = () => useStore.getState().notice?.text ?? "";
const n = (x: number, y: number): PathNode => [x, y, "c"];

beforeEach(async () => {
  await whenIdle();
});

describe("carving lines into a fill", () => {
  it("adds a finished pen line to geometry.carve and keeps carving until Esc", async () => {
    setDoc(fill());
    startCarve();
    expect(useStore.getState().tool).toBe("run");
    expect(useStore.getState().pen).toMatchObject({ kind: "run", a: [], carveFor: "f", carveBack: "select" });
    penAdd(n(2, 2));
    penAdd(n(18, 18));
    await penFinish();
    expect(carved()).toEqual([[n(2, 2), n(18, 18)]]);
    expect(useStore.getState().history.past).toHaveLength(1); // one undo step
    // Still carving, with a fresh pen: a second line.
    expect(useStore.getState().pen).toMatchObject({ a: [], carveFor: "f" });
    penAdd(n(2, 18));
    penAdd(n(10, 12));
    penAdd(n(18, 2));
    await penFinish();
    expect(carved()).toEqual([[n(2, 2), n(18, 18)], [n(2, 18), n(10, 12), n(18, 2)]]);
    // Esc with points drops that line only; Esc again leaves carving, the fill still selected.
    penAdd(n(5, 5));
    penCancel();
    expect(useStore.getState().pen).toMatchObject({ a: [], carveFor: "f" });
    expect(notice()).toMatch(/Line dropped/);
    penCancel();
    expect(useStore.getState().pen).toBeNull();
    expect(useStore.getState().tool).toBe("select");
    expect(useStore.getState().selectedId).toBe("f");
    expect(carved()).toHaveLength(2);
  });

  it("closes a closed line by repeating its first point", async () => {
    setDoc(fill());
    startCarve();
    useStore.getState().setPen({ ...useStore.getState().pen!, a: [n(5, 5), n(15, 5), n(10, 15)], closed: true });
    await penFinish();
    expect(carved()).toEqual([[n(5, 5), n(15, 5), n(10, 15), n(5, 5)]]);
  });

  it("needs two points, and Backspace keeps carving with an empty pen", async () => {
    setDoc(fill());
    startCarve();
    penAdd(n(5, 5));
    await penFinish();
    expect(carved()).toBeUndefined();
    penUndoPoint();
    expect(useStore.getState().pen).toMatchObject({ a: [], carveFor: "f" });
  });

  it("is registered as Shift+C", () => {
    expect(COMMANDS.find((c) => c.id === "object.carve")?.shortcut).toBe("Shift+C");
  });

  it("says why not on a pattern that isn't sewn in rows", () => {
    setDoc(fill("stipple"));
    startCarve();
    expect(useStore.getState().pen).toBeNull();
    expect(notice()).toMatch(/Stipple isn't/);
    for (const p of ["gradient", "wave", "blend"]) {
      setDoc(fill(p));
      startCarve();
      expect(useStore.getState().pen?.carveFor).toBe("f");
    }
  });

  it("removes every carved line from the menus' Remove carved lines", async () => {
    const f = fill();
    setDoc({ ...f, geometry: { ...f.geometry, carve: [[n(1, 1), n(9, 9)]] } } as ObjectItem);
    removeCarves("f");
    await whenIdle();
    await new Promise((r) => setTimeout(r, 0));
    expect(carved()).toBeUndefined();
    expect(notice()).toMatch(/Carved lines removed/);
  });
});
