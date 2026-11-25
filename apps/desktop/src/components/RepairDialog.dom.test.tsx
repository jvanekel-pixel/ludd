// @vitest-environment jsdom
/** "Repair this design" (P4-B1) with stand-in repair steps and a fake engine, so it works with
 *  whatever repairs are registered; its red highlight on the design; and "Fix it" on a check. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import type { Graphics } from "pixi.js";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { whenIdle } from "../actions";
import { drawOverlays } from "../canvas/hooks";
import { newDoc } from "../design/layout";
import type { CheckResult, Design, FileItem, Layout, LayoutOp, QualityCheck } from "../design/types";
import { DialogHost, registerDialog } from "../dialogs";
import { heldCount, letGoNewest } from "../escape";
import { fixFor, openRepair, registerRepairStep, type RepairPreview, type RepairStep, type Stats } from "../feat/repair/steps";
import { useStore } from "../store";
import { Checks } from "./QualityPanel";
import { RepairDialog, useRepairHighlight } from "./RepairDialog";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

registerDialog("repair", RepairDialog);

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

// ---------------------------------------------------------------- a fake engine

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const file = (id: string, ops: LayoutOp[] = []): FileItem => ({ id, kind: "file", path: `C:/d/${id}.pes`, transform: IDENT, threads: [], ops });

/** Each repair takes some stitches away, so a stand-in step can count its own. */
const TAKES: Record<string, number> = { rebuild: 1, filter_small: 10, declump: 5, density_limit: 3 };
const statsFor = (ops: LayoutOp[]): Stats => ({
  stitches: 100 - ops.reduce((n, o) => n + (TAKES[o.op] ?? 0), 0),
  trims: 2,
  jumps: 3,
  tiny: ops.some((o) => o.op === "filter_small") ? 0 : 12,
  longest_mm: 6.8,
  densest: ops.some((o) => o.op === "density_limit") ? 6.1 : 8.4,
  hits_max: ops.some((o) => o.op === "declump") ? 5 : 11,
});

const asked: { layout: Layout; item_id: string; ops: LayoutOp[] }[] = [];
let previewFails: string | null = null;

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method === "repair.preview") {
      const p = params as { layout: Layout; item_id: string; ops: LayoutOp[] };
      asked.push(p);
      if (previewFails) throw new Error(previewFails);
      const now = (p.layout.items.find((it) => it.id === p.item_id) as FileItem).ops;
      const answer: RepairPreview = {
        before: statsFor(now),
        after: statsFor(p.ops),
        removed: p.ops.some((o) => o.op === "filter_small") ? [[1, 3]] : [],
        added: 0,
        limit: 7,
        notes: p.ops.some((o) => o.op === "declump") ? ["Thinning stopped at 15% of the stitches."] : [],
      };
      return answer as T;
    }
    if (method !== "layout.render") return null as T;
    return render((params.layout as Layout).items as FileItem[]) as T;
  },
};

