// @vitest-environment jsdom
/**
 * Done-when 4 (P7-C1), the whole way: 300 pointer samples on the real design canvas (a fake
 * drawing library), Enter, and the real engine sews the shape. At most 25 points; every sample
 * within 0.4 mm of the drawn curve and the curve within 0.4 mm of the stroke; and every needle
 * point the engine sews within 0.4 mm of the stroke (testEngine.ts starts the engine).
 */
import { act } from "react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));
vi.mock("pixi.js", () => import("../canvas/fakePixi"));

import { COMMANDS, currentLayout, whenIdle } from "../actions";
import "../cmd";
import { mountCanvas, type TestCanvas } from "../canvas/testCanvas";
import { newDoc } from "../design/layout";
import { distToSegment, flatten, type Pt } from "../design/paths";
import { Kind, type ObjectItem, type PathNode } from "../design/types";
import { savePrefs } from "../prefs";
import { useStore } from "../store";
import { useFreehand } from "./freehand";
import { ENGINE_START_MS as LONG_MS, startEngine } from "./testEngine";

let engine: ReturnType<typeof startEngine>;

beforeAll(async () => {
  engine = startEngine();
  await engine.call("ping");
  // Lock stitches off, so every needle point the engine sews is a point on the line.
  savePrefs({ objectDefaults: { run: { style: "single", stitch_mm: 2.5, tie_in: false, tie_off: false } } });
}, LONG_MS);

afterAll(async () => {
  await engine?.stop();
}, 60_000);

/** A repeatable hand shake, -1..1. */
function shake(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) % 2147483648;
    return (s / 2147483648) * 2 - 1;
  };
}

/** 300 samples along f(0..1), the hand speeding up and slowing down, a little shaky. */
function samples(f: (t: number) => Pt, jitter = 0): Pt[] {
  const rnd = shake(5);
  return Array.from({ length: 300 }, (_, i) => {
    const t = i / 299;
    const [x, y] = f(Math.min(1, Math.max(0, t + (0.06 * Math.sin(5 * Math.PI * t)) / (5 * Math.PI))));
    return [x + jitter * rnd(), y + jitter * rnd()];
  });
}

const STROKES: [string, Pt[]][] = [
  ["S curve", samples((t) => [-30 + 60 * t, 14 * Math.sin(2 * Math.PI * t)])],
  ["circle", samples((t) => [20 * Math.cos(2 * Math.PI * t), 20 * Math.sin(2 * Math.PI * t)])],
  ["spiral", samples((t) => [(3 + 15 * t) * Math.cos(5 * Math.PI * t), (3 + 15 * t) * Math.sin(5 * Math.PI * t)])],
  ["wobble", samples((t) => [-40 + 80 * t, 9 * Math.sin((80 * t) / 13) + 0.18 * Math.sin(80 * t * 2.1)], 0.08)],
  [
    "square",
    samples((t) => {
      const d = (12 + 120 * t) % 120;
      const [side, u] = [Math.floor(d / 30), d % 30];
      const [x, y] = ([[u, 0], [30, u], [30 - u, 30], [0, 30 - u]] as Pt[])[side];
      return [x - 15, y - 15];
    }),
  ],
];

const toLine = (p: Pt, line: readonly Pt[]) => Math.min(...line.slice(1).map((b, i) => distToSegment(p, line[i], b)));
/** Points every 0.1 mm along a line. */
const dense = (line: readonly Pt[]) =>
  line.slice(1).flatMap((b, i) => {
    const a = line[i];
    const k = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1));
    return Array.from({ length: k + 1 }, (_, j) => [a[0] + ((b[0] - a[0]) * j) / k, a[1] + ((b[1] - a[1]) * j) / k] as Pt);
  });

describe("a freehand stroke, the whole way to the stitches", () => {
  it(
    "300 samples become at most 25 points, all within 0.4 mm of the stroke",
    async () => {
      for (const [name, drawn] of STROKES) {
        await whenIdle();
        const doc = newDoc();
        useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], pen: null, tool: "select", realistic: false, design: null, notice: null, traceAssist: false, snapGrid: false });
        const canvas: TestCanvas = await mountCanvas();
        await act(async () => COMMANDS.find((c) => c.id === "tool.run")!.run());
        act(() => useFreehand.setState({ on: true, smooth: 3 }));
        expect(canvas.pxMm).toBeGreaterThan(0.2); // an ordinary zoom (real size)
        canvas.down(drawn[0]);
        for (const p of drawn.slice(1, -1)) canvas.move(p);
        canvas.up(drawn[drawn.length - 1]);
        canvas.key("Enter");
        await act(async () => {
          await new Promise((r) => setTimeout(r, 0));
          await whenIdle();
        });
        expect(useStore.getState().notice?.kind, name).not.toBe("error");
        const item = currentLayout()!.items[0] as Extract<ObjectItem, { kind: "run" }>;
        const nodes: PathNode[] = item.geometry.nodes;
        expect(nodes.length, name).toBeLessThanOrEqual(25);
        // What the pointer reported: whole screen pixels.
        const stroke = drawn.map((p) => canvas.onScreen(p));
        const curve = flatten(nodes);
        expect(Math.max(...stroke.map((p) => toLine(p, curve))), `${name}: samples to curve`).toBeLessThanOrEqual(0.4);
        expect(Math.max(...dense(curve).map((p) => toLine(p, stroke))), `${name}: curve to samples`).toBeLessThanOrEqual(0.4);
        // And what the engine sews: every needle point by the stroke (stitches to 0.1 mm).
        const design = useStore.getState().design!;
        const { x, y, kind } = design.records;
        const sewn = kind.map((k, i) => (k === Kind.Stitch ? ([x[i], y[i]] as Pt) : null)).filter((p): p is Pt => !!p);
        expect(sewn.length, name).toBeGreaterThan(20);
        expect(Math.max(...sewn.map((p) => toLine(p, stroke))), `${name}: stitches to stroke`).toBeLessThanOrEqual(0.45);        canvas.unmount();
      }
    },
    LONG_MS,
  );
});
