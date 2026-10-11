/**
 * Command registry. Every user action is a command with a shortcut, so the
 * keyboard handler, toolbar and (later) command palette share one list.
 * Shortcut syntax: "Mod+Shift+S", "Space", "ArrowLeft", "F". Mod = Ctrl, or Cmd on macOS.
 */

export type Command = {
  id: string;
  title: string;
  shortcut: string;
  run: () => void;
  enabled?: () => boolean;
};

const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">;

export function matchesShortcut(e: KeyLike, shortcut: string, mac = isMac()): boolean {
  // "+" itself can be the key: "+", "Shift++".
  const plusKey = shortcut === "+" || shortcut.endsWith("++");
  const parts = (plusKey ? shortcut.slice(0, -1) : shortcut).split("+").filter(Boolean);
  const key = plusKey ? "+" : parts.pop()!;
  const want = new Set(parts);
  const mod = mac ? e.metaKey : e.ctrlKey;
  const other = mac ? e.ctrlKey : e.metaKey;
  if (want.has("Mod") !== mod || other) return false;
  if (want.has("Shift") !== e.shiftKey) return false;
  if (want.has("Alt") !== e.altKey) return false;
  const pressed = e.key === " " ? "Space" : e.key;
  return pressed.length === 1 ? pressed.toUpperCase() === key.toUpperCase() : pressed === key;
}

/** Human-readable shortcut for tooltips: "Ctrl+Shift+S" / "⌘⇧S". */
export function formatShortcut(shortcut: string, mac = isMac()): string {
  if (!mac) return shortcut.replace("Mod", "Ctrl");
  return shortcut
    .replace("Mod+", "⌘")
    .replace("Shift+", "⇧")
    .replace("Alt+", "⌥");
}

/** Run the first enabled command for a key event (several can share a key, e.g. Esc). Returns true if one ran. */
export function dispatchKey(e: KeyLike, commands: readonly Command[]): boolean {
  const cmd = commands.find((c) => matchesShortcut(e, c.shortcut) && (!c.enabled || c.enabled()));
  if (!cmd) return false;
  cmd.run();
  return true;
}
