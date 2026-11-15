/**
 * Regression tests for the live-behaviour QA findings (docs/QA-REPORT.md, areas live-esc and
 * live-state): Esc holds, selection, undo steps, edits that overlap a render, recovery, the
 * command registry and the keyboard handler. Uses a fake engine; no browser needed.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const dialog = vi.hoisted(() => ({ answer: "Cancel", asked: 0 }));
vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: async () => "C:/x/My Flower.ludd",
  open: async () => null,
  message: async () => {
    dialog.asked++;
    return dialog.answer;
  },
}));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import * as F from "./features";
import { matchesShortcut } from "./commands";
import { newDoc } from "./design/layout";
import type { Doc, LayoutItem, ObjectItem } from "./design/types";
import { heldCount, holdEscape, letGoNewest } from "./escape";
import { onKeyDown } from "./keys";
import { dragHandle } from "./dragDialogs";
import { useStore } from "./store";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** A stand-in engine. `fail` makes the next renders of layouts matching it fail. */
function fakeEngine(opts: { renderDelay?: number; recovery?: boolean } = {}) {
  const calls: string[] = [];
  const state = { failIf: null as null | ((layout: { items: LayoutItem[] }) => boolean), delay: opts.renderDelay ?? 0 };
  const engine = {
    calls,
    state,
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      calls.push(method);
      switch (method) {
        case "layout.render": {
          const layout = params.layout as { items: LayoutItem[] };
          if (state.delay) await sleep(state.delay);
          if (state.failIf?.(layout)) throw new Error("This shape is too small to fill");
          return {
            path: "",
            name: "x",
            format: "layout",
            info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
            threads: [],
            blocks: [],
            records: { x: [], y: [], kind: [] },
            items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })),
          } as T;
        }
        case "project.recovery":
          return (opts.recovery ? { title: "Lost", saved_at: 0, path: null, items: 1, images: 0 } : null) as T;
        case "project.restore":
          return { layout: { ...newDoc().layout, items: [fill("r1")] }, images: [], path: null } as T;
        case "project.save":
          return { path: params.path, images: 0, designs: 0 } as T;
        default:
          return null as T;
      }
    },
  };
  return engine;
}

