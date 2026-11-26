// @vitest-environment jsdom
/** Phase 6 C2: the Angle box of a fill with several angle lines. */
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

import type { FillParams, ObjectItem } from "../design/types";
import { AngleBox } from "./AngleBox";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fill = (params: FillParams): ObjectItem =>
  ({
    id: "f",
    kind: "fill",
    geometry: { outline: [] },
    params,
    thread: { color: "#cc2222", name: "", catalog: "", brand: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads: [],
    ops: [],
  }) as ObjectItem;

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
  act(() => root!.render(<AngleBox item={item} set={() => undefined} />));
  return host;
}

const buttons = (el: HTMLElement) => [...el.querySelectorAll("button")].map((b) => b.textContent);

describe("the Angle box", () => {
  it("with several lines says how many it follows and offers one angle back", () => {
    const lines: FillParams["angle_lines"] = [
      [[0, 0], [10, 0]],
      [[20, 0], [30, 10]],
    ];
    const el = show(fill({ angle_deg: 0, angle_lines: lines }));
    expect(el.textContent).toContain("Follows 2 lines");
    expect(buttons(el)).toEqual(["Back to one angle", "Add another line (Shift+I)"]);
    act(() => [...el.querySelectorAll("button")][0].click());
    const back = edits[0](fill({ angle_deg: 0, angle_lines: lines })).params as FillParams;
    expect(back.angle_lines).toBeUndefined();
    expect(back.angle_deg).toBe(0);
  });

  it("with one angle offers another line on Tatami only", () => {
    expect(buttons(show(fill({ angle_deg: 30 })))).toContain("Add another line (Shift+I)");
    act(() => root?.unmount());
    expect(buttons(show(fill({ pattern: "gradient" })))).not.toContain("Add another line (Shift+I)");
  });

  it("another pattern shows its one angle, whatever lines Tatami left behind", () => {
    const lines: FillParams["angle_lines"] = [
      [[0, 0], [10, 0]],
      [[20, 0], [30, 10]],
    ];
    const el = show(fill({ pattern: "gradient", angle_deg: 30, angle_lines: lines }));
    expect(el.textContent).not.toContain("Follows");
    expect(el.querySelector('button[aria-label="More angle"]')).not.toBeNull();
    expect(buttons(el)).not.toContain("Back to one angle");
  });
});
