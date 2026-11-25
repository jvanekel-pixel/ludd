// @vitest-environment jsdom
/** The setting for "Don't sew what's hidden under shapes on top" in the design panel. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../actions";
import { newDoc } from "../design/layout";
import type { Layout, LayoutItem } from "../design/types";
import { useStore } from "../store";
import { OverlapOptions } from "./OverlapOptions";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fill = { id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" }, transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] } as unknown as LayoutItem;

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as Layout).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  localStorage.clear();
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

function show(remove_overlap?: Layout["remove_overlap"], units: "mm" | "in" = "mm") {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [fill], ...(remove_overlap ? { remove_overlap } : {}) } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], notice: null, units });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<OverlapOptions />));
}

const box = () => host!.querySelector<HTMLInputElement>("input[type=checkbox]");
const field = () => host!.querySelector<HTMLInputElement>("input[type=number]");
const button = (label: string) => [...host!.querySelectorAll("button")].find((b) => b.textContent!.includes(label))!;
const setting = () => currentLayout()!.remove_overlap;
const past = () => useStore.getState().history.past.length;

async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await whenIdle();
  });
}

/** Type into the number box and leave it, which is when it takes effect. */
async function enter(value: string) {
  const input = field()!;
  await act(async () => {
    input.focus();
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.blur();
    await whenIdle();
  });
}

describe("the hidden-stitching setting", () => {
  it("shows nothing while the switch is off", () => {
    show();
    expect(host!.innerHTML).toBe("");
    act(() => root!.unmount());
    host!.remove();
    show({ enabled: false, keep_mm: 2 });
    expect(host!.innerHTML).toBe("");
  });

  it("while on, shows the switch, ticked; unticking it turns it off", async () => {
    show({ enabled: true, keep_mm: 1 });
    expect(box()!.checked).toBe(true);
    expect(box()!.closest("label")!.textContent).toContain("Don't sew what's hidden under shapes on top");
    expect(field()).toBeNull(); // the margin is under More options
    await click(box()!);
    expect(setting()).toEqual({ enabled: false, keep_mm: 1 });
    expect(host!.innerHTML).toBe("");
  });

  it("keeps the margin under More options, in mm, and takes a new one as one undo step", async () => {
    show({ enabled: true, keep_mm: 1 });
    await click(button("More options"));
    expect(field()!.closest("label")!.textContent).toContain("Keep under the edge");
    expect(field()!.closest("label")!.textContent).toContain("mm");
    expect(field()!.value).toBe("1.00");
    await enter("1.5");
    expect(setting()).toEqual({ enabled: true, keep_mm: 1.5 });
    expect(past()).toBe(1);
    expect(field()!.value).toBe("1.50");
  });

  it("brings a value out of range back into it, and shows what is used", async () => {
    show({ enabled: true, keep_mm: 1 });
    await click(button("More options"));
    await enter("10");
    expect(setting()!.keep_mm).toBe(3);
    expect(field()!.value).toBe("3.00");
    await enter("7"); // still 3: nothing to change, and the box says so
    expect(field()!.value).toBe("3.00");
    expect(past()).toBe(1);
  });

  it("shows what the engine uses when a project file holds something else", async () => {
    show({ enabled: true, keep_mm: 99 });
    await click(button("More options"));
    expect(field()!.value).toBe("3.00");
  });

  it("works in inches", async () => {
    show({ enabled: true, keep_mm: 1 }, "in");
    await click(button("More options"));
    expect(field()!.value).toBe("0.039");
    await enter("0.05");
    expect(setting()!.keep_mm).toBe(1.27);
    expect(field()!.value).toBe("0.050");
  });
});
