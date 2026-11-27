// @vitest-environment jsdom
/** The hint bar while freehand drawing is on (P7-C1): "Freehand · Smoothing" with a 1-to-5
 *  stepper, on the bars for drawing, a satin's edge fit and Trace Assist's suggestion. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import "../cmd";
import { setSmoothing, useFreehand } from "../feat/freehand";
import { useStore } from "../store";
import { DrawHint } from "./ToolRail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
const host = document.createElement("div");
function show() {
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<DrawHint />));
}
const text = () => host.textContent ?? "";
const button = (label: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!;

afterEach(() => {
  act(() => root?.unmount());
  host.remove();
  useFreehand.setState({ on: false });
  setSmoothing(3);
  useStore.setState({ tool: "select", pen: null, ghost: null, edgeFit: null });
});

describe("the drawing hint with freehand on", () => {
  it("shows Freehand · Smoothing with a 1-to-5 stepper, clickable", () => {
    useStore.setState({ tool: "run", pen: null });
    show();
    expect(text()).not.toContain("Freehand");
    act(() => useFreehand.setState({ on: true }));
    expect(text()).toContain("Freehand · Smoothing");
    expect(text()).toContain("Drag to draw");
    // The bar must take clicks (the plain hint lets the pointer through to the design).
    expect(host.querySelector(".draw-hint")!.className).toContain("auto-trace");
    for (let i = 0; i < 5; i++) act(() => button("More smoothing").click());
    expect(useFreehand.getState().smooth).toBe(5);
    expect(button("More smoothing").disabled).toBe(true);
    for (let i = 0; i < 5; i++) act(() => button("Less smoothing").click());
    expect(useFreehand.getState().smooth).toBe(1);
    expect(button("Less smoothing").disabled).toBe(true);
  });

  it("says how to draw each kind of shape, and keeps the stepper on the other drawing bars", () => {
    useFreehand.setState({ on: true });
    useStore.setState({ tool: "fill", pen: null });
    show();
    expect(text()).toContain("let go where you started");
    act(() => useStore.setState({ tool: "run", pen: { kind: "run", a: [], b: [], carveFor: "f" } }));
    expect(text()).toContain("carve");
    act(() => useStore.setState({ tool: "run", pen: { kind: "run", a: [[0, 0, "s"]], b: [] }, ghost: { point: [1, 1], alternatives: [], confidence: 1, corner: false, close: false, rails: null } }));
    expect(text()).toContain("Freehand · Smoothing");
    act(() =>
      useStore.setState({
        tool: "satin", ghost: null, pen: { kind: "satin", a: [[0, 0, "s"], [5, 0, "s"]], b: [] },
        edgeFit: { options: [{ label: "along the edge", nodes: [[0, 0, "s"], [5, 0, "s"]], closed: false }], index: 0, original: null },
      }),
    );
    expect(text()).toContain("Freehand · Smoothing");
    // Not with other tools.
    act(() => useStore.setState({ tool: "text", pen: null, edgeFit: null }));
    expect(text()).not.toContain("Freehand");
  });
});
