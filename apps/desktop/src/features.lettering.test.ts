import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { nameFileStem, textOnLineItem } from "./features";
import type { PathNode, TextItem } from "./design/types";

const text = (patch: Partial<TextItem> = {}): TextItem => ({
  id: "t1",
  kind: "text",
  text: "Hello",
  font: { path: "C:/Windows/Fonts/arial.ttf", index: 0, family: "Arial", style: "Regular" },
  size_mm: 10,
  spacing_mm: 0,
  style: "satin",
  shape: { type: "line" },
  monogram: false,
  thread: { color: "#000000", name: "Black", brand: "", catalog: "" },
  transform: { x: 10, y: 5, rotate: 30, scale_x: 2, scale_y: 2, flip_x: true, flip_y: false },
  threads: [],
  ops: [],
  ...patch,
});

const line: PathNode[] = [
  [20, 50, "c"],
  [100, 50, "c"],
];

describe("Put the text on the line", () => {
  it("lets go of the text's turn, mirror and resize and centres it on the line", () => {
    const out = textOnLineItem(text(), line, false);
    if (typeof out === "string") throw new Error(out);
    expect(out.transform).toEqual({ x: 60, y: 50, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false });
    // The line's points, in the text's own frame: the letters land on the line drawn.
    expect(out.shape).toEqual({ type: "path", nodes: [[-40, 0, "c"], [40, 0, "c"]], closed: false });
    // The resize is kept in the letter height.
    expect(out.size_mm).toBe(20);
  });

  it("refuses a monogram and keeps the line", () => {
    expect(textOnLineItem(text({ monogram: true, text: "ABC" }), line, false)).toMatch(/monogram/i);
  });
});

describe("One file per name: file names", () => {
  it("cleans characters and device names Windows refuses", () => {
    expect(nameFileStem(" A/B ")).toBe("A_B");
    expect(nameFileStem("A:B")).toBe("A_B");
    expect(nameFileStem("con")).toBe("_con");
    expect(nameFileStem("Emma.")).toBe("Emma");
    expect(nameFileStem("...")).toBe("_");
    expect(nameFileStem("Zoë")).toBe("Zoë");
  });
});
