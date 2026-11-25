# Phase 8: Specialty & in-the-hoop

| | |
| --- | --- |
| Weight | Medium |
| Session lead | Sonnet 5.5. No track needs the stronger model. |
| Audit | Standard phase gate. |
| Depends on | Phase 3 (seams) and Phase 6 (stitch quality, text options on patterns). Not on Phase 5 or 7, but read their Handoff if they were built first (section 4). |
| Changes stitches | Only the new lace fill, the puff and patch-edge satin options, and applique sets, partial cover and center-out order where the user turns them on. |
| Closes (compendium) | Freestanding lace fill · 3D puff foam satin · Patch edge and patch workflow · Applique from any group of objects, open shapes, partial cover · Multi-position hoops · Positioning sticker · Center-out sewing for caps · basting box margin (BACKLOG) · FCM cut files only if the owner says so |

## 1. Goal and done-when

Lace, puff, patches and bigger-than-the-hoop tricks are what hobbyists buy StitchArtist Level 2 and 3, PatchArtist or a bigger machine for. This phase adds them as options on what LUDD already has (a fill pattern, two satin options, a smarter applique, a hoop with positions), not as new kinds of object.

**Done when:**

1. `python scripts/check.py --all` prints `RESULT: PASS`, no snapshot recorded before this phase has changed, and each of the three new samples has PES and JEF beside it, covered by the golden test.
2. The new sample "Lace ornament" passes the lace checks on the wash-away fabric choice; with its border removed the check reports the bare edge (test).
3. A puff satin sews with no underlay, twice the density and capped open ends (tests), and the sample "Puff letter" renders.
4. Make a patch gives a base and a faux-merrow edge that sews last, with its cut file; the sample "Patch" renders.
5. Three shapes made into one applique set stop the machine twice, not six times (test).
6. A 100 × 170 mm design in a hoop with three positions saves as three files named by position, with no alignment crosses (test).

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P8-S1 | Branch, baseline check, shared-file seeds, command stubs | No | Step 0 |
| P8-A1 | Lace fill: grid, diamonds, honeycomb | Yes | A |
| P8-A2 | "Wash-away stabilizer (freestanding lace)" fabric choice and three lace checks | Yes | A |
| P8-A3 | 3D puff satin | Yes | A |
| P8-B1 | Applique sets: several pieces, two stops (`applique.fromSelection`) | Yes | B |
| P8-B2 | Leave the border out where a later shape covers it | Yes | B |
| P8-B3 | Open edges chosen by hand (first to cut if the track runs long) | Yes | B |
| P8-B4 | Patch edge: faux-merrow satin | Yes | B |
| P8-B5 | Make a patch (`tool.patch`), with its cut file | Yes | B |
| P8-B6 | FCM cut file, only if decision 1 says build | Yes | B |
| P8-C1 | Hoops with fixed positions; the design split into them | Yes | C |
| P8-C2 | Positioning stickers and a hooping sheet to print | Yes | C |
| P8-C3 | Sew from the center out: items and lettering | Yes | C |
| P8-C4 | Basting box margin | Yes | C |
| P8-Z1 | Three samples, docs, frozen-engine smoke check, handoff | – | Integration |

**Out of scope:** sequins, beads, chenille (out of scope for LUDD, L-009); cutwork needle lines (Phase 13); cap-frame machine profiles (Phase 12); camera positioning marks; an automatic stop for laying foam (decision 3).

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | FCM cut files for Brother ScanNCut: spend one hour looking for a written description of the format and a reference under a GPL-compatible license? Checking the result needs Brother's CanvasWorkspace and the owner's hands. | Skip. CanvasWorkspace imports the SVG cut file LUDD already writes. | Skipped. `applique.fcm` and F-1503 stay unused; L-051 says why. |
| 2 | Build Brother's 4" × 6.75" multi-position hoop into the PE550D profile? Its three positions are taken as 36 mm apart (172 mm long, 100 mm sewn at each: (172 − 100) / 2). That number must be checked against the hoop's own sheet. | Yes, with "check against your hoop's sheet; unverified until stitched" in its notes and a stitch-out row | The feature ships with no built-in multi-position hoop. The manual shows the JSON to add one. |
| 3 | Puff: no automatic stop for laying the foam. The manual says to give puff shapes their own color (the machine stops at a color change) or to insert a stop. | As stated | As stated. |
| 4 | Add three samples to `samples/` (Lace ornament, Puff letter, Patch)? They appear under "Open a sample". | Yes | Added: done-when needs them. |
| 5 | May workers commit on `phase-08/*` branches? | Yes; the kickoff prompt says so | One track at a time in the working tree, nothing committed. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Seams are in | `git ls-files engine/threadline_engine/digitize/fills/__init__.py engine/threadline_engine/layout/passes.py apps/desktop/src/dialogs.tsx apps/desktop/src/design/shapes.ts scripts/check.py` | five paths |
| Satin has no puff or patch edge yet | `grep -n -e "puff" -e "merrow" engine/threadline_engine/digitize/stitches.py` | no match |
| Applique is as read | `grep -n -e "def applique" -e "def _border" -e "def _edges" -e "def rings" engine/threadline_engine/digitize/applique.py` | four matches |
| Split is as read | `grep -n -e "def plan" -e "def _grid" -e "def _cell_of" -e "def section_pattern" engine/threadline_engine/split.py` | four matches |
| Lattice helper | `git ls-files engine/threadline_engine/digitize/fills/lattice.py` | a path if Phase 7 was built (reuse it); nothing if not (Track A creates it, section 7) |
| Mesh is in, and how a text-valued setting is checked | `git ls-files engine/threadline_engine/digitize/fills/mesh.py` and `grep -n "weave" engine/threadline_engine/digitize/stitches.py` | the path; `weave` as a plain `FillParams` field checked in `from_dict` (do the same for the lattice choice) |
| Lettering's letter order | `grep -n -e "def _text_block" -e "def text_letters" engine/threadline_engine/layout/text.py` and `grep -rn '"letter"' engine/threadline_engine/lettering` | two matches for the first. A match for the second means Phase 5 is in and letter parts carry `letter` and `line`: P8-C3 orders by those |
| Presets exist? | `git ls-files engine/threadline_engine/presets.py` | if a path, integration adds two lace presets |
| Shortcuts still free | `grep -nF -e 'shortcut: "Alt+Shift+C"' -e 'shortcut: "Alt+Shift+Q"' -e 'shortcut: "Mod+Alt+U"' -e 'shortcut: "Mod+Alt+K"' -e 'shortcut: "Alt+Shift+K"' apps/desktop/src/actions.ts apps/desktop/src/cmd/*.ts` | no match |
| Baseline is green | `python scripts/check.py` | `RESULT: PASS`; write the counts into the session notes |

