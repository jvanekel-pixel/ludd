# Phase 4: layout group (layout-order, layout-ops, compat, export)

Engine: `engine/threadline_engine/layout.py`, `split.py`, `design.py`, `prepare.py`, `profiles.py`; small edits in
`quality.py`, `fabrics.py`, `project.py` (features list). UI: `design/layout.ts`, `design/types.ts`, `features.ts`
(stitch edit, names), `components/ExportDialog.tsx`, `BatchDialog.tsx`, two small edits in `actions.ts`.

Tests: engine full suite with CI=1: 537 passed, 1 skipped. UI: typecheck clean, vitest 27 files / 144 tests passed.
New tests: `test_qa4_*` in test_layout.py, test_connectors.py, test_m8.py, test_design.py, test_prepare.py;
`src/features.layout.test.ts`; new cases in `src/design/layout.test.ts`.

## Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | layout-order | Overlap slider doesn't set the overlap | Fixed: hoop count chosen so neighbouring windows overlap by at least the setting | split.py `_grid` | test_m8 `test_qa4_overlap_setting_is_the_real_overlap…` |
| Medium | layout-order | Dense / needle-hit checks fire on every bought design | Fixed (no threshold change): thick spots only inside placed stitch files are an info note; anything drawn in LUDD taking part keeps the warning | quality.py `check`, `_drawn_cells` | test_layout `test_qa4_thick_spots_in_a_bought_design…` |
| Medium | layout-order | Satin lettering trips "long loose stitches" at exactly 7 mm | Already fixed (lettering 6.8 mm; quality.py tolerance added by another agent) | quality.py `LONG_TOLERANCE_MM` | (theirs) |
| Medium | layout-order | Gap check off above 80 shapes | Fixed: spatial index (STRtree), cap removed, shapes cached by stitches | quality.py `_gaps`, `_gap_shape` | test_layout `test_qa4_gap_check_still_runs_with_many_shapes` |
| Medium | layout-order | One file per name ignores machine profile | Already fixed (C12) | features.ts `exportNames` | test_layout `test_qa_c12_*` |
| Medium | layout-order | shortestOrder commits a stale layout | Already fixed (ui agent: applies order to newest layout) | features.ts | ui.qa.test.ts |
| Medium | layout-order | Slightly-over design defaults to a split, no shrink offer | Fixed: up to 5% over, "Make it N% smaller" is offered first; split only if ticked | ExportDialog.tsx, layout.ts `shrinkToFit`, `scaleDesign` | layout.test.ts `shrinkToFit`, `scaleDesign` |
| Medium | layout-order | Alignment crosses on stitched area | Fixed: crosses placed anywhere in both windows' overlap, on bare fabric when there's room, far apart | split.py `_Occupancy`, `_mark_spots`, `_marks` | test_m8 `test_qa4_alignment_crosses_sit_on_bare_fabric…` |
| Medium | layout-order | Sort colors buries top layers | Fixed: a colour is only moved forward if nothing it would jump ahead of overlaps it; an info note says when some colours stay apart | layout.py `_sort_by_thread`, `_footprint`, `_blocks_overlap` | test_layout `test_qa4_sort_colors_never_puts_a_shape_under…` |
| Medium | layout-order | Shortest order misses savings under Fewer jumps | Fixed: shape ends from its own stitches; hidden travel now belongs to no item (-1) | layout.py `optimize_order`, `_join_objects` | test_connectors `test_qa4_shortest_order_is_the_same_with_fewer_jumps_on`, `test_qa4_hidden_travel_belongs_to_no_shape` |
| Medium | layout-order | Shortest order all-or-nothing, same kind only | Fixed: kind dropped from the run key; overlapping shapes (real stitch overlap) only pin their own order | layout.py `optimize_order` | test_connectors `test_qa4_shortest_order_mixes_fills_and_lines…` |
| Medium | layout-order | Fewer jumps 40-100x slower | Already fixed (C3). Also: object cache 512 -> 4096 (1000 shapes: render 4.7 s -> 0.2 s) | layout.py `_OBJECT_CACHE_MAX` | test_connectors `test_qa_c3_*` |
| Medium | layout-order | Basting box counts toward hoop fit | Fixed: basting remembers the hoop it was turned on for (`fit_mm`) and comes in (down to 2 mm) to fit; a warning if even 2 mm doesn't fit. Margin control: not added (advanced) | layout.py `render`, actions.ts `toggleBasting`, types.ts | test_layout `test_qa4_basting_box_comes_in_to_fit_the_hoop` |
| Medium | layout-order | Knockdown thread can't be set (Suspected) | Handed over: InfoPanel owner (confirmed by reading: no picker writes `knockdown.thread`) | - | - |
| Medium | layout-ops | Cover treats gaps under 1.6 mm as solid | Fixed: own closing radius 0.35 mm (rows up to 0.7 mm apart count as covered) | layout.py `_cover`, `COVER_CLOSE_MM` | test_connectors `test_qa4_travel_is_hidden_only_under_close_rows` |
| Medium | layout-ops | Stitch-edit moves in page space | Already fixed (phase 2, `local` moves) | layout.py, features.ts | test_layout `test_a_moved_stitch_turns…` |
| Medium | layout-ops | Delete with nothing selected deletes the design | Fixed: stitch Delete/Backspace enabled whenever stitch editing is on | actions.ts COMMANDS | features.layout.test.ts |
| Medium | layout-ops | Inserted stop/trim lost when its stitch is deleted | Fixed: placed at the last kept stitch | layout.py `_apply_ops` | test_layout `test_qa4_an_inserted_stop_stays…` |
| Medium | layout-ops | Shortest order defeated by hidden travel | Fixed (as above) | layout.py | test_connectors |
| Medium | layout-ops | Shortest order: mixed kinds, bbox veto | Fixed (as above) | layout.py | test_connectors |
| Medium | compat | Fewer jumps per-render cost, quadratic | Already fixed (C3) | layout.py | test_connectors `test_qa_c3_*` |
| Medium | compat | Fewer jumps + Sort colors: travel on top | Already fixed (C6); test updated for the safer sort | layout.py | test_connectors `test_qa_c6_*` |
| Medium | compat | Text longer than its line: no warning | Already fixed (phase 2, lettering) | lettering.py | (theirs) |
| Medium | compat | Text on line ignores rotation/scale/flip | Already fixed by another agent (`textOnLineItem`) | features.ts | features.lettering.test.ts |
| Medium | compat | Stitch-edit moves world-space | Already fixed (phase 2) | | |
| Medium | compat | Stop/trim lost when its stitch is deleted | Fixed (as layout-ops) | layout.py | test_layout |
| Medium | compat | Stipple sews only the largest region | Handed over: patterns/fill owner (digitize/patterns.py `stipple_path`) | - | - |
| Medium | compat | onnxruntime on Intel Mac | Already fixed (C21) | pyproject.toml | - |
| Medium | export | Emptied colour keeps a colour change | Already fixed (C4) | layout.py | test_layout `test_qa_c4_*` |
| Medium | export | Text on line piles letters, no warning | Already fixed (phase 2) | lettering.py | - |
| Medium | export | JEF header assumes design centred | Fixed: JEF written with the design centred on the origin (a copy) | design.py `_for_format` | test_design `test_qa4_jef_is_centred_on_the_hoop`, roundtrip test updated |
| Medium | export | JEF turns stitches over 12.7 mm into jump + half stitch | Fixed: `long_stitch_contingency = SEW_TO` for every format | design.py `write` | test_design `test_qa4_long_stitches_are_sewn_in_pieces…`, test_layout `test_qa4_jef_export_for_janome…` |
| Medium | export | PES fails above 255 colour steps, no warning | Fixed: format check in the preview (error, with the cut-stop hint) and a plain refusal before writing | prepare.py `check`, design.py `write` | test_prepare `test_qa4_pes_colour_step_limit…`, test_design `test_qa4_pes_over_255…` |
| Medium | export | Export not atomic | Fixed: temp file in the same folder, `os.replace`; applique SVG too | design.py `write`, layout.py `export_applique_svg` | test_design `test_qa4_a_failed_save_leaves_the_old_file_alone` |
| Medium | export | Non-ASCII thread name corrupts PES thread table | Fixed: names written as plain letters in PES ("Grün" -> "Grun"); the design keeps its names | design.py `_for_format` | test_design `test_qa4_accented_thread_names…` |
| Medium | export | One file per name: machine, overwrite, device names | Already fixed (C12 + another agent's `nameFileStem`); plus: a name that fails no longer stops the rest, and the message lists what wasn't saved | features.ts `exportNames` | features.layout.test.ts |
| Medium | export | Stitch-edit moves world-space | Already fixed (phase 2) | | |
| Low | layout-order | Fabric preset doesn't reach lettering | Fixed | layout.py `_text_block` | test_layout `test_qa4_fabric_reaches_lettering…` |
| Low | layout-order | Empty hoopings exported | Fixed: dropped; marks link each hooping to an earlier one it overlaps | split.py `plan`, `_marks` | test_m8 `test_qa4_hoopings_with_nothing_to_sew_are_left_out` |
| Low | layout-order | Lock stitches on every cut piece (+9% stitches) | Fixed: locks only where the thread is cut next to the seam (trim, stop, colour change) | split.py `section_pattern`, `CUT_START/CUT_END` | test_m8 `test_qa4_seam_lock_stitches_only…`, `test_qa4_cut_pieces_that_end_in_a_trim_are_locked` |
| Low | layout-order | profiles._validate doesn't check types | Fixed (types, numbers > 0, non-empty formats; broken files skipped); also BOM-saved profiles read (engine-io handover) | profiles.py | test_prepare `test_qa4_machine_profiles_with_wrong_types…`, `test_qa4_a_profile_saved_with_a_byte_order_mark…` |
| Low | layout-order | fabrics.apply clamps spacing to 0.2-3 for all | Fixed: satin 0.15-3, fill 0.2-5 | fabrics.py `apply` | test_layout `test_qa4_fabric_presets_keep_spacing…` |
| Low | layout-order | No tests for optimize_order, travel_under, sort, split stops | Fixed (tests added throughout) | | see above |
| Low | layout-order | Presets never suggest knockdown | Fixed: towel and fleece advice names Knockdown stitches | fabrics.py `advice` | test_layout `test_qa4_fabric_presets…` |
| Low | layout-ops | Trim jumps doubles existing trims | Fixed: a TRIM just before the jump counts | layout.py `_jumps_to_trims` | test_layout `test_qa4_trim_jumps_leaves_already_trimmed…` (old test fixed: it asserted the bug) |
| Low | layout-ops | Malformed ops crash render; index -1 deletes lettering | Fixed: damaged ops skipped; negative indices ignored | layout.py `_index`, `_mm`, `_apply_ops`, `_move_stitches` | test_layout `test_qa4_damaged_stitch_edits…`, `test_qa4_index_minus_one…` |
| Low | layout-ops | New ops not versioned | Already fixed by engine-io (features list); added `move_stitches` and layout-wide `jumps_to_trims` (`trim_jumps_all`) to it | project.py `_features`, `KNOWN_FEATURES` | test_project (existing) |
| Low | layout-ops | N move_stitch ops per drag | Fixed: one `move_stitches` op per drag (old projects still read) | features.ts, layout.py `_move_stitches`, types.ts | test_layout `test_qa4_one_op_moves_many_stitches`, features.layout.test.ts |
| Low | compat | Project VERSION not bumped | Already fixed (engine-io) | project.py | |
| Low | compat | tsconfig.tsbuildinfo not ignored | Already fixed (`*.tsbuildinfo` in .gitignore) | .gitignore | - |
| Low | export | Split loses single stitches; overwrites numbered files | Fixed: one-stitch runs kept; never replaces earlier split files ("name (1) 1 of 3.pes") | split.py `_blocks`, `_cut`; layout.py `export_split` | test_m8 `test_qa4_single_stitch_dots…`, test_layout `test_qa4_split_export_never_replaces…` |
| Low | export | PE550D: untrimmed long jumps no cut, no warning; PEC trim flag on jumps | Fixed (warning): info note counts long jumps not marked for trimming; dialog wording. PEC trim flag: skipped (pyembroidery writer; harmless on PE550D) | prepare.py `check` (`untrimmed_jumps`), ExportDialog.tsx | test_prepare `test_qa4_long_jumps_not_marked…` |
| Low | export | PES v6 16-bit segment count | Skipped: in pyembroidery's PES table only, machines read the PEC block; a 65,535-stitch unbroken run doesn't fit the 4x4 hoop in practice | - | - |
| Low | export | Odd destinations: raw errors; batch into source does nothing | Fixed: plain messages (no extension, unknown type, Windows device names); converting into the source folder (or one holding it) works | design.py `write`, `convert_folder` | test_design `test_qa4_plain_messages…`, `test_qa4_batch_convert_into_the_source_folder…` |
| Low | export | Empty design exports silently | Fixed: preview error "There's nothing to sew" and a refusal before writing | prepare.py `check`, design.py `write` | test_prepare `test_qa4_empty_design…`, test_design `test_qa4_nothing_to_sew…` |
| Low | export | JEF hoop code / stop as colour 0 (Suspected) | Skipped: needs a Janome stitch-out (queue for the stitch-out log) | - | - |
| Medium | autotrace | Fewer jumps render time at 1000+ objects | Fixed: object cache 4096; 1000 shapes render 0.2 s warm (travel on or off) | layout.py | (timing, not pinned) |
| Medium | docs-a | Manual overstates cut-stops | Fixed in the app (note for untrimmed jumps); manual: see below | prepare.py | - |
| Medium | docs-b | Insert stop/trim can't target lettering | Fixed: lettering records are numbered | layout.py `_text_block`, layout.ts `insertAt` | test_layout `test_qa4_a_stop_can_be_inserted_in_lettering` |
| Medium | docs-b | Trim jumps covers only existing designs | Fixed: one layout-wide setting (`jumps_to_trims`); older per-design ops still read | layout.ts `jumpsToTrims`, layout.py `render` | layout.test.ts, test_layout `test_jumps_to_trims` |
| Medium | fuzz-rpc | Stop/trim in a drawn shape moves when the shape changes | Fixed: the insert remembers the shape's record count (`n`); when the shape changes it is left out with a note | layout.py `_apply_ops`, layout.ts `insertAt` | test_layout `test_qa4_a_stop_in_a_drawn_shape…`, layout.test.ts |
| Medium | fuzz-rpc / satin | JEF long stitches | Fixed (as export) | design.py | test_design |
| Medium | shapeops | Outline follows hidden travel | Fixed engine-side: hidden travel belongs to no item | layout.py `_join_objects` | test_connectors `test_qa4_hidden_travel_belongs_to_no_shape` |
| Medium | project | Machine/split files written in place | Fixed (as export) | design.py | test_design |
| Medium | tests | Split stops, seam locks, no-overwrite untested | Fixed | | test_m8, test_layout |
| Medium | tests | Golden PES/JEF tests skip in CI | Already fixed (test_golden uses committed samples/) | | test_golden |
| Medium | tests | Cuts that cut-stops depend on untested | Fixed | | test_layout `test_qa4_cut_stops_*` |
| Medium | tests | JEF/PES export settings barely tested | Fixed | | test_layout `test_qa4_jef_export_for_janome…`, `test_qa4_machine_stitch_limit…` |
| Medium | tests | travel_under one scenario | Fixed (more cases incl. cover margin) | | test_connectors `test_qa4_*` |
| Low | tests | Text cache key fields untested | Fixed | | test_layout `test_qa4_fabric_reaches_lettering_and_the_text_cache_key…` |
| Low | fuzz-rpc | Blank PES with every stitch removed | Fixed (as export) | | |
| Low | live-esc | Export/Batch busy guard beaten by second Esc (ui handover) | Fixed: Esc keydown stopped while busy; a close that slips through reopens | ExportDialog.tsx, BatchDialog.tsx | none (DOM; vitest has no DOM) |
| Low | live-esc | Names dialog defaults to PES on a JEF machine | Already fixed by another agent | FeatureDialogs.tsx | - |
| - | ui handover | layout.test.ts "jumps-to-trims is one setting" failing | Fixed: test updated to the layout-wide setting (my change) | layout.test.ts | itself |
| - | platform handover | Names: duplicates / names cleaning to one file name | Already fixed (keep_existing gives "Name (1)"; checked: Emma/Emma, A_B/A_B, anna/Anna); report now honest when a name fails | features.ts | features.layout.test.ts |
| Low | engine-io handover | Source-file cache trusts mtime, never evicted | Fixed: keyed by time, size and the copy read; at most 32 kept (least recently used out) | layout.py `_load` | test_layout `test_qa4_source_cache_notices…` |
| Low | engine-io handover | Object cache capped at 512 | Fixed: 4096 | layout.py | - |
| Low | engine-io handover | Text cache stale when a .luddfont changes | Already fixed (lettering agent: `font_stamp` in the key) | layout.py | - |
| Low | engine-io handover | Crafted .vp3/.hus allocates GBs | Skipped: inside pyembroidery's readers; a real guard needs a subprocess memory limit (owner's call) | - | - |
| - | stitches handover | Batch convert into the same folder; JEF long-stitch setting | Fixed (see export rows: `convert_folder`, SEW_TO) | design.py | test_design `test_qa4_batch_convert_into_the_source_folder…`, `test_qa4_long_stitches…` |
| - | stitches handover | Tighten applique cover-width tolerance in test_m8 | Fixed: 0.15 -> 0.03 mm | test_m8.py | itself |
| Low | engine-io handover | Batch convert follows folder junctions | Fixed: recursive convert doesn't enter links or junctions | design.py `convert_folder` | none (junctions need admin/mklink to set up) |

