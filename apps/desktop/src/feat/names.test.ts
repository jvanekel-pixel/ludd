/**
 * Names from a list (P5-D1), with a fake engine: placeholders filled row by row, long names
 * shrunk to fit, colors and file names from the list, a preview that changes nothing, and name
 * templates.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const native = vi.hoisted(() => ({ open: vi.fn(async (): Promise<string | null> => null) }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: native.open, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));
vi.mock("../engine/sidecar", async (original) => ({ ...(await original<typeof import("../engine/sidecar")>()), isTauri: () => true }));

import * as A from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import type { Chart, Design, Layout, TextItem } from "../design/types";
import { useStore } from "../store";
import * as N from "./names";

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const NAVY = { color: "#1f3a93", name: "Navy", brand: "", catalog: "" };
const text = (id: string, words: string, extra: Partial<TextItem> = {}): TextItem => ({
  id, kind: "text", text: words, font: { path: "f.ttf", index: 0, family: "Arial", style: "Regular" }, size_mm: 15,
  spacing_mm: 0, style: "satin", shape: { type: "line" }, monogram: false, thread: NAVY, transform: IDENT, threads: [], ops: [], ...extra,
});

const CHART: Chart = {
  id: "janome", name: "Janome", brand: "Janome", builtin: true, mine: false,
  threads: [{ code: "1001", name: "Scarlet", color: "#cc0000" }, { code: "005", name: "Silver", color: "#a0a0a0" }],
};

/** A letter is 0.6 of its height wide; plus the spacing between letters, plus 0.2 mm of edge pad. */
const widthOf = (t: TextItem) => (t.text.length * 0.6 * t.size_mm + (t.text.length - 1) * t.spacing_mm) * t.transform.scale_x + 0.2;

type Call = { method: string; params: Record<string, any> };

function fakeEngine() {
  const calls: Call[] = [];
  const replies: Record<string, unknown> = {};
  let gate: Promise<void> | null = null;
  return {
    calls,
    replies,
    /** Hold every render until the returned function is called. */
    holdRenders() {
      let letGo = () => {};
      gate = new Promise<void>((r) => (letGo = r));
      return () => {
        gate = null;
        letGo();
      };
    },
    async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      const sent = JSON.parse(JSON.stringify(params)) as Record<string, any>; // as it reaches the engine
      calls.push({ method, params: sent });
      if (method === "layout.render") {
        if (gate) await gate;
        const layout = sent.layout as Layout;
        const items = layout.items.map((it) => {
          const w = widthOf(it as TextItem);
          return { id: it.id, name: it.id, kind: "text", center_mm: [0, 0], bounds_mm: [-w / 2, -5, w / 2, 5], source_size_mm: null };
        });
        const name = layout.items.map((it) => (it as TextItem).text).join("|");
        return { path: "", name, format: "layout", info: { bounds_mm: [0, 0, 1, 1] }, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items } as T;
      }
      if (method === "layout.export") return { path: sent.dest, stops_added: 0, warnings: [] } as T;
      if (method === "threads.chart") return CHART as T;
      if (method in replies) {
        const r = replies[method];
        if (r instanceof Error) throw r;
        return r as T;
      }
      return null as T;
    },
  };
}

async function open(items: TextItem[], selected: string | null = items[0].id) {
  await A.whenIdle();
  const engine = fakeEngine();
  const blank = newDoc();
  const doc = { ...blank, layout: { ...blank.layout, items } };
  const design = await engine.call<Design>("layout.render", { layout: doc.layout });
  engine.calls.length = 0;
  useStore.setState({
    engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: selected, extraIds: [],
    design: { ...design, name: "as saved" }, notice: null, dialog: null, projectPath: null, machines: [], machineId: null,
  });
  return { engine, doc };
}

const exported = (engine: ReturnType<typeof fakeEngine>) =>
  engine.calls.filter((c) => c.method === "layout.export").map((c) => ({
    dest: c.params.dest as string,
    layout: c.params.layout as Layout,
    items: Object.fromEntries((c.params.layout as Layout).items.map((it) => [it.id, it as TextItem])),
  }));
const words = (e: ReturnType<typeof exported>[number]) => Object.fromEntries(Object.entries(e.items).map(([id, it]) => [id, it.text]));
const said = () => useStore.getState().notice?.text ?? "";
const list = (columns: string[], ...rows: string[][]) => ({ columns, rows, skipped: 0 });

beforeEach(async () => {
  await A.whenIdle();
  N.endPreview();
  native.open.mockClear();
});

