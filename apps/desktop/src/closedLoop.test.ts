import { describe, expect, it } from "vitest";
import { closedLoop } from "./actions";
import type { PathNode } from "./design/types";

const sq: PathNode[] = [[0, 0, "l"], [10, 0, "l"], [10, 10, "l"], [0, 10, "l"]];

describe("a line that goes all the way round", () => {
  it("is a loop when closed, or when it ends where it began", () => {
    expect(closedLoop(sq, true)).toEqual(sq);
    expect(closedLoop([...sq, [0.3, 0.2, "l"]], false)).toEqual(sq);
  });

  it("isn't when it's open or too short", () => {
    expect(closedLoop(sq, false)).toBeNull();
    expect(closedLoop(sq.slice(0, 2), true)).toBeNull();
  });
});
