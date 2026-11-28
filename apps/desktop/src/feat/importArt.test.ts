/** Importing artwork (P7-D1), with a fake engine whose answers the tests hand over when they like. */
import { beforeEach, describe, expect, it, vi } from "vitest";

const picked = vi.hoisted(() => ({ path: null as string | null }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => picked.path, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import type { Graphics } from "pixi.js";
import { defaultsFor, setObjectParams, undoEdit, whenIdle } from "../actions";
import { drawOverlays } from "../canvas/hooks";
import { importOutlines } from "../canvas/importOverlay";
import { newDoc } from "../design/layout";
import type { LayoutItem, ObjectItem } from "../design/types";
import { loadPrefs } from "../prefs";
import { useStore } from "../store";
import { addImported, ART_FILE, canAdd, countWords, importArtwork, setArtOptions, toggleColor, useImportArt, type ArtPreview, type ArtShape } from "./importArt";

/** localStorage for node: just enough for the prefs. */
const store = new Map<string, string>();
vi.stubGlobal("localStorage", { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v), clear: () => store.clear() });

const sq = (x: number, s = 10): [number, number, "l"][] => [[x, 0, "l"], [x + s, 0, "l"], [x + s, s, "l"], [x, s, "l"]];
const SHAPES: ArtShape[] = [
  { kind: "fill", geometry: { outline: sq(-45, 90) }, color: "#ffffff", name: "", background: true },
  { kind: "fill", geometry: { outline: sq(-40), holes: [sq(-37, 4)] }, color: "#ff0000", name: "Door" },
  { kind: "run", geometry: { nodes: [[0, 0, "c"], [20, 0, "l"]] }, color: "#0000ff", name: "" },
  { kind: "satin", geometry: { nodes: sq(10), width_mm: 3, closed: true }, color: "#ff0000", name: "" },
];
const answer = (patch: Partial<ArtPreview> = {}): ArtPreview => ({ size_mm: [86, 54], scale_note: null, shapes: SHAPES, skipped: [], warnings: [], pages: 1, ...patch });

type Call = { method: string; params: Record<string, unknown>; resolve: (v: unknown) => void; reject: (e: Error) => void };
let calls: Call[] = [];
/** art.preview and threads.match wait to be answered; layout.render answers at once. */
const engine = {
  call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "layout.render") {
      const items = (params.layout as { items: LayoutItem[] }).items;
      return Promise.resolve({ path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T);
    }
    return new Promise<T>((resolve, reject) => calls.push({ method, params, resolve: resolve as (v: unknown) => void, reject }));
  },
};
const asked = () => calls.filter((c) => c.method === "art.preview");
const tick = () => new Promise((r) => setTimeout(r, 0));

const already = {
  id: "a", kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
  transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [],
} as unknown as ObjectItem;

const items = () => (useStore.getState().history.present?.layout.items ?? []) as ObjectItem[];

beforeEach(async () => {
  useStore.getState().setDialog(null);
  await whenIdle();
  store.clear();
  calls = [];
  picked.path = null;
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items: [already] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], notice: null, tool: "select", pen: null, charts: [], units: "mm" });
});

/** Open the dialog on a file and answer its first preview. */
async function opened(path = "C:\\art\\logo.svg", preview = answer()) {
  const done = importArtwork(path);
  await tick();
  asked()[0].resolve(preview);
  await done;
}