/** Each file: five stitches along y = its row, numbered 0..4, in a 10 x 10 mm box 20 mm apart. */
function render(items: FileItem[]): Design {
  const rec = { x: [] as number[], y: [] as number[], kind: [] as number[], item: [] as number[], src: [] as number[] };
  items.forEach((_, i) => {
    for (let n = 0; n < 5; n++) {
      rec.x.push(i * 20 + n * 2);
      rec.y.push(5);
      rec.kind.push(0);
      rec.item.push(i);
      rec.src.push(n);
    }
  });
  return {
    path: "", name: "x", format: "layout",
    info: { stitches: rec.x.length, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
    threads: [], blocks: [], records: rec as Design["records"],
    items: items.map((it, i) => ({ id: it.id, name: `${it.id}.pes`, kind: "file", center_mm: [i * 20 + 5, 5], bounds_mm: [i * 20, 0, i * 20 + 10, 10], source_size_mm: [10, 10] })),
  };
}

// ---------------------------------------------------------------- stand-in steps

const step = (op: LayoutOp["op"], label: string, over: Partial<RepairStep> = {}): RepairStep => ({
  id: op,
  op,
  label,
  hint: `About ${label}`,
  visible: () => true,
  preset: () => false,
  make: (v) => ({ op, ...v }) as LayoutOp,
  fields: [],
  summary: (after, before) => `${label}: ${before.stitches - after.stitches} gone`,
  ...over,
});

const STEPS = () => [
  step("density_limit", "Density"),
  step("declump", "Clumps", { fields: [{ key: "max_hits", label: "Most hits", def: 5, min: 3, max: 10, step: 1, digits: 0 }] }),
  step("filter_small", "Tiny", { fields: [{ key: "min_mm", label: "Shorter than", def: 0.4, min: 0.2, max: 1, step: 0.05, suffix: "mm" }] }),
  step("rebuild", "Rebuild"),
  step("remove_hidden", "Hidden", { visible: () => false }),
];

// ---------------------------------------------------------------- the page

let root: Root | null = null;
let host: HTMLElement | null = null;
let unregister: (() => void)[] = [];

const doc = () => useStore.getState().history.present!;
const ops = (i = 0) => (doc().layout.items[i] as FileItem).ops;
const past = () => useStore.getState().history.past.length;

async function show(items: FileItem[], extra: { checks?: CheckResult | null } = {}) {
  const d = newDoc();
  const layout = { ...d.layout, items };
  const present = { ...d, layout };
  useStore.setState({
    engine: engine as never, history: { past: [], present, future: [] }, savedDoc: present, design: render(items),
    checks: extra.checks ?? null, selectedId: items[0].id, extraIds: [], dialog: null, tool: "select", pen: null, notice: null, stitchEdit: null, units: "mm",
  });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <>
        {extra.checks && <Checks sel="none" />}
        <DialogHost />
      </>,
    );
  });
}

beforeEach(async () => {
  await whenIdle();
  while (letGoNewest());
  localStorage.clear();
  asked.length = 0;
  previewFails = null;
  unregister = STEPS().map(registerRepairStep);
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  unregister.forEach((f) => f());
});

const dialog = () => host!.querySelector<HTMLDialogElement>("dialog");
const row = (label: string) => [...host!.querySelectorAll<HTMLLIElement>("dialog .repair-steps li")].find((li) => li.querySelector(".check span")!.textContent === label)!;
const tickBox = (label: string) => row(label).querySelector<HTMLInputElement>("input[type=checkbox]")!;
const setting = (label: string) => row(label).querySelector<HTMLInputElement>("input[type=number]")!;
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === label)!;
const cells = (name: string) => {
  const tr = [...host!.querySelectorAll("dialog .repair-table tbody tr")].find((r) => r.querySelector("th")!.textContent!.startsWith(name))!;
  return [...tr.querySelectorAll("td")].map((td) => td.textContent);
};

/** Long enough for the preview's 300 ms pause and its answers. */
const pause = (ms = 380) => act(async () => {
  await new Promise((r) => setTimeout(r, ms));
  await whenIdle();
});

async function open(tick?: string) {
  await act(async () => openRepair(tick));
}

async function click(el: HTMLElement) {
  await act(async () => {
    el.click();
    await whenIdle();
    await new Promise((r) => setTimeout(r, 0));
  });
}

async function press(target: EventTarget, key: string) {
  const e = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  await act(async () => {
    target.dispatchEvent(e);
    await whenIdle();
    await new Promise((r) => setTimeout(r, 0));
  });
  return e;
}

