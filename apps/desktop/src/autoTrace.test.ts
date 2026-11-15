import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import { acceptGuess, autoTraceAt, setSpacing, setSpread, yourUsualFirst } from "./autoTrace";
import { newDoc } from "./design/layout";
import type { Doc, RefImage } from "./design/types";
import { letGoNewest } from "./escape";
import * as F from "./features";
import { useStore, type TraceGuess, type TracedShape } from "./store";

const fill = (id: string, background = false) => ({ kind: "fill", id, label: id, outline: [], holes: [], background }) as TraceGuess;

describe("yourUsualFirst", () => {
  it("keeps the engine's order until you have a favourite", () => {
    const g = [fill("simple"), fill("middle"), fill("inside")];
    expect(yourUsualFirst(g, {}).map((x) => x.id)).toEqual(["simple", "middle", "inside"]);
  });
  it("puts the kind you pick most first, the background always last", () => {
    const g = [fill("simple"), fill("middle"), fill("inside"), fill("lines", true)];
    const order = yourUsualFirst(g, { inside: 5, middle: 2, lines: 9 }).map((x) => x.id);
    expect(order).toEqual(["inside", "middle", "simple", "lines"]);
  });
});

// ---------------------------------------------------------------- with a stand-in engine

type Pending = { method: string; params: Record<string, unknown>; resolve: (v: unknown) => void; reject: (e: unknown) => void };

/** An engine whose trace calls wait until the test answers them; renders answer at once. */
function fakeEngine(opts: { renderFails?: boolean } = {}) {
  const pending: Pending[] = [];
  const calls: string[] = [];
  const engine = {
    calls,
    pending,
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      calls.push(method);
      if (method.startsWith("trace.")) return new Promise((resolve, reject) => pending.push({ method, params, resolve: resolve as (v: unknown) => void, reject }));
      if (method === "layout.render") {
        if (opts.renderFails) throw new Error("This shape is too small to fill");
        const layout = params.layout as { items: { id: string }[] };
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
      return null as T;
    },
  };
  return engine;
}

const picture: RefImage = { id: "p1", name: "logo", path: "C:/pics/logo.png", data_url: "", x: 0, y: 0, width_mm: 100, height_mm: 80, rotate: 0, opacity: 0.5, locked: false, visible: true };

function setDoc(engine: ReturnType<typeof fakeEngine>) {
  const d = newDoc();
  const doc: Doc = { ...d, images: [picture] };
  useStore.setState({
    engine: engine as never,
    history: { past: [], present: doc, future: [] },
    savedDoc: doc,
    selectedId: null,
    notice: null,
    tool: "autotrace",
    autoTrace: null,
    autoAll: null,
    autoSpacing: 3,
    autoSpread: 5,
  });
}

const flush = () => new Promise((r) => setTimeout(r, 0));
const shape = (color: string): TracedShape => ({ kind: "fill", outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]], holes: [], color }) as TracedShape;

beforeEach(async () => {
  await A.whenIdle();
  while (letGoNewest());
});

describe("whole-picture preview", () => {
  it("shows only the newest run's answer", async () => {
    const e = fakeEngine();
    setDoc(e);
    const first = F.digitizeWholePicture({ outlines: true });
    useStore.getState().setAutoAll(null); // Esc
    const second = F.digitizeWholePicture({ outlines: false });
    e.pending[0].resolve({ shapes: [shape("#111111")] }); // the older, slower answer arrives first
    await first;
    expect(useStore.getState().autoAll).toMatchObject({ busy: true, outlines: false });
    e.pending[1].resolve({ shapes: [shape("#222222")] });
    await second;
    expect(useStore.getState().autoAll).toMatchObject({ busy: false, outlines: false, shapes: [{ color: "#222222" }] });
  });

  it("reads the picture again when point spacing, spread or the picture's place change", async () => {
    const e = fakeEngine();
    setDoc(e);
    const run = F.digitizeWholePicture();
    e.pending[0].resolve({ shapes: [shape("#111111")] });
    await run;
    setSpacing(5);
    expect(e.pending).toHaveLength(2);
    expect(e.pending[1].params.spacing_mm).toBe(5);
    e.pending[1].resolve({ shapes: [shape("#111111")] });
    await flush();
    setSpread(8);
    expect(e.pending).toHaveLength(3);
    expect(e.pending[2].params.spread).toBe(8);
    e.pending[2].resolve({ shapes: [shape("#111111")] });
    await flush();
    // The picture is moved: the preview follows it.
    const doc = useStore.getState().history.present!;
    useStore.getState().setHistory({ past: [doc], present: { ...doc, images: [{ ...picture, x: 40, rotate: 15 }] }, future: [] });
    expect(e.pending).toHaveLength(4);
    expect(e.pending[3].params.placement).toMatchObject({ x: 40, rotate: 15 });
  });
});

describe("accepting a guess", () => {
  async function guessOnScreen(e: ReturnType<typeof fakeEngine>, extra: Record<string, unknown> = {}) {
    const asked = autoTraceAt(0, 0);
    await flush();
    const g = { ...fill("simple"), outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]], color: "#dc2828" };
    e.pending[0].resolve({ candidates: [g], ...extra });
    await asked;
  }

  it("keeps the guess and says nothing about adding when the add fails", async () => {
    const e = fakeEngine({ renderFails: true });
    setDoc(e);
    await guessOnScreen(e);
    await acceptGuess("fill");
    const s = useStore.getState();
    expect(s.autoTrace).not.toBeNull();
    expect(s.autoTrace!.busy).toBe(false); // ready to try again
    expect(s.notice?.text ?? "").not.toMatch(/^Added/);
  });

  it("adds, then lets go of the guess and says so", async () => {
    const e = fakeEngine();
    setDoc(e);
    await guessOnScreen(e);
    await acceptGuess("fill");
    const s = useStore.getState();
    expect(s.autoTrace).toBeNull();
    expect(s.history.present!.layout.items).toHaveLength(1);
    expect(s.notice?.text).toMatch(/^Added/);
  });

  it("says when the AI couldn't run, and still shows the usual guesses", async () => {
    const e = fakeEngine();
    setDoc(e);
    await guessOnScreen(e, { ai_error: "The AI tracing model couldn't run (RuntimeError)." });
    expect(useStore.getState().autoTrace?.guesses).toHaveLength(1);
    expect(useStore.getState().notice?.text).toMatch(/AI tracing model couldn't run/);
  });
});
