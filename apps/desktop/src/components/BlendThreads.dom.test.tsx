// @vitest-environment jsdom
/** Phase 6 C1: a blend's colors in the panel (BlendThreads) and the edits behind its buttons
 *  (design/blend.ts). */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));
const edits: ((o: ObjectItem) => ObjectItem)[] = [];
vi.mock("../actions", async (original) => ({
  ...(await original<typeof import("../actions")>()),
  editObject: (_id: string, fn: (o: ObjectItem) => ObjectItem) => {
    edits.push(fn);
    return Promise.resolve(true);
  },
}));

import { addBlendColor, MAX_BLEND_COLORS, removeBlendColor, setBlendColor, slotThreads, swapBlendColors } from "../design/blend";
import type { FillParams, ObjectItem, Thread } from "../design/types";
import { BlendThreads } from "./BlendThreads";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const t = (color: string, name = color): Thread => ({ color, name, catalog: "", brand: "" });
const RED = t("#cc2222", "Red");
const BLUE = t("#2222cc", "Blue");
const GOLD = t("#ccaa22", "Gold");

function fill(params: FillParams, threads: (Thread | null)[] = [], own = RED): ObjectItem {
  return {
    id: "f",
    kind: "fill",
    geometry: { outline: [] },
    params: { pattern: "blend", ...params },
    thread: own,
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads,
    ops: [],
  } as ObjectItem;
}

const colors = (o: ObjectItem) => slotThreads(o).map((x) => x.name);

describe("blend edits", () => {
  it("setting a color writes params.blend and clears that color's Order & colors change", () => {
    const o = setBlendColor(fill({ blend: [BLUE, GOLD] }, [null, t("#00ff00"), t("#123456")]), 1, t("#ffffff", "White"));
    expect((o.params as FillParams).blend!.map((x) => x.name)).toEqual(["White", "Gold"]);
    expect(o.threads).toEqual([null, null, t("#123456")]);
    expect(colors(o)).toEqual(["Red", "White", "#123456"]);
    // The shape's own color (0) is not a blend color: unchanged.
    const same = fill({ blend: [BLUE] });
    expect(setBlendColor(same, 0, GOLD)).toBe(same);
  });

  it("adds colors up to three in all, and removes the third", () => {
    const two = fill({ blend: [BLUE] });
    const three = addBlendColor(two);
    expect(colors(three)).toHaveLength(3);
    expect(MAX_BLEND_COLORS).toBe(3);
    expect(addBlendColor(three)).toBe(three);
    const back = removeBlendColor({ ...three, threads: [null, null, t("#00ff00")] }, 2);
    expect(colors(back)).toEqual(["Red", "Blue"]);
    expect(back.threads).toEqual([null, null]);
    // It always keeps a second color.
    expect(removeBlendColor(two, 1)).toBe(two);
  });

  it("swapping reverses what the shape sews, its own thread included, and turns the balance round", () => {
    const o = swapBlendColors(fill({ blend: [BLUE, GOLD], blend_balance: 0.4 }, [null, t("#00ff00", "Green")]));
    expect(colors(o)).toEqual(["Gold", "Green", "Red"]);
    expect(o.threads).toEqual([]);
    expect((o.params as FillParams).blend_balance).toBe(-0.4);
    expect(colors(swapBlendColors(swapBlendColors(fill({ blend: [BLUE] }))))).toEqual(["Red", "Blue"]);
  });
});

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  edits.length = 0;
});

function show(item: ObjectItem): HTMLElement {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<BlendThreads item={item} />));
  return host;
}

const button = (el: HTMLElement, text: string) => [...el.querySelectorAll("button")].find((b) => b.textContent === text);

describe("the blend's colors in the panel", () => {
  it("shows the second color's thread, Add a color, Swap the colors and Balance", () => {
    const el = show(fill({ blend: [BLUE] }));
    expect(el.querySelector('button[aria-label="Second color"]')?.textContent).toContain("Blue");
    expect(button(el, "Add a color")).toBeTruthy();
    expect(button(el, "Swap the colors")).toBeTruthy();
    expect(button(el, "Remove")).toBeUndefined();
    expect(el.querySelector<HTMLInputElement>('input[aria-label="Balance"]')?.value).toBe("0");
  });

  it("with three colors offers to remove the third and no more to add", () => {
    const el = show(fill({ blend: [BLUE, GOLD] }));
    expect(el.querySelector('button[aria-label="Third color"]')?.textContent).toContain("Gold");
    expect(button(el, "Add a color")).toBeUndefined();
    act(() => button(el, "Remove")!.click());
    expect(colors(edits[0](fill({ blend: [BLUE, GOLD] })))).toEqual(["Red", "Blue"]);
  });

  it("the buttons make the edits", () => {
    const item = fill({ blend: [BLUE] });
    const el = show(item);
    act(() => button(el, "Swap the colors")!.click());
    act(() => button(el, "Add a color")!.click());
    expect(colors(edits[0](item))).toEqual(["Blue", "Red"]);
    expect(colors(edits[1](item))).toHaveLength(3);
  });

  it("a blend without a second color says what to do", () => {
    const el = show(fill({ blend: [] }));
    expect(el.textContent).toContain("Add a second color");
    expect(button(el, "Swap the colors")).toBeUndefined();
  });
});
