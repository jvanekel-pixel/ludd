# BACKLOG

Parked ideas, tech debt and nice-to-haves. Do not build these without the owner pulling them into `PLAN.md`. The full feature backlog with value/effort is in docs/PLAN.md ("Prioritized backlog").

## Tech debt and cleanup
- [ ] AGENTS.md (old CLAUDE.md) layout line still lists networkx, which is unused, and says onnxruntime is optional without noting it is bundled except on Intel Macs (QA-RESPONSE item 12)
- [ ] `schemas/` only has `machine.schema.json`; the project, fabric and thread-chart schemas promised in the rules do not exist (item 11)
- [ ] Offset limit message is in mm when units are inches
- [ ] UI mixes UK labels (Centre, Millimetres) with US text; pick one (item 15)
- [ ] Add a jsdom-style test environment so panels and the canvas can be tested (item 19)
- [ ] Pin GitHub Actions by commit SHA and add Dependabot (item 13)
- [ ] Vite build warns about chunks over 500 kB; consider code-splitting
- [ ] Delete the old git-ignored root `LUDD-User-Manual.pdf` (version 1.0); `docs/LUDD-User-Manual.pdf` is current (item 20)
- [ ] Clean the root of brand source PDFs/PNGs, research notes and the CSV (all git-ignored) into one folder
- [ ] Working tree shows LF to CRLF warnings; decide on `.gitattributes` line-ending policy

## Nice-to-haves from the QA decision list
- [ ] Progress bar and Cancel for whole-picture auto-digitize (item 3)
- [ ] Pin AI tracing model download to a fixed version with checksums (item 2)
- [ ] "Which side" option for motif lines (item 7)
- [ ] Basting box margin control (item 10)
- [ ] Multi-line lettering and a thin-stroke font warning (item 14)
- [ ] Keep design-browser thumbnails on disk, add Refresh (item 17)
- [ ] Show LUDD's fixed instructions in the AI send preview (item 18)
- [ ] Second Recover slot so autosave can stay on while the Recover banner is unanswered (item 1)
- [ ] Should pinned shapes also block arrow-key, R and Alt+H/V moves? (item 16)

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
