# Phase 16: Fixes, public manual & 2.0 release

| | |
| --- | --- |
| Weight | Medium |
| Session lead | Sonnet 5.5 |
| Audit | The release audit, by the top model, is part of this phase (Track C) |
| Depends on | Phase 15 (its fix list and constant verdicts) |
| Changes stitches | Yes: whatever the stitch-outs said to change |
| Old plan | The launch items of Phase 4 ("confirm the name") and the stop-contract of Phase 3 |

## 1. Goal and done-when

Turn what the machine taught into fixes, make the manual fit for strangers, and ship 2.0: the first LUDD release whose every stitch type has been sewn.

**Done when:**

1. Every item in Phase 15's fix list is fixed with a test that fails without the fix, or is recorded as a known limit (`L-`) with the owner's agreement.
2. Every fixed item's row has been re-sewn and logged as pass.
3. The release audit finds nothing Critical or High.
4. `docs/USER-MANUAL.md` covers every feature in the knowledge base's capability index, and `docs/LUDD-User-Manual.pdf` is regenerated from it.
5. The name check is recorded in `DECISIONS.md`.
6. A draft release `v2.0.0` has all four builds and a correct `latest.json`; the owner publishes.

## 2. Scope

| ID | Item | Track |
| --- | --- | --- |
| P16-A1 | Work through the fix list: reproduce in a test, fix, re-record snapshots on purpose | A |
| P16-A2 | Apply the constant verdicts | A |
| P16-A3 | Defaults the stitch-outs decide (True satin as the default? End trim on?) | A |
| P16-A4 | Re-sew sheet for the fixed rows | A (owner sews) |
| P16-B1 | Manual: one editorial pass, screenshots, the PDF | B |
| P16-B2 | Quick-start guide and README | B |
| P16-B3 | Samples that show off 2.0 | B |
| P16-C1 | Name check | C (owner) |
| P16-C2 | Release audit | C (top model, own session) |
| P16-C3 | Version 2.0.0, release notes, the release | C |

