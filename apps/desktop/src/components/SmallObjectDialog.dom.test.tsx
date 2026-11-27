// @vitest-environment jsdom
/** The buttonhole and eyelet dialogs (a fake engine), with the app's keyboard handler listening. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import type { LayoutItem } from "../design/types";
import { DialogHost } from "../dialogs";
import { heldCount, letGoNewest } from "../escape";
import { onKeyDown } from "../keys";
import { useStore } from "../store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

beforeAll(() => {
  // jsdom has the <dialog> element but not showModal() or close(): enough of both for the app.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

const asked: [string, Record<string, unknown>][] = [];
let refusal: string | null = null;
const SHAPE = { kind: "satin", name: "Buttonhole lip 1", geometry: { nodes: [[0, 0, "c"], [10, 0, "l"]], width_mm: 2 }, params: {} };

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method.startsWith("shape.")) {
      asked.push([method, params]);
      if (refusal) throw new Error(refusal);
      return { objects: [SHAPE], warnings: [] } as T;
    }
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "satin", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  asked.length = 0;
  refusal = null;
  const doc = newDoc();
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], dialog: null, tool: "select", pen: null, notice: null });
  window.addEventListener("keydown", onKeyDown);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DialogHost />));
});

afterEach(() => {
  window.removeEventListener("keydown", onKeyDown);
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

const dialog = () => host!.querySelector<HTMLDialogElement>("dialog");
const box = (label: string) =>
  [...host!.querySelectorAll<HTMLLabelElement>("dialog label")].find((l) => l.textContent!.startsWith(label))!.querySelector("input")!;
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("dialog button")].find((b) => b.textContent === label)!;
const items = () => useStore.getState().history.present!.layout.items;
const tip = () => dialog()!.querySelector(".hint")!.textContent;
const open = (id: string) => act(() => command(id).run());

async function settled() {
  await whenIdle();
  await new Promise((r) => setTimeout(r, 0));
}
async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await settled();
  });
}
async function press(target: EventTarget, key: string) {
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
    await settled();
  });
}
function type(label: string, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(box(label), value);
    box(label).dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("the buttonhole dialog", () => {
  it("offers the standard sizes, says how long to make it, and adds it with Enter", async () => {
    open("object.buttonhole");
    expect(dialog()!.querySelector("h2")!.textContent).toBe("Add a buttonhole");
    expect([box("Length").value, box("Width").value, box("Cut gap").value, box("Angle").value]).toEqual(["16", "5", "1", "0"]);
    expect(document.activeElement).toBe(box("Length"));
    expect(tip()).toBe("Length = the button's width + its thickness + 3 mm");
    // The cut gap and the angle are tucked away.
    expect(dialog()!.querySelector("details")!.open).toBe(false);
    expect(dialog()!.querySelector("details")!.contains(box("Cut gap"))).toBe(true);
    type("Length", "20");
    await press(box("Length"), "Enter");
    expect(asked).toEqual([["shape.buttonhole", { style: "bar", length_mm: 20, width_mm: 5, cut_gap_mm: 1, angle_deg: 0, at: [0, 0] }]]);
    expect(dialog()).toBeNull();
    expect(items()).toHaveLength(1);
    expect(heldCount()).toBe(0);
  });

  it("for rounded ends the same advice gives that style's own length", async () => {
    open("object.buttonhole");
    await click(button("Rounded ends"));
    expect(button("Rounded ends").getAttribute("aria-pressed")).toBe("true");
    // A rounded buttonhole's slit is shorter than it by the width less the cut gap: 4 mm here.
    expect(tip()).toBe("Length = the button's width + its thickness + 4 mm");
    type("Width", "8");
    expect(tip()).toBe("Length = the button's width + its thickness + 7 mm");
    await click(button("Add"));
    expect(asked[0][1]).toMatchObject({ style: "round", width_mm: 8 });
    // Both remembered next time.
    open("object.buttonhole");
    expect([button("Rounded ends").getAttribute("aria-pressed"), box("Width").value]).toEqual(["true", "8"]);
  });

  it("shows the engine's refusal and stays open to be fixed", async () => {
    refusal = "Make the buttonhole wider or the cut narrower";
    open("object.buttonhole");
    type("Width", "3");
    await click(button("Add"));
    expect(dialog()?.open).toBe(true);
    expect(dialog()!.querySelector('[role="alert"]')!.textContent).toBe("Make the buttonhole wider or the cut narrower");
    expect(items()).toHaveLength(0);
    refusal = null;
    type("Width", "5");
    await click(button("Add"));
    expect(dialog()).toBeNull();
    expect(items()).toHaveLength(1);
  });

  it("puts the refusal away as soon as a number or the style changes", async () => {
    refusal = "Length must be between 8 and 40 mm";
    open("object.buttonhole");
    const shown = () => dialog()!.querySelector('[role="alert"]')?.textContent ?? null;
    type("Length", "99");
    await click(button("Add"));
    expect(shown()).toBe("Length must be between 8 and 40 mm");
    type("Length", "20");
    expect(shown()).toBeNull();
    await click(button("Add"));
    expect(shown()).toBe("Length must be between 8 and 40 mm"); // the engine still says no
    await click(button("Rounded ends"));
    expect(shown()).toBeNull();
  });

  it("an empty box keeps its number; Esc and Cancel add nothing", async () => {
    open("object.buttonhole");
    type("Length", "");
    await press(box("Length"), "Escape");
    expect(dialog()).toBeNull();
    open("object.buttonhole");
    await click(button("Cancel"));
    expect(asked).toEqual([]);
    open("object.buttonhole");
    type("Length", " ");
    await click(button("Add"));
    expect(asked[0][1]).toMatchObject({ length_mm: 16 });
  });
});

describe("the eyelet dialog", () => {
  it("asks for the hole and the ring", async () => {
    open("object.eyelet");
    expect(dialog()!.querySelector("h2")!.textContent).toBe("Add an eyelet");
    expect([box("Hole").value, box("Ring").value]).toEqual(["4", "1.6"]);
    type("Hole", "6");
    await click(button("Add"));
    expect(asked).toEqual([["shape.eyelet", { hole_mm: 6, ring_mm: 1.6, at: [0, 0] }]]);
    open("object.eyelet");
    expect(box("Hole").value).toBe("6");
  });
});
