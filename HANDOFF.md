# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-25
- **Current Phase:** Phase 4 built on local branch `claude/phase-04-merge-safe-df7a99`, not pushed or merged; `phase` stays 4 until the top-model audit passes. P4-A1 not built (decision 1 unanswered).
- **Active Routing:** balanced (top model plans and audits, Sonnet builds; Track C ran on Opus)
- **What Changed:** repairs (Repair dialog, Fix it, tiny stitches, clumps, density limit, rebuild), stitch inserts, needle path view, Don't sew what's hidden; integration fixes and deviations in spec section 12. `origin/main` still 407e009.
- **Checks Run:** `check.py --all` PASS, Rust 2 ran: engine 1221 passed, 2 skipped (before: 1065 + 1), UI 337 (before: 276). Engine with `fixtures/` copied in: 1266 passed, 1 skipped (copy removed). Frozen engine: smoke ok; same stitches as source (rebuild, overlap, preview).
- **Done-when:** 1 yes (150% and 60% spacing tests). 2 partly: the lower fill stops at the margin, but the 1 mm margin is over the density limit (76 of 400 cells in a 20 mm test square, all in the margin; 109 with the switch off). 3 n/a (A1). 4 yes. 5 yes.
- **Rebuild coverage:** samples at 150% and 60%: Flower 97%, Star badge 98%, Wreath 95%. `fixtures/` at 150%: 11 designs, 61 to 96% (median 81%), none under 50% (per-file report in the shared notes folder, not committed).
- **Flower 150% via repair.preview, before (plain stretch) → after:** stitches 2594→4854, trims 9→9, jumps 10→10, tiny 0→11, longest 5.42→4.99 mm, densest 6.72→8.84 (file at 100%: 7.39), hits 4→5; limit 7.0; "Rebuilt 97%".
- **Density limits shipped:** fill under 0.33/d → 0.40/d, satin under 0.30/d → 0.36/d (`fabrics.DENSITY_LIMITS`).
- **For Phase 13 (`recognize.py`):** a fill's outline is its row ends, first and last rows pushed out half a spacing (holes come as separate fills; bends can self-cross); fills under 4 rows read as runs; narrow one-stitch rows as satins; no motif, cross-stitch or programmed fills; no satins spaced over 0.6 mm.
- **Seen in the preview:** Show on the design marks in red (white edge), window docks right, view zooms to the design; with Rebuild nearly all red (caption "taken out or made again"); Cancel clears it. Accept, Fix it, Edit stitches, needle path view, Alt+Shift+O work. A short travel line shows across a lower fill (L-002).
- **Preview safety:** the dev bridge uses the real `%APPDATA%\Ludd` (recovery copy included): start previews with `THREADLINE_DATA_DIR` set to a throwaway folder.
- **Blocked On Human:**
  1. Say when to push and merge Phase 4 (after the audit; it carries `fd7f43c`, the Phase 3 stamp, if that isn't merged first).
  2. Done-when 2 and the travel line: accept as they are, or have the planner change the fill generator (BACKLOG "From Phase 4").
  3. Older: P4-A1 patent check; tag v1.0.1; AI tracing download check; P6-A1 patent; photo stitch (Phase 9).
- **Next Action:** Phase 4 audit on the top model (`phase-audit-gate`).
