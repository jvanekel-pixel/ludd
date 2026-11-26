/** Adjusting single letters (P5-A4): the mode, its dots on the design, dragging and nudging a
 *  letter, resetting, and what Order & colors does to a text's color runs. A fake engine; no
 *  browser. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, currentLayout, recolorBlock, setText, whenIdle } from "../actions";
import { activeCanvasTool, drawOverlays, type CanvasCtx } from "../canvas/hooks";
import "../cmd";
import { newDoc } from "../design/layout";
import type { Design, LayoutItem, LetterPart, TextItem, TextRun, Thread, Transform } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { useStore } from "../store";
import {
  canAdjustLetters,
  leaveLetterMode,
  nudgeLetter,
  pickLetter,
  pruneLetterEdits,
  recolorRuns,
  resetLetter,
  setLetterEdit,
  useLetterMode,
} from "./letters";

const BLACK: Thread = { color: "#000000", name: "Black", brand: "", catalog: "" };
const RED: Thread = { color: "#cc2222", name: "Red", brand: "", catalog: "" };
const GREY: Thread = { color: "#888888", name: "Grey", brand: "", catalog: "" };
const IDENT: Transform = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };

const text = (patch: Partial<TextItem> = {}): TextItem => ({
  id: "t",
  kind: "text",
  text: "IOI",
  font: { path: "f.ttf", index: 0, family: "Test", style: "Regular" },
  size_mm: 10,
  spacing_mm: 0,
  style: "satin",
  shape: { type: "line" },
  monogram: false,
  thread: BLACK,
  transform: IDENT,
  threads: [],
  ops: [],
  ...patch,
});

/** Three letters as shown: 4 x 10 mm boxes round x = -8, 0 and 8. */
const box = (x: number): [number, number][] => [[x - 2, -5], [x + 2, -5], [x + 2, 5], [x - 2, 5]];
const PARTS: LetterPart[] = [-8, 0, 8].map((x, n) => ({
  index: n,
  kind: "fill",
  look: "satin",
  start: [x, -5],
  end: [x, 5],
  ring: box(x),
  letter: n,
  line: 0,
  run: 0,
}));

function designFor(items: LayoutItem[], runs: TextRun[] = [{ run: 0, what: "letters", letters: [0, 1, 2], slots: [0] }]): Design {
  return {
    path: "",
    name: "x",
    format: "layout",
    info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 20, height_mm: 10, bounds_mm: [-10, -5, 10, 5] },
    threads: [BLACK],
    blocks: runs.map((r) => ({ thread: 0, start: 0, end: 0, sources: [{ item: 0, block: r.run }] })),
    records: { x: [], y: [], kind: [] },
    items: items.map((it) => ({ id: it.id, name: it.id, kind: "text", center_mm: [0, 0], bounds_mm: [-10, -5, 10, 5], source_size_mm: null, letters: PARTS, runs })),
  };
}

/** The engine's text.letter_frame: an offset on the design in the text's unturned frame. */
function unturned(t: Transform, [x, y]: [number, number]): [number, number] {
  const a = (-t.rotate * Math.PI) / 180;
  const [rx, ry] = [x * Math.cos(a) - y * Math.sin(a), x * Math.sin(a) + y * Math.cos(a)];
  const round = (v: number) => Math.round(v * 1000) / 1000;
  return [round(rx / (t.scale_x * (t.flip_x ? -1 : 1))), round(ry / (t.scale_y * (t.flip_y ? -1 : 1)))];
}

const calls: string[] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    calls.push(method);
    if (method === "text.letter_frame") {
      const it = params.item as TextItem;
      const at = params.at as [number, number];
      return unturned(it.transform, [at[0] - it.transform.x, at[1] - it.transform.y]) as T;
    }
    if (method === "layout.render") return designFor((params.layout as { items: LayoutItem[] }).items) as T;
    return null as T;
  },
};

