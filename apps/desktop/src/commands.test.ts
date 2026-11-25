import { describe, expect, it, vi } from "vitest";
import { CORE_COMMANDS, command } from "./actions";
import "./cmd";
import { COMMANDS, dispatchKey, formatShortcut, matchesShortcut, registerCommands, type Command } from "./commands";

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

  it("matches Shift with punctuation by the key itself (Shift+, types '<')", () => {
    expect(matchesShortcut({ ...key("<", { shiftKey: true }), code: "Comma" }, "Shift+,", false)).toBe(true);
    expect(matchesShortcut({ ...key("<"), code: "Comma" }, "Shift+,", false)).toBe(false);
    expect(matchesShortcut({ ...key("<", { shiftKey: true }), code: "Comma" }, ",", false)).toBe(false);
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

describe("the command registry", () => {
  const extra = (id: string): Command => ({ id, title: "A test command", shortcut: "Mod+Alt+Shift+F9", run: () => {} });

  it("registerCommands refuses a duplicate id", () => {
    const before = [...COMMANDS];
    expect(() => registerCommands([extra("stitch.deleteSelected")])).toThrow("Command registered twice: stitch.deleteSelected");
    // Twice in one list counts too, and a refused list adds nothing.
    expect(() => registerCommands([extra("test.twice"), extra("test.twice")])).toThrow("Command registered twice: test.twice");
    expect(COMMANDS).toEqual(before);
  });

  it("every command has a title and a shortcut", () => {
    expect(COMMANDS.filter((c) => !c.title.trim() || !c.shortcut.trim()).map((c) => c.id)).toEqual([]);
  });

  it("core commands keep their order", () => {
    expect(COMMANDS[0].id).toBe("stitch.deleteSelected");
    expect(COMMANDS.length).toBeGreaterThanOrEqual(167);
    expect(COMMANDS.filter((c) => CORE_COMMANDS.includes(c))).toEqual(CORE_COMMANDS);
  });

  it("adds feature commands after the core list, or ahead of it with first", () => {
    const after = extra("test.after");
    const ahead = extra("test.ahead");
    registerCommands([after]);
    registerCommands([ahead], { first: true });
    try {
      expect(COMMANDS[0]).toBe(ahead);
      expect(COMMANDS.at(-1)).toBe(after);
      expect(command("test.after")).toBe(after);
    } finally {
      for (const c of [after, ahead]) COMMANDS.splice(COMMANDS.indexOf(c), 1);
    }
  });
});
