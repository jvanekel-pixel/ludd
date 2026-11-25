// @vitest-environment jsdom
/** Phase 3: the shape settings moved to ObjectPanel and the fill patterns became data
 *  (design/fillPatterns.ts). The panel shows what it showed before. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { newDoc } from "../design/layout";
import type { Design, Doc, ObjectItem } from "../design/types";
import { savePrefs } from "../prefs";
import { useStore } from "../store";
import { InfoPanel } from "./InfoPanel";
import { objectSummary } from "./ObjectPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const shape = (kind: ObjectItem["kind"], geometry: object, params: object = {}): ObjectItem =>
  ({ id: "a", kind, geometry, params, thread: { color: "#111111", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as unknown as ObjectItem;
const OUTLINE = [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]];
const fill = (params: object = {}) => shape("fill", { outline: OUTLINE }, params);

let root: Root | null = null;
let host: HTMLElement | null = null;

function unmount() {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
}
afterEach(() => {
  unmount();
  localStorage.clear();
});

/** The panel with this fill selected and the folds in its section open; returns that section. */
function show(item: ObjectItem): HTMLElement {
  unmount();
  savePrefs({ sections: { "object@fill": true, "sub:underlay-fill": true, "sub:advanced-fill": true } });
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, items: [item] }, images: [] };
  const design: Design = {
    path: "",
    name: "x",
    format: "pes",
    info: { stitches: 0, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 10, height_mm: 10, bounds_mm: [0, 0, 10, 10] },
    threads: [],
    blocks: [],
    records: { x: [], y: [], kind: [] },
    items: [{ id: "a", name: "Fill 1", kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null }],
  };
  useStore.setState({ history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a", extraIds: [], design, units: "mm" });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<InfoPanel />));
  return host.querySelector<HTMLElement>('section[aria-label="Fill"]')!;
}

const texts = (el: Element, selector: string) => [...el.querySelectorAll(selector)].map((x) => x.textContent);
const rowLabels = (el: Element) => texts(el, ".acc-label");

/** Each pattern's rows, top to bottom, as the panel showed them before the move
 *  ("" is a row with only a button: Draw the angle, Add a satin border). */
const ROWS: Record<string, string[]> = {
  tatami: ["Stitch as", "Density", "Spacing", "Pattern", "Angle", "", "", "Length", "Random", "Edge pad"],
  gradient: ["Stitch as", "Density", "Spacing", "Pattern", "Sparse end", "Angle", "", "", "Length", "Random", "Edge pad"],
  wave: ["Stitch as", "Density", "Spacing", "Pattern", "Wave height", "Wave length", "Angle", "", "", "Length", "Random", "Edge pad"],
  contour: ["Stitch as", "Density", "Spacing", "Pattern", "", "Length"],
  stipple: ["Stitch as", "Pattern", "Loop size", "", "Length"],
  cross: ["Stitch as", "Pattern", "Square", ""],
};

describe("shape settings after the panel split", () => {
  it("the six fill patterns show the fields they showed before", () => {
    for (const [pattern, rows] of Object.entries(ROWS)) {
      const section = show(fill({ pattern }));
      expect(rowLabels(section), pattern).toEqual(rows);
      // The six it offered before the move, first and in the same order; later patterns come after.
      expect(texts(section, 'select[aria-label="Fill pattern"] option').slice(0, 6), pattern).toEqual(["Tatami", "Gradient", "Wave", "Contour", "Stipple", "Cross-stitch"]);
      // Patterns sewn as lines over the shape offer no cross-hatch underlay.
      const open = ["contour", "stipple", "cross"].includes(pattern);
      expect(texts(section, '[aria-label="Underlay"] button'), pattern).toEqual(open ? ["Auto", "Edge"] : ["Auto", "Edge", "Cross-hatch"]);
    }
    // No pattern saved is tatami.
    expect(rowLabels(show(fill()))).toEqual(ROWS.tatami);
  });

  it("stipple hides Density; cross hides Length", () => {
    const stipple = rowLabels(show(fill({ pattern: "stipple" })));
    expect(stipple).not.toContain("Density");
    expect(stipple).not.toContain("Spacing");
    expect(host!.querySelector(".density-slider")).toBeNull();
    expect(stipple).toContain("Length");
    const cross = rowLabels(show(fill({ pattern: "cross" })));
    expect(cross).not.toContain("Length");
    expect(cross).not.toContain("Density");
    expect(host!.querySelector(".density-slider")).toBeNull();
    // Contour is sewn over the shape too, but its rings still follow the spacing.
    expect(rowLabels(show(fill({ pattern: "contour" })))).toContain("Density");
    expect(host!.querySelector(".density-slider")).not.toBeNull();
  });

  it("objectSummary is unchanged", () => {
    expect(objectSummary(fill())).toBe("Normal · 45°");
    expect(objectSummary(fill({ pattern: "contour", spacing_mm: 0.5 }))).toBe("Contour · Light");
    expect(objectSummary(fill({ pattern: "stipple" }))).toBe("Stipple");
    expect(objectSummary(shape("satin", { nodes: [[0, 0, "c"], [10, 0, "c"]], width_mm: 3 }))).toBe("3 mm wide · Normal");
    expect(objectSummary(fill({ pattern: "cross" }))).toBe("Cross-stitch");
    expect(objectSummary(fill({ pattern: "wave", spacing_mm: 0.33, angle_deg: 30.4 }))).toBe("Dense · 30°");
    expect(objectSummary(shape("run", { nodes: OUTLINE }))).toBe("Single · 2.5 mm");
    expect(objectSummary(shape("applique", { outline: OUTLINE }))).toBe("3 mm border");
  });
});
