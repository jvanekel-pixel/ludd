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

/** Every command, in dispatch order. actions.ts registers the core list; cmd/*.ts add theirs. */
export const COMMANDS: Command[] = [];

/** Add commands after the ones already there, or ahead of them (`first`: for a mode that must
 *  claim Enter, Tab or Delete before the core commands do). */
export function registerCommands(list: Command[], opts: { first?: boolean } = {}): void {
  const ids = new Set(COMMANDS.map((c) => c.id));
  for (const c of list) {
    if (ids.has(c.id)) throw new Error(`Command registered twice: ${c.id}`);
    ids.add(c.id);
  }
  if (opts.first) COMMANDS.unshift(...list);
  else COMMANDS.push(...list);
}

const isMac = () => typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

type KeyLike = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"> & { code?: string };

/** The physical key's code for a letter, digit or bracket ("KeyA", "Digit1", "BracketLeft"). */
function codeFor(key: string): string | null {
  if (/^[A-Za-z]$/.test(key)) return `Key${key.toUpperCase()}`;
  if (/^[0-9]$/.test(key)) return `Digit${key}`;
  return { "[": "BracketLeft", "]": "BracketRight", ",": "Comma", ".": "Period", "-": "Minus", "=": "Equal" }[key] ?? null;
}

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
  if (pressed.length === 1 ? pressed.toUpperCase() === key.toUpperCase() : pressed === key) return true;
  // On a Mac, Option changes the character (Option+A types "å"), and Shift changes punctuation
  // (Shift+, types "<"): match those shortcuts by the key itself.
  const code = e.altKey || (e.shiftKey && !/^[A-Za-z0-9]$/.test(key)) ? codeFor(key) : null;
  return !!code && e.code === code;
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