describe("one file per name", () => {
  it("placeholders are filled per row and two columns fill two texts", async () => {
    // Done when 4: a CSV of names with a second column fills two placeholders and writes one file per row.
    const { engine, doc } = await open([text("a", "Name", { placeholder: true }), text("b", "00", { placeholder: true, bind: "number" }), text("c", "Tigers")], "c");
    native.open.mockResolvedValueOnce("C:\\team\\players.csv");
    engine.replies["names.read_list"] = { columns: ["name", "number"], rows: [["Emma", "7"], ["Jack", "12"], ["Mia", "3"]], skipped: 0 };
    const players = await N.loadList();
    expect(engine.calls.find((c) => c.method === "names.read_list")!.params).toEqual({ path: "C:\\team\\players.csv" });
    expect(players!.file).toBe("players.csv");
    await N.exportList(players!, "C:\\out", "pes");
    const files = exported(engine);
    expect(files.map((f) => f.dest)).toEqual(["C:\\out\\Emma.pes", "C:\\out\\Jack.pes", "C:\\out\\Mia.pes"]);
    expect(files.map(words)).toEqual([
      { a: "Emma", b: "7", c: "Tigers" },
      { a: "Jack", b: "12", c: "Tigers" },
      { a: "Mia", b: "3", c: "Tigers" },
    ]);
    expect(engine.calls.filter((c) => c.method === "layout.export").every((c) => c.params.keep_existing === true)).toBe(true);
    // The design on screen isn't changed.
    const s = useStore.getState();
    expect(s.history.present).toBe(doc);
    expect(s.history.past).toHaveLength(0);
    expect(said()).toContain("Saved 3 files");
  });

  it("a long name shrinks to fit_width_mm", async () => {
    const { engine } = await open([text("a", "Bo", { placeholder: true, fit_width_mm: 40, spacing_mm: 1, transform: { ...IDENT, rotate: 30 } })]);
    await N.exportList(list(["name"], ["Bo"], ["Alexandria"]), "C:\\out", "pes");
    const [short, long] = exported(engine).map((f) => f.items.a);
    expect([short.size_mm, short.spacing_mm]).toEqual([15, 1]);
    expect(long.size_mm).toBeLessThan(7);
    expect(widthOf(long)).toBeLessThanOrEqual(40.05);
    expect(widthOf(long)).toBeGreaterThan(39);
    expect(long.spacing_mm / long.size_mm).toBeCloseTo(1 / 15, 3); // size and spacing together
    expect(long.transform.rotate).toBe(30); // only measured unturned
    // Measured by itself, unturned.
    const measured = engine.calls.filter((c) => c.method === "layout.render").at(-1)!.params.layout as Layout;
    expect(measured.items).toHaveLength(1);
    expect((measured.items[0] as TextItem).transform.rotate).toBe(0);
  });

  it("says so when a name can't fit even at the smallest size", async () => {
    const { engine } = await open([text("a", "Bo", { placeholder: true, fit_width_mm: 3 })]);
    await N.exportList(list(["name"], ["Alexandria"]), "C:\\out", "pes");
    expect(exported(engine)[0].items.a.size_mm).toBe(2);
    expect(said()).toMatch(/still .* wide/);
  });

  it("a color column sets the thread", async () => {
    const mine = [{ color: "#123456", name: "Changed", brand: "", catalog: "" }];
    const { engine } = await open([text("a", "Name", { placeholder: true, threads: mine }), text("b", "Tigers")]);
    await N.exportList(
      list(["name", "color"], ["A", "#00FF00"], ["B", "1001"], ["C", "5"], ["D", "ff8800"], ["E", "blorp"], ["F", ""]),
      "C:\\out", "pes", CHART,
    );
    const sewn = exported(engine).map((f) => [f.items.a.thread, f.items.a.threads]);
    expect(sewn[0]).toEqual([{ color: "#00ff00", name: "", brand: "", catalog: "" }, []]);
    expect(sewn[1]).toEqual([{ color: "#cc0000", name: "Scarlet", brand: "Janome", catalog: "1001" }, []]);
    expect(sewn[2]).toEqual([{ color: "#a0a0a0", name: "Silver", brand: "Janome", catalog: "005" }, []]); // 005 typed as 5
    expect(sewn[3]).toEqual([{ color: "#ff8800", name: "", brand: "", catalog: "" }, []]);
    expect(sewn[4]).toEqual([NAVY, mine]); // not a color: kept as it was, and said
    expect(sewn[5]).toEqual([NAVY, mine]);
    expect(exported(engine)[0].items.b.thread).toEqual(NAVY); // only the filled lettering
    expect(said()).toContain("blorp");
  });

  it("a file column names the output file", async () => {
    const { engine } = await open([text("a", "Name")]);
    await N.exportList(list(["name", "file"], ["Emma", "shirt-1.PES"], ["Jack", ""], ["Mia", "a/b"]), "/home/out", "pes");
    expect(exported(engine).map((f) => f.dest)).toEqual(["/home/out/shirt-1.pes", "/home/out/Jack.pes", "/home/out/a_b.pes"]);
  });

  it("without a placeholder the selected lettering is filled from the names typed in", async () => {
    const dots = { 0: { start_mm: [1, 2] as [number, number] } };
    const { engine } = await open([text("t1", "Tigers"), text("t2", "Name", { letters: dots })], "t2");
    const typed = N.typedList("Emma\n\n  Jack \n");
    expect(typed).toEqual({ columns: ["name"], rows: [["Emma"], ["Jack"]], skipped: 0 });
    await N.exportList(typed, "C:\\out", "jef");
    expect(exported(engine).map(words)).toEqual([{ t1: "Tigers", t2: "Emma" }, { t1: "Tigers", t2: "Jack" }]);
    expect(exported(engine)[0].items.t2.letters).toBeUndefined(); // new letters: old dots don't apply
    expect(exported(engine)[0].dest).toBe("C:\\out\\Emma.jef");
  });

  it("leaves lettering with an empty cell out of its file, and makes no file for an empty row", async () => {
    const { engine } = await open([text("a", "Name", { placeholder: true }), text("b", "00", { placeholder: true, bind: "number" }), text("c", "Tigers")]);
    await N.exportList(list(["name", "number"], ["Emma", ""], ["", ""]), "C:\\out", "pes");
    const files = exported(engine);
    expect(files).toHaveLength(1);
    expect(files[0].layout.items.map((it) => it.id)).toEqual(["a", "c"]); // never the sample's "00"
    expect(said()).toMatch(/Row 1 has no number/);
    expect(said()).toMatch(/Row 2 is empty/);
  });

  it("refuses a list without a placeholder's column before saving anything", async () => {
    const { engine } = await open([text("a", "Name", { placeholder: true }), text("b", "00", { placeholder: true, bind: "number" })]);
    await N.exportList(N.typedList("Emma"), "C:\\out", "pes");
    expect(exported(engine)).toHaveLength(0);
    expect(said()).toContain("number");
  });

  it("takes a single column of names whatever its header says", () => {
    expect(N.columnFor(list(["player"], ["Emma"]), "name")).toBe(0);
    expect(N.columnFor(list(["first name", "color"], ["Emma", ""]), "name")).toBe(0);
    expect(N.columnFor(list(["player", "number"], ["Emma", "7"]), "name")).toBe(-1);
    expect(N.columnFor(list(["name", "number"], ["Emma", "7"]), "number")).toBe(1);
    expect(N.columnFor(list(["name"], ["Emma"]), "number")).toBe(-1);
  });

  it("fills the lettering marked in the list's window, binding a second one to the next column", async () => {
    const { doc } = await open([text("a", "Name"), text("b", "00")]);
    expect(N.textTargets(doc.layout, "a").map((t) => t.id)).toEqual(["a"]);
    await N.setPlaceholder("b", true, ["name", "number", "color"]);
    const items = () => useStore.getState().history.present!.layout.items as TextItem[];
    expect(items().map((t) => [t.placeholder, t.bind])).toEqual([[true, undefined], [true, "number"]]);
    expect(useStore.getState().history.past).toHaveLength(1); // one undo step
    await N.setBind("b", "name");
    expect(items()[1].bind).toBeUndefined();
    await N.setPlaceholder("a", false, ["name"]);
    expect(items().map((t) => !!t.placeholder)).toEqual([false, true]);
    await N.setPlaceholder("b", false, ["name"]); // at least one stays
    expect(items()[1].placeholder).toBe(true);
  });

  it("starts shrinking to fit at the lettering's width now", async () => {
    const { engine } = await open([text("a", "Name")]);
    await N.setFitWidth("a", true);
    const a = () => useStore.getState().history.present!.layout.items[0] as TextItem;
    expect([a().placeholder, a().fit_width_mm]).toEqual([true, Math.ceil(widthOf(a()))]);
    await N.setFitWidth("a", false);
    expect(a().fit_width_mm).toBeUndefined();
    expect(engine.calls.some((c) => c.method === "layout.export")).toBe(false);
  });
});

