import { describe, expect, it, vi } from "vitest";
import { dispatchKey, formatShortcut, matchesShortcut } from "./commands";

const key = (k: string, mods: Partial<Record<"ctrlKey" | "metaKey" | "shiftKey" | "altKey", boolean>> = {}) => ({
  key: k,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  altKey: false,
  ...mods,
});

describe("shortcuts", () => {
  it("maps Mod to Ctrl on Windows and Cmd on Mac", () => {
    expect(matchesShortcut(key("o", { ctrlKey: true }), "Mod+O", false)).toBe(true);
    expect(matchesShortcut(key("o", { metaKey: true }), "Mod+O", false)).toBe(false);
    expect(matchesShortcut(key("o", { metaKey: true }), "Mod+O", true)).toBe(true);
  });

  it("requires exact modifiers", () => {
    expect(matchesShortcut(key("o"), "Mod+O", false)).toBe(false);
    expect(matchesShortcut(key("S", { ctrlKey: true, shiftKey: true }), "Mod+S", false)).toBe(false);
    expect(matchesShortcut(key("S", { ctrlKey: true, shiftKey: true }), "Mod+Shift+S", false)).toBe(true);
    expect(matchesShortcut(key("f", { ctrlKey: true }), "F", false)).toBe(false);
  });

  it("handles named keys", () => {
    expect(matchesShortcut(key(" "), "Space", false)).toBe(true);
    expect(matchesShortcut(key("ArrowLeft"), "ArrowLeft", false)).toBe(true);
    expect(matchesShortcut(key("ArrowLeft", { shiftKey: true }), "Shift+ArrowLeft", false)).toBe(true);
  });

  it("formats for display", () => {
    expect(formatShortcut("Mod+Shift+S", false)).toBe("Ctrl+Shift+S");
    expect(formatShortcut("Mod+Shift+S", true)).toBe("⌘⇧S");
  });

  it("dispatches to the first enabled match", () => {
    const run = vi.fn();
    const off = vi.fn();
    const cmds = [
      { id: "a", title: "A", shortcut: "F", run: off, enabled: () => false },
      { id: "b", title: "B", shortcut: "J", run },
    ];
    expect(dispatchKey(key("f"), cmds)).toBe(false);
    expect(dispatchKey(key("j"), cmds)).toBe(true);
    expect(off).not.toHaveBeenCalled();
    expect(run).toHaveBeenCalledOnce();
  });

  it("understands + as a key", () => {
    expect(matchesShortcut(key("+", { shiftKey: true }), "Shift++", false)).toBe(true);
    expect(matchesShortcut(key("+"), "+", false)).toBe(true);
    expect(matchesShortcut(key("="), "Shift++", false)).toBe(false);
  });

  it("skips a disabled command to reach the next one with the same key", () => {
    const run = vi.fn();
    const cmds = [
      { id: "a", title: "A", shortcut: "Escape", run: vi.fn(), enabled: () => false },
      { id: "b", title: "B", shortcut: "Escape", run },
    ];
    expect(dispatchKey(key("Escape"), cmds)).toBe(true);
    expect(run).toHaveBeenCalledOnce();
  });
});
