// @vitest-environment jsdom
/** P5-B1: the lettering panel offers Satin look, True satin and Fill, with a hint under True satin. */
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

const setText = vi.fn();
vi.mock("../../actions", () => ({
  setText: (...args: unknown[]) => setText(...args),
  command: () => ({ run: () => {}, enabled: () => true, shortcut: "" }),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import type { LayoutItemInfo, TextItem } from "../../design/types";
import { StyleControls, TRUE_SATIN_HINT, styleLabel } from "./StyleControls";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = host = null;
  setText.mockReset();
});

function show(style: TextItem["style"], path = "C:/Fonts/test.ttf", madeOf?: "stitches") {
  const item = { id: "t", kind: "text", text: "IOT", style, font: { path, index: 0, family: "Test", style: "Regular", made_of: madeOf } } as unknown as TextItem;
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<StyleControls item={item} info={{} as LayoutItemInfo} />));
  return host;
}

const buttons = (el: HTMLElement) => [...el.querySelectorAll<HTMLButtonElement>('[aria-label="Stitch look"] button')];

describe("StyleControls", () => {
  it("offers three looks and picks True satin", () => {
    const el = show("satin");
    expect(buttons(el).map((b) => b.textContent)).toEqual(["Satin look", "True satin", "Fill"]);
    expect(el.textContent).not.toContain(TRUE_SATIN_HINT);
    act(() => buttons(el)[1].click());
    expect(setText).toHaveBeenCalledWith("t", { style: "columns" });
  });

  it("explains True satin while it is chosen", () => {
    const el = show("columns");
    expect(buttons(el)[1].getAttribute("aria-pressed")).toBe("true");
    expect(el.textContent).toContain(TRUE_SATIN_HINT);
    expect(el.textContent).toContain("its own satin column that follows the stroke");
    expect(styleLabel({ style: "columns" } as TextItem)).toBe("True satin");
  });

  it("offers no start and end dots for letters made of stitches", () => {
    const el = show("satin", "C:/Fonts/mine.luddfont", "stitches");
    expect(el.textContent).toContain("sews the stitches from its letter file");
    expect(el.textContent).not.toContain("green (start)");
    const apart = [...el.querySelectorAll("button")].find((b) => b.textContent?.startsWith("Break into shapes"))!;
    expect(apart.disabled).toBe(true);
    expect(apart.title).toContain("no outlines to edit");
  });

  it("has no looks for a stitch font", () => {
    const el = show("columns", "C:/Fonts/test.luddfont");
    expect(buttons(el)).toHaveLength(0);
    expect(el.textContent).toContain("sews the stitches it was made with");
  });
});