function open(item: TextItem = text(), design?: Design) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [item] as LayoutItem[] } };
  useStore.setState({
    engine: engine as never,
    history: { past: [], present: doc, future: [] },
    savedDoc: doc,
    design: design ?? designFor([item]),
    selectedId: item.id,
    extraIds: [],
    tool: "select",
    stitchEdit: null,
    knife: null,
    pen: null,
    measure: null,
    ruler: null,
    angleFor: null,
    notice: null,
  });
}

/** Whatever an action started (an engine call, then a render) has finished. */
async function settle() {
  for (let i = 0; i < 3; i++) {
    await new Promise((r) => setTimeout(r, 0));
    await whenIdle();
  }
}

const item = () => currentLayout()!.items[0] as TextItem;
const edits = () => item().letter_edits;
const steps = () => useStore.getState().history.past.length;

const ctx: CanvasCtx = { toMm: () => [0, 0], pxMm: () => 0.1, redraw: () => {} };
const pointer = (extra: object = {}) => ({ button: 0, pointerId: 7, target: null, ...extra }) as unknown as PointerEvent;
const tool = () => activeCanvasTool()!;

async function drag(from: [number, number], to: [number, number]) {
  expect(tool().down!(from, pointer(), ctx)).toBe(true);
  expect(tool().move!(to, pointer(), ctx)).toBe(true);
  expect(tool().up!(to, pointer(), ctx)).toBe(true);
  await settle();
}

beforeEach(async () => {
  await settle();
  leaveLetterMode();
  while (letGoNewest());
  calls.length = 0;
  open();
});

describe("single-letter mode", () => {
  it("is turned on by its command for the selected text, and Esc leaves it", () => {
    command("text.letters").run();
    expect(useLetterMode.getState()).toEqual({ id: "t", letter: null });
    expect(activeCanvasTool()?.id).toBe("letters");
    expect(letGoNewest()).toBe(true); // Esc
    expect(useLetterMode.getState().id).toBeNull();
    expect(activeCanvasTool()).toBeUndefined();
    expect(heldCount()).toBe(0);
  });

  it("is turned off by its command too, and takes the pointer back from the Text tool", () => {
    useStore.getState().setTool("text");
    useStore.getState().select("t");
    useStore.setState({ tool: "text" });
    command("text.letters").run();
    expect(useStore.getState().tool).toBe("select");
    expect(useLetterMode.getState().id).toBe("t");
    command("text.letters").run();
    expect(useLetterMode.getState().id).toBeNull();
    expect(heldCount()).toBe(0);
  });

  it("ends when something else is selected, a tool is picked or the text goes", async () => {
    for (const leave of [
      () => useStore.getState().select(null),
      () => useStore.getState().setTool("fill"),
      () => useStore.setState({ history: { past: [], present: { ...newDoc() }, future: [] } }),
    ]) {
      open();
      command("text.letters").run();
      leave();
      expect(useLetterMode.getState().id).toBeNull();
      expect(heldCount()).toBe(0);
    }
  });

  it("isn't offered for a pinned text", () => {
    open(text({ locked: true }));
    expect(canAdjustLetters()).toBe(false);
  });
});

