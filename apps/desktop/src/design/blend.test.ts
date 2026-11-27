/** A blend's colors: what a new blend starts with, and the thread each of its colors sews in. */
import { describe, expect, it } from "vitest";
import { blendDefaults, secondColor, slotThreads } from "./blend";
import type { FillParams, ObjectItem, Thread } from "./types";

const t = (color: string, name = color): Thread => ({ color, name, catalog: "", brand: "" });

function fill(params: FillParams, own: Thread, threads: (Thread | null)[] = []): ObjectItem {
  return {
    id: "f",
    kind: "fill",
    geometry: { outline: [] },
    params,
    thread: own,
    transform: { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false },
    threads,
    ops: [],
  };
}

describe("blend colors", () => {
  it("starts with white, or navy on a light shape", () => {
    expect(secondColor(t("#cc0000")).name).toBe("White");
    expect(secondColor(t("#ffee55")).name).toBe("Navy");
  });

  it("choosing Blend gives a shape a second color only when it has none", () => {
    expect(blendDefaults(fill({}, t("#cc0000")))).toEqual({ blend: [t("#ffffff", "White")] });
    expect(blendDefaults(fill({ blend: [t("#00ff00")] }, t("#cc0000")))).toEqual({});
  });

  it("lists the thread each color sews in; a color changed in Order & colors wins", () => {
    const o = fill({ pattern: "blend", blend: [t("#00ff00"), t("#0000ff")] }, t("#cc0000"), [null, t("#123456")]);
    expect(slotThreads(o).map((x) => x.color)).toEqual(["#cc0000", "#123456", "#0000ff"]);
    expect(slotThreads(fill({ blend: [t("#00ff00")] }, t("#cc0000"))).map((x) => x.color)).toEqual(["#cc0000"]);
  });
});
