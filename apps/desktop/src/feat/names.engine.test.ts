/**
 * "One file per name" with the real engine (P5-D1, done when 4): the app's own list reading and
 * export, against the engine started from engine/ with `uv run` (as the engine tests and the
 * browser preview start it), in a data folder of its own. The font is made here with fontTools,
 * so it runs the same on every computer. Every file is compared with the same design saved with
 * its row typed in by hand.
 */
import { execFileSync, spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import * as A from "../actions";
import "../cmd";
import { DEFAULT_CUT_STOPS } from "../design/machine";
import { newDoc } from "../design/layout";
import type { Layout, TextItem } from "../design/types";
import { useStore } from "../store";
import * as N from "./names";

const ENGINE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../../engine");
const LONG_MS = 300_000; // the first run may have to set up the engine's environment

/** A font with a bar for each character, each its own width, so every name sews differently. */
const MAKE_FONT = `
import sys
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}
widths = {".notdef": (500, 0), "space": (300, 0)}
cmap = {32: "space"}
for i, c in enumerate(sys.argv[2]):
    pen = TTGlyphPen(None)
    w, h = 90 + 12 * i, 700 if c.isupper() or c.isdigit() else 500
    pen.moveTo((60, 0))
    for point in ((60, h), (60 + w, h), (60 + w, 0)):
        pen.lineTo(point)
    pen.closePath()
    name = f"g{i}"
    glyphs[name], widths[name], cmap[ord(c)] = pen.glyph(), (w + 120, 60), name
fb = FontBuilder(1000, isTTF=True)
fb.setupGlyphOrder(list(glyphs))
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics(widths)
fb.setupHorizontalHeader(ascent=800, descent=-200)
fb.setupNameTable({"familyName": "Names Test", "styleName": "Regular"})
fb.setupOS2(sCapHeight=700, sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
fb.setupPost()
fb.save(sys.argv[1])
`;

type Answer = { id: number; result?: unknown; error?: { message: string } };

/** The engine over JSON-RPC on stdio, one request per line, as the desktop app talks to it. */
function startEngine(dataDir: string) {
  const child = spawn("uv", ["run", "--locked", "python", "-m", "threadline_engine"], {
    cwd: ENGINE_DIR,
    env: { ...process.env, THREADLINE_DATA_DIR: dataDir },
  });
  const pending = new Map<number, (a: Answer) => void>();
  let buffer = "";
  let said = "";
  let nextId = 1;
  let gone: string | null = null;
  const exited = new Promise<void>((resolve) => {
    const over = (why: string) => {
      gone = why;
      for (const [id, done] of pending) done({ id, error: { message: why } });
      pending.clear();
      resolve();
    };
    child.on("error", (err) => over(`The engine didn't start (this test needs uv, as the engine tests do): ${err.message}`));
    child.on("exit", (code) => over(`The engine stopped (exit ${code}): ${said.slice(-800)}`));
  });
  child.stderr.on("data", (d) => (said += String(d)));
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (chunk: string) => {
    buffer += chunk;
    for (let nl = buffer.indexOf("\n"); nl >= 0; nl = buffer.indexOf("\n")) {
      const line = buffer.slice(0, nl);
      buffer = buffer.slice(nl + 1);
      if (!line.trim()) continue;
      const answer = JSON.parse(line) as Answer;
      pending.get(answer.id)?.(answer);
      pending.delete(answer.id);
    }
  });
  return {
    call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
      const id = nextId++;
      return new Promise<T>((resolve, reject) => {
        const done = (a: Answer) => (a.error ? reject(new Error(a.error.message)) : resolve(a.result as T));
        if (gone) return done({ id, error: { message: gone } });
        pending.set(id, done);
        child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
      });
    },
    async stop() {
      child.stdin.end();
      const kill = setTimeout(() => child.kill(), 10_000);
      await exited;
      clearTimeout(kill);
    },
  };
}

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const NAVY = { color: "#1f3a93", name: "Navy", brand: "", catalog: "" };