describe("dragging a letter", () => {
  beforeEach(() => command("text.letters").run());

  it("writes the move into letter_edits, one undo step", async () => {
    await drag([0.3, 0.2], [3.3, -1.8]);
    expect(useLetterMode.getState().letter).toBe(1);
    expect(edits()).toEqual({ "1": { dx_mm: 3, dy_mm: -2 } });
    expect(steps()).toBe(1);
    expect(calls).toContain("text.letter_frame");
    await drag([0, 0], [-1, 0]); // another drag adds to it (dots are where the design shows them)
    expect(edits()).toEqual({ "1": { dx_mm: 2, dy_mm: -2 } });
    expect(steps()).toBe(2);
  });

  it("is turned into the text's own frame first", async () => {
    open(text({ transform: { ...IDENT, x: 40, y: 10, rotate: 90 } }), designFor([text()]));
    expect(useLetterMode.getState().id).toBe("t"); // still on, from before the turn
    await drag([8, 0], [8, 3]);
    expect(edits()).toEqual({ "2": { dx_mm: 3 } });
  });

  it("starts on a letter anywhere inside it, not only on its dot", () => {
    expect(tool().down!([-9.5, 4], pointer(), ctx)).toBe(true);
    expect(useLetterMode.getState().letter).toBe(0);
    letGoNewest();
  });

  it("a click only picks the letter", async () => {
    tool().down!([8, 0], pointer(), ctx);
    tool().up!([8.1, 0], pointer(), ctx);
    await settle();
    expect(useLetterMode.getState().letter).toBe(2);
    expect(edits()).toBeUndefined();
    expect(heldCount()).toBe(1); // only the mode's own
  });

  it("leaves clicks away from the letters, and other buttons, to the canvas", () => {
    expect(tool().down!([30, 30], pointer(), ctx)).toBe(false);
    expect(tool().down!([0, 0], pointer({ button: 2 }), ctx)).toBe(false);
    expect(tool().down!([0, 0], pointer({ button: 1 }), ctx)).toBe(false);
    expect(tool().move!([0, 0], pointer(), ctx)).toBe(false);
    expect(tool().up!([0, 0], pointer(), ctx)).toBe(false);
    expect(useLetterMode.getState().letter).toBeNull();
  });

  it("Esc during a drag puts the letter back and stays in the mode", async () => {
    tool().down!([0, 0], pointer(), ctx);
    tool().move!([4, 4], pointer(), ctx);
    expect(tool().move!([5, 5], pointer({ pointerId: 8 }), ctx)).toBe(false); // another pointer
    letGoNewest();
    expect(tool().up!([4, 4], pointer(), ctx)).toBe(false);
    await settle();
    expect(edits()).toBeUndefined();
    expect(useLetterMode.getState()).toEqual({ id: "t", letter: 1 });
  });
});

describe("arrow keys", () => {
  beforeEach(() => command("text.letters").run());

  it("nudge the picked letter, a run of taps being one undo step", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(5000); // however slow the machine is
    try {
      pickLetter(2);
      for (let i = 0; i < 3; i++) {
        command("arrange.right").run();
        await settle();
      }
      command("arrange.upBig").run();
      await settle();
      command("arrange.leftFine").run();
      await settle();
      expect(edits()).toEqual({ "2": { dx_mm: 2.9, dy_mm: -10 } });
      expect(item().transform).toEqual(IDENT);
      expect(steps()).toBe(1);
      clock.mockReturnValue(6000); // after a pause, a tap is its own step
      command("arrange.right").run();
      await settle();
      expect(steps()).toBe(2);
    } finally {
      clock.mockRestore();
    }
  });

  it("move the whole text when no letter is picked", async () => {
    expect(nudgeLetter(1, 0)).toBe(false);
    command("arrange.right").run();
    await settle();
    expect(edits()).toBeUndefined();
    expect(item().transform.x).toBe(1);
  });
});

