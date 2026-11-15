import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { COMMANDS } from "./actions";

// The help agent answers from docs/LUDD-KNOWLEDGE-BASE.md: every command must be in its command
// table, with the shortcut the app uses. Run `python scripts/kb_commands.py` after changing COMMANDS.
const kb = readFileSync(resolve(__dirname, "../../../docs/LUDD-KNOWLEDGE-BASE.md"), "utf-8");

describe("the knowledge base", () => {
  it("lists every command with its shortcut", () => {
    const missing = COMMANDS.filter((c) => !kb.includes(`| \`${c.shortcut.replace(/\|/g, "\|")}\` | \`${c.id}\` |`)).map((c) => `${c.id} (${c.shortcut})`);
    expect(missing, "run python scripts/kb_commands.py").toEqual([]);
  });

  it("names the version the app is", () => {
    const conf = JSON.parse(readFileSync(resolve(__dirname, "../src-tauri/tauri.conf.json"), "utf-8")) as { version: string };
    expect(kb).toContain(`**${conf.version}**`);
  });
});
