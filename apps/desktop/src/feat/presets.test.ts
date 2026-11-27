// @vitest-environment jsdom
/** Stitch presets in the app (P7-C4): what a preset keeps, applying it to the selected shapes of
 *  its kind in one undo step, and "Use for new shapes" (a fake engine). */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { COMMANDS, currentLayout, defaultsFor, undoEdit, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import type { LayoutItem, ObjectItem } from "../design/types";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore } from "../store";
import { applyPreset, presetFrom, summary, targetsOf, useForNewShapes, type Preset } from "./presets";

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

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const THREAD = { color: "#cc0000", name: "Red", brand: "", catalog: "" };
const shape = (id: string, kind: ObjectItem["kind"], params: object, geometry?: object, transform = IDENT): ObjectItem =>
  ({
    id, kind, params, thread: THREAD, transform, threads: [], ops: [],
    geometry: geometry ?? (kind === "satin" ? { nodes: [[0, 0, "s"], [20, 0, "s"]], width_mm: 3 } : kind === "run" ? { nodes: [[0, 0, "s"], [20, 0, "s"]] } : { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]], carve: [[[1, 1, "s"], [8, 8, "s"]]] }),
  }) as unknown as ObjectItem;

const PER_SHAPE = {
  angle_deg: 30, reverse: true, start_mm: [1, 2], end_mm: [3, 4], angle_line: [[0, 0], [1, 1]],
  angle_lines: [[[0, 0], [1, 1]], [[2, 2], [3, 3]]], ripple_center: [5, 5], blend_flip: true, push_comp_mm: 0.4,
};
const preset = (over: Partial<Preset>): Preset => ({ id: "p", name: "P", kind: "fill", params: {}, width_mm: null, note: null, builtin: false, ...over });

function setDoc(...items: LayoutItem[]) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], pen: null, tool: "select", notice: null });
}
const item = (id: string) => currentLayout()!.items.find((it) => it.id === id) as ObjectItem;

beforeEach(async () => {
  await whenIdle();
  savePrefs({ objectDefaults: undefined, satinWidth: undefined });
});