describe("one file per name, with the real engine", () => {
  let work = "";
  let font = "";
  let engine: ReturnType<typeof startEngine>;

  const text = (id: string, words: string, y: number, extra: Partial<TextItem> = {}): TextItem => ({
    id, kind: "text", text: words, font: { path: font, index: 0, family: "Names Test", style: "Regular" }, size_mm: 15,
    spacing_mm: 0, style: "satin", shape: { type: "line" }, monogram: false, thread: NAVY, transform: { ...IDENT, y },
    threads: [], ops: [], ...extra,
  });

  /** The design open in the app. */
  function open(items: TextItem[]) {
    const blank = newDoc();
    const doc = { ...blank, layout: { ...blank.layout, items } };
    useStore.setState({
      engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: items[0].id,
      extraIds: [], design: null, notice: null, dialog: null, projectPath: null, machines: [], machineId: null,
    });
    return doc;
  }

  /** The app's own export of a list: a folder of one machine file per row. */
  async function exportRows(columns: string, rows: string[], into: string) {
    const csv = path.join(work, `${into}.csv`);
    writeFileSync(csv, [columns, ...rows].join("\r\n"), "utf8");
    const folder = path.join(work, into);
    mkdirSync(folder);
    const list = await engine.call<N.NameList>("names.read_list", { path: csv });
    await N.exportList(list, folder, "pes");
    return { folder, list, files: readdirSync(folder).sort() };
  }

  /** The same design saved for the machine after its words were typed in by hand. */
  async function typedByHand(layout: Layout, words: Record<string, string>, name: string) {
    const items = layout.items.map((it) => {
      const t = it as TextItem;
      return t.id in words ? { ...t, text: words[t.id], placeholder: undefined, bind: undefined } : t;
    });
    const dest = path.join(work, "by-hand", name);
    const options = A.exportOptions({ ...DEFAULT_CUT_STOPS, enabled: false });
    await engine.call("layout.export", { layout: { ...layout, items }, dest, options, keep_existing: false });
    return readFileSync(dest);
  }

  beforeAll(async () => {
    work = mkdtempSync(path.join(os.tmpdir(), "ludd-names-"));
    mkdirSync(path.join(work, "by-hand"));
    font = path.join(work, "NamesTest.ttf");
    execFileSync("uv", ["run", "--locked", "python", "-c", MAKE_FONT, font, "ABCDEJKMPLSTacekmx0127"], { cwd: ENGINE_DIR });
    engine = startEngine(path.join(work, "data"));
  }, LONG_MS);

  afterAll(async () => {
    await engine?.stop();
    if (work) rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  it("two rows with a second column fill two placeholders: one machine file per row", async () => {
    const doc = open([
      text("a", "SAMPLE", -15, { placeholder: true }),
      text("b", "00", 8, { placeholder: true, bind: "number" }),
      text("c", "Team", 30),
    ]);
    const { folder, list, files } = await exportRows("name,number", ["Emma,7", "Jack,12"], "team");
    expect(list).toEqual({ columns: ["name", "number"], rows: [["Emma", "7"], ["Jack", "12"]], skipped: 0 });
    expect(useStore.getState().notice?.text).toContain("Saved 2 files");
    expect(files).toEqual(["Emma.pes", "Jack.pes"]);
    expect(useStore.getState().history.present).toBe(doc); // the design on screen is unchanged

    const made = files.map((f) => readFileSync(path.join(folder, f)));
    expect(made[0].equals(await typedByHand(doc.layout, { a: "Emma", b: "7" }, "Emma.pes"))).toBe(true);
    expect(made[1].equals(await typedByHand(doc.layout, { a: "Jack", b: "12" }, "Jack.pes"))).toBe(true);
    expect(made[0].equals(made[1])).toBe(false);
    expect(made[0].subarray(0, 4).toString("latin1")).toBe("#PES");
  }, LONG_MS);

  it("long file names that differ only past the cut don't overwrite each other", async () => {
    const doc = open([text("a", "SAMPLE", 0, { placeholder: true })]);
    const long = "x".repeat(120);
    const { folder, files } = await exportRows("name,file", [`Emma,${long}A`, `Jack,${long}B`], "long");
    const stem = "x".repeat(100);
    expect(files).toEqual([`${stem} (1).pes`, `${stem}.pes`]);
    const read = (name: string) => readFileSync(path.join(folder, name));
    expect(read(`${stem}.pes`).equals(await typedByHand(doc.layout, { a: "Emma" }, `${stem}.pes`))).toBe(true);
    expect(read(`${stem} (1).pes`).equals(await typedByHand(doc.layout, { a: "Jack" }, `${stem} (1).pes`))).toBe(true);
  }, LONG_MS);
});
