/**
 * My motifs with the real engine (P6-B2): the app saves a drawn (and resized) line as a motif,
 * picks it for a motif line and a motif fill the way the Motif list does, and what the engine sews
 * is a copy of the drawn line at the shape's Repeat. The engine is started from engine/ with
 * `uv run` (as the engine tests and the browser preview start it), in a data folder of its own.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { setObjectParams, whenIdle } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import { Kind, type ObjectItem } from "../design/types";
import { useStore } from "../store";
import { motifPatch, saveLineMotif, selectedLine, useMotifs } from "./motifs";

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

const IDENT = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };
const shape = (id: string, kind: ObjectItem["kind"], geometry: object, params: object = {}, transform = IDENT): ObjectItem =>
  ({ id, kind, geometry, params, thread: { color: "#1f3a93", name: "Navy", brand: "", catalog: "" }, transform: { ...transform }, threads: [], ops: [] }) as unknown as ObjectItem;

// A hill drawn 20 mm long and 12 mm tall, then made half as tall with the handles: it shows 6 mm
// tall, 0.3 of its length.
const DRAWN = shape("src", "run", { nodes: [[0, -40, "c"], [10, -52, "c"], [20, -40, "c"]] }, {}, { ...IDENT, scale_y: 0.5 });
const ALONG = shape("line", "run", { nodes: [[0, 0, "c"], [40, 0, "c"]] }, { style: "motif", tie_in: false, tie_off: false });
const AREA = shape("fill", "fill", { outline: [[0, 10, "c"], [40, 10, "c"], [40, 40, "c"], [0, 40, "c"]] }, { pattern: "motif", angle_deg: 0, tie_in: false, tie_off: false });

describe("my motifs, with the real engine", () => {
  let work = "";
  let engine: ReturnType<typeof startEngine>;

  beforeAll(() => {
    work = mkdtempSync(path.join(os.tmpdir(), "ludd-motifs-"));
    engine = startEngine(path.join(work, "data"));
  });

  afterAll(async () => {
    await engine?.stop();
    if (work) rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  /** An item's needle points in the design on screen, in mm. */
  function needles(id: string): [number, number][] {
    const { design, history } = useStore.getState();
    const index = history.present!.layout.items.findIndex((it) => it.id === id);
    const r = design!.records;
    return r.x.flatMap((x, i): [number, number][] => (r.item![i] === index && r.kind[i] === Kind.Stitch ? [[x, r.y[i]]] : []));
  }

  /** The gaps between the x places of the points at height `y`. */
  const gaps = (points: [number, number][], y: number) => {
    const xs = [...new Set(points.filter(([, py]) => Math.abs(py - y) < 0.02).map(([x]) => Math.round(x * 100) / 100))].sort((a, b) => a - b);
    return xs.slice(1).map((x, i) => x - xs[i]);
  };

  it(
    "a drawn line saved as a motif sews with its drawn proportions, on a line and a fill",
    async () => {
      const blank = newDoc();
      const doc = { ...blank, layout: { ...blank.layout, items: [DRAWN, ALONG, AREA] } };
      useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: "src", extraIds: [], design: null, notice: null, dialog: null, pen: null });

      const saved = await saveLineMotif(selectedLine()!, "Hill");
      expect(saved.unit).toEqual([[0, 0], [0.5, -0.3], [1, 0]]);
      expect(readdirSync(path.join(work, "data", "motifs"))).toEqual(["hill.json"]);
      const entry = useMotifs.getState().list!.find((m) => m.id === saved.id)!;
      expect(entry).toEqual({ ...saved, builtin: false });

      // On a motif line (Repeat 4 mm): 6 mm over 20 mm drawn, so 1.2 mm tall.
      const item = (id: string) => useStore.getState().history.present!.layout.items.find((it) => it.id === id) as ObjectItem;
      setObjectParams("line", motifPatch(entry, item("line")));
      await whenIdle();
      expect(useStore.getState().notice).toBeNull();
      const along = needles("line");
      const ys = along.map(([, y]) => y);
      expect(Math.max(...ys) - Math.min(...ys)).toBeCloseTo(1.2, 1);
      const peaks = gaps(along, Math.min(...ys)); // the hills point up the screen, as drawn
      expect(peaks).toHaveLength(9);
      peaks.forEach((gap) => expect(gap).toBeCloseTo(4, 1));

      // On a motif fill (Repeat 5 mm): 1.5 mm tall, each row the same hills.
      setObjectParams("fill", motifPatch(entry, item("fill")));
      await whenIdle();
      expect(useStore.getState().notice).toBeNull();
      // 15 rows 2 mm apart down a 30 mm square (1.5 mm tall, 0.5 mm between); the middle one is
      // centered on y = 25.
      const row = needles("fill").filter(([x, y]) => x > 0.5 && x < 39.5 && Math.abs(y - 25) <= 0.76);
      const rowYs = row.map(([, y]) => y);
      expect(Math.max(...rowYs) - Math.min(...rowYs)).toBeCloseTo(1.5, 1);
      const tips = gaps(row, Math.min(...rowYs));
      expect(tips.length).toBeGreaterThanOrEqual(5);
      tips.forEach((gap) => expect(gap).toBeCloseTo(5, 1));
    },
    LONG_MS,
  );
});
