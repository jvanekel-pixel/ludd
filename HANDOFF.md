# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-24
- **Current Phase:** Phase 2: 1.0.1 Hardening & Release
- **Active Routing:** balanced
- **What Changed:** The owner's 10 QA pass 2 decisions (docs/QA-REPORT-2.md) are in, on branch `claude/qa2-decisions-e5fc5b` (cut from `claude/qa-pass-2-b93602`, PR #20), committed in 6 groups, not pushed:
  1-4 (stitch output): fills with a neck under 0.6 mm route travel along edges (all pieces of the shrunk zone, then a 0.05 mm inset); a fill never ends on a jump; tie_off locks before a trailing trim/jump; zigzag underlay crosses back; applique moves >3 mm between edges get TRIM+JUMP; Split long stitches subdivides the outer-edge step at sharp corners.
  5: a placed stitch file with edits (kept.has_edits) sews and saves from its private copy (`kept.pinned`, `as_added`); no format change.
  6: samples' PES/JEF regenerated (1.0.0 .ludd kept as-is); golden test renders each .ludd vs its PES.
  7-8: vitest pairs Tauri plugin crates with npm packages (Cargo.toml/package.json and both lockfiles); ci.yml `rust-macos` job with placeholder sidecar; release.yml runs `cargo test --lib` after the freeze (tauri-build needs the sidecar, so not inside the Tests step).
  9: Ctrl+Z while drawing removes the last point, Ctrl+Y waits. 10: 1.0.1 changelog in US spelling.
  Docs: CHANGELOG, KB (F-103/502/1307/1501/1901/204, L-025, T-019/020, index, history), manual, in-app Help; 4 stitch-out rows (QA2 1-4).
- **Snapshots re-recorded (intended):** applique_with_hole_run_tack (S3 trims), satin_ribbon_auto_comp_widen and satin_ribbon_split (S2 crossing).
- **Checks Run:** engine `CI=1 uv run --locked pytest -q` pass (697 passed, 1 skipped); `pnpm typecheck` pass; `pnpm test` pass (43 files, 230); desktop build pass (known >500 kB chunk warning); `cargo test --lib` with a placeholder sidecar pass on Windows. Not run: macOS CI (needs a push), installer, the app.
- **Note:** `test_ai.py::test_qa2_t1_a_redirect…` failed twice early in the session (sandbox couldn't reach its local test servers), then passed in the final run. The report's "fill ends on a jump" repro no longer reproduces on current code; the fix is kept and the lock-stitch part is unit-tested.
- **Blocked On Human:** Owner OK to push the branch and open a PR into `claude/qa-pass-2-b93602` (or main if #20 merged).
- **Next Action:** Push + PR after the owner's OK; then tag v1.0.1 when the owner asks. The LUDD-User-Manual.pdf was not regenerated.
