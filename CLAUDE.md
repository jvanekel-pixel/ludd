# LUDD: notes for Claude Code

## What this is
Cross-platform desktop embroidery digitizer. Full plan: docs/PLAN.md.
Work one milestone at a time. Stop at its acceptance criteria and explain how to verify.

## Layout
- apps/desktop: Tauri 2 + React + TypeScript + Vite; PixiJS canvas, SVG overlay for handles
- engine/: Python 3.12 sidecar, JSON-RPC 2.0 over stdio
  - deps: pyembroidery, shapely, numpy, networkx, opencv-python-headless; onnxruntime optional
- schemas/: JSON Schemas for project, machine, fabric, thread chart (source of truth; generate TS and Python types)
- fixtures/: real design files for golden tests
- docs/: PLAN.md, CHANGELOG.md, stitchout-log.md

## Rules
- Model units are millimetres. Convert to 0.1 mm only at export.
- Objects are the source of truth. Stitches are derived and cached by object hash.
- Imported stitch files are edited in a separate stitch-edit mode.
- Projects embed reference images (bytes plus placement). Never save only a path to a user's image. Test: save, delete the original image, reopen.
- UX is "Don't make me think": the default view shows only what a beginner needs; adjustables live behind "More options" or the ⋯ menu, never removed. Recommended defaults come from the machine profile.
- Core makes no network calls. AI lives behind engine/ai/providers and is off by default.
- Never auto-apply AI or Trace Assist output. Always preview, then accept or dismiss.
- Every command goes in the command registry with a keyboard shortcut.
- Every engine function gets a pytest; every stitch type gets snapshot tests.
- Formats: PES (the user's Brother machine) is primary; JEF must also export correctly. Golden tests cover both.
- Name and brand (Oct 11, 2026): the app is **LUDD** (formerly Threadline). Internal identifiers (`threadline_engine`, the `threadline-engine` sidecar, `THREADLINE_DATA_DIR`, npm package names) stay. Old `.thl` projects, `.tlfont` stitch fonts and the old `Threadline` data folder must keep working.
- Brand: ink #121114, bone #EEE9DF, techno yellow #C8FF2E, greys #B5AEA3 / #8E877D. Wordmark Archivo 900 at 62% width; secondary Space Mono uppercase (both bundled, OFL). Mark: `components/Logo.tsx`; app icon source `src-tauri/icons/icon.svg`. Colors come from CSS tokens in `styles.css`; light and dark mode follow the system unless chosen in Settings. The canvas fabric stays light in both.
- Esc lets go of one thing per press, newest first: anything registered with `holdEscape` (drags, open lists), then a focused field (its old value comes back), then the Escape commands in `COMMANDS` order.
- License: GPL-3.0-or-later (decided Oct 11, 2026). Code may be adapted from GPL-compatible projects such as Ink/Stitch; credit the source in a comment and keep their copyright notices.

## Commands
- pnpm build:engine: freeze the engine into the Tauri sidecar (needed before tauri dev/build, and after engine changes)
- pnpm tauri dev: run the app
- cd engine && uv run pytest: engine tests
- pnpm test: UI tests

## Definition of done for a milestone
- Acceptance criteria in docs/PLAN.md met and demonstrated
- CI green on Windows and macOS
- docs/CHANGELOG.md updated; stitchout-log.md updated if stitch output changed
