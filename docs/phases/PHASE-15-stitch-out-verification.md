# Phase 15: Stitch-out verification on the PE550D

| | |
| --- | --- |
| Weight | The owner's hands and the machine. One short build session before it, one short logging session after. |
| Session lead | Sonnet 5.5 for the two sessions; no workers |
| Depends on | Every build phase the owner wants in 2.0 |
| Changes stitches | No. It finds what Phase 16 must change. |
| Old plan | Phase 3 (moved here on 2026-11-24: features first, machine testing after, D-012 and D-019) |

## 1. Goal and done-when

Tests prove the stitches are where the code meant them. Only thread on fabric proves they sew well. Every stitch-changing feature since 1.0.0 has a row waiting in `docs/stitchout-log.md`.

**Done when:**

1. Every row under "Pending machine tests" has an entry in the Log table: date, fabric and stabilizer, result (pass, or what went wrong), and a photo file name.
2. Every row that did not pass has a fix item in section 6's list, with enough detail to reproduce it.
3. The constants in section 5 each have a verdict: keep, or change to a stated value.
4. The first Mac build has been run once on a Mac (Finder open, Cmd+Q, the Intel build starts).

## 2. Scope

| ID | Item | Who |
| --- | --- | --- |
| P15-A1 | Test sheets: sample projects that pack several rows into one hooping | Build session |
| P15-A2 | A printed checklist that matches the sheets | Build session |
| P15-B1 | Sew the sheets; photograph; write what happened | Owner |
| P15-C1 | Log results; write the fix list and the constant verdicts | Logging session |
| P15-C2 | Mac check | Owner, or anyone with a Mac |

**Out of scope:** fixing anything (Phase 16). JEF on a Janome needs a Janome: see decision 1.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | JEF hoop and stop codes have never been sewn on a Janome (D-006, D-017). Borrow one, ask a Janome owner to sew three files, or leave it marked unverified? | Ask a Janome owner: the three files are small. | The rows stay pending and L-016 says JEF is unverified on a real machine. Phase 15 can still close: note the exception in `HANDOFF.md`. |
| 2 | Which fabrics are on hand? | Quilting cotton, a T-shirt, a towel, felt, with the stabilizers the fabric presets name. | Sheets are made for cotton first; knit and towel sheets are marked optional. |
| 3 | An early look after Phase 8 on the six foundation rows (section 4)? | Yes if there is a free hour: it is cheap insurance. | Not done; everything waits for this phase. |

## 4. The rows, grouped

`docs/stitchout-log.md` is the list of record; this section only groups it. Count the rows when the session starts.

**Foundation six** (the rows everything else rests on; these are the "early look" in decision 3):

| # | Row in the log | Why it is foundational |
| --- | --- | --- |
| 1 | M4 Three-object test design | Fill, satin and run basics |
| 2 | M4 Fill angles and density | The density scale every fill uses |
| 3 | M4 Satin widths | Pull compensation |
| 4 | M7 Fabric presets | The fabric table every shape reads |
| 5 | M2 Cut-stops on the PE550D | The owner's machine cuts only at color changes |
| 6 | M6 10 mm name in a script font | Lettering at the size hobbyists use most |

**Groups for the full run** (one sheet or a few per group):

| Group | Rows from | Sheets |
| --- | --- | --- |
| Files and machine | M1 to M3, PES placement, accented names, cut-stops | 2 |
| Fills | M4, 1.0.1 fill patterns, QA2 rows, Phase 3 spiral, Phase 6 fills | 4 to 6 |
| Satins and lines | M4, ribbons, motif lines, satin fill, Phase 6 and 7 lines | 3 to 4 |
| Lettering | M6, 1.0.1 lettering rows, Phase 5 | 4 |
| Fabric | M7 presets, towel rows, knockdown | 3 (one per fabric) |
| Applique and split | M8, 1.0.1 applique and split rows, Phase 8 | 3 |
| Stitch files | 1.0.1 edited stitches, Phase 4 repair rows | 3 |
| Pictures | auto-trace and whole-picture rows, Phase 9 | 2 to 3 |
| Janome | the JEF rows | decision 1 |

