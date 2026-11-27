# Phase 7: Lines, sequencing & drawing tools

| | |
| --- | --- |
| Weight | Heavy. Do it on the larger plan. |
| Session lead | Sonnet 5.5. **Track B is hard: give its worker the stronger model.** |
| Audit | Standard phase gate. Ask the top model to read Track B's diff if its worker raised a spec question. |
| Depends on | Phase 3 (seams) and Phase 6 (motif library, push compensation, fills that sew in two threads) |
| Changes stitches | Only new line styles, lock-stitch shapes, blackwork, and shapes put in a branch. Everything saved before sews as before. |
| Closes (compendium) | Craft stitches · Buttonholes and eyelets · Branching ★ · Freehand drawing · Continue digitizing · Mirror-merge, wreath, kaleidoscope · Presets you save and reuse · Import SVG / DXF / PDF ★ |

## 1. Goal and done-when

Four things hobbyists pay for at the top level of other programs: hand-embroidery line looks, sewing a group of shapes as one unbroken path (StitchArtist Level 3, $699), drawing by hand instead of click by click, and bringing vector artwork in.

**Done when:**

1. `python scripts/check.py --all` prints `RESULT: PASS`, no snapshot recorded before this phase has changed, and `pnpm build:engine` passes its smoke check with the new dependencies (the handoff says how much bigger the frozen engine is).
2. Each new line style, the blackwork fill and each lock-stitch shape has a snapshot suite and passes the invariants.
3. Three touching same-thread shapes put in a branch sew with no trim and no jump between them, from one start to one end.
4. A freehand stroke of 300 pointer samples becomes 25 curve points or fewer, all within 0.4 mm of the stroke.
5. An SVG holding a filled path, a thin stroke and a 3 mm stroke imports as a fill, a line and a 3 mm satin ribbon at the file's real size, and nothing is added before Add is pressed.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P7-S1 | Branch, baseline check, shared-file seeds, command stubs | No | Step 0 |
| P7-A1 | Line styles: backstitch, stem stitch, candlewicking, redwork, French knots | Yes | A |
| P7-A2 | Blackwork fill (a lattice of double runs) | Yes | A |
| P7-A3 | Which side a motif line sits on | Yes | A |
| P7-A4 | Lock-stitch shapes: standard, triangle, back-tack | Yes | A |
| P7-A5 | Buttonholes and eyelets (added as ordinary grouped shapes) | Yes | A |
| P7-B1 | Branch: sew selected shapes as one path, with one start and one end | Yes | B |
| P7-B2 | Branch dots, the Branch and Take out commands, the panel note | Yes | B |
| P7-B3 | Optimize jumps also moves an applique's start and a text's first letter (L-017, part) | Yes | B |
| P7-C1 | Freehand drawing with smoothing | Yes | C |
| P7-C2 | Continue a line or satin ribbon from either end | Yes | C |
| P7-C3 | Repeat dialog: Mirror, Wreath round the hoop center, Kaleidoscope, live outlines | Yes | C |
| P7-C4 | Stitch presets: save, apply, import, export | Yes | C |
| P7-D1 | Import SVG and DXF artwork as editable shapes, previewed first | Yes | D |
| P7-D2 | PDF: a time-boxed attempt at vector paths, else the page as a picture | Yes | D |
| P7-Z1 | Docs, notices, frozen-engine smoke check, handoff | – | Integration |

