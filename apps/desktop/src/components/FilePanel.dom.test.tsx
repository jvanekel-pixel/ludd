// @vitest-environment jsdom
/** The stitch file panel's Repair fold (P4-B1), with the real tiny-stitch and needle-clump repairs
 *  (P4-B2, P4-B3) and a fake engine. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import type { Design, FileItem, Layout, LayoutItemInfo, LayoutOp } from "../design/types";
import { DialogHost } from "../dialogs";
import { letGoNewest } from "../escape";
import { repairStep, repairSteps, type RepairPreview, type Stats } from "../feat/repair/steps";
import { loadPrefs } from "../prefs";
import { selectLayout, useStore } from "../store";
import { FileSections } from "./FilePanel";

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

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const file = (ops: LayoutOp[] = [], scale = 1): FileItem => ({ id: "f", kind: "file", path: "C:/d/f.pes", transform: { ...IDENT, scale_x: scale, scale_y: scale }, threads: [], ops });
const info: LayoutItemInfo = { id: "f", name: "f.pes", kind: "file", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: [10, 10] };

const statsFor = (ops: LayoutOp[]): Stats => {
  const tiny = ops.some((o) => o.op === "filter_small");
  const clumps = ops.some((o) => o.op === "declump");
  return { stitches: 500 - (tiny ? 212 : 0) - (clumps ? 25 : 0), trims: 1, jumps: 1, tiny: tiny ? 0 : 212, longest_mm: 4, densest: 3, hits_max: clumps ? 5 : 11 };
};

const previews: LayoutOp[][] = [];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "repair.preview") {
      const p = params as { layout: Layout; item_id: string; ops: LayoutOp[] };
      previews.push(p.ops);
      const now = (p.layout.items.find((it) => it.id === p.item_id) as FileItem).ops;
      return { before: statsFor(now), after: statsFor(p.ops), removed: [], added: 0, limit: 7, notes: [] } satisfies RepairPreview as T;
    }
    if (method !== "layout.render") return null as T;
    const items = (params.layout as Layout).items;
    return {
      path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [], item: [], src: [] },
      items: items.map((it) => ({ ...info, id: it.id })),
    } as unknown as Design as T;
  },
};

let root: Root | null = null;
let host: HTMLElement | null = null;

/** The panel as it follows the design: the item as the layout has it now. */
function Panel() {
  const item = useStore((s) => selectLayout(s)?.items[0]) as FileItem;
  return (
    <>
      <FileSections item={item} info={info} sel="file" />
      <DialogHost />
    </>
  );
}

async function show(item: FileItem) {
  const d = newDoc();
  const present = { ...d, layout: { ...d.layout, items: [item] } };
  useStore.setState({ engine: engine as never, history: { past: [], present, future: [] }, savedDoc: present, selectedId: "f", extraIds: [], design: { items: [info] } as Design, dialog: null, notice: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(<Panel />));
}

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  previews.length = 0;
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
});

const ops = () => (useStore.getState().history.present!.layout.items[0] as FileItem).ops;
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent!.trim() === label)!;
const fold = () => [...host!.querySelectorAll<HTMLButtonElement>(".acc-sub-head")].find((b) => b.textContent!.startsWith("Repair"))!;
const lines = () => [...host!.querySelectorAll(".repair-list li span")].map((s) => s.textContent);

const pause = (ms = 380) => act(async () => {
  await new Promise((r) => setTimeout(r, ms));
  await whenIdle();
});

async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await whenIdle();
    await new Promise((r) => setTimeout(r, 0));
  });
}

