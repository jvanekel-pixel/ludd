import { describe, expect, it } from "vitest";
import { COMMANDS } from "./actions";
import { matchesShortcut } from "./commands";
import { canvasMenu, itemMenu, pictureMenu, tidySeparators, type ContextItem } from "./contextMenu";
import type { LayoutItem } from "./design/types";

const ids = (items: ContextItem[]) => items.flatMap((it) => (typeof it === "object" && "id" in it ? [it.id] : []));
const fill = { id: "f", kind: "fill" } as unknown as LayoutItem;
const text = { id: "t", kind: "text" } as unknown as LayoutItem;
const file = { id: "d", kind: "file" } as unknown as LayoutItem;

describe("right-click menus", () => {
  it("only offer commands that are in the registry (so each shows its shortcut)", () => {
    const known = new Set(COMMANDS.map((c) => c.id));
    for (const menu of [itemMenu(fill, false), itemMenu(fill, true), itemMenu(text, false), itemMenu(file, false), pictureMenu(), canvasMenu()]) {
      for (const id of ids(menu)) expect(known.has(id), id).toBe(true);
    }
  });

  it("fit the thing clicked", () => {
    expect(ids(itemMenu(fill, false))).toEqual(expect.arrayContaining(["object.thread", "object.hole", "arrange.earlier", "edit.copy", "arrange.centre"]));
    expect(ids(itemMenu(text, false))).toEqual(expect.arrayContaining(["object.thread", "text.edit"]));
    expect(ids(itemMenu(file, false))).toContain("edit.stitches");
    expect(ids(itemMenu(file, false))).not.toContain("object.thread");
    expect(ids(itemMenu(fill, true))).toEqual(expect.arrayContaining(["arrange.group", "object.merge", "object.cutOut"]));
    expect(ids(pictureMenu())).toEqual(expect.arrayContaining(["tool.autotrace", "arrange.pin"]));
    expect(ids(canvasMenu())).toEqual(expect.arrayContaining(["edit.paste", "tool.fill", "view.fit"]));
  });

  it("never show a separator first, last or twice in a row", () => {
    expect(tidySeparators(["separator", { id: "a" }, "separator", "separator", { id: "b" }, "separator"])).toEqual([{ id: "a" }, "separator", { id: "b" }]);
  });

  it("gives the new commands shortcuts that work with brackets and Shift", () => {
    const k = (key: string, code: string, shift = false) => ({ key, code, ctrlKey: true, metaKey: false, shiftKey: shift, altKey: false });
    expect(matchesShortcut(k("[", "BracketLeft"), "Mod+[", false)).toBe(true);
    expect(matchesShortcut(k("{", "BracketLeft", true), "Mod+Shift+[", false)).toBe(true);
    expect(matchesShortcut(k("{", "BracketLeft", true), "Mod+[", false)).toBe(false);
  });
});
