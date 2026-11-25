/** "Don't sew what's hidden under shapes on top" (P4-A2): the switch and "Keep under the edge". A
 *  fake engine; no browser. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, currentLayout, newProject, whenIdle } from "../actions";
import "../cmd/repair";
import { newDoc } from "../design/layout";
import type { Layout, LayoutItem } from "../design/types";
import { useStore } from "../store";
import { keepUnderEdge, setKeepUnderEdge, toggleRemoveOverlap } from "./overlap";

const fill = { id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" }, transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] } as unknown as LayoutItem;

const sent: Layout[] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const layout = params.layout as Layout;
    sent.push(layout);
    return {
      path: "", name: "x", format: "layout",
      info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
      threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null })),
    } as T;
  },
};

function setDoc(extra: Partial<Layout> = {}) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [fill], ...extra } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], notice: null });
}

const setting = () => currentLayout()!.remove_overlap;
const past = () => useStore.getState().history.past.length;
const notice = () => useStore.getState().notice?.text ?? "";

beforeEach(async () => {
  await whenIdle();
  sent.length = 0;
  setDoc();
});

describe("the switch", () => {
  it("turns on with 1 mm kept under the edge, as one undo step, saying how to undo it", async () => {
    await toggleRemoveOverlap();
    expect(setting()).toEqual({ enabled: true, keep_mm: 1 });
    expect(sent.at(-1)!.remove_overlap).toEqual({ enabled: true, keep_mm: 1 });
    expect(past()).toBe(1);
    expect(notice()).toMatch(/Ctrl\+Z undoes it/);
    expect(notice()).toMatch(/leave out/);
    command("edit.undo").run();
    await whenIdle();
    expect(setting()).toBeUndefined();
  });

  it("turns off again, keeping the margin chosen, one undo step each way", async () => {
    setDoc({ remove_overlap: { enabled: true, keep_mm: 2 } });
    await toggleRemoveOverlap();
    expect(setting()).toEqual({ enabled: false, keep_mm: 2 });
    expect(notice()).toMatch(/sewn whole/);
    expect(notice()).toMatch(/Ctrl\+Z undoes it/);
    await toggleRemoveOverlap();
    expect(setting()).toEqual({ enabled: true, keep_mm: 2 });
    expect(past()).toBe(2);
  });

  it("is what its command runs", async () => {
    command("object.removeOverlap").run();
    await whenIdle();
    expect(setting()).toEqual({ enabled: true, keep_mm: 1 });
  });

  it("isn't on in new designs, which don't have the setting at all", async () => {
    expect("remove_overlap" in newDoc().layout).toBe(false);
    setDoc();
    useStore.setState({ savedDoc: useStore.getState().history.present });
    await newProject();
    expect(currentLayout()!.items).toEqual([]);
    expect("remove_overlap" in currentLayout()!).toBe(false);
  });
});

describe("Keep under the edge", () => {
  it("is 1 mm unless set, and always within 0.5 to 3 mm, as the engine holds it", () => {
    const at = (keep_mm: unknown) => keepUnderEdge({ ...newDoc().layout, remove_overlap: { enabled: true, keep_mm: keep_mm as number } });
    expect([undefined, "2", Number.NaN, 0.1, 0.5, 1.7, 3, 40].map(at)).toEqual([1, 1, 1, 0.5, 0.5, 1.7, 3, 3]);
  });

  it("is kept in range, one undo step, and an unchanged value is no step at all", async () => {
    setDoc({ remove_overlap: { enabled: true, keep_mm: 1 } });
    await setKeepUnderEdge(10);
    expect(setting()).toEqual({ enabled: true, keep_mm: 3 });
    await setKeepUnderEdge(0.1);
    expect(setting()).toEqual({ enabled: true, keep_mm: 0.5 });
    await setKeepUnderEdge(1.2699999999);
    expect(setting()!.keep_mm).toBe(1.27);
    expect(past()).toBe(3);
    await setKeepUnderEdge(1.27);
    expect(past()).toBe(3);
  });
});
