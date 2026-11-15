# Response to the QA report (docs/QA-REPORT.md)

Status of each Critical/High item. Each fix has a regression test built from the report's reproduction.

| # | Problem | Status | Where fixed | Test |
|---|---|---|---|---|
| C1 | Split drops STOPs | Fixed (phase 1) | split.py `_blocks`, `section_pattern` | test_m8 `test_split_keeps_applique_stops` |
| C2 | Fewer jumps crashes (GEOS) | Fixed (phase 1) | layout.py `_cover`, `_join_same_thread_objects` | test_connectors `test_qa_c2_*` |
| C3 | Fewer jumps slow | Fixed (phase 1): Banner 3.96 s → 0.03 s, 100 squares 8.8 s → 0.15 s | layout.py | test_connectors `test_qa_c3_*` |
| C4 | Emptied colour stays; thread table shifts | Fixed (phase 1) | layout.py `render` | test_layout `test_qa_c4_*` |
| C5 | Split buries a top layer | Fixed (phase 1) | split.py `plan` | test_m8 `test_split_never_sews_a_lower_layer_over_a_higher_one` |
| C6 | Sort colors defeats fewer jumps | Fixed (phase 1) | layout.py (sort before join) | test_connectors `test_qa_c6_*` |
| C7 | Missing font blocks the project | Fixed (phase 1): stand-in font + warning. Fonts embedded in projects (phase 4) | lettering.py | test_lettering `test_qa_c7_*` |
| C8 | Applique ignores holes | Fixed (phase 1) | applique.py, layout.applique_svg | test_m8 `test_qa_c8_*` |
| C9 | Save deletes waiting recovery | Fixed (phase 1) | actions.ts `saveProject` | actions.qa.test.ts |
| C10 | Advisor crashes on ribbons | Fixed (phase 2); ribbon ↔ line proposals now apply | ai/advisor.py `_pairs`, ai.ts `applicable`/`withChange` | test_ai `test_qa_c10_*`, ai.test.ts |
| C11 | Updater URLs 404 | Fixed (phase 3): manifest uses `releases/download/v<version>/…`; RELEASING.md step 5 says to check | release.yml `updater-manifest` | to check on the 1.0.1 draft's latest.json |
| C12 | Names export ignores machine | Fixed (phase 1), plus no overwrite and fresh file type | features.ts, layout.export `keep_existing` | test_layout `test_qa_c12_*` |
| C13 | Knife/merge ignore transform | Fixed (phase 2): engine works in world coordinates; Ctrl+D bakes the offset into drawn shapes | shapeops `_world`, layout.ts `duplicateItem`, features.ts `mergeSelected` | test_shapeops `test_qa_c13_*`, layout.test.ts |
| C14 | Offset slow/timeouts | Fixed (phase 2): spiral 9 s → 0.5 s, Heart.thin 18 s → 1.7 s, NewFrog 18 s → 1.4 s; UI waits up to 2 min | shapeops `offset` (chunked, vectorised buffer), features.ts `LONG_MS` | test_shapeops `test_qa_c14_*` |
| C15 | Wave rows cross | Fixed (phase 1): 330 → under 2% crossings | stitches.py `tatami` | test_patterns `test_qa_c15_*` |
| C16 | Measuring readout | Confirmed and fixed (phase 2): distance in the hint bar; ⋯ menu entry | ToolRail.tsx `DrawHint`, Toolbar.tsx | checked in the preview |
| C17 | Re-render drops a drag | Fixed (phase 2): the ghost is remade on the new scene | StitchCanvas.tsx `placeGhost` | the report's repro run in the preview: moved, no errors |
| C18 | Key repeat floods renders | Fixed (phase 2): one render in flight, newest edit next; a held key is one undo step | actions.ts `showHistory`/`runRender`, `continueGesture` | actions.qa.test.ts |
| C19 | Edit while opening → wrong save path | Fixed (phase 1) | actions.ts `replaceDoc`/`showHistory` | actions.qa.test.ts |
| C20 | Text box not focused | Fixed (phase 2) | actions.ts `takeTextToEdit`, TextPanel.tsx | checked in the preview with real keys |
| C21 | Intel Mac build (onnxruntime) | Fixed (phase 3): onnxruntime only where it has wheels; `ai.trace_model` reports `runtime`; Settings explains | pyproject.toml, uv.lock, ai/segment.py, AISettings.tsx | `uv export` shows the marker; Intel leg to confirm in the release run |
| C22 | Print unstyled in installed app | Fixed (phase 2): no style nonce (`dangerousDisableAssetCspModification: ["style-src"]`); check in the installed app in phase 3 | tauri.conf.json | print.test.ts |
| C23 | 180 MB temp folder per quit | Fixed (phase 3): `engine.shutdown` on quit and before installing an update; startup sweep of marked, unused `_MEI*` folders (Windows) | rpc.py, methods.py, cleanup.py, build_engine.py (marker), sidecar.ts, manager.ts, App.tsx, updates.ts | test_rpc, test_cleanup; the packaged engine tried for real: shut down → no folder, killed → swept by the next run |
| C24 | Second instance / false crash | Fixed (phase 3): tauri-plugin-single-instance forwards the file to the open window; the launch file opens after Recover/Discard | lib.rs, Cargo.toml, App.tsx | checked with the built app |
| C25 | Engine death not recovered | Fixed (phase 3): automatic restart (not in a loop), Restart engine button, failed start kills the child, 60 s first ping | engine/manager.ts, sidecar.ts, StatusBar.tsx | manager.test.ts; checked with the built app |
| C26 | Clean checkout fails a test | Fixed (phase 3): test_library uses the committed samples in tmp_path | tests/test_library.py | itself |

