// @vitest-environment jsdom
/**
 * Done-when 5 of Phase 7, with the real engine and the whole path a user takes: Import artwork
 * (the command), the file picker, the dialog, its preview from the engine, and its Add button. An
 * SVG with a filled path, a thin stroke and a 3 mm stroke comes in as a fill, a line and a 3 mm
 * satin ribbon at the file's real size, nothing is added before Add is pressed, and the engine sews
 * them. The engine is started from engine/ with `uv run`, in a data folder of its own.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

const picked = vi.hoisted(() => ({ path: null as string | null }));
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => picked.path, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { Kind, type ObjectItem } from "../design/types";
import { DialogHost } from "../dialogs";
import { useStore } from "../store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

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

/** 80 x 50 mm: a filled path 30 x 20 mm, a 0.4 mm stroke 50 mm long and a 3 mm stroke 25 mm long. */
const ART = `<svg xmlns="http://www.w3.org/2000/svg" width="80mm" height="50mm" viewBox="0 0 80 50">
  <path d="M10 10 H40 V30 H10 Z" fill="#cc0000"/>
  <path d="M10 40 H60" fill="none" stroke="#006600" stroke-width="0.4"/>
  <path d="M45 15 H70" fill="none" stroke="#0000cc" stroke-width="3"/>
</svg>`;

describe("importing artwork, with the real engine", () => {
  let work = "";
  let engine: ReturnType<typeof startEngine>;
  let root: Root | null = null;
  const host = document.createElement("div");

  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
      this.open = true;
    };
    work = mkdtempSync(path.join(os.tmpdir(), "ludd-art-"));
    engine = startEngine(path.join(work, "data"));
    document.body.append(host);
  });

  afterAll(async () => {
    act(() => root?.unmount());
    host.remove();
    await engine?.stop();
    if (work) rmSync(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  const dialog = () => host.querySelector<HTMLDialogElement>("dialog.import-art");
  const addButton = () => [...(dialog()?.querySelectorAll("button") ?? [])].find((b) => b.textContent === "Add") as HTMLButtonElement | undefined;

  async function waitFor(what: () => boolean, words: string) {
    for (let i = 0; i < 600 && !what(); i++) await act(() => new Promise<void>((r) => setTimeout(r, 100)));
    expect(what(), `${words}: ${dialog()?.textContent ?? useStore.getState().notice?.text}`).toBe(true);
  }

  const items = () => (useStore.getState().history.present?.layout.items ?? []) as ObjectItem[];

  /** An item's needle points on the design on screen, as [min x, min y, max x, max y] in mm. */
  function sewn(id: string): [number, number, number, number] {
    const { design } = useStore.getState();
    const index = items().findIndex((it) => it.id === id);
    const r = design!.records;
    const pts = r.x.flatMap((x, i): [number, number][] => (r.item![i] === index && r.kind[i] === Kind.Stitch ? [[x, r.y[i]]] : []));
    expect(pts.length).toBeGreaterThan(10);
    return [Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1]))];
  }

  it(
    "an SVG comes in as a fill, a line and a 3 mm satin at its real size, only once Add is pressed",
    async () => {
      useStore.setState({ engine: engine as never, history: { past: [], present: null, future: [] }, savedDoc: null, design: null, selectedId: null, extraIds: [], dialog: null, tool: "select", pen: null, notice: null, charts: [], units: "mm" });
      picked.path = path.join(work, "Logo.svg");
      writeFileSync(picked.path, ART);
      root = createRoot(host);
      act(() => root!.render(createElement(DialogHost)));

      await act(async () => command("file.importArt").run());
      await waitFor(() => !!dialog(), "the dialog didn't open");
      expect(addButton()!.disabled || items().length === 0).toBe(true);
      await waitFor(() => addButton()?.disabled === false, "no preview");
      expect(dialog()!.textContent).toContain("1 fill, 1 line, 1 satin · 60 × 30 mm");
      expect(dialog()!.textContent).not.toContain("96 pixels"); // the file says its real size
      expect(items()).toEqual([]); // nothing added before Add
      expect(useStore.getState().history.past).toHaveLength(0);

      await act(async () => addButton()!.click());
      await waitFor(() => !dialog(), "Add didn't finish");
      await act(() => whenIdle());
      expect(useStore.getState().notice?.kind).toBe("info");
      const [fill, line, ribbon] = items();
      expect(items().map((o) => [o.kind, o.thread.color])).toEqual([["fill", "#cc0000"], ["run", "#006600"], ["satin", "#0000cc"]]);
      expect((ribbon.geometry as { width_mm: number }).width_mm).toBe(3);
      // At the file's real size, round the artwork's middle (40, 25.1 in the file).
      expect((fill.geometry as { outline: [number, number, string][] }).outline.map((n) => n.slice(0, 2))).toEqual([[-30, -15.1], [0, -15.1], [0, 4.9], [-30, 4.9]]);
      expect((line.geometry as { nodes: [number, number, string][] }).nodes.map((n) => n.slice(0, 2))).toEqual([[-30, 14.9], [20, 14.9]]);
      expect((ribbon.geometry as { nodes: [number, number, string][] }).nodes.map((n) => n.slice(0, 2))).toEqual([[5, -10.1], [30, -10.1]]);
      expect(new Set(items().map((o) => o.group)).size).toBe(1);
      const state = useStore.getState();
      expect([state.selectedId, ...state.extraIds]).toEqual(items().map((o) => o.id));

      // The engine sews each at its size (the fill and satin a little wider: edge pad).
      const [fx0, fy0, fx1, fy1] = sewn(fill.id);
      expect(fx1 - fx0).toBeGreaterThan(29.5);
      expect(fx1 - fx0).toBeLessThan(31);
      expect(fy1 - fy0).toBeGreaterThan(19.5);
      expect(fy1 - fy0).toBeLessThan(21);
      const [lx0, ly0, lx1, ly1] = sewn(line.id);
      expect(lx1 - lx0).toBeCloseTo(50, 0);
      expect(ly1 - ly0).toBeLessThan(0.1);
      const [sx0, sy0, sx1, sy1] = sewn(ribbon.id);
      expect(sx1 - sx0).toBeCloseTo(25, 0);
      expect(sy1 - sy0).toBeGreaterThan(2.9);
      expect(sy1 - sy0).toBeLessThan(3.6);
    },
    LONG_MS,
  );
});
