/** The repair contract: at most one op of each repair, written in a fixed order, and the direct
 *  commands' on and off. A fake engine; no browser. */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../../actions";
import { newDoc } from "../../design/layout";
import type { LayoutItem, LayoutOp } from "../../design/types";
import { useStore } from "../../store";
import { registerRepairStep, REPAIR_ORDER, repairSteps, toggleRepair, withRepairs, type RepairStep } from "./steps";

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const file = (ops: LayoutOp[] = []): LayoutItem => ({ id: "f", kind: "file", path: "C:/d/x.pes", transform: IDENT, threads: [], ops });
const fill = { id: "s", kind: "fill", geometry: { outline: [] }, params: {}, thread: { color: "#000000", name: "", brand: "", catalog: "" }, transform: IDENT, threads: [], ops: [] } as unknown as LayoutItem;

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return {
      path: "", name: "x", format: "layout",
      info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
      threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind ?? "file", center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null })),
    } as T;
  },
};

function setDoc(item: LayoutItem) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [item] } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: item.id, extraIds: [], notice: null });
}

const ops = () => currentLayout()!.items[0].ops;
const past = () => useStore.getState().history.past.length;

const step = (over: Partial<RepairStep> & Pick<RepairStep, "id" | "op">): RepairStep => ({
  label: over.id, hint: "", visible: () => true, preset: () => false, make: () => ({ op: over.op }) as LayoutOp, fields: [], summary: () => "", ...over,
});

beforeEach(async () => {
  await whenIdle();
});

describe("repair ops", () => {
  it("are written once each, in the fixed order, after the other edits", () => {
    const before: LayoutOp[] = [{ op: "delete_block", block: 0 }, { op: "declump" }, { op: "jumps_to_trims", min_mm: 3 }, { op: "filter_small", min_mm: 0.4 }];
    const repairs: LayoutOp[] = [{ op: "density_limit" }, { op: "declump", max_hits: 4 }, { op: "rebuild" }, { op: "declump", max_hits: 6 }, { op: "filter_small", min_mm: 0.3 }];
    expect(withRepairs(before, repairs)).toEqual([
      { op: "delete_block", block: 0 },
      { op: "jumps_to_trims", min_mm: 3 },
      { op: "rebuild" },
      { op: "filter_small", min_mm: 0.3 },
      { op: "declump", max_hits: 6 },
      { op: "density_limit" },
    ]);
    expect(REPAIR_ORDER).toEqual(["rebuild", "filter_small", "declump", "density_limit", "remove_hidden"]);
  });

  it("steps are listed in that order, however they registered", () => {
    const off = [step({ id: "t_density", op: "density_limit" }), step({ id: "t_rebuild", op: "rebuild" })].map(registerRepairStep);
    try {
      expect(repairSteps().map((s) => s.id).filter((id) => id.startsWith("t_"))).toEqual(["t_rebuild", "t_density"]);
    } finally {
      off.forEach((f) => f());
    }
    expect(repairSteps().some((s) => s.id.startsWith("t_"))).toBe(false);
  });
});

describe("a direct repair command", () => {
  const off = () =>
    registerRepairStep(
      step({
        id: "t_tiny",
        op: "filter_small",
        label: "Tiny stitches",
        fields: [{ key: "min_mm", label: "Shorter than", def: 0.4, min: 0.2, max: 1, step: 0.05 }],
        make: (v) => ({ op: "filter_small", min_mm: v.min_mm }),
      }),
    );

  it("turns the repair on with its standard value, then off, one undo step each", async () => {
    const unregister = off();
    try {
      setDoc(file([{ op: "delete_block", block: 1 }]));
      await toggleRepair("t_tiny");
      expect(ops()).toEqual([{ op: "delete_block", block: 1 }, { op: "filter_small", min_mm: 0.4 }]);
      expect(past()).toBe(1);
      expect(useStore.getState().notice?.text).toMatch(/Tiny stitches: on/);
      await toggleRepair("t_tiny");
      expect(ops()).toEqual([{ op: "delete_block", block: 1 }]);
      expect(past()).toBe(2);
      expect(useStore.getState().notice?.text).toMatch(/Tiny stitches: off/);
    } finally {
      unregister();
    }
  });

  it("asks for a stitch file when a drawn shape is selected, and changes nothing", async () => {
    const unregister = off();
    try {
      setDoc(fill);
      await toggleRepair("t_tiny");
      expect(ops()).toEqual([]);
      expect(past()).toBe(0);
      expect(useStore.getState().notice?.text).toMatch(/stitch file/);
    } finally {
      unregister();
    }
  });
});
