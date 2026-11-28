# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-27
- **Current Phase:** Phase 7 (lines, sequencing and drawing tools) built and the audit's findings fixed (NOT YET at `1299ab8`) on local branch `claude/phase-07-lines-cf5833`; re-audit pending, nothing pushed.
- **Active Routing:** Sonnet lead; fix workers: artwork (Sonnet 5.5) and branching (Opus 5.5), their commits cherry-picked.
- **Checks:** `check.py --all` PASS (engine frozen from this code): engine 3297 passed, 2 skipped; UI 726; types, kb, build; Rust 2 passed. With the owner's designs copied in: 3342 passed, 1 skipped (copies removed). No stitch snapshot from before this phase changed; re-recorded since the audit: `branch/lines_and_fill` (one jump fewer).
- **Findings:** 1, 3, 4, 5 fixed. 2 partly: crossing and T lines not built (BACKLOG); two tries at the other joins broke their limits and were reverted.
- **Branching:** 9 of the 15 three-shape cases sew whole (L-049 says what still cuts or jumps). 120 random branches: 6.6 mm uncovered, 281 snips by hand (5.1 mm and 301 before the fixes).
- **Blackwork:** a join is sewn only by an edge or on a lattice line, else it jumps (planner's decision). Solid shapes never jump; shapes with holes can (up to 14 with four holes), and the fill says how many.
- **Artwork:** limits refuse by rule; PDFs and big wide lines are worked out by a one-use helper (`--ludd-artwork-worker`). Mac and Linux not tried by hand.
- **Frozen engine:** 77,110,585 bytes on `main` → about 84.1 MB (about 7 MB more); its start-up check reads an SVG, a DXF and a PDF and starts the helper.
- **Owner decisions:** 1 and 2 yes (`svgelements`, `ezdxf` with `pyparsing`, `pypdfium2`); 3 to 5 as recommended (D-022). P7-D2 succeeded. P7-B3 built (L-017 PARTIAL).
- **Tried by hand** (browser preview, scratch data folder): a hostile SVG refused, then SVG and PDF imports; a branch's order list and pasting; Repeat's Mirror outline; the end-dot refusal; the K preview; the Blackwork note.
- **Not tried by hand:** buttonhole, eyelet and preset windows, DXF in the app, a pen tablet, the desktop app.
- **For later phases:** `LineStyle.recs`, `RunParams.notes`, `FillPattern.join`/`notes`, `FillPatternDef.choices`, `fills/lattice.py` (Phase 8). One router for Blackwork joins and Phase 8's lace (BACKLOG).
- **Spec deviations:** PHASE-07 section 12, with the changes after the audit.
- **Known, older:** a lone plain fill starting at a corner isn't the same on every computer (BACKLOG).
- **For the owner:** a test build left `.cache\ezdxf\font_manager_cache.json` in the home folder; safe to delete.
- **Blocked On Human:** nothing for Phase 7. Older: P6-A1 and P4-A1 patent checks; tag v1.0.1; AI tracing download check; photo stitch (Phase 9).
- **Next Action:** the planning session's re-audit (notes and pull request text are in its shared notes folder); push only on the owner's yes.
