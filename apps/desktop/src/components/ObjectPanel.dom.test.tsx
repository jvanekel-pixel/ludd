// @vitest-environment jsdom
/** Phase 3: the shape settings moved to ObjectPanel and the fill patterns became data
 *  (design/fillPatterns.ts). The panel shows what it showed before. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { whenIdle } from "../actions";
import "../cmd"; // registers the commands the panel's buttons run (object.carve)
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
  return showKind(item, "Fill");
}

/** The panel with this shape selected and its section's folds open; returns the section titled `title`. */
function showKind(item: ObjectItem, title: string): HTMLElement {
  unmount();
  const k = item.kind;
  savePrefs({ sections: { [`object@${k}`]: true, [`size@${k}`]: true, [`sub:underlay-${k}`]: true, [`sub:advanced-${k}`]: true } });
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
  return host.querySelector<HTMLElement>(`section[aria-label="${title}"]`)!;
}

const texts = (el: Element, selector: string) => [...el.querySelectorAll(selector)].map((x) => x.textContent);
const rowLabels = (el: Element) => texts(el, ".acc-label");

/** Each pattern's rows, top to bottom, as the panel showed them before the move, with Phase 7's
 *  Lock stitches under the lock boxes ("" is a row with only a button: Draw the angle, Add a satin
 *  border). */
