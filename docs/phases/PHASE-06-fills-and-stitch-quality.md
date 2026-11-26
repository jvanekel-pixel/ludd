# Phase 6: Fills & stitch quality

| | |
| --- | --- |
| Weight | Heavy. Do it on the larger plan. |
| Session lead | Sonnet 5.5. Step 0 touches `tatami()`, the most delicate function in the engine: do it alone, in small commits. |
| Hard tracks | A (the rows engine) and C (blend, turning fills): give both workers the stronger model if there is room; C first |
| Depends on | Phase 3 (fill and line registries, descriptors, invariants) |
| Parallel-safe with | Phases 4, 5, 9, 10, 11, 12 |
| Changes stitches | Yes for new options. Existing shapes sew the same: every new setting is off or absent on old objects. |
| Closes (compendium) | Two-color blend ★ · Push compensation ★ · Motif fill · Custom motifs · Maze fill · Wave, ripple, mesh (was Partial) · Emboss and carving · Hand-stitch look · Multiple angles in one fill · Tatami patterns (was limited) · feathered fills (`docs/PLAN.md` backlog) |
| Old plan | Phase 7, first half; push compensation from Phase 4 |

## 1. Goal and done-when

Blend is Hatch 4's headline feature and is locked to its $1,199 Digitizer level. This phase gives LUDD blend, the decorative fills competitors charge for, and the quality controls (push compensation, feathering, weave) that make ordinary fills sew better.

**Done when:**

1. Every new fill pattern and option has: a registry entry, a descriptor entry, its named tests, a snapshot suite, the invariants, and a PES and JEF round trip.
2. A blend of two colors has, across the shape, a combined row density within 15% of the same fill in one color.
3. A fill with two angle lines 60° apart has rows whose direction at each line is within 5° of that line.
4. A line saved as a motif can be used in a motif line and a motif fill, and the project reopens on a computer that does not have the motif.
5. The 27 cases in `digitize.json` are unchanged.
6. `python scripts/check.py --all` prints `RESULT: PASS`.

## 2. Scope

| ID | Item | Track |
| --- | --- | --- |
| P6-S1 | Row hooks in `tatami()`, multi-thread objects, carve geometry, contracts | Step 0 |
| P6-A1 | Push compensation ("End trim") for fills and satins (**held until decision 1**) | A |
| P6-A2 | Weave: how a fill's needle points line up (standard, brick, twill, smooth, random) | A |
| P6-A3 | Carved lines in a fill (emboss) | A |
| P6-A4 | Feathered edges | A |
| P6-A5 | Hand-sewn look for lines, satins and fills | A |
| P6-B1 | Motif fill | B |
| P6-B2 | My motifs: save a drawn line as a motif; import, export | B |
| P6-B3 | Maze fill | B |
| P6-B4 | Ripple fill | B |
| P6-B5 | Mesh fill | B |
| P6-C1 | Blend: two or three colors fading into each other (lifts L-001) | C |
| P6-C2 | Turning fills: several angle lines in one fill | C |
| P6-Z1 | Docs, golden round trips, stitch-out rows, handoff | Integration |

**Out of scope:** freestanding lace and 3D puff (Phase 8, which builds on mesh and on satin options), blackwork (Phase 7), photo-stitch tone fill (Phase 9), custom stamp shapes beyond lines.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | `PLAN.md` has always said push compensation waits for a patent check. Has it been done? | The owner's call. Shortening a column's ends for push is taught in every digitizing course and ships in Floriani and StitchArtist; the method in A1 is that plain one. | A1 is **not built**; its stub stays and the control is hidden. |
| 2 | If A1 is built: on for every design, or only new ones? | New designs only. A design-wide switch that new designs start with on; old projects open with it off and sew as before. | New designs only. |
| 3 | Turning fills can adapt Ink/Stitch's "guided fill" (GPL-3). D-005 already allows this with credit. Confirm? | Yes, with the copyright notice in the file header. | Yes (D-005 stands). |
| 4 | Blend: two or three colors in the first version? | Up to three in the panel; the engine takes four. | Up to three. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Registries exist | `git ls-files engine/threadline_engine/digitize/fills/__init__.py engine/threadline_engine/digitize/lines/__init__.py` | two paths |
| Spiral proves the seam | `git ls-files engine/threadline_engine/digitize/fills/spiral.py` | the path |
| The rows functions | `grep -n "^def tatami\|^def _rows\|^def _row_stitches\|^def _fill_part\|^def gradient_ys" engine/threadline_engine/digitize/stitches.py engine/threadline_engine/digitize/patterns.py` | all five |
| Brick offset is still inline | `grep -n "(r % 3) \* stitch / 3" engine/threadline_engine/digitize/stitches.py` | one match |
| One block per object | `grep -n "def _object_blocks" engine/threadline_engine/layout/objects.py` | one |
| Geometry keys | `grep -n '"nodes", "rail_a", "rail_b", "outline"' engine/threadline_engine/digitize/stitches.py` | at least one |
| Descriptors | `grep -n "FILL_PATTERN_DEFS" apps/desktop/src/design/fillPatterns.ts` | present |
| Baseline | `python scripts/check.py` | `RESULT: PASS` |

