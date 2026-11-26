/** Phase 6 C2: a turning fill's angle lines. Adding, dragging and removing lines edits
 *  `angle_lines`; "Back to one angle" keeps the first line's angle. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const edits: ((o: ObjectItem) => ObjectItem)[] = [];
let items: ObjectItem[] = [];
const said: string[] = [];
vi.mock("../actions", async (original) => ({
  ...(await original<typeof import("../actions")>()),
  currentLayout: () => ({ items }),
  editObject: (_id: string, fn: (o: ObjectItem) => ObjectItem) => {
    edits.push(fn);
    return Promise.resolve(true);
  },
  info: (text: string) => void said.push(text),
}));

import { runCanvasMenu, runCanvasTool, type CanvasCtx } from "../canvas/hooks";
import type { FillParams, ObjectItem } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { useStore } from "../store";
import {
  addLine,
  angleLines,
  backToOneAngle,
  currentLine,
  finishAngleLine,
  moveLineEnd,
  oneAngleAgain,
  removeLine,
  replaceFirstLine,
  startAddAngle,
  type AngleLine,
} from "./angleLines";

const SQUARE = [
  [0, 0, "c"],
  [40, 0, "c"],
  [40, 40, "c"],
  [0, 40, "c"],
] as ObjectItem["geometry"] extends { outline: infer O } ? O : never;

function fill(params: FillParams = {}): ObjectItem {
  return {
    id: "f",
    kind: "fill",
    geometry: { outline: SQUARE },
    params: { angle_deg: 0, ...params },
    thread: { color: "#cc2222", name: "", catalog: "", brand: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  } as ObjectItem;
}

const A: AngleLine = [
  [5, 10],
  [15, 10],
];
const B: AngleLine = [
  [25, 20],
  [30, 25],
];
const C: AngleLine = [
  [10, 30],
  [10, 38],
];
const lines = (o: ObjectItem) => (o.params as FillParams).angle_lines;

describe("angle line edits", () => {
  it("adding the first extra line makes the fill's current direction line 1", () => {
    const o = addLine(fill({ angle_deg: 0 }), B);
    expect(lines(o)).toEqual([[[0, 20], [40, 20]], B]); // across the middle at 0 degrees
    expect(lines(addLine(o, C))).toEqual([[[0, 20], [40, 20]], B, C]);
    // Its purple dots, when it has them.
    const placed = fill({ angle_deg: 45, angle_line: [[0, 0], [40, 40]] });
    expect(lines(addLine(placed, B))![0]).toEqual([[0, 0], [40, 40]]);
    expect(currentLine(fill({ angle_deg: 90 }))).toEqual([[20, 0], [20, 40]]);
  });

  it("I with several lines replaces the first; dragging moves one end", () => {
    const o = fill({ angle_lines: [A, B] });
    expect(lines(replaceFirstLine(o, C))).toEqual([C, B]);
    expect(lines(moveLineEnd(o, 1, 0, [26.123, 19.999]))).toEqual([A, [[26.12, 20], B[1]]]);
    expect(replaceFirstLine(fill(), C)).toEqual(fill()); // one angle: I sets the angle as always
  });

  it("removing a line, and down to one goes back to one angle", () => {
    const three = fill({ angle_lines: [A, B, C] });
    expect(lines(removeLine(three, 1))).toEqual([A, C]);
    const one = removeLine(removeLine(three, 1), 0);
    expect(lines(one)).toBeUndefined();
    expect((one.params as FillParams).angle_deg).toBe(90); // C's
    expect(angleLines(one)).toEqual([]);
  });

  it("Back to one angle keeps the first line's angle", () => {
    const o = backToOneAngle(fill({ angle_deg: 0, angle_lines: [B, A] }));
    expect(lines(o)).toBeUndefined();
    expect((o.params as FillParams).angle_deg).toBe(45);
    expect((o.params as { angle_line?: AngleLine }).angle_line).toEqual(B);
  });
});

const ctx: CanvasCtx = { toMm: (e) => [e.clientX, e.clientY], pxMm: () => 0.1, redraw: () => undefined };
const pointer = (x: number, y: number, button = 0) => ({ clientX: x, clientY: y, button, pointerId: 1, target: null }) as unknown as PointerEvent;

function select(o: ObjectItem) {
  items = [o];
  useStore.setState({ selectedId: o.id, extraIds: [], tool: "select", pen: null, knife: null, measure: null, ruler: null, angleFor: null });
}

describe("the commands and the canvas", () => {
  beforeEach(() => {
    edits.length = 0;
    said.length = 0;
  });
  afterEach(() => {
    useStore.setState({ selectedId: null, angleFor: null });
    items = [];
  });

  it("Shift+I starts another line; drawing it adds it", () => {
    const o = fill({ angle_deg: 0 });
    select(o);
    startAddAngle();
    expect(useStore.getState().angleFor).toEqual({ id: "f", points: [], add: true });
    expect(finishAngleLine("f", B[0], B[1], true)).toBe(true);
    expect(lines(edits[0](o))).toEqual([[[0, 20], [40, 20]], B]);
    // I on a fill with one angle is left to set its angle, as always.
    expect(finishAngleLine("f", B[0], B[1], false)).toBe(false);
    // I with several lines sets the first.
    const two = fill({ angle_lines: [A, B] });
    select(two);
    expect(finishAngleLine("f", C[0], C[1], false)).toBe(true);
    expect(lines(edits[1](two))).toEqual([C, B]);
    // A line too short to give a direction is refused, with a word.
    expect(finishAngleLine("f", [1, 1], [1.2, 1], true)).toBe(true);
    expect(edits).toHaveLength(2);
    expect(said.at(-1)).toContain("longer line");
  });

  it("only Tatami fills turn", () => {
    select(fill({ pattern: "gradient" }));
    startAddAngle();
    expect(useStore.getState().angleFor).toBeNull();
    expect(said.at(-1)).toContain("Tatami");
  });

  it("dragging a line's dot moves it; Esc puts it back", () => {
    const o = fill({ angle_lines: [A, B] });
    select(o);
    expect(runCanvasTool("down", pointer(15.3, 10.2), ctx)).toBe(true); // A's second dot
    expect(heldCount()).toBe(1);
    runCanvasTool("move", pointer(18, 12), ctx);
    expect(runCanvasTool("up", pointer(18, 12), ctx)).toBe(true);
    expect(heldCount()).toBe(0);
    expect(lines(edits[0](o))).toEqual([[A[0], [18, 12]], B]);
    // Esc while dragging: nothing changes.
    runCanvasTool("down", pointer(25, 20), ctx);
    expect(letGoNewest()).toBe(true);
    expect(runCanvasTool("up", pointer(30, 30), ctx)).toBe(false);
    expect(edits).toHaveLength(1);
    // Away from the dots the canvas keeps its own clicks.
    expect(runCanvasTool("down", pointer(35, 5), ctx)).toBe(false);
  });

  it("right-clicking a line removes it; elsewhere the canvas's own menu opens", () => {
    const o = fill({ angle_lines: [A, B, C] });
    select(o);
    const menu = (x: number, y: number) => ({ clientX: x, clientY: y }) as MouseEvent;
    expect(runCanvasMenu(menu(10, 10.3), ctx)).toBe(true);
    expect(lines(edits[0](o))).toEqual([B, C]);
    expect(runCanvasMenu(menu(35, 5), ctx)).toBe(false);
  });

  it("the Angle box's Back to one angle", () => {
    const o = fill({ angle_lines: [B, A] });
    select(o);
    oneAngleAgain("f");
    expect((edits[0](o).params as FillParams).angle_deg).toBe(45);
  });
});
