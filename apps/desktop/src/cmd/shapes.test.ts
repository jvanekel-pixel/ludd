/** The commands for the five shapes added after the rectangle, circle and star (a fake engine). */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { addShape, command, COMMANDS, whenIdle } from "../actions";
import "./shapes";
import { canvasMenu } from "../contextMenu";
import { newDoc } from "../design/layout";
import { shapeNodes, type ShapeId } from "../design/shapes";
import type { LayoutItem, ObjectItem } from "../design/types";
import { useStore } from "../store";

const RESERVED = [
  ["shape.roundedRect", "Add a rounded rectangle", "Mod+Alt+4"],
  ["shape.ellipse", "Add an oval", "Mod+Alt+5"],
  ["shape.triangle", "Add a triangle", "Mod+Alt+6"],
  ["shape.polygon", "Add a polygon", "Mod+Alt+7"],
  ["shape.heart", "Add a heart", "Mod+Alt+8"],
];

const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

const items = () => useStore.getState().history.present!.layout.items as ObjectItem[];
const outlineOf = (it: ObjectItem) => (it.geometry as { outline: unknown }).outline;
/** Wait for the edit to be sewn, and for what follows it (the new shape is selected). */
async function settled() {
  await whenIdle();
  await new Promise((r) => setTimeout(r, 0));
}

beforeEach(async () => {
  await whenIdle();
  const doc = newDoc();
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [], dialog: null, tool: "select", pen: null, notice: null });
});

describe("the new shape commands", () => {
  it("the five commands are registered with their reserved shortcuts", () => {
    expect(RESERVED.map(([id]) => [command(id)?.id, command(id)?.title, command(id)?.shortcut])).toEqual(RESERVED);
    // Nothing else answers to those keys.
    for (const [id, , key] of RESERVED) expect(COMMANDS.filter((c) => c.shortcut === key).map((c) => c.id)).toEqual([id]);
  });

  it("each adds its shape as a fill in the middle of the hoop, selected", async () => {
    for (const shape of ["roundedRect", "ellipse", "triangle", "heart"] as ShapeId[]) {
      useStore.getState().setTool("fill");
      const before = items().length;
      command(`shape.${shape}`).run();
      await settled();
      expect(items()).toHaveLength(before + 1);
      const added = items().at(-1)!;
      expect(added.kind).toBe("fill");
      // With no machine picked: 60 mm, on the hoop's middle.
      expect(outlineOf(added)).toEqual(shapeNodes(shape, 0, 0, 60));
      expect(useStore.getState().selectedId).toBe(added.id);
      expect(useStore.getState().tool).toBe("select");
    }
  });

  it("the polygon asks how many sides before it adds anything", async () => {
    command("shape.polygon").run();
    await settled();
    expect(useStore.getState().dialog).toBe("polygon");
    expect(items()).toHaveLength(0);
  });

  it("addShape makes the polygon with the number of sides asked for", async () => {
    await addShape("polygon", { sides: 9 });
    expect(outlineOf(items()[0])).toEqual(shapeNodes("polygon", 0, 0, 60, { sides: 9 }));
    expect(items()[0]).toMatchObject({ kind: "fill" });
  });

  it("they wait for the engine, like the other shapes", () => {
    useStore.setState({ engine: null });
    for (const [id] of RESERVED) expect(command(id).enabled?.(), id).toBe(false);
    useStore.setState({ engine: engine as never });
    for (const [id] of RESERVED) expect(command(id).enabled?.(), id).toBe(true);
  });

  it("the empty canvas's right-click menu offers them after the star", () => {
    const ids = canvasMenu().flatMap((it) => (typeof it === "object" && "id" in it ? [it.id] : []));
    const star = ids.indexOf("shape.star");
    expect(ids.slice(star + 1, star + 6)).toEqual(RESERVED.map(([id]) => id));
  });
});
