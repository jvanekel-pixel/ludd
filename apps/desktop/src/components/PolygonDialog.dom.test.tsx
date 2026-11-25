// @vitest-environment jsdom
/** The polygon dialog, the first to use the dialog registry, with the app's own keyboard handler
 *  listening on the window as it does in the app (a fake engine). */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { registerCommands } from "../commands";
import { newDoc } from "../design/layout";
import { shapeNodes } from "../design/shapes";
import type { LayoutItem, ObjectItem } from "../design/types";
import { DialogHost } from "../dialogs";
import { heldCount, holdEscape, letGoNewest } from "../escape";
import { onKeyDown } from "../keys";
import { useStore } from "../store";
import { ToolRail } from "./ToolRail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** If a key got past the dialog to the app's shortcuts, one of these would run. */
const reached = vi.fn();
registerCommands(
  [
    { id: "test.enter", title: "Test: Enter", shortcut: "Enter", run: () => reached("Enter") },
    { id: "test.escape", title: "Test: Esc", shortcut: "Escape", run: () => reached("Escape") },
  ],
  { first: true },
);

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

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

const already: ObjectItem = {
  id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
  transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [],
} as ObjectItem;

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  reached.mockClear();
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items: [already] } };
  // One shape on the design, selected: a key that got through to the app could let go of it.
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: "a", extraIds: [], dialog: null, tool: "select", pen: null, notice: null });
  window.addEventListener("keydown", onKeyDown);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() =>
    root!.render(
      <>
        <ToolRail />
        <DialogHost />
      </>,
    ),
  );
});

afterEach(() => {
  window.removeEventListener("keydown", onKeyDown);
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

const dialog = () => host!.querySelector<HTMLDialogElement>("dialog");
const sidesBox = () => host!.querySelector<HTMLInputElement>("dialog input[type=number]")!;
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("dialog button")].find((b) => b.textContent === label)!;
const shapes = () => useStore.getState().history.present!.layout.items as ObjectItem[];
const added = () => shapes().slice(1);
const outlineOf = (it: ObjectItem) => (it.geometry as { outline: unknown[] }).outline;

const openDialog = () => act(() => command("shape.polygon").run());

/** Wait for the edit to be sewn, and for what follows it (the new shape is selected). */
async function settled() {
  await whenIdle();
  await new Promise((r) => setTimeout(r, 0));
}

/** A key press on `target`, heard by the dialog and then the window, as in the app. */
async function press(target: EventTarget, key: string, more: KeyboardEventInit = {}) {
  const e = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...more });
  await act(async () => {
    target.dispatchEvent(e);
    await settled();
  });
  return e;
}

async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await settled();
  });
}

