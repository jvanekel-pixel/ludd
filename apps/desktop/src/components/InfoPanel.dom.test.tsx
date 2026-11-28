// @vitest-environment jsdom
/** QA pass 2, U8: the sewing-order row drag ends on a lost mouse-up and when the panel goes away. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { newDoc } from "../design/layout";
import type { Doc, ObjectItem } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { useStore } from "../store";
import { InfoPanel } from "./InfoPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fill = (id: string): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as ObjectItem;

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  while (letGoNewest());
});

function show() {
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, items: [fill("a"), fill("b")] }, images: [] };
  useStore.setState({ history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], design: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<InfoPanel />));
}

function grab() {
  const grip = host!.querySelector<HTMLElement>('li[data-row="a"] .grip')!;
  act(() => {
    grip.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, button: 0 }));
  });
}

describe("sewing-order row drag", () => {
  it("a move with no button down ends the drag (the mouse-up was lost)", () => {
    show();
    grab();
    expect(heldCount()).toBe(1);
    expect(host!.querySelector(".design-list.reordering")).not.toBeNull();
    act(() => {
      window.dispatchEvent(new MouseEvent("pointermove", { buttons: 0, clientY: 0 }));
    });
    expect(heldCount()).toBe(0);
    expect(host!.querySelector(".design-list.reordering")).toBeNull();
  });

  it("the panel going away mid-drag lets go of Esc and the window listeners", () => {
    show();
    grab();
    expect(heldCount()).toBe(1);
    const removed = vi.spyOn(window, "removeEventListener");
    act(() => root!.unmount());
    root = null;
    expect(heldCount()).toBe(0);
    expect(removed.mock.calls.map((c) => c[0])).toEqual(expect.arrayContaining(["pointermove", "pointerup", "pointercancel", "blur"]));
    removed.mockRestore();
  });
});

describe("Order & colors: a branch's shapes", () => {
  // The audit's case: shapes d, a, c, b of one branch, in that order in the design, sew d, c, a, b.
  it("are listed in the order they sew, and the arrows step through that order", () => {
    const d = newDoc();
    const items = ["d", "a", "c", "b"].map((id) => ({ ...fill(id), name: `Shape ${id}`, branch: "B" }));
    const doc: Doc = { layout: { ...d.layout, items }, images: [] };
    useStore.setState({
      history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [],
      design: {
        path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [] },
        info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
        branches: [{ id: "B", items: ["d", "c", "a", "b"], start: [0, 0], end: [1, 1], hidden_mm: 0, cuts: 0 }],
      } as never,
    });
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    act(() => root!.render(<InfoPanel />));
    const rows = [...host.querySelectorAll<HTMLElement>("li[data-row]")];
    expect(rows.map((r) => r.dataset.row)).toEqual(["d", "c", "a", "b"]);
    expect(rows.map((r) => r.querySelector(".name")!.textContent)).toEqual(["1. Shape d", "2. Shape c", "3. Shape a", "4. Shape b"]);
    const arrows = (label: string) => rows.map((r) => r.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!.disabled);
    expect(arrows("Sew earlier")).toEqual([true, false, false, false]);
    expect(arrows("Sew later")).toEqual([false, false, false, true]);
  });
});

describe("Design panel: sewing time and thread", () => {
  it("shows about how long the design sews on this machine and how much thread it uses", () => {
    const d = newDoc();
    const doc: Doc = { layout: { ...d.layout, items: [fill("a")] }, images: [] };
    // 1300 stitches, 1 mm apart, in two colors: 2 minutes at 650 a minute; one thread change.
    const n = 1300;
    const kind = [...Array(650).fill(0), 4, ...Array(650).fill(0), 5];
    const x = kind.map((_, i) => i);
    const y = kind.map(() => 0);
    useStore.setState({
      history: { past: [], present: doc, future: [] },
      savedDoc: doc,
      selectedId: null,
      extraIds: [],
      units: "mm",
      machineId: "pe",
      machines: [{ id: "pe", name: "PE", brand: "", formats: ["pes"], needles: 1, hoops: [{ id: "h", name: "h", width_mm: 100, height_mm: 100 }], cuts: "color_change", max_stitch_mm: null, max_stitches: null, max_colors: null, speed_spm: 650, notes: "", builtin: true }],
      design: {
        path: "",
        name: "x",
        format: "pes",
        info: { stitches: n, jumps: 0, trims: 0, stops: 0, color_changes: 1, colors: 2, width_mm: 50, height_mm: 0, bounds_mm: [0, 0, 50, 0] },
        threads: [
          { color: "#ff0000", name: "Red", brand: "", catalog: "" },
          { color: "#0000ff", name: "Blue", brand: "", catalog: "" },
        ],
        blocks: [
          { thread: 0, start: 0, end: 650 },
          { thread: 1, start: 651, end: 1301 },
        ],
        records: { x, y, kind: kind as never },
      },
    });
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    act(() => root!.render(<InfoPanel />));
    const text = host.textContent ?? "";
    expect(text).toContain("Sewing time");
    expect(text).toContain("about 2 min");
    expect(text).toContain("1 thread change");
    expect(text).toContain("Thread used");
    // Each color: 649 mm of stitching + 650 × 1 mm allowance ≈ 1.3 m; both ≈ 2.6 m.
    expect(text).toContain("about 2.5 m");
  });
});
