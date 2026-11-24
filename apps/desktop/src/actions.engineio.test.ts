/**
 * QA phase 4 (engine-io): project open, autosave and recovery, with a fake engine.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "./actions";
import { keySavedText, sendTitle } from "./ai";
import { newDoc } from "./design/layout";
import type { Doc, Machine, ObjectItem } from "./design/types";
import { loadPrefs } from "./prefs";
import { useStore } from "./store";

type Call = { method: string; params: Record<string, unknown> };

function fakeEngine(answers: Record<string, unknown> = {}) {
  const calls: Call[] = [];
  return {
    calls,
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      calls.push({ method, params });
      if (method === "layout.render") {
        const items = ((params.layout as { items: { id: string }[] }).items ?? []).map((it) => ({ id: it.id, name: it.id, kind: "fill", center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null }));
        return { path: "", name: "x", format: "layout", info: { stitches: 1, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 1, height_mm: 1 }, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items } as T;
      }
      return (answers[method] ?? null) as T;
    },
  };
}

const machine = (id: string, hoops: string[]): Machine =>
  ({ id, name: id, brand: "", formats: ["pes"], needles: 1, cuts: "trim", max_stitch_mm: null, max_stitches: null, max_colors: null, notes: "",
    hoops: hoops.map((h) => ({ id: h, name: h, width_mm: 100, height_mm: 100 })) }) as unknown as Machine;

function docWith(id: string): Doc {
  const d = newDoc();
  const fill = { id, kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#cc0000", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] } as unknown as ObjectItem;
  return { ...d, layout: { ...d.layout, items: [fill] } };
}

beforeEach(() => {
  useStore.setState({ history: { past: [], present: null, future: [] }, savedDoc: null, projectPath: null, notice: null });
});

describe("QA project: the crash copy can't be deleted before it's offered", () => {
  it("a design started while LUDD is still starting doesn't delete it", async () => {
    // (Runs first: the module starts out waiting for the recovery check.)
    const engine = fakeEngine();
    useStore.setState({ engine: engine as never });
    const stop = A.startAutosave();
    const doc = docWith("a");
    useStore.setState({ history: { past: [], present: doc, future: [] }, savedDoc: doc });
    stop();
    expect(engine.calls.map((c) => c.method)).not.toContain("project.discard_recovery");
    await A.checkRecovery(); // nothing to recover: autosave works normally from now on
    expect(A.isRecoveryWaiting()).toBe(false);
  });
});

describe("QA project: a project's machine is used for it, not made your default", () => {
  it("opens on the project's machine and hoop without changing the saved preference", async () => {
    const opened = docWith("p");
    const engine = fakeEngine({ "project.open": { layout: opened.layout, images: [], machine: "janome", hoop: "j2", path: "C:/p/x.ludd" } });
    useStore.setState({ engine: engine as never, machines: [machine("pe550d", ["b1"]), machine("janome", ["j1", "j2"])], machineId: "pe550d", hoopId: "b1" });
    const before = loadPrefs().machineId;
    await A.openDesign("C:/p/x.ludd", true);
    expect(useStore.getState().machineId).toBe("janome");
    expect(useStore.getState().hoopId).toBe("j2");
    expect(loadPrefs().machineId).toBe(before);
  });
});

describe("QA project: autosave sends pictures by path, with the hoop", () => {
  it("leaves out the picture bytes", async () => {
    vi.useFakeTimers();
    try {
      const engine = fakeEngine();
      useStore.setState({ engine: engine as never, machines: [machine("pe550d", ["b1"])], machineId: "pe550d", hoopId: "b1" });
      await A.checkRecovery();
      const stop = A.startAutosave();
      const doc = docWith("a");
      const image = { id: "i", name: "p.png", path: "C:/p.png", data_url: "data:image/png;base64,AAAA", x: 0, y: 0, width_mm: 10, height_mm: 10, rotate: 0, opacity: 1, locked: false, visible: true };
      useStore.setState({ history: { past: [], present: { ...doc, images: [image] }, future: [] }, savedDoc: null });
      await vi.advanceTimersByTimeAsync(5000);
      stop();
      const sent = engine.calls.find((c) => c.method === "project.autosave")?.params.project_data as { images: { data_url?: string; path: string }[]; hoop: string };
      expect(sent.images[0].path).toBe("C:/p.png");
      expect(sent.images[0].data_url).toBeUndefined();
      expect(sent.hoop).toBe("b1");
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("QA security: AI wording", () => {
  it("names where things are sent, and says how the key is kept", () => {
    expect(sendTitle({ provider: "anthropic", host: "api.anthropic.com" })).toBe("Send this to Anthropic at api.anthropic.com?");
    expect(sendTitle({ provider: "ollama", host: "192.168.1.20" })).toBe("Send this to the AI model at 192.168.1.20?");
    expect(keySavedText({ key_protection: "file" })).not.toContain("encrypted");
    expect(keySavedText({ key_protection: "windows" })).toContain("encrypted");
  });
});

describe("QA2 P4: parts of a damaged project left out by the engine are said", () => {
  it("shows the engine's note after opening", async () => {
    const opened = docWith("p");
    const note = "1 part of this project was damaged and left out.";
    const engine = fakeEngine({ "project.open": { layout: opened.layout, images: [], path: "C:/p/d.ludd", notes: [note] } });
    useStore.setState({ engine: engine as never, machines: [machine("pe550d", ["b1"])], machineId: "pe550d", hoopId: "b1" });
    await A.openDesign("C:/p/d.ludd", true);
    expect(useStore.getState().notice?.text).toContain("damaged and left out");
  });
});
