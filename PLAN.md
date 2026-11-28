# PLAN

Phase tracker for Command Center. This file only tracks phases and checkboxes. Each phase from 3 on has a full spec in `docs/phases/`; how a phase is built is in `BUILDPLAN.md`. The original milestone plan and research are in `docs/PLAN.md`.

Order of work (decided 2026-11-24, D-019): build the features first, phases 3 to 14; sew the stitch-outs once, in Phase 15; fix and release in Phase 16. Phases 3 to 12 close the gaps found in the competitive review (`docs/COMPETITIVE-REVIEW.md`); 13 and 14 are extras the owner can pull in or leave.

Built ahead of plan: sewing time and thread estimate (F-406), merged in pull request #23.

Owner actions that belong to no phase:
- Tag v1.0.1 when ready, ideally before Phase 3 merges; check the draft release's `latest.json`; publish. Moved out of Phase 2 on 2026-11-24.
- Check Settings > AI tracing > Download once.
- Before each phase: answer the "Owner decisions" table in its spec.

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

## Phase 2: 1.0.1 Hardening
Why it matters: two QA passes and the Phase 1 audit fixes had to be committed, merged and green before anything was built on top.
> Verify: `cd engine && uv run --locked pytest -q && pnpm typecheck && pnpm test && pnpm --filter @threadline/desktop build` | Done when: the QA fixes and the owner's decisions are merged to `main` and CI is green on Windows, both Macs and Linux
- [x] QA report written (docs/QA-REPORT.md, 420 findings)
- [x] QA phases 1-3 fixed: all Critical/High items C1-C26 (docs/QA-RESPONSE.md)
- [x] QA phase 4 (Medium/Low) fixed area by area (docs/qa-phase4/)
- [x] Knowledge base for the help agent (docs/LUDD-KNOWLEDGE-BASE.md)
- [x] Owner approves committing the uncommitted working tree; commit in logical groups
- [x] Owner decides the 20 open items listed in docs/QA-RESPONSE.md (decided 2026-11-14; applied in ed160f1)
- [x] Run the second QA pass using docs/QA-PROMPT.md and fix what it finds (docs/QA-REPORT-2.md, merged in #20)
- [x] Owner decides the 10 items on the QA pass 2 decision list (all as recommended, 2026-11-24)
- [x] Implement the 10 QA pass 2 decisions, with tests, docs and stitch-out rows (merged in #21)
- [x] Fix the three Phase 1 audit items (merged in #22)
- [x] Push to GitHub and confirm CI is green on Windows, both Macs and Linux

## Phase 3: Build Seams, Spiral Fill, More Shapes
Why it matters: today a new stitch type means editing five files of over 1,000 lines each, so only one worker can build at a time; this phase puts a seam at each of those places and proves them with two real features.
Spec: docs/phases/PHASE-03-build-seams.md
> Verify: `python scripts/check.py --all` | Done when: every earlier test passes with the two old snapshot files byte-for-byte unchanged, a spiral fill sews, five new shapes add from the Shapes menu, and the spiral change touched no existing file beyond its registry lines
- [x] P3-A Engine seams: `layout/` and `methods/` packages, render hooks, fill and line registries, feature-flag table
- [x] P3-B UI seams: command registry and `cmd/`, panel split, pattern descriptors, dialog registry, canvas hooks
- [x] P3-C Tooling: `scripts/check.py`, `kb_commands.py --check`, snapshot files per suite, stitch invariants
- [x] P3-D1 Spiral fill
- [x] P3-E1 More shapes: rounded rectangle, oval, triangle, polygon, heart
- [x] P3-Z1 Docs and the frozen-engine smoke check

## Phase 4: Merge-Safe Stitch Files
Why it matters: merged and resized bought designs are the top cause of needle breaks, and Embrilliance sells the fix as a separate product (Density Repair Kit).
Spec: docs/phases/PHASE-04-merge-safe-stitch-files.md
> Verify: `python scripts/check.py --all` | Done when: a stitch file scaled to 150% or 60% and rebuilt keeps its row spacing within 10% of the original, two overlapping drawn fills sew nothing hidden and show no red on the density map, and Repair changes nothing until Accept
- [ ] P4-A1 Remove stitches of a placed design hidden under what is sewn on top (held: owner decision 1 in the spec)
- [x] P4-A2 Don't sew what's hidden under shapes on top (drawn shapes)
- [x] P4-B1 Repair dialog with before and after numbers; Fix it on the checks
- [x] P4-B2 Remove tiny stitches (fixes, not only warns)
- [x] P4-B3 Thin out spots where the needle hits over and over
- [x] P4-B4 Edit stitches: insert a stitch, insert a jump, lock both sides of a jump
- [x] P4-B5 Needle path view
- [x] P4-C1 Recognize fills, satins and runs inside a stitch file
- [x] P4-C2 Rebuild stitches at a new size (narrows L-020)
- [x] P4-C3 Limit density for the fabric

## Phase 5: Lettering & Personalization
Why it matters: lettering is LUDD's biggest gap (11 of 17 lettering features missing) and where hobbyists spend most time; AlphaTricks ($119) and BX fonts keep users tied to Embrilliance.
Spec: docs/phases/PHASE-05-lettering.md
> Verify: `python scripts/check.py --all` | Done when: a two-line, slanted, envelope-shaped name with one letter moved and recolored renders, a folder of 26 single-letter PES files becomes a working stitch font, and a CSV of names fills two placeholders
- [x] P5-A1 Multi-line text with line spacing and left/center/right (lifts L-003)
- [x] P5-A2 Slant
- [x] P5-A3 Envelopes (bulge, pinch, pennant, wave, arch) and vertical text
- [x] P5-A4 Adjust single letters: move, turn, size, thread, stitch angle (lifts L-005)
- [x] P5-B1 True satin columns from outline fonts (narrows L-014)
- [x] P5-B2 Small letters: underlay left out under 6 mm; thin-stroke warning
- [x] P5-C1 Stitch font from a folder of single-letter stitch files
- [x] P5-D1 Names from a list (CSV) and templates with placeholders
- [x] P5-D2 Monogram styles and frames
- [x] P5-D3 Shadow and outline that follow the text
- [x] P5-D4 Placement guides for towels, bedding and garments

## Phase 6: Fills & Stitch Quality
Why it matters: two-color blend is Hatch 4's headline feature and is locked to its $1,199 Digitizer level; push compensation, weave and feathering make ordinary fills sew better.
Spec: docs/phases/PHASE-06-fills-and-stitch-quality.md
> Verify: `python scripts/check.py --all` | Done when: every new fill and option has its tests, snapshots, invariants and a PES and JEF round trip; a two-color blend's combined density is within 15% of a plain fill; rows follow each angle line within 5 degrees
- [ ] P6-A1 Push compensation ("End trim") for fills and satins (held: owner decision 1 in the spec)
- [x] P6-A2 Weave: standard, brick, twill, smooth, random
- [x] P6-A3 Carved lines in a fill (emboss)
- [x] P6-A4 Feathered edges
- [x] P6-A5 Hand-sewn look for lines, satins and fills
- [x] P6-B1 Motif fill
- [x] P6-B2 My motifs: save a drawn line as a motif; import and export
- [x] P6-B3 Maze fill
- [x] P6-B4 Ripple fill
- [x] P6-B5 Mesh fill
- [x] P6-C1 Blend: two or three colors fading into each other (lifts L-001)
- [x] P6-C2 Turning fills: several angle lines in one fill

## Phase 7: Lines, Sequencing & Drawing Tools
Why it matters: branching is sold only in StitchArtist Level 3 ($699); freehand drawing and SVG import are what people expect from any drawing program.
Spec: docs/phases/PHASE-07-lines-sequencing-drawing.md
> Verify: `python scripts/check.py --all` | Done when: three touching same-thread fills in a branch, and lines and satin ribbons meeting end to end, sew with no trim or jump between them (any other join sews hidden or says why it cuts), a 300-sample freehand stroke becomes 25 curve points or fewer within 0.4 mm at 3.8 screen pixels per mm or more, and an SVG imports as a fill, a line and a satin ribbon at real size after a preview (the first two reworded by the planner, 2026-11-27)
- [x] P7-A1 Line styles: backstitch, stem stitch, candlewicking, redwork, French knots
- [x] P7-A2 Blackwork fill
- [x] P7-A3 Which side a motif line sits on
- [x] P7-A4 Lock-stitch shapes: standard, triangle, back-tack
- [x] P7-A5 Buttonholes and eyelets
- [x] P7-B1 Branch: sew selected shapes as one path with one start and one end
- [x] P7-B2 Branch dots, commands and panel note
- [x] P7-B3 Optimize jumps also moves an applique's start and a text's first letter (part of L-017)
- [x] P7-C1 Freehand drawing with smoothing (lifts L-011)
- [x] P7-C2 Continue a line or satin ribbon from either end
- [x] P7-C3 Repeat dialog: mirror, wreath, kaleidoscope
- [x] P7-C4 Stitch presets: save, apply, import, export
- [x] P7-D1 Import SVG and DXF artwork as editable shapes
- [x] P7-D2 PDF artwork: vector paths if a time-boxed attempt works, else the page as a picture

## Phase 8: Specialty & In-the-Hoop
Why it matters: lace, puff, patches and multi-position hoops are what hobbyists buy StitchArtist Level 2-3, PatchArtist or a bigger machine for.
Spec: docs/phases/PHASE-08-specialty-in-the-hoop.md
> Verify: `python scripts/check.py --all` | Done when: a lace ornament passes the lace checks, a puff letter and a patch each render from a sample project, three shapes in one applique set stop the machine twice, and a 100 x 170 mm design saves as three files for a three-position hoop
- [ ] P8-A1 Lace fill: grid, diamonds, honeycomb
- [ ] P8-A2 Freestanding-lace fabric choice and the checks that the lace holds together
- [ ] P8-A3 3D puff satin
- [ ] P8-B1 Applique sets: several pieces from a selection, two stops
- [ ] P8-B2 Applique border left out where a later shape covers it
- [ ] P8-B3 Applique with open edges chosen by hand
- [ ] P8-B4 Patch edge (faux merrow)
- [ ] P8-B5 Make a patch, with its cut file
- [ ] P8-B6 FCM cut file for ScanNCut (only if owner decision 1 in the spec says build)
- [ ] P8-C1 Hoops with fixed positions; the design split into them
- [ ] P8-C2 Positioning stickers and a hooping sheet to print
- [ ] P8-C3 Sew from the center out (caps)
- [ ] P8-C4 Basting box margin

## Phase 9: Images & Photo Stitch
Why it matters: photo stitch is in every big competitor but LUDD, and a one-click color fill is what beginners reach for first.
Spec: docs/phases/PHASE-09-images-photo-stitch.md
> Verify: `python scripts/check.py --all` | Done when: one wand click matches the true outline within 1 mm, whole-picture auto-digitize shows progress and Cancel stops it within a second, and a photo becomes ordinary fills that sew darker where the photo is darker
- [ ] P9-A1 Progress and Cancel for background engine jobs
- [ ] P9-A2 Magic wand
- [ ] P9-A3 Simplify the picture's colors before auto-digitize
- [ ] P9-B1 Tone fill pattern (rows that follow a brightness map)
- [ ] P9-B2 Photo stitch with an editable result (owner decision in the spec: `SPEC.md` lists it as out of scope; lifts L-008)
- [ ] P9-B3 Cross-stitch from a picture
- [ ] P9-C1 Save a picture of the design (PNG), with the garment preview
- [ ] P9-C2 Design notes saved in the project
- [ ] P9-C3 Lighten or darken all colors together

## Phase 10: Design Library, OS Thumbnails & Thread Inventory
Why it matters: OS thumbnails and an organizer are sold separately (Embrilliance Thumbnailer $44.95, Hatch Organizer), and people with thousands of designs cannot find anything.
Spec: docs/phases/PHASE-10-library-thumbnails-inventory.md
> Verify: `python scripts/check.py --all` | Done when: a folder of 1,000 designs shows tagged thumbnails and opens fast the second time, the duplicate finder groups copies, Explorer shows thumbnails for projects and PES/JEF/DST, and the shopping list names every missing or low thread
- [ ] P10-A1 Library index and incremental scan
- [ ] P10-A2 Thumbnails kept on disk between sessions
- [ ] P10-A3 Search, filters, paging
- [ ] P10-A4 Tags and collections
- [ ] P10-A5 Duplicate finder
- [ ] P10-B1 Organizer window replaces Browse designs
- [ ] P10-B2 Find, tag and duplicate review in the organizer
- [ ] P10-C1 Thumbnail crate with bounded readers for PES, JEF, DST and `.ludd`
- [ ] P10-C2 Windows Explorer thumbnails
- [ ] P10-C3 Linux file-manager thumbnails
- [ ] P10-C4 A preview picture inside every saved `.ludd`
- [ ] P10-D1 How much is left on each spool
- [ ] P10-D2 Thread inventory and shopping list

## Phase 11: Learnability
Why it matters: the steep learning curve is the most common complaint about every digitizer.
Spec: docs/phases/PHASE-11-learnability.md
> Verify: `python scripts/check.py --all` | Done when: a new user finishes the guided first design without the manual, F4 switches Simple and Expert, every panel setting has a hint, and F1 opens Help at the section for what is in use
- [ ] P11-A1 Simple / Expert switch
- [ ] P11-A2 Reset arrow beside a setting that is not at its standard value
- [ ] P11-A3 Hint text and pictures, written once
- [ ] P11-A4 Hint pane
- [ ] P11-A5 F1 opens Help at the right section
- [ ] P11-B1 Start screen with recent designs
- [ ] P11-B2 Guided first design
- [ ] P11-B3 Troubleshooting by symptom
- [ ] P11-C1 Hide, show and ghost mode
- [ ] P11-C2 Show one color
- [ ] P11-C3 Snap new points to shapes
- [ ] P11-C4 Travel by object in the player
- [ ] P11-D1 Find a command
- [ ] P11-D2 Change keyboard shortcuts
- [ ] P11-D3 Workspaces

## Phase 12: Machines, Threads & Languages
Why it matters: only two machines and two thread brands are built in, and the app speaks only English.
Spec: docs/phases/PHASE-12-machines-threads-languages.md
> Verify: `python scripts/check.py --all` | Done when: typing a model name finds a profile that names its source, a multi-needle machine gets a color-to-needle plan, four more thread brands match offline, the whole app runs in a second language, and three schemas validate every sample and data file
- [ ] P12-A1 Machine profiles as data files with a source and a verified mark
- [ ] P12-A2 Choose your machine from a searchable list
- [ ] P12-A3 The first set of machines, entered from manuals (lifts L-018)
- [ ] P12-A4 Assign colors to needles
- [ ] P12-A5 Machine setup advice
- [ ] P12-B1 Thread chart data files with credits (owner decision in the spec: licensing)
- [ ] P12-B2 Charts load on first use, each with a thread weight
- [ ] P12-B3 Thread-weight guidance
- [ ] P12-C1 `t()` helper, string harvest, pseudo-language test
- [ ] P12-C2 Every UI string goes through `t()`
- [ ] P12-C3 Every engine message is a template the UI can translate
- [ ] P12-C4 Language choice in Settings; catalogs for the first languages
- [ ] P12-C5 The in-app guide in each language
- [ ] P12-D1 Project, fabric and thread-chart JSON Schemas
- [ ] P12-D2 Schema tests

## Phase 13: Long-Tail Stitch Features
Why it matters: these are the review's "Later" rows; they finish the comparison with Wilcom and Floriani but none is a top complaint, so the owner may pull in only some.
Spec: docs/phases/PHASE-13-long-tail-stitch-features.md
> Verify: `python scripts/check.py --all` | Done when: a known run, satin and fill sewn to stitches and turned back into shapes match within 0.5 mm, 3 degrees and 10%, the new stitch types pass their tests, and word art fills a circle with ten words that do not overlap
- [ ] P13-A1 Recognition of runs, satins and fills with their underlay
- [ ] P13-A2 Shapes from what was recognized, each with a confidence
- [ ] P13-A3 File slices: a placed file that shows only part of its stitches
- [ ] P13-A4 Turn stitches into shapes, previewed first (lifts L-007)
- [ ] P13-B1 Chain stitch
- [ ] P13-B2 String stitch
- [ ] P13-B3 Shadow work
- [ ] P13-B4 Cutwork needle lines (owner decision in the spec)
- [ ] P13-B5 Outline for cross-stitch fills
- [ ] P13-B6 One underlay under touching shapes
- [ ] P13-C1 Word art
- [ ] P13-C2 Parts library

## Phase 14: Extensibility, Accessibility & Performance
Why it matters: plugins let others add stitch types without touching the core, and the app must stay usable by keyboard, by screen reader and on 100,000-stitch designs.
Spec: docs/phases/PHASE-14-extensibility-accessibility-performance.md
> Verify: `python scripts/check.py --all` | Done when: with plugins off nothing in the plugins folder runs and with them on two example plugins work, the accessibility test passes for the panel and every dialog, and a 100,000-stitch design meets the performance budget
- [ ] P14-A1 Plugin loader and trust rules (owner decision in the spec)
- [ ] P14-A2 The `ludd` plugin API, version 1
- [ ] P14-A3 Plugin stitch types in the panel and in project files
- [ ] P14-A4 Scripts: run on this design
- [ ] P14-A5 Plugins dialog
- [ ] P14-A6 Two example plugins and `docs/PLUGINS.md`
- [ ] P14-B1 Keyboard reach and a visible focus ring everywhere
- [ ] P14-B2 Names, roles and announcements for screen readers
- [ ] P14-B3 More contrast, text size, reduced motion
- [ ] P14-B4 Pen and touch on the canvas
- [ ] P14-B5 High-DPI check
- [ ] P14-B6 Automated accessibility checks and the manual checklist
- [ ] P14-C1 Benchmark script, test designs, budget table
- [ ] P14-C2 Stitch records sent as typed arrays
- [ ] P14-C3 Engine caching for placed files
- [ ] P14-C4 Canvas level of detail
- [ ] P14-C5 Bundle split
- [ ] P14-C6 Stipple speed
- [ ] P14-C7 Memory-limited reader for risky formats (owner decision in the spec; lifts L-024)
- [ ] P14-C8 Second Recover slot (owner decision in the spec)
- [ ] P14-C9 AI key in the system keychain (owner decision in the spec)

## Phase 15: Stitch-Out Verification on the PE550D
Why it matters: automated tests cannot prove thread on fabric, so every output-changing feature is unverified until the machine stitches it.
Spec: docs/phases/PHASE-15-stitch-out-verification.md
> Verify: Manual review of docs/stitchout-log.md | Done when: every row in "Pending machine tests" has a photographed result logged as pass or a fix item filed, and every first-guess constant has a verdict
- [ ] Owner confirms the build phases wanted for 2.0 are done and stitching can start
- [ ] P15-A1 Test sheets that pack several rows into one hooping
- [ ] P15-A2 Printed checklist that matches the sheets
- [ ] P15-B1 Sew the sheets: files and machine, fills, satins and lines, lettering
- [ ] P15-B1 Sew the sheets: fabric presets, applique and split, stitch files, pictures
- [ ] JEF hoop and stop codes on a Janome (owner decision in the spec)
- [ ] P15-C1 Results logged; fix list and constant verdicts written
- [ ] P15-C2 First Mac build checked (Intel build starts, Finder open, Cmd+Q)

## Phase 16: Fixes, Public Manual & 2.0 Release
Why it matters: what the machine taught has to become fixes, and strangers need a manual, before 2.0 is the first release whose every stitch type has been sewn.
Spec: docs/phases/PHASE-16-fixes-manual-release.md
> Verify: `python scripts/check.py --all` | Done when: every fix-list item is fixed with a test or agreed as a known limit, fixed rows are re-sewn and pass, the release audit finds nothing Critical or High, and a v2.0.0 draft release has all four builds and a correct `latest.json`
- [ ] P16-A1 Work through the stitch-out fix list, each with a test
- [ ] P16-A2 Apply the constant verdicts
- [ ] P16-A3 Defaults the stitch-outs decide
- [ ] P16-A4 Re-sew the fixed rows
- [ ] P16-B1 Manual: editorial pass, screenshots, PDF
- [ ] P16-B2 Quick-start guide and README
- [ ] P16-B3 New samples
- [ ] P16-C1 Confirm the name "LUDD" is free before wider promotion
- [ ] P16-C2 Release audit with docs/QA-PROMPT.md
- [ ] P16-C3 Version 2.0.0, release notes, draft release; owner publishes
