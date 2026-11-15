# SPEC: LUDD

## Product Goal
A free, open-source, fully offline embroidery digitizer for Windows, Mac and Linux that covers what hobbyists pay Embrilliance/Hatch for: open and edit existing designs, digitize new ones, lettering, fabric-aware stitching, applique, hoop splitting. Digitizing stays a human job; the software proposes (Auto-trace, Stitch Advisor) and the human accepts every object. AI is an optional add-on, off by default. No account, sign-in, licence check, or network use in the core.

## Target Audience
One hobbyist owner (Brother PE550D, 4" x 4" hoop, PES primary, JEF second) who buys Amazon thread. Public release for other hobbyists via GitHub Releases. UX rule: "Don't make me think" (beginner view first, adjustables behind "More options" / the ⋯ menu).

## Deploy Target
Desktop installers (Windows, Mac Apple chip and Intel, Linux) built by GitHub Actions into a draft release on `jvanekel-pixel/ludd`; the owner publishes. Signed auto-updater (`latest.json`). Installers are not code-signed.

## Current Architecture
- `apps/desktop`: Tauri 2 (Rust shell) + React 19 + TypeScript + Vite; PixiJS canvas for stitches, SVG overlay for handles; Zustand state with command-pattern undo; command registry with shortcuts (`commands.ts`).
- `engine/` (`threadline_engine`): Python 3.12 sidecar over JSON-RPC 2.0 on stdio, frozen with PyInstaller and bundled as a Tauri sidecar. Deps: pyembroidery, shapely, numpy, opencv-python-headless, pillow, fonttools; onnxruntime optional (not on Intel Mac).
- Data model: project = zip (`.ludd`; `.thl` opens too) with `design.json` plus embedded reference images. Objects (mm) are the source of truth; stitches are derived and cached by object hash. Export runs a pattern through a machine profile into pyembroidery.
- `engine/threadline_engine/ai/`: provider layer (Off / Ollama / Anthropic or OpenAI-compatible with the user's key), Stitch Advisor, Help assistant, MobileSAM tracing (optional download).
- `docs/`: PLAN.md (original milestone plan), CHANGELOG, USER-MANUAL, USER-GUIDE, LUDD-KNOWLEDGE-BASE (a separate help agent's source), QA-REPORT / QA-RESPONSE, qa-phase4/, stitchout-log, RELEASING.

## Already Implemented
- M0-M10 from docs/PLAN.md: sidecar and CI installers; viewer, stitch player, converter and batch convert; machine/hoop/thread profiles and cut-stops; stitch-file editing, merge, print template; digitizing (run, satin, tatami, underlay, pull comp, node editing, embedded reference images, autosave/recovery); Auto-trace and whole-picture auto-digitize; lettering (system fonts, stitch fonts, arcs, monograms, one file per name); fabric presets and quality checks; applique with SVG cut files, hoop splitting, repeats, knockdown; AI add-on; auto-update, user guide, samples, release workflow.
- v1.0.0 published 2026-10-11 (tag `v1.0.0`).
- 1.0.1 (unreleased, in the working tree): Embrilliance-style keys, realistic thread, motif/stipple/cross/gradient/contour fills, optimizer for jumps and trims, design browser, right-click menus, Order & colors, start/end/direction dots, knowledge base, and the QA phases 1-4 fixes (docs/QA-RESPONSE.md).

## Remaining In Scope (MVP)
- Commit and release 1.0.1 (working tree is uncommitted; ask the owner first).
- Owner decisions on the 20 open items in docs/QA-RESPONSE.md; a second QA pass (docs/QA-PROMPT.md).
- Real stitch-outs on the PE550D for every queued row in docs/stitchout-log.md (owner is testing at about 95% done).
- Confirm on the first real run: Intel Mac leg, macOS-only code, `latest.json` URLs.
- v1.x backlog from docs/PLAN.md that the owner chooses to pull in (see BACKLOG.md).

## Out of Scope (Anti-Bloat)
- Any account, sign-in, licence check, telemetry, or network call in the core.
- Auto-applying AI or Trace Assist output without a preview and accept step.
- Hosted AI service, sequins/beading, wireless send to machines, browser/PWA build, photo stitch (all "Later" in docs/PLAN.md).
- Changing the internal `threadline_*` identifiers or breaking `.thl` / `.tlfont` / old data folder support.
- Closed-source dependencies; the project stays GPL-3.0-or-later.