function type(input: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("the repair dialog", () => {
  it("repair dialog: Accept writes ops in the fixed order", async () => {
    await show([file("f", [{ op: "delete_block", block: 1 }])]);
    await open();
    expect(dialog()?.open).toBe(true);
    // Ticked out of order; written in the fixed one.
    await click(tickBox("Density"));
    await click(tickBox("Tiny"));
    await click(tickBox("Rebuild"));
    type(setting("Tiny"), "0.6");
    await click(button("Accept"));
    expect(dialog()).toBeNull();
    expect(ops()).toEqual([{ op: "delete_block", block: 1 }, { op: "rebuild" }, { op: "filter_small", min_mm: 0.6 }, { op: "density_limit" }]);
    expect(past()).toBe(1);
    expect(heldCount()).toBe(0);
  });

  it("repair dialog: Cancel writes nothing", async () => {
    await show([file("f")]);
    for (const how of ["Cancel", "Escape"]) {
      await open();
      expect(heldCount(), how).toBe(1);
      await click(tickBox("Tiny"));
      await pause();
      expect(cells("Stitches"), how).toEqual(["100", "90"]);
      if (how === "Cancel") await click(button("Cancel"));
      else expect((await press(setting("Tiny"), "Escape")).defaultPrevented).toBe(true);
      expect(dialog(), how).toBeNull();
      expect(ops(), how).toEqual([]);
      expect(past(), how).toBe(0);
      expect(heldCount(), how).toBe(0);
      expect(useStore.getState().dialog, how).toBeNull();
    }
  });

  it("a hidden step is not listed", async () => {
    // One that's on already stays on, though it isn't listed.
    await show([file("f", [{ op: "remove_hidden" }])]);
    await open();
    expect(dialog()!.textContent).not.toContain("Hidden");
    expect([...host!.querySelectorAll("dialog .repair-steps .check span")].map((s) => s.textContent)).toEqual(["Rebuild", "Tiny", "Clumps", "Density"]);
    await click(tickBox("Clumps"));
    await click(button("Accept"));
    expect(ops()).toEqual([{ op: "declump", max_hits: 5 }, { op: "remove_hidden" }]);
  });

  it("opens with what's on already ticked, at its setting, and the step Fix it asks for", async () => {
    await show([file("f", [{ op: "declump", max_hits: 7 }])]);
    unregister.push(registerRepairStep(step("rebuild", "Rebuild", { preset: () => true })));
    await open("filter_small");
    expect(["Rebuild", "Tiny", "Clumps", "Density"].map((l) => tickBox(l).checked)).toEqual([true, true, true, false]);
    expect(setting("Clumps").value).toBe("7");
    expect(setting("Tiny").value).toBe("0.40");
    // Settings are usable only for ticked repairs.
    expect(setting("Tiny").disabled).toBe(false);
    await click(tickBox("Tiny"));
    expect(setting("Tiny").disabled).toBe(true);
    expect(row("Tiny").textContent).toContain("About Tiny"); // unticked: what it does
  });

  it("shows before and after from the preview after a 300 ms pause, and each repair's own result", async () => {
    await show([file("f")]);
    await open();
    await pause();
    expect(cells("Stitches")).toEqual(["100", "100"]);
    asked.length = 0;
    await click(tickBox("Tiny"));
    await click(tickBox("Clumps"));
    await pause(100);
    expect(asked).toEqual([]); // not yet
    await pause();
    expect(asked.map((a) => a.ops.map((o) => o.op))).toEqual([["filter_small"], ["filter_small", "declump"]]);
    expect(row("Tiny").textContent).toContain("Tiny: 10 gone");
    expect(row("Clumps").textContent).toContain("Clumps: 5 gone");
    expect(cells("Stitches")).toEqual(["100", "85"]);
    expect(cells("Trims")).toEqual(["2", "2"]);
    expect(cells("Tiny stitches")).toEqual(["12", "0"]);
    expect(cells("Longest stitch")).toEqual(["6.8 mm", "6.8 mm"]);
    expect(cells("Densest spot")).toEqual(["8.4", "8.4"]);
    expect(dialog()!.textContent).toContain("7"); // the limit
    expect(host!.querySelectorAll("dialog .repair-table td.over")).toHaveLength(2);
    expect(dialog()!.textContent).toContain("Thinning stopped at 15%");
    await click(tickBox("Density"));
    await pause();
    expect(cells("Densest spot")).toEqual(["8.4", "6.1"]);
    expect(host!.querySelectorAll("dialog .repair-table td.over")).toHaveLength(1);
  });

  it("counts a repair that's on already against the file without repairs", async () => {
    await show([file("f", [{ op: "filter_small", min_mm: 0.4 }])]);
    await open();
    await pause();
    expect(row("Tiny").textContent).toContain("Tiny: 10 gone");
    expect(cells("Stitches")).toEqual(["90", "90"]); // the table: now, and after Accept
  });

  it("holds each setting to its range and its digits, and to the standard value when empty", async () => {
    for (const [typed, hits] of [["5.6", 6], ["99", 10], ["1", 3], ["", 5], ["x", 5]] as const) {
      await show([file("f")]);
      await open("declump");
      type(setting("Clumps"), typed);
      await click(button("Accept"));
      expect(ops(), typed).toEqual([{ op: "declump", max_hits: hits }]);
      act(() => root!.unmount());
      host!.remove();
    }
    await show([file("f")]);
    await open("filter_small");
    type(setting("Tiny"), "7");
    act(() => {
      setting("Tiny").focus();
      setting("Tiny").blur();
    });
    expect(setting("Tiny").value).toBe("1.00");
  });

  it("shows why when the preview can't be made, and Accept waits", async () => {
    await show([file("f")]);
    previewFails = "There are no stitches left: everything was deleted";
    await open();
    await pause();
    expect(dialog()!.textContent).toContain("There are no stitches left");
    expect(button("Accept").disabled).toBe(true);
    expect(button("Cancel").disabled).toBe(false);
  });

  it("Enter accepts, but not from a button", async () => {
    await show([file("f")]);
    await open("declump");
    expect((await press(button("Cancel"), "Enter")).defaultPrevented).toBe(false);
    expect(dialog()?.open).toBe(true);
    expect((await press(setting("Clumps"), "Enter")).defaultPrevented).toBe(true);
    expect(dialog()).toBeNull();
    expect(ops()).toEqual([{ op: "declump", max_hits: 5 }]);
  });

  it("asks for a stitch file when there's none to repair", async () => {
    await show([file("f")]);
    useStore.setState({ history: { past: [], present: { ...doc(), layout: { ...doc().layout, items: [] } }, future: [] }, selectedId: null });
    await open();
    expect(dialog()).toBeNull();
    expect(useStore.getState().notice?.text).toMatch(/stitch file/);
  });

  it("closes when its design is gone", async () => {
    await show([file("f"), file("g")]);
    await open();
    await act(async () => {
      const d = doc();
      useStore.setState({ history: { past: [], present: { ...d, layout: { ...d.layout, items: [d.layout.items[1]] } }, future: [] }, design: render([file("g")]) });
    });
    expect(dialog()).toBeNull();
    expect(heldCount()).toBe(0);
  });
});

// ---------------------------------------------------------------- "Show on the design"

/** What a canvas overlay drew, as a Pixi Graphics would be asked to. */
function drawn() {
  const calls: [string, ...number[]][] = [];
  const g: Record<string, (...a: unknown[]) => unknown> = {};
  for (const name of ["moveTo", "lineTo", "circle", "rect", "stroke", "fill", "beginPath", "poly", "closePath"]) {
    g[name] = (...a: unknown[]) => {
      calls.push([name, ...(a.filter((v) => typeof v === "number") as number[])]);
      return g;
    };
  }
  drawOverlays(g as unknown as Graphics, 0.1, { toMm: () => [0, 0], pxMm: () => 0.1, redraw: () => {} });
  return calls;
}

describe("Show on the design", () => {
  it("marks the stitches that would come out in red, and goes away with the dialog", async () => {
    await show([file("g"), file("f")]);
    useStore.setState({ selectedId: "f" });
    await open();
    await click(tickBox("Tiny"));
    await pause();
    expect(drawn()).toEqual([]);
    const zooms = useStore.getState().zoomRequest.n;
    await click(button("Show on the design"));
    expect(button("Show on the design").getAttribute("aria-pressed")).toBe("true");
    // The dialog moves aside so the design shows, and the view frames the design.
    expect(dialog()!.classList.contains("peek")).toBe(true);
    expect(useStore.getState().zoomRequest.n).toBe(zooms + 1);
    expect(useStore.getState().zoomRequest.kind).toBe("box");
    expect(useRepairHighlight.getState().shown).toEqual({ id: "f", ranges: [[1, 3]] });
    // Stitches 1 and 2 of the second file are at x = 22 and 24, on y = 5.
    const marks = drawn().filter(([name]) => name === "circle").map(([, x, y]) => [x, y]);
    expect(marks).toEqual([[22, 5], [24, 5]]);
    expect(drawn().some(([name, x]) => name === "lineTo" && x === 26)).toBe(true); // and the thread from them on
    // It follows the preview.
    await click(tickBox("Tiny"));
    await pause();
    expect(drawn()).toEqual([]);
    await click(tickBox("Tiny"));
    await pause();
    expect(drawn().length).toBeGreaterThan(0);
    await click(button("Show on the design"));
    expect(dialog()!.classList.contains("peek")).toBe(false);
    expect(drawn()).toEqual([]);
    await click(button("Show on the design"));
    await click(button("Cancel"));
    expect(useRepairHighlight.getState().shown).toBeNull();
    expect(drawn()).toEqual([]);
  });
});

// ---------------------------------------------------------------- Fix it

const check = (code: string, over: Partial<QualityCheck> = {}): QualityCheck => ({ level: "info", code, message: `check ${code}`, ...over });
const checks = (...list: QualityCheck[]): CheckResult => ({ checks: list, fabric: { id: "woven", name: "Woven", advice: "" } });

describe("Fix it on a check", () => {
  it("opens the dialog with that repair ticked, for the stitch file under the spot", async () => {
    await show([file("f"), file("g")], { checks: checks(check("short", { at: [25, 5] })) });
    await click(button("Fix it"));
    expect(dialog()?.open).toBe(true);
    expect(tickBox("Tiny").checked).toBe(true);
    expect(useStore.getState().selectedId).toBe("g");
    expect(dialog()!.textContent).toContain("g.pes");
  });

  it("each kind of check goes to its repair", async () => {
    await show([file("f")]);
    const layout = doc().layout;
    const design = useStore.getState().design;
    const fix = (c: QualityCheck) => fixFor(c, layout, design);
    expect(fix(check("short", { at: [5, 5] }))).toEqual({ step: "filter_small", item: "f" });
    expect(fix(check("needle_hits", { level: "warning", at: [5, 5] }))).toEqual({ step: "declump", item: "f" });
    expect(fix(check("needle_hits"))).toEqual({ step: "declump", item: "f" });
    expect(fix(check("dense", { at: [5, 5] }))).toEqual({ step: "density_limit", item: "f" });
    // Thick spots that drawn shapes take part in have no repair; nor do the other checks.
    expect(fix(check("dense", { level: "warning", at: [5, 5] }))).toBeNull();
    expect(fix(check("long"))).toBeNull();
    // Only with the repair there to offer.
    unregister.forEach((f) => f());
    unregister = [];
    expect(fix(check("short"))).toBeNull();
  });

  it("chooses the file under the spot (the one sewn last), else the only stitch file", async () => {
    // "b" is drawn over "a" (both boxes hold 5, 5) and sewn after it.
    const a = file("a");
    const b = file("b");
    await show([a, b]);
    const design = useStore.getState().design!;
    design.items![1].bounds_mm = [4, 4, 14, 14];
    const layout = doc().layout;
    expect(fixFor(check("short", { at: [5, 5] }), layout, design)?.item).toBe("b");
    expect(fixFor(check("short", { at: [1, 1] }), layout, design)?.item).toBe("a");
    // A 1 mm spot's middle can sit just outside a design's box.
    expect(fixFor(check("short", { at: [14.5, 10] }), layout, design)?.item).toBe("b");
    // Two stitch files and the spot in neither: no telling which.
    expect(fixFor(check("short", { at: [80, 80] }), layout, design)).toBeNull();
    expect(fixFor(check("short"), layout, design)).toBeNull();
    const shape = { ...a, id: "s", kind: "fill" } as unknown as FileItem;
    const one = { ...layout, items: [shape, layout.items[1]] };
    expect(fixFor(check("short", { at: [80, 80] }), one, design)?.item).toBe("b");
    expect(fixFor(check("short"), { ...layout, items: [shape] }, design)).toBeNull();
  });

  it("is only offered where it can do something", async () => {
    await show([file("f"), file("g")], { checks: checks(check("long", { at: [5, 5] }), check("short", { at: [80, 80] })) });
    expect(button("Fix it")).toBeUndefined();
    expect(host!.textContent).toContain("check short");
  });
});
