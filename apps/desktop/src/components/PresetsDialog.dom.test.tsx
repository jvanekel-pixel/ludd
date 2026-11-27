// @vitest-environment jsdom
/** The Stitch presets window (P7-C4), opened with Alt+P's command through the app's dialog host,
 *  with a fake engine holding presets as the real one lists them. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { COMMANDS, currentLayout, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import type { LayoutItem, ObjectItem } from "../design/types";
import { DialogHost } from "../dialogs";
import { heldCount } from "../escape";
import { usePresets, type Preset } from "../feat/presets";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore } from "../store";

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

const BUILTINS: Preset[] = [
  { id: "builtin:light-sketch-fill", name: "Light sketch fill", kind: "fill", params: { spacing_mm: 1 }, width_mm: null, note: "Open rows.", builtin: true },
  { id: "builtin:bold-outline", name: "Bold outline", kind: "run", params: { style: "bean" }, width_mm: null, note: "Bold.", builtin: true },
  { id: "builtin:narrow-satin-border", name: "Narrow satin border", kind: "satin", params: { spacing_mm: 0.4 }, width_mm: 2, note: "A 2 mm satin.", builtin: true },
];

let mine: Preset[] = [];
const calls: [string, Record<string, unknown>][] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "layout.render") {
      const items = (params.layout as { items: LayoutItem[] }).items;
      return { path: "", name: "x", format: "layout", threads: [], blocks: [], records: { x: [], y: [], kind: [] }, info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
    }
    calls.push([method, params]);
    if (method === "presets.list") return [...BUILTINS, ...mine] as T;
    if (method === "presets.save") {
      const p = params.preset as { name: string; kind: Preset["kind"]; params: Record<string, unknown>; width_mm?: number };
      const same = mine.find((m) => m.kind === p.kind && m.name.toLowerCase() === p.name.toLowerCase());
      if (same && !params.replace) throw new Error("You already have a preset called that.");
      const id = same?.id ?? p.name.toLowerCase().replace(/\s+/g, "-");
      mine = [...mine.filter((m) => m !== same), { id, name: p.name, kind: p.kind, params: p.params, width_mm: p.width_mm ?? null, note: null, builtin: false }];
      return { id } as T;
    }
    if (method === "presets.delete") {
      mine = mine.filter((m) => m.id !== params.id);
      return null as T;
    }
    if (method === "presets.export") return { path: `${params.dest as string}` } as T;
    if (method === "presets.import") {
      if ((params.path as string).includes("bad")) throw new Error("bad.luddpreset isn't a LUDD preset.");
      mine = [...mine, { id: "shared", name: "Shared", kind: "fill", params: {}, width_mm: null, note: null, builtin: false }];
      return { id: "shared", name: "Shared", kind: "fill" } as T;
    }
    return null as T;
  },
};

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const satin: ObjectItem = {
  id: "s", name: "Edge", kind: "satin", geometry: { nodes: [[0, 0, "s"], [20, 0, "s"]], width_mm: 3 }, params: { spacing_mm: 0.5 },
  thread: { color: "#cc0000", name: "", brand: "", catalog: "" }, transform: IDENT, threads: [], ops: [],
} as unknown as ObjectItem;

let root: Root | null = null;
let host: HTMLDivElement;

const settle = () => act(async () => {
  await new Promise((r) => setTimeout(r, 0));
  await whenIdle();
});

async function open(selected: string | null = "s") {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [satin] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: selected, extraIds: [], pen: null, tool: "select", dialog: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DialogHost />));
  await act(async () => COMMANDS.find((c) => c.id === "presets.open")!.run());
  await settle();
}

const dialog = () => host.querySelector("dialog")!;
const said = () => dialog().textContent!;
const buttons = () => [...dialog().querySelectorAll("button")];
const button = (name: string) => buttons().find((b) => b.textContent === name)!;
const click = async (name: string) => {
  await act(async () => button(name).click());
  await settle();
};
const entries = () => [...dialog().querySelectorAll('[aria-label="Presets"] button')].map((b) => b.querySelector("span")!.textContent);
const pick = async (name: string) => {
  await act(async () => ([...dialog().querySelectorAll('[aria-label="Presets"] button')].find((b) => b.querySelector("span")!.textContent === name) as HTMLButtonElement).click());
};
const type = (value: string) => {
  const input = dialog().querySelector("input")!;
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    set.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
};
const esc = () => act(() => void dialog().dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));

beforeEach(async () => {
  await whenIdle();
  mine = [];
  calls.length = 0;
  usePresets.setState({ list: null });
  savePrefs({ objectDefaults: undefined });
});
afterEach(() => {
  act(() => root?.unmount());
  root = null;
  host.remove();
  vi.restoreAllMocks();
});

describe("the Stitch presets window", () => {
  it("lists the selected shape's kind, or every kind with nothing selected", async () => {
    await open();
    expect(entries()).toEqual(["Narrow satin border"]);
    expect(said()).toContain("Showing presets for satins");
    act(() => useStore.getState().select(null));
    expect(entries()).toEqual(["Light sketch fill", "Bold outline", "Narrow satin border"]);
    expect(said()).toContain("Showing every preset");
  });

  it("applies the picked preset to the selection, and says so", async () => {
    await open();
    expect(button("Apply to selection").disabled).toBe(true);
    await pick("Narrow satin border");
    expect(said()).toContain("A 2 mm satin.");
    await click("Apply to selection");
    const now = currentLayout()!.items[0] as ObjectItem;
    expect([now.params, (now.geometry as { width_mm: number }).width_mm]).toEqual([{ spacing_mm: 0.4 }, 2]);
    expect(said()).toContain("Applied “Narrow satin border” to 1 satin");
  });

  it("can't delete or replace a built-in, and uses one for new shapes", async () => {
    await open();
    await pick("Narrow satin border");
    expect(button("Delete").disabled).toBe(true);
    await click("Use for new shapes");
    expect(loadPrefs().objectDefaults?.satin).toEqual({ spacing_mm: 0.4 });
    expect(said()).toContain("New satins start with “Narrow satin border”");
  });

  it("saves the selected shape's settings under a name, asking before replacing yours", async () => {
    await open();
    await click("Save current as…");
    const input = dialog().querySelector("input")!;
    expect(input.value).toBe("Edge");
    type("My edge");
    await click("Save preset");
    expect(calls.find(([m]) => m === "presets.save")![1]).toEqual({ preset: { name: "My edge", kind: "satin", params: { spacing_mm: 0.5 }, width_mm: 3 }, replace: false });
    expect(entries()).toEqual(["Narrow satin border", "My edge"]);
    calls.length = 0;
    await click("Save current as…");
    type("my EDGE");
    await click("Save preset");
    expect(calls.some(([m]) => m === "presets.save")).toBe(false);
    expect(said()).toContain("already have");
    await click("Replace it");
    expect(calls.find(([m]) => m === "presets.save")![1]).toMatchObject({ replace: true });
    expect(entries()).toEqual(["Narrow satin border", "my EDGE"]);
  });

  it("needs a selected shape to save from", async () => {
    await open(null);
    expect(button("Save current as…").disabled).toBe(true);
  });

  it("deletes one of yours only after asking", async () => {
    mine = [{ id: "mine", name: "Mine", kind: "satin", params: {}, width_mm: null, note: null, builtin: false }];
    await open();
    await pick("Mine");
    await click("Delete");
    expect(mine).toHaveLength(1);
    await click("Delete preset");
    expect(mine).toHaveLength(0);
    expect(said()).toContain("Deleted “Mine”");
  });

  it("imports and exports files you name (in the browser preview), and shows what went wrong", async () => {
    await open();
    vi.spyOn(window, "prompt").mockReturnValueOnce("C:/shared/bad.luddpreset");
    await click("Import…");
    expect(dialog().querySelector('[role="alert"]')!.textContent).toContain("isn't a LUDD preset");
    vi.spyOn(window, "prompt").mockReturnValueOnce("C:/shared/good.luddpreset");
    await click("Import…");
    // A fill preset while a satin is selected: it says where to find it.
    expect(said()).toContain("Added “Shared” to your presets. It's for fills");
    await pick("Narrow satin border");
    vi.spyOn(window, "prompt").mockReturnValueOnce("C:/shared/border");
    await click("Export…");
    expect(calls.find(([m]) => m === "presets.export")![1]).toEqual({ id: "builtin:narrow-satin-border", dest: "C:/shared/border" });
    expect(said()).toContain("Saved “Narrow satin border” as C:/shared/border");
  });

  it("lets Esc go of one thing at a time", async () => {
    const held = heldCount();
    await open();
    await click("Save current as…");
    esc();
    expect(dialog().querySelector("input")).toBeNull();
    expect(useStore.getState().dialog).toBe("presets");
    esc();
    expect(useStore.getState().dialog).toBeNull();
    expect(heldCount()).toBe(held);
  });
});
