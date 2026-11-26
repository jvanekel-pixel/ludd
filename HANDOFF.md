# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-26
- **Current Phase:** Phase 5 (lettering) audit **PASSED** at `6e78498` (branch `claude/phase-05-lettering-f1ee69`): first audited at `79a6ea0` with five findings, none blocking; all five fixed and re-checked. This stamp lands on `main` with the Phase 5 pull request. `phase` is now 6. P5-C2 (BX fonts) not done by owner decision 1; L-036 says to use the letter files that came with the font.
- **Active Routing:** balanced (top model plans and audits, Sonnet builds)
- **Checks Run (audit, at `6e78498`):** `check.py --all` PASS with a frozen engine: engine 1630 passed, 2 skipped; UI 420; types, kb, build; Rust 2 passed. Engine with `fixtures/` copied in: 1675 passed, 1 skipped (copies removed). No snapshot file changed since `main` except Phase 5's three new ones and `rpc_methods.json`; no test deleted. True satin fall-backs re-measured on Arial (62 letters): 0 at 5 and 12 mm, 1 at 25, 27 at 60.
- **Findings, all fixed (each fix's tests fail with the fix switched off):**
  1. The under-6 mm rule read the typed height; underlay and the note now go by the height each letter sews at (handles, a turned or curved letter, a letter's own size; an envelope isn't counted, stitched fonts keep their stitches) (`1835d07`).
  2. Names-list file names: "Con.Smith"-style device names get a `_`, names cut at 100 characters or 200 bytes (`c7f5fde`).
  3. True satin's Satin-look pieces, and a letter with no columns, go in a fixed order (`24d4faa`).
  4. Done-when 4 now has a test of the app's own export against the real engine, in a temporary data folder, inside `pnpm test` (`968aec4`).
  5. The pull request text was corrected; the motif list test asserts all five motifs (`6e78498`).
- **Audit verdicts on the planner's points:** old text sews the same except letters sewn under 6 mm (decision 3, told in CHANGELOG, KB F-1420, stitchout-log); older tests changed only as the spec needs; True satin tests check shape and 97% cover; snapshots are exact on fonts built in the tests, cross-computer risk low; every new setting reaches every cache, including resizing across 6 mm and back; names-list files never leave the folder or overwrite; tests use a temporary data folder, names are made up, frames and placements are LUDD's own, plain text sets no project flag.
- **Parked (BACKLOG, "From the Phase 5 audit"):** a stitched font under 6 mm says underlay is left out though its stitches don't change; the thin-stroke note ignores the handles; envelopes aren't counted in the 6 mm rule; True satin's pass checks have no margin; an older stand-in-font cache gap.
- **Blocked On Human:**
  1. Answer the Phase 6 spec's Owner decisions.
  2. Older: P4-A1 patent check; tag v1.0.1; AI tracing download check; P6-A1 patent; photo stitch (Phase 9).
- **Next Action:** After the merge, Phase 6 (fills and stitch quality) in a fresh session: answer its spec's Owner decisions first.
