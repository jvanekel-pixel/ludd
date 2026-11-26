// @vitest-environment jsdom
/** The lettering panel's layout controls (P5-A1 to A4): each shows only when it applies, and an
 *  envelope is turned off on a curve with the reason as its tooltip. A fake engine. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { currentLayout, whenIdle } from "../../actions";
import "../../cmd";
import { newDoc } from "../../design/layout";
import type { Design, LayoutItem, LayoutItemInfo, LetterPart, TextItem } from "../../design/types";
import { letGoNewest } from "../../escape";
import { leaveLetterMode, pickLetter, useLetterMode } from "../../feat/letters";
import { useStore } from "../../store";
import { LayoutControls, LayoutMore } from "./LayoutControls";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const text = (patch: Partial<TextItem> = {}): TextItem => ({
  id: "t",
  kind: "text",
  text: "Happy",
  font: { path: "f.ttf", index: 0, family: "Test", style: "Regular" },
  size_mm: 10,
  spacing_mm: 0,
  style: "satin",
  shape: { type: "line" },
  monogram: false,
  thread: { color: "#000000", name: "Black", brand: "", catalog: "" },
  transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
  threads: [],
  ops: [],
  ...patch,
});

const part = (letter: number, kind = "fill"): LetterPart => ({
  index: letter, kind, look: kind === "fill" ? "satin" : kind, start: [0, 0], end: [1, 1], ring: [[0, 0], [1, 0], [1, 1]], letter, line: 0, run: 0,
});

const info = (parts: LetterPart[] = [part(0), part(1)]): LayoutItemInfo => ({
  id: "t", name: "t", kind: "text", center_mm: [0, 0], bounds_mm: [0, 0, 1, 1], source_size_mm: null, letters: parts, runs: [],
});

let parts: LetterPart[] = [part(0), part(1)];
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (method !== "layout.render") return null as T;
    const items = (params.layout as { items: LayoutItem[] }).items;
    return { path: "", name: "x", format: "layout", info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: items.map(() => info(parts)) } as T;
  },
};

function Harness() {
  const item = useStore((s) => s.history.present!.layout.items[0]) as TextItem;
  const shown = useStore((s) => s.design?.items?.[0]) ?? info();
  return (
    <>
      <div id="main">
        <LayoutControls item={item} info={shown} />
      </div>
      <div id="more">
        <LayoutMore item={item} info={shown} />
      </div>
    </>
  );
}

let root: Root | null = null;
let host: HTMLElement | null = null;

function unmount() {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
}

function show(patch: Partial<TextItem> = {}, letterParts: LetterPart[] = [part(0), part(1)]) {
  unmount();
  leaveLetterMode();
  parts = letterParts;
  const d = newDoc();
  const doc = { ...d, layout: { ...d.layout, items: [text(patch)] as LayoutItem[] } };
  const design = { info: {}, threads: [], blocks: [], records: { x: [], y: [], kind: [] }, items: [info(letterParts)] } as unknown as Design;
  useStore.setState({ engine: engine as never, history: { past: [], present: doc, future: [] }, savedDoc: doc, design, selectedId: "t", extraIds: [], tool: "select", units: "mm", stitchEdit: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<Harness />));
  return host;
}

beforeEach(async () => {
  await whenIdle();
  leaveLetterMode();
  while (letGoNewest());
});
afterEach(unmount);

const item = () => currentLayout()!.items[0] as TextItem;
const labels = (part: "main" | "more") => [...host!.querySelectorAll(`#${part} .acc-label`)].map((x) => x.textContent);
const button = (name: string) => [...host!.querySelectorAll("button")].find((b) => b.textContent === name || b.getAttribute("aria-label") === name);
const envelope = () => host!.querySelector<HTMLSelectElement>('select[aria-label="Envelope"]')!;
const stack = () => [...host!.querySelectorAll("label")].find((l) => l.textContent?.includes("Stack the letters (vertical)"));
const stackBox = () => stack()!.querySelector("input")!;

async function click(el: Element | undefined) {
  expect(el, "the button to click").toBeDefined();
  await act(async () => {
    (el as HTMLElement).click();
    await whenIdle();
  });
}

async function choose(select: HTMLSelectElement, value: string) {
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await whenIdle();
  });
}

describe("what shows under More options", () => {
  it("a straight line of text: slant, envelope and stacked letters, not alignment or line spacing", () => {
    show();
    expect(labels("more")).toEqual(["Slant", "Envelope"]);
    expect(envelope().disabled).toBe(false);
    expect([...envelope().options].map((o) => o.textContent)).toEqual(["None", "Bulge", "Pinch", "Pennant right", "Pennant left", "Wave", "Arch top", "Arch bottom"]);
    expect(stackBox().disabled).toBe(false);
  });

  it("two lines add Align and Line spacing", async () => {
    show({ text: "Happy\nBirthday" });
    expect(labels("more")).toEqual(["Align", "Line spacing", "Slant", "Envelope"]);
    expect(button("Center")?.getAttribute("aria-pressed")).toBe("true");
    await click(button("Left"));
    expect(item().align).toBe("left");
    expect(button("Left")?.getAttribute("aria-pressed")).toBe("true");
    await click(button("More line spacing"));
    expect(item().line_spacing).toBe(1.4);
    show({ text: "Happy\n  \n" }); // blank lines don't make it two
    expect(labels("more")).toEqual(["Slant", "Envelope"]);
  });

  it("on an arch the envelope and stacking are off, with the reason as their tooltip", () => {
    show({ text: "Happy\nBirthday", shape: { type: "arc_up", radius_mm: 40 } });
    expect(envelope().disabled).toBe(true);
    expect(envelope().title).toMatch(/straight text/i);
    expect(envelope().closest("[title]")!.getAttribute("title")).toMatch(/arch/);
    expect(stackBox().disabled).toBe(true);
    expect(stack()!.title).toMatch(/straight text/i);
    expect(labels("more")).toEqual(["Align", "Line spacing", "Slant", "Envelope"]); // lines go on circles
  });

  it("a circle or a drawn line takes one line, so alignment and spacing hide", () => {
    for (const [shape, words] of [[{ type: "circle", radius_mm: 40 }, /circle/], [{ type: "path", nodes: [] }, /line you drew/]] as const) {
      show({ text: "Happy\nBirthday", shape: shape as TextItem["shape"] });
      expect(labels("more")).toEqual(["Slant", "Envelope"]);
      expect(envelope().disabled).toBe(true);
      expect(envelope().title).toMatch(words);
    }
  });

  it("choosing an envelope shows its amount; None takes it off", async () => {
    show();
    await choose(envelope(), "wave");
    expect(item().envelope).toEqual({ type: "wave", amount: 0.5 });
    expect(labels("more")).toEqual(["Slant", "Envelope", "Amount"]);
    const slider = host!.querySelector<HTMLInputElement>('input[type="range"][aria-label="Envelope amount"]')!;
    expect(slider.value).toBe("0.5");
    await choose(envelope(), "");
    expect(item().envelope).toBeUndefined();
    expect(labels("more")).toEqual(["Slant", "Envelope"]);
  });

  it("stacked letters turn the envelope off, saying why, and have no alignment", async () => {
    show({ text: "Happy\nBirthday" });
    await click(stackBox());
    expect(item().vertical).toBe(true);
    expect(envelope().disabled).toBe(true);
    expect(envelope().title).toMatch(/Stack/);
    expect(labels("more")).toEqual(["Line spacing", "Slant", "Envelope"]); // lines are columns
    await click(stackBox());
    expect(item().vertical).toBeFalsy();
    expect(envelope().disabled).toBe(false);
  });

  it("slant leans the letters a degree at a time", async () => {
    show();
    await click(button("More slant"));
    expect(item().slant_deg).toBe(1);
    show({ slant_deg: 30 });
    expect(button("More slant")?.hasAttribute("disabled")).toBe(true);
  });

  it("a monogram has no lines or stacking, but can slant and be bent", () => {
    show({ text: "ABC", monogram: true, shape: { type: "arc_up", radius_mm: 40 } });
    expect(labels("more")).toEqual(["Slant", "Envelope"]);
    expect(stack()).toBeUndefined();
    expect(envelope().disabled).toBe(false); // a monogram is always straight
  });
});

describe("single letters", () => {
  it("the button turns the mode on, and a picked letter shows its settings", async () => {
    show();
    expect(labels("main")).toEqual([]);
    await click(button("Adjust single letters"));
    expect(useLetterMode.getState().id).toBe("t");
    expect(host!.querySelector("#main")!.textContent).toMatch(/Click a letter/);
    act(() => pickLetter(1));
    expect(labels("main")).toEqual(["Size", "Turn", "Thread", "Stitch angle"]);
    expect(host!.querySelector("#main")!.textContent).toMatch(/Letter 2 of 2/);
    expect(button("Put this letter back")?.hasAttribute("disabled")).toBe(true);
    await click(button("More size"));
    expect(item().letter_edits).toEqual({ "1": { scale: 1.05 } });
    await click(button("More turn"));
    expect(item().letter_edits).toEqual({ "1": { scale: 1.05, rotate: 5 } });
    await click(button("Put this letter back"));
    expect(item().letter_edits).toBeUndefined();
    await click(button("Done"));
    expect(useLetterMode.getState().id).toBeNull();
  });

  it("the stitch angle shows only for letters sewn across at an angle", async () => {
    for (const [patch, kind, shown] of [
      [{ style: "fill" }, "fill", true],
      [{ style: "columns" }, "fill", false],
      [{ font: { path: "f.luddfont", index: 0, family: "Mine", style: "" } }, "fill", true],
      [{ font: { path: "f.luddfont", index: 0, family: "Mine", style: "" } }, "stitches", false],
    ] as const) {
      show(patch as Partial<TextItem>, [part(0, kind)]);
      await click(button("Adjust single letters"));
      act(() => pickLetter(0));
      expect(labels("main").includes("Stitch angle"), JSON.stringify(patch)).toBe(shown);
    }
  });

  it("offers to put every letter back once one has changed", () => {
    show();
    expect(button("Put the letters back")).toBeUndefined();
    show({ letter_edits: { "0": { dx_mm: 1 } } });
    expect(button("Put the letters back")).toBeDefined();
  });
});
