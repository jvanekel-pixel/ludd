/** Mirroring a line whose motif sits to one side (P7-A3) swaps the side, so the teeth stay where
 *  they were on the picture: points are mirrored but their order is not. */
import { describe, expect, it } from "vitest";
import { addObject, mirror, newDoc, repeatItem } from "./layout";
import type { Layout, ObjectItem, RunParams } from "./types";

const withLine = (params: RunParams): { layout: Layout; id: string } =>
  addObject(newDoc().layout, {
    kind: "run",
    geometry: { nodes: [[0, 0, "c"], [20, 0, "c"], [20, 10, "c"]] },
    params,
    thread: { color: "#000000", name: "Black", brand: "", catalog: "" },
  } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);

const side = (layout: Layout, id: string) => ((layout.items.find((it) => it.id === id) as ObjectItem).params as RunParams).motif_side;

describe("mirroring a one-sided motif", () => {
  it("swaps left and right, and back again", () => {
    const { layout, id } = withLine({ style: "motif", motif: "blanket", motif_side: "left" });
    for (const axis of ["x", "y"] as const) {
      const once = mirror(layout, id, axis);
      expect(side(once, id)).toBe("right");
      expect(side(mirror(once, id, axis), id)).toBe("left");
    }
  });

  it("leaves a centered motif and other lines alone", () => {
    for (const params of [{ style: "motif", motif_side: "center" }, { style: "motif" }, { style: "triple" }] as RunParams[]) {
      const { layout, id } = withLine(params);
      expect(side(mirror(layout, id, "x"), id)).toBe(params.motif_side);
    }
  });

  it("gives mirrored copies from Repeat the other side", () => {
    const { layout, id } = withLine({ style: "motif", motif: "blanket", motif_side: "right" });
    const { layout: out, ids } = repeatItem(layout, id, [10, 5], [20, 10], { kind: "mirror4", gap: 5 });
    // The copies, in order: mirrored left to right, top to bottom, and both.
    expect(ids.map((i) => side(out, i))).toEqual(["left", "left", "right"]);
  });
});
