// @vitest-environment jsdom
/** Buttonholes and eyelets in the app (a fake engine): what it asks for, and how it adds them. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd/lines";
import { newDoc } from "../design/layout";
import type { LayoutItem, ObjectItem } from "../design/types";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore } from "../store";
import { addSmallObject, BUTTONHOLE, EYELET, lastSizes } from "./smallObjects";

/** What the engine makes (shape.buttonhole): four ordinary shapes. */
const FOUR = ["lip 1", "lip 2", "bar 1", "bar 2"].map((part, i) => ({
  kind: "satin",
  name: `Buttonhole ${part}`,
  geometry: { nodes: [[0, i, "c"], [10, i, "l"]], width_mm: 1.5 },
  params: { spacing_mm: 0.4, underlay: [] },
}));

const asked: [string, Record<string, unknown>][] = [];
let answer: { objects: typeof FOUR; warnings: string[] } | Error = { objects: FOUR, warnings: [] };

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method.startsWith("shape.")) {
      asked.push([method, params]);
      if (answer instanceof Error) throw answer;
      return answer as T;
    }
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "satin", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

const store = () => useStore.getState();
const items = () => (store().history.present?.layout.items ?? []) as ObjectItem[];
const selected = () => [store().selectedId, ...store().extraIds];
async function settled() {
  await whenIdle();
  await new Promise((r) => setTimeout(r, 0));
}

const already = { id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [9, 0, "c"], [9, 9, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" }, transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] } as unknown as ObjectItem;

beforeEach(async () => {
  await whenIdle();
  localStorage.clear();
  asked.length = 0;
  answer = { objects: FOUR, warnings: [] };
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items: [already] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: "a", extraIds: [], dialog: null, tool: "fill", pen: null, notice: null, drawThread: { color: "#cc0000", name: "Red", brand: "", catalog: "" } });
});

describe("buttonholes and eyelets in the app", () => {
  it("a buttonhole is added grouped, selected, in one undo step", async () => {
    expect(await addSmallObject("buttonhole", BUTTONHOLE)).toBe(true);
    await settled();
    expect(asked).toEqual([["shape.buttonhole", { style: "bar", length_mm: 16, width_mm: 5, cut_gap_mm: 1, angle_deg: 0, at: [0, 0] }]]);
    const added = items().slice(1);
    expect(added.map((it) => it.name)).toEqual(FOUR.map((o) => o.name));
    expect(added.map((it) => it.geometry)).toEqual(FOUR.map((o) => o.geometry));
    expect(added.map((it) => it.params)).toEqual(FOUR.map((o) => o.params)); // as made, not your satin settings
    expect(added.every((it) => it.thread.color === "#cc0000")).toBe(true);
    expect(new Set(added.map((it) => it.group)).size).toBe(1);
    expect(added[0].group).toBeTruthy();
    expect(new Set(added.map((it) => it.id)).size).toBe(4);
    expect(selected()).toEqual(added.map((it) => it.id));
    expect(store().tool).toBe("select");
    expect(store().history.past).toHaveLength(1);
    command("edit.undo").run();
    await settled();
    expect(items().map((it) => it.id)).toEqual(["a"]);
  });

  it("an eyelet asks for its two sizes, and says what the engine warns about", async () => {
    answer = { objects: FOUR.slice(0, 2), warnings: ["This satin curves more tightly than it is wide."] };
    await addSmallObject("eyelet", { hole_mm: 2, ring_mm: 3 });
    await settled();
    expect(asked).toEqual([["shape.eyelet", { hole_mm: 2, ring_mm: 3, at: [0, 0] }]]);
    expect(items()).toHaveLength(3);
    expect(store().notice).toEqual({ kind: "info", text: "This satin curves more tightly than it is wide." });
  });

  it("with nothing open, a new design is made first, and one undo takes the buttonhole away again", async () => {
    useStore.setState({ history: { past: [], present: null, future: [] }, savedDoc: null, selectedId: null });
    await addSmallObject("buttonhole", BUTTONHOLE);
    await settled();
    expect(items()).toHaveLength(4);
    expect(store().history.present!.layout.travel_under).toBe(true); // as every new design
    command("edit.undo").run();
    await settled();
    expect(items()).toEqual([]);
  });

  it("the engine's refusal reaches the caller; nothing is added or remembered", async () => {
    answer = new Error("Make the buttonhole wider or the cut narrower");
    await expect(addSmallObject("buttonhole", { ...BUTTONHOLE, width_mm: 3, cut_gap_mm: 2 })).rejects.toThrow("Make the buttonhole wider");
    await settled();
    expect(items()).toHaveLength(1);
    expect(loadPrefs().smallObjects).toBeUndefined();
  });

  it("nothing is added if the dialog was closed before the shapes arrived", async () => {
    expect(await addSmallObject("buttonhole", BUTTONHOLE, () => false)).toBe(false);
    await settled();
    expect(items()).toHaveLength(1);
  });

  it("the sizes used last are kept for each dialog, and a damaged setting falls back", async () => {
    expect(lastSizes("buttonhole", BUTTONHOLE)).toEqual(BUTTONHOLE);
    await addSmallObject("buttonhole", { ...BUTTONHOLE, length_mm: 20, style: "round" });
    await addSmallObject("eyelet", { ...EYELET, hole_mm: 6 });
    await settled();
    expect(lastSizes("buttonhole", BUTTONHOLE)).toEqual({ ...BUTTONHOLE, length_mm: 20, style: "round" });
    expect(lastSizes("eyelet", EYELET)).toEqual({ hole_mm: 6, ring_mm: 1.6 });
    savePrefs({ smallObjects: { eyelet: { hole_mm: "big", ring_mm: 2 } } });
    expect(lastSizes("eyelet", EYELET)).toEqual({ hole_mm: 4, ring_mm: 2 });
  });

  it("Alt+B and Alt+E open their dialogs", () => {
    expect([command("object.buttonhole").shortcut, command("object.eyelet").shortcut]).toEqual(["Alt+B", "Alt+E"]);
    command("object.buttonhole").run();
    expect(store().dialog).toBe("buttonhole");
    command("object.eyelet").run();
    expect(store().dialog).toBe("eyelet");
  });
});
