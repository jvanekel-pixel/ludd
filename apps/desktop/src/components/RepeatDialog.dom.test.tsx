// @vitest-environment jsdom
/** The Repeat window (P7-C3): its four patterns, the outline boxes on the design while it's open,
 *  and the stitch warning and refusal worked out before any copy is made (a fake engine). */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../actions";
import { repeatPreview } from "../canvas/repeatOverlay";
import { newDoc } from "../design/layout";
import { Kind, type Design, type LayoutItem, type ObjectItem } from "../design/types";
import { useStore } from "../store";
import { RepeatDialog } from "./RepeatDialog";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return rendered(items, 1) as T;
  },
};

const shape = (id: string): ObjectItem =>
  ({
    id, kind: "fill", geometry: { outline: [[10, 10, "c"], [30, 10, "c"], [30, 20, "c"], [10, 20, "c"]] }, params: {},
    thread: { color: "#111111", name: "", brand: "", catalog: "" }, transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [],
  }) as unknown as ObjectItem;

/** A render in which the first item has `own` stitches (and one jump, which isn't a stitch). */
function rendered(items: LayoutItem[], own: number): Design {
  const kind = [...Array(own).fill(Kind.Stitch), Kind.Jump];
  return {
    path: "", name: "x", format: "layout", threads: [], blocks: [],
    info: { stitches: own, jumps: 1, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 20, height_mm: 10, bounds_mm: [10, 10, 30, 20] },
    records: { x: kind.map(() => 0), y: kind.map(() => 0), kind, item: kind.map(() => 0) },
    items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [20, 15], bounds_mm: [10, 10, 30, 20], source_size_mm: null })),
  };
}

let root: Root | null = null;
let host: HTMLDivElement;

/** The window open for the one shape, sewn with `own` stitches. */
function show(own = 1000) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [shape("a")] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "a", extraIds: [], pen: null, tool: "select", units: "mm" });
  useStore.getState().setDesign(rendered(doc.layout.items, own));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<RepeatDialog />));
  act(() => useStore.getState().setRepeatOpen(true));
}

const button = (name: string) => [...host.querySelectorAll("button")].find((b) => b.textContent === name)!;
const click = (name: string) => act(() => button(name).click());
const box = (label: string) => [...host.querySelectorAll("label")].find((l) => l.textContent!.startsWith(label))!.querySelector("input")!;
function type(label: string, value: string) {
  const input = box(label);
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    set.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
const said = () => host.textContent!;

beforeEach(async () => {
  await whenIdle();
});
afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host.remove();
  useStore.setState({ repeatOpen: false });
});

describe("the Repeat window", () => {
  it("offers Row, Wreath, Kaleidoscope and Mirror, each with what it needs", () => {
    show();
    const modes = [...host.querySelectorAll('[aria-label="Pattern"] button')].map((b) => b.textContent);
    expect(modes).toEqual(["Row", "Wreath", "Kaleidoscope", "Mirror"]);
    click("Wreath");
    expect(said()).toContain("How many");
    expect(said()).toContain("Below the design");
    click("The middle of the hoop");
    // The design's middle is (20, 15): 25 mm from the middle of the hoop.
    expect(said()).toContain("25 mm");
    click("Kaleidoscope");
    expect(said()).toContain("Pairs");
    expect(said()).toContain("Makes 8 in all");
    click("Mirror");
    expect([...host.querySelectorAll('[aria-label="Mirror"] button')].map((b) => b.textContent)).toEqual(["Left–right", "Top–bottom", "Both"]);
    expect(said()).toContain("Makes 2 in all");
    click("Both");
    expect(said()).toContain("Makes 4 in all");
  });

  it("draws a box where each copy will land, until it closes", () => {
    show();
    // Row, 3 across: two copies, 25 mm and 50 mm to the right (20 mm wide, 5 mm apart).
    expect(repeatPreview()).toHaveLength(2);
    expect(repeatPreview()![1]).toEqual([[60, 10], [80, 10], [80, 20], [60, 20]]);
    type("Across", "5");
    expect(repeatPreview()).toHaveLength(4);
    click("Kaleidoscope");
    expect(repeatPreview()).toHaveLength(7);
    act(() => useStore.getState().setRepeatOpen(false));
    expect(repeatPreview()).toBeNull();
  });

  it("warns above 60,000 stitches and refuses above 400,000, with the number", async () => {
    show(30_000);
    // 30,000 stitches, three in all: 90,000.
    expect(said()).toContain(`about ${(90_000).toLocaleString()} stitches`);
    expect(said()).toContain("Fewer copies sew faster");
    expect(button("Repeat").disabled).toBe(false);
    type("Across", "20");
    expect(said()).toContain(`about ${(600_000).toLocaleString()} stitches`);
    expect(said()).toContain("Make fewer copies");
    expect(button("Repeat").disabled).toBe(true);
    type("Across", "2");
    expect(said()).not.toContain("Fewer copies sew faster");
    expect(button("Repeat").disabled).toBe(false);
    await act(async () => button("Repeat").click());
    await act(() => whenIdle());
    expect(currentLayout()!.items).toHaveLength(2);
    expect(useStore.getState().repeatOpen).toBe(false);
  });

  it("keeps the counts in range however they are typed", () => {
    show();
    click("Kaleidoscope");
    type("Pairs", "99");
    expect(said()).toContain("Makes 24 in all");
    act(() => box("Pairs").dispatchEvent(new Event("focusout", { bubbles: true })));
    expect(box("Pairs").value).toBe("12");
  });
});
