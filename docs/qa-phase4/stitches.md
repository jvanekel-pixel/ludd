# QA phase 4: stitches (fill, patterns, satin, shape ops, applique)

Files changed: `engine/threadline_engine/digitize/stitches.py`, `patterns.py`, `paths.py`, `applique.py`,
`engine/threadline_engine/shapeops.py`, `engine/threadline_engine/quality.py`, tests `test_digitize.py`,
`test_patterns.py`, `test_shapeops.py`, `test_quality.py`, `tests/snapshots/digitize.json`.
Full engine suite (with `CI=1`): 537 passed, 1 skipped.

## Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | fill | Wave rows drift / gaps | Already fixed (C15); coverage now same as tatami (0.20 mm farthest point) | stitches.py `tatami` | test_patterns `test_qa_c15_*` |
| Medium | fill | Stipple sews only the largest patch | Fixed: one loop per patch (lone cells too), joined by travel; warning when a part is too narrow for the loop size | patterns.py `stipple_paths`, stitches.py `_open_paths` | test_patterns `test_qa_stipple_fills_every_part…`, `…too_narrow…` |
| Medium | fill | Fill/applique keep one part of a split or self-crossing shape | Fixed: every piece is sewn (lock, trim, move, lock between pieces); applique places/tacks/covers and cuts each piece | stitches.py `valid_parts`, `fill_parts`, `fill`; applique.py `_pieces` | test_digitize `test_self_intersecting…`, `test_qa_hole_cutting…`, `test_qa_self_crossing_applique…` |
| Medium | fill | Underlay only on the largest part; hole edges get no edge run | Fixed: edge run on every piece and every hole; cross-hatch under every piece | stitches.py `_edge_rings`, `_fill_part` | test_digitize `test_qa_underlay_reaches_every_lobe…` |
| Medium | fill | Fill very slow on wobbly outlines / many holes | Fixed: travel's buffers worked out once per fill (`Zone`): 250-point blob 8.7 s → 2 s, 600-point 17 s → 0.7 s | stitches.py `Zone`, `travel`, `tatami` | test_digitize `test_qa_wobbly_outline_fills_quickly` |
| Medium | fill | Satin-look lettering trips "long loose stitches (up to 7.0 mm)" | Fixed: 0.15 mm tolerance (float noise + 0.1 mm grid); also covers the lettering agent's handover | quality.py `LONG_TOLERANCE_MM` | test_quality `test_qa_a_stitch_right_at_the_7_mm_limit…` |
| Medium | patterns | Gradient keeps the cross-hatch, never fades | Fixed: gradient skips the cross-hatch (keeps the edge run) | stitches.py `_fill_part` | test_digitize `test_qa_gradient_skips_the_cross_hatch…` |
| Medium | patterns | Self-crossing outline loses loops | Fixed (same as fill item above) | | |
| Medium | patterns | Stipple leaves parts unfilled | Fixed (same as fill item above) | | |
| Medium | patterns | Contour on lobes/holes: long travel, stacked ridge | Fixed: each piece finished depth-first, hole rings sewn from inside out; H shape 32 long joins → 3, donut ridge 22 → 6.5 mm/mm² | patterns.py `contour_paths` | test_patterns `test_qa_contour_finishes_each_lobe…`, `…no_stacked_ridge` |
| Medium | patterns | Cross-stitch vertical bar on every cell edge | Fixed: each run is a zigzag out and back with one turn (190 bars → 10 turns on a 30 mm square) | patterns.py `cross_paths` | test_patterns `test_qa_cross_stitch_has_no_bars…` |
| Medium | patterns | Cross-stitch run order: long travel over finished crosses | Fixed: runs sewn nearest first from any corner (donut: 8 long moves → 1) | patterns.py `cross_paths` | test_patterns `test_qa_cross_stitch_round_a_hole…` |
| Medium | patterns | Wave rows sampled at different phases | Already fixed (C15) | | |
| Medium | patterns | Applique border spacing quantised (0.4 sews 0.33) | Fixed: border stitches placed at the asked spacing along the edge | applique.py `_border` | test_digitize `test_qa_applique_border_spacing…` |
| Medium | satin | Batch convert into the same folder converts nothing | Handed over: design.py owner | | |
| Medium | satin | Fewer jumps decided before Sort colors | Already fixed (C6) | layout.py | |
| Medium | satin | JEF turns >12.7 mm stitches into trim+jump | Handed over: design.py / prepare.py owner (also in engine-io notes) | | |
| Medium | satin | Split long stitches ignores edge/zigzag underlay | Fixed: underlay legs and the step to the top stitching are split too | stitches.py `satin_from_pairs` | test_digitize `test_qa_split_satin_pieces…` |
| Medium | satin | Knife on a closed ribbon/line gives 3 pieces | Fixed: the two pieces either side of the start point are joined | shapeops.py `split` | test_shapeops `test_qa_one_cut_across_a_closed_line…` |
| Medium | shapeops | Outline follows hidden travel (Fewer jumps on) | Fixed: outline renders without hidden travel | shapeops.py `offset` | test_shapeops `test_qa_outline_ignores_hidden_travel…` |
| Medium | shapeops | Knife pieces lose colour override, ops, pin, group; success after failed commit | Handed over: features.ts owner | | |
| Medium | shapeops | Knife on closed line: 3 pieces | Fixed (see satin) | | |
| Medium | shapeops | Design browser search hint false | Handed over: FeatureDialogs.tsx owner | | |
| Medium | tests | Snapshot tests missing for stitch types | Fixed: 16 new cases (triple, 3 motifs incl. closed, edge+zigzag underlay, auto underlay + comp_by_width + auto_widen, split, random+reverse, heavy underlay, cross/stipple with underlay, bow-tie, 2 applique). Lettering/knockdown/basting: handed over (layout/lettering) | test_digitize `SNAPSHOT_CASES` | itself |
| Medium | tests | Missing snapshot entry recorded silently | Already fixed by another agent (fails under `CI`) | test_digitize | |
| Medium | tests | Self-crossing test only checks "some stitches" | Fixed: asserts both lobes and the lock/trim between | test_digitize | `test_self_intersecting_outline_is_repaired` |
| Medium | visual | Split long stitches can't clear the check on wide satins | Fixed (see satin) | | |
| Medium | visual | Stipple largest group only | Fixed (see fill) | | |
| Medium | visual | Stipple/cross travel visible on top (edge-run chord) | Fixed: open patterns are planned first; the edge run ends beside the pattern start (22.8 mm → under 4 mm) | stitches.py `_fill_part` | test_patterns `test_qa_open_pattern_underlay_ends_beside…` |
| Medium | visual | Cross-stitch vertical bars | Fixed (see patterns) | | |
| Medium | visual | Satin-look lettering false long warning | Fixed (see fill) | | |
| Medium | visual | Self-crossing outline dropped | Fixed (see fill) | | |
| Medium | visual | (Disputed) Spacing under 0.3 drops needle points | Fixed: shortest kept step is min(0.3, 0.75 × spacing) for fill rows and satin tops; output at spacing ≥ 0.4 unchanged | stitches.py `_min_step` | test_digitize `test_qa_dense_rows_reach_both_edges`, `test_qa_dense_satin_gets_denser…` |
| Medium | visual | Cross-hatch leaks outside at zero-width spikes | Fixed: an invalid rotated shape is repaired | stitches.py `tatami` | test_digitize `test_qa_cross_hatch_stays_inside…` |
| Low | fill | UI ranges allow loose stitches (fill Length 8, cross, applique border) | Engine side fixed: cross diagonals over 7 mm split, applique border split at 7 mm. Fill Length max 7: handed over (InfoPanel) | stitches.py `_open_paths`, applique.py `_border` | test_patterns `test_qa_big_cross_stitch_squares_are_split`, test_digitize `test_qa_wide_applique_border_is_split` |
| Low | fill | Fill Auto underlay ignores heavy fabrics | Fixed: heavy fabrics get the cross-hatch 1.5 mm apart (was 2). Width still not used for fills (manual) | stitches.py `FillParams` | test_digitize `test_qa_heavy_fabric…` |
| Low | fill | No upper size limit | Fixed: shapes over 1000 mm, or fills needing over 400,000 stitches, refused with a plain message; also covers engine-io's handover (runs, satins too) | stitches.py `check_points`, `fill`, `generate` | test_digitize `test_qa_no_object_can_ask_for_millions…`, `test_qa_bad_or_absurd…` |
| Low | fill | travel/contour cut corners outside the shape | Fixed: routes, edge runs, contour rings and applique edges keep sharp corners (comb: 0.47 → under 0.25 mm outside) | paths.py `sharp_points`, stitches.py `travel` | test_digitize `test_qa_travel_keeps_to_the_shape…`, test_patterns contour corners |
| Low | fill | Fill/applique settings not validated (NaN, null, pull comp) | Fixed: non-numbers refused, null means default, pull comp 0-2, tack width 0.5-4 | stitches.py `_finite`, applique.py | test_digitize `test_qa_bad_or_absurd…` |
| Low | fill | Spacing under 0.3 drops row starts | Fixed (see Disputed item) | | |
| Low | patterns | Zero-length stitches at joins | Fixed | stitches.py `_append` | test_digitize `test_qa_no_second_needle_drop…` |
| Low | patterns | Edge underlay one polygon only | Fixed (see fill) | | |
| Low | patterns | Applique ignores Lock stitches boxes | Handed over: InfoPanel owner (hide the two boxes for applique; locks at stops are needed for the PE550D) | | |
| Low | patterns | Contour rings cut corners 1.2 mm | Fixed | patterns.py | test_patterns `test_qa_contour_finishes_each_lobe_and_keeps_corners` |
| Low | patterns | Cross Square > 4.95 mm over 7 mm; advice doesn't fit | Fixed: diagonals split; check advice mentions Split long stitches and smaller squares | patterns/stitches, quality.py | test_patterns `test_qa_big_cross…` |
| Low | patterns | Panel shows settings that do nothing for open patterns | Handed over: InfoPanel owner | | |
| Low | patterns | Fabric preset clamps fill spacing to 3.0 / turns 0 into 0.2 | Handed over: fabrics.py owner (clamp per kind: fill 5, satin 3; don't turn ≤0 into 0.2) | | |
| Low | patterns | Motif side flips with drawing direction | Skipped: a new side option is a feature for the owner to decide | | |
| Low | patterns | Contour slow on jagged outlines | Fixed: simplified once, each ring shrinks the previous one (5 s → 0.3 s) | patterns.py | test_patterns `test_qa_contour_on_a_jagged_outline_is_quick` |
| Low | patterns | Applique satin border never split | Fixed (split at 7 mm) | applique.py | test_digitize `test_qa_wide_applique_border_is_split` |
| Low | patterns | Stipple reshuffles when moved | Fixed: seed from size and area, not position | stitches.py `_stipple_seed` | test_patterns `test_qa_stipple_keeps_its_pattern_when_moved` |
| Low | satin | Ribbon tighter than its width folds, no warning | Fixed: warning (mitred corners excluded) | stitches.py `satin_ribbon`, applique `_border` | test_digitize `test_qa_satin_tighter_than_its_width_warns` |
| Low | satin | Reversed/twisted rails: only "too wide" | Fixed: "the two sides cross each other" warning | stitches.py `satin` | test_digitize `test_qa_reversed_satin_rails…` |
| Low | satin | Too-short run: lone unlocked needle drop, no message | Fixed: warning (not an error: an error would stop the whole design rendering) | stitches.py `generate` | test_digitize `test_qa_a_line_shorter_than_a_stitch…` |
| Low | satin | Closed motif line doesn't close at a corner start | Fixed | patterns.py `motif_points` | test_patterns `test_qa_closed_motif_line_meets_itself` |
| Low | satin | Test gaps; split test tolerance 1.2× | Fixed: split test exact, new snapshots and property tests | tests | |
| Low | satin | Split pieces up to 33% over Longest | Fixed: enough pieces that staggered ones stay within Longest | stitches.py `_split_across` | test_digitize `test_qa_split_satin_pieces…` |
| Low | satin | Satin warning at 10 mm, manual and check say 7 | Fixed: warns over 7 mm unless Split long stitches (≤ 7) is on | stitches.py | test_digitize `test_qa_satin_warns_from_7_mm…` |
| Low | satin | Pen curves hook at uneven node spacing | Skipped: changes every curve in every design and must change in paths.ts at the same time; owner's decision | | |
| Low | satin | Ribbon widths 0.5-0.99 sew at 1.0 | Handed over: InfoPanel owner (Width stepper min 1, or "sews as 1 mm" hint) | | |
| Low | shapeops | Small holes skipped by "around holes" | Fixed: hole rings come from the stitches before the closing-up | shapeops.py `offset` | test_shapeops `test_qa_outline_rings_small_holes_too` |
| Low | shapeops | Ring inside the distance at tight turns | Skipped: needs a node-placement rework of to_nodes; error ≤ 0.6 mm, low value | | |
| Low | shapeops | Misleading/raw messages | Engine fixed: knife along a line, one-point line get plain messages. Sign-aware empty-offset text, inch limit text, knife re-arm, success after failed commit: handed over (features.ts) | shapeops.py `split` | test_shapeops `test_qa_knife_mistakes…` |
| Low | shapeops | Merge "first" = layout order; corner-only touch accepted | Corner-only touch now refused. Which settings win: handed over (features.ts) | shapeops.py `merge` | test_shapeops `test_qa_merge_refuses…` |
| Low | shapeops | Knife/merge drop holes < 2 mm²; vacuous test | Fixed: holes kept down to 0.5 mm²; `or True` removed; dead import gone | shapeops.py `_poly_nodes` | test_shapeops `test_qa_knife_keeps_small_holes…`, `test_offset_rings…` |
| Low | shapeops | Text longer than its line | Already fixed (phase 2) | lettering.py | |
| Low | shapeops | Knife doesn't snap | Handed over: StitchCanvas.tsx owner | | |
| Low | shapeops | One file per name overwrites | Handed over: features.ts owner | | |
| Low | tests | Tests that pass when broken (ribbon miter, motif shape) | Fixed for ribbon miter (hairpin) and motif height; optimize_order D07: layout owner | test_digitize, test_patterns | `test_qa_ribbon_miter…`, `test_motif_lines…` |
| Low | tests | Assertions that cannot fail (`or True`, stipple `or`) | Fixed in my files; test_layout/test_ai/test_library ones: their owners | test_shapeops, test_patterns | |
| Low | visual | Cross-hatch leak at zero-width spikes | Fixed (see Medium) | | |
| Low | visual | Underlay skipped behind a narrow neck | Fixed (see fill) | | |
| Low | visual | Zero-length stitch at joins | Fixed | | |
| Low | visual | Satin fold on tight curve | Fixed (warning) | | |
| Low | visual | Satin width thresholds disagree | Fixed (7 mm) | | |
| Handover | lettering | Long-stitch check flags exactly 7.0 mm | Fixed (tolerance 0.15 mm) | quality.py | test_quality `test_qa_a_stitch_right_at_the_7_mm_limit…` |
| Handover | engine-io | No bound on shape size / stitch count | Fixed (1000 mm, 400,000 stitches per object) | stitches.py | test_digitize `test_qa_no_object_can_ask_for_millions…` |

Counts: 53 rows Fixed (many are the same fix seen from several areas), 6 Already fixed, 4 Skipped, 16 Handed over (some partly fixed on the engine side).

## Changelog lines
- Fills and appliques whose outline crosses itself, or that a hole cuts in two, now sew every piece instead of quietly leaving part bare.
- Stipple now fills every part of a shape and says when a part is too thin for the loop size. Moving a stippled shape no longer reshuffles its pattern.
- Cross-stitch looks like little Xs: no more bars between the crosses, and far fewer threads crossing finished crosses.
- Contour fill finishes one part at a time and keeps its corners, and is much faster on jagged outlines.
- Gradient fills now fade out properly (no cross-hatch showing at the light end).
- The edge underlay now runs round every part of a shape and round holes; heavy fabrics (knit, fleece, towel, stretch) get a firmer fill base.
- Fills with wobbly outlines or many holes generate several times faster.
- Dense spacings (under 0.3 mm) now really sew denser; fill rows reach the edge.
- "Split long stitches" now also splits the underlay, and no piece is longer than the Longest setting. Satins over 7 mm warn unless split.
- Applique borders sew at the spacing you set, and wide borders are split automatically.
- New warnings: a satin curving tighter than it is wide, satin sides that cross, a line too short to sew.
- No more double needle drops where rows and travel meet.
- Satin-look lettering no longer gets a false "long loose stitches" warning.
- Knife: one cut across a closed line or ribbon gives two pieces; cutting along a line gives a plain message; small holes are kept. Merge refuses shapes that only meet at a corner.
- Outline: no spur back to the previous shape with Fewer jumps & trims on; small holes get their inside ring.
- A shape far bigger than any hoop (a typing slip) is refused with a message instead of freezing the engine.

## Manual changes needed
- Fill underlay Auto: light fabrics get an edge run only; others an edge run plus cross-hatch, closer (1.5 mm) on knit, fleece, towel and stretch. It does not depend on the width (the manual says "the fabric and the width").
- Gradient: no cross-hatch underlay (like contour, stipple and cross-stitch), so it fades out.
- Satin: the satin's own warning starts at 7 mm (was 10), and goes away when Split long stitches is on.
- Applique: borders over 7 mm stitch length are split automatically.
- Cross-stitch: squares over about 5 mm get a needle point in the middle of each diagonal.
- Merge: shapes that only touch at a corner can't be merged.

## Stitch output changed
Test design for each: the snapshot case named, plus the shapes in the tests named above.
- All fills with an edge-run underlay: the edge run keeps sharp corners; extra edge runs round holes and every piece; cross-hatch under every piece (snapshot `fill_square_45`, `fill_donut` re-recorded).
- All fills: no repeated needle drop where travel meets a row (`fill_square_45`).
- Travel inside fills keeps the route's corners (shapes with holes or notches).
- Self-crossing / split fills and appliques: every piece sewn, with lock, trim and jump between pieces (`fill_bowtie`, new).
- Fill spacing under 0.4 mm (e.g. Dense on Towel) and satin spacing under 0.4 mm: steps between rows/rungs no longer dropped (more penetrations).
- Gradient with cross-hatch underlay: cross-hatch gone.
- Heavy fabrics, fill Auto underlay: cross-hatch 1.5 mm apart (`fill_heavy_auto_underlay`, new).
- Contour: new ring order and corners (`fill_contour` re-recorded). Stipple: new seed and all patches (`fill_stipple` re-recorded). Cross-stitch: new zigzag paths and order (`fill_cross` re-recorded).
- Open patterns with edge underlay: edge run ends beside the pattern start (`fill_cross_with_underlay`, `fill_stipple_with_underlay`, new).
- Satin with Split long stitches: more pieces where they used to run over the limit; underlay split (`satin_ribbon_split`, new).
- Applique: border and tack-down stitches at the set spacing, corners hit exactly, border split over 7 mm (`applique_square`, `applique_with_hole_run_tack`, new). Worth a stitch-out: a 30 mm square applique, 3 mm border.
- Closed motif lines: start and end meet (`run_motif_blanket_closed`, new).
- Knockdown (layout.py uses tatami/travel) changes slightly where its travel routes bend.
- Unchanged (snapshots identical): run single/bean/scallop, all satins at default settings, gradient and wave with no underlay.

Suggested stitch-out entries: (1) bow-tie fill; (2) 50 mm donut in cross-stitch and in contour; (3) 30 mm square applique, 3 mm border; (4) 9 mm satin with Split long stitches at 4 mm; (5) 20 mm square fill at 0.25 mm spacing.

## Handed over
- design.py owner: batch convert into the same folder (raise a plain DesignError when dest is src or contains it); JEF long-stitch contingency (`long_stitch_contingency: CONTINGENCY_LONG_STITCH_SEW_TO` with max_stitch).
- fabrics.py owner: clamp spacing per kind (fill up to 5, satin up to 3) and don't turn 0 or negative into 0.2.
- features.ts owner: knife pieces should copy threads/locked/group/ops from the original; report success only when commit worked; empty negative offset message by sign; limit text in the current unit; keep the knife armed after a harmless mistake; merge should keep the first-selected item's settings; one-file-per-name.
- InfoPanel.tsx owner: fill Length max 7; hide Lock stitches boxes for applique; hide Density/Random/Edge pad/Cross-hatch for contour/stipple/cross (keep spacing for contour); ribbon Width stepper min 1 (or "sews as 1 mm").
- StitchCanvas.tsx owner: knife clicks through `snapped()`.
- FeatureDialogs.tsx owner: design browser search should re-scan with `query`.
- test_m8.py owner: tighten the applique cover-width tolerance to 0.03.
- layout/lettering owners: snapshot cases for lettering, knockdown and basting; test for optimize_order's overlap guard.

## For the lead to decide
- Wide satins (over 7 mm) are not split automatically (they now warn from 7 mm). Defaulting Split long stitches on when a satin is wider than 7 mm would change existing designs' output.
- Pen-tool curve overshoot (Catmull-Rom) left alone: fixing changes every curve.
- Very large fills (over 400,000 stitches, e.g. a 1 m square at default density) are now refused.
