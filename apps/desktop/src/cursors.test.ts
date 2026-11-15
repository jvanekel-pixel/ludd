import { describe, expect, it } from "vitest";
import { CURSOR_NAMES, cursorCss, cursorSvg, type CursorName } from "./cursors";

describe("LUDD's mouse pointers", () => {
  it("has a pointer for every drawing tool and kind of point", () => {
    for (const tool of ["run", "satin", "fill"]) for (const kind of ["s", "c", "l"]) expect(CURSOR_NAMES).toContain(`draw-${tool}-${kind}`);
    for (const n of ["arrow", "move", "point", "resize", "resize-nesw", "stretch-x", "stretch-y", "rotate", "guide-x", "guide-y", "grab", "grabbing", "text", "autotrace", "knife", "measure", "angle", "stitch", "busy"]) {
      expect(CURSOR_NAMES).toContain(n);
    }
  });

  it("gives each one a 32×32 drawing, a hot spot inside it and a system pointer to fall back on", () => {
    for (const name of CURSOR_NAMES) {
      const css = cursorCss(name);
      const svg = cursorSvg(name);
      if (svg === null) {
        expect(css).toMatch(/^[a-z-]+$/); // a system pointer (busy)
        continue;
      }
      expect(svg).toMatch(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="32" height="32"/);
      const m = css.match(/^url\("data:image\/svg\+xml,([^"]+)"\) (\d+) (\d+), ([a-z-]+)$/);
      expect(m, name).not.toBeNull();
      expect(decodeURIComponent(m![1])).toBe(svg);
      for (const v of [Number(m![2]), Number(m![3])]) expect(v >= 0 && v < 32, `${name} hot spot`).toBe(true);
    }
  });

  it("puts the hot spot of a precise pointer at the centre of its crosshair", () => {
    for (const name of ["precise", "text", "knife", "draw-fill-c"] as CursorName[]) expect(cursorCss(name)).toMatch(/\) 11 11, crosshair$/);
  });
});
