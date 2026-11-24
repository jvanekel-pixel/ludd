# PLAN

Phase tracker for Command Center. The original milestone plan and research are in `docs/PLAN.md`; this file only tracks phases and checkboxes.

## Phase 1: Foundation & Shipped Core (M0-M10, v1.0.0)
Why it matters: everything later builds on a working engine, viewer, digitizer and release pipeline, so this must stay green.
> Verify: `cd engine && uv run --locked pytest -q && pnpm typecheck && pnpm test` | Done when: engine tests, typecheck and UI tests all pass and tag `v1.0.0` exists
- [x] Tauri 2 shell, React UI and Python sidecar over JSON-RPC (M0)
- [x] Viewer, stitch player, converter and batch convert via pyembroidery (M1)
- [x] Machine, hoop and thread profiles; cut-stops for the PE550D (M2)
- [x] Edit existing designs, merge, print template and run sheet (M3)
- [x] Digitizing core with embedded reference images, autosave and recovery (M4)
- [x] Trace Assist / Auto-trace (M5: `trace.py`, `autotrace.py`)
- [x] Lettering (M6: `lettering.py`)
- [x] Fabric profiles and quality checks (M7: `fabrics.py`, `quality.py`)
- [x] Applique, hoop splitting, repeats, knockdown (M8: `digitize/applique.py`, `split.py`)
- [x] AI add-on, off by default (M9: `engine/threadline_engine/ai/`)
- [x] Release workflow, updater, user guide, samples, v1.0.0 published (M10)
- [x] Rebrand to LUDD with `.thl` / `.tlfont` compatibility

## Phase 2: 1.0.1 Hardening & Release
Why it matters: about 100 modified and 70 new files sit uncommitted, so until they are committed and released the app's real state is one disk failure from lost.
> Verify: `cd engine && uv run --locked pytest -q && pnpm typecheck && pnpm test && pnpm --filter @threadline/desktop build` | Done when: 1.0.1 is committed, CI is green on Windows and macOS, and a draft release has all four builds plus a correct `latest.json`
- [x] QA report written (docs/QA-REPORT.md, 420 findings)
- [x] QA phases 1-3 fixed: all Critical/High items C1-C26 (docs/QA-RESPONSE.md)
- [x] QA phase 4 (Medium/Low) fixed area by area (docs/qa-phase4/)
- [x] Knowledge base for the help agent (docs/LUDD-KNOWLEDGE-BASE.md)
- [x] Owner approves committing the uncommitted working tree; commit in logical groups (5 local commits, not pushed)
- [x] Owner decides the 20 open items listed in docs/QA-RESPONSE.md (decided 2026-11-14; applied in ed160f1)
- [x] Run the second QA pass using docs/QA-PROMPT.md and fix what it finds (docs/QA-REPORT-2.md; clear bugs fixed 2026-11-24, uncommitted)
- [ ] Owner decides the 10 items on the QA pass 2 decision list (docs/QA-REPORT-2.md)
- [x] Push to GitHub and confirm CI is green on Windows, both Macs and Linux (green at 46b0de4, incl. the Windows installer job)
- [ ] Tag v1.0.1, check the draft release's `latest.json` URLs, owner publishes

## Phase 3: Stitch-Out Verification on the PE550D
Why it matters: automated tests cannot prove thread on fabric, so every output-changing feature is unverified until the machine stitches it.
> Verify: Manual review of docs/stitchout-log.md | Done when: every row in "Pending machine tests" has a photographed result logged as pass or a fix filed
- [ ] Owner confirms the software is about 95% done and stitching can start
- [ ] Cut-stops on the PE550D (Key.PES): machine ties off, cuts, resumes
- [ ] Converted PES and recolored PES open correctly on the machine (centred in hoop)
- [ ] Three-object digitizing test, fill angles/density, satin widths, fill with hole
- [ ] Lettering: 10 mm script name, block letters, arch and monogram
- [ ] Fabric presets (cotton, T-shirt, towel) and quality-check gap test
- [ ] Two-hooping split and applique (stops, hole, cut file)
- [ ] 1.0.1 rows: ribbons, fill patterns, motif lines, hidden travel, auto-digitize
- [ ] JEF hoop and stop codes on a Janome (decision item 9 in QA-RESPONSE.md)
- [ ] First Mac build: check the Intel leg and macOS-only code (Finder open, Cmd+Q)

## Phase 4: v1.x Features & Launch Polish
Why it matters: after the core is verified, only owner-chosen backlog items should be added so the app does not bloat.
> Verify: `cd engine && uv run --locked pytest -q && pnpm test` | Done when: each pulled-in feature has tests, docs, CHANGELOG and knowledge-base updates and a stitch-out row
- [ ] Confirm the name "LUDD" is free before wider promotion (docs/PLAN.md decision)
- [ ] Thread inventory and shopping list
- [ ] SVG, DXF and PDF import
- [ ] Guided first-design tutorial and contextual hints / F1 help per tool
- [ ] Push compensation along stitch direction (after a patent check)
- [ ] Stitch time and thread usage estimate
- [ ] Write the project, fabric and thread-chart JSON Schemas (optional: AGENTS.md no longer promises them, decision item 11)
