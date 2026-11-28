/**
 * Track A's settings with the real engine: every line style, motif side, lock-stitch shape and
 * blackwork lattice the panel offers sews, the panel's starting numbers are the engine's, and the
 * buttonhole and eyelet dialogs add shapes the engine makes and sews, a bar buttonhole's lips with
 * no jump between them. The engine is started from engine/ with `uv run`, as in the other engine
 * tests, in a data folder of its own.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { setObjectParams, whenIdle } from "../actions";
import "../cmd";
import { fillPatternDef } from "../design/fillPatterns";
import { newDoc } from "../design/layout";
import { LINE_STYLE_DEFS } from "../design/lineStyles";
import { Kind, type ObjectItem } from "../design/types";
import { useStore } from "../store";
import { addSmallObject, BUTTONHOLE, EYELET } from "./smallObjects";

const ENGINE_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../../engine");
const LONG_MS = 300_000; // the first run may have to set up the engine's environment

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

const shape = (id: string, kind: ObjectItem["kind"], geometry: object, params: object = {}): ObjectItem =>
  ({ id, kind, geometry, params, thread: { color: "#1f3a93", name: "Navy", brand: "", catalog: "" }, transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as unknown as ObjectItem;

const LINE = shape("line", "run", { nodes: [[0, 0, "c"], [30, 0, "c"], [30, 12, "c"]] });
const AREA = shape("area", "fill", { outline: [[0, 20, "c"], [30, 20, "c"], [30, 50, "c"], [0, 50, "c"]] });
const COLUMN = shape("satin", "satin", { nodes: [[40, 0, "c"], [70, 0, "c"]], width_mm: 3 });

describe("Phase 7's lines, locks, blackwork and small objects, with the real engine", () => {
  let work = "";
  let engine: ReturnType<typeof startEngine>;

  beforeAll(() => {
    work = mkdtempSync(path.join(os.tmpdir(), "ludd-lines-"));
    engine = startEngine(path.join(work, "data"));
  });

  afterAll(async () => {
    await engine?.stop();
    if (work) rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  /** An item's records in the design on screen: [x, y, kind]. */
  function records(id: string): [number, number, number][] {
    const { design, history } = useStore.getState();
    const index = history.present!.layout.items.findIndex((it) => it.id === id);
    const r = design!.records;
    return r.x.flatMap((x, i): [number, number, number][] => (r.item![i] === index ? [[x, r.y[i], r.kind[i]]] : []));
  }

  /** Set it as the panel does, wait for the engine to sew it, and give back the item's records. */
  async function set(id: string, patch: Record<string, unknown>) {
    useStore.getState().notify(null);
    setObjectParams(id, patch);
    await whenIdle();
    expect(useStore.getState().notice, JSON.stringify(patch)).toBeNull();
    return records(id);
  }

  it(
    "everything the panel offers sews, and its starting numbers are the engine's",
    async () => {
      const blank = newDoc();
      const doc = { ...blank, layout: { ...blank.layout, items: [LINE, AREA, COLUMN] } };
      useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "line", extraIds: [], design: null, notice: null, dialog: null, pen: null });

      const sewnAs = new Set<string>();
      for (const style of LINE_STYLE_DEFS) {
        const plain = await set("line", { style: style.id, ...Object.fromEntries(style.fields.map((f) => [f.key, undefined])) });
        expect(plain.filter(([, , k]) => k === Kind.Stitch).length, style.id).toBeGreaterThan(5);
        sewnAs.add(JSON.stringify(plain));
        if (style.fields.length) expect(await set("line", Object.fromEntries(style.fields.map((f) => [f.key, f.def]))), style.id).toEqual(plain);
      }
      expect(sewnAs.size).toBe(LINE_STYLE_DEFS.length); // each style sews its own way
      await set("line", { style: "motif", motif: "blanket" });
      const left = await set("line", { motif_side: "left" });
      const right = await set("line", { motif_side: "right" });
      expect(left).not.toEqual(right);
      for (const id of ["line", "satin", "area"]) {
        const plain = records(id);
        for (const tie of ["triangle", "backtack"]) expect(await set(id, { tie_style: tie }), `${id} ${tie}`).not.toEqual(plain);
        expect(await set(id, { tie_style: undefined })).toEqual(plain);
      }
      const blackwork = fillPatternDef("blackwork");
      const cells = Object.fromEntries(blackwork.fields.map((f) => [f.key, f.def]));
      const unset = await set("area", { pattern: "blackwork" });
      expect(await set("area", { ...cells, blackwork_lattice: blackwork.choices![0].def })).toEqual(unset);
      const lattices = new Set<string>();
      for (const option of blackwork.choices![0].options) lattices.add(JSON.stringify(await set("area", { blackwork_lattice: option.id })));
      expect(lattices.size).toBe(4);
    },
    LONG_MS,
  );

  it(
    "the dialogs add a buttonhole and an eyelet the engine makes and sews, the lips with no jump",
    async () => {
      // From nothing open, as the first thing made: a new design (with fewer jumps and trims on).
      useStore.setState({ engine: engine as never, history: { past: [], present: null, future: [] }, savedDoc: null, selectedId: null, extraIds: [], design: null, notice: null, dialog: null, pen: null });
      expect(await addSmallObject("buttonhole", BUTTONHOLE)).toBe(true);
      await whenIdle();
      const items = () => useStore.getState().history.present!.layout.items as ObjectItem[];
      expect(items().map((it) => it.kind)).toEqual(["satin", "satin", "satin", "satin"]);
      const r = useStore.getState().design!.records;
      const stitches = r.x.map((_, i) => i).filter((i) => r.kind[i] === Kind.Stitch);
      const lastOfFirst = Math.max(...stitches.filter((i) => r.item![i] === 0));
      const firstOfSecond = Math.min(...stitches.filter((i) => r.item![i] === 1));
      expect(firstOfSecond).toBeGreaterThan(lastOfFirst);
      expect(new Set(r.kind.slice(lastOfFirst, firstOfSecond + 1))).toEqual(new Set([Kind.Stitch]));

      expect(await addSmallObject("buttonhole", { ...BUTTONHOLE, style: "round" })).toBe(true);
      expect(await addSmallObject("eyelet", EYELET)).toBe(true);
      await whenIdle();
      expect(items().map((it) => it.name).slice(4)).toEqual(["Rounded buttonhole", "Eyelet run", "Eyelet ring"]);
      await expect(addSmallObject("buttonhole", { ...BUTTONHOLE, width_mm: 3, cut_gap_mm: 1.5 })).rejects.toThrow("Make the buttonhole wider or the cut narrower");
      expect(items()).toHaveLength(7);
    },
    LONG_MS,
  );
});
