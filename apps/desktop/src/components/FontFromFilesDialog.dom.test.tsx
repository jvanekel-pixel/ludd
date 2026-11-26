// @vitest-environment jsdom
/** "Make a stitch font from letter files…" (P5-C1) with a fake engine: files without a character
 *  or sharing one are flagged, a character can be typed over, Save waits while one is used twice,
 *  the preview stands the letters on a baseline, and nudges are sent. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, whenIdle } from "../actions";
import "../cmd";
import { DialogHost } from "../dialogs";
import { RpcError } from "../engine/rpc";
import { useStore } from "../store";
import { autoDrop, fontMetrics, previewText, type LetterFile } from "./FontFromFilesDialog";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

beforeAll(() => {
  // jsdom has the <dialog> element but not showModal() or close(): enough of both for the app.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

// ---------------------------------------------------------------- a fake engine

const file = (name: string, guess: string, w: number, h: number): LetterFile => ({
  path: `/letters/${name}`,
  name,
  guess,
  thumb: `data:image/png;base64,${name}`,
  width_mm: w,
  height_mm: h,
  stitches: 40,
  colors: 1,
});

const FILES: LetterFile[] = [
  file("Set_H.pes", "H", 6, 10),
  file("Set_a.pes", "a", 5, 7),
  file("Set_g.pes", "g", 5, 10),
  file("Set_h2.pes", "H", 6, 10), // the same character twice
  file("Set_leaf.pes", "", 20, 20), // no character
  { ...file("Set_torn.pes", "", 0, 0), thumb: "", stitches: 0, colors: 0, error: "Couldn't read Set_torn.pes: no stitches found" },
];

const calls: { method: string; params: Record<string, unknown> }[] = [];
let scanFails: string | null = null;
const engine = {
  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    calls.push({ method, params });
    if (method === "fonts.scan_letter_files") {
      if (scanFails) throw new RpcError(-32000, scanFails);
      return { files: FILES, common: { prefix: "Set_", suffix: "" } } as T;
    }
    if (method === "fonts.build_from_files")
      return { path: "/data/fonts/Mine.luddfont", glyphs: (params.letters as unknown[]).length, cap_height_mm: 10, folder: "/data/fonts" } as T;
    if (method === "fonts.list") return [{ family: "Mine", style: "Stitch font", path: "/data/fonts/Mine.luddfont", index: 0, kind: "stitch", made_of: "stitches" }] as T;
    return null as T;
  },
};
const sent = (method: string) => calls.filter((c) => c.method === method).map((c) => c.params);

// ---------------------------------------------------------------- the page

let root: Root | null = null;
let host: HTMLElement | null = null;

beforeEach(async () => {
  await whenIdle();
  calls.length = 0;
  scanFails = null;
  useStore.setState({ engine: engine as never, dialog: null, fonts: null, notice: null });
  vi.spyOn(window, "prompt").mockReturnValue("/letters");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(<DialogHost />));
  await act(async () => command("text.fontFromFiles").run());
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  vi.restoreAllMocks();
});

const dialog = () => host!.querySelector<HTMLDialogElement>("dialog");
const button = (label: string) => [...host!.querySelectorAll<HTMLButtonElement>("button")].find((b) => b.textContent === label)!;
const saveButton = () => button("Save font");
const box = (name: string) => host!.querySelector<HTMLInputElement>(`input[aria-label="Character for ${name}"]`)!;
const cell = (name: string) => box(name)?.closest("li") ?? [...host!.querySelectorAll("li")].find((li) => li.textContent!.includes(name))!;
const nameBox = () => host!.querySelector<HTMLInputElement>("input[aria-label='Font name']")!;
const letter = (char: string) => host!.querySelector<SVGImageElement>(`svg image[data-char="${CSS.escape(char)}"]`);
const num = (el: Element, attr: string) => Number(el.getAttribute(attr));
const bottomOf = (char: string) => num(letter(char)!, "y") + num(letter(char)!, "height");

async function click(el: Element) {
  await act(async () => {
    el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await whenIdle();
    await new Promise((r) => setTimeout(r, 0));
  });
}

function type(input: HTMLInputElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function press(target: EventTarget, key: string) {
  const e = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  await act(async () => {
    target.dispatchEvent(e);
    await whenIdle();
  });
  return e;
}

const chooseFolder = () => click(button("Choose folder…"));

describe("make a stitch font from letter files", () => {
  it("shows every file with the character guessed from its name, and flags the rest", async () => {
    expect(dialog()?.open).toBe(true);
    expect(dialog()!.textContent).toContain("Only make fonts from designs you're allowed to use this way.");
    expect(saveButton().disabled).toBe(true);
    await chooseFolder();
    expect(sent("fonts.scan_letter_files")).toEqual([{ folder: "/letters" }]);
    expect(host!.querySelectorAll("dialog li")).toHaveLength(6);
    expect(["Set_H.pes", "Set_a.pes", "Set_g.pes", "Set_h2.pes", "Set_leaf.pes"].map((n) => box(n).value)).toEqual(["H", "a", "g", "H", ""]);
    expect(cell("Set_H.pes").textContent).toContain("H is used twice");
    expect(cell("Set_h2.pes").textContent).toContain("H is used twice");
    expect(dialog()!.textContent).toContain("H is used twice: change one, or clear its box to leave it out.");
    expect(cell("Set_a.pes").textContent).not.toContain("twice");
    expect(cell("Set_leaf.pes").textContent).toContain("No character: left out");
    expect(box("Set_torn.pes")).toBeNull(); // nothing to type for a file that can't be read
    expect(cell("Set_torn.pes").textContent).toContain("no stitches found");
  });

  it("Save waits while a character is used twice, and for a name", async () => {
    await chooseFolder();
    type(nameBox(), "Mine");
    expect(saveButton().disabled).toBe(true);
    expect(saveButton().title).toContain("used twice");
    // Typing next to the old character replaces it.
    type(box("Set_h2.pes"), "HI");
    expect(box("Set_h2.pes").value).toBe("I");
    expect(host!.textContent).not.toContain("is used twice");
    expect(saveButton().disabled).toBe(false);
    type(box("Set_h2.pes"), "H");
    expect(saveButton().disabled).toBe(true);
    type(box("Set_h2.pes"), ""); // left out instead
    expect(saveButton().disabled).toBe(false);
    type(nameBox(), "  ");
    expect(saveButton().disabled).toBe(true);
  });

  it("stands the preview's letters on the baseline, hanging and nudged ones too", async () => {
    await chooseFolder();
    const baseline = host!.querySelector("svg line.baseline")!;
    expect([num(baseline, "y1"), num(baseline, "y2")]).toEqual([0, 0]);
    // "Hamburg 123" with what's there.
    expect([...host!.querySelectorAll("svg image")].map((i) => i.getAttribute("data-char"))).toEqual(["H", "a", "g"]);
    expect(bottomOf("H")).toBeCloseTo(0, 3);
    expect(bottomOf("a")).toBeCloseTo(0, 3);
    expect(num(letter("g")!, "y")).toBeCloseTo(-7, 3); // its top level with the a's
    expect(bottomOf("g")).toBeCloseTo(3, 3);
    expect(num(letter("a")!, "x")).toBeGreaterThan(num(letter("H")!, "x") + 6);

    await click(letter("g")!);
    await click(button("Nudge down"));
    await click(button("Nudge down"));
    expect(bottomOf("g")).toBeCloseTo(3.4, 3);
    await click(button("Nudge up"));
    expect(bottomOf("g")).toBeCloseTo(3.2, 3);
    expect(dialog()!.textContent).toContain("0.2 mm down");
    await click(button("Put back"));
    expect(bottomOf("g")).toBeCloseTo(3, 3);
    // The arrow keys nudge the picked letter too.
    await press(host!.querySelector("[aria-label='Preview on the baseline']")!, "ArrowUp");
    expect(bottomOf("g")).toBeCloseTo(2.8, 3);

    // A letter that isn't in the sample is added to it when you pick it from the list.
    type(box("Set_leaf.pes"), "&");
    await click(cell("Set_leaf.pes").querySelector("button")!);
    expect(letter("&")).not.toBeNull();
  });

  it("saves the named letters, with a nudge only where there is one, then lists the font again", async () => {
    await chooseFolder();
    type(box("Set_h2.pes"), "I");
    await click(letter("g")!);
    await click(button("Nudge down"));
    type(nameBox(), " Mine ");
    type(host!.querySelector<HTMLInputElement>("input[aria-label='Letter gap']")!, "12");
    await click(saveButton());
    expect(sent("fonts.build_from_files")).toEqual([
      {
        letters: [
          { path: "/letters/Set_H.pes", char: "H" },
          { path: "/letters/Set_a.pes", char: "a" },
          { path: "/letters/Set_g.pes", char: "g", dy_mm: 3.2 },
          { path: "/letters/Set_h2.pes", char: "I" },
        ],
        name: "Mine",
        gap_pct: 12,
        dest: "",
      },
    ]);
    expect(dialog()).toBeNull();
    expect(useStore.getState().dialog).toBeNull();
    expect(sent("fonts.list")).toHaveLength(1);
    expect(useStore.getState().fonts?.[0].made_of).toBe("stitches");
    expect(useStore.getState().notice?.text).toContain("Mine");
  });

  it("a letter gap that isn't a number holds Save", async () => {
    await chooseFolder();
    type(box("Set_h2.pes"), "");
    type(nameBox(), "Mine");
    for (const bad of ["", "500", "abc"]) {
      type(host!.querySelector<HTMLInputElement>("input[aria-label='Letter gap']")!, bad);
      expect(saveButton().disabled, bad).toBe(true);
    }
  });

  it("says why the files couldn't be read", async () => {
    scanFails = "No embroidery files in that folder.";
    await chooseFolder();
    expect(dialog()!.textContent).toContain("No embroidery files in that folder.");
    expect(saveButton().disabled).toBe(true);
  });

  it("Esc in a box puts back what it said, and the next Esc closes the dialog", async () => {
    await chooseFolder();
    const input = box("Set_a.pes");
    await act(async () => input.focus());
    type(input, "A");
    expect((await press(input, "Escape")).defaultPrevented).toBe(true);
    expect(box("Set_a.pes").value).toBe("a");
    expect(dialog()?.open).toBe(true);
    await press(dialog()!, "Escape");
    expect(dialog()).toBeNull();
    expect(useStore.getState().dialog).toBeNull();
  });
});

// The same rules as the engine's (engine/threadline_engine/lettering/fontbuild.py, tested there).
describe("lining letters up in the preview", () => {
  const heights = (h: Record<string, number>) => Object.entries(h).map(([char, height]) => ({ char, height }));

  it("takes the capital height from capitals and digits, else from the small letters", () => {
    expect(fontMetrics(heights({ H: 10, I: 14, "7": 11 })).cap).toBe(11);
    expect(fontMetrics(heights({ H: 10, I: 11, a: 7, b: 20 })).cap).toBe(10.5);
    expect(fontMetrics(heights({ a: 7, b: 10, d: 10.4 })).cap).toBeCloseTo(10.2, 6);
    expect(fontMetrics(heights({ a: 6.8, o: 6.8 })).cap).toBe(10);
    expect(fontMetrics(heights({ H: 10 })).small).toBeCloseTo(6.8, 6);
    expect(fontMetrics(heights({ H: 10, x: 7 })).small).toBe(7);
  });

  it("hangs and lifts letters as the font will", () => {
    expect(autoDrop("H", 10, 10, 7)).toBe(0);
    expect(autoDrop("g", 10, 10, 7)).toBe(3);
    expect(autoDrop(",", 3, 10, 7)).toBe(1.5);
    expect(autoDrop("'", 3, 10, 7)).toBe(-7);
    expect(autoDrop("-", 1, 10, 7)).toBe(-4.5);
  });

  it("previews Hamburg 123 with the letters there are, in either case", () => {
    expect(previewText(new Set("ABGHMRU12"), "")).toBe("HAMBURG 12");
    expect(previewText(new Set("Hag"), "")).toBe("Hag");
    expect(previewText(new Set("xyz"), "")).toBe("xyz");
    expect(previewText(new Set("Hag&"), "&")).toBe("Hag &");
  });
});