**Out of scope:** converting stitches back to shapes, chain stitch, string stitch, shadow work (Phase 13); custom motifs (built in Phase 6); branching lettering, appliques or stitch files; pen pressure; SVG text, gradients and clipping; snapping to shapes (Phase 11).

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Add two engine dependencies for artwork import: `svgelements` (MIT, pure Python, by the author of pyembroidery) and `ezdxf` (MIT; it needs `pyparsing`, MIT, plus numpy and fonttools, already bundled)? Both licenses are GPL-compatible. | Yes | SVG is read by a small parser written here (paths, basic shapes, transforms, units; no CSS classes, no `<use>`). DXF is not built; L-047 says so. |
| 2 | Add `pypdfium2` for PDF (Apache-2.0 / BSD-3-Clause, both GPL-3-compatible; bundles the PDFium library, about 6 MB per installer)? | Yes, with the 90-minute attempt in P7-D2 | No PDF library. Choosing a PDF says how to save it as SVG or add a screenshot as a picture. |
| 3 | In a branch, LUDD chooses each shape's start and end and the order of shapes that don't overlap, and the Branch command moves the shapes next to each other in the sewing order. OK? | Yes: that is the feature | Built as described. |
| 4 | Ship five built-in presets (Light sketch fill, Bold outline, Redwork line, Narrow satin border, Felt applique)? | Yes | Shipped. |
| 5 | May workers commit on `phase-07/*` branches? | Yes; the kickoff prompt says so | One track at a time in the working tree, nothing committed. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Seams are in | `git ls-files engine/threadline_engine/digitize/lines/__init__.py engine/threadline_engine/layout/passes.py apps/desktop/src/canvas/hooks.ts scripts/check.py` | four paths |
| Phase 6 is in | `cd engine && uv run python -c "from threadline_engine.digitize import fills; print(sorted(fills.REGISTRY))"` | includes the motif fill (read PHASE-06's Handoff for its name) |
| How a text-valued setting is checked | `grep -n "weave" engine/threadline_engine/digitize/stitches.py` | Phase 6's `weave` as a plain field on `FillParams`, checked in `from_dict`. Follow whatever is there (section 5.1) |
| Jump helpers still there | `grep -n -e "def _variants" -e "def _ends" -e "def _shape_of" -e "def _reversed_path" engine/threadline_engine/jumps.py` | four matches |
| Shortcuts still free | `grep -nF -e 'shortcut: "Y"' -e 'shortcut: "Alt+Shift+B"' -e 'shortcut: "Alt+Shift+U"' -e 'shortcut: "Alt+P"' -e 'shortcut: "Mod+Alt+I"' -e 'shortcut: "Alt+B"' -e 'shortcut: "Alt+E"' apps/desktop/src/actions.ts apps/desktop/src/cmd/*.ts` | no match |
| Dependencies not there yet | `grep -n -e "svgelements" -e "ezdxf" -e "pypdfium2" engine/pyproject.toml` | no match |
| Baseline is green | `python scripts/check.py` | `RESULT: PASS`; write the counts into the session notes |

## 5. Architecture

### 5.1 Engine

New modules, each owned by one track: `digitize/lines/craft.py`, `digitize/fills/lattice.py`, `digitize/fills/blackwork.py`, `digitize/ties.py`, `digitize/smallobjects.py` (A); `layout/branch.py` (B); `presets.py` and `methods/presets.py` (C); `artimport/` (`svg.py`, `dxf.py`, `pdf.py`, `convert.py`) and `methods/art.py` (D). `lattice.py` is shared with Phase 8's lace: if Phase 8 was built first it exists already, to the same contract.

`LineStyle` gains one optional field, `recs` (`(nodes, params, closed, start) -> list[Rec]`), for a style that needs jumps (French knots). When set, `running()` uses it instead of `points` plus `stitch_run`.

Text-valued settings (`motif_side`, `tie_style`, the blackwork lattice): Phase 6 keeps its own (`weave`, `motif`) as plain fields on the params dataclasses, checked in `from_dict` with a plain-words error. Do the same. Only if Phase 6 was built another way, follow that instead.

### 5.2 Data model (`design/types.ts`, seeded in Step 0)

```ts
// RunParams
style?: "single" | "triple" | "bean" | "motif" | "backstitch" | "stem" | "candlewick" | "redwork" | "knots";
motif_side?: "center" | "left" | "right"; stem_width_mm?: number; knot_mm?: number; knot_gap_mm?: number;
tie_style?: "standard" | "triangle" | "backtack";   // also on SatinParams and FillParams
// FillPattern gains "blackwork"; FillParams gains
blackwork_mm?: number; blackwork_lattice?: "diamonds" | "grid" | "honeycomb" | "crossed";
branch?: string;             // ObjectBase: shapes with the same id are sewn as one path
branches?: Record<string, { start_mm?: [number, number]; end_mm?: [number, number] }>;   // Layout: dots set by hand, mm on the hoop
branches?: BranchInfo[];     // Design (layouts only): each branch as sewn
export type BranchInfo = { id: string; items: string[]; start: [number, number]; end: [number, number]; hidden_mm: number; cuts: number };
```

`RepeatSpec` (Track C, in `design/layout.ts`): `circle` gains `center?: "below" | "hoop"` and `mirror?: boolean`; new `{ kind: "mirror2"; axis: "x" | "y"; gap: number }`.

A preset file (`.luddpreset`): `{ "format": "ludd-preset", "version": 1, "name", "kind": "run" | "satin" | "fill" | "applique", "params": {…}, "width_mm"?: number, "note"?: string }`.

### 5.3 RPC methods (stubs and manifest names seeded in Step 0)

| Method | Parameters | Returns | Group file |
| --- | --- | --- | --- |
| `shape.buttonhole` | `length_mm=16, width_mm=5, style="bar", cut_gap_mm=1.0, angle_deg=0, at=[0,0]` | `{objects, warnings}` | `shapes.py` |
| `shape.eyelet` | `hole_mm=4, ring_mm=1.6, at=[0,0]` | `{objects, warnings}` | `shapes.py` |
| `layout.branch_plan` | `layout, ids` | `{ok, reason, order}` (`order`: every item id, members moved together) | `layouts.py` |
| `presets.list` | – | `[{id, name, kind, params, width_mm, note, builtin}]` | `presets.py` |
| `presets.save` | `preset, replace=False` | `{id}` | `presets.py` |
| `presets.delete`, `presets.export`, `presets.import` | `id` · `id, dest` · `path` | – · `{path}` · `{id, name, kind}` | `presets.py` |
| `art.preview` (background) | `path, options` | `{size_mm, scale_note, shapes, skipped, warnings}` | `art.py` |

`art.preview` options: `width_mm` (null = the file's real size), `strokes` (`"auto"`, `"lines"`, `"satins"`), `spacing_mm=3.0` (how far apart fitted points are), `closed_as_fills=False` (DXF), `page=0`. Each shape is `{kind: "fill" | "run" | "satin", geometry, color, name}` in mm, centered on the artwork's center. There is no "import" method: the app adds the shapes the user accepted through an ordinary commit.

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-07/lines-sequencing-drawing` from `main`.
2. `design/types.ts`: everything in 5.2. `store.ts`: `Pen` gains `prepend?: boolean`. `prefs.ts`: `freehandSmooth?: number`, `smallObjects?: Record<string, Record<string, number | string>>`, `importArt?: { strokes?: string; match?: boolean }`.
3. Engine stubs for the nine methods in 5.3 (each raises `APP_ERROR` "not built yet"), their names in `rpc_methods.json`, the two new group files imported in `methods/__init__.py`.
4. Nine feature flags in `project.py` with their detectors: `line_backstitch`, `line_stem`, `line_candlewick`, `line_redwork`, `line_knots`, `fill_blackwork`, `motif_side` (a motif line not centered), `tie_styles` (a lock style other than standard), `branches` (any item with `branch`). Buttonholes, eyelets, freehand shapes, repeats, presets and imported artwork are ordinary shapes and need none.
5. Command files with the reserved shortcuts, each `run` calling a stub that says "Not built yet": `cmd/lines.ts` (`object.buttonhole` Alt+B, `object.eyelet` Alt+E), `cmd/branch.ts` (`layout.branch` Alt+Shift+B, `layout.unbranch` Alt+Shift+U), `cmd/draw.ts` (`tool.freehand` Y, `presets.open` Alt+P), `cmd/importArt.ts` (`file.importArt` Mod+Alt+I); stubs in `feat/smallObjects.ts`, `feat/branch.ts`, `feat/freehand.ts`, `feat/presets.ts`, `feat/importArt.ts`; four import lines in `cmd/index.ts`.
6. Shared menus and panel rows, so no track edits them: the Shapes menu (`ToolRail.tsx`) gains Buttonhole and Eyelet; the toolbar's More menu gains Import artwork and Stitch presets; `contextMenu.ts` gains Branch and Take out of the branch (several shapes selected) and Stitch presets (one shape); `ObjectPanel.tsx` gains `<Cmd id="presets.open" label="Presets… (Alt+P)" />` in the Advanced fold and, under "Stitch as" when `item.branch` is set, "In a branch" with `<Cmd id="layout.unbranch" …>`.
7. `python scripts/kb_commands.py`, then `python scripts/check.py`, then commit ("Phase 7: start"). Workers branch from this commit.

## 7. Tracks

All four run together. Every worker follows "Worker rules" in `BUILDPLAN.md`.

### Track A: line styles and small objects

**Owns:** `digitize/lines/**`, `digitize/fills/lattice.py`, `digitize/fills/blackwork.py`, one import line in `fills/__init__.py`, `digitize/ties.py`, in `digitize/stitches.py` only `RunParams` (new fields), the blackwork lattice field in `FillParams` and the two tie calls in `generate`, `motif_points` in `digitize/patterns.py`, `digitize/smallobjects.py`, the two `shape.*` stubs, `design/lineStyles.ts`, the blackwork entry in `design/fillPatterns.ts`, the Style row and lock-stitch control in `components/ObjectPanel.tsx`, `feat/smallObjects.ts`, `components/SmallObjectDialog.tsx`, `cmd/lines.ts`, new tests and snapshot suites.

#### P7-A1 Five line styles (`digitize/lines/craft.py`)

`s` is distance along the line, `L` the stitch length (`stitch_mm`), `n` the unit normal.

| Style (id) | Needle points | Settings (default, range) |
| --- | --- | --- |
| Backstitch (`backstitch`) | `0, L, L/2, 3L/2, L, 2L, 3L/2, …`: forward one stitch, back half, to the end. A hole every half stitch; three threads thick. | Length |
| Stem stitch (`stem`) | For `k = 0, 1, …`: from `s = kL/2` offset `-w/2·n` to `s = kL/2 + L` offset `+w/2·n`, then back to the next start. Slanted stitches that overlap by half: a rope. | Length; `stem_width_mm` Width 0.8 (0.3 to 2.5) |
| Candlewicking (`candlewick`) | A single run along the line; every `knot_gap_mm` the needle sews a knot centered on the line, then runs on. | Length; `knot_mm` Knot size 1.6 (1 to 3); `knot_gap_mm` Between knots 4 (2 to 15) |
| Redwork (`redwork`) | Out along the line at `0, L, 2L, …`, then back with holes midway between the outward ones; ends where it started. A closed line goes round twice. | Length |
| French knots (`knots`) | A knot at every point of the line, with a jump between knots (trimmed when over 3 mm). Uses `recs`. | `knot_mm` Knot size 1.6 (1 to 3) |

A knot: five points on a circle of diameter `knot_mm`, visited in star order `0, 2, 4, 1, 3` twice, then back to the center: ten stitches of about 0.95 × `knot_mm`. Candlewicking refuses a gap under `knot_mm + 1` ("Knots this close would touch: make the gap at least … mm"). French-knot points closer together than `knot_mm` are skipped with a warning.

**Panel.** The Style row keeps its four buttons. Under it a select, "More styles", lists the five; when one is chosen none of the four buttons is pressed. `LINE_STYLE_DEFS` entries gain `more?: boolean` and `fields` (as fill patterns have), so each style shows only its own settings.

#### P7-A2 Blackwork fill (`blackwork`, open pattern)

`lattice.py`: `tile_segments(kind, cell_mm, bounds)`, `clip_segments(segments, poly)` (pieces under 0.8 mm dropped), `double_run_paths(segments, stitch_mm, start)`. The last builds a graph with a node at every crossing and end, then walks each connected piece depth-first, out along an edge and back: every segment is sewn exactly twice, there is a needle point at every node, and each path ends where it began. One path per connected piece; `_sew_paths` joins pieces.

Lattices (all connected, so a simple shape sews with no jump): `diamonds`, `grid`, `honeycomb` (hexagons `cell` across the flats), `crossed` (grid plus both diagonals). Settings: `blackwork_mm` Cell size 5 (3 to 12); lattice, default `diamonds`. Registration: `open`, `noSpacing`, `step_mm2 = cell × stitch / 4`, no underlay on automatic.

#### P7-A3 Which side a motif sits on

`motif_side`: `center` (today, unchanged), `left`, `right`. In `motif_points`, the across value `v` (−0.5 to 0.5) becomes `-(v + 0.5)` for left and `+(v + 0.5)` for right, times the width, along `n = (-ty, tx)`. Left is the left hand when walking the line the way it was drawn (up on screen for a line drawn left to right). The motif's flat side lies on the line and its teeth point away: blanket stitch round an applique. Panel: "Which side" (Centered, Left, Right) under the motif's Width.

#### P7-A4 Lock-stitch shapes (`digitize/ties.py`)

`tie_style`, read in `generate` beside `tie_in` and `tie_off`:

| Style | At the start `a`, direction `u` toward the next stitch (mirrored at the end) |
| --- | --- |
| `standard` | today's `tie_in` / `tie_off`, called unchanged |
| `triangle` | `a → a + 0.6u → a + 0.3u + 0.52n → a`: holds better on knits and slippery thread |
| `backtack` | `a → a + t·u → a → a + t·u → a`, `t = min(1.0, 80% of the first stitch)`: the strongest |

No lock stitch is shorter than `MIN_STITCH_MM`. At the end, the lock still goes before a trailing trim or jump. Appliques and lettering keep `standard`. Panel: a "Lock stitches" select in the Advanced fold, shown when either lock box is ticked.

#### P7-A5 Buttonholes and eyelets (`digitize/smallobjects.py`)

Generators that return ordinary objects, so they stay editable and need no new object kind. The app adds them at the hoop center in one group, selected, in one undo step, from dialogs `buttonhole` and `eyelet` (`registerDialog`; last values kept in `prefs.smallObjects`).

- **Bar buttonhole** (`style="bar"`): two lips (open satin ribbons, each `(width − cut_gap) / 2` wide, `length` long, `cut_gap` apart, center underlay), sewn down one and back up the other, then a bar tack across each end (a satin ribbon the full width, 1.5 mm long). Four objects.
- **Rounded buttonhole** (`style="round"`): one closed satin ribbon round a stadium-shaped center line.
- Ranges: length 8 to 40 mm, width 3 to 8, cut gap 0.6 to 2. A lip under 1 mm is refused ("Make the buttonhole wider or the cut narrower"). The dialog says "Length = the button's width + its thickness + 3 mm".
- **Eyelet**: a triple run on a circle 0.3 mm outside the hole, then a closed satin ribbon `ring_mm` wide round it. Hole 2 to 12 mm, ring 1 to 3. The existing fold warning applies when the ring is wider than the hole.

#### Track A tests

| Test (file) | Asserts |
| --- | --- |
| `test_five_styles_registered` (`test_lines_craft.py`) | names; `knots` has `recs` |
| `test_backstitch_holes_are_half_a_stitch_apart`, `test_backstitch_covers_the_line_three_times`, `test_stem_stitches_slant_and_overlap` | stem: top stitches 10° to 25° off the line at L 3, width 0.8 |
| `test_candlewick_knots_evenly_spaced_on_the_line`, `test_a_knot_is_ten_short_stitches_round_its_center`, `test_french_knots_sit_on_the_points_with_jumps_between` | a trim only when the jump is over 3 mm |
| `test_redwork_sews_every_stretch_twice_and_ends_where_it_started`, `test_redwork_return_holes_fall_between` | |
| `test_knots_do_not_trip_the_needle_hits_check` | `layout.check` gives no `needle_hits`; if it does, sew the star once, not twice |
| `test_style_settings_are_range_checked`, `test_closed_lines_meet_without_a_gap` | `Knot size must be between 1 and 3 mm`; each style on a closed square |
| invariants and snapshots | suite `lines_craft`: `backstitch_s_curve`, `stem_s_curve`, `candlewick_line`, `redwork_closed_square`, `knots_five` |
| `test_center_is_unchanged`, `test_left_is_above_a_left_to_right_line`, `test_right_mirrors_left`, `test_blanket_teeth_point_away` (`test_motif_side.py`) | the old `run_motif_*` snapshots do not move |
| `test_every_segment_sewn_twice`, `test_one_piece_has_no_jumps`, `test_lines_stay_inside_the_shape`, `test_cell_size_checked` (`test_fill_blackwork.py`) | suite `fills_blackwork`: `diamonds_40`, `grid_donut`, `honeycomb_40`, `crossed_40` |
| `test_standard_equals_the_old_ties`, `test_triangle_returns_to_the_start`, `test_backtack_goes_back_and_forth_twice`, `test_lock_goes_before_a_trailing_trim`, `test_unknown_tie_style_is_refused` (`test_ties.py`) | suite `ties` |
| `test_bar_buttonhole_is_two_lips_and_two_bars`, `test_the_slit_is_left_clear`, `test_lips_join_without_a_jump`, `test_rounded_buttonhole_is_one_closed_ribbon`, `test_sizes_are_checked`, `test_eyelet_is_a_run_then_a_ring`, `test_generated_objects_render_and_pass_invariants` (`test_smallobjects.py`) | |
| `test_projects_name_each_feature` | the eight flags of this track |
| `five more styles sit behind More styles`; `Stem stitch shows Width and presses none of the four buttons`; `Lock stitches appears when a lock box is ticked`; `a buttonhole is added grouped, selected, in one undo step` (`design/lineStyles.test.ts`, `ObjectPanel.dom.test.tsx`, `feat/smallObjects.test.ts`) | |

### Track B: branching (hard)

**Owns:** `layout/branch.py`, three call sites in `layout/render.py` (`prepared_items` before the item loop, the pass registration, `info` into `Rendered.branches` and `render_summary`), `jumps.py`, the `layout.branch_plan` stub, `feat/branch.ts`, `canvas/branchOverlay.ts`, `cmd/branch.ts`, one condition in `StitchCanvas.tsx` (a shape in a branch shows no start and end dots of its own), new tests.

#### P7-B1 Sewing a branch as one path

**Who can be in one.** Drawn lines, satins and fills that are sewn in the same thread. A member whose thread differs, that sews in more than one thread (a Phase 6 blend), or that has been turned into an applique, is left out with a note. A branch id with one member is ignored. Copies of a member join its branch.

**Where it sews.** Members that are next to each other in the sewing order are routed together, at the place of the first. A member separated from the rest by another item starts a path of its own, with a note. (The Branch command puts them together: P7-B2.)

**Planning** (`branch.plan`, cached by the members' geometry, settings, transforms and the branch's dots):

1. *Order.* Members whose stitching overlaps keep their order (the later one is on top; `_blocks_overlap`). The rest are ordered to make the gaps between neighbors smallest, the gap being the distance between two members' shapes (`jumps._shape_of`; zero when they touch). Eight members or fewer: exact search over the orders the overlaps allow. More: nearest-first, then up to 200 two-swap improvements. The first member is the one nearest the branch's `start_mm` when set; the last is the one nearest `end_mm`.
2. *Entry and exit.* A member leaves at the point of its outline nearest the next member, and the next enters at the point of its outline nearest that. An open line or ribbon is turned round (`_reversed_path`) when that shortens the two moves; a closed one starts at its nearest point. These become `start_mm` / `end_mm` (or a reversed path) on a copy of the item: `prepared_items(layout)` returns the items with those overrides, and returns `layout["items"]` itself when there is no branch.
3. *Joins*, worked out from the stitches actually generated, last stitch `a` of one member to first stitch `b` of the next. Under 0.3 mm: nothing. Otherwise look for a route inside what is sewn later: the union of `_cover` of every block sewn at or after the next member, tried straight and then along its edges (`dz._route` on a `Zone`). Found: running stitches 2.5 mm long that belong to no item (as `_join_objects` writes hidden travel), whatever the layout's "Fewer jumps & trims" setting is. Not found: a trim (when the move is over 3 mm) and a jump, with the note "Branch: no hidden way from A to B (they don't touch and nothing sewn later covers the gap), so the thread is cut there. Move them together or put a shape over the gap."
4. *Locks.* Where the thread runs on, the lock stitches at that join are left out (the member is generated again with that lock off; the object cache makes this cheap). Round a cut they stay.
5. The members' blocks become one block, in planned order, with the joins between. `BranchInfo` reports the order, the first and last stitch, the hidden travel in mm and the number of cuts.

The pass is registered `after_items`. Projects without a branch never reach any of this code.

#### P7-B2 Commands, dots, panel

- `layout.branch` (Alt+Shift+B) calls `layout.branch_plan`, which refuses in plain words: fewer than two drawn shapes; more than one thread; lettering, an applique or a stitch file in the selection; another item sewn between the members that overlaps one of them ("Leaf 3 is sewn between these shapes and overlaps Leaf 2: move it first"). Otherwise the app applies `order`, gives the members a new branch id, and commits once.
- `layout.unbranch` (Alt+Shift+U) takes the selected shapes out; a branch left with one member is dissolved and its entry in `layout.branches` removed.
- Dots: when a member is selected, an overlay (`registerOverlay`) draws one green and one red dot at `BranchInfo.start` and `end`; dragging one (a canvas tool through `registerCanvasTool`) stores the drop point in `layout.branches[id]`. Members show no dots of their own while in a branch.

#### P7-B3 L-017, the cheap part

`optimize_jumps` gains two more movers: an applique starts each of its edges at the point nearest where the piece before ended (a `start_mm` read by `applique`, turning each ring with `nearest_rotation`); a text's first letter starts at its edge nearest the piece before (`letters["0"].start_mm`). Stitch files stay as they are. L-017 becomes PARTIAL. Drop this item first if the track runs long, and say so in the handoff.

#### Track B tests (`engine/tests/test_branch.py` unless noted)

| Test | Asserts |
| --- | --- |
| `test_three_touching_squares_sew_as_one_path` | one block; no trim or jump between its first and last stitch; `assert_sane` |
| `test_order_is_the_shortest`, `test_overlapping_members_keep_their_layering` | four squares in a row, listed scrambled, sew left to right or right to left |
| `test_join_runs_under_a_later_shape` | two red squares 10 mm apart under a later blue fill: the join is stitches inside the blue cover, belonging to no item |
| `test_no_hidden_way_is_a_cut_with_a_note` | a trim, a jump, a warning whose code starts `branch_` |
| `test_branch_start_and_end_are_honored`, `test_open_lines_are_turned_to_shorten_moves` | first and last stitch within 1.5 mm of the dots |
| `test_inner_locks_are_left_out_where_the_thread_runs_on` | and kept round a cut |
| `test_other_threads_and_appliques_are_left_out_with_a_note`, `test_a_branch_of_one_is_ignored`, `test_no_branch_means_the_same_items_object` | `prepared_items(layout) is layout["items"]` |
| `test_plan_is_cached`, `test_twenty_members_plan_in_under_two_seconds` | a second render generates nothing new |
| `test_branch_plan_refuses_in_plain_words`, `test_branch_plan_names_the_blocker`, `test_render_summary_lists_branches`, `test_project_names_the_feature` | |
| snapshots | suite `branch`: `three_squares`, `under_a_later_fill`, `lines_and_fill`, `with_a_gap` |
| `test_optimize_jumps_moves_an_applique_start`, `test_optimize_jumps_sets_the_first_letters_start` (`test_jumps.py`) | |
| `Branch needs two shapes in one thread`; `Take out dissolves a branch of one`; `a dragged dot is stored` (`feat/branch.test.ts`) | |

### Track C: drawing tools

**Owns:** `design/simplify.ts`, `feat/freehand.ts`, `canvas/freehandTool.ts`, the `DrawHint` bar in `components/ToolRail.tsx`, `cmd/draw.ts`, `continueDrawing` and `penFinish` in `actions.ts` (those two functions only), `RepeatSpec` and `repeatItem` in `design/layout.ts`, `components/RepeatDialog.tsx`, `canvas/repeatOverlay.ts`, `presets.py`, the `presets.*` stubs, `feat/presets.ts`, `components/PresetsDialog.tsx`, new tests.

#### P7-C1 Freehand (`tool.freehand`, Y)

A switch on the drawing tools, not a tool of its own. With it on and Line, Satin or Fill chosen, press and drag to draw; on release the stroke becomes pen points, so the shape can go on with clicks or another stroke and finishes with Enter as usual. A Fill stroke let go within 12 screen pixels of its start closes and finishes. Pressing Y with no drawing tool chosen picks Line. State lives in a small store in `feat/freehand.ts`; the canvas side is a registered tool plus an overlay for the live stroke. The DrawHint bar shows "Freehand · Smoothing" with a 1-to-5 stepper while it is on. Mouse or pen tablet; pressure is not used.

`design/simplify.ts`, pure functions:

1. Drop samples within 0.15 mm of the last one.
2. Ramer–Douglas–Peucker with tolerance from the Smoothing setting 1 to 5: 0.15, 0.25, 0.4, 0.6, 0.9 mm (default 3), never less than 1.5 screen pixels.
3. A kept point where the stroke turns more than 50° (measured over 1 mm either side) is a corner; the rest are curve points.
4. Between corners, drop a curve point while the curve through the others (`design/paths.ts`) stays within tolerance of the samples.
5. A stroke under 2 mm long is one click.

#### P7-C2 Continue from either end (`draw.continue`, K)

Today K picks a shape up in the pen and adds points at its end. For an open line or satin ribbon with its first point selected, K now continues from the start: the pen gets the points reversed and `prepend: true`, and `penFinish` reverses them back, so the shape keeps its direction and its start and end. Otherwise it continues from the end, as now. The panel hint under "Add points (K)" says "Select the first point to add at the start." Freehand strokes continue a shape the same way.

#### P7-C3 Repeat: Mirror, Wreath, Kaleidoscope

Modes become **Row · Wreath · Kaleidoscope · Mirror**.

- **Wreath** is today's Circle, with a choice of center: "Below the design" (today) or "The middle of the hoop" (`center: "hoop"`: the radius is the design's distance from (0, 0), so one motif placed off-center repeats round the middle).
- **Kaleidoscope** is a wreath with `mirror: true`: an even number of copies, every other one mirrored left to right before it is turned, so neighbors are mirror images across the line between them. The dialog asks for "Pairs" (2 to 12).
- **Mirror**: Left–right or Top–bottom (`mirror2`: one mirrored copy across a line `gap / 2` beyond the design's edge) or Both (today's `mirror4`).
- While the dialog is open an overlay draws each copy's outline box where it will land.

#### P7-C4 Stitch presets (`presets.open`, Alt+P)

A preset is one shape's stitch settings under a name. It leaves out what belongs to one shape: `angle_deg`, `reverse`, `start_mm`, `end_mm`, `angle_line`, extra angle lines and carved lines. Files live in `<data dir>/presets/<slug>.luddpreset`; import and export copy a file. Ids are slugs made the way thread chart ids are (no reserved Windows names, no path parts). Import checks the settings with that kind's `from_dict` and refuses in plain words: out of range, or "made by a newer LUDD" for a pattern or style this version does not know.

Dialog `presets`: the list for the selected shape's kind (all kinds when nothing is selected); **Apply to selection** (every selected shape of that kind, one undo step); **Save current as…**; **Use for new shapes** (writes `prefs.objectDefaults`); Delete; Import…; Export…. Built-ins are read-only.

#### Track C tests

| Test (file) | Asserts |
| --- | --- |
| `a wobbly straight stroke becomes two points`; `a square keeps four corners`; `a circle becomes at most 12 curve points within 0.4 mm`; `300 samples become at most 25 points`; `smoothing 1 keeps more points than 5`; `a tiny stroke is one click` (`design/simplify.test.ts`) | |
| `Y picks Line when no drawing tool is chosen`; `a stroke is added to the pen's points`; `a fill stroke let go at its start finishes the shape`; `Esc drops the stroke before the shape` (`feat/freehand.test.ts`) | |
| `continuing from the first point adds at the start and keeps the direction`; `continuing from the end is unchanged` (`features.draw.test.ts`) | |
| `row, circle and mirror4 give the same copies as before`; `mirror2 lands across the axis and is flipped`; `a wreath round the hoop keeps every copy the same distance from the middle`; `kaleidoscope neighbors are mirror images` (`design/repeat.test.ts`) | fixed node lists for the old modes |
| `test_save_list_delete_round_trip`, `test_names_cannot_escape_the_presets_folder`, `test_import_refuses_out_of_range_settings`, `test_import_refuses_a_newer_pattern`, `test_export_then_import_is_equal`, `test_builtins_cannot_be_deleted` (`engine/tests/test_presets.py`) | |
| `a preset leaves out per-shape settings`; `applying changes only shapes of its kind, in one undo step` (`feat/presets.test.ts`) | |

### Track D: artwork import

**Owns:** `artimport/**`, `methods/art.py`, `engine/pyproject.toml`, `engine/uv.lock`, `feat/importArt.ts`, `components/ImportArtDialog.tsx`, `canvas/importOverlay.ts`, `cmd/importArt.ts`, the dropped-file branch in `App.tsx` (`useFileDrop`), new tests with small SVG and DXF files written inside the tests.

#### P7-D1 SVG and DXF to shapes

1. **Read.** SVG through `svgelements` (paths, basic shapes, groups, transforms, `<use>`, CSS classes, units); DXF through `ezdxf` (LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC, ELLIPSE, SPLINE, HATCH, INSERT; `$INSUNITS`; layer colors). Refuse files over 20 MB (SVG) or 50 MB (DXF), and any SVG that declares entities. Nothing is ever fetched: linked images are skipped.
2. **Size and points.** Millimeters from the file's units. An SVG with no real size is read at 96 pixels per inch and says so; a DXF with no units is read as millimeters and says so. `width_mm` rescales everything. DXF's y axis is flipped. Curves are flattened to 0.1 mm, then points are fitted with `shapeops.to_nodes` (the fitter tracing uses).
3. **Filled paths become fills**, holes worked out by the path's fill rule. Pieces under 1 mm² are dropped and counted.
4. **Strokes**: under 1 mm wide a running-stitch line; 1 to 12 mm a satin ribbon of that width; wider, the stroke's outline as a fill, with a note. A path with both gives a fill, then its stroke on top. DXF closed outlines are lines unless `closed_as_fills`.
5. **Order** is the file's drawing order (bottom first). **Colors** come across as they are; one thread per color.
6. **Limits and skips.** Over 2,000 shapes is refused ("simplify it first"); over 200 warns. Text, pictures inside the file, gradients, clipping and dashes are skipped or flattened and listed in `skipped`. A filled rectangle that covers 95% of the artwork and lies at the bottom is flagged as background.

**The dialog** (`importArt`, also opened by dropping an .svg, .dxf or .pdf on the window): the shapes as outlines on the hoop; "12 fills, 4 lines, 2 satins · 86 × 54 mm"; Width (keeps the proportions); Lines as (Automatic, Running stitch, Satin); a tick per color (background unticked); "Match colors to my threads" (`threads.match`, on when My threads has spools); what was skipped and why; Add and Cancel. Add makes ordinary shapes with `defaultsFor(kind)`, in one group, selected, in one undo step.

#### P7-D2 PDF (90 minutes, then decide)

Try to read page objects of type path through `pypdfium2`'s raw PDFium calls (segments, fill and stroke color, stroke width, matrix; forms opened one level deep; 1 unit = 1/72 inch) into the same path list `convert.py` takes. **Success** is one test: a one-page PDF with a filled path and a stroked path gives two shapes of the right size. If that passes inside the time, PDF pages import like SVG. If not, a PDF page is rendered at 300 dpi and comes in as a picture to trace, embedded in the project like any picture, with the note "This PDF was added as a picture. Trace it with Auto-trace, or save it as SVG from the program that made it."

#### Track D tests (`engine/tests/test_artimport_svg.py`, `test_artimport_dxf.py`)

| Test | Asserts |
| --- | --- |
| `test_real_size_from_mm_units`, `test_pixels_assume_96_per_inch_with_a_note`, `test_width_rescales` | |
| `test_filled_path_is_a_fill`, `test_evenodd_ring_is_a_hole`, `test_nonzero_same_way_rings_have_no_hole` | |
| `test_thin_stroke_is_a_line`, `test_3mm_stroke_is_a_3mm_ribbon`, `test_very_thick_stroke_is_a_fill_with_a_note`, `test_fill_and_stroke_make_two_shapes_fill_first` | |
| `test_groups_transforms_use_and_classes`, `test_basic_shapes`, `test_a_circle_becomes_few_points` | a circle: 16 points or fewer, within 0.2 mm |
| `test_file_order_is_sewing_order`, `test_text_and_pictures_are_skipped_and_counted`, `test_background_rectangle_is_flagged` | |
| `test_entities_are_refused`, `test_huge_files_are_refused`, `test_too_many_shapes_is_refused` | plain-words errors |
| `test_imported_shapes_render_and_pass_invariants` | through `layout.render` |
| `test_dxf_inches_become_mm`, `test_dxf_y_axis_is_flipped`, `test_dxf_closed_outline_is_a_line_unless_asked`, `test_dxf_hatch_is_a_fill`, `test_dxf_block_is_expanded`, `test_dxf_layer_color_is_used`; `test_pdf_vector_paths` or `test_pdf_comes_in_as_a_picture` | the PDF test is whichever D2 ended on |
| `shapes become objects with default settings in one group`; `unticked colors are left out`; `Add is off until the preview arrives`; `Cancel adds nothing` (`feat/importArt.test.ts`, `ImportArtDialog.dom.test.tsx`) | |

## 8. Integration (session lead)

1. Merge in the order D, A, C, B. Run `python scripts/check.py` after each.
2. `python scripts/make_notices.py` (new dependencies), then `python scripts/kb_commands.py`.
3. `pnpm build:engine` once. The smoke check must pass. Note the frozen engine's size before and after; if `ezdxf` adds more than 15 MB, leave its drawing add-ons out of the freeze and try again.
4. Write the docs (section 9). `python scripts/check.py --all`. Then the stop contract in `BUILDPLAN.md`.

Expected conflicts: none. `ObjectPanel.tsx` is Track A's after Step 0; `StitchCanvas.tsx` is touched only by Track B's one condition; `stitches.py` only by Track A.

## 9. Docs payload

**`docs/CHANGELOG.md`**, under the current unreleased heading:

```
### Phase 7: line styles, branching, freehand, artwork import (YYYY-MM-DD)
- **More line styles**: Backstitch, Stem stitch, Candlewicking, Redwork (out and back) and French knots, under More styles. Motif lines can sit to one side of the line. A new Blackwork fill sews a lattice of double lines.
- **Lock stitches**: choose Standard, Triangle or Back-tack for a shape's start and end.
- **Buttonholes and eyelets**: Shapes menu, or Alt+B and Alt+E. They are ordinary shapes you can reshape.
- **Branch** (Alt+Shift+B): sew the selected same-color shapes as one path with one start and one end. Moves between them run hidden under later stitching; where that isn't possible LUDD says so and cuts once. Optimize jumps now also chooses where an applique and a text's first letter start.
- **Freehand** (Y): drag to draw; Smoothing sets how many points you get. **K** can now continue a line from its first point.
- **Repeat**: Mirror, Wreath round the middle of the hoop, and Kaleidoscope, with outlines showing where copies will land.
- **Stitch presets** (Alt+P): save a shape's settings under a name, apply them to other shapes, share them as files.
- **Import artwork** (Ctrl+Alt+I): SVG and DXF drawings come in as fills, lines and satins at their real size, after a preview.
```

**`docs/LUDD-KNOWLEDGE-BASE.md`**

| ID | Entry |
| --- | --- |
| F-1317 | Craft stitches: the five styles, their settings, More styles; blackwork fill; Which side for motifs (also update F-1306 and F-1305) |
| F-1318 | Buttonholes and eyelets: sizes, the cut gap, that they are grouped shapes |
| F-1320 | Lock-stitch shapes |
| F-1808 | Branching: who can join, how moves are hidden, the note when one can't be, the branch's dots |
| F-504 | Freehand drawing (mark L-011 superseded by F-504) |
| F-505 | Continue a shape from its end (update F-501, F-601) |
| F-1109 | Mirror, wreath and kaleidoscope (update F-1108) |
| F-1319 | Stitch presets, the `.luddpreset` file, the presets folder |
| F-209 | Import artwork: formats, sizes, what becomes what, what is skipped |
| L-017 | now PARTIAL: appliques and a text's first letter are moved; stitch files are not |
| L-045 to L-048 | L-045 a branch takes drawn lines, satins and fills in one thread only · L-046 artwork import leaves out text, pictures inside the file, gradients, clipping and dashes · L-047 PDF (how D2 ended) and DXF (if decision 1 was no) · L-048 freehand ignores pen pressure. L-049 stays unused. |
| T-035 to T-038 | T-035 "My branch still has a cut" (the shapes don't touch and nothing covers the gap) · T-036 "Imported artwork is the wrong size" (the file has no real size: set Width) · T-037 "Shapes are missing after import" (text not made into outlines, background unticked, tiny pieces) · T-038 "My freehand line is wobbly or has too many points" (Smoothing) |

Section 2 index rows for each F- entry; freehand becomes YES. Section 23 history row; *Last updated*; section 25 by the script.

**`docs/USER-MANUAL.md`**: section 2 (Import artwork), 4 (Freehand, continue, buttonholes and eyelets), 5 (Repeat modes), 6 (line styles, blackwork, lock stitches, presets, branch). **`ai/helpdocs.py`**: the same, with every new shortcut.

**`docs/stitchout-log.md`**, rows for "Pending machine tests":

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 7 | **Craft line styles** | A 60 mm S curve in Backstitch, Stem stitch, Candlewicking and Redwork; five French knots; blanket stitch round a felt circle with its teeth toward the felt | Each looks like its name; stem stitch looks like rope; knots stand up and don't pull out; every blanket tooth catches the felt; no thread nests |
| Phase 7 | **Blackwork fill** | A 40 mm square in each lattice, 5 mm cells | Lines crisp and doubled; no loose threads across cells |
| Phase 7 | **Lock-stitch shapes** | The same 30 mm satin on T-shirt knit with Standard, Triangle and Back-tack | Tug the tails: none unravels; the triangle doesn't show |
| Phase 7 | **Buttonhole and eyelet** | A 16 mm bar buttonhole and a rounded one on two layers of cotton; a 4 mm eyelet | Cut the slit: lips don't fray and the button passes; the eyelet holds once punched |
| Phase 7 | **Branch** | Three touching leaves in one green; two red shapes joined under a later blue patch; two shapes with a gap | One start and one end; nothing to snip where shapes touch or are covered; the hidden run doesn't show through; the gap is cut once |
| Phase 7 | **Imported artwork** | A simple SVG logo (fills and 2 mm strokes) imported 80 mm wide | Measures 80 mm; strokes sew as satins of the drawn width; fills meet their borders |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Branch planning is slow or its search is wrong for big branches | the 20-member timing test fails | Lower the exact-search limit from 8 to 6; nearest-first with two-swaps is always the fallback. |
| A hidden run shows through sparse stitching, or a join with no locks pulls loose | the Branch stitch-out row (not testable here) | `_cover` already counts only rows 0.7 mm apart or closer: do not loosen it. A branch-wide "Lock every shape" switch can be added later; note it in the backlog. |
| `svgelements` or `ezdxf` fails on Python 3.12 or in the frozen engine | import error, or the smoke check fails | SVG: the small parser from decision 1. DXF: left out, L-047. |
| The PDF attempt eats the track | 90 minutes pass | Stop and ship "PDF as a picture". |
| Freehand feels wrong and jsdom cannot show it | no failing test | The math is tested; the handoff says the tool was not tried by hand. |
| Four tracks are too much for one session | context or time runs out | Tracks are independent. Merge what is green, list the rest in `HANDOFF.md`, and finish them in a second session. |

## 11. Handoff

Write in `HANDOFF.md`: test counts before and after; which of decisions 1 and 2 applied and how P7-D2 ended; the frozen engine's size change; whether P7-B3 was built; that freehand, the branch dots and the two overlays were not tried by hand (unless they were); any change made to `canvas/hooks.ts`, `LineStyle` or `FillPattern` that later phases should know about; any spec deviation, one line each.

## 12. Build notes (2026-11-27)

- Handoff (section 11): decisions 1 and 2 were yes, so `svgelements`, `ezdxf` (with `pyparsing`) and `pypdfium2` are dependencies (`uv.lock` adds only them and `typing-extensions`; wheels for all four CI platforms). **P7-D2 succeeded** (about 7 minutes of the 90): PDF vector paths import, forms one level deep. The frozen engine went from 77,110,585 to 84,065,359 bytes (+6,954,774; ezdxf's drawing add-ons aren't pulled in), and its smoke check now reads a small SVG, DXF and PDF. **P7-B3 was built** (the text's first letter in Track B, the applique's start by the lead). Tried by hand in the browser preview with a scratch data folder: freehand, a branch of three squares (and dragging its start dot), the Repeat window's Kaleidoscope with its outlines, and an SVG import; not tried by hand: the buttonhole and eyelet windows, the presets window, DXF and PDF import in the app, a pen tablet, the desktop (Tauri) build. `canvas/hooks.ts` is unchanged; `LineStyle` gained `recs`; `RunParams` gained `notes`; `FillPatternDef` gained `choices`; `fills/lattice.py` (`tile_segments`, `clip_segments`, `double_run_paths`) is ready for Phase 8's lace.
- Branch, thread that shows (`showing()` in `test_branch.py`: joining thread on stitching already sewn and not covered afterwards, sampled every 0.1 mm): three shapes sharing edges, overlapping, or touching at corners: **0.0 mm, 0 cuts** (hidden travel 0.99, 5.14 and 1.36 mm). 120 seeded random branches of 3 to 6 members: 34.5 mm in all, median 0.29 mm, worst 1.89 mm; more than 0.5 mm inside the outlines 7.4 mm in all, worst 1.64; 205 cuts, nearly all where members are 2 to 6 mm apart with nothing covering the gap; 217.9 mm of hidden travel. Twenty members plan and draw in under 1 s.
- Step 0: the every-method test got sample arguments for the nine new methods, and the method count is 80 (was 71). `tie_styles` is flagged only for lines, satins and fills with a lock style other than Standard and a lock box ticked.
- A: a motif's side is measured from its flat edge (Scallop sits on the line; one of your own motifs that is all on one side goes to the chosen side); Backstitch and Stem stitch start again at corners over 35 degrees; blackwork joins its pieces itself; the rounded buttonhole's tip says + (width less cut gap) mm, since + 3 mm can leave its slit too short; the eyelet's satin starts at the hole's edge. `test_seams_engine.py` names all nine line styles; `ObjectPanel.dom.test.tsx`'s exact row lists gained Lock stitches.
- B: where shapes only touch, a join may reach the later cover over up to 1 mm at each end, and a join up to 1 mm long is one stitch (`REACH_MM`; without it, three touching shapes get two jumps, because `_cover` is shrunk 0.3 mm inside the stitching). With no hidden way over a gap of 3 mm or less, the move is a jump with no trim and its note says so; it isn't counted as a cut. Where two shapes share an edge, the way out is a third of the way along it (the middle was a tie). Members aren't reordered in `items`: the pass puts their blocks in the planned order. Applique starts were outside B's files.
- C: smoothing gives each stretch between corners the fewest points, spread by how much it bends, then adds and drops points checked both ways (the spec's steps alone gave 31 points on a spiral); at less than about 3.75 screen pixels per mm the 1.5-pixel floor exceeds 0.4 mm. Reversing a line in the app keeps corners with their points and moves "straight" with its stretch. Kaleidoscope mirrors across the line out from the circle's middle. Repeat's stitch count is the whole design afterwards (warns over 60,000, refuses over 400,000). Preset export overwrites only a preset file; a clashing import gets "(2)"; built-in names are refused per kind; presets also leave out `ripple_center`, `blend_flip` and `push_comp_mm`.
- D: an extra `keep_background` option (the background rectangle is left out of the size unless ticked) and "pages" in the answer; svgelements reads only a rebuilt, bounded copy of the SVG; ezdxf is imported with an empty font list (its first import otherwise reads every font and writes a cache in the home folder); curves flatten within 0.05 mm; DXF reads model space only, and polyline widths count as stroke widths; added limits: PDF 50 MB, 1,000 mm after Width, about 400,000 stitches, 60 s. With no design open, an empty one is made for the preview and removed on Cancel.
- Integration (lead), found merging or in the running app, each with a test that fails without it: **an older bug**, `jumps._reversed_path` moved every point's kind to its neighbor, bending lines that mix curves and straight parts (Optimize jumps, the end dot, branches); now only "straight" moves, and branches and Optimize jumps don't turn a line that can't be turned exactly. A one-sided motif changes sides when mirrored (the app) or turned round (the engine). Optimize jumps now saves both the points and settings of a turned piece (it saved one), starts an applique's edges nearest the piece before (no feature flag: an older LUDD ignores it and sews the same shape from another point), and leaves a satin with both dots as it is (the bar buttonhole's first lip now has both; same stitches). The app now applies a text's new first-letter start (it was dropped). The gap check says a gap made on purpose can stay. The panel says how to add points at a line's start. After a freehand stroke the pen's preview line reaches where the button was let go (it ran back to the press until the mouse moved). `build_engine.py` gives PyInstaller an empty ezdxf font cache (otherwise building writes one in the home folder); `make_notices.py` takes every file in a wheel's licenses folder (pypdfium2's 37 weren't found).