const fill = (id: string, color = "#111111"): ObjectItem =>
  ({
    id,
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] },
    params: {},
    thread: { color, name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as ObjectItem;

const file = (id: string): LayoutItem =>
  ({ id, kind: "file", path: "C:/d/x.pes", transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as unknown as LayoutItem;

function docOf(...items: LayoutItem[]): Doc {
  const d = newDoc();
  return { ...d, layout: { ...d.layout, items } };
}

function setDoc(engine: ReturnType<typeof fakeEngine>, ...items: LayoutItem[]) {
  const doc = docOf(...items);
  useStore.setState({
    engine: engine as never,
    history: { past: [], present: doc, future: [] },
    savedDoc: doc,
    selectedId: null,
    extraIds: [],
    notice: null,
    projectPath: null,
    tool: "select",
    pen: null,
    knife: null,
    stitchEdit: null,
    design: null,
  });
  return doc;
}

const items = () => useStore.getState().history.present!.layout.items;
const colorOf = (id: string) => (items().find((it) => it.id === id) as ObjectItem).thread.color;
const run = (id: string) => A.COMMANDS.find((c) => c.id === id)!.run();

beforeEach(async () => {
  await A.whenIdle();
  while (letGoNewest());
  dialog.answer = "Cancel";
  dialog.asked = 0;
});

describe("Esc holds go away with the thing they hold", () => {
  it("the knife's hold goes when a tool key puts the knife away", () => {
    setDoc(fakeEngine(), fill("a"));
    useStore.getState().select("a");
    F.startKnife();
    expect(heldCount()).toBe(1);
    useStore.getState().setTool("fill");
    expect(useStore.getState().knife).toBeNull();
    expect(heldCount()).toBe(0);
  });

  it("stitch editing ends (and its hold goes) when its design is deleted", async () => {
    const engine = fakeEngine();
    setDoc(engine, file("f"), fill("b"));
    useStore.getState().select("f");
    F.startStitchEdit();
    expect(heldCount()).toBe(1);
    A.removeSelected();
    await A.whenIdle();
    expect(useStore.getState().stitchEdit).toBeNull();
    expect(heldCount()).toBe(0);
  });

  it("stitch editing ends when a new design is started", async () => {
    const engine = fakeEngine();
    setDoc(engine, file("f"));
    useStore.getState().select("f");
    F.startStitchEdit();
    await A.newProject();
    expect(useStore.getState().stitchEdit).toBeNull();
    expect(heldCount()).toBe(0);
  });
});

describe("Selection", () => {
  it("changing tool lets go of everything selected, not just the first", () => {
    setDoc(fakeEngine(), fill("a"), fill("b"));
    useStore.getState().setSelection("a", ["b"]);
    useStore.getState().setTool("run");
    useStore.getState().setTool("select");
    expect(useStore.getState().selectedId).toBeNull();
    expect(useStore.getState().extraIds).toEqual([]);
  });

  it("Duplicate copies everything selected, in one undo step, and selects the copies", async () => {
    setDoc(fakeEngine(), fill("a"), fill("b"), fill("c"));
    useStore.getState().setSelection("a", ["b", "c"]);
    run("arrange.duplicate");
    await A.whenIdle();
    await sleep(0);
    const s = useStore.getState();
    expect(items().length).toBe(6);
    expect(s.history.past.length).toBe(1);
    expect([s.selectedId, ...s.extraIds].filter((id) => ["a", "b", "c"].includes(id!))).toEqual([]);
    expect(s.extraIds.length).toBe(2);
  });
});

describe("Edits that overlap a render", () => {
  it("Delete builds on an edit that's still rendering", async () => {
    const engine = fakeEngine({ renderDelay: 40 });
    setDoc(engine, fill("x"), fill("y"));
    A.setObjectThread("x", { color: "#ff0000", name: "", brand: "", catalog: "" });
    useStore.getState().select("y");
    A.removeSelected();
    await A.whenIdle();
    expect(items().map((i) => i.id)).toEqual(["x"]);
    expect(colorOf("x")).toBe("#ff0000");
  });

  it("an edit that rendered fine is kept when the newer one fails", async () => {
    const engine = fakeEngine({ renderDelay: 40 });
    setDoc(engine, fill("x"), fill("y"));
    A.setObjectThread("x", { color: "#ff0000", name: "", brand: "", catalog: "" });
    await sleep(5);
    engine.state.failIf = (l) => l.items.some((it) => (it as ObjectItem).thread.color === "#00ff00");
    A.setObjectThread("y", { color: "#00ff00", name: "", brand: "", catalog: "" });
    await A.whenIdle();
    expect(useStore.getState().notice?.kind).toBe("error");
    expect(colorOf("x")).toBe("#ff0000");
    expect(colorOf("y")).toBe("#111111");
  });

  it("edits overtaken by quicker ones still count as done (their follow-ups, like selecting the new shape, run)", async () => {
    const engine = fakeEngine({ renderDelay: 30 });
    setDoc(engine, fill("x"));
    const l = () => A.currentLayout()!;
    const first = A.commit({ ...l(), items: [...l().items, fill("y")] }); // renders...
    await sleep(5);
    const second = A.commit({ ...l(), items: [...l().items, fill("z")] }); // ...this one waits
    const third = A.commit({ ...l(), items: [...l().items, fill("w")] }); // ...and is replaced by this
    expect(await Promise.all([first, second, third])).toEqual([true, true, true]);
    expect(items().map((i) => i.id)).toEqual(["x", "y", "z", "w"]);
  });

  it("a shape whose render fails keeps its clicked points", async () => {
    const engine = fakeEngine();
    setDoc(engine, fill("x"));
    engine.state.failIf = (l) => l.items.length > 1;
    useStore.getState().setTool("fill");
    A.penAdd([0, 0, "c"]);
    A.penAdd([5, 0, "c"]);
    A.penAdd([10, 0, "c"]);
    await A.penFinish();
    expect(useStore.getState().pen?.a.length).toBe(3);
    expect(useStore.getState().notice?.kind).toBe("error");
  });

  it("a change that changes nothing is no undo step and doesn't count as unsaved", async () => {
    const engine = fakeEngine();
    const doc = setDoc(engine, fill("a"));
    await A.commit(JSON.parse(JSON.stringify(doc.layout)));
    A.setItemPinned("gone", true);
    await A.whenIdle();
    const s = useStore.getState();
    expect(s.history.past.length).toBe(0);
    expect(s.history.present).toBe(s.savedDoc);
  });

  it("closing or opening asks about an edit that's still rendering", async () => {
    const engine = fakeEngine({ renderDelay: 40 });
    setDoc(engine, fill("a"));
    A.setObjectThread("a", { color: "#00ff00", name: "", brand: "", catalog: "" });
    expect(await A.confirmDiscard()).toBe(false); // the "Save your changes?" question was asked, and cancelled
    expect(dialog.asked).toBe(1);
    await A.whenIdle();
  });

  it("two quick turns of several things land where two slow ones do", async () => {
    const engine = fakeEngine({ renderDelay: 30 });
    setDoc(engine, file("f1"), file("f2"));
    await A.commit({ ...A.currentLayout()!, items: [file("f1"), { ...file("f2"), transform: { ...file("f2").transform, x: 40 } } as LayoutItem] });
    // Make the shown render say where each design is (f2 40 mm to the right).
    useStore.setState({
      design: { ...useStore.getState().design!, items: [{ id: "f1", bounds_mm: [0, 0, 10, 10] }, { id: "f2", bounds_mm: [40, 0, 50, 10] }] as never },
    });
    useStore.getState().setSelection("f1", ["f2"]);
    // A move that hasn't rendered yet, then a turn: the turn uses where f2 is now.
    A.editSelection({ move: [10, 0] });
    const g = A.selectionGeometry(["f1", "f2"]);
    expect(g.centers.f2[0]).toBeCloseTo(55);
    expect(g.centers.f1[0]).toBeCloseTo(15);
    await A.whenIdle();
  });
});

describe("Documents and files", () => {
  it("a drawing tool chosen before there's a design stays chosen", async () => {
    useStore.setState({ engine: fakeEngine() as never, history: { past: [], present: null, future: [] }, savedDoc: null, tool: "select" });
    run("tool.fill");
    await A.whenIdle();
    await sleep(0);
    expect(useStore.getState().history.present).not.toBeNull();
    expect(useStore.getState().tool).toBe("fill");
  });

  it("after Save the design takes the file's name, without counting as a change", async () => {
    const engine = fakeEngine();
    setDoc(engine, fill("a"));
    useStore.setState({ history: { ...useStore.getState().history, present: { ...useStore.getState().history.present!, layout: { ...A.currentLayout()!, title: "Flower.pes" } } } });
    expect(await A.saveProject(true)).toBe(true);
    const s = useStore.getState();
    expect(s.history.present!.layout.title).toBe("My Flower");
    expect(s.history.present).toBe(s.savedDoc);
    expect(s.projectPath).toBe("C:/x/My Flower.ludd");
  });

  it("Recover keeps the copy and doesn't claim success when the work can't be shown", async () => {
    const engine = fakeEngine({ recovery: true });
    setDoc(engine, fill("a"));
    await A.checkRecovery();
    engine.state.failIf = () => true;
    expect(await A.restoreRecovery()).toBe(false);
    expect(useStore.getState().notice?.kind).toBe("error");
    expect(A.isRecoveryWaiting()).toBe(true);
    engine.state.failIf = null;
    expect(await A.restoreRecovery()).toBe(true);
    expect(A.isRecoveryWaiting()).toBe(false);
  });
});

describe("Command registry", () => {
  it("every command has its own id and a keyboard shortcut", () => {
    const ids = A.COMMANDS.map((c) => c.id);
    expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([]);
    expect(A.COMMANDS.filter((c) => !c.shortcut.trim()).map((c) => c.id)).toEqual([]);
  });
});

describe("Shortcuts on a Mac", () => {
  const ev = (key: string, code: string, alt = true) => ({ key, code, ctrlKey: false, metaKey: false, shiftKey: false, altKey: alt });
  it("Option+letter shortcuts match although Option changes the character", () => {
    // What a Mac reports for Option+A, Option+H, Option+[: "å", "˙", "“".
    expect(matchesShortcut(ev("å", "KeyA"), "Alt+A", true)).toBe(true);
    expect(matchesShortcut(ev("˙", "KeyH"), "Alt+H", true)).toBe(true);
    expect(matchesShortcut(ev("“", "BracketLeft"), "Alt+[", true)).toBe(true);
    expect(matchesShortcut(ev("å", "KeyA"), "Alt+H", true)).toBe(false);
    // Without Option, the code isn't used.
    expect(matchesShortcut(ev("å", "KeyA", false), "A", true)).toBe(false);
  });
});

describe("Keyboard handler", () => {
  type FakeKey = { key: string; repeat?: boolean; target?: unknown; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean; altKey: boolean; prevented: boolean; preventDefault: () => void };
  const key = (k: string, extra: Partial<FakeKey> = {}): FakeKey => {
    const e: FakeKey = { key: k, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, prevented: false, preventDefault: () => (e.prevented = true), ...extra };
    return e;
  };
  /** A focused element that matches the given selectors. */
  const el = (matches: (sel: string) => boolean, closest: (sel: string) => unknown = () => null) => ({ matches, closest });
  const press = (e: FakeKey) => onKeyDown(e as unknown as KeyboardEvent);

  beforeEach(() => {
    setDoc(fakeEngine(), fill("a"));
  });

  it("holding Esc down lets go of one thing, not one per key repeat", () => {
    useStore.setState({ tool: "fill", pen: { kind: "fill", a: [[0, 0, "c"]], b: [] } });
    press(key("Escape"));
    expect(useStore.getState().pen).toBeNull();
    press(key("Escape", { repeat: true }));
    expect(useStore.getState().tool).toBe("fill");
  });

  it("keys don't reach the design behind an open dialog, even with the focus on the page", () => {
    useStore.getState().select("a");
    const g = globalThis as { document?: unknown };
    g.document = { querySelector: (sel: string) => (sel === "dialog[open]" ? {} : null), activeElement: null };
    try {
      const e = key("Escape");
      press(e);
      expect(e.prevented).toBe(false); // the dialog's own Esc still closes it
      expect(useStore.getState().selectedId).toBe("a");
    } finally {
      delete g.document;
    }
  });

  it("Space on a focused name (role=button) doesn't also play the stitch-out", () => {
    const t = el((sel) => sel.includes("[role=button]") && sel.includes(":focus-visible"));
    press(key(" ", { target: t }));
    expect(useStore.getState().spaceDown).toBe(false);
  });

  it("arrow keys on the focused panel edge don't nudge the design", () => {
    useStore.getState().select("a");
    const t = el((sel) => sel === "[role=separator]");
    press(key("ArrowLeft", { target: t }));
    expect(useStore.getState().history.past.length).toBe(0);
  });

  it("Esc lets go of a held thing before the field being typed in", () => {
    let letGo = 0;
    holdEscape(() => letGo++);
    let blurred = 0;
    const field = { blur: () => blurred++ };
    const t = el(() => false, (sel) => (sel.startsWith("input") ? field : null));
    press(key("Escape", { target: t }));
    expect(letGo).toBe(1);
    expect(blurred).toBe(0);
  });
});

describe("Dialog dragging", () => {
  it("a dialog is dragged by its title, or by the empty part of a leading tab bar", () => {
    const title = { closest: (sel: string) => (sel.includes("h2") ? "TITLE" : null), matches: () => false };
    const tabs = { closest: () => null, matches: (sel: string) => sel.includes(".tabs") };
    const tabButton = { closest: () => null, matches: () => false };
    expect(dragHandle(title as never)).toBe("TITLE");
    expect(dragHandle(tabs as never)).toBe(tabs);
    expect(dragHandle(tabButton as never)).toBeNull();
    expect(dragHandle(null)).toBeNull();
  });
});
