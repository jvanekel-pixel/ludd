# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-25
- **Current Phase:** Phase 5 (lettering) **built, not yet audited**, on local branch `claude/phase-05-lettering-f1ee69` (from `8ce7f28`; `origin/main` has not moved). Not pushed, no PR, no tag. `phase` stays 5 until the audit and merge.
- **Active Routing:** balanced (top model plans and audits, Sonnet builds; Track B on Opus 5.5)
- **Checks Run:** `check.py --all` PASS with a frozen engine, so Rust ran: engine 1601 passed, 2 skipped (main 1221/2); UI 416 (337); types, kb, build; Rust 2. With the owner's designs copied into `fixtures/`: 1646 passed, 1 skipped (1266/1); copies removed.
- **Done when 1-6: met.** 4: CSV engine test, app test with a stand-in engine, and a one-off app export with the real engine (3 files byte-identical to typing each row in). No test deleted; old expectations changed only where Phase 5 changes behavior; old snapshots (with `layout.json`) unchanged.
- **Not done:** P5-C2. Owner decision 1 skipped the BX look, so it found nothing; L-036 says to use the letter files that came with the font.
- **True satin fallbacks:** test font 0; Arial A-Z, a-z, 0-9: 0 of 62 at 5 and 12 mm, 1 at 25, 27 at 60. Parts over 7 mm are Satin-look fills by design (all of Arial at 150 mm, edges within 0.04 mm of Satin look, with no note: BACKLOG).
- **Stitched fonts:** Phase 4's rebuild is wired in past a 20% size change (not only the warning); the corner handles only stretch, and LUDD says so.
- **Naming patterns missed** (expected ones; no bought font was available, none from the owner's files): several formats per letter, per-file size suffixes, order numbers, "(1)"/"copy", caps/lowercase words, uc/lc or U/L, doubled letters, spelled-out punctuation; one stray design stops prefix removal (BACKLOG).
- **Behaves differently:** under 6 mm no underlay (decision 3); a 4-letter monogram is refused (before: the first three sewn without a word), so such names-list rows aren't saved.
- **Seen in the app** (scratch data folder): slanted two-line name in a Bulge clean and centered; single letters: one dot each, a dragged letter moved 5.1 mm, Put back and Esc work; True satin follows strokes (many dots: BACKLOG); no console errors.
- **For the audit:** spec section 12 lists departures; look at Step 0 `a1ec927`, integration `28f8f36` and `9c35a79`, tie rules in `lettering/satin.py`. Spec flaw built as written: a stitched font's dotted j sits low (T-029).
- **Blocked On Human:** nothing for the audit. Older: P4-A1 patent check; tag v1.0.1; AI tracing download check; P6-A1 patent; photo stitch (Phase 9).
- **Next Action:** Phase 5 audit on the top model (phase-audit-gate), started by the planning session; then the owner's yes before pushing and opening the pull request (its text is kept outside git).
