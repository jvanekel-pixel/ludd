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

  it("lets Tauri's fast messaging through (no CSP error and slow fallback on every start)", () => {
    expect(csp).toMatch(/connect-src [^;]*\bipc:/);
    expect(csp).toMatch(/connect-src [^;]*http:\/\/ipc\.localhost/);
  });

  it("declares the oldest macOS the bundled engine runs on (its libraries need macOS 14)", () => {
    expect(conf.bundle.macOS.minimumSystemVersion).toBe("14.0");
  });

  it("ships the licences of the libraries and fonts it includes", () => {
    expect(Object.values(conf.bundle.resources)).toContain("THIRD-PARTY-NOTICES.txt");
    const build = readFileSync(new URL("../../../scripts/build_engine.py", import.meta.url), "utf8");
    expect(build).toContain("make_notices.py");
  });

  it("loads PixiJS's no-eval add-on before anything draws", () => {
    const main = readFileSync(new URL("./main.tsx", import.meta.url), "utf8");
    const firstImport = main.indexOf("import ");
    expect(main.indexOf('import "pixi.js/unsafe-eval"')).toBe(firstImport);
  });
});