## 5. Architecture

### 5.1 Engine

```
engine/threadline_engine/
  digitize/fills/lattice.py   tile_segments, clip_segments, double_run_paths (shared with Phase 7's blackwork)
  digitize/fills/lace.py      NEW (A)
  digitize/puff.py            NEW (A): satin(pairs, params) for puff
  digitize/merrow.py          NEW (B): satin(pairs, params) for the patch edge
  digitize/patch.py           NEW (B): build(...) -> ordinary objects
  digitize/applique.py        (B) sections exposed; no_cover, cover_gaps, open_edges
  layout/appliques.py         NEW (B): prepared_items (cover gaps), the "applique_sets" pass
  quality_fsl.py              NEW (A): lace_checks(layout, rendered)
  split.py                    (C) plan(..., positions=None)
  profiles.py                 (C) hoops may carry positions
```

`satin_from_pairs` begins with a two-line hand-off, seeded in Step 0: `if params.puff: return puff.satin(pairs, params)` and `if params.merrow: return merrow.satin(pairs, params)`. Each track then works only in its own file.

### 5.2 Data model (`design/types.ts`, seeded in Step 0)

```ts
// FillPattern gains "lace"; FillParams gains
lace_mm?: number; lace_lattice?: "grid" | "diamonds" | "honeycomb";
// SatinParams
puff?: boolean; merrow?: boolean;
// AppliqueParams
cover_under?: "keep" | "skip";   // the border where a later shape covers the edge
no_cover?: boolean;              // placement and tack-down only (a patch's base)
open_edges?: number[];           // outline segments left unsewn; segment i runs from point i to point i + 1
// ObjectBase
applique_set?: string;           // appliques with the same id share their two stops
sew_last?: boolean;              // new shapes are added before it (a patch's edge)
// TextItem
sew_order?: "normal" | "center_out";
// Hoop
positions?: HoopPosition[];
export type HoopPosition = { id: string; name: string; x_mm: number; y_mm: number; width_mm: number; height_mm: number; rotate?: 0 | 180 };
// Fabric
freestanding?: boolean;
```

A hoop with positions, in a machine profile. `width_mm` and `height_mm` are the whole area the positions reach; each position gives its field's center, measured from the hoop's center, and its size:

```json
{ "id": "4x6.75-multi", "name": "4\" × 6.75\" multi-position (10 × 17.2 cm)", "width_mm": 100, "height_mm": 172,
  "positions": [
    { "id": "a", "name": "Top",    "x_mm": 0, "y_mm": -36, "width_mm": 100, "height_mm": 100 },
    { "id": "b", "name": "Middle", "x_mm": 0, "y_mm": 0,   "width_mm": 100, "height_mm": 100 },
    { "id": "c", "name": "Bottom", "x_mm": 0, "y_mm": 36,  "width_mm": 100, "height_mm": 100 } ] }
```

### 5.3 RPC methods

| Method | Parameters | Returns | Group file |
| --- | --- | --- | --- |
| `patch.build` (new) | `shape="circle", width_mm=60, height_mm=60, border_mm=3.5, base="fabric", outline=None` | `{objects, warnings}` | `shapes.py` |
| `layout.center_out` (new) | `layout, ids=None` | `{order, moved, texts}` | `layouts.py` |
| `applique.export_fcm` (new, only if decision 1 says build) | `layout, dest` | `{path, pieces}` | `layouts.py` |
| `layout.split_plan`, `layout.export_split` (changed) | `hoop` may carry `positions` | each section gains `name`; the result gains `positions: true` | `layouts.py` |
| `layout.check` (changed) | – | lace checks when the fabric is freestanding | `layouts.py` |

