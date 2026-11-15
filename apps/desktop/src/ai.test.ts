import { describe, expect, it } from "vitest";
import { applicable, withChange, withOrder } from "./ai";
import { addObject, newLayout } from "./design/layout";
import type { ObjectItem } from "./design/types";

const thread = { color: "#000", name: "", catalog: "", brand: "" };
const fill = (): ObjectItem => {
  const { layout } = addObject(newLayout(), { kind: "fill", geometry: { outline: [[0, 0, "c"], [9, 0, "c"], [9, 9, "c"]] }, params: { angle_deg: 45 }, thread });
  return layout.items[0] as ObjectItem;
};

describe("Stitch Advisor proposals", () => {
  it("applies an angle, density and underlay to a fill", () => {
    const o = withChange(fill(), { angle_deg: 120, density: "dense", underlay: "light" });
    expect(o.params).toMatchObject({ angle_deg: 120, spacing_mm: 0.33, underlay: ["edge"] });
  });

  it("turns a fill into a line and keeps its outline", () => {
    const o = withChange(fill(), { stitch_type: "run" });
    expect(o.kind).toBe("run");
    expect((o as Extract<ObjectItem, { kind: "run" }>).geometry).toMatchObject({ closed: true, nodes: [[0, 0, "c"], [9, 0, "c"], [9, 9, "c"]] });
  });

  it("can't switch a fill into a satin (that needs two rails), so leaves it alone", () => {
    const f = fill();
    expect(applicable(f, { stitch_type: "satin" })).toBe(false);
    expect(withChange(f, { stitch_type: "satin" }).kind).toBe("fill");
  });

  it("QA C10: swaps a satin ribbon and a line, and adjusts a ribbon's density", () => {
    const { layout } = addObject(newLayout(), { kind: "satin", geometry: { nodes: [[0, 0, "c"], [20, 0, "c"]], width_mm: 3 }, params: {}, thread } as never);
    const r = layout.items[0] as ObjectItem;
    expect(applicable(r, { stitch_type: "run" })).toBe(true);
    expect(applicable(r, { stitch_type: "fill" })).toBe(false);
    const line = withChange(r, { stitch_type: "run" });
    expect(line.kind).toBe("run");
    expect((line as Extract<ObjectItem, { kind: "run" }>).geometry.nodes).toHaveLength(2);
    expect(withChange(line, { stitch_type: "satin" }).geometry).toMatchObject({ nodes: [[0, 0, "c"], [20, 0, "c"]] });
    expect(withChange(r, { density: "dense" }).params).toMatchObject({ spacing_mm: 0.33 });
  });

  it("reorders only the advised shapes, in their own places", () => {
    let l = newLayout();
    for (const n of ["a", "b", "c"]) l = addObject(l, { kind: "run", geometry: { nodes: [] }, params: {}, thread, name: n } as never).layout;
    const [a, b, c] = l.items.map((it) => it.id);
    const out = withOrder(l, [c, a]);
    expect(out.items.map((it) => it.id)).toEqual([c, b, a]);
  });
});