describe("importing artwork", () => {
  it("asks the engine for the drawing at its real size, and nothing is added yet", async () => {
    await opened();
    expect(useStore.getState().dialog).toBe("importArt");
    expect(asked()[0].params).toEqual({ path: "C:\\art\\logo.svg", options: { width_mm: null, strokes: "auto", closed_as_fills: false, page: 0, keep_background: false } });
    expect(items()).toEqual([already]);
    expect(useStore.getState().history.past).toHaveLength(0);
    expect(countWords(SHAPES.slice(1))).toBe("1 fill, 1 line, 1 satin");
  });

  it("shapes become objects with default settings in one group", async () => {
    localStorage.setItem("ludd.prefs", JSON.stringify({ objectDefaults: { run: { stitch_mm: 3 } } }));
    await opened();
    expect(await addImported()).toBe(true);
    const added = items().slice(1);
    expect(added.map((o) => [o.kind, o.thread.color, o.name])).toEqual([["fill", "#ff0000", "Door"], ["run", "#0000ff", undefined], ["satin", "#ff0000", undefined]]);
    expect(added.map((o) => o.geometry)).toEqual(SHAPES.slice(1).map((s) => s.geometry));
    expect(added.map((o) => o.params)).toEqual([defaultsFor("fill"), defaultsFor("run"), defaultsFor("satin")]);
    expect(added[1].params).toMatchObject({ stitch_mm: 3 }); // your own last settings for lines
    expect(new Set(added.map((o) => o.group)).size).toBe(1);
    expect(added[0].group).toBeTruthy();
    const s = useStore.getState();
    expect([s.selectedId, ...s.extraIds]).toEqual(added.map((o) => o.id));
    expect([s.dialog, s.tool, s.history.past.length]).toEqual([null, "select", 1]);
    undoEdit(); // one step takes them all out
    await whenIdle();
    expect(items()).toEqual([already]);
  });

  it("unticked colors are left out, and the background only comes when ticked", async () => {
    await opened();
    toggleColor("#ff0000", false);
    expect(importOutlines().map((o) => o.color)).toEqual(["#0000ff"]);
    expect(await addImported()).toBe(true);
    expect(items().slice(1).map((o) => [o.kind, o.group])).toEqual([["run", undefined]]); // one shape: no group
  });

  it("ticking the background asks again with it kept, and then adds it", async () => {
    await opened();
    setArtOptions({ keep_background: true });
    expect(canAdd(useImportArt.getState())).toBe(false);
    expect(asked()[1].params.options).toMatchObject({ keep_background: true });
    asked()[1].resolve(answer({ size_mm: [90, 90] }));
    await tick();
    expect(await addImported()).toBe(true);
    expect(items().slice(1).map((o) => o.kind)).toEqual(["fill", "fill", "run", "satin"]);
  });

  it("a late answer for older options never replaces a newer one, and Add waits for the newest", async () => {
    await opened();
    expect(canAdd(useImportArt.getState())).toBe(true);
    setArtOptions({ width_mm: 40 });
    expect(canAdd(useImportArt.getState())).toBe(false);
    setArtOptions({ width_mm: 60 });
    const [, older, newer] = asked();
    newer.resolve(answer({ size_mm: [60, 38] }));
    await tick();
    older.resolve(answer({ size_mm: [40, 25] }));
    await tick();
    expect(useImportArt.getState().preview?.size_mm).toEqual([60, 38]);
    expect(canAdd(useImportArt.getState())).toBe(true);
    setArtOptions({ width_mm: 70 });
    older.resolve(answer({ size_mm: [40, 25] })); // (already answered; changes nothing)
    await tick();
    expect(canAdd(useImportArt.getState())).toBe(false);
    asked()[3].reject(new Error("Set a smaller Width."));
    await tick();
    const s = useImportArt.getState();
    expect([s.preview, s.error, canAdd(s), importOutlines()]).toEqual([null, "Set a smaller Width.", false, []]);
    expect(await addImported()).toBe(false);
    expect(items()).toEqual([already]);
  });

  it("Cancel adds nothing, and an answer that arrives afterwards is dropped", async () => {
    const done = importArtwork("C:\\art\\logo.svg");
    await tick();
    useStore.getState().setDialog(null);
    asked()[0].resolve(answer());
    await done;
    await tick();
    expect(items()).toEqual([already]);
    expect(useStore.getState().history.past).toHaveLength(0);
    expect([useImportArt.getState().preview, importOutlines()]).toEqual([null, []]);
    expect(await addImported()).toBe(false);
  });

  it("with no design open, Cancel leaves none open; Add starts one that Undo empties", async () => {
    useStore.setState({ history: { past: [], present: null, future: [] }, savedDoc: null });
    await opened();
    expect(items()).toEqual([]); // an empty design, to show the outlines on its hoop
    useStore.getState().setDialog(null);
    expect(useStore.getState().history.present).toBeNull();
    expect(useStore.getState().design).toBeNull();

    calls = [];
    await opened();
    expect(await addImported()).toBe(true);
    expect(items()).toHaveLength(3);
    undoEdit();
    await whenIdle();
    expect(items()).toEqual([]);
  });

  it("matches colors to your threads, and adds nothing if cancelled while matching", async () => {
    useStore.setState({ charts: [{ id: "my_threads", name: "My threads", brand: "", builtin: false, count: 4, mine: true }] });
    await opened();
    expect(useImportArt.getState().match).toBe(true);
    const adding = addImported();
    await tick();
    const [match] = calls.filter((c) => c.method === "threads.match");
    expect(match.params).toEqual({ colors: ["#ff0000", "#0000ff"], chart: "my_threads", count: 1 });
    useStore.getState().setDialog(null); // cancelled while matching
    match.resolve([[{ code: "1", name: "Red", color: "#ee0000", brand: "Amazon", delta_e: 2 }], [{ code: "2", name: "Blue", color: "#0000ee", brand: "", delta_e: 1 }]]);
    expect(await adding).toBe(false);
    expect(items()).toEqual([already]);

    calls = [];
    await opened();
    const again = addImported();
    await tick();
    calls.filter((c) => c.method === "threads.match")[0].resolve([[{ code: "1", name: "Red", color: "#ee0000", brand: "Amazon", delta_e: 2 }], [{ code: "2", name: "Blue", color: "#0000ee", brand: "", delta_e: 1 }]]);
    expect(await again).toBe(true);
    expect(items().slice(1).map((o) => o.thread)).toEqual([
      { color: "#ee0000", name: "Red", catalog: "1", brand: "Amazon" },
      { color: "#0000ee", name: "Blue", catalog: "2", brand: "" },
      { color: "#ee0000", name: "Red", catalog: "1", brand: "Amazon" },
    ]);
  });

  it("without spools it doesn't ask to match", async () => {
    await opened();
    expect(useImportArt.getState().match).toBe(false);
    expect(await addImported()).toBe(true);
    expect(calls.some((c) => c.method === "threads.match")).toBe(false);
    expect(items()[1].thread).toEqual({ color: "#ff0000", name: "", catalog: "", brand: "" });
  });

  it("remembers how lines come in, and picks the file when none is given", async () => {
    await opened();
    setArtOptions({ strokes: "satins" });
    expect(loadPrefs().importArt).toEqual({ strokes: "satins" });
    useStore.getState().setDialog(null);
    calls = [];
    picked.path = "C:\\art\\badge.dxf";
    const done = importArtwork();
    await tick();
    expect(asked()[0].params).toEqual({ path: "C:\\art\\badge.dxf", options: expect.objectContaining({ strokes: "satins" }) });
    asked()[0].resolve(answer());
    await done;
    picked.path = null;
    useStore.getState().setDialog(null);
    await importArtwork(); // no file chosen: nothing opens
    expect(useStore.getState().dialog).toBeNull();
  });

  it("shapes that can't be sewn keep the dialog open and add nothing", async () => {
    await opened();
    const render = engine.call;
    engine.call = (<T,>(method: string, params: Record<string, unknown> = {}) =>
      method === "layout.render" ? Promise.reject(new Error("This shape is too small to fill")) : (render.call(engine, method, params) as Promise<T>)) as typeof render;
    try {
      expect(await addImported()).toBe(false);
    } finally {
      engine.call = render;
    }
    expect([useStore.getState().dialog, items()]).toEqual(["importArt", [already]]);
    expect(useStore.getState().notice?.text).toBe("This shape is too small to fill");
    setObjectParams("a", {}); // the design is as it was, and still editable
    await whenIdle();
  });

  it("the shapes show as outlines on the hoop, redrawn as ticks change and gone once closed", async () => {
    const moves: [number, number][] = [];
    const strokes: Record<string, unknown>[] = [];
    const g = {} as Record<string, unknown>;
    g.moveTo = vi.fn((x: number, y: number) => (moves.push([x, y]), g));
    g.lineTo = vi.fn(() => g);
    g.stroke = vi.fn((style: Record<string, unknown>) => (strokes.push(style), g));
    const ctx = { toMm: () => [0, 0] as [number, number], pxMm: () => 0.1, redraw: vi.fn() };
    const draw = () => {
      moves.length = strokes.length = 0;
      drawOverlays(g as unknown as Graphics, 0.1, ctx);
    };
    draw(); // nothing to import yet
    expect(moves).toEqual([]);
    await opened();
    expect(ctx.redraw).toHaveBeenCalled();
    draw();
    // Each outline is traced twice (an edge, then its color), a satin's width a third time. The
    // background isn't ticked, so it isn't shown; the fill's hole is.
    expect(moves.filter(([x, y]) => x === -45 && y === 0)).toHaveLength(0);
    expect(moves.filter(([x, y]) => x === -37 && y === 0)).toHaveLength(2);
    expect(strokes).toContainEqual(expect.objectContaining({ width: 3, color: 0xff0000, alpha: 0.35 }));
    ctx.redraw.mockClear();
    toggleColor("#ff0000", false);
    expect(ctx.redraw).toHaveBeenCalled();
    draw();
    expect(new Set(strokes.map((s) => s.color))).toEqual(new Set([0xffffff, 0x0000ff])); // the blue line and its edge
    ctx.redraw.mockClear();
    useStore.getState().setDialog(null);
    expect(ctx.redraw).toHaveBeenCalled();
    draw();
    expect(moves).toEqual([]);
  });

  it("dropped SVG, DXF and PDF files are artwork; designs and pictures are not", () => {
    expect(["a.svg", "b.SVG", "c.dxf", "d.pdf", "e.svgz"].every((p) => ART_FILE.test(p))).toBe(true);
    expect(["a.pes", "b.jef", "c.png", "d.ludd", "svg.pes"].some((p) => ART_FILE.test(p))).toBe(false);
  });
});