Applique sets, partial cover, open edges, puff and the patch edge need no method: they are fields on shapes.

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-08/specialty-in-the-hoop` from `main`.
2. `design/types.ts`: everything in 5.2.
3. `stitches.py`: `SatinParams` gains `puff: bool = False` and `merrow: bool = False`, read in `from_dict`; the hand-off at the top of `satin_from_pairs`; `digitize/puff.py` and `digitize/merrow.py` as stubs that raise `DigitizeError("not built yet")`.
4. `layout/appliques.py` as a stub (`prepared_items(layout)` returns `layout["items"]`; no pass registered), imported in `layout/__init__.py`, and called in `render()` just before the item loop.
5. Method stubs for `patch.build` and `layout.center_out` (and `applique.export_fcm` if decided), with their names in `rpc_methods.json`.
6. Eight feature flags in `project.py` with their detectors: `fill_lace`, `satin_puff`, `satin_merrow`, `applique_sets`, `applique_cover_skip`, `applique_no_cover`, `applique_open_edges`, `text_center_out`. Hoop positions live in machine profiles, not projects. `sew_last` only says where new shapes go (the saved order already says what sews when), so it needs none.
7. Commands with the reserved shortcuts, each calling a stub: `cmd/specialty.ts` (`tool.patch` Alt+Shift+C, `applique.fromSelection` Alt+Shift+Q, and `applique.fcm` Mod+Alt+U only if decided), `cmd/production.ts` (`file.printStickers` Mod+Alt+K, `layout.centerOut` Alt+Shift+K); stubs in `feat/patch.ts`, `feat/applique.ts`, `feat/stickers.ts`, `feat/centerOut.ts`; two import lines in `cmd/index.ts`.
8. Menu entries: Shapes menu "Make a patch…"; right-click menu "Make an applique from the selection"; the toolbar's More menu "Print positioning stickers…" under Print and "Sew from the center out (caps)" beside the shortest-order entry.
9. `ObjectPanel.tsx`: in the satin's Advanced fold two ticks that exclude each other, "3D puff (over foam)" and "Patch edge (faux merrow)", writing `puff` and `merrow`; inside the applique block `<AppliqueExtras item={item} />` (an empty component in its own file).
10. `python scripts/kb_commands.py`, `python scripts/check.py`, commit ("Phase 8: start"). Workers branch from this commit.

## 7. Tracks

All three run together. Every worker follows "Worker rules" in `BUILDPLAN.md`. Every number below that shapes a stitch is a named constant at the top of its module, so a stitch-out can change it in one place.

### Track A: lace and puff

**Owns:** `digitize/fills/lace.py`, `digitize/fills/lattice.py` (only if it does not exist), one import line in `fills/__init__.py`, `digitize/puff.py`, in `stitches.py` only `satin()`, `satin_ribbon()` and the lace lattice field in `FillParams`, `fabrics.py`, `quality.py`, `quality_fsl.py`, the `check` function in `layout/render.py`, the lace entry in `design/fillPatterns.ts`, `ObjectPanel.tsx` apart from the Step 0 lines, new tests and snapshot suites.

#### P8-A1 Lace fill (`lace`, open pattern)

A lattice of lines, each sewn twice, with a needle point at every crossing so the threads lock each other. Phase 6's mesh fill is the look on fabric; lace is the version that holds with no fabric under it. `grid` and `diamonds` are mesh's two sets of lines (reuse the line builder in `fills/mesh.py` where it fits), walked differently.

- Settings: `lace_mm` Cell size 3 (1.5 to 8, step 0.5); lattice `grid` (default), `diamonds` (the grid turned 45°) or `honeycomb` (hexagons `lace_mm` across the flats). Stitch length is the shape's, capped at 2.5 mm.
- `lattice.py` (create it to this contract if preflight found none): `tile_segments(kind, cell_mm, bounds)`; `clip_segments(segments, poly)`, pieces under 0.8 mm dropped; `double_run_paths(segments, stitch_mm, start)`, which makes a graph with a node at every crossing and end and walks each connected piece depth-first, out along an edge and back, so every segment is sewn exactly twice and each path ends where it began.
- Lines are clipped to the shape grown by 0.3 mm, so every line end reaches just past the outline and a border catches it.
- On automatic underlay it has an edge run, sewn first (`auto_underlay=lambda level: ["edge"]`).
- `step_mm2 = lace_mm × stitch / 4`. Descriptor flags: `open`, `noSpacing`, `maxStitch: 2.5`. Hint: "For freestanding lace, set Stitching on to Wash-away stabilizer and add a satin border (Shift+B)."
- Cells under 2 mm warn: "Cells this small sew stiff, more like a fill than lace." A shape that holds fewer than two whole cells is refused: "This shape is too small for … mm lace cells; make the cells smaller."

#### P8-A2 The wash-away fabric choice and the lace checks

`fabrics.FABRICS` gains: id `fsl`, name "Wash-away stabilizer only (freestanding lace)", examples "Ornaments, bookmarks, lace edging", density 1.0, `pull_comp_mm` 0.1, underlay `heavy`, stabilizer "Two layers of fibrous wash-away stabilizer, hooped drum-tight (not the clear film kind)", no topping, `freestanding: True`.

When the layout's fabric is freestanding, `layout.check` adds `quality_fsl.lace_checks(layout, rendered)`:

| Code | Level | Test | Words |
| --- | --- | --- | --- |
| `fsl_pieces` | warning | Draw every stitch 0.4 mm wide on a 0.25 mm grid; count connected pieces of 4 mm² or more (`cv2.connectedComponents`, 8-way). More than one fails. `at`: the middle of the smallest piece. | "This lace would come apart into N pieces." Why: once the stabilizer washes away, only thread holds the design together. Fix: overlap the loose part with the rest, or add a line or border that touches both. |
| `fsl_border` | warning | For each lace fill, sample its outline every 1 mm. A sample is held when it is within half a satin's width plus 0.5 mm of that satin's center line, or within 0.6 mm of a line sewn more than once (triple, bean, and backstitch or redwork if Phase 7 is in). Under 90% held fails. `at`: the middle of the longest bare stretch. | "The lace's edge has no border for about N mm." Why: without a border the lattice frays at the edge. Fix: select the lace and press Shift+B, 2.5 mm or wider. |
| `fsl_single_run` | info | A running-stitch line with style Single. | "A single line of stitching won't hold on its own in lace." Fix: use Triple. |

#### P8-A3 3D puff satin (`digitize/puff.py`)

A satin with `puff: true` is sewn to cover and cut craft foam.

| Part | Rule |
| --- | --- |
| Density | spacing = the satin's spacing × 0.5, kept between 0.15 and 0.25 mm |
| Underlay | none, whatever the setting or the fabric (underlay flattens foam) |
| First | a run 0.4 mm inside both edges, down one side and back up the other: it holds the foam |
| Caps | at each open end, before the top stitching: stitches that run along the column, from the end edge to 1.5 mm in, stepping 0.25 mm across the width (0.2 mm in from each side). Their needle holes along the end edge cut the foam. A closed ring has none. |
| Top | the satin, edge pad 1.5 × the usual amount; `split_mm` ignored (a split stitch presses the foam down) |
| Start and end dots | ignored: it sews end to end (`satin()` and `satin_ribbon()` skip `satin_with_ends` for puff) |
| Width | under 2.5 mm warns "under 2.5 mm the foam shows at the sides: widen it or turn Puff off"; over 10 mm warns "over 10 mm the stitches lie loose over the foam" |

`quality.check` gains `relaxed_long: set[int] | None`: items whose stitches may be up to 10.5 mm before the long-stitch check speaks. `layout.check` passes the puff items. In the panel, a puff satin shows "Underlay: none for puff" and hides Split long stitches.

#### Track A tests

| Test (file) | Asserts |
| --- | --- |
| `test_lace_is_open_with_three_lattices`, `test_grid_lines_are_a_cell_apart`, `test_every_line_is_sewn_twice`, `test_a_square_is_one_piece_with_no_jumps`, `test_needle_point_at_every_crossing`, `test_lines_reach_the_outline`, `test_edge_run_first_on_automatic` (`test_fill_lace.py`) | |
| `test_cell_size_is_checked`, `test_small_cells_warn`, `test_a_shape_too_small_is_refused` | `Cell size must be between 1.5 and 8 mm` |
| lace invariants and snapshots | suite `fills_lace`: `grid_40`, `diamonds_40`, `honeycomb_40`, `grid_donut` |
| `test_checks_run_only_on_the_freestanding_fabric`, `test_lace_with_a_border_passes`, `test_two_separate_motifs_are_two_pieces`, `test_a_joining_line_makes_one_piece`, `test_a_missing_border_is_reported_with_its_length`, `test_a_single_run_gets_a_note`, `test_the_fabric_is_listed_with_its_stabilizer` (`test_quality_fsl.py`) | |
| `test_puff_has_no_underlay`, `test_puff_is_twice_as_dense`, `test_open_ends_are_capped_before_the_top_stitching`, `test_a_closed_ring_has_no_caps`, `test_split_and_chosen_ends_are_ignored`, `test_narrow_and_wide_puff_warn`, `test_puff_does_not_trip_the_long_stitch_check` (`test_satin_puff.py`) | |
| puff invariants (`max_stitch_mm=10.5`) and snapshots | suite `satin_puff`: `ribbon_4mm`, `ring_5mm`, `column_tapered` |
| `test_projects_name_the_features` | `fill_lace`, `satin_puff` |
| `Lace shows Cell size and the lattice choice`; `Puff hides Split long stitches and shows no underlay` (`design/fillPatterns.test.ts`, `ObjectPanel.dom.test.tsx`) | |

### Track B: applique and patches

**Owns:** `digitize/applique.py`, `digitize/merrow.py`, `digitize/patch.py`, `layout/appliques.py`, the `patch.build` stub, `feat/applique.ts`, `feat/patch.ts`, `components/AppliqueExtras.tsx`, `components/PatchDialog.tsx`, `canvas/openEdgesTool.ts`, `cmd/specialty.ts`, `addObject` in `design/layout.ts`, `insertNode` and `deleteNode` in `actions.ts` (for P8-B3 only), `cutfile.py` (only if decided), new tests.

First, with no change in output: `applique()` is split into `sections(outline, params, holes) -> (placement, tack, cover, warnings)` and `join_parts(out, parts, stop_after)` (today's inner `section`). The two applique snapshots must not move.

#### P8-B1 Applique sets (`applique.fromSelection`, Alt+Shift+Q)

Several pieces cut from one fabric should stop the machine twice, not twice each.

- **Command.** Each selected closed shape (fill, applique, closed line) becomes an applique by today's conversion; they get one new `applique_set` id and are moved next to each other in the sewing order, at the place of the first, in one undo step. Anything else in the selection is named in a message and left alone. One closed shape alone simply becomes an applique.
- **Pass** `applique_sets` (`after_items`). For each run of appliques next to each other with the same set id and thread: split each one's stitches at its stops into placement, tack-down and cover (a member with placement off has no first part), then write all placements, one stop, all tack-downs, one stop, all covers. Moves between members follow `join_parts`. Stitches keep their item and source numbers, so a stop or trim the user inserted stays on its stitch.
- A set of one is an ordinary applique. Members apart in the order, or in different threads, sew on their own with a note. The cut file lists every member, as now.

#### P8-B2 Partial cover (`cover_under: "skip"`)

Where a later shape covers part of an applique's edge, a second satin underneath only makes a ridge.

- `appliques.prepared_items(layout)` gives each such applique a derived `cover_gaps` (never saved): for each edge, the stretches (in mm along it) that lie inside a later area shape shrunk by 0.5 mm. Later means sewn after it; area shapes are appliques, fills, and satins by their outline.
- `_border` builds its pairs for the whole edge, then sews only the stretches outside the gaps. Each cut end reaches 1 mm under the covering shape and is locked; moves between stretches use `travel`.
- Placement and tack-down stay whole: the fabric must still be held.
- `AppliqueExtras`: "Where a later shape covers the edge" with "Sew the border anyway" (default) and "Leave the border out there".

#### P8-B3 Open edges by hand (cut this first if the track runs long)

`open_edges` lists outline segments that get no placement, tack-down or cover: an edge that runs into a seam or off the piece. `sections` maps segment numbers to stretches of the flattened edge with the point indexes `flatten` returns. `applique.fromSelection` on an open line closes it with a straight segment and marks that segment open. In `AppliqueExtras`, "Choose open edges" turns on a canvas tool (`registerCanvasTool`): a click on an outline segment toggles it; an overlay draws open segments dashed. `insertNode` and `deleteNode` renumber the list (a split open segment stays open on both halves). The cut file keeps the whole outline. If cut: L-050 says edges are left out only automatically (P8-B2).

#### P8-B4 Patch edge: faux merrow (`digitize/merrow.py`)

A satin with `merrow: true`, 2.5 to 6 mm wide, sewn to look like an overlocked edge:

1. Underlay, always: a run 0.4 mm inside each edge, then a zigzag.
2. Top: spacing = the smaller of the satin's spacing and 0.32 mm. Each stitch slants: from point `i` on the outer edge to point `i + k` on the inner edge, `k = round(0.25 × width / spacing)`; on a closed ring the count wraps, on an open ribbon it stops at the ends. Edge pad at least 0.3 mm.
3. Bead: last, a line 0.3 mm inside the outer edge, 2 mm stitches each sewn three times.

The outer edge is the longer one on a closed ring, and side A on an open ribbon. A ring starts where its green dot is, as now.

#### P8-B5 Make a patch (`tool.patch`, Alt+Shift+C)

`patch.build` returns ordinary shapes; the app adds them in one undo step.

| Base | Shapes, in sewing order |
| --- | --- |
| Fabric | "Patch base": an applique with `no_cover` (placement, stop, tack-down, stop: trim the fabric there, or lay a piece pre-cut from the cut file). "Patch edge": a closed satin ribbon on the same outline, `border_mm` wide, `merrow`, `sew_last`. |
| Thread | "Patch background": a tatami fill of the outline shrunk by 0.5 mm. "Patch edge" as above. No stops. |

Shapes: circle, oval, rectangle, rounded rectangle (from `design/shapes.ts`), shield, or the selected closed shape's own outline. Width and height 20 to 120 mm; border 2.5 to 6 mm, default 3.5. `addObject` puts new shapes before any `sew_last` shapes at the end of the order, so whatever is drawn on the patch later still sews before its edge. Dialog `patch` through `registerDialog`: shape, size (it warns when the patch will not fit the hoop with 3 mm to spare), border, base, the note "Sew on wash-away or tear-away stabilizer. The edge is sewn last.", Add. The fabric base's cut file is today's Save applique cut file.

#### P8-B6 FCM cut file (only if decision 1 says build)

One hour: find a written description of the format and a reference writer under a GPL-compatible license. Found: `cutfile.write_fcm(rings_mm, dest)`, `applique.export_fcm`, the `applique.fcm` command, a structural test, and a stitch-out row asking the owner to open the file in CanvasWorkspace. Not found: stop, register nothing, write L-051.

#### Track B tests

| Test (file) | Asserts |
| --- | --- |
| `test_one_applique_is_unchanged` (`test_applique_sets.py`) | `join_parts` over `sections` equals the old output; old snapshots untouched |
| `test_three_in_a_set_stop_twice`, `test_a_member_without_placement_adds_none`, `test_members_apart_or_in_other_threads_sew_alone_with_a_note`, `test_an_inserted_stop_stays_on_its_stitch`, `test_the_cut_file_has_every_member` | suite `applique_sets`: `three_hearts` |
| `test_cover_is_whole_by_default`, `test_cover_skips_what_a_later_fill_covers`, `test_tack_down_stays_whole`, `test_an_earlier_shape_does_not_count`, `test_cut_ends_are_locked_and_tucked_under` (`test_applique_cover.py`) | suite `applique_cover`: `two_overlapping`, `ring_under_a_fill` |
| `test_an_open_segment_gets_no_stitches`, `test_an_open_line_is_closed_with_an_open_edge`, `test_the_cut_file_keeps_the_whole_outline` (`test_applique_open_edges.py`, with P8-B3) | |
| `test_underlay_comes_first`, `test_top_stitches_slant`, `test_the_bead_runs_last_along_the_outer_edge`, `test_a_ring_closes_without_a_gap`, `test_width_is_checked` (`test_merrow.py`) | invariants; suite `satin_merrow`: `ring_60`, `open_ribbon` |
| `test_a_fabric_patch_is_a_base_and_an_edge`, `test_the_base_stops_twice_and_has_no_cover`, `test_a_thread_patch_is_a_fill_and_an_edge_with_no_stops`, `test_the_edge_covers_the_tack_down`, `test_shapes_and_sizes_are_checked` (`test_patch.py`) | suite `patch`: `round_60_fabric`, `shield_thread` |
| `the selection becomes one set, next to each other, in one undo step`; `a patch is added with its edge last`; `new shapes go in before the patch edge`; `inserting a point keeps an open edge open on both halves` (`feat/applique.test.ts`, `feat/patch.test.ts`, `design/layout.test.ts`); `test_projects_name_the_features` | the five flags of this track |

### Track C: hoops and production

**Owns:** `profiles.py`, `schemas/machine.schema.json`, `split.py`, `layout/export.py`, `layout/order.py`, the letter order in `layout/text.py`, the `layout.center_out` stub, `apps/desktop/src/print.ts`, `feat/stickers.ts`, `components/StickersDialog.tsx`, `feat/centerOut.ts`, `canvas/hoopPositions.ts`, `components/ExportDialog.tsx`, the Basting box row in `components/InfoPanel.tsx`, the "Letters sew" control in `components/TextPanel.tsx`, `cmd/production.ts`, new tests.

#### P8-C1 Hoops with positions

A multi-position hoop is moved on the machine between fixed positions without re-hooping the fabric, so the design is split at known offsets and needs no alignment crosses.

- `profiles._validate`: `positions` is a list of two or more entries with numeric `x_mm`, `y_mm`, `width_mm`, `height_mm`, `rotate` 0 or 180 (default 0), each field inside the hoop's whole area. Errors in the same plain style as the others. The schema gains the same.
- `split.plan(pattern, hoop_w, hoop_h, overlap, positions=None)`: with positions, each section's window is that position's field (less `SAFETY_MM` on each side), placed from the hoop's center at (0, 0); a stitch belongs to the position whose center is nearest. Cutting at seams, sewing a crossing run whole when it fits a window and keeps the layering, and the stop handling are today's code, with `_cell_of` replaced by "nearest position". No alignment marks. A position with nothing to sew is left out. A position with `rotate: 180` has its section turned half a turn about its window's center when written.
- Stitching outside every field is refused: "Part of the design is outside the hoop's positions. Move it or make it smaller."
- `export_split` names files by position: "name (Top).pes". The summary's sections carry `name`.
- Save for machine: with such a hoop chosen and a design too big for one field, the dialog says "This hoop sews in 3 positions. LUDD saves one file for each: attach the hoop at Top for the first…" and lists the files. An overlay (`registerOverlay`) outlines the fields on the hoop.
- Built in only by decision 2.

#### P8-C2 Positioning stickers (`file.printStickers`, Mod+Alt+K)

For a machine with no camera: print, stick, and hoop so the needle sits on the cross.

- `print.ts` gains `stickersSvg(labels, sizeMm)` (a sheet of circles 15, 20 or 25 mm across, each with a cross, an arrow for "up" and its number) and `positioningHtml(d, hoop, plan, opts)`: the 1:1 template with every hooping's center marked and numbered; a table giving each hooping's center measured from the first ("Hooping 2: 64.0 mm right, 0.0 mm down"); the sticker sheet; the 1 inch and 25 mm check bars. Colors go through `safeColor`, text through `esc`.
- Dialog `stickers`: "This design" or "Each hooping" (asks `layout.split_plan` when the design is bigger than the hoop or the hoop has positions), sticker size, Print.

#### P8-C3 Sew from the center out (`layout.centerOut`, Alt+Shift+K)

On caps, and anything that shifts in the hoop, sewing from the middle outward keeps the fabric from being pushed into a pucker.

- **Items** (`order.center_out_order`). Within each run of same-thread items next to each other, nearest the design's vertical center line first, lower first on a tie. An item never moves ahead of an earlier item it overlaps (the rule `optimize_order` uses). Color order is never changed.
- **Lettering** (`sew_order: "center_out"`). The letters' sewing order becomes: from the middle letter to the last, then from the one before the middle back to the first. With `count` letters and `mid = ceil((count − 1) / 2)`: `mid … count − 1`, then `mid − 1 … 0`. With Phase 5 in, "letter" is the `letter` tag (a letter's parts stay together) and each `line` is ordered on its own, top line first; without it, each part counts as a letter. Each part keeps its own number, so chosen start and end dots stay on their letters. The move back to the middle is one trimmed jump.
- **Command.** Applies the item order and sets `sew_order` on the selected texts, or on every text when none is selected, in one undo step, and says what moved. The Lettering panel gains "Letters sew: Left to right / From the middle out".

#### P8-C4 Basting box margin

The Basting box row in Order & colors gains "Margin", 2 to 20 mm (default 5), writing `layout.basting.margin_mm`. The engine clamps to that range and still brings the box in to fit the hoop.

#### Track C tests

| Test (file) | Asserts |
| --- | --- |
| `test_three_positions_make_three_files_named_by_position`, `test_windows_are_the_profile_positions`, `test_every_stitch_falls_in_its_window`, `test_an_empty_position_is_left_out`, `test_no_alignment_crosses`, `test_a_turned_position_is_turned_half_a_turn`, `test_a_crossing_run_is_sewn_whole_when_it_fits`, `test_layering_is_kept_across_positions`, `test_a_design_outside_every_field_is_refused`, `test_free_splitting_is_unchanged` (`test_split_positions.py`) | the existing split tests pass untouched |
| `test_positions_are_validated`, `test_the_schema_accepts_the_built_in_profiles` (`test_profiles.py`) | |
| `stickers are the size asked, in millimeters`; `each hooping's distance from the first is listed`; `the check bars are on the sheet`; `labels and colors are made safe` (`print.test.ts`) | |
| `test_items_in_one_thread_go_nearest_the_middle_first`, `test_overlapping_items_keep_their_order`, `test_thread_runs_are_not_mixed`, `test_lettering_sews_its_middle_letter_first`, `test_letter_numbers_are_unchanged`, `test_normal_order_is_untouched` (`test_center_out.py`) | suite `center_out`: `five_letters`, `three_motifs`; flag `text_center_out` |
| `test_basting_margin_is_clamped` (`test_layout.py`); `the Basting box row has a Margin field` (`InfoPanel.dom.test.tsx`) | |