function typeSides(value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(sidesBox(), value);
    sidesBox().dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("the polygon dialog", () => {
  it("the polygon dialog adds a hexagon on Enter", async () => {
    // Its shortcut opens it, through the app's keyboard handler.
    await press(document.body, "7", { ctrlKey: true, altKey: true, code: "Digit7" });
    expect(dialog()?.open).toBe(true);
    expect(dialog()!.textContent).toContain("Sides");
    // Six sides the first time, selected, so typing replaces it.
    expect(sidesBox().value).toBe("6");
    expect(document.activeElement).toBe(sidesBox());
    // Typing in the box is left alone, by the dialog and by the app.
    for (const key of ["8", "Backspace", "ArrowUp", "Tab"]) expect((await press(sidesBox(), key)).defaultPrevented, key).toBe(false);
    expect(dialog()?.open).toBe(true);

    // Enter stops at the dialog: the app's handler on the window never hears it.
    const atWindow = vi.fn();
    window.addEventListener("keydown", atWindow);
    const e = await press(sidesBox(), "Enter");
    window.removeEventListener("keydown", atWindow);
    expect(atWindow).not.toHaveBeenCalled();
    expect(e.defaultPrevented).toBe(true);
    expect(dialog()).toBeNull();
    expect(useStore.getState().dialog).toBeNull();
    expect(added()).toHaveLength(1); // once, not once more from the app's keyboard handler
    expect(added()[0].kind).toBe("fill");
    expect(outlineOf(added()[0])).toEqual(shapeNodes("polygon", 0, 0, 60, { sides: 6 }));
    expect(outlineOf(added()[0])).toHaveLength(6);
    expect(useStore.getState().selectedId).toBe(added()[0].id);
    expect(reached).not.toHaveBeenCalled();
    expect(heldCount()).toBe(0);
  });

  it("Esc closes it through the Esc hold, and lets go of nothing else", async () => {
    // The spies do hear keys when no dialog is open.
    await press(document.body, "Enter");
    expect(reached).toHaveBeenCalledWith("Enter");
    reached.mockClear();

    const older = vi.fn();
    holdEscape(older);
    openDialog();
    expect(heldCount()).toBe(2);

    const e = await press(sidesBox(), "Escape");
    expect(e.defaultPrevented).toBe(true); // the browser doesn't close it a second way
    expect(dialog()).toBeNull();
    expect(useStore.getState().dialog).toBeNull();
    expect(heldCount()).toBe(1);
    expect(older).not.toHaveBeenCalled(); // one thing per press
    expect(reached).not.toHaveBeenCalled();
    expect(useStore.getState().selectedId).toBe("a");
    expect(added()).toHaveLength(0);

    // Esc from a button in the dialog closes it just the same.
    openDialog();
    await press(button("Cancel"), "Escape");
    expect(dialog()).toBeNull();
    expect(older).not.toHaveBeenCalled();
    expect(heldCount()).toBe(1);
  });

  it("a held key does one thing only", async () => {
    // Enter held down on the menu item that opened it mustn't add a polygon straight away.
    openDialog();
    await press(sidesBox(), "Enter", { repeat: true });
    expect(dialog()).not.toBeNull();
    expect(added()).toHaveLength(0);
    // A repeating Esc doesn't go on to let go of older things.
    const older = vi.fn();
    holdEscape(older);
    await press(sidesBox(), "Escape", { repeat: true });
    expect(older).not.toHaveBeenCalled();
    expect(dialog()).not.toBeNull();
  });

  it("leaves Enter on a button to that button, so nothing is added twice", async () => {
    openDialog();
    for (const label of ["Cancel", "Add"]) {
      const e = await press(button(label), "Enter");
      expect(e.defaultPrevented, label).toBe(false); // so the browser clicks the button
      expect(added(), label).toHaveLength(0);
    }
    await click(button("Add"));
    expect(added()).toHaveLength(1);
    expect(dialog()).toBeNull();
    expect(reached).not.toHaveBeenCalled();
  });

  it("starts at the number of sides used last; Cancel changes nothing", async () => {
    openDialog();
    typeSides("8");
    await press(sidesBox(), "Enter");
    expect(outlineOf(added()[0])).toHaveLength(8);

    openDialog();
    expect(sidesBox().value).toBe("8");
    typeSides("4");
    await click(button("Cancel"));
    expect(dialog()).toBeNull();
    expect(added()).toHaveLength(1);

    openDialog();
    expect(sidesBox().value).toBe("8");
    expect(heldCount()).toBe(1);
  });

  it("keeps the number between 3 and 12", async () => {
    // An empty box means the number it started with (the last one used: 5, from "4.6").
    for (const [typed, sides] of [["40", 12], ["1", 3], ["0", 3], ["4.6", 5], ["", 5]] as const) {
      openDialog();
      typeSides(typed);
      await press(sidesBox(), "Enter");
      expect(outlineOf(added().at(-1)!), `typed "${typed}"`).toHaveLength(sides);
    }
  });

  it("closed by the browser itself (Esc with the focus on the page), the app hears of it", async () => {
    openDialog();
    // A key on the page behind goes nowhere: the app's handler leaves it to the open dialog.
    const e = await press(document.body, "Escape");
    expect(e.defaultPrevented).toBe(false);
    expect(reached).not.toHaveBeenCalled();
    act(() => dialog()!.close()); // what the browser does next
    expect(useStore.getState().dialog).toBeNull();
    expect(dialog()).toBeNull();
    expect(heldCount()).toBe(0);
  });

  it("opens from the Shapes menu, which lists the five new shapes under Star", async () => {
    await click(host!.querySelector<HTMLButtonElement>("button[aria-label=Shapes]")!);
    const rows = [...host!.querySelectorAll("[role=menu] [role=menuitem]")].map((b) => [b.querySelector(".label")!.textContent!.replace(/^\S+\s+/, ""), b.querySelector("kbd")!.textContent]);
    expect(rows.slice(0, 8)).toEqual([
      ["Rectangle", "Ctrl+Alt+1"],
      ["Circle", "Ctrl+Alt+2"],
      ["Star", "Ctrl+Alt+3"],
      ["Rounded rectangle", "Ctrl+Alt+4"],
      ["Oval", "Ctrl+Alt+5"],
      ["Triangle", "Ctrl+Alt+6"],
      ["Polygon…", "Ctrl+Alt+7"],
      ["Heart", "Ctrl+Alt+8"],
    ]);
    await click([...host!.querySelectorAll<HTMLButtonElement>("[role=menuitem]")].find((b) => b.textContent!.includes("Polygon"))!);
    expect(dialog()?.open).toBe(true);
    expect(host!.querySelector("[role=menu]")).toBeNull();
    expect(heldCount()).toBe(1); // the menu's hold is gone, the dialog's is there
  });
});
