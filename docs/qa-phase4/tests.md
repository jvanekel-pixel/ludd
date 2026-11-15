# QA phase 4: tests

Files changed (tests only): `engine/tests/test_qa4_coverage.py` (new, 21 tests),
`engine/tests/test_layout_snapshots.py` (new, 9 tests), `engine/tests/snapshots/layout.json` (new, 8 entries),
`engine/tests/test_layout.py` (`test_preview_export_with_cut_stops` made strict),
`apps/desktop/src/features.colorways.test.ts` (new, 4 tests). No product code changed; no existing
snapshot re-recorded.

Results: engine full suite with `CI=1`: 581 passed, 1 skipped (the opt-in real AI model test).
vitest: 29 files, 154 tests passed. `pnpm typecheck` fails in `src/leftovers.qa.test.ts:100` (the
leftovers agent's new file, work in progress: `AppliqueParams` type narrowing), not in mine.

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | tests | Repeated moves of one stitch untested; moves don't follow a turned/scaled/flipped design | Already fixed (phase 2, `local` moves; engine-io/layout) + test added for two ops on one stitch, with turn, mirror and turn+scale | - | test_qa4_coverage `test_two_moves_of_one_stitch_add_up_and_follow_the_design` (4 cases) |
| Medium | tests | Missing snapshot tests (applique, lettering, knockdown, basting, variants) | Applique + variants: Already fixed (stitches, 16 cases; applique tolerance 0.03: layout). Lettering, knockdown, basting: Fixed | new `snapshots/layout.json` | test_layout_snapshots (5 lettering cases incl. arc, monogram, drawn line; 2 knockdown; 1 basting; plus a check that each case really contains what it names) |
| Medium | tests | Stops, seam locks, no-overwrite of split export untested | Already fixed (layout) | | test_m8, test_layout |
| Medium | tests | RPC method wiring untested | Already fixed (engine-io) | | test_rpc |
| Medium | tests | New UI has almost no tests; no DOM | Partly fixed (ui: ui.qa.test.ts, key handler in keys.ts). Added colorways, guides, undo/redo tests. jsdom: Skipped (no installs this phase) | | features.colorways.test.ts |
| Medium | tests | Golden PES/JEF tests skip in CI | Already fixed (platform) | | test_golden |
| Medium | tests | Alt shortcuts on macOS | Already fixed (ui) | | ui.qa.test.ts |
| Medium | tests | "One file per name" overwrites duplicates | Already fixed (keep_existing; lettering/ui) | | features.layout.test.ts "saves the others when one name fails" |
| Medium | tests | CI never smoke-tests the frozen sidecar | Already fixed (platform) | | test_packaging |
| Medium | tests | Snapshot test records a missing entry and passes | Already fixed (platform); the new layout snapshot test does the same (fails under `CI`) | | |
| Medium | tests | Cuts that cut-stops depend on untested | Already fixed (layout) + the key-membership assertion replaced (see Low below) | | test_layout `test_qa4_cut_stops_*` |
| Medium | tests | JEF/PES export settings barely tested | Already fixed (layout) | | test_layout |
| Medium | tests | Self-crossing fill test only checks "some stitches" | Already fixed (stitches) | | test_digitize |
| Medium | tests | Text on a line piles letters at the ends, no warning | Already fixed (phase 2; lettering) | | test_lettering `test_text_longer_than_its_line_warns` |
| Medium | tests | Curve flattening, kerning, cap-height fallback untested | Kerning (GPOS) and cap height from H: Already fixed (lettering). Fixed the rest: TrueType quadratic O and CFF cubic O must come out round (points on the circle, area within 1%), the old `kern` table, and the cap-height fallback (font field, then 0.7 em) | | test_qa4_coverage `test_truetype_quadratic…`, `test_cff_cubic…`, `test_the_old_kern_table…`, `test_cap_height_falls_back…` |
| Medium | tests | travel_under: one scenario | Already fixed (layout) | | test_connectors `test_qa4_*` |
| Low | tests | Nothing detects a field dropped from the text-cache key | Fixed (size/shape test by layout; now complete): a spy checks lettering reads only fields that are in the key, and each input changed after caching must equal a fresh render (text, font file, size, spacing, style, shape type/radius, drawn line, monogram). Checked by mutation: dropping shape, size or monogram from the key fails it | | test_qa4_coverage `test_lettering_reads_only_what_the_text_cache_key_holds`, `test_text_cache_never_returns_stale_letters` (11 cases) |
| Low | tests | Tests that pass when broken (ribbon miter, motif shape, shortest-order overlap guard) | Ribbon miter, motif: Already fixed (stitches). Overlap guard: Fixed: a layout where nearest-first alone would sew a top shape before the one under it; the test also turns the guard off and checks the order then changes, so it fails if the guard breaks | | test_qa4_coverage `test_shortest_order_never_puts_an_overlapping_shape_ahead`, `…keeps_every_overlapping_pair_in_order` |
| Low | tests | Assertions that cannot fail (`or True`, key-membership, stipple `or`, registered-name lists) | `or True`, stipple: Already fixed (stitches). Key-membership: Fixed (`test_preview_export_with_cut_stops` now asserts 0 stops after a colour change, exactly 1 for a long same-colour move, 0 with cut stops off). test_library all() over empty list: Already fixed (non-empty checked first). Registered-name list (test_ai): superseded by engine-io's every-method dispatcher test; left as is | test_layout.py | test_layout `test_preview_export_with_cut_stops` |
| Low | tests | TypeError reported as invalid params, not logged | Already fixed (engine-io) | | test_rpc |
| Low | tests | No registry invariant test; duplicate ids | Already fixed (ui) | | ui.qa.test.ts |
| Low | tests | Test collection reads the real user data folder; AI-model test machine-dependent | Already fixed (autotrace) | | test_autotrace |
| Low | tests | Wall-clock assertions can flake | Already fixed (autotrace) | | test_autotrace |

## Changelog lines
- (Behind the scenes) More tests: lettering, knockdown and basting stitch-outs are now pinned by snapshots;
  curved letters, old-style kerning, the text cache, the shortest-order guard for overlapping shapes,
  repeated stitch moves, colour sets and guides are tested.

## Manual changes needed
- None.

## Stitch output changed
- None (tests only). New snapshot entries in `engine/tests/snapshots/layout.json` record today's output for:
  lettering satin/fill/arc/monogram/drawn line, knockdown under a square and under text, basting box.
  Recorded on Windows; if they differ on macOS/Linux CI, that is cross-platform drift to look at.

## Handed over
- None. No product bug found by the new tests.
- Note for the lead: `pnpm typecheck` currently fails in `apps/desktop/src/leftovers.qa.test.ts:100`
  (leftovers agent, in progress).