## 8. Integration (session lead)

1. Merge in the order C, B, A. Run `python scripts/check.py` after each.
2. Samples (decision 4): add "Lace ornament" (a 60 mm circle in honeycomb lace, a 3 mm satin border and a small hanging ring, on the wash-away fabric), "Puff letter" (an "L" from two puff satins in their own color) and "Patch" (a 60 mm round fabric patch with a star) to `scripts/make_samples.py`; run it; the golden test picks them up.
3. If `presets.py` exists: two built-in presets, "Lace, 3 mm grid" and "Lace, 2 mm honeycomb".
4. `python scripts/kb_commands.py`. `pnpm build:engine` once: its smoke check must pass.
5. Write the docs (section 9). `python scripts/check.py --all`. Then the stop contract in `BUILDPLAN.md`.

Expected conflicts: none. `stitches.py` is Track A's after Step 0, `applique.py` Track B's, `split.py` Track C's.

## 9. Docs payload

**`docs/CHANGELOG.md`**, under the current unreleased heading:

```
### Phase 8: lace, puff, patches, applique sets, hoops with positions (YYYY-MM-DD)
- **Lace fill**: a lattice of doubled lines (grid, diamonds or honeycomb). Choose "Wash-away stabilizer only" under Stitching on and LUDD checks that the lace will hold together: no loose pieces, a border all round.
- **3D puff**: tick it on a satin to sew over craft foam: twice as dense, no underlay, ends capped so the foam tears away cleanly.
- **Patches**: Make a patch (Alt+Shift+C) adds a base and an overlock-style edge that always sews last. Fabric or all-thread base.
- **Applique**: several shapes can be one applique set (Alt+Shift+Q) with two stops in all. The border can be left out where a later shape covers it. Edges can be left open.
- **Hoops with positions**: a design too long for one field is saved as one file per position, with no alignment crosses.
- **Positioning stickers** (Ctrl+Alt+K): print crosshair stickers and a sheet showing where each hooping's center goes.
- **Sew from the center out** (Alt+Shift+K) for caps: shapes and letters sew from the middle outward.
- The basting box has a Margin setting.
```

