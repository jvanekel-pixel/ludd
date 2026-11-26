import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { COMMANDS } from "../actions";
import { itemMenu } from "../contextMenu";
import type { TextItem } from "../design/types";
import "./index";

describe("lettering commands", () => {
  it("are registered with their reserved shortcuts", () => {
    const want: Record<string, string> = {
      "text.letters": "Alt+Shift+A",
      "text.resetLetters": "Alt+Shift+Z",
      "text.fontFromFiles": "Mod+Alt+F",
      "text.saveTemplate": "Mod+Alt+P",
      "text.placement": "Alt+Shift+G",
    };
    for (const [id, shortcut] of Object.entries(want)) {
      const c = COMMANDS.find((x) => x.id === id);
      expect(c?.shortcut, id).toBe(shortcut);
      expect(COMMANDS.filter((x) => x.shortcut === shortcut).map((x) => x.id), shortcut).toEqual([id]);
    }
  });

  it("offers single letters and templates in a text's menu", () => {
    const ids = itemMenu({ kind: "text" } as TextItem, false).flatMap((it) => (it !== "separator" && "id" in it ? [it.id] : []));
    expect(ids).toEqual(expect.arrayContaining(["text.letters", "text.resetLetters", "text.saveTemplate"]));
  });
});
