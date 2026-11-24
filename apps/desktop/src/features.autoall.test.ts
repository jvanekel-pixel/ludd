/** Whole-picture auto-digitize (features.ts digitizeWholePicture / acceptWholePicture): stale
 *  answers, dismissing while it works, an empty result, and one Ctrl+Z for everything added. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import * as F from "./features";
import { newDoc } from "./design/layout";
import type { Doc, LayoutItem, RefImage } from "./design/types";
import { heldCount, letGoNewest } from "./escape";
import { useStore, type TracedShape } from "./store";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const sq = (x: number, y: number, w: number) => [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]] as never;

/** Each "trace.digitize_all" call takes the next planned answer (after its delay). */
function fakeEngine(plan: { delay: number; shapes: TracedShape[] }[]) {
  let n = 0;
  return {
    async call<R>(method: string, params: Record<string, unknown> = {}): Promise<R> {
      if (method === "trace.digitize_all") {
        const p = plan[n++] ?? { delay: 0, shapes: [] };
        await sleep(p.delay);
        return { shapes: p.shapes } as R;
      }
      if (method === "layout.render") {
        const layout = params.layout as { items: LayoutItem[] };
        return {
          path: "", name: "x", format: "layout",
          info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 },
          threads: [], blocks: [], records: { x: [], y: [], kind: [] },
          items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })),
        } as R;
      }
      return null as R;
    },
  };
}

const pic: RefImage = { id: "im", name: "im", path: "C:/p.png", data_url: "", x: 0, y: 0, width_mm: 100, height_mm: 100, rotate: 0, opacity: 1, locked: false, visible: true };
const fillShape = (x: number, color = "#ff0000"): TracedShape => ({ kind: "fill", outline: sq(x, 0, 10), holes: [], color });
const A1 = [fillShape(0)];
const B2 = [fillShape(20, "#00ff00"), { kind: "run", nodes: sq(40, 0, 10), closed: true, color: "#000000" } as TracedShape];

function setDoc(engine: ReturnType<typeof fakeEngine>) {
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, items: [] }, images: [pic] };
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc,
    selectedId: null, extraIds: [], notice: null, tool: "select", pen: null, autoTrace: null, autoAll: null, design: null,
  });
}
const items = () => useStore.getState().history.present!.layout.items;

beforeEach(async () => {
  await A.whenIdle();
  while (letGoNewest());
});

describe("whole-picture auto-digitize", () => {
  it("two runs at once: only the newest answer is shown (slow first run)", async () => {
    setDoc(fakeEngine([{ delay: 40, shapes: A1 }, { delay: 5, shapes: B2 }]));
    const p1 = F.digitizeWholePicture();
    const p2 = F.digitizeWholePicture({ outlines: false });
    await Promise.all([p1, p2]);
    const a = useStore.getState().autoAll!;
    expect(a.busy).toBe(false);
    expect(a.shapes).toEqual(B2);
    expect(a.outlines).toBe(false);
  });

  it("two runs at once: only the newest answer is shown (slow second run)", async () => {
    setDoc(fakeEngine([{ delay: 5, shapes: A1 }, { delay: 40, shapes: B2 }]));
    const p1 = F.digitizeWholePicture();
    const p2 = F.digitizeWholePicture();
    await p1;
    expect(useStore.getState().autoAll?.busy).toBe(true); // the older answer isn't shown
    await p2;
    expect(useStore.getState().autoAll?.shapes).toEqual(B2);
  });

  it("dismissed (Esc) while working: the answer doesn't bring it back", async () => {
    setDoc(fakeEngine([{ delay: 30, shapes: A1 }]));
    const p = F.digitizeWholePicture();
    expect(heldCount()).toBe(1);
    letGoNewest(); // Esc
    expect(useStore.getState().autoAll).toBeNull();
    await p;
    expect(useStore.getState().autoAll).toBeNull();
    expect(heldCount()).toBe(0);
  });

  it("nothing found: a message, and no preview left", async () => {
    setDoc(fakeEngine([{ delay: 0, shapes: [] }]));
    await F.digitizeWholePicture();
    expect(useStore.getState().autoAll).toBeNull();
    expect(useStore.getState().notice?.text).toMatch(/Couldn't find shapes/);
    expect(heldCount()).toBe(0);
  });

  it("accept adds every shape, and one Ctrl+Z takes them all away", async () => {
    setDoc(fakeEngine([{ delay: 0, shapes: B2 }]));
    await F.digitizeWholePicture();
    await F.acceptWholePicture();
    await A.whenIdle();
    expect(useStore.getState().autoAll).toBeNull();
    expect(items().map((it) => it.kind)).toEqual(["fill", "run"]);
    A.undoEdit();
    await A.whenIdle();
    expect(items()).toHaveLength(0);
    expect(useStore.getState().history.present!.images).toHaveLength(1);
  });
});