**`docs/LUDD-KNOWLEDGE-BASE.md`** (new section 27, Specialty, for the `F-22xx` entries)

| ID | Entry |
| --- | --- |
| F-2201 | Freestanding lace: the Lace pattern, the wash-away fabric choice, the three checks and their fixes |
| F-2202 | 3D puff: what changes, widths, when to lay the foam (own color or an inserted stop) |
| F-2203 | Patches: the dialog, fabric or thread base, the faux-merrow edge, why the edge sews last |
| F-1502 | Applique sets, leaving the border out under later shapes, open edges (update F-1501) |
| F-1503 | FCM cut file: only if P8-B6 was built; otherwise not added |
| F-304 | Hoops with positions: how files are named, where to attach the hoop, adding one as JSON |
| F-210 | Positioning stickers |
| F-1809 | Center-out order for shapes and letters |
| F-1801, F-1701, F-1702, F-1305 | updated: Margin; the new fabric choice; the three check codes; Lace |
| L-009 | now PARTIAL: lace and puff YES (F-2201, F-2202); sequins and chenille stay out; cutwork is Phase 13 |
| L-050 | Applique edges can't be opened by hand (only if P8-B3 was cut) |
| L-051 | No FCM cut files; CanvasWorkspace imports the SVG (unless P8-B6 was built) |
| L-052 | Puff has no automatic stop for laying foam |
| L-053 | The built-in multi-position hoop is unverified until stitched; turned positions are untested |
| L-054 | Center-out keeps your color order: it reorders only within a color |
| T-039 | "My lace fell apart in the wash": the checks, the border, the fibrous stabilizer |
| T-040 | "Foam shows at the sides or pokes through": width, foam color, density, caps |
| T-041 | "The patch edge doesn't cover the fabric": trim closer or pre-cut from the cut file; widen the edge |
| T-042 | "The second position doesn't line up": attach at the named position, don't re-hoop, check the profile's offsets |

