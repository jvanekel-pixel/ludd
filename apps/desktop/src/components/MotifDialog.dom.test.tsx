// @vitest-environment jsdom
/** The Motifs window and the Motif list of motif lines and motif fills, with the app's own keyboard
 *  handler listening as in the app (a fake engine). */
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
import { heldCount, holdEscape, letGoNewest } from "../escape";
import { drawnSize, motifSpan, useMotifs, type MotifEntry } from "../feat/motifs";
import { onKeyDown } from "../keys";
import { useStore } from "../store";
import { MotifSelect } from "./MotifSelect";
import { Toolbar } from "./Toolbar";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** If a key got past the window to the app's shortcuts, this would run. */
const reached = vi.fn();
registerCommands(
  [
    { id: "test.motifs.enter", title: "Test: Enter", shortcut: "Enter", run: () => reached("Enter") },
    { id: "test.motifs.escape", title: "Test: Esc", shortcut: "Escape", run: () => reached("Escape") },
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

const ENDS = "A motif runs from where it starts to where it ends; draw it left to right";
const WAVE: MotifEntry = { id: "wave", name: "Wave", builtin: true, unit: [[0, 0], [0.25, 0.5], [0.75, -0.5], [1, 0]] };
const ZIGZAG: MotifEntry = { id: "zigzag", name: "Zigzag", builtin: true, unit: [[0, -0.5], [0.5, 0.5], [1, -0.5]] };
const HILL: [number, number][] = [[0, 0], [0.5, -0.3], [1, 0]];

let mine: MotifEntry[] = [];
let calls: [string, Record<string, unknown>][] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    calls.push([method, params]);
    if (method === "motifs.list") return [WAVE, ZIGZAG, ...mine] as T;
    if (method === "motifs.save") {
      if (params.closed) throw new Error(ENDS);
      const saved = { id: "user:hill", name: String(params.name), unit: HILL };
      mine = [...mine, { ...saved, builtin: false }];
      return saved as T;
    }
    if (method === "motifs.delete") {
      mine = mine.filter((m) => m.id !== params.id);
      return null as T;
    }
    if (method === "motifs.import") {
      const added = { id: "user:star", name: "Star", unit: [[0, 0], [0.5, 0.4], [1, 0]] as [number, number][] };
      mine = [...mine, { ...added, builtin: false }];
      return added as T;
    }
    if (method === "motifs.export") return { path: params.dest } as T;
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const shape = (id: string, kind: ObjectItem["kind"], geometry: object, params: object = {}, extra: object = {}): ObjectItem =>
  ({ id, kind, geometry, params, thread: { color: "#111111", name: "", brand: "", catalog: "" }, transform: { ...IDENT }, threads: [], ops: [], ...extra }) as unknown as ObjectItem;

const LINE_NODES = [[0, 0, "c"], [5, -3, "c"], [10, 0, "c"]];
const items = () => [
  shape("l", "run", { nodes: LINE_NODES }),
  shape("l2", "run", { nodes: [[0, 5, "c"], [10, 5, "c"]] }),
  shape("f", "fill", { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }),
  shape("m", "run", { nodes: [[0, 20, "c"], [40, 20, "c"]] }, { style: "motif" }),
  shape("mf", "fill", { outline: [[0, 30, "c"], [30, 30, "c"], [30, 60, "c"]] }, { pattern: "motif" }),
];

let root: Root | null = null;
let host: HTMLElement | null = null;

/** The window (when open) beside the Motif list of the shape `selectFor`, as in the panel. */
function Harness({ selectFor }: { selectFor: string }) {
  const item = useStore((s) => s.history.present?.layout.items.find((it) => it.id === selectFor)) as ObjectItem;
  return (
    <>
      <DialogHost />
      <div id="panel">
        <MotifSelect item={item} />
      </div>
    </>
  );
}

function mount(selectFor = "m") {
  act(() => root!.render(<Harness selectFor={selectFor} />));
}

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  reached.mockClear();
  mine = [];
  calls = [];
  useMotifs.setState({ list: null });
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items: items() } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], dialog: null, tool: "select", pen: null, notice: null });
  window.addEventListener("keydown", onKeyDown);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  window.removeEventListener("keydown", onKeyDown);
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  vi.restoreAllMocks();
});

const dialog = () => host!.querySelector<HTMLDialogElement>("dialog");
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("dialog button")].find((b) => b.textContent === label)!;
const saveButton = () => button("Save the selected line as a motif…");
const card = (name: string) => [...host!.querySelectorAll<HTMLButtonElement>("dialog [role=group] button")].find((b) => b.textContent === name)!;
const cards = (group: string) => [...host!.querySelectorAll(`dialog [role=group][aria-label="${group}"] button`)].map((b) => b.textContent);
const nameBox = () => host!.querySelector<HTMLInputElement>("dialog input[type=text]")!;
const motifSelect = () => host!.querySelector<HTMLSelectElement>('#panel select[aria-label="Motif"]')!;
const options = () => [...motifSelect().options].map((o) => o.textContent);
const params = (id: string) => (useStore.getState().history.present!.layout.items.find((it) => it.id === id) as ObjectItem).params as Record<string, unknown>;
const called = (method: string) => calls.filter(([m]) => m === method).map(([, p]) => p);

