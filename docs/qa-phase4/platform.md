# QA phase 4: platform (tauri, packaging, CI tests)

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | packaging | updater-manifest skipped if any build leg fails | Fixed | `.github/workflows/release.yml` (`if: !cancelled() && create-release ok`), `docs/RELEASING.md` step 6 (re-run failed jobs only) | none possible offline (workflow) |
| Medium | packaging | Packaged engine needs macOS 14, app declares 10.13; no OS minimums documented | Fixed (docs part handed over) | `tauri.conf.json` `bundle.macOS.minimumSystemVersion: "14.0"`; minimums in `docs/RELEASING.md` | `src/release.test.ts` |
| Medium | packaging | Nothing ever runs the frozen engine; FFmpeg drop not verified | Fixed | new `scripts/smoke_engine.py` (ping, engine.info, formats, OpenCV auto-trace, clean `engine.shutdown` exit); `scripts/build_engine.py` runs it after freezing, fails if the spec edit can't apply, and fails if `opencv_videoio_ffmpeg` is in the PKG table of contents; so CI's Windows-installer job and every release leg run it | `engine/tests/test_packaging.py`; also run by hand on the current frozen Windows sidecar: passes |
| Medium | packaging | No single-instance handling, no macOS open-file event | Already fixed (single instance, C24) + Fixed (macOS `RunEvent::Opened`) | `src-tauri/src/lib.rs` | Rust unit tests in `lib.rs` (`cargo test --lib`, now in CI) |
| Medium | packaging | No third-party licence notices ship | Fixed (link from Settings handed over) | new `scripts/make_notices.py` (Python libs + Python itself + PyInstaller bootloader, npm runtime packages incl. OFL fonts, Rust crates from Cargo.lock), run by `build_engine.py` into `src-tauri/binaries/THIRD-PARTY-NOTICES.txt`; shipped via `bundle.resources` | `engine/tests/test_packaging.py`, `src/release.test.ts` |
| Medium | tauri | macOS: Finder double-click doesn't open the .ludd; Cmd+Q skips "Save your changes first?" | Fixed (not run: no Mac here) | `lib.rs`: `RunEvent::Opened` kept until the window asks (`launch_file`) or sent as `ludd:open-file`; on macOS the app menu's Quit is replaced by "Quit LUDD" (Cmd+Q) that closes the window the normal way, so the prompt runs | `lib.rs` tests (open-request queue); macOS menu code is not compiled on Windows: **check on the first Mac CI/release run** |
| Medium | tauri | Update check contacts GitHub 8 s after launch even after unticking the box | Fixed | `src/updates.ts`: prefs are read again when the check is due; nothing before the Welcome card is answered (waits, then checks if allowed) | `src/updates.test.ts` |
| Medium | tauri | F5 / browser right-click menu live in the installed app (reload loses the design, leaks an engine) | Fixed | new `src/browserKeys.ts` (cancels F5, Ctrl+R/F/G/P/U/J/H, F3, F7, Alt+Left/Right; right-click menu off outside text fields; stops the engine on `pagehide`), installed from `src/main.tsx` (one line, installed app only) | `src/browserKeys.test.ts` |
| Medium | tauri | Engine start needs a 10 s first ping after a 180 MB unpack | Already fixed (C25: 60 s first ping, restart) | `src/engine/sidecar.ts` | `sidecar.test.ts`, `manager.test.ts` |
| Medium | tauri | "One file per name" overwrites / merges files, reports "Saved N" | Handed over: features.ts owner | n/a | n/a |
| Medium | tauri | Zooming a 40k-stitch design is slow | Handed over: StitchCanvas owner | n/a | n/a |
| Medium | tests | All PES/JEF golden round trips skip in CI | Fixed | `engine/tests/test_golden.py` now always runs on the committed `samples/*.pes`/`*.jef` (fixtures/ added when present); JEF compares the shape allowing the new centring on export (another agent's change) | `test_committed_samples_are_tested` + 25 sample cases |
| Medium | tests | CI never runs or smoke-tests the frozen sidecar | Fixed (same as packaging smoke test) | `build_engine.py`, `ci.yml` | as above |
| Medium | tests | Snapshot test records a missing entry and passes, also in CI | Fixed | `engine/tests/test_digitize.py::test_snapshot` fails in CI (`CI` set) when a case has no recorded entry; locally it still records | checked with `CI=1`: no missing entries today |
| Medium | tests | CI covers only Windows + Apple-chip Mac | Fixed | `ci.yml` test matrix adds `macos-15-intel` and `ubuntu-22.04` (every release target) | CI |
| Low | packaging | Workflow hardening: tag-pinned actions, checkout keeps token, ci.yml no permissions, no tag/version guard | Fixed, except SHA pinning (Skipped: looking up commit SHAs needs the network) | `persist-credentials: false` on every checkout; `permissions: contents: read` in ci.yml; release fails at once if the tag isn't `v<version>` | n/a |
| Low | packaging | CI/release builds not locked | Fixed | `uv run --locked` in ci.yml/release.yml and root `package.json` `build:engine`; `cargo metadata --locked` check in both workflows; `uv lock --check --offline` passes | n/a |
| Low | packaging | Cargo.toml rust-version 1.77, deps need 1.90 | Fixed | `src-tauri/Cargo.toml` | `cargo check` |
| Low | packaging | .gitignore: tsbuildinfo, *.pfx/*.p12 | Fixed | `.gitignore` (`*.tsbuildinfo`, `*.password.txt`, `*.pfx`, `*.p12`, `*.p8`) | `git check-ignore` |
| Low | packaging | Docs out of step (USER-GUIDE 1.0.0 names, CLAUDE.md deps, RELEASING lockfiles) | Fixed (RELEASING) / Handed over (USER-GUIDE, CLAUDE.md, README) | `docs/RELEASING.md` step 1 | n/a |
| Low | packaging | Dev engine bridge accepts POSTs from any origin | Fixed | `vite-engine-bridge.ts` `allowedRequest`: Host must be localhost/127.0.0.1/[::1], Origin (if any) must be that same host; else 403 | `vite-engine-bridge.test.ts` |
| Low | packaging | CI never runs golden tests; snapshot records missing entry | Fixed (see tests rows) | | |
| Low | packaging | make_installer_art.py documented command fails | Fixed | docstring lists the extra libraries (checked: imports work offline) | n/a |
| Low | tauri | CSP has no connect-src: Tauri IPC falls back to postMessage with a CSP error | Fixed | `tauri.conf.json` CSP `connect-src 'self' ipc: http://ipc.localhost` | `src/release.test.ts` |
| Low | tauri | Offline "Check for updates" shows a raw networking error | Fixed | `src/updates.ts` `updateCheckError` | `src/updates.test.ts` |
| Low | tauri | launch_file uses std::env::args() (panics on non-Unicode) | Fixed | `lib.rs` uses `args_os` (lossy) | `lib.rs` tests |
| Low | tauri | project-files copies never pruned; autosave resends whole pictures | Handed over: engine project/kept owner | n/a | n/a |
| Low | tauri | tsconfig.tsbuildinfo not git-ignored | Fixed | `.gitignore` | |

## Changelog lines
- On a Mac, double-clicking a .ludd project in Finder opens it in LUDD, and Cmd+Q asks about unsaved changes before quitting.
- If you untick "Tell me when a new version is out" on the first-run card, LUDD no longer checks anyway; it never checks before you've answered.
- Offline, "Check for updates" now says "Couldn't reach the update server. Check your internet connection and try again." instead of a technical error.
- F5, Ctrl+R, Ctrl+F, Ctrl+P and the browser's right-click menu no longer reload or search the app window (a reload used to lose the open design without asking).
- The installer now includes the licences of the libraries and fonts LUDD uses (THIRD-PARTY-NOTICES.txt in the install folder).
- LUDD for Mac needs macOS 14 Sonoma or newer (it says so at install instead of failing to start its engine).
- Slightly faster messaging between the window and the engine (no security-policy error at every start).
- Behind the scenes: every build starts the packaged engine once and checks it works; CI tests on Windows, both kinds of Mac and Linux, and runs the PES/JEF round trips on the bundled samples.

## Manual changes needed
- USER-GUIDE download table: file names should be `LUDD_<version>_...` (they say 1.0.0), and it should state the minimums: Windows 10/11 64-bit, macOS 14 Sonoma or newer (Apple chip or Intel), Linux with glibc 2.35+ (Ubuntu 22.04 or newer).
- If the manual mentions where licences are: `THIRD-PARTY-NOTICES.txt` in the install folder.

## Stitch output changed
- None from this group. (Note: `engine/tests/test_golden.py` JEF comparison now allows the JEF re-centring that another agent added in `design.py`; the shape is still compared stitch for stitch.)

## Handed over
- **features.ts owner** ("One file per name"): make destinations unique case-insensitively, ask before overwriting, count distinct files (tauri Medium + tests Medium).
- **StitchCanvas owner**: zoom performance on 40k stitches (cache stitch-edit points, cull to the viewport).
- **engine project / kept.py owner**: prune `project-files` copies not referenced by the current document or recovery; strip `data_url` before autosave.
- **Settings owner** (`SettingsDialog.tsx`): an "About / Licences" line that opens the bundled `THIRD-PARTY-NOTICES.txt` (resolveResource("THIRD-PARTY-NOTICES.txt")). Needs an opener permission LUDD doesn't have today, so showing it in a dialog (read via the engine) may be simpler.
- **docs owner**: USER-GUIDE (see above); README prerequisites "Rust 1.90 or newer"; CLAUDE.md dependency line lists networkx (not used) and should say onnxruntime is optional only on Intel Macs (owner's file: lead to decide).
- **Lead**: `.github/dependabot.yml` for github-actions plus SHA pinning needs a network lookup.

## Notes for the lead
- `tauri.conf.json` now ships `binaries/THIRD-PARTY-NOTICES.txt`, which `pnpm build:engine` writes (like the sidecar). `cargo check`, `tauri dev` and `tauri build` need `pnpm build:engine` (or `uv run --project engine python scripts/make_notices.py`) first, as they already did for the sidecar. I generated it locally (git-ignored folder).
- The macOS-only Rust (menu replacement, `RunEvent::Opened`) could not be compiled here; the shared logic is compiled and unit-tested on Windows. Watch the first `macos-latest` build.
- CI now tests on Linux and Intel Mac. The digitize snapshots were recorded on Windows only; if a snapshot differs on another OS, that's real cross-platform drift to look at (the release legs already ran these tests there).
- Engine suite at the end: 360 passed, 6 failed, all in other areas (5 fill snapshots changed by the fill work; `test_design.py::test_export_roundtrips_stitch_positions[jef]` from the JEF centring change). UI: 128 passed, 1 failed (`layout.test.ts` jumps-to-trims, another area).