Section 2 index rows for each new F- entry; the "3D puff, sequins, chenille, cutwork?" row is split. Section 23 history row; *Last updated*; section 25 by the script.

**`docs/USER-MANUAL.md`**: section 8 (applique sets, partial cover, patches), 6 (Lace, puff, patch edge), 10 (the wash-away choice and lace checks), 2 (hoops with positions, stickers, new samples), 5 (center-out), 7 (Letters sew). **`ai/helpdocs.py`**: the same, with the new shortcuts.

**`docs/stitchout-log.md`**, rows for "Pending machine tests":

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 8 | **Freestanding lace** | The Lace ornament sample on two layers of fibrous wash-away; rinse it out | Stays in one piece; lattice even; the border doesn't part from the lace |
| Phase 8 | **3D puff** | A 6 mm puff bar and the Puff letter sample over 3 mm craft foam | Foam fully covered; ends cut clean by the caps; the spare foam tears away; not flattened |
| Phase 8 | **Patch, fabric base** | The Patch sample on twill, the piece pre-cut from the SVG | The edge covers the fabric all round and looks overlocked; the bead sits on the outside; no gap where the edge closes |
| Phase 8 | **Patch, thread base** | A 50 mm shield patch on wash-away | Lies flat; edge and background meet with no fabric showing |
| Phase 8 | **Applique set** | Three hearts as one set | Two stops in all; every piece placed, tacked and covered |
| Phase 8 | **Border left out under a later shape** | Two overlapping appliques, the lower one set to leave its border out | No double ridge where they overlap; the lower piece's edge is still held |
| Phase 8 | **Hoop with positions** | A 100 × 170 mm design in the 4" × 6.75" hoop | The parts meet with no gap or step when the hoop is moved between positions |
| Phase 8 | **Positioning stickers** | Print at 100%, stick sticker 1 on the fabric, hoop to it | The bars measure right; the needle lands on the cross |
| Phase 8 | **Center out** | A five-letter word and three motifs with Sew from the center out | Sews from the middle outward; no pucker in the middle |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| The lace checks cry wolf, or miss a loose piece | `test_quality_fsl.py` cases disagree with the drawing | They are warnings and never block saving. Tune the grid (0.25 mm) and the 0.4 mm thread width, not the wording. |
| Puff and patch-edge numbers are untested on thread | only a stitch-out can tell | Every number is a named constant at the top of `puff.py` and `merrow.py`. |
| The 36 mm position offset is wrong for the real hoop | the stitch-out row | Decision 2; the profile is plain JSON a user can correct. |
| The set pass moves a stop the user inserted | `test_an_inserted_stop_stays_on_its_stitch` fails | Split blocks at their stops; never regenerate the members. |
| Open edges lose their place when points are added | the layout test fails | Cut P8-B3 and write L-050. |
| The seeded hand-off in `satin_from_pairs` is missed | both tracks edit `stitches.py` | Step 0 item 3 is not optional; without it the tracks cannot run together. |
| Three tracks are too much for one session | context or time runs out | Tracks are independent. Merge what is green and list the rest in `HANDOFF.md`. |

## 11. Handoff

Write in `HANDOFF.md`: test counts before and after; how each of the five decisions was applied; whether P8-B3 and P8-B6 were built; whether `lattice.py` was created here or reused; that the lace checks, puff, the patch edge and the position offsets are unproven until Phase 15; that the open-edges tool, the stickers print and the position overlay were not tried by hand (unless they were); any spec deviation, one line each.