/** Wait for engine answers and edits to be done. */
async function settled() {
  await new Promise((r) => setTimeout(r, 0));
  await whenIdle();
  await new Promise((r) => setTimeout(r, 0));
}

async function open(selected: string | null, extra: string[] = []) {
  await act(async () => {
    useStore.setState({ selectedId: selected, extraIds: extra });
    command("motif.library").run();
    await settled();
  });
}

async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await settled();
  });
}

async function press(target: EventTarget, key: string, more: KeyboardEventInit = {}) {
  const e = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...more });
  await act(async () => {
    target.dispatchEvent(e);
    await settled();
  });
  return e;
}

function type(value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(nameBox(), value);
    nameBox().dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function choose(value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!.set!.call(motifSelect(), value);
    motifSelect().dispatchEvent(new Event("change", { bubbles: true }));
    await settled();
  });
}

describe("the Motifs window", () => {
  it("opens from the Motif list's My motifs button and from the ⋯ menu", async () => {
    mount();
    await click([...host!.querySelectorAll<HTMLButtonElement>("#panel button")].find((b) => b.textContent === "My motifs…")!);
    expect(dialog()?.open).toBe(true);
    await click(button("Close"));
    expect(dialog()).toBeNull();

    await act(async () => root!.render(<Toolbar />));
    await click(host!.querySelector<HTMLButtonElement>('button[aria-label="More"]')!);
    const item = [...host!.querySelectorAll<HTMLButtonElement>('[role="menu"] button')].find((b) => b.querySelector(".label")?.textContent === "Motifs…")!;
    await click(item);
    expect(useStore.getState().dialog).toBe("motifs");
  });

  it("opens with Alt+Shift+M and shows the built-in motifs and your own, each as two repeats", async () => {
    mine = [{ id: "user:mine", name: "Mine", builtin: false, unit: HILL }];
    mount();
    await press(document.body, "M", { altKey: true, shiftKey: true, code: "KeyM" });
    expect(dialog()?.open).toBe(true);
    expect(cards("Built in")).toEqual(["Wave", "Zigzag"]);
    expect(cards("My motifs")).toEqual(["Mine"]);
    // Two repeats: the second starts where the first ends.
    expect(card("Mine").querySelector("polyline")!.getAttribute("points")).toBe("0,0 0.5,-0.3 1,0 1,0 1.5,-0.3 2,0");
  });

  it("Save is disabled unless one drawn line is selected", async () => {
    mount();
    await open(null);
    expect(saveButton().disabled).toBe(true);
    for (const [selected, extra] of [["f", []], ["l", ["l2"]], ["l", ["f"]]] as const) {
      await act(async () => useStore.setState({ selectedId: selected, extraIds: [...extra] }));
      expect(saveButton().disabled, `${selected} ${extra}`).toBe(true);
    }
    await act(async () => useStore.setState({ selectedId: "l", extraIds: [] }));
    expect(saveButton().disabled).toBe(false);
    // Not while a shape is half drawn.
    await act(async () => useStore.setState({ pen: { kind: "run", a: [[0, 0, "c"]], b: [] } }));
    expect(saveButton().disabled).toBe(true);
  });

  it("a saved motif appears in the Motif list", async () => {
    mount();
    await open("l");
    expect(options()).not.toContain("Hill");
    await click(saveButton());
    expect(nameBox().value).toBe("My motif");
    expect(document.activeElement).toBe(nameBox());
    type("Hill");
    await press(nameBox(), "Enter");
    expect(called("motifs.save")).toEqual([{ name: "Hill", nodes: LINE_NODES, closed: false }]);
    expect(cards("My motifs")).toEqual(["Hill"]);
    expect(dialog()!.textContent).toContain("Saved “Hill” to My motifs.");
    expect(nameBox()).toBeNull();
    await click(button("Close"));
    expect(options()).toEqual(["Wave", "Zigzag", "Scallop", "Blanket stitch (applique edge)", "Leaves", "Hill"]);
    expect(motifSelect().querySelector("optgroup")!.label).toBe("My motifs");
    expect(reached).not.toHaveBeenCalled();
    expect(heldCount()).toBe(0);
  });

  it("saves the line as it looks: resized and mirrored", async () => {
    const doc = useStore.getState().history.present!;
    const turned = { ...IDENT, x: 3, rotate: 30, scale_x: 2, scale_y: 1.5, flip_y: true };
    useStore.setState({ history: { past: [], present: { ...doc, layout: { ...doc.layout, items: [shape("l", "run", { nodes: LINE_NODES }, {}, { transform: turned })] } }, future: [] } });
    mount("l");
    await open("l");
    await click(saveButton());
    await click(button("Save motif"));
    expect(called("motifs.save")[0].nodes).toEqual([[0, 0, "c"], [10, 4.5, "c"], [20, 0, "c"]]);
  });

  it("shows why the engine refused a line", async () => {
    const doc = useStore.getState().history.present!;
    useStore.setState({ history: { past: [], present: { ...doc, layout: { ...doc.layout, items: [shape("l", "run", { nodes: LINE_NODES, closed: true }), ...items().slice(1)] } }, future: [] } });
    mount();
    await open("l");
    await click(saveButton());
    await press(nameBox(), "Enter");
    expect(called("motifs.save")[0].closed).toBe(true);
    expect(host!.querySelector("dialog [role=alert]")!.textContent).toBe(ENDS);
    expect(cards("My motifs")).toEqual([]);
  });

  it("Delete asks first, saying shapes that use it keep their copy", async () => {
    mine = [{ id: "user:mine", name: "Mine", builtin: false, unit: HILL }];
    mount();
    await open(null);
    expect(button("Delete").disabled).toBe(true);
    await click(card("Wave"));
    expect(button("Delete").disabled).toBe(true); // built-ins stay
    expect(button("Export…").disabled).toBe(false);
    await click(card("Mine"));
    await click(button("Delete"));
    const question = host!.querySelector("dialog [role=alertdialog]")!;
    expect(question.textContent).toContain("Delete “Mine” from My motifs? Shapes that use it keep their own copy.");
    expect(called("motifs.delete")).toEqual([]);
    await click(button("Keep it"));
    expect(host!.querySelector("dialog [role=alertdialog]")).toBeNull();
    expect(called("motifs.delete")).toEqual([]);
    await click(button("Delete"));
    await click(button("Delete motif"));
    expect(called("motifs.delete")).toEqual([{ id: "user:mine" }]);
    expect(cards("My motifs")).toEqual([]);
    expect(dialog()!.textContent).toContain("Deleted “Mine”. Shapes that use it keep their own copy.");
  });

  it("Esc takes away the name box or the question first, then the window, and nothing else", async () => {
    mine = [{ id: "user:mine", name: "Mine", builtin: false, unit: HILL }];
    mount();
    const older = vi.fn();
    holdEscape(older);
    await open("l");
    await click(saveButton());
    await press(nameBox(), "Escape");
    expect(nameBox()).toBeNull();
    expect(dialog()?.open).toBe(true);
    await click(card("Mine"));
    await click(button("Delete"));
    await press(button("Keep it"), "Escape");
    expect(host!.querySelector("dialog [role=alertdialog]")).toBeNull();
    expect(dialog()?.open).toBe(true);
    // A repeating Esc does nothing.
    await press(button("Close"), "Escape", { repeat: true });
    expect(dialog()?.open).toBe(true);
    await press(button("Close"), "Escape");
    expect(dialog()).toBeNull();
    expect(older).not.toHaveBeenCalled();
    expect(heldCount()).toBe(1);
    expect(reached).not.toHaveBeenCalled();
    expect(useStore.getState().selectedId).toBe("l");
    expect(called("motifs.save")).toEqual([]);
  });

  it("Enter outside the name box goes no further than the window", async () => {
    mount();
    await open("l");
    const atWindow = vi.fn();
    window.addEventListener("keydown", atWindow);
    await press(dialog()!, "Enter");
    window.removeEventListener("keydown", atWindow);
    expect(atWindow).not.toHaveBeenCalled();
    expect(called("motifs.save")).toEqual([]);
    expect((await press(button("Close"), "Enter")).defaultPrevented).toBe(false); // the browser clicks it
  });

  it("imports and exports by a typed path in the browser", async () => {
    const asked = vi.spyOn(window, "prompt").mockReturnValueOnce("C:\\motifs\\star.json").mockReturnValueOnce("C:\\motifs\\wave-copy.json").mockReturnValueOnce(null);
    mount();
    await open(null);
    await click(button("Import…"));
    expect(called("motifs.import")).toEqual([{ path: "C:\\motifs\\star.json" }]);
    expect(cards("My motifs")).toEqual(["Star"]);
    expect(card("Star").getAttribute("aria-pressed")).toBe("true");
    await click(card("Wave"));
    await click(button("Export…"));
    expect(called("motifs.export")).toEqual([{ id: "wave", dest: "C:\\motifs\\wave-copy.json" }]);
    expect(asked.mock.calls[1][1]).toBe("Wave.json");
    expect(dialog()!.textContent).toContain("Saved “Wave” as C:\\motifs\\wave-copy.json.");
    await click(button("Import…")); // cancelled: nothing happens
    expect(called("motifs.import")).toHaveLength(1);
  });
});

