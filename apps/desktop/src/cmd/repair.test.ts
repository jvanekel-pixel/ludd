/** The commands for repairs, stitch inserts, the hidden-stitching switch and the needle path view. */
import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "Cancel" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { command, COMMANDS } from "../actions";
import "./repair";
import { useStore } from "../store";

/** The ids, titles and shortcuts reserved in docs/phases/README.md. */
const RESERVED = [
  ["stitch.repair", "Repair this design…", "Mod+Alt+D"],
  ["stitch.removeHidden", "Remove stitches hidden under what's on top", "Alt+Shift+H"],
  ["stitch.declump", "Thin out dense spots", "Alt+Shift+D"],
  ["stitch.filterSmall", "Remove tiny stitches", "Alt+Shift+S"],
  ["stitch.densityLimit", "Limit density for this fabric", "Alt+Shift+L"],
  ["stitch.rebuild", "Rebuild stitches at this size", "Alt+Shift+R"],
  ["stitch.insert", "Insert a stitch here", "Insert"],
  ["stitch.insertJump", "Insert a jump here", "Shift+Insert"],
  ["stitch.lockJump", "Lock both sides of this jump", "Alt+Shift+T"],
  ["object.removeOverlap", "Remove stitching hidden under shapes on top", "Alt+Shift+O"],
  ["view.wireframe", "Needle path only", "Shift+P"],
];
const INSERTS = ["stitch.insert", "stitch.insertJump", "stitch.lockJump"];

const enabled = (id: string) => command(id).enabled?.() ?? true;
const engine = { call: async () => null };

describe("the repair commands", () => {
  it("the eleven are registered with their reserved titles and shortcuts", () => {
    expect(RESERVED.map(([id]) => [command(id)?.id, command(id)?.title, command(id)?.shortcut])).toEqual(RESERVED);
    // Nothing else answers to those keys.
    for (const [id, , key] of RESERVED) expect(COMMANDS.filter((c) => c.shortcut === key).map((c) => c.id), key).toEqual([id]);
  });

  it("wait for a design and the engine", () => {
    useStore.setState({ engine: null, design: null, stitchEdit: null });
    for (const [id] of RESERVED) expect(enabled(id), id).toBe(false);
    useStore.setState({ engine: engine as never, design: {} as never });
    for (const [id] of RESERVED.filter(([id]) => !INSERTS.includes(id))) expect(enabled(id), id).toBe(true);
  });

  it("insert and lock only work while editing stitches, so Shift+Insert still pastes elsewhere", () => {
    useStore.setState({ engine: engine as never, design: {} as never, stitchEdit: null });
    for (const id of INSERTS) expect(enabled(id), id).toBe(false);
    useStore.setState({ stitchEdit: { id: "a", selected: [] } });
    for (const id of INSERTS) expect(enabled(id), id).toBe(true);
    useStore.setState({ stitchEdit: null, design: null, engine: null });
  });
});
