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
- [ ] `check.py --all` prints RESULT: PASS when Rust is SKIP (no frozen engine): make a skip under `--all` say so in the RESULT line, or fail (Phase 3 audit, finding 1)
- [ ] `check.py` doesn't say when `fixtures/` is missing (a worktree runs ~44 fewer engine tests and still passes): print it on the engine line (Phase 3 audit, finding 2)
- [ ] `fills/spiral.py` `_middle`: the shapely < 2.1 fallback can't run (pyproject needs >= 2.2); drop it (Phase 3 audit, finding 4)
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

## From Phase 3 (2026-11-24)
- [x] Spiral showed lines across hearts, ovals and ring shapes: its pieces are now joined along the edge that cut them apart (done 2026-11-24, owner approved)
- [x] Spiral piled its joining thread along the edge (up to 27 threads in one spot on the ready-made Heart): it now sews each time the piece nearest along the same edge, so at most 4 or 5 share a spot, with 10 to 51% fewer stitches on the ready-made shapes but the Circle (done 2026-11-24, owner approved; L-026)
- [ ] The green start dot can be dragged on Stipple, Cross-stitch and Spiral fills but changes nothing (only Contour uses it): honor it, or don't offer the drag
- [ ] Cross-stitch fills show the purple direction dots although the angle doesn't change them (as before Phase 3)
- [ ] The side panel's "Check before stitching" title runs into its "Density map" box (seen at 1280 × 800; older than Phase 3)
- [ ] Rare engine quirks found stress-testing Spiral (all older): a travel stitch can reach 2.75 mm and run 0.31 mm outside a shape; ties between the parts of a self-crossing outline can be under 0.3 mm; one too-tiny piece makes a whole open-pattern fill refuse; with an Edge underlay, moving a symmetric open-pattern fill can start its edge run on another side

## From docs/PLAN.md backlog (not yet started)
Planned on 2026-11-24: every item in this section, and the nice-to-haves above that name a phase there, now sits in a phase (3 to 14) with a spec in `docs/phases/`. `docs/phases/README.md` has the index. The list stays for history; tick an item when its phase ships it.
- [ ] Thread inventory and shopping list
- [ ] SVG, DXF and PDF import
- [ ] Guided first-design tutorial; contextual hints and F1 help per tool
- [ ] Push compensation along stitch direction (patent check first)
- [ ] Stitch time and thread usage estimate
- [ ] Monogram templates and ornaments
- [ ] Multi-color blending, embossing/carving, 3D foam, patch edge (v2)
- [ ] Python plugin/scripting API; translations (v2)
- [ ] Browser/PWA build via Pyodide (Later)

## From Phase 4 (2026-11-25)
- [ ] The browser preview's engine uses your real LUDD data folder (`vite-engine-bridge.ts` starts it without `THREADLINE_DATA_DIR`): a preview can autosave over the recovery copy and add private copies. Give the dev bridge its own data folder unless asked otherwise
- [ ] "Don't sew what's hidden": the kept margin is still over the density limit; leaving the lower fill's edge run out round a cut would help (needs the fill generator to know which holes are cuts; PHASE-04 Build notes)
- [ ] L-002 with "Don't sew what's hidden" on: the fill router prefers a straight move across sewn rows to a covered way round
- [ ] Rebuild adds jumps and a few very short stitches in shapes with holes or notches (Wreath at 150%: 35 jumps instead of 15)
- [ ] The Repair window and the panel's Repair list preview once per repair on every design change (about 1 s each at 50,000 stitches)
- [ ] If P4-A1 is built, give `remove_hidden` its own project feature flag
- [ ] Planner: reword Phase 4 done-when 2 to "no cell over the limit past the keep margin" (what is built and tested); add an L- entry for the margin band over the limit, which today is only in F-1207 (Phase 4 audit, finding 1)
- [ ] `test_lower_fill_stops_under_the_cover` allows keep + 0.4 mm; the fill reaches keep + 0.16 to 0.20 mm: tighten to + 0.25 so a regression shows (Phase 4 audit, finding 3)

