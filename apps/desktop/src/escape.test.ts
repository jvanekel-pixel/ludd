import { beforeEach, describe, expect, it } from "vitest";
import { COMMANDS } from "./actions";
import { dispatchKey } from "./commands";
import { heldCount, holdEscape, letGoNewest } from "./escape";
import { useStore } from "./store";
import { resolveTheme } from "./theme";

const esc = { key: "Escape", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false };

describe("Esc lets go", () => {
  beforeEach(() => {
    while (letGoNewest());
    useStore.setState({ pen: null, measure: null, tool: "select", selectedNode: null, selectedId: null, playing: false });
  });

  it("lets go of the newest held thing first, once per press", () => {
    const order: string[] = [];
    holdEscape(() => order.push("drag"));
    holdEscape(() => order.push("menu"));
    expect(letGoNewest()).toBe(true);
    expect(order).toEqual(["menu"]);
    expect(letGoNewest()).toBe(true);
    expect(letGoNewest()).toBe(false);
    expect(order).toEqual(["menu", "drag"]);
  });

  it("released holds are forgotten", () => {
    const release = holdEscape(() => {
      throw new Error("should not run");
    });
    release();
    expect(heldCount()).toBe(0);
    expect(letGoNewest()).toBe(false);
  });

  it("steps back one thing per press: shape, tool, point, selection, playback", () => {
    useStore.setState({
      tool: "fill",
      pen: { kind: "fill", a: [[0, 0, "c"]], b: [] } as never,
      selectedNode: { id: "x", list: "a", index: 0 } as never,
      playing: true,
    });
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().pen).toBeNull(); // the half-drawn shape goes
    expect(useStore.getState().tool).toBe("fill");
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().tool).toBe("select");
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().selectedNode).toBeNull();
    useStore.setState({ selectedId: "x" });
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().selectedId).toBeNull();
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().playing).toBe(false);
  });

  it("stops measuring before anything else is let go", () => {
    useStore.setState({ measure: { imageId: "p", points: [[0, 0]] }, selectedId: "p" });
    dispatchKey(esc, COMMANDS);
    expect(useStore.getState().measure).toBeNull();
    expect(useStore.getState().selectedId).toBe("p");
  });
});

describe("theme", () => {
  it("follows the computer unless a choice is made", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });
});
