import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Layout, ObjectItem } from "./design/types";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

// A fake of the parts of ./actions the knife, merge and offset use.
const h = vi.hoisted(() => ({
  layout: null as Layout | null,
  commitOk: true,
  call: (async () => ({})) as (method: string, params: unknown) => Promise<unknown>,
  messages: [] as { kind: string; text: string }[],
}));
vi.mock("./actions", () => ({
  addTraced: async () => true,
  commit: async (l: Layout) => {
    if (!h.commitOk) return false;
    h.layout = l;
    return true;
  },
  currentDoc: () => null,
  currentLayout: () => h.layout,
  defaultsFor: () => ({}),
  engine: () => ({ call: (m: string, p: unknown) => h.call(m, p) }),
  exportOptions: () => ({}),
  fail: (err: unknown) => h.messages.push({ kind: "error", text: String((err as Error)?.message ?? err) }),
  info: (text: string) => h.messages.push({ kind: "info", text }),
}));

import { addOffset, finishKnife, mergeSelected, startKnife } from "./features";
import { safeColor, printHtml } from "./print";
import { useStore } from "./store";

const I = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const sq = (x: number, y: number, w: number) => [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]];
const RED = { color: "#cc2222", name: "Red", brand: "", catalog: "" };
const BLUE = { color: "#2222cc", name: "Blue", brand: "", catalog: "" };

function fill(id: string, patch: Partial<ObjectItem> = {}): ObjectItem {
  return { id, kind: "fill", geometry: { outline: sq(0, 0, 20) }, params: { spacing_mm: 0.4 }, thread: RED, transform: I, threads: [], ops: [], ...patch } as ObjectItem;
}

function setLayout(items: ObjectItem[]) {
  h.layout = { items } as unknown as Layout;
}

beforeEach(() => {
  h.commitOk = true;
  h.messages = [];
  useStore.getState().setKnife(null);
});

describe("Knife", () => {
  it("gives each piece the original's colour change, stops, pin and group", async () => {
    const ops = [{ op: "insert", after: 5, command: "stop", n: 40 }] as ObjectItem["ops"];
    setLayout([fill("a", { name: "Face", threads: [BLUE], locked: true, group: "g1", ops })]);
    h.call = async () => ({ geometries: [{ outline: sq(0, 0, 10) }, { outline: sq(10, 0, 10) }] });
    useStore.getState().select("a");
    startKnife();
    await finishKnife([10, -5], [10, 25]);
    const pieces = h.layout!.items as ObjectItem[];
    expect(pieces).toHaveLength(2);
    for (const p of pieces) {
      expect(p.threads).toEqual([BLUE]);
      expect(p.ops).toEqual(ops);
      expect(p.locked).toBe(true);
      expect(p.group).toBe("g1");
      expect(p.thread).toEqual(RED);
    }
    expect(pieces.map((p) => p.name)).toEqual(["Face 1", "Face 2"]);
    expect(h.messages.at(-1)?.text).toMatch(/Cut into 2 pieces/);
  });

  it("stays ready after a cut that missed", async () => {
    setLayout([fill("a")]);
    h.call = async () => {
      throw new Error("The cut doesn't cross the shape");
    };
    useStore.getState().select("a");
    startKnife();
    await finishKnife([50, 50], [60, 60]);
    expect(h.messages.at(-1)?.kind).toBe("error");
    expect(useStore.getState().knife).toEqual({ id: "a", points: [] });
    expect(h.layout!.items).toHaveLength(1);
  });

  it("says nothing about pieces when the change couldn't be made", async () => {
    setLayout([fill("a")]);
    h.call = async () => ({ geometries: [{ outline: sq(0, 0, 10) }, { outline: sq(10, 0, 10) }] });
    h.commitOk = false;
    useStore.getState().select("a");
    startKnife();
    await finishKnife([10, -5], [10, 25]);
    expect(h.messages.some((m) => /Cut into/.test(m.text))).toBe(false);
  });
});

describe("Merge", () => {
  it("keeps the settings and place of the shape selected first", async () => {
    setLayout([fill("a"), fill("b", { thread: BLUE, params: { spacing_mm: 0.3 } as never })]);
    h.call = async () => ({ geometry: { outline: sq(0, 0, 30) } });
    useStore.getState().setSelection("b", ["a"]);
    await mergeSelected();
    const items = h.layout!.items as ObjectItem[];
    expect(items).toHaveLength(1);
    expect(items[0].id).toBe("b");
    expect(items[0].thread).toEqual(BLUE);
    expect(useStore.getState().selectedId).toBe("b");
  });
});

describe("Outline / offset", () => {
  it("says to come closer to 0 when an inset leaves nothing", async () => {
    setLayout([fill("a")]);
    h.call = async () => ({ rings: [] });
    useStore.getState().select("a");
    await addOffset({ distance_mm: -15, as: "run", width_mm: 2, holes: false });
    expect(h.messages.at(-1)?.text).toMatch(/smaller inset/);
    await addOffset({ distance_mm: 40, as: "run", width_mm: 2, holes: false });
    expect(h.messages.at(-1)?.text).toMatch(/bigger one/);
  });
});

describe("Print: thread colours", () => {
  it("only lets a plain #hex colour into the page", () => {
    expect(safeColor("#AbC")).toBe("#AbC");
    expect(safeColor("#112233")).toBe("#112233");
    expect(safeColor('#fff" onload="x')).toBe("#808080");
    expect(safeColor("red;}</style><script>")).toBe("#808080");
    expect(safeColor(undefined)).toBe("#808080");
    const html = printHtml(
      {
        path: "x.pes",
        name: "x",
        format: "pes",
        info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
        threads: [{ color: "red;}</style><script>alert(1)</script>", name: "", brand: "", catalog: "" }],
        blocks: [{ thread: 0, start: 0, end: 1 }],
        records: { x: [0], y: [0], kind: [0] },
      } as never,
      null,
      null,
    );
    expect(html).not.toMatch(/<script>/);
  });
});

describe("Thread list: stitching LUDD adds", () => {
  it("tells the basting box and knockdown apart", async () => {
    const { addedStitching } = await import("./components/InfoPanel");
    const both = { basting: { enabled: true, margin_mm: 5 }, knockdown: { enabled: true, margin_mm: 2 } } as unknown as Layout;
    expect(addedStitching(both, {}, 0)).toBe("basting");
    expect(addedStitching(both, { sources: [] }, 1)).toBe("knockdown");
    expect(addedStitching(both, { sources: [{ item: 0, block: 0 }] }, 2)).toBeNull();
    const knockdownOnly = { basting: { enabled: false, margin_mm: 5 }, knockdown: { enabled: true, margin_mm: 2 } } as unknown as Layout;
    expect(addedStitching(knockdownOnly, {}, 0)).toBe("knockdown");
  });
});