## From Phase 5 (2026-11-25)
- [ ] `RepairDialog.dom.test.tsx` "shows before and after ... after a 300 ms pause" uses real time: on a busy computer two clicks and a 100 ms wait can pass 300 ms and fail it (seen once in Phase 5's merge). Use fake timers
- [ ] Stitch fonts from letter files: the file-name guesser could also read uppercase/lowercase/caps/capital words, trailing uc/lc, U/L prefixes, doubled letters ("aa"), "capa", words such as exclamation_point, question_mark, full_stop, amp, plus, equals, star, dollar, percent, parentheses, "num1", size suffixes that differ per file, order numbers in front and "(1)"/"copy"; letters sold in several formats show as used twice; and one stray design in the folder stops the shared prefix from being removed (these are expected patterns; no bought font was available)
- [ ] Stitch fonts from letter files: a dotted j sits too low (the g j p q y rule puts its dot at small-letter height); treat j by its stem, not its box
- [ ] Stitch fonts: the preview in the dialog repeats the engine's baseline rules in TypeScript; have the engine return each letter's drop instead
- [ ] Stitched letters resized with the corner handles only stretch (LUDD says so): fold a handle resize into the letter height so they're rebuilt
- [ ] True satin: many large letters fall back (Arial at 60 mm: 27 of 62), mostly columns whose sides cross near the 7 mm limit; split wide strokes or relax the fold test
- [ ] True satin on letters whose strokes are all over 7 mm (Arial at 150 mm) sews as Satin-look fills, as designed (edges within 0.05 mm of Satin look's), but with no note: say so
- [ ] Shadow plus outline adds 2 to 3 s to the first drawing of a two-word text (mostly choosing the shadow fills' angles)
- [ ] Order & colors has no "Back to ..." for a single letter's own color (the letter panel can undo it)
- [ ] Color sets don't include single letters' own colors (L-035)
- [ ] True satin shows a start and end dot on every column (74 on "Happy Birthday"): consider showing them only for the letter under the mouse, or only on fills

## From the Phase 5 audit (2026-11-25)
- [ ] A stitched font typed under 6 mm says "underlay is left out so they stay thin", but its stitches aren't changed (the knowledge base says so; the app's note doesn't). Give stitched fonts their own wording, such as "Letters 5 mm tall are hard to stitch clearly. 6 mm or more is safer."
- [ ] The thin-stroke warning measures strokes at the letter height typed in; the resize handles and a single letter's own size don't count (the under-6 mm rule now does)
- [ ] An envelope's squeeze or swell isn't counted in the under-6 mm rule (the knowledge base says so): a pinched 7 mm text's middle letters can sew under 6 mm with underlay. The manual's "goes by the height each letter sews at" could add "(an envelope isn't counted)"
- [ ] True satin's pass or fall-back checks (`lettering/satin.py`: a letter's 97% cover, a join's cover, a column outside the letter) compare GEOS areas with their limits exactly; a letter right at a limit could fall back on one computer and not another. Low risk; a small margin or rounding before the compare would settle it
- [ ] Older than Phase 5: the text layout cache and the overlap areas cache key on the font path saved in the project; when that font is missing and a stand-in is used, installing the real font elsewhere doesn't redraw until the text is edited or LUDD restarts. Key on the font actually used

## From the Phase 5 pull request checks (2026-11-26)
- [ ] The older snapshot suites (`digitize`, `layout`, `fills_spiral`, `repair_*`) still use the plain digests, which depend on the last digit of a sine wherever a stitch lies exactly on a rounding step (Phase 5's `bulge` case failed on both Macs that way). If one fails on one kind of computer only, move it to `snapshot_util.digest_pattern_steady` and re-record
- [ ] The same last digit can move an exported stitch by one 0.1 mm step from one computer to another: harmless in thread, but rounding stitch coordinates to a millionth of a mm before the export rounds them would make the files the same everywhere

## From Phase 6 (2026-11-26)
- [ ] Gradient offers a Cross-hatch underlay button but never sews one (older than Phase 6; Blend, which doesn't either, no longer offers it): hide it for Gradient too (`noCrossHatch` in `fillPatterns.ts`) and update the panel test that lists Gradient's buttons
- [ ] The green start dot can be dragged on Ripple fills but changes nothing, like Stipple, Cross-stitch and Spiral (above)
- [ ] The line's Style row clips its Motif button at the panel's width (it shows "Mot" and the panel scrolls sideways): let the row wrap
- [ ] A ripple's middle can't be set in the app (the engine takes `ripple_center`): add a draggable middle dot
- [ ] A new third blend color can start as the first color again (navy, white, navy): start it unlike both
- [ ] Turning fills show thin lines of thread across finished rows (L-002), from moves between row groups and from long straight steps inside a group (rows are joined by their distance along the guide, so on the outside of a bend a step reaches 25.6 mm; spec P6-C2 step 6 asks for `travel()` there). Thread over rows sewn before and not covered after, more than 0.5 mm from the edge: 129 of 160 random shapes show over 1 mm, 60 rectangles 1,555 mm in all (also in the build the first audit saw); the re-audit measured unbroken lines up to about 9 cm across a shape, about 21 mm per shape at the median. A fix was tried and stopped (PHASE-06 section 12): the checked routing cut that to 186 mm, but 25 of the 60 stayed over 1 mm, 3 of them got a loose stitch 10 to 26 mm long, it ran about 3 times slower and edge travel tripled. It needs an order over the whole shape (sweep across the rows, or sew crease-wedged groups before their neighbours) and moves along edges only where needed. Joining rows only when their ends are within a stitch (8 lines, no snapshot changes) removes the long steps but alone barely changes what shows; do it as part of the same fix