describe("putting letters back", () => {
  it("Put the letters back clears every letter's changes", async () => {
    open(text({ letter_edits: { "0": { rotate: 20 }, "2": { thread: RED } } }));
    expect(command("text.resetLetters").enabled?.()).toBe(true);
    command("text.resetLetters").run();
    await settle();
    expect(edits()).toBeUndefined();
    expect("letter_edits" in item()).toBe(false);
    expect(steps()).toBe(1);
  });

  it("Put this letter back keeps the others", async () => {
    open(text({ letter_edits: { "0": { rotate: 20 }, "2": { thread: RED } } }));
    await resetLetter("t", 0);
    expect(edits()).toEqual({ "2": { thread: RED } });
  });

  it("a change back to nothing leaves no letter_edits, and nothing changed is no undo step", async () => {
    await setLetterEdit("t", 1, { scale: 1.5, rotate: 360 });
    expect(edits()).toEqual({ "1": { scale: 1.5 } });
    await setLetterEdit("t", 1, { scale: 1 });
    expect(edits()).toBeUndefined();
    const before = steps();
    await setLetterEdit("t", 1, { dx_mm: 0 });
    expect(steps()).toBe(before);
  });

  it("keeps sizes within 50 to 200% and turns within -180 to 180", async () => {
    await setLetterEdit("t", 0, { scale: 5, rotate: 270, angle_deg: -30 });
    expect(edits()).toEqual({ "0": { scale: 2, rotate: -90, angle_deg: 150 } });
  });

  it("a letter's chosen start and end move with it, and go back to automatic when it's turned or resized", async () => {
    open(text({ letters: { "1": { start_mm: [0, -5] }, "0": { end_mm: [-8, 5] } } }));
    await setLetterEdit("t", 1, { dx_mm: 3, dy_mm: 1 });
    expect(item().letters).toEqual({ "1": { start_mm: [3, -4] }, "0": { end_mm: [-8, 5] } });
    await resetLetter("t", 1);
    expect(item().letters).toEqual({ "1": { start_mm: [0, -5] }, "0": { end_mm: [-8, 5] } });
    await setLetterEdit("t", 1, { rotate: 45 });
    expect(item().letters).toEqual({ "0": { end_mm: [-8, 5] } });
  });
});

describe("Order & colors", () => {
  const runs: TextRun[] = [
    { run: 0, what: "shadow", letters: [], slots: [] },
    { run: 1, what: "letters", letters: [0], slots: [] },
    { run: 2, what: "letters", letters: [1, 2], slots: [] },
    { run: 3, what: "outline", letters: [], slots: [] },
    { run: 4, what: "frame", letters: [], slots: [] },
  ];
  const it_ = text({
    shadow: { dx_mm: 1, dy_mm: 1, thread: GREY },
    outline: { gap_mm: 1, width_mm: 1.5, style: "satin", thread: GREY },
    ornament: { id: "circle" },
    letter_edits: { "1": { dx_mm: 2, thread: GREY } },
  });
  const layout = () => ({ ...newDoc().layout, items: [it_] as LayoutItem[] });
  const recolored = (block: number, thread: Thread | null) => recolorRuns(layout(), [{ item: 0, block }], thread, designFor([it_], runs)).items[0] as TextItem;

  it("recoloring a run of letters sets the thread on each of its letters", () => {
    expect(recolored(2, RED).letter_edits).toEqual({ "1": { dx_mm: 2, thread: RED }, "2": { thread: RED } });
    expect(recolored(2, RED).threads).toEqual([]);
    // Back to as it was: the letters' own thread goes.
    expect(recolored(2, null).letter_edits).toEqual({ "1": { dx_mm: 2 } });
    const only = recolorRuns({ ...newDoc().layout, items: [text({ letter_edits: { "0": { thread: RED } } })] }, [{ item: 0, block: 1 }], null, designFor([it_], runs));
    expect("letter_edits" in only.items[0]).toBe(false);
  });

  it("a run holding all of a color's letters takes the change as the text's color", () => {
    const d = designFor([text()]);
    const out = recolorRuns({ ...newDoc().layout, items: [text()] }, [{ item: 0, block: 0 }], RED, d);
    expect((out.items[0] as TextItem).threads).toEqual([RED]);
    expect((out.items[0] as TextItem).letter_edits).toBeUndefined();
    const back = recolorRuns(out, [{ item: 0, block: 0 }], null, d);
    expect((back.items[0] as TextItem).threads).toEqual([null]);
    const second = designFor([text()], [{ run: 0, what: "letters", letters: [0, 1, 2], slots: [1] }]);
    expect((recolorRuns({ ...newDoc().layout, items: [text()] }, [{ item: 0, block: 0 }], GREY, second).items[0] as TextItem).threads).toEqual([null, GREY]);
  });

  it("a shadow, outline or frame run recolors that extra", () => {
    expect(recolored(0, RED).shadow).toEqual({ dx_mm: 1, dy_mm: 1, thread: RED });
    expect(recolored(3, RED).outline?.thread).toEqual(RED);
    expect(recolored(4, RED).ornament).toEqual({ id: "circle", thread: RED });
    expect(recolored(0, null)).toBe(it_);
    expect(recolored(4, RED).threads).toEqual([]);
  });

  it("several runs at once, with stitch files recolored as before", () => {
    const file = { id: "f", path: "x.pes", transform: IDENT, threads: [], ops: [] } as unknown as LayoutItem;
    const d = designFor([it_], runs);
    const out = recolorRuns({ ...newDoc().layout, items: [it_, file] }, [{ item: 0, block: 1 }, { item: 0, block: 2 }, { item: 1, block: 0 }], RED, d);
    expect((out.items[0] as TextItem).letter_edits).toEqual({ "0": { thread: RED }, "1": { dx_mm: 2, thread: RED }, "2": { thread: RED } });
    expect(out.items[1].threads).toEqual([RED]);
  });

  it("is what choosing a color there does", async () => {
    open(text(), designFor([text()], [{ run: 0, what: "letters", letters: [0], slots: [] }]));
    recolorBlock(0, RED);
    await settle();
    expect(edits()).toEqual({ "0": { thread: RED } });
  });
});