describe("stitch presets", () => {
  it("a preset leaves out per-shape settings", () => {
    const fill = shape("f", "fill", { pattern: "tatami", spacing_mm: 0.5, underlay: ["edge"], tie_in: false, ...PER_SHAPE, hand_pct: undefined });
    expect(presetFrom(fill, "Mine")).toEqual({ name: "Mine", kind: "fill", params: { pattern: "tatami", spacing_mm: 0.5, underlay: ["edge"], tie_in: false } });
    // A ribbon's width goes with it, as it sews: here the handles made it 1.5 times as wide.
    const ribbon = shape("s", "satin", { spacing_mm: 0.4, start_mm: [0, 0] }, undefined, { ...IDENT, scale_x: 1.5, scale_y: 1.5 });
    expect(presetFrom(ribbon, "Edge")).toEqual({ name: "Edge", kind: "satin", params: { spacing_mm: 0.4 }, width_mm: 4.5 });
    // Kept within the widths a ribbon can have.
    expect(presetFrom({ ...ribbon, transform: { ...IDENT, scale_x: 9, scale_y: 9 } }, "Wide").width_mm).toBe(12);
    // A satin clicked side by side has no width to keep.
    expect(presetFrom(shape("c", "satin", {}, { rail_a: [[0, 0, "s"]], rail_b: [[0, 2, "s"]] }), "Columns")).not.toHaveProperty("width_mm");
  });

  it("applying changes only shapes of its kind, in one undo step", async () => {
    const a = shape("a", "fill", { spacing_mm: 0.4, stipple_mm: 5, angle_deg: 15, start_mm: [1, 1] });
    const b = shape("b", "fill", { pattern: "contour", angle_deg: 70, angle_lines: PER_SHAPE.angle_lines });
    const c = shape("c", "satin", { spacing_mm: 0.6 });
    const d = shape("d", "fill", { spacing_mm: 0.9 });
    setDoc(a, b, c, d);
    useStore.getState().setSelection("a", ["b", "c"]);
    const p = preset({ params: { pattern: "tatami", spacing_mm: 0.7, underlay: [] } });
    expect(targetsOf(p).map((o) => o.id)).toEqual(["a", "b"]);
    await expect(applyPreset(p)).resolves.toBe(2);
    // Each gets exactly the preset's settings, keeping what's its own; nothing else changes.
    expect(item("a").params).toEqual({ pattern: "tatami", spacing_mm: 0.7, underlay: [], angle_deg: 15, start_mm: [1, 1] });
    expect(item("b").params).toEqual({ pattern: "tatami", spacing_mm: 0.7, underlay: [], angle_deg: 70, angle_lines: PER_SHAPE.angle_lines });
    expect(item("a").geometry).toEqual(a.geometry); // carved lines and all
    expect(item("c")).toBe(c);
    expect(item("d")).toBe(d);
    expect(useStore.getState().history.past).toHaveLength(1);
    undoEdit();
    await whenIdle();
    expect(currentLayout()!.items).toEqual([a, b, c, d]);
  });

  it("gives a ribbon the preset's width as it sews, whatever the handles did to it", async () => {
    const resized = shape("a", "satin", {}, undefined, { ...IDENT, scale_x: 2, scale_y: 0.5, rotate: 20 });
    const plain = shape("b", "satin", { pull_comp_mm: 0.3 }, undefined, { ...IDENT, scale_x: 4, scale_y: 4 });
    setDoc(resized, plain);
    useStore.getState().setSelection("a", ["b"]);
    await applyPreset(preset({ kind: "satin", params: { spacing_mm: 0.35 }, width_mm: 2 }));
    expect((item("a").geometry as { width_mm: number }).width_mm).toBe(2);
    expect((item("b").geometry as { width_mm: number }).width_mm).toBe(0.5);
    expect(item("b").params).toEqual({ spacing_mm: 0.35 });
    // A preset without a width leaves widths alone.
    await applyPreset(preset({ kind: "satin", params: {} }));
    expect((item("b").geometry as { width_mm: number }).width_mm).toBe(0.5);
  });

  it("does nothing without a selected shape of its kind", async () => {
    setDoc(shape("a", "fill", {}));
    await expect(applyPreset(preset({ kind: "run" }))).resolves.toBe(0);
    useStore.getState().select("a");
    await expect(applyPreset(preset({ kind: "run" }))).resolves.toBe(0);
    expect(useStore.getState().history.past).toHaveLength(0);
  });

  it("Use for new shapes makes new shapes of the kind start with it", () => {
    savePrefs({ objectDefaults: { fill: { spacing_mm: 0.3, stipple_mm: 4 }, run: { style: "triple" } } });
    useForNewShapes(preset({ params: { pattern: "contour", spacing_mm: 0.8 } }));
    expect(loadPrefs().objectDefaults).toEqual({ fill: { pattern: "contour", spacing_mm: 0.8 }, run: { style: "triple" } });
    expect(defaultsFor("fill")).toMatchObject({ pattern: "contour", spacing_mm: 0.8 });
    expect(defaultsFor("fill")).not.toHaveProperty("stipple_mm");
    useForNewShapes(preset({ kind: "satin", params: { spacing_mm: 0.35 }, width_mm: 2 }));
    expect([useStore.getState().satinWidth, loadPrefs().satinWidth]).toEqual([2, 2]);
  });

  it("sums a preset up in a few words", () => {
    expect(summary(preset({ kind: "run", params: { style: "bean", stitch_mm: 2.5 } }))).toBe("Line · Bean · stitches 2.5 mm");
    expect(summary(preset({ kind: "satin", params: { spacing_mm: 0.35 }, width_mm: 5.5 }))).toBe("Satin · 5.5 mm wide · spacing 0.35 mm");
    expect(summary(preset({ params: { pattern: "contour", spacing_mm: 1 } }))).toBe("Fill · Contour · spacing 1 mm");
    expect(summary(preset({ kind: "applique", params: { cover_width_mm: 2.5, tack: "run" } }))).toBe("Applique · border 2.5 mm · straight tack-down");
    expect(summary(preset({ kind: "run", params: { style: "redwork" } }))).toMatch(/^Line · Redwork/);
  });

  it("is registered as Alt+P and opens its window", () => {
    expect(COMMANDS.find((c) => c.id === "presets.open")?.shortcut).toBe("Alt+P");
    setDoc();
    COMMANDS.find((c) => c.id === "presets.open")!.run();
    expect(useStore.getState().dialog).toBe("presets");
  });
});
