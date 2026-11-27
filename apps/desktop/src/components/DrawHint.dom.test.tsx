// @vitest-environment jsdom
/** The hint shown while drawing says what Esc does, including while carving lines (Shift+C). */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { useStore, type Pen } from "../store";
import { DrawHint } from "./ToolRail";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** The hint's text with the Line tool and this pen. */
function hint(pen: Pen | null): string {
  useStore.setState({ tool: "run", pen });
  const host = document.createElement("div");
  const root = createRoot(host);
  act(() => root.render(<DrawHint />));
  const text = host.textContent ?? "";
  act(() => root.unmount());
  return text;
}

describe("the drawing hint", () => {
  afterEach(() => useStore.setState({ tool: "select", pen: null }));

  it("says what Esc does, also while carving a line into a fill", () => {
    const carving: Pen = { kind: "run", a: [], b: [], carveFor: "f" };
    expect(hint(carving)).toContain("Click along the line to carve.");
    expect(hint(carving)).toContain("Esc stops carving.");
    expect(hint({ ...carving, a: [[1, 1, "s"]] })).toContain("Esc drops this line.");
    expect(hint({ kind: "run", a: [], b: [] })).toContain("Esc drops the shape.");
    expect(hint(null)).toContain("Esc goes back to Select.");
  });
});
