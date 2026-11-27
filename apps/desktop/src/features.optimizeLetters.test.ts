/** Optimize jumps also moves a text's first letter (P7-B3): the app has to keep that change. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { whenIdle } from "./actions";
import { newDoc } from "./design/layout";
import type { LayoutItem, TextItem } from "./design/types";
import { optimizeJumps } from "./features";
import { useStore } from "./store";

const LETTERS = { "0": { start_mm: [1.5, 2] as [number, number] } };

const text = {
  id: "t",
  kind: "text",
  text: "AB",
  font: { path: "f.ttf", index: 0, family: "F", style: "Regular" },
  size_mm: 10,
  spacing_mm: 0,
  style: "satin",
  shape: { type: "line" },
  monogram: false,
  thread: { color: "#000000", name: "Black", brand: "", catalog: "" },
  transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
  threads: [],
  ops: [],
} as TextItem;

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "layout.optimize_jumps") return { changes: { t: { letters: LETTERS } }, before_mm: 30, after_mm: 10 } as T;
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: "text", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

beforeEach(async () => {
  await whenIdle();
  const doc = { ...newDoc(), layout: { ...newDoc().layout, items: [text] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, notice: null });
});

describe("Optimize jumps and lettering", () => {
  it("keeps where the first letter now starts", async () => {
    await optimizeJumps();
    await whenIdle();
    expect((useStore.getState().history.present!.layout.items[0] as TextItem).letters).toEqual(LETTERS);
  });
});