Other notes:
- MobileSAM licence: now says Apache-2.0 (the original project's) in Settings, the engine and the docs (phase 2).
- Also in phase 2: text on a line warns when the text is longer than its line; stitch-edit moves turn and resize with the design.
- The stray `docs/QA-REPORT-2026-10-11.md` was deleted.
- Medium/Low items (about 380): phase 4, area by area (below).

## Phase 4: Medium and Low findings

Nine groups worked through the Medium and Low findings area by area, then a leftovers group took
the items they handed to each other, and the docs group brought the manual, guide, README and
in-app Help in line. The full per-item tables (finding, outcome, where fixed, test) are in
[docs/qa-phase4/](qa-phase4/). Many findings were reported by several areas; each notes file
lists them all, so the rows below overlap. "Handed over" items were mostly fixed later by the
leftovers or layout group; what is still open is listed at the end.

| Group (notes file) | Areas | Fixed | Already fixed | Skipped | Handed over / decision |
|---|---|---|---|---|---|
| [autotrace](qa-phase4/autotrace.md) | autotrace, AI tests | 22 (2 partly) | 1 | 2 parts (progress/cancel, model hash) | 1 (picked up by leftovers) |
| [stitches](qa-phase4/stitches.md) | fill, patterns, satin, shapeops, visual | 53 | 6 | 4 | 16 (most picked up by leftovers / layout) |
| [layout](qa-phase4/layout.md) | layout-order, layout-ops, compat, export | 55 | 22 | 3 | 2 + 3 decisions |
| [lettering](qa-phase4/lettering.md) | lettering | 26 | 5 | 2 (+ parts) | 1 (picked up by leftovers) |
| [engine-io](qa-phase4/engine-io.md) | fuzz-rpc, project, security | 31 | 15 | 2 | 14 (most picked up by others) |
| [ui](qa-phase4/ui.md) | live-esc, live-state, UI tests | 36 | 9 | 0 | 4 (3 picked up; 1 decision) |
| [platform](qa-phase4/platform.md) | tauri, packaging, CI | 23 | 2 | 0 | 3 (picked up by leftovers / engine-io) |
| [leftovers](qa-phase4/leftovers.md) | items handed over above | 23 (1 partly) | 1 | 1 | 0 |
| [tests](qa-phase4/tests.md) | tests | 6 | 17 | 0 | 0 |
| [docs](qa-phase4/docs.md) | docs-a, docs-b, docs-c | 17 | 27 | 0 | 9 |

Tests at the end of phase 4: engine `CI=1 uv run pytest` and the UI's vitest suite all pass
(see the final run in the docs notes); new tests are named `test_qa_*` / `test_qa4_*` and
`*.qa.test.ts`.

### Decisions on the 20 open items (owner, 2026-11-14)
| # | Item | Decision | Done |
|---|---|---|---|
| 1 | Autosave while the Recover banner is unanswered | Keep it off | no change |
| 2 | AI tracing model download | Pin the revision and check SHA-256 | Done: `ai/segment.py` (`REVISION`, `FILES`), tests in test_autotrace.py |
| 3 | Whole picture progress bar and Cancel | Backlog | BACKLOG.md |
| 4 | Wide satins | No new default; keep the warning | no change |
| 5 | Pen-tool curve overshoot | Leave | no change |
| 6 | 400,000-stitch fill limit | Keep | no change |
| 7 | Motif "which side" option | Backlog | BACKLOG.md |
| 8 | Crafted .vp3/.hus memory use | Accept the risk, document it | L-024 in the knowledge base; guard on the backlog |
| 9 | JEF hoop and stop codes | Stay queued for a Janome stitch-out | stitchout-log.md |
| 10 | Basting box margin | Backlog | BACKLOG.md |
| 11 | Schemas | Change the docs, not write the schemas | AGENTS.md; writing them is on the backlog |
| 12 | AGENTS.md / CLAUDE.md out of date | Fix now | Done: AGENTS.md (CLAUDE.md imports it) |
| 13 | GitHub Actions | Pin by SHA, add Dependabot | Done: `.github/workflows/*.yml`, `.github/dependabot.yml` |
| 14 | Lettering (multi-line, thin-stroke warning, V-shaped lines) | Backlog | BACKLOG.md |
| 15 | Spelling | US | Done: app labels (Center, Millimeters, Licenses, same-color), docs and Help text |
| 16 | Pinned shapes and the arrow keys, R, Alt+H/V | Pin blocks them | Done: `editSelection`, `nudge` in actions.ts; test in actions.qa.test.ts |
| 17 | Design browser | Refresh button now; thumbnails on disk later | Done: Refresh in FeatureDialogs.tsx |
| 18 | AI send preview | Also show LUDD's fixed instructions | Done: `instructions` in the estimate, AIPanels.tsx; test in test_ai.py and AIPanels.dom.test.tsx |
| 19 | UI tests | Add jsdom | Done: jsdom dev dependency; `*.dom.test.tsx` files (AIPanels.dom.test.tsx is the first) |
| 20 | Old root `LUDD-User-Manual.pdf` | Delete | Done (it was git-ignored) |

To check on the first real run: the pinned GitHub Actions and Dependabot (the first CI run on GitHub), and the model download checksum (press Download in Settings → AI tracing once on a real connection).

### Small handed-over code fixes (done by the lead after the docs pass)
- Shift+comma (machine speed) now works: Shift with punctuation is matched by the physical key (`commands.ts`, test in commands.test.ts).
- Shapes from the Shapes menu start with your remembered fill settings (`addShape` uses `defaultsFor`).
- Adding a picture says "pin it (📌)".
- Backspace with a point selected removes the point, not the shape (`node.deleteAlt`).
- Pictures hidden with B can't be clicked or dragged.
- `schemas/machine.schema.json` says LUDD and the Ludd data folder.
- Still open: the offset limit message is in mm when units are inches. Skipped as low value: outline ring a little inside the distance at tight turns; PEC trim flag on jumps (harmless on the PE550D); PES v6 segment count.

### To check on the first real run
- The macOS-only code (Finder open, Cmd+Q prompt) was compiled only on Windows: watch the first Mac build.
- The phase-4 stitch output changes are queued in stitchout-log.md (rows marked "1.0.1 (phase 4)").
