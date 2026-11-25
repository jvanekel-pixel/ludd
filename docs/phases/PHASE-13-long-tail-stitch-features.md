# Phase 13: Long-tail stitch features

| | |
| --- | --- |
| Weight | Heavy |
| Session lead | Sonnet 5.5. **Track A is hard: give its worker the stronger model.** |
| Depends on | Phases 4, 6 and 7. Track C's thumbnails use Phase 10's cache if it is built (fallback in P13-C2). |
| Changes stitches | Yes: new stitch types and shared underlay. Nothing that exists sews differently. |
| Closes (compendium) | Convert stitches back to objects (L-007); string stitch, shadow work, chain stitch; cutwork needle lines; cross-stitch outline; continuous underlay across objects; word art; assemble designs from parts |
| Spec depth | Light: scope, architecture and tests are fixed. **Do section 4 first** and update this file before building. |

## 1. Goal and done-when

These are the review's "Later" rows: things the big commercial packages have and hobbyists ask for now and then. The largest is turning a bought stitch file back into shapes that can be resized, re-angled and recolored like anything drawn in LUDD.

**Done when:**

1. A known run, satin and fill, sewn to stitches and turned back into shapes, match the originals: outline within 0.5 mm, angle within 3°, spacing within 10% (the round-trip tests in Track A).
2. Converting `samples/Flower.pes` gives shapes that cover the same area (overlap of 0.9 or more), and every stitch that was not converted is still in the design, in the same sewing order.
3. Chain, string, shadow-work and cross-stitch-outline stitches pass their tests and the invariants, each with its own snapshot suite.
4. Two touching same-thread fills with a shared underlay sew one underlay, then both tops.
5. Word art fills an 80 mm circle with ten or more words, none overlapping, all inside; the same seed gives the same layout.
6. A selection saved as a part comes back from the Parts dialog as one group.
7. `python scripts/check.py --all` prints `RESULT: PASS`, the snapshot files of earlier phases are unchanged, and `pnpm build:engine` passes its smoke check.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P13-S1 | Types, feature flags, method stubs, descriptors, command files, `fill_underlay` extraction | No | Step 0 |
| P13-A1 | Recognition: runs, satins, fills, with their underlay and ties attached | No | A |
| P13-A2 | Shapes from what was recognized, each with a confidence | No | A |
| P13-A3 | File slices: a placed file that shows only part of its stitches (`keep_range`) | No | A |
| P13-A4 | Turn stitches into shapes: preview, per-shape choice, accept (`stitch.toShapes`) | Yes | A |
| P13-B1 | Chain stitch (line style) | Yes | B |
| P13-B2 | String stitch (fill pattern) | Yes | B |
| P13-B3 | Shadow work (satin style) | Yes | B |
| P13-B4 | Cutwork needle lines (line style); owner decision 1 | Yes | B |
| P13-B5 | Outline for cross-stitch fills | Yes | B |
| P13-B6 | One underlay under touching shapes (`layout.sharedUnderlay`) | Yes | B |
| P13-C1 | Word art: fill a shape with words (`text.wordArt`) | Yes | C |
| P13-C2 | Parts library (`file.parts`) | Yes | C |
| P13-Z1 | Docs, stitch-out rows, frozen-engine check, handoff | – | Integration |

**Out of scope:** recognizing motif, contour, stipple, cross-stitch or blended fills inside a stitch file (they stay stitches); shared underlay for satins, lettering or different threads; a cutwork wizard (cover satin, bridges); word art that packs to letter outlines instead of boxes; sequins and beads (L-009); downloading parts.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Build cutwork lines? They cut fabric, and cannot be tested without cutwork needles that fit the PE550D. | Only if you will buy a needle set and test it in Phase 15. | P13-B4 is not built; its spec stays here. |
| 2 | "String stitch" is specified as the string-art fill (threads stretched across a shape). Is that what you meant? | Yes. Check it against the Wilcom and Floriani pages from the review. | Built as specified. |
| 3 | Add a fabric preset "Sheer (organza, batiste)" for shadow work? | Yes: light density, 0.1 mm edge pad, light underlay, water-soluble stabilizer. | No new preset; the panel hint names the nearest fabric and the stabilizer. |
| 4 | Ship about twelve built-in parts, drawn by a script in this repo? | Yes. They are made here, so there is no license question. | Yes. |