describe("the Motif list of a motif line and a motif fill", () => {
  beforeEach(() => {
    mine = [{ id: "user:hill", name: "Hill", builtin: false, unit: HILL }];
  });

  const shown = async (id: string) => {
    await act(async () => {
      mount(id);
      await settled();
    });
  };

  it("choosing one of yours sews it with its drawn proportions: Width = Repeat × how far across it goes", async () => {
    await shown("m"); // a new line's Repeat is 4 mm
    await choose("user:hill");
    expect(params("m")).toMatchObject({ motif: "user:hill", motif_unit: HILL, motif_width_mm: 1.2 });
    expect(params("m").motif_mm).toBeUndefined();
    await shown("mf"); // a motif fill's Repeat is 5 mm
    await choose("user:hill");
    expect(params("mf")).toMatchObject({ motif: "user:hill", motif_unit: HILL, motif_width_mm: 1.5 });
    expect(motifSelect().value).toBe("user:hill");
  });

  it("choosing a built-in one drops the copy", async () => {
    await shown("m");
    await choose("user:hill");
    await choose("zigzag");
    expect(params("m").motif).toBe("zigzag");
    expect(params("m").motif_unit).toBeUndefined();
    expect(motifSelect().value).toBe("zigzag");
  });

  it("shows a motif this computer doesn't have, from the shape's own copy", async () => {
    const doc = useStore.getState().history.present!;
    const far = shape("x", "run", { nodes: [[0, 0, "c"], [20, 0, "c"]] }, { style: "motif", motif: "user:far-away-swirl", motif_unit: HILL });
    useStore.setState({ history: { past: [], present: { ...doc, layout: { ...doc.layout, items: [...doc.layout.items, far] } }, future: [] } });
    await shown("x");
    expect(motifSelect().selectedOptions[0].textContent).toBe("Far away swirl (kept in this shape, not in My motifs)");
    expect(options()).toContain("Hill");
  });

  it("says when the shape's copy differs from the one in My motifs", async () => {
    const doc = useStore.getState().history.present!;
    const old = shape("x", "fill", { outline: [[0, 0, "c"], [30, 0, "c"], [30, 30, "c"]] }, { pattern: "motif", motif: "user:hill", motif_unit: [[0, 0], [0.5, 0.4], [1, 0]] });
    useStore.setState({ history: { past: [], present: { ...doc, layout: { ...doc.layout, items: [...doc.layout.items, old] } }, future: [] } });
    await shown("x");
    expect(motifSelect().selectedOptions[0].textContent).toBe("Hill (this shape's own copy)");
    await choose("user:hill"); // take the one in My motifs
    expect(params("x").motif_unit).toEqual(HILL);
    expect(motifSelect().selectedOptions[0].textContent).toBe("Hill");
  });

  it("keeps a motif the shape carries while the list can't be read", async () => {
    const broken = { call: async (method: string) => (method === "motifs.list" ? Promise.reject(new Error("no")) : null) };
    useStore.setState({ engine: broken as never });
    const doc = useStore.getState().history.present!;
    const far = shape("x", "run", { nodes: [[0, 0, "c"], [20, 0, "c"]] }, { style: "motif", motif: "user:hill", motif_unit: HILL });
    useStore.setState({ history: { past: [], present: { ...doc, layout: { ...doc.layout, items: [...doc.layout.items, far] } }, future: [] } });
    await shown("x");
    expect(motifSelect().selectedOptions[0].textContent).toBe("Hill (kept in this shape)");
    expect(options().slice(1, 3)).toEqual(["Wave", "Zigzag"]);
  });
});

describe("the width rule", () => {
  it("keeps the proportions within the ranges, changing the Repeat only when the Width's range makes it", () => {
    expect(motifSpan(HILL)).toBeCloseTo(0.3, 9);
    expect(drawnSize(0.3, 4)).toEqual({ motif_width_mm: 1.2 });
    expect(drawnSize(0.3, 5)).toEqual({ motif_width_mm: 1.5 });
    expect(drawnSize(1, 12)).toEqual({ motif_width_mm: 10, motif_mm: 10 }); // 12 mm tall is too tall
    expect(drawnSize(5, 4)).toEqual({ motif_width_mm: 10, motif_mm: 2 });
    expect(drawnSize(0.05, 4)).toEqual({ motif_width_mm: 0.5, motif_mm: 10 });
    expect(drawnSize(20, 4)).toEqual({ motif_width_mm: 10, motif_mm: 1.5 }); // as near as the ranges allow
    expect(drawnSize(0, 4)).toEqual({}); // a flat one keeps its sizes
  });
});