## 5. Constants waiting for a verdict

First guesses made without a machine. Each phase's handoff adds its own; gather them here when the build session starts.

| Constant | Where | Set in | Verdict |
| --- | --- | --- | --- |
| Fabric table: density, Edge pad, underlay level | `fabrics.py` `FABRICS` | 1.0.0 | |
| End trim per fabric | `fabrics.py` `push_comp_mm` | Phase 6 | |
| Density limits per fabric | `repair/density.py` | Phase 4 | |
| "Keep under the edge" defaults (1.0 and 0.8 mm) | `repair/overlap.py`, `repair/hidden.py` | Phase 4 | |
| Small-letter threshold (6 mm) and no-underlay rule | `lettering` `SMALL_TEXT_MM` | Phase 5 | |
| True satin spacing (0.36) | `lettering/satin.py` | Phase 5 | |
| Blend: combined density, lone-row cutoff (4 mm) | `digitize/fills/blend.py` | Phase 6 | |
| Spiral: tight-ring warning (0.6 mm) | `digitize/fills/spiral.py` | Phase 3 | |
| Long stitch limit (7 mm), short stitch (0.3 mm) | `stitches.py`, `quality.py` | 1.0.0 | |
| Lock stitch length (0.7 mm) | `TIE_MM` | 1.0.0 | |

## 6. The two sessions

### Build session (before the machine)

**P15-A1 Test sheets.** New `scripts/make_stitchout_sheets.py`, in the style of `scripts/make_samples.py`: it writes `.ludd` projects and their PES files into `stitchouts/` (add `stitchouts/*.pes` and `*.jef` to `.gitignore`; keep the `.ludd` files and a `README.md`). Each sheet fits the 4" × 4" hoop with a 5 mm margin, uses at most four thread colors, and has a small stitched label beside each test (a number in a 5 mm run-stitch font) so a photo can be matched to its row.

Rules for packing a sheet: tests that need the same fabric and stabilizer go together; a test that needs its own hooping (split designs, applique, towel) gets its own sheet; nothing overlaps; 3 mm between tests.

Tests: `engine/tests/test_stitchout_sheets.py` checks that every sheet renders, fits the hoop, has no quality-check errors, and that every pending row's test is on some sheet (a table in the script maps row titles to sheets; a row with no sheet fails the test with its title).

**P15-A2 Checklist.** The script also writes `stitchouts/CHECKLIST.md`: per sheet, the fabric, stabilizer and topping, the thread colors in order, and for each numbered test the "What to check" text from the log with a blank line for the result. Printable from the app's print dialog or any Markdown viewer.

### Owner at the machine

For each sheet: hoop the fabric with the stabilizer the checklist names; sew; photograph front and back before unhooping (phone is fine; name the file `sheet-<n>-front.jpg`); write a few words per test on the checklist. A test that fails badly enough to stop (thread nest, needle break) gets the stitch number from the machine's screen if it shows one.

### Logging session (after)

**P15-C1.** The owner gives the photos and the filled-in checklist. The session:
1. Adds a row to the Log table per test: date, milestone, design, machine, fabric and stabilizer, result, notes.
2. Moves passed rows out of "Pending machine tests".
3. Writes the fix list below, one item per failure: `X-01`, the row, what was seen, the suspected cause, the file and constant or function to look at, and the test that should have caught it (to be written in Phase 16).
4. Fills the Verdict column in section 5.
5. Updates L-016 ("Real machine verification") in the knowledge base.

## 7. Fix list

*(Filled in by the logging session. Phase 16 Track A works through it.)*

| ID | Row | What happened | Suspected cause | Look at |
| --- | --- | --- | --- | --- |

## 8. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| Too many rows for one sitting | The groups in section 4 are independent: do Foundation, Fills and Lettering first; the rest another day |
| A failure makes later tests on the sheet meaningless | Each test is separate on the sheet; skip to the next number |
| No Janome | Decision 1's fallback |
| A photo does not show the problem | The checklist note is the record; the photo is a help |

## 9. Handoff

Write: how many rows passed, how many are in the fix list, which constants change, and whether the Janome and Mac checks happened. Phase 16 starts from the fix list.