describe("editing the words", () => {
  it("drops changes past the end, counting only characters that can draw", () => {
    const many = Object.fromEntries([0, 1, 2, 3, 4].map((n) => [String(n), { dx_mm: n + 1 }]));
    expect(pruneLetterEdits(text({ text: "A B\n​C", letter_edits: many })).letter_edits).toEqual({ "0": { dx_mm: 1 }, "1": { dx_mm: 2 }, "2": { dx_mm: 3 } });
    expect(Object.keys(pruneLetterEdits(text({ text: "ABCDE", monogram: true, letter_edits: many })).letter_edits!)).toEqual(["0", "1", "2"]);
    expect("letter_edits" in pruneLetterEdits(text({ text: " ", letter_edits: many }))).toBe(false);
    const kept = text({ text: "ABCDE", letter_edits: many });
    expect(pruneLetterEdits(kept)).toBe(kept);
  });

  it("keeps the changes by letter number when the words change", async () => {
    open(text({ letter_edits: { "0": { dx_mm: 1 }, "2": { dx_mm: 1 } } }));
    setText("t", { text: "XO" });
    await settle();
    expect(edits()).toEqual({ "0": { dx_mm: 1 } });
  });
});

describe("the dots on the design", () => {
  function recorder() {
    const dots: [number, number][] = [];
    let lines = 0;
    const g: Record<string, unknown> = {};
    for (const name of ["moveTo", "lineTo", "closePath", "fill", "stroke", "rect"]) g[name] = () => (name === "lineTo" ? lines++ : 0, g);
    g.circle = (x: number, y: number) => (dots.push([x, y]), g);
    return { g: g as never, dots, lines: () => lines };
  }

  it("sit in the middle of each letter, only while in the mode, with the picked one lit up", () => {
    const none = recorder();
    drawOverlays(none.g, 0.1, ctx);
    expect(none.dots).toEqual([]);
    command("text.letters").run();
    const plain = recorder();
    drawOverlays(plain.g, 0.1, ctx);
    expect(plain.dots).toEqual([[-8, 0], [0, 0], [8, 0]]);
    expect(plain.lines()).toBe(0);
    pickLetter(1);
    const picked = recorder();
    drawOverlays(picked.g, 0.1, ctx);
    expect(picked.lines()).toBeGreaterThan(0); // its outline
  });

  it("follow the letter being dragged", () => {
    command("text.letters").run();
    tool().down!([0, 0], pointer(), ctx);
    tool().move!([3, 2], pointer(), ctx);
    const live = recorder();
    drawOverlays(live.g, 0.1, ctx);
    expect(live.dots).toContainEqual([3, 2]);
    letGoNewest();
  });
});