A and B run together; C follows.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Is the name "LUDD" free to use for embroidery software (trademark and app-store search in the countries that matter to you)? | The owner's check; an hour with the trademark databases. Record the result as a decision. | The release is held at "draft" until this is answered. |
| 2 | Code-sign the installers for 2.0 (D-009's "revisit if")? | Decide on cost against how many people report the warning. Signing on a Mac also unlocks Finder thumbnails (Phase 10). | Unsigned, as now; L-015 stays. |
| 3 | Which fix-list items may become known limits instead of fixes? | Only ones that need hardware or a redesign. | Everything is fixed or the phase stays open. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Fix list exists | `grep -c "^| X-" docs/phases/PHASE-15-stitch-out-verification.md` | one or more (zero means nothing failed: skip Track A's fixes) |
| Verdicts filled | section 5 of the Phase 15 file | no empty Verdict cell |
| Baseline | `python scripts/check.py --all` | `RESULT: PASS` |
| Manual tools | `git ls-files scripts/make_manual_pdf.py scripts/make_samples.py` | both |

## 5. Tracks

### Track A: fixes from the machine

**Owns:** whatever each fix item names; `fabrics.py`; `scripts/make_stitchout_sheets.py` (one more sheet).

For each item `X-nn`, in the list's order:
1. Write a test that shows the fault in numbers (a density, a width, a gap, a stitch length, a missing lock). If the fault cannot be put in numbers, say so in the item and fix by the suspected cause.
2. Fix it. Smallest change that makes the test pass.
3. Run the snapshot suites. Each one that changes is listed in the commit message with the item's ID: these re-records are intended.
4. Add the item's test to the sheet for re-sewing.

**P16-A2.** Change each constant whose verdict says so. A constant that changes many snapshots (the fabric table) is one commit of its own.

**P16-A3.** Defaults: change only what a logged stitch-out supports, and write a decision for each (`D-`).

**P16-A4.** One more sheet from `make_stitchout_sheets.py` with every fixed item. The owner sews it; results go in the log. An item that fails again goes back to step 1 once; after that it is the owner's call under decision 3.

Tests: every `X-nn` has a test named `test_x<nn>_<what>` in the suite of the area it touches.

### Track B: the manual and samples

**Owns:** `docs/USER-MANUAL.md`, `docs/USER-GUIDE.md`, `docs/images/**`, `docs/LUDD-User-Manual.pdf`, `README.md`, `samples/**`, `scripts/make_samples.py`.

**P16-B1.** Every phase added its own manual sections as it shipped. This pass makes them one book: the chapter order of the owner's manual outline (the Claude Doc "LUDD User Manual - Outline"; ask the owner for its current text), one voice, no feature described twice, every shortcut checked against the command table, a troubleshooting chapter by symptom, and a "what's new since 1.0" page. Screenshots: taken from the running app at one window size in light mode; a list of the shots needed is written first so the owner can take any the session cannot. Regenerate the PDF with `scripts/make_manual_pdf.py`.

A test already ties the in-app guide's shortcuts to the command table; add `test_manual_covers_the_capability_index`: every `F-` ID with status YES in the knowledge base's index is mentioned by title in the manual.

**P16-B2.** `docs/USER-GUIDE.md` becomes a four-page quick start (install, open and save for the machine, your first shape, your first name). `README.md` gets the 2.0 feature list and three screenshots.

**P16-B3.** Three or four new samples that use what is new (a blended fill, a multi-line name in a frame, a repaired merge, a patch), made by `scripts/make_samples.py` so the golden test keeps them honest.

### Track C: release

**P16-C1.** The owner's name check; the session records the result as a decision.

**P16-C2.** A fresh session on the top model runs `docs/QA-PROMPT.md` over everything since `v1.0.1` (or the last release audit). Findings come back as a report in `docs/QA-REPORT-3.md` with the same severity scale as the earlier two. Critical and High are fixed in this phase with tests; the rest go to the owner as a decision list, as in QA pass 2.

**P16-C3.** `docs/RELEASING.md`, step by step: version `2.0.0` in the four places it lives, changelog heading dated, release notes written for people who have never seen the changelog, samples regenerated, then the tag and the draft release when the owner says so. The knowledge base's "Version described" and L-016 are updated in the same change.

## 6. Integration

1. Merge A, then B. `python scripts/check.py --all`.
2. Track C's audit runs on the merged branch. Its fixes are merged the same way.
3. `pnpm build:engine` and one installer build from CI (local NSIS bundling has failed before with "file in use": use the CI artifact).
4. Stop contract. The tag, the push and the Publish button are the owner's.

## 7. Docs payload

- Changelog: `## 2.0.0 (date)` gathers the unreleased sections; a short "Checked on the machine" paragraph says what was sewn.
- Knowledge base: L-016 "Real machine verification" becomes "Done for 2.0 on a Brother PE550D" with any exceptions (JEF on a Janome); history row; version.
- `docs/stitchout-log.md`: "Pending machine tests" holds only what is truly still pending, each with why.
- `DECISIONS.md`: name check; any default changed in A3; signing.

## 8. Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| A fix changes many snapshots and hides a second change | One fix per commit; each commit lists the suites it re-recorded |
| The fix list is long | Fix by group (fabric table first: it moves the most), re-sew once per group |
| Screenshots cannot be taken by the session | The shot list goes to the owner; the manual ships with the ones that exist and a test that no image link is broken |
| The audit finds something structural | It becomes its own phase after 2.0, or 2.0 waits: the owner's call |
| Name check fails | The rename path from the Threadline → LUDD change exists (D-008): internal names stay, the product name and brand files change |

## 9. Handoff

Write: what shipped in 2.0, what was left as a known limit and why, and the first three things worth doing next (from `BACKLOG.md` and the audit's lower-severity list).
