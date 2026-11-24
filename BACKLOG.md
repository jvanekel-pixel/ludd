# BACKLOG

Parked ideas, tech debt and nice-to-haves. Do not build these without the owner pulling them into `PLAN.md`. The full feature backlog with value/effort is in docs/PLAN.md ("Prioritized backlog").

## Tech debt and cleanup
- [x] AGENTS.md (old CLAUDE.md) layout line still lists networkx, which is unused, and says onnxruntime is optional without noting it is bundled except on Intel Macs (QA-RESPONSE item 12) (done 2026-11-14)
- [x] `schemas/` only has `machine.schema.json`: AGENTS.md now says so (item 11, 2026-11-14)
- [ ] Write the project, fabric and thread-chart JSON Schemas (and generate types from them) if they are wanted
- [ ] Offset limit message is in mm when units are inches
- [x] UI mixes UK labels (Centre, Millimetres) with US text; pick one (item 15) (done: US spelling)
- [x] Add a jsdom-style test environment so panels and the canvas can be tested (item 19) (done: `*.dom.test.tsx` files run in jsdom)
- [x] Pin GitHub Actions by commit SHA and add Dependabot (item 13) (done)
- [ ] Vite build warns about chunks over 500 kB; consider code-splitting
- [x] Delete the old git-ignored root `LUDD-User-Manual.pdf` (version 1.0); `docs/LUDD-User-Manual.pdf` is current (item 20) (done)
- [ ] Clean the root of brand source PDFs/PNGs, research notes and the CSV (all git-ignored) into one folder
- [ ] Working tree shows LF to CRLF warnings; decide on `.gitattributes` line-ending policy
- [x] AI key storage: create `ai-key.bin` atomically with `0o600` (done 2026-11-24)
- [ ] AI key storage: use the OS keychain on macOS/Linux instead of base64 (new dependency; owner decision)
- [x] Multi-select Zoom to Selection (`apps/desktop/src/actions.ts`): update `zoomSelected()` (`S`) to use `selectionGeometry(selectionIds()).box` when multiple items are selected
- [x] Dev Vite engine bridge (`apps/desktop/vite-engine-bridge.ts`): ignore/clean up JSON-RPC notifications (no `id`) instead of leaking `pending` entries and cap request body size

## From QA pass 2 (docs/QA-REPORT-2.md, 2026-11-24)
- [x] Owner decisions 1-10 in docs/QA-REPORT-2.md: decided 2026-11-24 (all as recommended, 9 = a); being implemented (PLAN.md Phase 2)
- [ ] Stipple at small loop sizes on hoop-sized shapes is slow (6.5 s); wave's stitch-count estimate is low (S8)
- [ ] test_helpdocs: check each documented key against the command it describes, bare keys too (D9)
- [ ] knowledgeBase.test.ts: compare the whole command table, so removed or renamed commands fail (D10)
- [ ] Guide snapping as a pure function with tests (D12)

## Nice-to-haves from the QA decision list
- [ ] Progress bar and Cancel for whole-picture auto-digitize (item 3)
- [x] Pin AI tracing model download to a fixed version with checksums (item 2) (done: revision + SHA-256)
- [ ] "Which side" option for motif lines (item 7)
- [ ] Basting box margin control (item 10)
- [ ] Multi-line lettering and a thin-stroke font warning (item 14)
- [x] Design browser Refresh button (item 17, done)
- [ ] Keep design-browser thumbnails on disk between sessions (item 17, decided: later)
- [x] Show LUDD's fixed instructions in the AI send preview (item 18) (done)
- [ ] Second Recover slot so autosave can stay on while the Recover banner is unanswered (item 1)
- [x] Should pinned shapes also block arrow-key, R and Alt+H/V moves? (item 16) (decided yes, done)

## Decided to keep as is (QA decisions, 2026-11-14)
- Autosave stays off while the Recover banner is unanswered (item 1); wide satins keep warning only, no new default (item 4); pen-tool curve overshoot left alone (item 5); the 400,000-stitch fill limit stays (item 6).
- [ ] Memory guard for crafted .vp3/.hus files: read files in a separate memory-limited process (item 8; documented as L-024)
- JEF hoop and stop codes wait for a Janome stitch-out (item 9, queued in stitchout-log.md).

## From docs/PLAN.md backlog (not yet started)
- [ ] Thread inventory and shopping list
- [ ] SVG, DXF and PDF import
- [ ] Guided first-design tutorial; contextual hints and F1 help per tool
- [ ] Push compensation along stitch direction (patent check first)
- [ ] Stitch time and thread usage estimate
- [ ] Monogram templates and ornaments
- [ ] Multi-color blending, embossing/carving, 3D foam, patch edge (v2)
- [ ] Python plugin/scripting API; translations (v2)
- [ ] Browser/PWA build via Pyodide (Later)