## 4. Refresh this spec first

These facts are the most likely to have moved since this was written. Check each, fix the spec, then build.

| Fact assumed | How to check | If it changed |
| --- | --- | --- |
| Phase 4 left a recognizer that splits one color of a stitch file into fill rows and satin columns | `grep -rnE "def (recogni[sz]e\|segment\|find_rows\|find_columns)" engine/threadline_engine` (Phase 4's spec puts it in `repair/recognize.py`: `recognize(points) -> list[Span]`) | P13-A1 builds on what it returns. If there is none, A1 writes it from the thresholds in Track A. |
| No item op already shows a slice of a file | `grep -rn "register_item_op(" engine/threadline_engine` | Reuse the existing op instead of `keep_range`. |
| `backstitch` is a registered line style; `chain` and `cutwork` are not | in `engine/`: `uv run python -c "from threadline_engine.digitize import lines; print(list(lines.REGISTRY))"` | Rename to avoid a clash. |
| `SatinParams` has no `style` field yet (Phase 8's puff may have added one) | `grep -n "class SatinParams" -A 14 engine/threadline_engine/digitize/stitches.py` | Herringbone becomes one more value of the field that exists. |
| `cross` is registered in `fills/builtin.py` and calls `cross_paths(poly, size)` | `grep -n "cross" engine/threadline_engine/digitize/fills/builtin.py` | Follow the new call. |
| `_fill_part` still sews the edge rings, then the cross-hatch, then the top | read `_fill_part` | Adjust the Step 0 extraction. |
| A placed file with any op other than `jumps_to_trims` sews from its private copy | `kept.has_edits` | Slices depend on this; if it changed, pin slices explicitly. |
| Samples are a bundled folder found with `resolveResource("samples")`; the golden tests list `samples/` without subfolders | `openSample` in `actions.ts`; `designs_in` in `test_golden.py` | Put built-in parts where a bundled folder is, and keep them out of the sample tests. |
| Phase 10's library can make and keep a thumbnail for a `.ludd` | `grep -n "def " engine/threadline_engine/library*.py` | Use the fallback in P13-C2. |
| `fabrics.FABRICS` ids; `lettering.layout_text(spec)` returns objects centered on (0, 0) | read both | Adjust decision 3 and Track C. |
| The four reserved shortcuts are still free | `grep -rnF -e "Alt+Shift+X" -e "Alt+Shift+W" -e "Alt+Shift+Y" -e "\"Alt+L\"" apps/desktop/src` | Pick from the free list in `README.md`. |

## 5. Architecture

### 5.1 Data model (TypeScript types and what the engine accepts)

```
LayoutOp        += { op: "keep_range"; from: number; to: number }   // a placed file showing only file stitches from..to
RunParams.style += "chain" | "cutwork";  chain_mm?, chain_width_mm?, cut_step_mm?, cut_reinforce?
FillPattern     += "string";             string_mm?, string_reach?;  cross_outline?: boolean (cross-stitch only)
SatinParams     += style?: "satin" | "herringbone";  herring_mm?
ObjectBase      += underlay_group?: string                           // fills that share one underlay
```

Feature flags: `file_slices`, `line_chain`, `line_cutwork`, `fill_string`, `fill_cross_outline`, `satin_herringbone`, `shared_underlay`. Word art and parts make ordinary items and need none.

### 5.2 Engine

```
engine/threadline_engine/
  toshapes.py                  NEW (A)  recognize -> shapes -> confidence
  layout/slices.py             NEW (A)  the keep_range item op (local stage)
  digitize/lines/chain.py      NEW (B)
  digitize/lines/cutwork.py    NEW (B, decision 1)
  digitize/fills/string.py     NEW (B)
  digitize/satin_styles.py     NEW (B)  herringbone, called from satin_from_pairs
  layout/shared_underlay.py    NEW (B)  an after_items pass
  wordart.py                   NEW (C)
  parts.py                     NEW (C)
  methods/parts.py             NEW (C)  one more group file
```

### 5.3 RPC methods (names go into `rpc_methods.json` in Step 0)

| Method | Parameters | Returns |
| --- | --- | --- |
| `stitch.to_shapes` | `layout, id, block=None` | `{shapes: [{from, to, kind, object, confidence, stitches}], kept: [[from, to]], colors}` |
| `text.word_art` | `container, words, font, options` | `{items, coverage, placed, left_out}` |
| `parts.list` | – | `[{path, name, category, builtin, thumb, width_mm, height_mm, stitches}]` |
| `parts.open` | `path` | a project, as `project.open` gives |
| `parts.save` | `name, category, project_data` | `{path}` |
| `parts.delete` | `path` | – |

### 5.4 UI

```
apps/desktop/src/
  feat/toShapes.ts, components/ToShapesDialog.tsx, cmd/toShapes.ts            (A)
  feat/sharedUnderlay.ts, cmd/sharedUnderlay.ts                               (B)
  feat/wordArt.ts, components/WordArtDialog.tsx                               (C)
  feat/parts.ts, components/PartsDialog.tsx, cmd/compose.ts                   (C)
```

Previews draw through `registerOverlay`; dialogs open through `registerDialog`.

## 6. Step 0 (session lead)

1. `git switch -c phase-13/long-tail-stitch-features`.
2. `design/types.ts`: everything in 5.1. `project.py`: the seven feature flags with their detectors.
3. `rpc_methods.json` and stub methods (they raise "not built yet") for the six methods in 5.3; `methods/__init__.py` imports `parts`.
4. Stub modules with their registry import lines: `lines/chain.py`, `lines/cutwork.py`, `fills/string.py`; entries in `design/lineStyles.ts` and `design/fillPatterns.ts` (the fields are in Track B); the `cross_outline` tick in the cross-stitch entry.
5. `stitches.py`, two pure moves that must leave every snapshot unchanged: the underlay part of `_fill_part` becomes `fill_underlay(poly, params, start, target)`; `satin_from_pairs` gains a `style` lookup that calls `satin_styles` for anything but `"satin"`. `SatinParams` gains `style` and `herring_mm`.
6. `patterns.py`: `cross_squares(poly, size)` returns the squares `cross_paths` uses; `cross_paths` calls it. Output unchanged.
7. `cmd/index.ts`: import lines for the three command files, each registering its command with a "not built yet" notice.
8. Run `python scripts/check.py`; commit. Workers branch from here.

## 7. Tracks

A, B and C run together. Every worker follows "Worker rules" in `BUILDPLAN.md`.

---

### Track A: stitches to shapes (hard)

**Owns:** `toshapes.py`, `layout/slices.py`, the body of `stitch.to_shapes`, `feat/toShapes.ts`, `components/ToShapesDialog.tsx`, `cmd/toShapes.ts`, `engine/tests/test_toshapes.py`.

**Behavior.** Select a placed stitch file (or one of its colors in Order & colors) and press `Alt+Shift+X`. LUDD shows the shapes it can make, each outlined on the design with a confidence and a "Keep as stitches" tick. Accept swaps those stitches for shapes in one undo step. Stitches it could not make sense of stay stitches, in the same sewing order. The file on disk is never changed.

**P13-A1 Recognition** (in the file's own frame, millimeters):

1. Split each color at jumps, trims and stops into segments.
2. For each stitch take its length, its direction and the turn from the stitch before.
3. Label windows of eight or more stitches:
   - **Satin:** every turn sharper than 150°, lengths 1 to 12 mm, midpoints moving on 0.2 to 1.0 mm a stitch. Even points are one edge, odd points the other.
   - **Fill:** rows of two or more stitches in line (turns under 15°, lengths within 25% of the row's median), a step of 1.5 mm or less at each row end, neighboring rows parallel within 3°, rows 0.25 to 1.2 mm apart. Rows of one stitch each are a satin.
   - **Run:** what is left, with stitches up to 5 mm. Each stitch sewn three times is Bean; the whole path three times is Triple.
4. Attach what belongs to a shape: a sparse segment (center run, edge run, zigzag or cross-hatch 1.5 to 3 mm apart) with 90% of its length inside a later satin or fill of the same color is that shape's **underlay**; three or four stitches under 0.8 mm at an end are **ties**; a run inside a later fill that only joins two segments is **travel**. The new shape makes its own, so these are dropped with it, not sewn twice.

**P13-A2 Shapes.**

| Kind | Geometry | Settings read from the stitches |
| --- | --- | --- |
| Fill | row ends on each side make region polygons; merge with `buffer(spacing / 2).buffer(-spacing / 2)`; holes kept; nodes from `shapeops.to_nodes` | `angle_deg` median row direction; `spacing_mm` median row gap; `stitch_mm` median stitch in a row; `pull_comp_mm: 0` (the outline is where the stitches really ended); `underlay` what was attached, else `[]` |
| Satin | edges thinned to a point about every 2.5 mm; a ribbon (`nodes`, `width_mm`) when the width varies under 10%, else a column (`rail_a`, `rail_b`) | `spacing_mm` median advance; `pull_comp_mm: 0`; `underlay` as attached |
| Run | the path simplified to 0.15 mm; closed when its ends meet within 0.5 mm | `style` single, triple or bean; `stitch_mm` median |

**Confidence** (0 to 1): generate the proposed shape with `dz.generate` and compare it with the stitches it replaces. Fills and satins: overlap (intersection over union) of the two covered areas, lines thickened 0.35 mm as `_cover` does. Runs: 1 at a Hausdorff distance of 0.4 mm, falling to 0 at 1.5 mm. Multiply by a count factor: 1 when the stitch counts agree within 15%, falling to 0 at 50%. 0.85 or more is "good" (ticked to convert); 0.60 to 0.85 is "check this one" (shown, unticked); under 0.60 is not offered.

**P13-A3 Slices.** `keep_range` is a local item op: it keeps the records whose file index is from `from` to `to`. Accepting turns one placed file into several items on the same path, in file order, with the new shapes between them, grouped. Threads and other ops stay on every slice.

**P13-A4 Preview and accept.** `stitch.to_shapes` answers from a background thread and takes the dispatcher's lock only while it reads the file. The dialog lists shapes by color with kind, size and confidence; the overlay outlines them (good in the mark color, "check" in amber).

| Test (`test_toshapes.py`) | Asserts |
| --- | --- |
| `test_run_round_trip`, `test_bean_and_triple_are_recognized` | path within 0.5 mm; style and stitch length within 10% |
| `test_satin_ribbon_round_trip`, `test_satin_column_round_trip` | edges within 0.5 mm; width within 0.3 mm; spacing within 10% |
| `test_fill_round_trip_square_45`, `test_fill_with_hole_round_trip` | outline within 0.5 mm; angle within 3°; spacing and stitch length within 10% |
| `test_underlay_is_attached_not_doubled` | the converted design sews one underlay per shape |
| `test_low_confidence_stays_stitches` | a stipple fill is not offered |
| `test_every_stitch_is_kept_or_converted` | the ranges cover the file with no gap and no overlap |
| `test_sewing_order_is_unchanged` | slices and shapes alternate in file order |
| `test_keep_range_shows_only_its_slice` | through `layout.render` |
| `test_flower_sample_covers_the_same_area` | overlap of covered area 0.9 or more |
| `test_samples_convert_without_error` | every sample; the owner's `fixtures/` too when present |
| `test_one_color_only`, `test_project_names_file_slices` | `block` limits it; the feature flag is set |
| `accept swaps stitches for shapes in one undo step` (`feat/toShapes.test.ts`) | undo brings the file back whole |
| `unticked shapes stay stitches` (same) | |

---

### Track B: more stitch types

**Owns:** `lines/chain.py`, `lines/cutwork.py`, `fills/string.py`, `satin_styles.py`, the `cross` entry in `fills/builtin.py`, `layout/shared_underlay.py`, `feat/sharedUnderlay.ts`, `cmd/sharedUnderlay.ts`, one line in the Underlay fold of `ObjectPanel.tsx`, the cutwork skip in `quality.py`, new tests `test_line_chain.py`, `test_line_cutwork.py`, `test_fill_string.py`, `test_satin_herringbone.py`, `test_cross_outline.py`, `test_shared_underlay.py`. Each new type passes `assert_sane`, `assert_deterministic` and `assert_moves_with_shape`.

| Item | What it is | Settings (default, range) | How it is sewn |
| --- | --- | --- | --- |
| B1 Chain | **Line style** `chain`: small loops like a hand chain stitch | `chain_mm` Link length 3, 2–6 · `chain_width_mm` Width 1.5, 0.8–3 | Per link from `s` to `s+L`: `s` → mid left → `s+L` → mid right → `s` → `s+L`. Links are fitted between corners sharper than 40° (length adjusted up to 20%), so none straddles a corner. |
| B2 String | **Fill pattern** `string`, open: threads stretched across the shape, like string art | `string_mm` Point spacing 3, 1.5–8 · `string_reach` Reach 35%, 10–50 | `n` points round the outer edge; `k = round(n × reach)`; one unbroken line p0 → p(k) → p1 → p(k+1) → p2 … A thread longer than the stitch length (default 4, at most 7) gets needle points. A thread that would leave the shape follows the edge instead, and a warning counts them. No underlay on automatic. |
| B3 Shadow work | **Satin style** `herringbone`, for sheer fabric: crossing diagonals with a line of short stitches along each edge | `herring_mm` Step 2, 1–5 | Edge points every half step: A0 → B2 → B1 → A3 → A2 → B4 → B3 … Works for ribbons, columns and satin fills. No underlay, no edge pad, no split. Warns when a diagonal passes 7 mm. |
| B4 Cutwork | **Line style** `cutwork` (decision 1): the line is cut by the four cutwork needles (blades at 0°, 45°, 90°, 135°) | `cut_step_mm` Step 0.3, 0.2–0.6 · `cut_reinforce` on | First two passes of running stitch 1 mm outside the line (off if unticked). Then, for each needle, the parts of the line within 22.5° of its blade as needle drops `cut_step_mm` apart, with a stop before each needle (as applique stops). The panel and the print template say which needle to fit and when to take the thread out and put it back. Marked "Needs cutwork needles and a machine that takes them. Not tested on the PE550D." The "needle hits one spot" and "very short stitches" checks skip it. |
| B5 Cross-stitch outline | A tick on Cross-stitch fills (`cross_outline`) | off | After the crosses, a backstitch round the stepped edge of the crossed area and round holes: each square side sewn there and back, in the fill's thread. Sides over 7 mm get a midpoint. |

**P13-B6 One underlay under touching shapes.** Select two or more fills and press `Alt+Shift+Y`; again to separate them. Two fills **touch** when their outlines overlap or lie within 0.6 mm of each other (the gap check's distance). A group is fills with a row pattern that allows cross-hatch underlay, in one thread, next to each other in the sewing order, twelve at most. The pass builds the union (each outline grown 0.3 mm, merged, shrunk back), sews one edge run round it and one cross-hatch across it (the first member's angle plus 90°, spacing from the fabric) at the start of the first member, then each member's top with `underlay: []`. Travel from the underlay to the first top stitch stays inside the union. A member that touches no other, or breaks a rule, sews as usual with a note. The Underlay fold says "Shares one underlay with 2 other shapes".

| Test | Asserts |
| --- | --- |
| `test_chain_links_are_even`, `test_chain_keeps_corners`, `test_chain_closed_line_meets` | suite `lines_chain` |
| `test_string_circle_is_one_line`, `test_threads_span_the_reach`, `test_long_threads_get_needle_points`, `test_inward_curve_follows_the_edge_and_warns` | suite `fills_string` |
| `test_herringbone_order`, `test_diagonals_cross`, `test_no_underlay`, `test_wide_column_warns`, `test_plain_satin_unchanged` | suite `satin_herringbone`; old satin snapshots untouched |
| `test_cutwork_splits_by_direction`, `test_a_stop_before_each_needle`, `test_reinforcing_run_is_outside`, `test_quality_checks_skip_cutwork` | suite `lines_cutwork` (decision 1) |
| `test_outline_follows_the_grid`, `test_outline_round_a_hole`, `test_each_side_sewn_twice`, `test_off_by_default_unchanged` | suite `fills_cross_outline`; `fill_cross` snapshot untouched |
| `test_two_touching_fills_get_one_underlay` | fewer underlay stitches than the two apart; all inside the union |
| `test_tops_are_unchanged`, `test_underlay_sews_before_any_top` | each top equals that fill generated with no underlay |
| `test_apart_or_other_thread_or_not_adjacent_sews_alone_with_a_note` | suite `shared_underlay` |
| `the command joins two fills and separates them again` (`feat/sharedUnderlay.test.ts`) | |
| `each new setting shows its fields` (`ObjectPanel.dom.test.tsx`) | from the descriptors |

---

### Track C: composition

**Owns:** `wordart.py`, `parts.py`, `methods/parts.py`, the body of `text.word_art`, `scripts/make_parts.py`, `samples/parts/**`, `feat/wordArt.ts`, `components/WordArtDialog.tsx`, `feat/parts.ts`, `components/PartsDialog.tsx`, `cmd/compose.ts`, `engine/tests/test_wordart.py`, `engine/tests/test_parts.py`.

**P13-C1 Word art** (`Alt+Shift+W`, with a closed shape selected). The dialog asks for words (one per line; the first is the biggest), and offers Biggest (22% of the shape's smaller side, 40 mm at most), Smallest (6 mm, never under 5), Directions (Level / Level and upright / Tilted up to 30°), Gap (1.2 mm, 0.6–4), Repeat words to fill (on), Colors (one thread, or cycle the design's threads) and Shuffle. Packing: sizes go from Biggest down by 0.8 each step; for each word its box is the bounds of `lettering.layout_text` at that size, grown by half the gap and turned; positions are tried along a spiral from the shape's middle in 1 mm steps; the first where the box is inside the shape (shrunk 1.5 mm) and clear of every placed box is taken. It stops at 150 words, when a pass at the smallest size places nothing, or after 2 seconds. A seed makes it repeatable. The result is ordinary lettering, one text item per word, in one group; the shape stays. The preview shows outlines; Add commits one undo step.

**P13-C2 Parts library** (`Alt+L`). A part is an ordinary `.ludd` file. "My parts" live in the data folder's `parts` folder (subfolders are categories); built-in parts ship in `samples/parts/` and are read-only. The dialog shows thumbnails with search and category chips; Enter or a double-click inserts; "Save the selection as a part…" and Delete (My parts, after a confirm) are buttons in the dialog. Insert appends the part's items with new ids as one group, centered in the hoop and selected; the part's pictures and fabric are ignored. Save re-centers the selection on (0, 0). Names are cleaned as stitch-font names are, and no method reads or writes outside the two parts folders. Thumbnails come from Phase 10's cache; without it, render the part with `layout.render` and `library.thumbnail`. `scripts/make_parts.py` draws the built-in twelve (leaf, petal, flower center, star, heart, bow, banner, swirl, laurel half, frame corner, dot row, ribbon tail) from shapes only.

| Test | Asserts |
| --- | --- |
| `test_same_seed_same_layout`, `test_boxes_never_overlap`, `test_everything_inside_the_shape` | `test_wordart.py` |
| `test_first_word_is_biggest`, `test_repeat_off_places_each_word_once`, `test_too_small_a_shape_reports_left_out`, `test_stops_at_150_words` | |
| `test_items_render` | `layout.render` on the result, with the test font from `test_lettering.py` |
| `test_save_list_open_round_trip`, `test_part_is_recentered` | `test_parts.py` |
| `test_names_cannot_leave_the_parts_folder` | `../x`, absolute paths and reserved names are refused |
| `test_built_in_parts_cannot_be_deleted`, `test_every_built_in_part_renders` | |
| `insert gives new ids and one group; undo removes it whole` (`feat/parts.test.ts`) | |
| `Add makes one group in one undo step` (`feat/wordArt.test.ts`) | |

## 8. Integration (session lead)

1. Merge B, then A, then C. Run `python scripts/check.py --all`. Snapshot files from earlier phases must be unchanged.
2. `pnpm build:engine` once: there are new engine modules and a new method group.
3. Write the docs (section 9); run `python scripts/kb_commands.py`; check again; then the stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**Knowledge base.** New entries: `F-1907` Turn stitches into shapes · `F-1810` One underlay under touching shapes · `F-1321` Chain, string and shadow-work stitches · `F-1322` Cutwork lines (if built) · `F-1323` Cross-stitch outline · `F-1421` Word art · `F-213` Parts library. `L-007` becomes PARTIAL and points to `F-1907`. Index rows for each. Limits and troubleshooting from this phase's blocks:

| ID | Entry |
| --- | --- |
| L-075 | Stitches to shapes does not recognize motif, contour, stipple, cross-stitch or blended fills; the original edge pad and underlay are estimated |
| L-076 | Shared underlay: same-thread row fills next to each other in the sewing order only; not satins or lettering |
| L-077 | Cutwork lines are untested on a real machine (or: not built) |
| L-078 | Word art packs boxes, not letter shapes; thin or deeply notched shapes fill poorly; 150 words at most |
| L-079 | String stitch suits shapes that bulge outward; threads that would leave the shape are left out |
| T-059 | "A converted shape doesn't look like the stitches it came from": undo, or tick Keep as stitches |
| T-060 | "Turn stitches into shapes found nothing": layered or hand-punched designs; what to try |
| T-061 | "Word art left words out": bigger shape, smaller Smallest, fewer words |
| T-062 | "A part looks different after I insert it": this design's fabric applies; a missing font is replaced |

**Changelog, manual, Help:** one line per user-visible item in section 2; manual sections 2 (parts), 4 (line styles), 6 (fill patterns, satin styles, shared underlay), 7 (word art) and the stitch-file section (stitches to shapes); the same facts with their shortcuts in `ai/helpdocs.py`.

**`docs/stitchout-log.md`**, rows in "Pending machine tests":

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 13 | **Stitches to shapes** | A bought design converted, then sewn beside the original | Same look and size; no doubled underlay; no gaps where shapes meet kept stitches |
| Phase 13 | **Chain stitch** | A 60 mm S curve and a closed square, 3 mm links | Even links; corners clean; the square meets itself |
| Phase 13 | **String stitch** | A 50 mm circle and a hexagon, Reach 35% | Threads lie flat; no loose long stitches |
| Phase 13 | **Shadow work** | A 4 mm ribbon and a petal on organza with water-soluble stabilizer | Diagonals cross evenly; edge stitches make a clean line; fabric does not pucker |
| Phase 13 | **Cross-stitch outline** | A 40 mm cross-stitch heart with Outline on | The outline sits on the edge of the crosses, corners square |
| Phase 13 | **Shared underlay** | Two abutting fills, and three overlapping petals | No gap or ridge where the shapes meet; lies as flat as separate underlays |
| Phase 13 | **Cutwork lines** (if built) | A 30 mm circle on stabilized cotton | A clean cut all the way round; the reinforcing run holds the edge |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Recognition is good on LUDD's own stitches and poor on bought files | the Flower sample passes, the owner's fixtures score low | Ship it honestly: low-confidence shapes stay stitches. Record the share converted per fixture in the handoff; do not loosen the thresholds to raise it. |
| Underlay is attached to the wrong shape and stitches vanish | `test_every_stitch_is_kept_or_converted` or the covered-area test fails | Attach only above 90%; otherwise keep the underlay as stitches and give the shape `underlay: []`. |
| The Step 0 moves in `stitches.py` shift a stitch | an old snapshot changes | The move is wrong. Never re-record an old snapshot here. |
| Shared underlay travel shows on an open-looking top | stitch-out row, or a long stitch in the invariants | Limit the first version to plain tatami tops. |
| Word art is slow with real fonts | the 2-second stop triggers before 20 words | Cache each word's box per size; lower the candidate count before raising the time. |
| Cutwork cannot be verified | no needles | Decision 1's default: not built. |
| The session runs out with three tracks | time or context | A, B and C are independent. Land what is merged and green; say which track is left in `HANDOFF.md`. |

## 11. Handoff

Write in `HANDOFF.md`: which owner decisions were answered and how; for stitches to shapes, the share of stitches converted on each sample (and fixture, if present); whether cutwork was built; whether Phase 10's thumbnail cache was used or the fallback; every spec deviation, one line each.