## Changelog lines
- "Sort colors" no longer sews a shape before the one meant to be underneath it; colours that can't be gathered safely stay apart, with a note.
- "Sew in the shortest order" now works with "Fewer jumps & trims" on, mixes fills and lines in one thread, and only keeps overlapping shapes in their order.
- "Fewer jumps & trims" hides a move only under rows close enough to really cover it.
- Splitting across hoopings: the overlap setting is now the real overlap; empty hoopings are left out; the pink crosses go on bare fabric where there's room; single-stitch dots are kept; fewer lock stitches at the seam; earlier split files are never replaced.
- A design a little too big for the hoop gets a "Make it N% smaller" button before the split.
- The basting box comes in closer to fit the hoop instead of making the design too big.
- JEF files: stitches longer than 12.7 mm are sewn in pieces (no more needle-up jumps), and the design is centred on the hoop.
- Saving never leaves a half-written file; PES files with accented thread names keep a readable thread list; PES files over 255 colour steps are refused with an explanation; designs with nothing to sew are refused.
- Save for machine notes long jumps the design doesn't mark for trimming (they won't be cut).
- Thick spots inside bought stitch files are a note, not a warning; the gap check works on designs with many shapes.
- Stitch editing: Delete with nothing selected no longer deletes the design; a stop or trim survives deleting its stitch; a drag is saved as one edit.
- Stops and trims can be inserted in lettering; one added to a shape is left out (with a note) if the shape changes.
- "Trim jumps longer than 3 mm" now covers designs added later too.
- Fabric presets now adjust lettering; towel and fleece advice mentions knockdown.
- Machine profiles with wrong values (or saved by Notepad with a byte-order mark) are handled.
- "One file per name" saves the other names when one fails and says which.

