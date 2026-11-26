// @vitest-environment jsdom
/** A Blend sews no cross-hatch underlay, and its panel offers none to turn off, so one set while
 *  the shape had another pattern (or suggested for it) is dropped rather than silently ignored. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { defaultsFor, setObjectParams, whenIdle } from "../actions";
import { withChange } from "../ai";
import { savePrefs } from "../prefs";
import { useStore } from "../store";
import { fillPatternDef } from "./fillPatterns";
import { newDoc } from "./layout";
import type { LayoutItem, ObjectItem } from "./types";

const fill = (id: string, params: object): ObjectItem =>
  ({
    id,
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"]] },
    params,
    thread: { color: "#111111", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as unknown as ObjectItem;

/** Answers a render with nothing sewn. */
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] },
      items: items.map((it) => ({ id: it.id, name: it.id, kind: it.kind, center_mm: [0, 0], bounds_mm: null, source_size_mm: null })) } as T;
  },
};

const underlay = (id: string) =>
  (useStore.getState().history.present!.layout.items.find((it) => it.id === id) as ObjectItem).params as { underlay?: string[] };

beforeEach(async () => {
  await whenIdle();
  localStorage.clear();
  const blank = newDoc();
  const items = [fill("a", { underlay: ["edge", "tatami"] }), fill("b", { underlay: ["tatami"] }), fill("c", { underlay: ["edge", "tatami"] })];
  const doc = { ...blank, layout: { ...blank.layout, items } };
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, selectedId: null, extraIds: [] });
});
afterEach(async () => {
  await whenIdle();
  localStorage.clear();
});

describe("a Blend keeps no cross-hatch underlay it can't sew", () => {
  it("drops it when the pattern becomes Blend in the panel, keeping the rest", async () => {
    for (const id of ["a", "b"]) {
      const item = useStore.getState().history.present!.layout.items.find((it) => it.id === id) as ObjectItem;
      setObjectParams(id, { pattern: "blend", ...fillPatternDef("blend").onChoose?.(item) });
      await whenIdle();
    }
    expect(underlay("a").underlay).toEqual(["edge"]);
    expect(underlay("b").underlay).toBeUndefined(); // only the cross-hatch: back to Auto
    // Other patterns keep theirs.
    setObjectParams("c", { pattern: "wave" });
    await whenIdle();
    expect(underlay("c").underlay).toEqual(["edge", "tatami"]);
  });

  it("leaves it out of new fills that start with your Blend settings", () => {
    savePrefs({ objectDefaults: { fill: { pattern: "blend", underlay: ["tatami", "edge"] } } });
    expect(defaultsFor("fill").underlay).toEqual(["edge"]);
    savePrefs({ objectDefaults: { fill: { underlay: ["tatami", "edge"] } } });
    expect(defaultsFor("fill").underlay).toEqual(["tatami", "edge"]);
  });

  it("leaves it out of the Stitch Advisor's underlay on a Blend", () => {
    const params = (o: ObjectItem) => o.params as { underlay?: string[] };
    expect(params(withChange(fill("a", { pattern: "blend" }), { underlay: "normal" })).underlay).toEqual(["edge"]);
    expect(params(withChange(fill("a", {}), { underlay: "normal" })).underlay).toEqual(["edge", "tatami"]);
  });
});
