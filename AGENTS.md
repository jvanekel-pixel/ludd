# AGENTS.md

Static on purpose (keeps prompt caching intact). Live state lives in `HANDOFF.md` and `project.json`, never here.

## Project Goal
LUDD (formerly Threadline) is a free, open-source, offline desktop embroidery digitizer for Windows, Mac and Linux, built for a hobbyist with a Brother PE550D. It opens and edits stitch files, digitizes new designs, adds lettering, and exports PES/JEF and other formats, with AI only as an optional, off-by-default add-on.

## Tool Roles & Routing
- **Claude Code**: primary code editor. Follow `routing` in `project.json`.
- **Antigravity**: architecture, security, and phase-close QoL audits.
- **Local Ollama**: read-only log checks, compression, and briefs. It never edits code.
- **Command Center MCP** (`iammachine-command-center`): call `get_project_context` before starting and `log_session` when done.

## Token Policy & Guardrails
- **Static prefix**: do not put dates, counts, or status in `AGENTS.md` / `CLAUDE.md`.
- **Diff-only and quiet checks**: edit with diffs, run tests quietly, and summarize failures to <=30 lines.
- **Fresh chat per phase**; park QoL ideas in `BACKLOG.md` instead of building them.
- **Two-Strike Rule**: stop after 2 failed attempts on the same error. Log it in `HANDOFF.md` and escalate.
- **Session Stop Contract**: overwrite `HANDOFF.md` (<=25 lines), update `project.json`, and check off `- [x]` in `PLAN.md`.
- Never read or copy secret values (`.env`, `%USERPROFILE%\.tauri\*.key`, `*.password.txt`). Never commit, tag, push, or publish without the owner asking.

## Compute & Budget Tier
Subscription-First, `$0 extra API`. The app handles no PII (embroidery designs and thread charts only), so local-only AI rules are not forced. The app's own AI add-on stays off by default and is user-keyed.

## Verification Commands
- Engine tests: `cd engine && uv run --locked pytest -q`
- UI typecheck: `pnpm typecheck`
- UI tests: `pnpm test`
- UI build: `pnpm --filter @threadline/desktop build` (tsc + vite build)
- Rust tests: `cargo test --locked --lib --manifest-path apps/desktop/src-tauri/Cargo.toml`
- Frozen engine sidecar + smoke check: `pnpm build:engine` (slow; needed before `tauri dev/build`)
- After changing `COMMANDS`: `python scripts/kb_commands.py`
- Installer: `pnpm tauri build --config '{"bundle":{"createUpdaterArtifacts":false}}'`

---

# Project rules (carried over unchanged from the previous CLAUDE.md)

## What this is
Cross-platform desktop embroidery digitizer. Full plan: docs/PLAN.md (original milestone plan); the phase tracker for Command Center is the root `PLAN.md`.
Work one milestone at a time. Stop at its acceptance criteria and explain how to verify.

## Layout
- apps/desktop: Tauri 2 + React + TypeScript + Vite; PixiJS canvas, SVG overlay for handles
- engine/: Python 3.12 sidecar, JSON-RPC 2.0 over stdio
  - deps: pyembroidery, shapely, numpy, opencv-python-headless; onnxruntime is bundled everywhere except Intel Macs, which have no wheels (AI tracing is simply unavailable there)
- schemas/: JSON Schemas (source of truth). Only `machine.schema.json` exists so far; project, fabric and thread-chart schemas are on the backlog, and until then the TypeScript types in `design/types.ts` and the engine's own validation are the reference
- fixtures/: real design files for golden tests
- docs/: PLAN.md, CHANGELOG.md, stitchout-log.md, LUDD-KNOWLEDGE-BASE.md (the help agent's source; instructions in LUDD-HELP-AGENT-INSTRUCTIONS.md)

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
- Brand: ink #121114, bone #EEE9DF, techno yellow #C8FF2E, greys #B5AEA3 / #8E877D. Wordmark Archivo 900 at 62% width; secondary Space Mono uppercase (both bundled, OFL). Mark: `components/Logo.tsx`; app icon source `src-tauri/icons/icon.svg`. Colors come from CSS tokens in `styles.css`; light and dark mode follow the system unless chosen in Settings. The canvas fabric stays light in both by default (Settings: "Always show the design on light fabric", ticked); unticking it makes the design area follow dark mode.
- Esc lets go of one thing per press, newest first: anything registered with `holdEscape` (drags, open lists), then a focused field (its old value comes back), then the Escape commands in `COMMANDS` order.
- License: GPL-3.0-or-later (decided Oct 11, 2026). Code may be adapted from GPL-compatible projects such as Ink/Stitch; credit the source in a comment and keep their copyright notices.

## Commands
- pnpm build:engine: freeze the engine into the Tauri sidecar (needed before tauri dev/build, and after engine changes)
- pnpm tauri dev: run the app
- cd engine && uv run pytest: engine tests
- pnpm test: UI tests

## Knowledge base (the owner's help agent reads it)
- docs/LUDD-KNOWLEDGE-BASE.md must match the app. Every user-visible change updates it in the same change as CHANGELOG.md and USER-MANUAL.md: the F- entry, the capability index, limits (L-), troubleshooting (T-), the history table, and *Last updated*.
- After changing COMMANDS, run `python scripts/kb_commands.py` (a UI test fails if a command is missing).
- Never delete an ID; mark it superseded. The help agent never edits code; requests it writes come here.

## Definition of done for a milestone
- Acceptance criteria in docs/PLAN.md met and demonstrated
- CI green on Windows and macOS
- docs/CHANGELOG.md updated; stitchout-log.md updated if stitch output changed