const ROWS: Record<string, string[]> = {
  // Phase 6 (Track A) adds Weave, Feather and Hand-sewn look to Advanced, after Edge pad.
  tatami: ["Stitch as", "Density", "Spacing", "Pattern", "Angle", "", "", "Length", "Random", "Edge pad", "Weave", "Feather", "Hand-sewn look", "Lock stitches"],
  gradient: ["Stitch as", "Density", "Spacing", "Pattern", "Sparse end", "Angle", "", "", "Length", "Random", "Edge pad", "Weave", "Feather", "Hand-sewn look", "Lock stitches"],
  wave: ["Stitch as", "Density", "Spacing", "Pattern", "Wave height", "Wave length", "Angle", "", "", "Length", "Random", "Edge pad", "Feather", "Hand-sewn look", "Lock stitches"],
  contour: ["Stitch as", "Density", "Spacing", "Pattern", "", "Length", "Lock stitches"],
  stipple: ["Stitch as", "Pattern", "Loop size", "", "Length", "Lock stitches"],
  cross: ["Stitch as", "Pattern", "Square", "", "Lock stitches"],
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

  it("Spiral shows Ring spacing and hides Density and Angle", () => {
    const section = show(fill({ pattern: "spiral" }));
    expect(rowLabels(section)).toEqual(["Stitch as", "Pattern", "Ring spacing", "", "Length", "Lock stitches"]);
    expect(host!.querySelector(".density-slider")).toBeNull();
    expect(texts(section, 'select[aria-label="Fill pattern"] option')).toContain("Spiral");
    expect(texts(section, '[aria-label="Underlay"] button')).toEqual(["Auto", "Edge"]);
    expect(objectSummary(fill({ pattern: "spiral" }))).toBe("Spiral");
    // Length stops at 4 mm: longer stitches would cut across the turns.
    const longer = show(fill({ pattern: "spiral", stitch_mm: 4 })).querySelector<HTMLButtonElement>('button[aria-label="More length"]')!;
    expect(longer.disabled).toBe(true);
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

  it("a turning fill's heading says it follows its lines; another pattern keeps its angle", () => {
    const lines = [[[0, 0], [10, 0]], [[0, 5], [10, 9]]];
    expect(objectSummary(fill({ angle_lines: lines }))).toBe("Normal · follows 2 lines");
    expect(objectSummary(fill({ angle_lines: [[[0, 2], [10, 2]], [[5, 0], [5, 4]]] }))).toBe("Normal · follows 1 of 2 lines");
    expect(objectSummary(fill({ pattern: "gradient", angle_lines: lines }))).toBe("Normal · 45°");
  });
});

describe("Phase 6: weave, feathered edges, the hand-sewn look and carved lines (Track A)", () => {
  const advanced = (section: HTMLElement) => rowLabels(section).slice(rowLabels(section).indexOf("Edge pad") + 1);

  it("Weave, Feather and Hand-sewn look appear under Advanced for a tatami fill and not for stipple", () => {
    const tatami = show(fill());
    expect(advanced(tatami)).toEqual(["Weave", "Feather", "Hand-sewn look", "Lock stitches"]);
    expect(texts(tatami, 'select[aria-label="Weave"] option')).toEqual(["Standard", "Brick", "Twill", "Smooth", "Random"]);
    expect(texts(tatami, '[aria-label="Feather"] button')).toEqual(["Off", "Left ends", "Right ends", "Both"]);
    expect(tatami.querySelector('input[aria-label="Hand-sewn look"]')).not.toBeNull();
    expect(texts(tatami, "button")).toContain("Carve lines (Shift+C)");
    // Off: no Depth, no picture.
    expect(tatami.querySelector(".feather-picture")).toBeNull();

    const stipple = show(fill({ pattern: "stipple" }));
    for (const label of ["Weave", "Feather", "Hand-sewn look", "Depth"]) expect(rowLabels(stipple)).not.toContain(label);
    expect(stipple.querySelector('input[aria-label="Hand-sewn look"]')).toBeNull();
    expect(texts(stipple, "button")).not.toContain("Carve lines (Shift+C)");
  });

  it("a feathered fill shows Depth and which side is which", () => {
    const section = show(fill({ feather: "left", feather_mm: 3 }));
    expect(advanced(section)).toEqual(["Weave", "Feather", "Depth", "Hand-sewn look", "Lock stitches"]);
    expect(section.querySelector('[aria-label="Feather"] button[aria-pressed="true"]')?.textContent).toBe("Left ends");
    expect(section.querySelector(".feather-picture")?.getAttribute("aria-label")).toMatch(/Left and right/);
  });

  it("wave: Feather and Hand-sewn look, no Weave (its rows copy each other)", () => {
    expect(advanced(show(fill({ pattern: "wave" })))).toEqual(["Feather", "Hand-sewn look", "Lock stitches"]);
  });

  it("a blend offers no cross-hatch underlay, which it never sews", () => {
    expect(texts(show(fill({ pattern: "blend" })), '[aria-label="Underlay"] button')).toEqual(["Auto", "Edge"]);
  });

  it("lines and satins have the Hand-sewn look; motif lines don't", () => {
    const run = showKind(shape("run", { nodes: OUTLINE }, { hand_pct: 40 }), "Line");
    expect(rowLabels(run)).toContain("Hand-sewn look");
    expect(run.querySelector<HTMLInputElement>('input[aria-label="Hand-sewn look"]')?.value).toBe("40");
    for (const label of ["Weave", "Feather"]) expect(rowLabels(run)).not.toContain(label);
    expect(rowLabels(showKind(shape("run", { nodes: OUTLINE }, { style: "motif" }), "Line"))).not.toContain("Hand-sewn look");
    const satin = showKind(shape("satin", { nodes: [[0, 0, "c"], [10, 0, "c"]], width_mm: 3 }), "Satin");
    expect(rowLabels(satin)).toContain("Hand-sewn look");
    expect(rowLabels(satin)).not.toContain("Weave");
  });
});

describe("Phase 7: line styles, lock stitches and blackwork (Track A)", () => {
  const line = (params: object = {}) => showKind(shape("run", { nodes: OUTLINE }, params), "Line");
  const pressed = (section: HTMLElement) => texts(section, '[aria-label="Line style"] button[aria-pressed="true"]');
  const select = (section: HTMLElement, label: string) => section.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`);

  /** Answers a render with the design already on screen, so a change can be read back from the store. */
  const drawing = { call: async <T,>(method: string): Promise<T> => (method === "layout.render" ? useStore.getState().design : null) as T };
  const params = () => (useStore.getState().history.present!.layout.items[0] as ObjectItem).params as Record<string, unknown>;
  const change = async (what: () => void) => {
    await act(async () => {
      what();
      await whenIdle();
    });
  };
  const pick = (el: HTMLSelectElement, value: string) =>
    change(() => {
      el.value = value;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
  const press = (section: HTMLElement, group: string, label: string) =>
    change(() => [...section.querySelectorAll<HTMLButtonElement>(`[aria-label="${group}"] button`)].find((b) => b.textContent === label)!.click());

  it("five more styles sit behind More styles", () => {
    const section = line();
    expect(texts(section, '[aria-label="Line style"] button')).toEqual(["Single", "Triple", "Bean", "Motif"]);
    expect(texts(section, 'select[aria-label="More styles"] option')).toEqual(["More styles…", "Backstitch", "Stem stitch", "Candlewicking", "Redwork", "French knots"]);
    expect(select(section, "More styles")!.value).toBe("");
    expect(pressed(section)).toEqual(["Single"]);
  });

  it("Stem stitch shows Width and presses none of the four buttons", () => {
    const section = line({ style: "stem" });
    expect(pressed(section)).toEqual([]);
    expect(select(section, "More styles")!.value).toBe("stem");
    expect(rowLabels(section)).toContain("Width");
    expect(section.querySelector<HTMLInputElement>(".stepper input")!.value).toBe("0.8");
  });

  it("each line style shows only its own settings", () => {
    const plain = ["Stitch as", "Style", "Length", "Hand-sewn look", "Lock stitches"];
    const rows: Record<string, string[]> = {
      single: plain,
      triple: plain,
      bean: plain,
      motif: ["Stitch as", "Style", "Motif", "", "Repeat", "Width", "Which side", "Length", "Lock stitches"],
      backstitch: ["Stitch as", "Style", "Length", "Lock stitches"],
      stem: ["Stitch as", "Style", "Width", "Length", "Lock stitches"],
      candlewick: ["Stitch as", "Style", "Knot size", "Between knots", "Length", "Lock stitches"],
      redwork: ["Stitch as", "Style", "Length", "Lock stitches"],
      knots: ["Stitch as", "Style", "Knot size", "Lock stitches"], // a stitch length would change nothing
    };
    for (const [style, want] of Object.entries(rows)) expect(rowLabels(line({ style })), style).toEqual(want);
  });

  it("a motif line's Which side sits under its Width", () => {
    const section = line({ style: "motif", motif_side: "right" });
    expect(texts(section, '[aria-label="Which side"] button')).toEqual(["Centered", "Left", "Right"]);
    expect(texts(section, '[aria-label="Which side"] button[aria-pressed="true"]')).toEqual(["Right"]);
    expect(texts(line({ style: "motif" }), '[aria-label="Which side"] button[aria-pressed="true"]')).toEqual(["Centered"]);
    // A motif fill has no side: its rows cross the whole shape.
    expect(rowLabels(show(fill({ pattern: "motif" })))).not.toContain("Which side");
  });

  it("Lock stitches appears when a lock box is ticked", () => {
    const kinds = [
      line,
      (p: object) => showKind(shape("satin", { nodes: [[0, 0, "c"], [10, 0, "c"]], width_mm: 3 }, p), "Satin"),
      (p: object) => show(fill(p)),
    ];
    for (const open of kinds) {
      expect(texts(open({}), 'select[aria-label="Lock stitches"] option')).toEqual(["Standard", "Triangle", "Back-tack"]);
      expect(select(open({ tie_in: false }), "Lock stitches")).not.toBeNull();
      expect(select(open({ tie_off: false }), "Lock stitches")).not.toBeNull();
      expect(select(open({ tie_in: false, tie_off: false }), "Lock stitches")).toBeNull();
      expect(select(open({ tie_style: "backtack" }), "Lock stitches")!.value).toBe("backtack");
    }
    // An applique locks at its stops, the usual way.
    expect(select(showKind(shape("applique", { outline: OUTLINE }), "Applique"), "Lock stitches")).toBeNull();
  });

  it("blackwork shows its lattice and cell size, and no Density or Angle", () => {
    const section = show(fill({ pattern: "blackwork" }));
    expect(rowLabels(section)).toEqual(["Stitch as", "Pattern", "Lattice", "Cell size", "", "Length", "Lock stitches"]);
    expect(texts(section, 'select[aria-label="Lattice"] option')).toEqual(["Diamonds", "Grid", "Honeycomb", "Crossed"]);
    expect(select(section, "Lattice")!.value).toBe("diamonds");
    expect(texts(section, '[aria-label="Underlay"] button')).toEqual(["Auto", "Edge"]);
    expect(texts(section, 'select[aria-label="Fill pattern"] option')).toContain("Blackwork");
    expect(rowLabels(show(fill({ pattern: "tatami" })))).not.toContain("Lattice");
  });

  it("the folded heading names each new style as you know it", () => {
    const heading = (style?: string) => objectSummary(shape("run", { nodes: OUTLINE }, style ? { style } : {}));
    expect([undefined, "triple", "bean", "motif", "backstitch", "stem", "candlewick", "redwork", "knots"].map(heading)).toEqual([
      "Single · 2.5 mm",
      "Triple · 2.5 mm",
      "Bean · 2.5 mm",
      "Motif · 2.5 mm",
      "Backstitch · 2.5 mm",
      "Stem stitch · 2.5 mm",
      "Candlewicking · 2.5 mm",
      "Redwork · 2.5 mm",
      "French knots",
    ]);
    expect(objectSummary(fill({ pattern: "blackwork" }))).toBe("Blackwork");
  });

  it("a style, side, lattice or lock chosen is saved, and the usual ones leave nothing behind", async () => {
    let section = line();
    useStore.setState({ engine: drawing as never });
    await pick(select(section, "More styles")!, "candlewick");
    expect(params().style).toBe("candlewick");
    await pick(select(section, "Lock stitches")!, "triangle");
    expect(params().tie_style).toBe("triangle");
    await pick(select(section, "Lock stitches")!, "standard");
    expect(params().tie_style).toBeUndefined();
    await press(section, "Line style", "Single");
    expect(params().style).toBe("single");

    section = line({ style: "motif" });
    await press(section, "Which side", "Left");
    expect(params().motif_side).toBe("left");
    await press(section, "Which side", "Centered");
    expect(params().motif_side).toBeUndefined();

    section = show(fill({ pattern: "blackwork" }));
    await pick(select(section, "Lattice")!, "honeycomb");
    expect(params().blackwork_lattice).toBe("honeycomb");
  });
});

describe("Phase 7: the hint under Add points (K)", () => {
  const START = "Select the first point to add at the start.";
  const LINE = [[0, 0, "c"], [10, 0, "c"]];
  const sizeText = (item: ObjectItem) => showKind(item, "Size and points").textContent!;

  it("says how to add at the start only where K can: open lines and satin ribbons", () => {
    expect(sizeText(shape("run", { nodes: LINE }))).toContain(START);
    expect(sizeText(shape("satin", { nodes: LINE, width_mm: 3 }))).toContain(START);
    const column = { rail_a: LINE, rail_b: [[0, 3, "c"], [10, 3, "c"]] };
    for (const item of [shape("run", { nodes: [...LINE, [10, 10, "c"]], closed: true }), shape("satin", column), fill()]) {
      expect(sizeText(item)).not.toContain(START);
    }
  });
});