## 5. Architecture

### 5.1 Row hooks (Step 0)

`tatami()` gains four optional arguments. Left out, it behaves exactly as today.

| Argument | Type | Used by | Default behavior |
| --- | --- | --- | --- |
| `row_ys` | `Sequence[float] \| None` | blend (C1): the heights of this color's rows in the turned frame | even spacing, or `gradient_ys` when `sparse_to` is set |
| `offsets` | `Callable[[int], float] \| None` | weave (A2): row number → shift as a fraction of a stitch | `(r % 3) / 3` |
| `forced` | `Callable[[float, float, float], list[float]] \| None` | carve (A3): `(y, x0, x1)` → x positions that must be needle points | none |
| `end_shift` | `Callable[[int, float, float], tuple[float, float]] \| None` | feather and hand-sewn look (A4, A5): `(row, x0, x1)` → new ends | unchanged |

`_row_stitches` gains `forced_xs: Sequence[float] = ()`: each becomes a needle point, and grid points within 0.8 mm of one are dropped (the existing gap-splitting then keeps every stitch at or under the step).

A pattern passes these through its registry entry: `FillPattern.rows(params)` already returns extra keyword arguments for `tatami()`.

### 5.2 Objects that sew in more than one thread (Step 0)

```python
# digitize/stitches.py
def generate_parts(obj) -> list[tuple[list[Rec], list[str], int]]:
    """(records, warnings, thread slot) per part. One part in slot 0 for everything that exists today."""
```

`FillPattern` gains `parts: Callable | None` (a pattern that returns several parts) and `covers: bool = False` (an open-kind pattern that hides the fabric: it may have cross-hatch underlay and Edge pad). `layout/objects.py` `_object_blocks` makes one block per part: slot 0 sews in the object's thread, slot `k` in `params.blend[k-1]`; `threads[k]` on the item overrides slot `k` (today only `threads[0]` is read). Block sources are `(item, k)`, so Order & colors recolors each part.

### 5.3 Data model (`design/types.ts`)

```ts
export type FillPattern = "tatami" | "gradient" | "wave" | "contour" | "stipple" | "cross" | "spiral"
  | "blend" | "motif" | "maze" | "ripple" | "mesh";
export type FillGeometry = { outline: PathNode[]; holes?: PathNode[][]; carve?: PathNode[][] };
export type FillParams = {
  // …existing…
  push_comp_mm?: number;                      // A1: 0 = off for this shape; absent = the design's setting
  weave?: "standard" | "brick" | "twill" | "smooth" | "random";   // A2
  feather?: "none" | "left" | "right" | "both";   // A4: which row ends
  feather_mm?: number;                        // 0.5 to 6, default 2
  hand_pct?: number;                          // A5: 0 to 100
  blend?: Thread[];                           // C1: the colors after the shape's own (1 to 3)
  blend_balance?: number;                     // C1: -1 to 1, default 0
  angle_lines?: [[number, number], [number, number]][];   // C2: two or more
  motif?: string; motif_mm?: number; motif_width_mm?: number; motif_gap_mm?: number; motif_stagger?: number;   // B1
  motif_unit?: [number, number][];            // B2: a user motif, carried with the shape
  maze_mm?: number; ripple_mm?: number; ripple_center?: [number, number]; mesh_mm?: number; mesh_cross_deg?: number;   // B3–B5
};
export type RunParams  = { /* …existing… */ hand_pct?: number; motif_unit?: [number, number][] };
export type SatinParams = { /* …existing… */ hand_pct?: number; push_comp_mm?: number };
export type Layout = { /* …existing… */ push_comp?: boolean };   // A1: the design-wide switch
```

`FillPatternDef` (Phase 3) gains `angle?: boolean` (show Angle although the pattern is open) and `threads?: number` (how many extra thread pickers).

### 5.4 Engine files

```
digitize/rows/__init__.py
digitize/rows/push.py      A1  directional shrink
digitize/rows/weave.py     A2  offset sequences
digitize/rows/carve.py     A3  crossings
digitize/rows/ends.py      A4, A5  feather and jitter
digitize/fills/motif.py    B1
digitize/fills/maze.py     B3
digitize/fills/ripple.py   B4
digitize/fills/mesh.py     B5
digitize/fills/blend.py    C1
digitize/fills/turning.py  C2
motifs.py                  B2  the user's motif folder
methods/motifs.py          B2  motifs.list, motifs.save, motifs.delete, motifs.export, motifs.import
```

### 5.5 RPC (Track B)

| Method | Parameters | Returns |
| --- | --- | --- |
| `motifs.list` | – | `[{ id, name, builtin, unit }]` |
| `motifs.save` | `name: str`, `nodes: list`, `closed: bool = False` | `{ id, name, unit }` |
| `motifs.delete` | `id: str` | `None` |
| `motifs.export` | `id: str`, `dest: str` | `{ path }` |
| `motifs.import` | `path: str` | `{ id, name, unit }` |

## 6. Step 0 (session lead, committed before workers start)