describe("the stitch file panel's Repair fold", () => {
  it("file panel lists active repairs and removes one", async () => {
    await show(file([{ op: "delete_block", block: 1 }, { op: "filter_small", min_mm: 0.4 }, { op: "declump", max_hits: 5 }]));
    expect(fold().textContent).toContain("2 on");
    await pause();
    expect(previews).toEqual([]); // nothing is worked out while it's folded away
    await click(fold());
    await pause();
    expect(lines()).toEqual(["212 tiny stitches removed", "25 stitches taken out of crowded spots (most needle hits in one spot: 11 → 5)"]);
    await click(host!.querySelector<HTMLButtonElement>('button[aria-label="Turn off Remove tiny stitches"]')!);
    expect(ops()).toEqual([{ op: "delete_block", block: 1 }, { op: "declump", max_hits: 5 }]);
    expect(useStore.getState().history.past).toHaveLength(1);
    expect(useStore.getState().notice?.text).toMatch(/Remove tiny stitches: off/);
    await pause();
    expect(lines()).toEqual(["25 stitches taken out of crowded spots (most needle hits in one spot: 11 → 5)"]);
  });

  it("has the Repair button even with nothing on", async () => {
    await show(file());
    expect(fold().textContent).toBe("Repair");
    await click(fold());
    expect(lines()).toEqual([]);
    await click(button("Repair this design…"));
    expect(useStore.getState().dialog).toBe("repair");
    expect(host!.querySelector("dialog")?.open).toBe(true);
    await click(button("Cancel"));
  });

  it("stops saying a resized file may stitch too dense once it's rebuilt", async () => {
    await show(file([], 1.5));
    const note = () => host!.querySelector(".scale-note")!;
    expect(note().textContent).toContain("may stitch too dense or too sparse");
    expect(note().classList.contains("warn")).toBe(true);
    act(() => root!.unmount());
    host!.remove();
    await show(file([{ op: "rebuild" }], 1.5));
    expect(note().textContent).toBe("150% of original");
    expect(note().classList.contains("warn")).toBe(false);
  });
});

describe("the clean-up repairs (P4-B2, P4-B3)", () => {
  it("are registered with the spec's settings, unticked to start, and Fix it can name them", () => {
    const [tiny, clumps] = ["filter_small", "declump"].map((id) => repairStep(id)!);
    expect(repairSteps().map((s) => s.id)).toEqual(expect.arrayContaining(["filter_small", "declump"]));
    expect(tiny.fields).toMatchObject([{ key: "min_mm", label: "Shorter than", def: 0.4, min: 0.2, max: 1, step: 0.05 }]);
    expect(clumps.fields).toMatchObject([{ key: "max_hits", label: "Most needle hits in one spot", def: 5, min: 3, max: 10, step: 1 }]);
    expect([tiny, clumps].map((s) => [s.op, s.label, s.visible(file(), info), s.preset(file(), info)])).toEqual([
      ["filter_small", "Remove tiny stitches", true, false],
      ["declump", "Thin out dense spots", true, false],
    ]);
    expect(tiny.make({ min_mm: 0.5 })).toEqual({ op: "filter_small", min_mm: 0.5 });
    expect(clumps.make({ max_hits: 6 })).toEqual({ op: "declump", max_hits: 6 });
    expect(tiny.summary(statsFor([]), statsFor([]))).toBe("No stitches that short");
    expect(clumps.summary(statsFor([]), statsFor([]))).toBe("Nothing to thin out (most needle hits in one spot: 11)");
    const one = { ...statsFor([]), stitches: 499 };
    expect(tiny.summary(one, statsFor([]))).toBe("1 tiny stitch removed");
  });

  it("their commands turn them on with the standard settings, saying what happened", async () => {
    await show(file());
    await act(async () => {
      command("stitch.filterSmall").run();
      await new Promise((r) => setTimeout(r, 10));
      await whenIdle();
    });
    expect(ops()).toEqual([{ op: "filter_small", min_mm: 0.4 }]);
    expect(useStore.getState().notice?.text).toBe("Remove tiny stitches: on, 212 tiny stitches removed. Ctrl+Z undoes it.");
    await act(async () => {
      command("stitch.declump").run();
      await new Promise((r) => setTimeout(r, 10));
      await whenIdle();
    });
    expect(ops()).toEqual([{ op: "filter_small", min_mm: 0.4 }, { op: "declump", max_hits: 5 }]);
    await act(async () => {
      command("stitch.declump").run();
      await new Promise((r) => setTimeout(r, 10));
      await whenIdle();
    });
    expect(ops()).toEqual([{ op: "filter_small", min_mm: 0.4 }]);
    expect(useStore.getState().notice?.text).toBe("Thin out dense spots: off. Ctrl+Z undoes it.");
  });

  it("the needle path view is a switch, remembered", () => {
    useStore.setState({ showWire: false, design: { items: [info] } as Design });
    command("view.wireframe").run();
    expect(useStore.getState().showWire).toBe(true);
    expect(loadPrefs().showWire).toBe(true);
    command("view.wireframe").run();
    expect(useStore.getState().showWire).toBe(false);
  });
});
