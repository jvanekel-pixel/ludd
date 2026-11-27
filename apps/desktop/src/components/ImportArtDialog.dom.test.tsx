// @vitest-environment jsdom
/** The "Import artwork" dialog (P7-D1), with a fake engine whose answers the tests hand over. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { registerCommands } from "../commands";
import { newDoc } from "../design/layout";
import type { LayoutItem, ObjectItem } from "../design/types";
import { DialogHost } from "../dialogs";
import { heldCount, letGoNewest } from "../escape";
import { importArtwork, type ArtPreview } from "../feat/importArt";
import { onKeyDown } from "../keys";
import { useStore } from "../store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const reached = vi.fn();
registerCommands(
  [
    { id: "test.enter", title: "Test: Enter", shortcut: "Enter", run: () => reached("Enter") },
    { id: "test.escape", title: "Test: Esc", shortcut: "Escape", run: () => reached("Escape") },
  ],
  { first: true },
);

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

const square = (x: number): [number, number, "l"][] => [[x, 0, "l"], [x + 10, 0, "l"], [x + 10, 10, "l"], [x, 10, "l"]];
const PREVIEW: ArtPreview = {
  size_mm: [86, 54],
  scale_note: "This SVG doesn't say its real size, so LUDD read it at 96 pixels per inch. Set Width to the size you want.",
  shapes: [
    { kind: "fill", geometry: { outline: square(-40) }, color: "#ffffff", name: "", background: true },
    { kind: "fill", geometry: { outline: square(-20) }, color: "#ff0000", name: "" },
    { kind: "fill", geometry: { outline: square(0) }, color: "#ff0000", name: "" },
    { kind: "run", geometry: { nodes: [[0, 0, "c"], [20, 0, "l"]] }, color: "#0000ff", name: "" },
    { kind: "satin", geometry: { nodes: [[0, 5, "c"], [20, 5, "l"]], width_mm: 3 }, color: "#0000ff", name: "" },
  ],
  skipped: [{ what: "text", count: 2, message: "2 pieces of text left out: LUDD doesn't import text." }],
  warnings: [{ level: "info", code: "art_wide_stroke", message: "1 stroke wider than 12 mm came in as filled shapes." }],
  pages: 1,
};

type Call = { method: string; params: Record<string, unknown>; resolve: (v: unknown) => void };
let calls: Call[] = [];
const engine = {
  call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "layout.render") {
      const list = (params.layout as { items: LayoutItem[] }).items;
      return Promise.resolve({ path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: list.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T);
    }
    return new Promise<T>((resolve) => calls.push({ method, params, resolve: resolve as (v: unknown) => void }));
  },
};

const already = {
  id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
  transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [],
} as unknown as ObjectItem;

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  reached.mockClear();
  calls = [];
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items: [already] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: "a", extraIds: [], dialog: null, tool: "select", pen: null, notice: null, charts: [], units: "mm", machines: [], hoopId: null });
  window.addEventListener("keydown", onKeyDown);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DialogHost />));
});

afterEach(() => {
  window.removeEventListener("keydown", onKeyDown);
  act(() => useStore.getState().setDialog(null));
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

const dialog = () => document.querySelector<HTMLDialogElement>("dialog.import-art");
const button = (label: string) => [...(dialog()?.querySelectorAll("button") ?? [])].find((b) => b.textContent === label) as HTMLButtonElement;
const text = () => dialog()?.textContent ?? "";
const press = (el: Element, key: string) => act(() => void el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true })));
const flush = () => act(async () => await new Promise((r) => setTimeout(r, 0)));
const previews = () => calls.filter((c) => c.method === "art.preview");
const added = () => (useStore.getState().history.present!.layout.items.length - 1);

async function open(path = "C:\\art\\Logo.svg") {
  await act(async () => {
    command("file.importArt"); // registered
    void importArtwork(path);
    await new Promise((r) => setTimeout(r, 0));
  });
}
const reply = async (patch: Partial<ArtPreview> = {}, which = previews().length - 1) => {
  previews()[which].resolve({ ...PREVIEW, ...patch });
  await flush();
};

describe("the Import artwork dialog", () => {
  it("Add is off until the preview arrives, and off again while new options are read", async () => {
    await open();
    expect(dialog()).not.toBeNull();
    expect(text()).toContain("Logo.svg: nothing is added until you press Add.");
    expect(button("Add").disabled).toBe(true);
    press(dialog()!, "Enter");
    await flush();
    expect(added()).toBe(0);
    await reply();
    expect(button("Add").disabled).toBe(false);
    act(() => button("Satin").click());
    expect(button("Add").disabled).toBe(true);
    expect(previews()[1].params.options).toMatchObject({ strokes: "satins" });
    await reply();
    expect(button("Add").disabled).toBe(false);
    expect(button("Satin").getAttribute("aria-pressed")).toBe("true");
  });

  it("shows what it would add, how big, what was left out and why", async () => {
    await open();
    await reply();
    expect(text()).toContain("2 fills, 1 line, 1 satin · 86 × 54 mm");
    expect(text()).toContain("96 pixels per inch");
    expect(text()).toContain("2 pieces of text left out");
    expect(text()).toContain("wider than 12 mm");
    expect(text()).toContain("#ff0000 · 2 shapes");
    const background = [...dialog()!.querySelectorAll("label")].find((l) => l.textContent?.includes("Background rectangle"))!;
    expect(background.querySelector("input")!.checked).toBe(false); // the background starts unticked
    act(() => useStore.setState({ units: "in" }));
    expect(text()).toContain("3.39 × 2.13 in");
  });

  it("untick a color and the count follows; Add then adds the ticked shapes", async () => {
    await open();
    await reply();
    const red = [...dialog()!.querySelectorAll("label")].find((l) => l.textContent?.includes("#ff0000"))!.querySelector("input")!;
    act(() => red.click());
    expect(text()).toContain("1 line, 1 satin ·");
    await act(async () => {
      button("Add").click();
      await whenIdle();
    });
    await flush();
    expect(added()).toBe(2);
    expect(dialog()).toBeNull();
  });

  it("Cancel adds nothing", async () => {
    await open();
    await reply();
    act(() => button("Cancel").click());
    await flush();
    expect(dialog()).toBeNull();
    expect(added()).toBe(0);
    expect(useStore.getState().history.past).toHaveLength(0);
    expect(heldCount()).toBe(0);
  });

  it("Esc closes it without adding, and no key reaches the design behind it", async () => {
    await open();
    await reply();
    press(dialog()!, "Escape");
    await flush();
    expect([dialog(), added(), heldCount()]).toEqual([null, 0, 0]);
    expect(reached).not.toHaveBeenCalled();
  });

  it("Enter in Width only sets the width; the next Enter adds", async () => {
    await open();
    await reply();
    const width = dialog()!.querySelector<HTMLInputElement>('input[aria-label="Width"]')!;
    expect(width.value).toBe("86.0");
    act(() => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(width, "40");
      width.dispatchEvent(new Event("input", { bubbles: true }));
    });
    press(width, "Enter");
    await flush();
    expect(previews()).toHaveLength(2);
    expect(previews()[1].params.options).toMatchObject({ width_mm: 40 });
    expect(added()).toBe(0);
    await reply({ size_mm: [40, 25], scale_note: PREVIEW.scale_note });
    expect(text()).not.toContain("96 pixels per inch"); // the size is chosen now
    await act(async () => {
      press(dialog()!, "Enter");
      await whenIdle();
    });
    await flush();
    expect(added()).toBe(4);
  });

  it("a DXF can fill its closed shapes, and a PDF can pick its page", async () => {
    await open("C:\\art\\part.dxf");
    await reply();
    const fill = [...dialog()!.querySelectorAll("label")].find((l) => l.textContent?.includes("Fill closed shapes"))!.querySelector("input")!;
    act(() => fill.click());
    expect(previews()[1].params.options).toMatchObject({ closed_as_fills: true });
    expect(dialog()!.querySelector("select")).toBeNull();
    act(() => useStore.getState().setDialog(null));
    await flush();

    await open("C:\\art\\two.pdf");
    await reply({ pages: 2 });
    expect(dialog()!.textContent).not.toContain("Fill closed shapes");
    const page = dialog()!.querySelector("select")!;
    expect([...page.options].map((o) => o.textContent)).toEqual(["1 of 2", "2 of 2"]);
    act(() => {
      page.value = "1";
      page.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(previews().at(-1)!.params.options).toMatchObject({ page: 1 });
  });

  it("matching to my threads waits until there are spools", async () => {
    await open();
    await reply();
    const match = () => [...dialog()!.querySelectorAll("label")].find((l) => l.textContent?.includes("Match colors to my threads"))!.querySelector("input")!;
    expect([match().disabled, match().checked]).toEqual([true, false]);
    act(() => useStore.setState({ charts: [{ id: "my_threads", name: "My threads", brand: "", builtin: false, count: 2, mine: true }] }));
    expect(match().disabled).toBe(false);
  });
});
