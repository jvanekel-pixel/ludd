# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-24
- **Current Phase:** Phase 3 ships to `main` as pull request 25 (branch `claude/goofy-goldwasser-7af929`, squash merge). `phase` stays 3 until the top-model audit passes.
- **Active Routing:** balanced (top model plans and audits, Sonnet builds; BUILDPLAN.md section 3)
- **What Changed:** engine and UI seams (`layout/`, `methods/`; fill, line, command, dialog and canvas-hook registries), `scripts/check.py`, Spiral fill, five new shapes, docs. Track branches `phase-03/track-a` to `-e` are kept.
  - Then, owner approved twice: Spiral joins its pieces along the edge, sewing the nearest piece next, so nothing runs across the rings and little thread gathers on the edge (`fills/spiral.py` only; only Spiral snapshots re-recorded).
- **Checks Run:** `check.py --all` PASS: engine 1065 passed, 1 skipped (before the phase: 657 + 1); UI 276 (before: 241); typecheck, command table, build, Rust (2). No test removed; `digitize.json` and `layout.json` unchanged. With the sample designs copied in: PASS too (engine 1109 passed, 1 skipped).
  - CI's first run failed on the Apple-chip Mac only (donut spiral in another corner); the spot is now chosen in `fills/spiral.py`, proven against rounding-sized noise on 150 shape and spacing cases.
  - `pnpm build:engine` run, smoke ok; the frozen engine renders like the source. Preview: shapes, Spiral (Heart: nothing across, light edge), polygon Enter/Esc ok. The canvas hooks have no real user yet.
  - Spiral stress test (39 shapes, 36 settings each): nothing more than 0.3 mm outside, no stitch over its length, nothing across the rings; every stretch over 1 mm sewn.
- **Spec deviations** (details: spec section 12, Build notes):
  - The canvas dots read the pattern descriptors (new `directionDots`, only on cross-stitch).
  - Wave 1 tests now let wave 2 add items (old ones still required, in order); the menu test imports `./cmd`.
  - Spiral: where spots tie, the middle is the centroid; needle points at exact length; corner test measures to the thread.
  - `layout.render`/`export` stay functions; `text.py` imports `objects.py`; a local item op's transform also sets `center_mm`.
  - Overlays wrap `drawOverlay`; `CanvasTool.cursor` is not applied; `registerDialog` replaces a repeated id.
  - Rounded rectangle has 20 points; the width test checks the star's tips; the polygon dialog handles Enter and Esc itself.
  - `check.py -k` runs vitest through node, and an engine run matching no test counts as skipped.
  - Spiral steps 4 and 6: nearest piece next, not spiral order, joined along the edge by Spiral itself (owner approved).
- **Blocked On Human:**
  1. Start the Phase 3 audit in a new session on the top model.
  2. Older: tag v1.0.1 on commit `281272e` (PR #23); AI tracing Download check; patent checks (P4-A1, P6-A1); photo stitch (Phase 9). Phase 2's audit is not stamped.
- **Next Action:** the Phase 3 audit on the top model (`phase-audit-gate`), before Phase 4.
