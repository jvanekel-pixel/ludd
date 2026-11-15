/**
 * QA phase 4 (tests): colour sets (colorways), guides and undo/redo through the store, with a fake
 * engine. No browser needed.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import * as F from "./features";
import { newDoc } from "./design/layout";
import type { LayoutItem, ObjectItem } from "./design/types";
import { useStore } from "./store";

function fakeEngine() {
  return {
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      if (method !== "layout.render") return null as T;
      const layout = params.layout as { items: LayoutItem[] };
      return {
        path: "",
        name: "x",
        format: "layout",
        info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
        threads: [],
        blocks: [],
        records: { x: [], y: [], kind: [] },
        items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })),
      } as T;
    },
  };
}

const fill = (id: string, color: string): ObjectItem =>
  ({
    id,
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] },
    params: {},
    thread: { color, name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as ObjectItem;

const layoutNow = () => useStore.getState().history.present!.layout;
const colorOf = (id: string) => (layoutNow().items.find((it) => it.id === id) as ObjectItem).thread.color;

async function recolor(id: string, color: string) {
  const l = layoutNow();
  await A.commit({ ...l, items: l.items.map((it) => (it.id === id ? ({ ...it, thread: { ...(it as ObjectItem).thread, color } } as LayoutItem) : it)) });
}

beforeEach(async () => {
  await A.whenIdle();
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [fill("a", "#ff0000"), fill("b", "#00ff00")] } };
  useStore.setState({
    engine: fakeEngine() as never,
    history: { past: [], present: doc, future: [] },
    savedDoc: doc,
    selectedId: null,
    extraIds: [],
    notice: null,
    projectPath: null,
    tool: "select",
    pen: null,
    knife: null,
    stitchEdit: null,
    design: null,
  });
});

describe("Colour sets", () => {
  it("a saved set brings its colours back, as one undo step, and can be deleted", async () => {
    await F.saveColorway("  Spring ");
    expect(layoutNow().colorways?.map((c) => c.name)).toEqual(["Spring"]);
    await recolor("a", "#0000ff");
    await recolor("b", "#ffff00");
    await F.applyColorway("Spring");
    await A.whenIdle();
    expect([colorOf("a"), colorOf("b")]).toEqual(["#ff0000", "#00ff00"]);
    A.undoEdit();
    await A.whenIdle();
    expect([colorOf("a"), colorOf("b")]).toEqual(["#0000ff", "#ffff00"]);
    await F.deleteColorway("Spring");
    expect(layoutNow().colorways ?? []).toEqual([]);
  });

  it("saving under a name already used replaces that set, and a blank name saves nothing", async () => {
    await F.saveColorway("Set");
    await recolor("a", "#123456");
    await F.saveColorway("Set");
    await F.saveColorway("   ");
    const sets = layoutNow().colorways ?? [];
    expect(sets.map((c) => c.name)).toEqual(["Set"]);
    expect(sets[0].items.a.thread?.color).toBe("#123456");
  });

  it("a shape added after the set was saved keeps its colour", async () => {
    await F.saveColorway("Old");
    const l = layoutNow();
    await A.commit({ ...l, items: [...l.items, fill("c", "#abcdef")] });
    await F.applyColorway("Old");
    expect(colorOf("c")).toBe("#abcdef");
  });
});

describe("Guides", () => {
  it("guides are set, cleared and come back with undo", async () => {
    await F.setGuides([{ axis: "x", at: 12 }, { axis: "y", at: -3 }]);
    expect(F.guidesOf()).toEqual([{ axis: "x", at: 12 }, { axis: "y", at: -3 }]);
    F.clearGuides();
    await A.whenIdle();
    expect(F.guidesOf()).toEqual([]);
    A.undoEdit();
    await A.whenIdle();
    expect(F.guidesOf()).toHaveLength(2);
    A.redoEdit();
    await A.whenIdle();
    expect(F.guidesOf()).toEqual([]);
  });
});
