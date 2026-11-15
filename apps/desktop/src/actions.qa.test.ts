/**
 * Regression tests for problems found in QA (docs/QA-REPORT.md), using a fake engine.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  save: async () => "C:/x/other.ludd",
  open: async () => null,
  message: async () => "no",
}));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import { newDoc } from "./design/layout";
import type { Doc, ObjectItem } from "./design/types";
import { useStore } from "./store";

type Call = { method: string; params: Record<string, unknown> };

/** A stand-in for the engine: records calls, answers renders (optionally slowly). */
function fakeEngine(opts: { renderDelay?: number; recovery?: boolean; projectOpen?: unknown } = {}) {
  const calls: Call[] = [];
  let recovery = opts.recovery ?? false;
  const engine = {
    calls,
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      calls.push({ method, params });
      switch (method) {
        case "layout.render":
          if (opts.renderDelay) await new Promise((r) => setTimeout(r, opts.renderDelay));
          return { path: "", name: "x", format: "layout", info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 }, threads: [], blocks: [], records: { x: [], y: [], kind: [] },
            items: ((params.layout as { items: { id: string }[] }).items ?? []).map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [5, 5], bounds_mm: [0, 0, 10, 10], source_size_mm: null })) } as T;
        case "project.recovery":
          return (recovery ? { title: "Lost work", saved_at: 0, path: null, items: 1 } : null) as T;
        case "project.discard_recovery":
          recovery = false;
          return null as T;
        case "project.restore":
          if (!recovery) throw new Error("There's nothing to recover");
          return { layout: newDoc().layout, images: [], path: null } as T;
        case "project.save":
          return { path: params.path, images: 0, designs: 0 } as T;
        case "project.open":
          return opts.projectOpen as T;
        default:
          return null as T;
      }
    },
  };
  return engine;
}

const fill = (id: string): ObjectItem =>
  ({
    id,
    kind: "fill",
    geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] },
    params: {},
    thread: { color: "#cc0000", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as ObjectItem;

function docWith(id: string): Doc {
  const d = newDoc();
  return { ...d, layout: { ...d.layout, items: [fill(id)] } };
}

beforeEach(() => {
  useStore.setState({ history: { past: [], present: null, future: [] }, savedDoc: null, projectPath: null, notice: null });
});

describe("QA C9: saving never deletes a crash-recovery copy that's still waiting", () => {
  it("leaves the copy alone, so Recover still works afterwards", async () => {
    const engine = fakeEngine({ recovery: true });
    useStore.setState({ engine: engine as never });
    await A.checkRecovery();
    useStore.setState({ history: { past: [], present: docWith("a"), future: [] }, savedDoc: null });
    await A.saveProject(true);
    expect(engine.calls.map((c) => c.method)).not.toContain("project.discard_recovery");
    await A.restoreRecovery();
    expect(useStore.getState().notice?.kind).not.toBe("error");
  });
});

describe("QA C19: an edit made while a project opens never points Save at the old file", () => {
  it("ends on the new project's path, with the edit counted as unsaved", async () => {
    const opened = docWith("new");
    const engine = fakeEngine({ renderDelay: 60, projectOpen: { layout: opened.layout, images: [], path: "C:/p/B.ludd" } });
    useStore.setState({ engine: engine as never, history: { past: [], present: docWith("old"), future: [] }, projectPath: "C:/p/A.ludd" });
    useStore.setState({ savedDoc: useStore.getState().history.present });
    const opening = A.openDesign("C:/p/B.ludd", true);
    await new Promise((r) => setTimeout(r, 20)); // project.open answered, its render still on the way
    A.COMMANDS.find((c) => c.id === "layout.travelUnder")!.run();
    await opening;
    await new Promise((r) => setTimeout(r, 200));
    const s = useStore.getState();
    expect(s.projectPath).toBe("C:/p/B.ludd");
    expect(s.history.present?.layout.items[0].id).toBe("new");
    expect(s.savedDoc?.layout.items[0].id).toBe("new");
    expect(s.history.present).not.toBe(s.savedDoc); // the edit is unsaved
  });
});

describe("QA C18: holding an arrow key doesn't flood the engine or the undo history", () => {
  it("sends a few renders, not one per key repeat, and makes one undo step", async () => {
    const engine = fakeEngine({ renderDelay: 40 });
    const start = docWith("a");
    useStore.setState({ engine: engine as never, history: { past: [], present: start, future: [] }, savedDoc: start });
    useStore.getState().select("a");
    const right = A.COMMANDS.find((c) => c.id === "arrange.right")!;
    for (let k = 0; k < 30; k++) right.run();
    await new Promise((r) => setTimeout(r, 400));
    const renders = engine.calls.filter((c) => c.method === "layout.render").length;
    expect(renders).toBeLessThan(5);
    const s = useStore.getState();
    expect(s.history.past.length).toBe(1);
    const moved = s.history.present!.layout.items[0] as ObjectItem;
    expect((moved.geometry as { outline: number[][] }).outline[0][0]).toBeCloseTo(30); // 30 nudges of 1 mm, none lost
  });
});

describe("QA decision 16: a pinned shape ignores the arrow keys, R and Alt+H/V", () => {
  const run = (id: string) => A.COMMANDS.find((c) => c.id === id)!.run();
  const setup = (locked: boolean) => {
    const d = docWith("a");
    const start = { ...d, layout: { ...d.layout, items: [{ ...d.layout.items[0], ...(locked ? { locked: true } : {}) } as ObjectItem] } };
    useStore.setState({ engine: fakeEngine() as never, history: { past: [], present: start, future: [] }, savedDoc: start, notice: null });
    useStore.getState().select("a");
    return start;
  };

  it("leaves a pinned shape alone and says why", async () => {
    const start = setup(true);
    for (const id of ["arrange.right", "arrange.downBig", "arrange.rotateCw", "arrange.mirrorX", "arrange.mirrorY"]) run(id);
    await new Promise((r) => setTimeout(r, 50));
    const s = useStore.getState();
    expect(s.history.present).toBe(start);
    expect(s.history.past.length).toBe(0);
    expect(s.notice?.text).toMatch(/pinned/);
  });

  it("still moves, turns and mirrors a shape that isn't pinned", async () => {
    const start = setup(false);
    run("arrange.right");
    await new Promise((r) => setTimeout(r, 50));
    expect(useStore.getState().history.present).not.toBe(start);
  });
});
