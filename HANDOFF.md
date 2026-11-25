# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-25
- **Current Phase:** Phase 4 audit **PASSED** at `8f5d568` (branch `claude/phase-04-merge-safe-df7a99`, which also carries `fd7f43c`, the Phase 3 stamp); this stamp lands on `main` with the Phase 4 pull request. `phase` is now 5. P4-A1 stays held (patent check).
- **Active Routing:** balanced (top model plans and audits, Sonnet builds)
- **Checks Run (audit):** `check.py --all` PASS with a frozen engine: engine 1221 passed, 2 skipped; UI 337; build; Rust 2 passed. Engine with `fixtures/` copied in: 1266 passed, 1 skipped (copy removed). `digitize.json` and `layout.json` snapshots unchanged against `main`; no test deleted; the one rewritten test (hooks start empty) checks a fresh copy of `passes.py`, same strength.
- **Audit verdicts on the planner's points:**
  1. Done-when 2 is accepted as a known limit. The 76 over-limit cells (20 mm on 40 mm, keep 1 mm) are exactly the outer 1 mm ring; none lies deeper. The lower fill reaches 1.16 to 1.20 mm (keep + pull compensation). F-1207 and L-002 say so honestly.
  2. Flower 150% Rebuild 8.84 is explained by the original: measured at the same footprint, the 100% file peaks at 10.9 with 37 cells over 7; the rebuild has 8. Thread 2.13x (2.25x is the most a full re-space can add). No doubling.
  3. P4-A1: the step is hidden (`visible: () => false`), the command only says "Not built yet", the engine refuses the op, and L-030 says NO.
  4. Nothing earlier weakened (see Checks).
  5. Committed tests and scripts use a temporary data folder (autouse `conftest.py`); `.claude/launch.json` is unchanged in this phase. The dev bridge issue predates this phase and is already in BACKLOG.
- **Findings (no blocker):** 1 done-when 2 wording vs the margin band (planner); 2 Rebuild adds jumps in shapes with holes (Wreath 35 vs 15; documented, backlog); 3 loose depth tolerance in a test; 4 L-002 travel line (documented, backlog).
- **Blocked On Human:**
  1. Answer the Phase 5 spec's Owner decisions.
  2. Older: P4-A1 patent check; tag v1.0.1; AI tracing download check; P6-A1 patent; photo stitch (Phase 9).
- **Next Action:** After the merge, Phase 5 (lettering) in a fresh session: answer its spec's Owner decisions first.
