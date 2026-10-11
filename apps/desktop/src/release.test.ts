import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

/**
 * The installed app runs under a strict content security policy (no 'unsafe-eval'). PixiJS needs
 * its no-eval add-on there, or the design area stays blank; the dev server doesn't show this.
 */
describe("installed app", () => {
  const conf = JSON.parse(readFileSync(new URL("../src-tauri/tauri.conf.json", import.meta.url), "utf8"));
  const csp: string = conf.app.security.csp;

  it("keeps a strict security policy", () => {
    expect(csp).not.toContain("unsafe-eval");
  });

  it("loads PixiJS's no-eval add-on before anything draws", () => {
    const main = readFileSync(new URL("./main.tsx", import.meta.url), "utf8");
    const firstImport = main.indexOf("import ");
    expect(main.indexOf('import "pixi.js/unsafe-eval"')).toBe(firstImport);
  });
});