1. `git switch -c phase-06/fills-and-stitch-quality`.
2. The four `tatami()` arguments and `forced_xs` in 5.1, each defaulting to today's behavior. Run the engine suite after each one. `digitize.json` must not change.
3. `generate_parts`, `FillPattern.parts` and `covers`, and blocks per part in `_object_blocks` (5.2). Add `test_one_part_objects_are_unchanged` and `test_threads_k_overrides_slot_k` (with a throwaway two-part pattern) to `test_seams_engine.py`.
4. Geometry key `carve`: add it wherever the engine walks geometry keys (`transform_geometry`; not `geometry_points`, so carve lines never change a shape's bounds) and in the UI's node helpers in `design/layout.ts` (`objectNodeLists`, `mapObjectNodes`, `mapObjectPoints`).
5. `design/types.ts`: 5.3. `design/fillPatterns.ts`: the type additions, and an entry for each of `blend`, `motif`, `maze`, `ripple`, `mesh` with the fields given in section 7.
6. Engine stubs: every file in 5.4, each registered (fills with a generator that raises `DigitizeError("not built yet")`). `methods/motifs.py` stubs; five names in `rpc_methods.json`.
7. `fabrics.py`: add `push_comp_mm` to each fabric (woven 0.2, denim 0.15, knit 0.3, fleece 0.3, towel 0.3, stretch 0.35, felt 0.1). Data only; nothing reads it yet.
8. Feature flags in `project.py`: `push_comp`, `fill_weave`, `fill_carve`, `fill_feather`, `hand_look`, `fill_blend`, `fill_turning`, `fill_motif`, `fill_maze`, `fill_ripple`, `fill_mesh`, `user_motifs`. Each is detected from the field that turns it on.
9. UI stubs: `cmd/fills.ts` with `object.addAngle`, `object.carve`, `motif.library`; `components/MotifDialog.tsx` registered as dialog "motifs"; `feat/carve.ts`, `feat/angleLines.ts`, `feat/motifs.ts` with stub exports.
10. `python scripts/kb_commands.py`, `python scripts/check.py`, commit "Phase 6: contracts".

## 7. Tracks

A, B and C run together. Worker rules are in `BUILDPLAN.md`. Every new stitch type's tests include `assert_sane`, `assert_deterministic` and `assert_moves_with_shape` from `invariants.py`; the tables below list what is specific to each.

---

### Track A: the rows engine (Hard)

**Owns:** `digitize/rows/**`, the parts of `digitize/stitches.py` that read the new settings (`FillParams`, `SatinParams`, `RunParams`, `satin_from_pairs`, `running`), `digitize/fills/builtin.py` (the `rows` function of tatami, gradient and wave), `fabrics.py` (`apply` only), `feat/carve.ts`, the Advanced fold in `components/ObjectPanel.tsx`, the push switch in `components/QualityPanel.tsx`, new `engine/tests/test_rows.py`, snapshot suite `rows`.

#### P6-A1 Push compensation: **held until decision 1**

**Plain words in the app:** "End trim". Hint: "Push compensation. Stitching pushes the fabric out past the first and last rows, so shapes come out longer than drawn. This draws them a little shorter there."

**Behavior.** A design-wide switch under the fabric picker, "Allow for push at the ends", on for new designs (decision 2). The amount comes from the fabric (Step 0's table). A shape can set its own in Advanced: End trim, 0 to 1.5 mm, with "Back to Auto".

**Fills** (`rows/push.py`): shrink the shape along the direction the rows stack, by the amount at every edge that faces that direction: `poly ∩ shift(poly, +p·n) ∩ shift(poly, −p·n)`, where `n` is the unit vector across the rows. A U shape is trimmed at both tops, a ring inside and out. If the result is empty or under `MIN_PART_MM2`, the shape is left alone with a warning ("too small for End trim").

**Satins:** an open column loses the rungs within the amount of each end, measured along its center line. Closed ribbons are not trimmed. A column shorter than three times the amount is left alone.

`fabrics.apply` sets `push_comp_mm` from the fabric when the design's switch is on and the shape has none of its own.

#### P6-A2 Weave

How the needle points of neighboring rows line up. In Advanced, a select "Weave":

| Value | Offsets by row (fraction of a stitch) | Looks like |
| --- | --- | --- |
| standard | 0, ⅓, ⅔ | today's fill |
| brick | 0, ½ | brickwork |
| twill | 0, ¼, ½, ¾ | fine diagonal lines |
| smooth | 0, ⅖, ⅘, ⅕, ⅗ | no visible lines |
| random | a repeatable pseudo-random value per row | matte, no pattern |

`rows/weave.py` returns the `offsets` function. Applies to tatami, gradient and blend. Wave keeps its own rule (rows copy each other).

#### P6-A3 Carved lines

**Behavior.** `object.carve` (`Shift+C`) with a fill selected: draw a line over it with the pen (same clicks as any line); Enter finishes; draw another or press Esc. Every row drops a needle exactly where it crosses a carved line, so the line shows as a groove. Lines live in `geometry.carve`, move and resize with the shape, and are edited as points like a hole. "Remove carved lines" sits in the shape's ⋯ menu.

**Algorithm** (`rows/carve.py`): flatten each carved line into the rows' turned frame once. `forced(y, x0, x1)` returns where the horizontal line at `y` crosses any of them, keeping crossings at least 0.4 mm inside the row's ends. Where a carved segment runs within 15° of the rows it cannot be crossed cleanly; if more than a third of a line's length is like that, warn: "A carved line that runs along the stitch rows won't show. Turn the fill's angle or the line."

Applies to rows-kind patterns. On other patterns the command says why not.

#### P6-A4 Feathered edges

In Advanced: "Feather" (Off / Left ends / Right ends / Both) and "Depth" (0.5 to 6 mm, default 2). Each row's end on a feathered side is pulled in by `depth × (0.25 + 0.75·j)`, `j` a repeatable value in 0..1 for that row, so the edge is ragged and blends into what is beside it (fur, shading). `rows/ends.py` returns the `end_shift` function. On automatic underlay a feathered fill has no edge run (it would show beyond the short rows).

"Left" and "right" are as the rows run at angle 0; the panel shows a small picture of which side.

#### P6-A5 Hand-sewn look

One slider in Advanced on lines, satins and fills: "Hand-sewn look", 0 to 100%. All changes are repeatable (the same design always gives the same stitches).

| Kind | At 100% |
| --- | --- |
| Line (single, triple, bean) | each stitch length varies ±30%; each needle point moves up to 0.25 mm sideways |
| Satin | each rung's ends move up to 0.3 mm along the rung; spacing varies ±20% |
| Fill (rows kind) | row ends move ±0.6 mm; needle points move as Random 50% does |

#### Track A tests (`test_rows.py`)

| Test | Asserts |
| --- | --- |
| `test_push_shortens_across_the_rows_only` | 40 × 20 mm fill at 0°: stitched height = 20 − 2p ± 0.2; width unchanged ± 0.2 |
| `test_push_trims_both_tops_of_a_U` | |
| `test_push_on_a_satin_drops_end_rungs` | length shorter by 2p ± spacing |
| `test_push_leaves_tiny_shapes_with_a_warning` | |
| `test_old_object_without_the_design_switch_is_unchanged` | |
| `test_fabric_sets_push_when_switch_is_on` | knit → 0.3 |
| `test_each_weave_has_its_offsets` | needle x positions modulo the stitch, per row |
| `test_weave_standard_equals_today` | records equal to the `fill_square_45` snapshot case |
| `test_every_row_has_a_needle_on_the_carved_line` | distance from the line to the nearest needle point of each crossing row ≤ 0.05 mm |
| `test_no_grid_point_crowds_a_carved_point` | none within 0.8 mm |
| `test_carve_along_the_rows_warns` | |
| `test_carve_moves_and_resizes_with_the_shape` | |
| `test_carve_does_not_change_bounds` | |
| `test_feather_shortens_only_the_chosen_side` | the other side's ends are unchanged |
| `test_feather_depth_is_respected` | no end pulled in more than `depth` |
| `test_feathered_fill_has_no_edge_run_on_automatic` | |
| `test_hand_look_is_repeatable_and_bounded` | for each kind: within the table's limits; two runs equal |
| `test_hand_look_zero_is_unchanged` | |
| `test_snapshots` | suite `rows`: `push_0_3`, `weave_brick`, `weave_twill`, `weave_smooth`, `carve_cross`, `feather_both`, `hand_fill_60`, `hand_satin_60`, `hand_run_60` |

UI: `ObjectPanel.dom.test.tsx` gains "Weave, Feather and Hand-sewn look appear under Advanced for a tatami fill and not for stipple"; `feat/carve.test.ts` (a finished pen line lands in `geometry.carve`).

---

### Track B: motif fill, my motifs, maze, ripple, mesh

**Owns:** `digitize/fills/motif.py`, `maze.py`, `ripple.py`, `mesh.py`, `motifs.py`, `methods/motifs.py`, the motif lookup in `digitize/lines/` (reading `motif_unit`), `components/MotifDialog.tsx`, `feat/motifs.ts`, the motif select in `components/ObjectPanel.tsx` (a small `MotifSelect` component of its own file, `components/MotifSelect.tsx`), new `engine/tests/test_fills_decorative.py`, `test_motifs.py`, snapshot suite `fills_decorative`.

#### P6-B1 Motif fill

Rows of a motif across the shape. Open pattern with Angle (`open`, `noSpacing`, `angle`).

| Field | Label | Default | Range |
| --- | --- | --- | --- |
| `motif` | Motif | wave | built-in and My motifs |
| `motif_mm` | Repeat | 5 | 1.5 to 20 |
| `motif_width_mm` | Height | 4 | 0.5 to 10 |
| `motif_gap_mm` | Row gap | 0.5 | 0 to 10 |
| `motif_stagger` | Shift alternate rows | 0.5 | 0 to 1 |

**Algorithm:** rows across the shape at the angle, `motif_width_mm + motif_gap_mm` apart. On each row, lay whole repeats (`motif_points`) starting at a phase that centers them, alternate rows shifted by `motif_stagger × motif_mm`; clip to the shape; drop pieces under half a repeat. Sew the rows back and forth; `_sew_paths` joins them inside the shape. `step_mm2` = `(motif_width_mm + motif_gap_mm) × 2`.

#### P6-B2 My motifs

`motif.library` (`Alt+Shift+M`) opens "Motifs": the built-in ones and the user's, each drawn as two repeats. Buttons: **Save the selected line as a motif…** (needs one line selected), Import…, Export…, Delete (the user's only).

Saving turns the line into one repeat: its first point goes to (0, 0) and its last to (1, 0), everything scaled by the same factor, so its proportions hold. The first and last point must be at least 2 mm apart ("A motif runs from where it starts to where it ends; draw it left to right"), and the line may have at most 200 points after flattening. It is stored as `motifs/<slug>.json` in the data folder: `{ "format": "ludd-motif", "version": 1, "name": …, "unit": [[x, y], …] }`.

A shape that uses a user motif carries a copy (`params.motif = "user:<slug>"`, `params.motif_unit = [...]`), so a project opens anywhere. The engine uses `motif_unit` when present and checks it (finite numbers, at most 200 points). `MotifSelect` lists built-in and user motifs for motif lines and motif fills alike.

#### P6-B3 Maze fill

One path that winds into the shape and back out between its own turns, never crossing itself. Open, `noSpacing`.

| Field | Label | Default | Range |
| --- | --- | --- | --- |
| `maze_mm` | Path spacing | 2 | 0.8 to 6 |

**Algorithm:** rings following the outline inward every `maze_mm` (the ring code behind `contour_paths`). Odd rings (1st, 3rd, …) are linked into one inward spiral: each ring is opened next to where the one before it was opened, and joined to it by a short diagonal. Even rings are linked the same way and sewn outward. The inward spiral's inner end joins the outward spiral's inner end. Where the inward offsets split a shape into pieces (a neck), each piece gets its own maze and they are joined by travel along the outer ring; more than four pieces warns: "This shape is too branched for one maze; Contour may suit it better."

#### P6-B4 Ripple fill

Rings spreading from a point, like a drop in water. Open, `noSpacing`.

| Field | Label | Default | Range |
| --- | --- | --- | --- |
| `ripple_mm` | Ring spacing | 2 | 0.6 to 8 |

Center: `ripple_center` if set (in the shape's frame), else the middle found as Spiral finds it. Circles at `k × ripple_mm`, sampled so no chord strays more than 0.1 mm, clipped to the shape, sewn from the center out; arcs of one ring are joined inside the shape.

#### P6-B5 Mesh fill

A net of two sets of lines. Open with Angle (`open`, `noSpacing`, `angle`).

| Field | Label | Default | Range |
| --- | --- | --- | --- |
| `mesh_mm` | Cell size | 3 | 1 to 10 |
| `mesh_cross_deg` | Crossing angle | 90 | 45 to 90 |

Lines at the angle every `mesh_mm`, then lines at angle + `mesh_cross_deg`, each set sewn back and forth and joined along the edge. Phase 8's freestanding lace builds on this.

#### Track B tests

| Test (file) | Asserts |
| --- | --- |
| `test_motif_rows_are_evenly_spaced_and_staggered` (`test_fills_decorative.py`) | row gap and alternate shift as set |
| `test_motif_fill_keeps_whole_repeats_inside` | `assert_sane(inside=shape, tolerance_mm=0.3)` |
| `test_motif_fill_with_a_user_unit` | uses `motif_unit` |
| `test_maze_is_one_path_that_never_crosses` | a 40 mm square: no jumps or trims; the stitch line is simple (`LineString.is_simple`) |
| `test_maze_starts_and_ends_at_the_edge` | both within `maze_mm` of the outline |
| `test_maze_spacing` | neighboring turns `maze_mm` ± 0.3 apart on a ray from the middle |
| `test_branched_shape_warns` | |
| `test_ripple_rings_are_circles_about_the_center` | radii are multiples of `ripple_mm` ± 0.15 |
| `test_ripple_center_can_be_set` | |
| `test_mesh_has_two_directions` | stitch directions cluster at the angle and at angle + cross |
| `test_mesh_cell_size` | |
| `test_snapshots` | suite `fills_decorative`: `motif_wave`, `motif_user`, `maze_square`, `maze_star`, `ripple_square`, `mesh_90`, `mesh_60` |
| `test_save_normalizes_to_a_unit` (`test_motifs.py`) | first (0, 0), last (1, 0), proportions kept |
| `test_save_refuses_a_closed_or_tiny_line` | plain-words message |
| `test_list_has_builtins_and_mine`, `test_delete_only_mine` | |
| `test_export_import_round_trip` | |
| `test_shape_carries_its_motif` | **done-when 4**: render with the motif folder emptied |
| `test_bad_motif_unit_is_refused` | 300 points; a NaN |

UI: `components/MotifDialog.dom.test.tsx` (Save disabled without a line selected; a saved motif appears in `MotifSelect`).

---

### Track C: blend and turning fills (Hard)

**Owns:** `digitize/fills/blend.py`, `digitize/fills/turning.py`, `feat/angleLines.ts`, the blend thread pickers (`components/BlendThreads.tsx`), the direction-dot drawing for several lines (a canvas overlay in `feat/angleLines.ts`; the existing single-line dots in `StitchCanvas.tsx` stay), new `engine/tests/test_fill_blend.py`, `test_fill_turning.py`, snapshot suites `fill_blend`, `fill_turning`.

#### P6-C1 Blend

**Behavior.** Pattern "Blend": the shape's color fades into a second (and optionally a third) across the rows. Each color is its own set of rows; where one thins out the next thickens, so together they cover like one fill. Rows kind (Angle, Random, Weave and Edge pad all apply).

**Panel.** Pattern → Blend shows: the second color's thread button, "Add a color" (up to three in all), "Swap the colors", Balance (a slider: which color takes more of the shape). Density sets the combined coverage.

**Row placement** (`blend.py`). Across the shape, `t` runs 0 to 1 over the height `H` in the turned frame; combined density `ρ = 1 / spacing_mm`.
- Two colors: color 1 has density `ρ·(1 − t^γ)`, color 2 `ρ·t^γ`, with `γ = 2^(−blend_balance)`.
- Three: triangular weights peaking at `t = 0`, `0.5` and `1`.
- A color's rows sit where its cumulative density passes each whole number. For two colors at balance 0 that is `y = H·(1 − sqrt(1 − 2k/(ρH)))` for color 1 and `y = H·sqrt(2k/(ρH))` for color 2.
- Rows of a color more than 4 mm from that color's nearest other row are dropped (no lone threads).
- A row of one color within 0.15 mm of a row of another is moved to 0.15 mm away.

Each color is one part (`parts`), sewn with `tatami(…, row_ys=its rows)`, colors in order. On automatic underlay a blend has none (an edge run in color 1 would show along color 2's side), as a gradient has no cross-hatch.

**Tests** (`test_fill_blend.py`):

| Test | Asserts |
| --- | --- |
| `test_two_parts_in_two_threads` | two blocks, the object's thread then `blend[0]` |
| `test_combined_density_is_even` | **done-when 2**: rows of both colors counted in five bands across the shape: each band within 15% of the one-color fill |
| `test_each_color_fades_the_right_way` | color 1's row count falls band to band; color 2's rises |
| `test_balance_shifts_the_meeting_point` | |
| `test_three_colors_peak_at_start_middle_end` | |
| `test_rows_never_coincide` | no two rows of different colors within 0.14 mm |
| `test_no_lone_rows` | |
| `test_swap_reverses` | |
| `test_color_sort_keeps_the_two_parts_in_order` | with `color_sort` on |
| `test_order_and_colors_can_recolor_each_part` | `threads[1]` |
| `test_snapshots` | suite `fill_blend`: `two_colors`, `three_colors`, `balance_0_6`, `blend_twill` |

#### P6-C2 Turning fills

**Behavior.** A fill can have more than one angle line. `object.angle` (`I`) sets the first as today; `object.addAngle` (`Shift+I`) draws another. With two or more, the rows turn smoothly to follow each line where it lies (a leaf whose stitches fan, a ribbon that bends). The Angle box shows "Follows N lines" with "Back to one angle". Each line shows its purple dots and can be dragged; right-click a line to remove it.

**Algorithm** (`turning.py`; if code is adapted from Ink/Stitch's guided fill, keep its copyright notice in the header, per D-005).
1. Order the lines along the principal axis of their midpoints.
2. Guide curve: a smooth curve through each line's midpoint, running in that line's direction there (cubic Hermite), carried straight on past both ends beyond the shape.
3. Rows: parallel copies of the guide at `k × spacing` to both sides (`shapely.offset_curve`), as far as the shape reaches.
4. Clip each to the shape grown by half the Edge pad; drop pieces under `MIN_STITCH_MM`.
5. Needle points along each piece every `stitch_mm`, shifted by the weave's offset for that row, measured from where the row meets a fixed line across the guide (so the brick pattern holds as rows curve).
6. Sew row by row, alternating direction; where the next piece starts more than a stitch away, `travel()` inside the shape.
7. If an offset curve loops on itself (the guide turns tighter than the shape is wide there), stop adding rows on that side and warn: "The stitch direction turns too sharply for this shape here. Move the angle lines further apart or make the turn gentler."

Registered through the tatami pattern: when `angle_lines` has two or more entries, tatami's generator hands over to `turning.rows`. Cross-hatch underlay uses the mean direction + 90°. Start and end dots: the start is honored; the end is the last row's end nearest the red dot.

**Tests** (`test_fill_turning.py`):

| Test | Asserts |
| --- | --- |
| `test_one_line_is_the_plain_fill` | records equal to a tatami at that angle |
| `test_rows_follow_each_line` | **done-when 3**: at each line's midpoint the nearest row's direction is within 5° of the line |
| `test_spacing_holds_across_the_turn` | neighbor rows `spacing` ± 20% apart, measured at ten places |
| `test_coverage` | `coverage(recs, shape, spacing) ≥ 0.97` |
| `test_too_sharp_a_turn_warns_and_still_fills_most` | coverage ≥ 0.8 with the warning |
| `test_lines_move_and_turn_with_the_shape` | |
| `test_removing_down_to_one_line_goes_back` | |
| `test_snapshots` | suite `fill_turning`: `leaf_two_lines`, `ribbon_three_lines`, `fan_60` |

UI: `feat/angleLines.test.ts` (adding, dragging and removing lines edits `angle_lines`; "Back to one angle" keeps the first line's angle).

If, after two honest attempts, rows cannot hold spacing across a 60° turn, stop (two-strike rule): ship turning fills limited to 30° between neighboring lines, with the limit stated in the panel and in L-042.

## 8. Integration (session lead)

1. Merge B, then A, then C. `python scripts/check.py` after each. `digitize.json` unchanged.
2. Golden round trips: add each new pattern to a parametrized test that renders a 30 mm square, exports PES and JEF, reopens and compares stitch counts (`test_golden.py` style, new file `test_golden_fills.py`).
3. One combined test: a blend with twill weave, a carved line and a feathered side renders and passes `assert_sane`.
4. Docs (section 9), `python scripts/kb_commands.py`, `python scripts/check.py --all`.

## 9. Docs payload

**Knowledge base:**

| ID | Entry |
| --- | --- |
| F-1309 | End trim (push compensation): only if A1 was built |
| F-1310 | Blend |
| F-1311 | Motif fill and My motifs |
| F-1312 | Maze, ripple and mesh fills |
| F-1313 | Carved lines |
| F-1314 | Hand-sewn look |
| F-1315 | Turning fills (several angle lines) |
| F-1316 | Feathered edges |
| F-1305, F-1303, F-1306 | Fill patterns, the settings table, line styles and motifs: updated (weave; user motifs) |
| L-001 | Two-color blend: now YES |
| L-040 | Blend fades across the rows only, not along them |
| L-041 | Carved lines show only where rows cross them; not on open patterns |
| L-042 | Turning fills: how sharp a turn they take (as shipped) |
| L-043 | Maze on branched shapes sews as several mazes |
| L-044 | Push compensation: NO, if A1 was held, with the reason |
| T-031 | "My carved line doesn't show" → turn the angle |
| T-032 | "Blend looks stripy" → raise density or change Weave to Smooth |
| T-033 | "My motif isn't on another computer" → it travels with the shape; re-save to add it to the list |
| T-034 | "Shapes come out longer than I drew" → End trim (if built) |

Index rows for each new "Can LUDD…"; the blend row flips to YES. History row; *Last updated*.

**USER-MANUAL** section 6: one part per item, with a small picture of each pattern. **helpdocs.py** likewise, short.

**Stitch-out rows:**

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 6 | **Blend** | A 50 × 30 mm rectangle, red into yellow; the same with three colors | An even fade with no stripes or bare fabric; not stiffer than a plain fill |
| Phase 6 | **End trim** (if built) | A 30 mm square fill and a 5 × 40 mm satin, with and without, on cotton and on a T-shirt | With it, the sewn shape measures what was drawn |
| Phase 6 | **Weave** | The same square in Standard, Brick, Twill and Smooth | Each looks as named; Smooth shows no lines |
| Phase 6 | **Carved lines** | A 40 mm fill with a carved star and a carved wavy line | Grooves clear and unbroken; no loose stitches beside them |
| Phase 6 | **Feather and hand-sewn** | Two fills feathered into each other; a line, satin and fill at 60% hand-sewn | Soft join with no gap; the hand-sewn pieces look deliberately irregular, nothing loose |
| Phase 6 | **Motif fill, maze, ripple, mesh** | A 40 mm circle in each | Each lies flat; the maze has no crossing; mesh cells are even |
| Phase 6 | **Turning fill** | A leaf with two angle lines 50° apart | Stitches fan smoothly; no bunching inside the turn, no gaps outside it |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| A Step 0 hook changes `tatami()` output | `digitize.json` differs | Revert that hook and add it again behind an `if hook is not None` branch that leaves the old code path untouched |
| Blend rows of two colors pile up and pucker | the density test fails, or the stitch-out is stiff | The 15% band test is the guard; lower each color's peak density by 10% and note it for Phase 16 |
| `offset_curve` misbehaves on tight guides | loops, missing rows | Step 7's stop-and-warn; the 30° limit as the shipped fallback |
| Maze linking fails on shapes with holes | crossing path in a test | Holes split the rings: treat a shape with holes as branched (several mazes) |
| Three heavy tracks overrun the session | context runs short | Order of value: C1 (blend), A2–A5, B, C2. Stop after any merge with the branch green and say what is left |
| Both decisions on A1 unanswered | – | A1 held; nothing else depends on it |

## 11. Handoff

Write: whether A1 was built and how decision 2 went; the blend density numbers from `test_combined_density_is_even`; the turn limit turning fills shipped with; whether any Ink/Stitch code was adapted (file and notice). Phase 7's branching and Phase 8's lace both read this.

## 12. Build notes (2026-11-26)

- Handoff (section 11): **A1 (push compensation) is not built** (decision 1 is unanswered, so decision 2 wasn't needed): its stub refuses a shape that asks for it, its control stays hidden, there is no `push_comp` feature flag (a project from a LUDD that has it is refused), and F-1309, T-034 and the End trim stitch-out row are left out. Blend density (`test_combined_density_is_even`): rows per band 20, 20, 20, 20, 20 for the blend and for one color, 0.0% apart at worst (also on the shape resized to 0.6× and 2×). Turning fills ship with **no turn limit** (lines 60° apart work; at each line the nearest row is off by 0.2° and 0.1° on `fan_60`, 1.7° and 0.0° on the leaf, 1.1°, 0.8° and 0.3° on the ribbon). **No Ink/Stitch code was adapted** (turning fills were written from this spec).
- Done-when 1, exactly: the new patterns (blend, motif, maze, ripple, mesh) have registry and descriptor entries. Weave, carved lines, feather, the hand-sewn look and turning are settings, not patterns, so they have feature flags and panel controls but no registry or descriptor entry of their own. All have named tests, snapshots, invariants and PES and JEF round trips (`test_golden_fills.py`).
- Step 0: with any rows hook, rows more than a stitch step apart are not joined (a test found a 12.6 mm loose stitch), and equally good choices are rounded to six decimals (the plain path is untouched). `forced` gets `bend` on wave fills. `end_shift` splits long steps and widens the travel zone by any outward shift. `Param` takes a unit for its refusal messages. Beyond 5.3: `blend_flip`. Turning or mirroring a fill can turn its rows round (angles stay 0 to 179), which would swap the feathered side and a blend's ends on the shape, so the app swaps Left and Right and flips the blend to keep both in place (Gradient behaves as before). The knife, cut out and merge keep carved lines. New snapshot suites use `digest_recs_steady`, with last-digit tests; no older digest changed. Older tests changed: the RPC method count is 66 to 71, and lettering's last-digit test uses the shared `tests/steady_util.py`.
- A: no push tests or `push_0_3` snapshot. `assert_moves_with_shape` moves rows fills across their rows, top stitching only (a tatami's needle grid is fixed along the rows, older than this phase). Rows with new settings sew their cross-hatch steadily. A narrow feathered row keeps its full length or 1 mm; the hand-sewn look's travel may reach up to its own end shift outside the shape; satins take it once over their whole length (top stitching only); lines keep their ends and sharp corners; motif lines don't have it. The cross-hatch is cut back from a feathered side by the whole depth. `ObjectPanel.dom.test.tsx`'s row lists gained Weave, Feather and Hand-sewn look (still exact).
- B: the motif, mesh and ripple pieces are joined along the edges in the Spiral's order, so cut rings sew part by part outward (by Track B's measure, straight travel piled up to 53 threads in one spot; now at most 6). A maze splices pinched parts into one path and gives first-ring parts and holes their own mazes, with travel round the outer ring; stitches that don't meet stay 0.2 mm apart where any layout allows, never under 0.05 mm. Own simplify and corner finding, so every computer keeps the same points. A motif of your own sews as wide as Width says (`sewn_unit`, thinned to 0.1 mm), centered in its row; choosing it sets Width to the drawn proportions. Export includes built-ins; import needs a unit from 0 to 1. Refused: unit values over 1,000, a motif fill far beyond the stitch limit, a ripple middle over 2 m away. The ripple middle can't be set in the app.
- C: a blend's rows sit where the cumulative density passes k − ½ (so one color matches a plain fill's inset); lone rows are dropped only with two or more colors; a tiny shape sews plain rows in the first color; the rows are measured from the shape's corner, so they move with it; with three or more colors Balance warps t^γ; Swap flips its sign; Reverse reverses each color. Turning rows are the guide moved along its normals at (k + ½) × spacing (`shapely.offset_curve` gives pieces in no fixed order); Hermite tangents lengthen with the turn; a stitch more than 0.04 mm off its curve is split; the end is the row end nearest the red dot; one angle line alone is ignored; Shift+I is Tatami only.
- Integration: turning fills judge the carved-line warning against their curved rows, widen travel by the hand-sewn look's reach, sew the cross-hatch steadily (the leaf differed by 10 stitches under last-digit noise) and don't swap a feathered side. Ctrl+right-click closes a carved line. A maze in a shape with a hole says so in its own words. **Changed from step 7:** stopping a side at its first loop left a plausible second line covering only 18% of the app's own 60 × 42 mm rectangle, so rows are now cut only where they come nearer the guide than their own distance. The shape stays covered (97% or more in that case) with the same warning. Over the whole shape it lays about a plain fill's thread (1.01×); in 2 mm squares, 99% stay within 1.2× of a plain fill, and the densest, in the crease, has 1.6× (with the loops left in: 1.39× overall and 3× in the densest square). The test holds the whole shape to 1.15× and every 2 mm square to 1.8×. The fan and leaf test fills reach 1.2× and 1.33× in their densest squares.
- Looked at in the app (scratch data folder), and fixed: lines left over from Tatami still showed as active on other patterns (the panel claimed the rows followed them, the pattern's own dots were hidden and I changed nothing sewn); the drawing hint while carving; a turning fill's folded heading; Blend's Cross-hatch button, which sews nothing, is gone; the Motifs window is now also in the ⋯ menu and under the Motif list (before, only Alt+Shift+M opened it).

### After the first audit (at `34227e2`, not passed): fixes

- Fix 5: a motif export needs a full path and never writes into LUDD's data folder (before, `foo.json` landed in the engine's working folder, and `<data folder>\settings` replaced LUDD's `settings.json`).
