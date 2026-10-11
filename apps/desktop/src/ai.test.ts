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

  it("reorders only the advised shapes, in their own places", () => {
    let l = newLayout();
    for (const n of ["a", "b", "c"]) l = addObject(l, { kind: "run", geometry: { nodes: [] }, params: {}, thread, name: n } as never).layout;
    const [a, b, c] = l.items.map((it) => it.id);
    const out = withOrder(l, [c, a]);
    expect(out.items.map((it) => it.id)).toEqual([c, b, a]);
  });
});