describe("previewing the list", () => {
  it("shows each row on the design without changing it, and puts it back", async () => {
    const { engine, doc } = await open([text("a", "Name", { placeholder: true }), text("b", "Tigers")]);
    const saved = useStore.getState().design;
    const people = list(["name"], ["Emma"], ["Jack"]);
    expect(await N.showRow(people, 1, null)).toEqual([]);
    expect(useStore.getState().design!.name).toBe("Jack|Tigers");
    await N.showRow(people, 0, null);
    expect(useStore.getState().design!.name).toBe("Emma|Tigers");
    const s = useStore.getState();
    expect(s.history).toEqual({ past: [], present: doc, future: [] });
    expect(s.savedDoc).toBe(doc);
    expect(engine.calls.some((c) => c.method === "layout.export")).toBe(false);
    N.endPreview();
    expect(useStore.getState().design).toBe(saved);
  });

  it("throws away a row that finishes after the window has closed", async () => {
    const { engine } = await open([text("a", "Name")]);
    const saved = useStore.getState().design;
    const letGo = engine.holdRenders();
    const late = N.showRow(list(["name"], ["Emma"]), 0, null);
    await new Promise((r) => setTimeout(r, 0));
    N.endPreview();
    letGo();
    expect(await late).toBeNull();
    expect(useStore.getState().design).toBe(saved);
  });

  it("keeps a change made while it's open, and still puts the saved design back", async () => {
    await open([text("a", "Name"), text("b", "Two")], "a");
    const people = list(["name"], ["Emma"]);
    await N.showRow(people, 0, null);
    await N.setPlaceholder("b", true, ["name"]);
    await N.showRow(people, 0, null);
    expect(useStore.getState().design!.name).toBe("Emma|Emma");
    N.endPreview();
    expect(useStore.getState().design!.name).toBe("Name|Two");
  });
});

