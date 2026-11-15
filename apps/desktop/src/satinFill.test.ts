import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { columnOutline } from "./actions";
import type { PathNode } from "./design/types";

describe("satin fill back to a shape", () => {
  it("joins the two sides into the outline, without doubling the shared tips", () => {
    const rail_a: PathNode[] = [[0, 0, "c"], [10, -3, "s"], [20, 0, "c"]];
    const rail_b: PathNode[] = [[0, 0, "c"], [10, 3, "s"], [20, 0, "c"]];
    expect(columnOutline({ rail_a, rail_b })).toEqual([[0, 0, "c"], [10, -3, "s"], [20, 0, "c"], [10, 3, "s"]]);
  });

  it("keeps both ends when the sides don't share them (a satin drawn by clicking both sides)", () => {
    const rail_a: PathNode[] = [[0, 0, "c"], [20, 0, "c"]];
    const rail_b: PathNode[] = [[0, 5, "c"], [20, 5, "c"]];
    expect(columnOutline({ rail_a, rail_b })).toHaveLength(4);
  });
});
