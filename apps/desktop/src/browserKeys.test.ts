import { describe, expect, it } from "vitest";
import { isBrowserKey } from "./browserKeys";

const key = (key: string, mods: Partial<Record<"ctrlKey" | "metaKey" | "altKey" | "shiftKey", boolean>> = {}) => ({
  key,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  shiftKey: false,
  ...mods,
});

describe("browser keys in the installed app (QA tauri: F5 wiped the design)", () => {
  it("cancels reload, find, print and back", () => {
    expect(isBrowserKey(key("F5"))).toBe(true);
    expect(isBrowserKey(key("r", { ctrlKey: true }))).toBe(true);
    expect(isBrowserKey(key("R", { ctrlKey: true, shiftKey: true }))).toBe(true);
    expect(isBrowserKey(key("f", { ctrlKey: true }))).toBe(true);
    expect(isBrowserKey(key("p", { metaKey: true }))).toBe(true);
    expect(isBrowserKey(key("ArrowLeft", { altKey: true }))).toBe(true);
  });

  it("leaves typing, editing and LUDD's other keys alone", () => {
    for (const k of [key("r"), key("c", { ctrlKey: true }), key("v", { ctrlKey: true }), key("z", { ctrlKey: true }), key("ArrowLeft"), key("F1"), key("Escape")])
      expect(isBrowserKey(k)).toBe(false);
  });
});