describe("name templates", () => {
  it("saves the whole design as a template without touching the open project", async () => {
    const { engine, doc } = await open([text("a", "Name", { placeholder: true, fit_width_mm: 60 })]);
    useStore.setState({ projectPath: "C:\\mine.ludd" });
    engine.replies["names.save_template"] = { name: "Team shirts", path: "C:\\data\\templates\\Team shirts.ludd" };
    expect(await N.saveTemplateAs("Team shirts", false)).toBeNull();
    const sent = engine.calls.find((c) => c.method === "names.save_template")!.params;
    expect(sent.name).toBe("Team shirts");
    expect(sent.replace).toBe(false);
    expect(sent.project_data).toEqual({ title: "Team shirts", layout: doc.layout, images: [], machine: null, hoop: null });
    const s = useStore.getState();
    expect([s.projectPath, s.savedDoc, s.history.present]).toEqual(["C:\\mine.ludd", doc, doc]);
    engine.replies["names.save_template"] = new Error("A template named Team shirts already exists.");
    expect(await N.saveTemplateAs("Team shirts", false)).toContain("already exists");
  });

  it("starts from a template as a new design that Save asks a name for", async () => {
    const { engine } = await open([text("a", "Name")]);
    const template = { ...newDoc().layout, items: [text("p", "Name", { placeholder: true })] };
    engine.replies["project.open"] = { layout: template, images: [], path: "C:\\data\\templates\\Team.ludd" };
    await N.openTemplate("C:\\data\\templates\\Team.ludd");
    await A.whenIdle();
    const s = useStore.getState();
    expect(s.history.present!.layout.items.map((it) => it.id)).toEqual(["p"]);
    expect(s.projectPath).toBeNull();
    expect(engine.calls.find((c) => c.method === "project.open")!.params.path).toBe("C:\\data\\templates\\Team.ludd");
  });

  it("keeps the open project when a template can't be opened", async () => {
    const { engine, doc } = await open([text("a", "Name")]);
    useStore.setState({ projectPath: "C:\\mine.ludd" });
    engine.replies["project.open"] = new Error("Team isn't a LUDD project");
    await N.openTemplate("C:\\data\\templates\\Team.ludd");
    expect([useStore.getState().projectPath, useStore.getState().history.present]).toEqual(["C:\\mine.ludd", doc]);
  });

  it("Save this layout as a name template asks for its name", async () => {
    await open([text("a", "Name")]);
    const command = A.command("text.saveTemplate");
    expect(command.enabled!()).toBe(true);
    command.run();
    expect(useStore.getState().dialog).toBe("saveTemplate");
  });
});
