// @vitest-environment jsdom
/** QA pass 2, U8: the sewing-order row drag ends on a lost mouse-up and when the panel goes away. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { newDoc } from "../design/layout";
import type { Doc, ObjectItem } from "../design/types";
import { heldCount, letGoNewest } from "../escape";
import { useStore } from "../store";
import { InfoPanel } from "./InfoPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fill = (id: string): ObjectItem =>
  ({ id, kind: "fill", geometry: { outline: [[0, 0, "c"], [10, 0, "c"], [10, 10, "c"]] }, params: {}, thread: { color: "#111111", name: "", brand: "", catalog: "" },
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false }, threads: [], ops: [] }) as ObjectItem;

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  while (letGoNewest());
});

function show() {
  const d = newDoc();
  const doc: Doc = { layout: { ...d.layout, items: [fill("a"), fill("b")] }, images: [] };
  useStore.setState({ history: { past: [], present: doc, future: [] }, savedDoc: doc, selectedId: null, extraIds: [], design: null });
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<InfoPanel />));
}

function grab() {
  const grip = host!.querySelector<HTMLElement>('li[data-row="a"] .grip')!;
  act(() => {
    grip.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, button: 0 }));
  });
}

describe("sewing-order row drag", () => {
  it("a move with no button down ends the drag (the mouse-up was lost)", () => {
    show();
    grab();
    expect(heldCount()).toBe(1);
    expect(host!.querySelector(".design-list.reordering")).not.toBeNull();
    act(() => {
      window.dispatchEvent(new MouseEvent("pointermove", { buttons: 0, clientY: 0 }));
    });
    expect(heldCount()).toBe(0);
    expect(host!.querySelector(".design-list.reordering")).toBeNull();
  });

  it("the panel going away mid-drag lets go of Esc and the window listeners", () => {
    show();
    grab();
    expect(heldCount()).toBe(1);
    const removed = vi.spyOn(window, "removeEventListener");
    act(() => root!.unmount());
    root = null;
    expect(heldCount()).toBe(0);
    expect(removed.mock.calls.map((c) => c[0])).toEqual(expect.arrayContaining(["pointermove", "pointerup", "pointercancel", "blur"]));
    removed.mockRestore();
  });
});
