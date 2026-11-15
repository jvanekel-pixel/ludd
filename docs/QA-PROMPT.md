You are doing a full QA/QC review of LUDD, a free, open-source desktop embroidery digitizer. The repo is the current folder (`threadline`). Your job is to find real problems and report them with evidence. Do not fix anything unless it's a one-line typo; report everything else.

## What LUDD is
- Desktop app: Tauri 2 (Rust) + React 19 + TypeScript + Vite + PixiJS 8 + Zustand, in `apps/desktop`.
- Engine: Python 3.12 sidecar over JSON-RPC (stdio), in `engine/` (pyembroidery, shapely, numpy, OpenCV, ONNX Runtime). It is frozen with PyInstaller into `apps/desktop/src-tauri/binaries/`.
- The owner is a hobbyist with a Brother PE550D (4"×4" hoop; it cuts thread only at color changes). PES is the main output format; JEF must also be correct.
- Read `CLAUDE.md` first: its rules are requirements. Examples: model units are mm; objects are the source of truth; pictures are embedded in projects; the core makes no network calls; AI output is never auto-applied; every command has a keyboard shortcut; Esc lets go of one thing per press.
- `docs/USER-MANUAL.md` describes every feature as the user is told it works. Treat it as the spec: anything it promises that doesn't work is a bug.

## How to run things
- Engine tests: `cd engine && uv run pytest`
- UI tests and types: `cd apps/desktop && corepack pnpm test` and `corepack pnpm typecheck`
- Browser preview: `.claude/launch.json` has a "ui" server (Vite on port 1420). It runs a real dev engine, so the app works in a plain browser. You can drive the app's own modules from the page, e.g. `await import('/src/actions.ts')`, `(await import('/src/store.ts')).useStore`. Use `addPicture(path)` and `openDesign(path, true)` to load files without file dialogs.
- Real test designs are in `fixtures/` (PES files). Synthetic test pictures are easy to make with Pillow.
- Do not push, tag, publish, or change GitHub settings. Do not download anything without asking. Do not run `pnpm tauri build` unless asked (it takes minutes and overwrites the installer).

## What to check
Work through these areas. For each, read the code, run what exists, and try it in the preview.

1. **Correctness of stitch output** (the most important area: bad stitches waste fabric and thread).
   - `engine/threadline_engine/digitize/` (running, satin ribbons and columns, tatami, and the patterns in `patterns.py`: gradient, wave, contour, stipple, cross, motif lines).
   - Look for stitches longer than about 7 mm, stitches outside the shape, gaps, doubled-up rows, and degenerate shapes (tiny, self-intersecting, holes touching the edge) that crash or produce garbage.
   - Check what PES and JEF export actually writes: units (0.1 mm), color changes, trims, stops, jumps.
2. **Layout and render pipeline** (`engine/threadline_engine/layout.py`):
   - Ops on stitch files, including the new `delete_stitches` and `move_stitch`.
   - Joining same-thread objects, `travel_under` (hidden travel instead of jump/trim), `optimize_order`, color sort and merge, basting, knockdown, splitting a design across hoopings.
   - Is hidden travel ever left visible on top of earlier stitching?
3. **Auto-trace and whole-picture digitizing** (`autotrace.py`, `ai/segment.py`):
   - Robustness on real-world pictures: JPEG noise, gradients, transparent PNGs, huge or tiny images, rotated or scaled placements.
   - Performance (calls should stay under a few seconds).
   - Make sure the AI model is only downloaded on user request.
4. **Shape operations** (`shapeops.py`: offset, knife, merge) and their UI in `src/features.ts`.
5. **The UI state and interaction model** (`src/actions.ts`, `src/store.ts`, `src/features.ts`, `src/autoTrace.ts`, `src/components/StitchCanvas.tsx`, `InfoPanel.tsx`, `Accordion.tsx`):
   - **Esc behavior** (`src/escape.ts`): any `holdEscape` that can leak? Esc not working was a real recent bug.
   - **Drags and mouse capture:** pointer capture, window blur, release outside the window.
   - **Undo/redo:** every edit should be one Ctrl+Z.
   - **Selection and multi-select:** what is selected after deletes or undo.
   - **Keyboard shortcuts:** conflicts in the `COMMANDS` registry (the first *enabled* match wins, so check order-dependent conflicts), and shortcuts swallowing typing in text fields.
   - **Stale UI state:** after an engine error, and when an engine reply comes back after the user has moved on.
6. **Projects and files** (`project.py`, `storage.py`, `kept.py`):
   - Save, reopen, recovery after a crash.
   - Embedded pictures survive deleting the original.
   - Old projects (`.thl`, satin columns made with rails, no `travel_under`) still open and sew the same.
   - Damaged files fail gracefully.
7. **Security & privacy:**
   - The Tauri CSP and capabilities (`src-tauri/tauri.conf.json`, `capabilities/`).
   - The only network code should be the updater and the opt-in AI add-on (`engine/threadline_engine/ai/`). Check for any network calls elsewhere.
   - API key storage (DPAPI on Windows).
   - Path handling: `library.scan`, `export` destinations, folder pickers.
8. **Packaging:**
   - `scripts/build_engine.py`: the frozen engine must include OpenCV and ONNX Runtime and leave out the FFmpeg DLL.
   - `.github/workflows/release.yml`.
   - Version numbers agree in `package.json`, `tauri.conf.json`, `Cargo.toml`, `engine/pyproject.toml` and `__init__.py`.
9. **Docs vs reality:**
   - Spot-check `docs/USER-MANUAL.md` and the in-app help text (`engine/threadline_engine/ai/helpdocs.py`) against the code: shortcuts listed but not registered (or the reverse), features described that don't exist, stale names.
   - Check that `docs/CHANGELOG.md` is accurate.
10. **Test quality:** important behavior with no test, tests that can't fail, and snapshot tests that would hide a regression.

## Known soft spots (verify, and look for more)
- **Fewer jumps** only hides a move when the straight path is entirely under later stitching.
- **Guides** snap placed and dragged points only, not whole-shape drags.
- **Text on a drawn line:** if the text is longer than the line, the extra letters pile up at the ends.
- **Stitch-edit moves** are stored as world-space deltas, which drift if the design is later rotated.
- **Not tested in the installed app:** "One file per name" export and the design-browser folder picker (browser-preview only).
- **Stitch editing canvas:** draws every needle point. Check performance on 30k+ stitch designs.
- **New features with little or no test coverage:** whole-picture digitize (one test), offsets/knife/merge (engine tests only, no UI tests), and colorways/preview/guides (no tests).

## How to report
Report your findings in Markdown, most severe first. Severity levels:
- **Critical:** ruins a stitch-out, loses work, security
- **High:** a feature broken or misleading
- **Medium:** wrong in some cases, or a confusing UX
- **Low:** polish

For each finding, give:
- a short title;
- `file:line` references;
- what happens versus what should happen;
- exact steps or a test case that reproduces it (a failing pytest or vitest snippet is best);
- a suggested fix in a sentence or two.

End with:
- a short list of things you checked that are solid;
- the gaps you couldn't check, and why;
- your top five fixes to make first.

Keep it factual: say "confirmed" only for what you reproduced, and "suspected" otherwise.
