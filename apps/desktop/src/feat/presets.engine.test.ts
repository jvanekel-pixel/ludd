// @vitest-environment jsdom
/** Stitch presets with the real engine (P7-C4): a satin resized with the handles saved as a preset,
 *  applied to another resized one, which then sews just as wide; shared as a file and brought back
 *  (testEngine.ts starts the engine). */
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import { Kind, type Design, type LayoutItem, type ObjectItem } from "../design/types";
import { useStore } from "../store";
import { applyPreset, deletePreset, loadPresets, savePreset, usePresets, type Preset } from "./presets";
import { ENGINE_START_MS, startEngine } from "./testEngine";

let engine: ReturnType<typeof startEngine>;
let shared: string;

beforeAll(async () => {
  engine = startEngine();
  shared = mkdtempSync(path.join(os.tmpdir(), "ludd-shared-"));
  await engine.call("ping");
}, ENGINE_START_MS);

afterAll(async () => {
  await engine?.stop();
  rmSync(shared, { recursive: true, force: true });
}, 60_000);

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
/** A level satin ribbon 20 mm long at height y, resized k times with the handles. */
const ribbon = (id: string, y: number, width: number, k: number, params: object = {}): ObjectItem =>
  ({
    id, kind: "satin", geometry: { nodes: [[-10 / k, y, "l"], [10 / k, y, "l"]], width_mm: width }, params,
    thread: { color: "#1f3a93", name: "Navy", brand: "", catalog: "" }, transform: { ...IDENT, scale_x: k, scale_y: k }, threads: [], ops: [],
  }) as unknown as ObjectItem;

/** How wide a level ribbon's stitches reach, mm. */
function sewnWidth(design: Design, index: number): number {
  const { y, kind, item } = design.records;
  const ys = y.filter((_, i) => item![i] === index && kind[i] === Kind.Stitch);
  return Math.max(...ys) - Math.min(...ys);
}

describe("stitch presets with the real engine", () => {
  it(
    "a resized satin's preset sews just as wide on another resized one",
    async () => {
      await whenIdle();
      // Drawn 2 mm wide and made 1.5 times as big: 3 mm as it sews. The other is drawn 1 mm wide,
      // made twice as big, and has settings of its own.
      const source = ribbon("a", 0, 2, 1.5, { spacing_mm: 0.35, pull_comp_mm: 0.3, underlay: ["center"], start_mm: [0, 0] });
      const other = ribbon("b", 20, 1, 2, { spacing_mm: 0.8 });
      const d = newDoc();
      const doc = { ...d, layout: { ...d.layout, items: [source, other] as LayoutItem[] } };
      useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "b", extraIds: [], pen: null, tool: "select", notice: null });
      await loadPresets();
      expect(usePresets.getState().list!.map((p) => p.name)).toEqual(["Light sketch fill", "Bold outline", "Redwork line", "Narrow satin border", "Felt applique"]);

      const id = await savePreset(source, "Wide edge");
      const saved = usePresets.getState().list!.find((p) => p.id === id)!;
      expect(saved).toEqual<Preset>({ id, name: "Wide edge", kind: "satin", params: { spacing_mm: 0.35, pull_comp_mm: 0.3, underlay: ["center"] }, width_mm: 3, note: null, builtin: false });
      await expect(savePreset(source, "wide edge")).rejects.toThrow(/already have a preset called/);

      await expect(applyPreset(saved)).resolves.toBe(1);
      const applied = currentLayout()!.items[1] as ObjectItem;
      expect(applied.params).toEqual(saved.params);
      expect((applied.geometry as { width_mm: number }).width_mm).toBe(1.5);
      const design = useStore.getState().design!;
      expect(sewnWidth(design, 0)).toBeCloseTo(3.3, 1); // 3 mm and 0.3 of edge pad
      expect(sewnWidth(design, 1)).toBeCloseTo(sewnWidth(design, 0), 1);

      // Shared as a file and brought back, it's the same preset.
      const { path: file } = await engine.call<{ path: string }>("presets.export", { id, dest: path.join(shared, "edge") });
      expect(JSON.parse(readFileSync(file, "utf8"))).toMatchObject({ format: "ludd-preset", version: 1, name: "Wide edge", kind: "satin", width_mm: 3 });
      await deletePreset(id);
      await engine.call("presets.import", { path: file });
      await loadPresets();
      expect(usePresets.getState().list!.at(-1)).toEqual({ ...saved, id: expect.any(String) });
    },
    ENGINE_START_MS,
  );
});
