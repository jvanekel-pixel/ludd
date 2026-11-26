// @vitest-environment jsdom
/** Placement guides (P5-D4): where designs go on common things, and the printed sheet. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command } from "../actions";
import "../cmd";
import { newDoc } from "../design/layout";
import { formatMeasure, PLACEMENTS } from "../design/placements";
import { Kind, type Design } from "../design/types";
import { DialogHost } from "../dialogs";
import { placementSheetHtml } from "../print";
import { useStore } from "../store";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ITEMS = ["Bath towel", "Hand towel", "Pillowcase", "Sheet hem", "Adult left chest", "Child left chest", "Tote bag", "Napkin corner", "Cap front"];
const BOTH_UNITS = /\d+(\.\d+)?( to \d+(\.\d+)?)? in \(\d+(\.\d+)?( to \d+(\.\d+)?)? cm\)/;
const NOTE = "A starting point: check on your item.";

const design: Design = {
  path: "x", name: "Emma", format: "layout",
  info: { stitches: 2, jumps: 0, trims: 0, stops: 0, color_changes: 0, colors: 1, width_mm: 50.8, height_mm: 25.4, bounds_mm: [0, 0, 50.8, 25.4] },
  threads: [{ color: "#1f3a93", name: "Navy", catalog: "", brand: "" }],
  blocks: [{ thread: 0, start: 0, end: 2 }],
  records: { x: [0, 50.8], y: [0, 25.4], kind: [Kind.Stitch, Kind.Stitch] },
};

beforeAll(() => {
  // jsdom has the <dialog> element but not showModal() or close().
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
});

let root: Root | null = null;
let host: HTMLElement | null = null;
const doc = newDoc();

beforeEach(() => {
  useStore.setState({ history: { past: [], present: doc, future: [] }, savedDoc: doc, design: null, dialog: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DialogHost />));
});

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  document.querySelectorAll("iframe").forEach((f) => f.remove());
  root = host = null;
});

const entries = () => [...host!.querySelectorAll<HTMLElement>("li[data-placement]")];
const openDialog = () => act(() => command("text.placement").run());

describe("placement guides", () => {
  it("placement dialog lists items with both units", () => {
    openDialog();
    expect(entries().map((e) => e.querySelector("h3")!.textContent)).toEqual(ITEMS);
    for (const e of entries()) {
      const measures = [...e.querySelectorAll("ul li")];
      expect(measures.length).toBeGreaterThan(0);
      for (const m of measures) expect(m.textContent).toMatch(BOTH_UNITS);
      expect(e.textContent).toContain(NOTE);
      expect(e.querySelector("svg")).not.toBeNull(); // a small drawing
      const print = e.querySelector("button")!;
      expect(print.textContent).toBe("Print a placement sheet");
      expect(print.getAttribute("aria-label")).toContain(e.querySelector("h3")!.textContent!);
    }
  });

  it("writes every measure in inches and centimeters", () => {
    expect(formatMeasure({ label: "", inches: [7, 9] })).toBe("7 to 9 in (18 to 23 cm)");
    expect(formatMeasure({ label: "", inches: [0.5, 0.75] })).toBe("0.5 to 0.75 in (1.3 to 1.9 cm)");
    expect(formatMeasure({ label: "", inches: 2.5 })).toBe("2.5 in (6.5 cm)");
    expect(new Set(PLACEMENTS.map((p) => p.id)).size).toBe(PLACEMENTS.length);
  });

  it("prints a sheet with the item's measurements, a crosshair and the design at real size", () => {
    useStore.setState({ design });
    openDialog();
    const hand = entries()[1];
    act(() => hand.querySelector("button")!.click());
    const sheet = document.querySelector("iframe")!.srcdoc;
    expect(sheet).toContain("Hand towel");
    expect(sheet).toContain("check on your item");
    for (const m of PLACEMENTS[1].measures) expect(sheet).toContain(formatMeasure(m));
    expect(sheet).toContain('class="cross"');
    expect(sheet).toContain('width="74.8mm"'); // the design, 1:1, with its margins
    expect(sheet).toContain("2.00 × 1.00 in");
    expect(sheet).toContain("1 inch"); // bars to check it printed at 100%
  });

  it("prints a crosshair on its own when no design is open", () => {
    const sheet = placementSheetHtml(PLACEMENTS[0], null, null, null);
    expect(sheet).toContain("Bath towel");
    expect(sheet).toContain('class="cross"');
    expect(sheet).toContain("25 mm");
  });

  it("changes nothing in the design, and closes", () => {
    openDialog();
    const close = [...host!.querySelectorAll<HTMLButtonElement>("dialog button")].find((b) => b.textContent === "Close")!;
    act(() => close.click());
    expect(useStore.getState().dialog).toBeNull();
    expect(useStore.getState().history).toEqual({ past: [], present: doc, future: [] });
  });
});
