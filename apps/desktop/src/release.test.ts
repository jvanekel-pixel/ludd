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

/**
 * QA2 T6 (decision 7): each Tauri plugin is a Rust crate plus an npm package, and the two must be
 * on the same major.minor or the installer build fails. Dependabot bumps them one at a time.
 */
describe("Tauri plugin pairs", () => {
  const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
  const cargo = read("../src-tauri/Cargo.toml");
  const cargoLock = read("../src-tauri/Cargo.lock");
  const pkg = JSON.parse(read("../package.json"));
  const pnpmLock = read("../../../pnpm-lock.yaml");
  const majorMinor = (v: string) => /(\d+)\.(\d+)/.exec(v)?.slice(1, 3).join(".") ?? null;
  const npm: Record<string, string> = { ...pkg.dependencies, ...pkg.devDependencies };
  const pairs = Object.keys(npm)
    .filter((n) => n.startsWith("@tauri-apps/plugin-"))
    .map((n) => ({ npm: n, crate: `tauri-plugin-${n.slice("@tauri-apps/plugin-".length)}` }));

  it("finds the plugins", () => {
    expect(pairs.length).toBeGreaterThanOrEqual(4);
  });

  it.each(pairs)("$crate and $npm ask for the same major.minor", ({ npm: name, crate }) => {
    const want = new RegExp(String.raw`^${crate}\s*=\s*(?:"([^"]+)"|\{[^}]*version\s*=\s*"([^"]+)")`, "m").exec(cargo);
    expect(want, `${crate} missing from Cargo.toml`).not.toBeNull();
    const crateVersion = want![1] ?? want![2];
    expect(majorMinor(crateVersion), `${crate} = "${crateVersion}" must name a major.minor`).not.toBeNull();
    expect(majorMinor(crateVersion)).toBe(majorMinor(npm[name]));
  });

  it.each(pairs)("$crate and $npm are locked to the same major.minor", ({ npm: name, crate }) => {
    const locked = new RegExp(String.raw`name = "${crate}"\r?\nversion = "([^"]+)"`).exec(cargoLock);
    const npmLocked = new RegExp(String.raw`'${name}':\r?\n\s+specifier: [^\n]+\r?\n\s+version: (\d+\.\d+\.\d+)`).exec(pnpmLock);
    expect(locked, `${crate} missing from Cargo.lock`).not.toBeNull();
    expect(npmLocked, `${name} missing from pnpm-lock.yaml`).not.toBeNull();
    expect(majorMinor(locked![1])).toBe(majorMinor(npmLocked![1]));
  });
});
