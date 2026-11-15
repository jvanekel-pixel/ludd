import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({ save: async () => null, open: async () => null, message: async () => "no" }));
vi.mock("@tauri-apps/api/path", () => ({ resolveResource: async (p: string) => p }));

import { toDesignFrame } from "./features";

const T = { rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };

describe("Stitch editing: a move is kept in the design's own frame", () => {
  it("undoes the design's turn, resize and mirror", () => {
    expect(toDesignFrame(T, 3, 4)).toEqual([3, 4]);
    // Turned 90 degrees and doubled: 2 mm down on screen is 1 mm right in the design.
    const [x, y] = toDesignFrame({ ...T, rotate: 90, scale_x: 2, scale_y: 2 }, 0, 2);
    expect(x).toBeCloseTo(1);
    expect(y).toBeCloseTo(0);
    expect(toDesignFrame({ ...T, flip_x: true }, 2, 1)).toEqual([-2, 1]);
  });
});
