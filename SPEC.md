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
- Data model: project = zip (`.ludd`; `.thl` opens too) with `project.json` plus embedded reference images. Objects (mm) are the source of truth; stitches are derived and cached by object hash. Export runs a pattern through a machine profile into pyembroidery.
- `engine/threadline_engine/ai/`: provider layer (Off / Ollama / Anthropic or OpenAI-compatible with the user's key), Stitch Advisor, Help assistant, MobileSAM tracing (optional download).
- `docs/`: PLAN.md (original milestone plan), CHANGELOG, USER-MANUAL, USER-GUIDE, LUDD-KNOWLEDGE-BASE (a separate help agent's source), QA-REPORT / QA-RESPONSE, qa-phase4/, stitchout-log, RELEASING.

## Already Implemented
- M0-M10 from docs/PLAN.md: sidecar and CI installers; viewer, stitch player, converter and batch convert; machine/hoop/thread profiles and cut-stops; stitch-file editing, merge, print template; digitizing (run, satin, tatami, underlay, pull comp, node editing, embedded reference images, autosave/recovery); Auto-trace and whole-picture auto-digitize; lettering (system fonts, stitch fonts, arcs, monograms, one file per name); fabric presets and quality checks; applique with SVG cut files, hoop splitting, repeats, knockdown; AI add-on; auto-update, user guide, samples, release workflow.
- v1.0.0 published 2026-10-11 (tag `v1.0.0`).
- 1.0.1 (merged to `main`, not yet tagged): Embrilliance-style keys, realistic thread, motif/stipple/cross/gradient/contour fills, optimizer for jumps and trims, design browser, right-click menus, Order & colors, start/end/direction dots, knowledge base, and the QA phases 1-4 fixes (docs/QA-RESPONSE.md).

## Remaining In Scope
- Tag and publish 1.0.1 (the owner's step; the work is merged).
- Phases 3 to 14 in `PLAN.md`, each with a spec in `docs/phases/`: close the gaps found in the competitive review (docs/COMPETITIVE-REVIEW.md). Phases 13 and 14 are extras the owner may leave.
- Phase 15: real stitch-outs on the PE550D for every queued row in docs/stitchout-log.md, once the features are built (D-012, D-019).
- Phase 16: fixes from the stitch-outs, the public manual, the 2.0 release.
- Confirm on the first real run: Intel Mac leg, macOS-only code, `latest.json` URLs.

## Out of Scope (Anti-Bloat)
- Any account, sign-in, licence check, telemetry, or network call in the core.
- Auto-applying AI or Trace Assist output without a preview and accept step.
- Hosted AI service, sequins/beading, wireless send to machines, browser/PWA build, photo stitch (all "Later" in docs/PLAN.md).
- Changing the internal `threadline_*` identifiers or breaking `.thl` / `.tlfont` / old data folder support.
- Closed-source dependencies; the project stays GPL-3.0-or-later.
