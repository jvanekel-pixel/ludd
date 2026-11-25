/**
 * Regression tests for the layout/export QA findings (phase 4): stitch-edit moves and Delete,
 * and "One file per name" reporting. Uses a fake engine; no browser needed.
 */
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import * as F from "./features";
import { newDoc } from "./design/layout";
import type { LayoutItem } from "./design/types";
import { useStore } from "./store";

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const file = (id: string): LayoutItem => ({ id, kind: "file", path: "C:/d/x.pes", transform: IDENT, threads: [], ops: [] }) as unknown as LayoutItem;
const text = (id: string): LayoutItem =>
  ({ id, kind: "text", text: "Emma", font: { path: "f.ttf", index: 0 }, size_mm: 10, style: "satin", thread: { color: "#000000", name: "", brand: "", catalog: "" }, transform: IDENT, threads: [], ops: [] }) as unknown as LayoutItem;

function engine(onExport?: (dest: string) => string) {
  const calls: { method: string; params: Record<string, unknown> }[] = [];
  return {
    calls,
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      calls.push({ method, params });
      if (method === "layout.render") {
        const layout = params.layout as { items: LayoutItem[] };
        return {
          path: "", name: "x", format: "layout",
          info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1, bounds_mm: [0, 0, 1, 1] },
          threads: [], blocks: [], records: { x: [], y: [], kind: [] },
          items: layout.items.map((it) => ({ id: it.id, name: it.id, kind: "file", center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null })),
        } as T;
      }
      if (method === "layout.export") return { path: onExport!(params.dest as string), stops_added: 0, warnings: [] } as T;
      return null as T;
    },
  };
}

function setDoc(e: ReturnType<typeof engine>, ...items: LayoutItem[]) {
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items } };
  useStore.setState({ engine: e as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], stitchEdit: null, design: null, notice: null } as never);
}

const items = () => useStore.getState().history.present!.layout.items;

describe("stitch editing", () => {
  it("one drag of many stitches is one op", async () => {
    setDoc(engine(), file("f"));
    useStore.setState({ stitchEdit: { id: "f", selected: [3, 4, 5] } } as never);
    F.moveSelectedStitches(1, 2);
    await A.whenIdle();
    expect(items()[0].ops).toEqual([{ op: "move_stitches", indices: [3, 4, 5], dx_mm: 1, dy_mm: 2, local: true }]);
  });

  it("says which stitches can't be picked once Rebuild or Limit density remade some", () => {
    for (const op of ["rebuild", "density_limit", "filter_small"] as const) {
      const it = { ...file("f"), ops: [op === "filter_small" ? { op, min_mm: 0.4 } : { op }] } as LayoutItem;
      setDoc(engine(), it);
      useStore.setState({ selectedId: "f" } as never);
      F.startStitchEdit();
      const said = useStore.getState().notice?.text ?? "";
      expect(said).toMatch(/^Editing stitches/);
      expect(said.includes("can't be picked"), op).toBe(op !== "filter_small");
      F.endStitchEdit();
    }
  });

  it("Delete with no stitch selected is taken by stitch editing, so it never deletes the design", () => {
    setDoc(engine(), file("f"));
    useStore.setState({ selectedId: "f", stitchEdit: { id: "f", selected: [] } } as never);
    const del = A.COMMANDS.find((c) => c.id === "stitch.deleteSelected")!;
    expect(del.enabled?.()).toBe(true);
    del.run();
    expect(items()).toHaveLength(1);
  });
});

describe("one file per name", () => {
  it("saves the others when one name fails, and says which", async () => {
    const taken = new Set<string>();
    setDoc(
      engine((dest) => {
        if (dest.includes("Bad")) throw new Error("Couldn't write Bad.pes");
        let p = dest;
        for (let n = 1; taken.has(p.toLowerCase()); n++) p = dest.replace(/\.pes$/, ` (${n}).pes`);
        taken.add(p.toLowerCase());
        return p;
      }),
      text("t"),
    );
    useStore.getState().select("t");
    await F.exportNames(["Emma", "Bad", "Emma"], "C:\\out", "pes");
    const notice = JSON.stringify(useStore.getState().notice ?? "");
    expect(notice).toContain("Saved 2 of 3");
    expect(notice).toContain('\\"Bad\\"');
    expect(notice).toContain("Emma (1).pes");
  });
});