## Manual changes needed
- Cut-stops (USER-MANUAL around "long jumps become stops"): only jumps marked for trimming become stops unless "Also cut jumps the design doesn't mark" is ticked; Save for machine now says when there are such jumps.
- Split (around 86-89): overlap is now the real minimum overlap of the hoopings (more overlap can mean more hoopings); empty hoopings are skipped; crosses go on bare fabric when possible.
- Save for machine: describe "Make it N% smaller" for designs up to 5% too big.
- Basting (around 504): the box comes in closer (to 2 mm) to fit the hoop chosen when it was turned on.
- Sort colors (around 464): colours that would hide a shape under another stay apart.
- Shortest order (around 512-514): matches the new behaviour (overlapping shapes keep their order; fills and lines mix).
- Fabric section: presets affect lettering too; towel/fleece mention knockdown.
- Trim jumps: one setting for the whole design.
- Check-before-stitching: thick spots in bought designs are notes.

## Stitch output changed
- JEF: every JEF now centred on (0,0) (was the source position). Test design: Key.PES -> JEF on a Janome; check it sits centred in the hoop. Also stitches over 12.7 mm (all formats except PES) are now split into stitches, not jump+stitch: test a 13 mm satin to JEF.
- PES thread names with accents are transliterated (Grün -> Grun); colours unchanged.
- Fewer jumps & trims: travel hidden only under rows ≤0.7 mm apart (more trims on sparse covers).
- Sort colors: may keep some colours apart (more colour changes) where gathering would bury a shape.
- Split: hoop count can rise (180 mm wide at 10 mm overlap: 3 hoopings, was 2); crosses in new places; fewer seam locks; single stitches kept. Test design: "Banner (two hoopings)" sample split on the PE550D; check the seam for gaps and that the crosses can be pulled out.
- Lettering on towel/knit/fleece etc.: density now follows the fabric preset.
- Basting with `fit_mm`: box margin may shrink to 2 mm.
- Snapshots: none re-recorded.

## Handed over
- InfoPanel owner: Knockdown thread picker (layout.knockdown.thread) and telling basting and knockdown apart in the thread list.
- patterns/fill owner: stipple sews only the largest region (digitize/patterns.py `stipple_path`).
- Lead / owner decision: pyembroidery reader memory guard for crafted .vp3/.hus; JEF hoop code and stop colour index need a Janome stitch-out; consider a margin control for basting.
- styles.css owner (optional): `.shrink-fit` paragraph in ExportDialog has no style of its own (renders as a plain paragraph with a primary button).
