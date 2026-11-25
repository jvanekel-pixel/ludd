# Phase 4: Merge-safe stitch files

| | |
| --- | --- |
| Weight | Heavy. Do it on the larger plan. |
| Session lead | Sonnet 5.5 |
| Hard track | C (rebuild at a new size): give its worker the stronger model |
| Depends on | Phase 3 (render hooks, `methods/`, `cmd/`, dialog registry, `check.py`, invariants) |
| Parallel-safe with | Phases 5, 6, 9, 10, 11, 12 |
| Changes stitches | Yes, only where the user turns a repair on. A stitch file with no repair sews exactly as before. |
| Closes (compendium) | Remove hidden stitches ★ · Remove overlap · De-clump, sweep, density limit ★ · Small-stitch filter · Resize with density recalculated ★ · Insert stitches and jumps · Tie-offs both sides of a jump · Density map with a wireframe zoom |
| Old plan | Phase 5 |

## 1. Goal and done-when

The review's top-ranked gap: people merge and resize bought designs, the overlap turns into a hard lump that breaks needles, and Embrilliance sells the fix separately (Density Repair Kit). This phase makes a placed stitch file safe to merge and resize, without ever changing the file on disk: every repair is an edit stored on the item and applied when the design is drawn or saved.

**Done when:**

1. A stitch file scaled to 150% with "Rebuild stitches at this size" keeps its row spacing within 10% of the original, and at 60% likewise (tests in Track C).
2. Two overlapping drawn fills with "Don't sew what's hidden" sew no stitch of the lower one more than the keep margin inside the upper one, and the density map shows no cell over the limit where they overlap.
3. If the owner approves item A1: two overlapping PES designs save with the lower one's hidden stitches left out and no cell over the limit where they overlap.
4. "Repair this design…" shows before and after numbers and changes nothing until Accept.
5. `python scripts/check.py --all` prints `RESULT: PASS`.

## 2. Scope

| ID | Item | Changes stitches | Track |
| --- | --- | --- | --- |
| P4-S1 | Contracts: op types, stubs, flags, commands, empty modules | No | Step 0 |
| P4-A1 | Remove stitches of a placed stitch file hidden under what is sewn on top of it (**held until decision 1**) | Yes | A |
| P4-A2 | Don't sew what's hidden: drawn fills leave out the part covered by shapes on top | Yes | A |
| P4-B1 | Repair dialog, the panel's Repair section, "Fix it" on checks | No | B |
| P4-B2 | Remove tiny stitches (fixes, not only warns) | Yes | B |
| P4-B3 | Thin out spots where the needle hits over and over | Yes | B |
| P4-B4 | Edit stitches: insert a stitch, insert a jump, lock both sides of a jump | Yes | B |
| P4-B5 | Needle path view (wireframe) | No | B |
| P4-C1 | Recognize fills, satins and runs inside a stitch file | No | C |
| P4-C2 | Rebuild stitches at this size (narrows L-020) | Yes | C |
| P4-C3 | Limit density for this fabric | Yes | C |
| P4-Z1 | Docs, stitch-out rows, handoff | – | Integration |

**Out of scope:** turning stitches into editable shapes (Phase 13 reuses C1 for that); thinning layers inside one bought design; changing a bought design's stitch types.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | The competitive review says Embrilliance's "Remove Hidden Stitches" for merged stitch files is patented. May LUDD build A1? | Check the patent's number, dates and claims first (the owner's call, as with push compensation). A2 is a different thing: it trims LUDD's own drawn shapes by their outlines, which Wilcom, Bernina and Floriani all do. | A1 is **not built**. Its stub stays, its step is hidden in the dialog, and L-030 records the gap. Everything else in the phase is built. |
| 2 | Should repairs on a stitch file pin it to LUDD's private copy (as recolors and deletions do)? | No for the repairs that name no stitch (tiny stitches, clumps, density, rebuild, hidden); yes for inserts and jump locks, which name stitches by number. | As recommended. |
| 3 | Density limits per fabric (section 7, C3) are first guesses. Accept them until the stitch-outs? | Yes; they are constants in one file and are tuned in Phase 16. | As recommended. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Phase 3 is in | `git ls-files engine/threadline_engine/layout/passes.py scripts/check.py apps/desktop/src/cmd/index.ts` | three paths |
| Hooks exist | `grep -n "ITEM_OPS_LOCAL\|ITEM_OPS_PLACED\|AFTER_ITEMS" engine/threadline_engine/layout/passes.py` | all three |
| Ops still applied here | `grep -n "def _apply_ops\|def _move_stitches" engine/threadline_engine/layout/files.py` | both |
| Cover helper | `grep -n "def _cover\|COVER_CLOSE_MM" engine/threadline_engine/layout/joins.py` | both |
| Density constants | `grep -n "DENSE_MM_PER_MM2\|HITS_PER_MM2\|SHORT_MM" engine/threadline_engine/quality.py` | all three |
| Pinning rule | `grep -n "def has_edits" engine/threadline_engine/kept.py` | one |
| Samples to test on | `git ls-files samples/*.pes` | Flower, Star badge, Wreath |
| Baseline | `python scripts/check.py` | `RESULT: PASS` |

## 5. Architecture

### 5.1 Repairs are edits on the item

A placed stitch file already carries `ops` (delete a color, delete or move stitches, insert a stop or trim). Repairs are more ops. The file on disk is never touched, undo works as for any edit, and removing the op puts the stitches back.

```ts
// design/types.ts: added to LayoutOp
| { op: "filter_small"; min_mm: number }          // B2
| { op: "declump"; max_hits?: number }             // B3
| { op: "density_limit" }                          // C3: uses the layout's fabric
| { op: "rebuild" }                                // C2: at the item's current size
| { op: "remove_hidden"; keep_mm?: number }        // A1
| { op: "insert_stitch"; after: number; index: number; x_mm?: number; y_mm?: number }   // B4
| { op: "insert_jump"; after: number }             // B4
| { op: "lock_jump"; after: number }               // B4

// design/types.ts: added to Layout
remove_overlap?: { enabled: boolean; keep_mm: number };   // A2
```

An item holds at most one op of each repair name; setting it again replaces it. The UI writes repair ops in this fixed order so results never depend on click order: `rebuild`, `filter_small`, `declump`, `density_limit`, `remove_hidden`.

### 5.2 Where each runs in `render()`

| Stage (Phase 3 hook) | Ops | Frame |
| --- | --- | --- |
| inside `_apply_ops`, before deletes | `insert_stitch`, `insert_jump`, `lock_jump` | the file's own |
| `ITEM_OPS_LOCAL` | `rebuild` (takes over the scaling: sets `ctx.transform` scale to 1) | the file's own |
| `ITEM_OPS_PLACED` | `filter_small`, `declump`, `density_limit` | on the hoop, final size |
| `BEFORE_ITEMS` (new in Step 0) | `remove_overlap`: gives lower fills extra holes before any stitches are made | layout |
| `AFTER_ITEMS` | `remove_hidden` | on the hoop |

Records are `[x, y, kind, item, src]` with x and y in 0.1 mm. A repair keeps `src` on the records it keeps and writes `-1` on records it adds, so stitch editing still finds every original stitch by number.

### 5.3 Engine

```
engine/threadline_engine/repair/
  __init__.py     registers every op and pass (written in Step 0)
  small.py        B2 filter_small
  clumps.py       B3 declump
  stats.py        B1 numbers for the preview
  recognize.py    C1 fills, satins, runs in a stitch run
  rebuild.py      C2 rebuild
  density.py      C3 density_limit, the per-fabric limits
  hidden.py       A1 remove_hidden pass
  overlap.py      A2 remove_overlap (layout -> layout)
methods/repair.py   repair.preview
```

RPC, one method: `repair.preview(layout: dict, item_id: str, ops: list) -> dict`, a background method. It renders the layout as it is and again with the item's repair ops replaced by `ops`, and returns

```json
{ "before": { "stitches": 8410, "trims": 12, "jumps": 30, "tiny": 212, "longest_mm": 6.8, "densest": 3.9, "hits_max": 11 },
  "after":  { "…": "same keys" },
  "removed": [[1200, 1340], [5010, 5122]],
  "added": 96,
  "limit": 2.4,
  "notes": ["Rebuilt 86% of the stitches; the rest were resized as they are."] }
```

`removed` is ranges of `src` numbers (half-open), for the canvas highlight. `densest` is thread millimeters per mm² in the worst 1 mm cell, as `quality.py` measures it.

### 5.4 UI

```
apps/desktop/src/
  cmd/repair.ts                  the eleven commands (Step 0, stub handlers)
  feat/repair/steps.ts           registerRepairStep(), the list the dialog shows
  feat/repair/hidden.ts          A1 step + command handler
  feat/repair/tiny.ts            B2
  feat/repair/clumps.ts          B3
  feat/repair/density.ts         C3
  feat/repair/rebuild.ts         C2
  feat/overlap.ts                A2
  feat/stitchInsert.ts           B4
  feat/wireframe.ts              B5
  components/RepairDialog.tsx    B1, registered as dialog "repair"
  components/FilePanel.tsx       B1 adds the Repair section
```

A repair step is data plus one small control:

```ts
export type RepairStep = {
  id: string; op: LayoutOp["op"]; label: string; hint: string;
  visible(item: FileItem, info: LayoutItemInfo): boolean;
  preset(item: FileItem, info: LayoutItemInfo): boolean;          // ticked when the dialog opens?
  make(values: Record<string, number>): LayoutOp;
  fields: Field[];                                                 // Field from design/fillPatterns.ts
  summary(after: Stats, before: Stats): string;                    // "212 tiny stitches removed"
};
```

## 6. Step 0 (session lead, committed before workers start)

Contracts first, so three workers can build against fixed names.

1. `git switch -c phase-04/merge-safe-stitch-files`.
2. `design/types.ts`: the op and layout additions in 5.1.
3. `layout/passes.py` and `layout/render.py`: add `BEFORE_ITEMS: list[tuple[str, Callable[[dict], dict]]]` and `register_pass("before_items", …)`; `render()` runs them on the layout before the item loop. Empty, so nothing changes; add `test_before_items_starts_empty` to `test_seams_engine.py`.
4. `engine/threadline_engine/repair/`: every module in 5.3 with its function signature and a body that raises `LayoutError("not built yet")`; `__init__.py` registers them all (`register_item_op("rebuild", rebuild.apply, stage="local")`, and so on). `threadline_engine/__init__` or `layout/__init__` imports `repair` once so the registrations happen.
5. `methods/repair.py` with a stub `repair.preview`; import it in `methods/__init__.py`; add the name to `rpc_methods.json`.
6. `kept.py`: `INDEX_FREE_OPS = {"jumps_to_trims", "filter_small", "declump", "density_limit", "rebuild", "remove_hidden"}`; `has_edits` uses it (decision 2). Extend its existing test.
7. `project.py` feature flags: `stitch_repairs` (an item has any of `filter_small`, `declump`, `density_limit`, `rebuild`, `remove_hidden`), `stitch_inserts` (`insert_stitch`, `insert_jump`, `lock_jump`), `remove_overlap` (layout flag on).
8. UI stubs: every file in 5.4 with its exports as `() => info("Not built yet")`; `cmd/repair.ts` registering the eleven commands from the README table against those exports; one import line in `cmd/index.ts`.
9. `python scripts/kb_commands.py`, `python scripts/check.py`, commit "Phase 4: contracts".

## 7. Tracks

A, B and C run together. Worker rules are in `BUILDPLAN.md`.

---

### Track A: overlap

**Owns:** `repair/hidden.py`, `repair/overlap.py`, `feat/repair/hidden.ts`, `feat/overlap.ts`, new `engine/tests/test_repair_overlap.py`, new snapshot suite `repair_overlap`, one item in the toolbar's ⋯ menu (`components/Toolbar.tsx`).

#### P4-A2 Don't sew what's hidden (drawn shapes)

**Behavior.** One switch for the whole design, in the ⋯ menu beside "Hide moves under later stitching": "Don't sew what's hidden under shapes on top" (`object.removeOverlap`, `Alt+Shift+O`). On: a fill leaves out the part of itself that a shape sewn later covers, keeping a margin tucked under the edge so no fabric shows. It follows the shapes as they move. Off by default; old projects are unchanged.

**Setting.** `keep_mm`, "Keep under the edge", default 1.0, range 0.5 to 3. Shown under More options next to the switch.

**What counts.** The lower shape is a `fill` with a rows-kind pattern. A cover is a shape later in the sewing order that hides what is under it: a rows-kind fill or a satin with spacing of 0.6 mm or less after the fabric preset, lettering, or an applique (its fabric covers everything inside its outline). Open patterns and gradients cover nothing.

**Algorithm** (`repair/overlap.py`, registered as a `BEFORE_ITEMS` pass):
1. For each drawn item compute its outline in hoop millimeters (`dz.transform_geometry` then `fill_parts`; satin ribbons and columns by their two edges; lettering by its letter outlines from `text_letters`).
2. For each lower fill, `hidden = union(covers after it).buffer(-keep_mm) ∩ its own shape`.
3. Keep only pieces of `hidden` at least 9 mm² that survive `buffer(-1).buffer(1)` (drops slivers under 2 mm wide).
4. If anything is left, return the fill with those pieces added to `geometry.holes` (in the item's own frame: undo its transform). The stitch generator does the rest; the object cache keys on geometry, so unchanged shapes stay cached.
5. A fill that would be wholly hidden is left alone and a note says so: "<name> is completely hidden under <cover>. Delete it, or move it up in the sewing order."

**Tests** (`test_repair_overlap.py`):

| Test | Asserts |
| --- | --- |
| `test_off_by_default_changes_nothing` | render with and without the key are identical |
| `test_lower_fill_stops_under_the_cover` | 40 mm square under a 20 mm square: no lower stitch more than `keep_mm + 0.4` inside the upper outline |
| `test_margin_is_kept` | lower stitches reach at least `keep_mm − 0.3` inside the upper outline all the way round |
| `test_density_under_the_overlap_is_within_the_limit` | `quality.check(heatmap=True)`: no cell over the limit inside the upper square |
| `test_open_patterns_and_gradients_cover_nothing` | upper square in stipple: lower fill unchanged |
| `test_slivers_are_ignored` | covers overlapping by 1 mm: unchanged |
| `test_follows_the_cover_when_it_moves` | move the upper shape 10 mm: the hole moves 10 mm |
| `test_fully_hidden_fill_is_kept_with_a_note` | |
| `test_lettering_and_applique_count_as_covers` | |
| `test_snapshots` | suite `repair_overlap`: `square_under_square`, `fill_under_text`, `fill_under_applique` |

#### P4-A1 Remove hidden stitches (placed stitch files): **held until decision 1**

If approved, build it; if not, leave the stub and hide the step (`visible: () => false`).

**Behavior.** For a placed stitch file with the `remove_hidden` op, stitches lying under anything sewn after it are left out. It follows the things on top as they move. Only across items: layers inside one file are the designer's intent.

**Setting.** `keep_mm`, "Keep under the edge", default 0.8, range 0.3 to 3.

**Algorithm** (`repair/hidden.py`, an `AFTER_ITEMS` pass):
1. For each item carrying the op, `C = union(_cover(b) for b in blocks of later items).buffer(-keep_mm)`. `_cover` is cached by stitches. Skip if `C` is empty or its overlap with the item's footprint is under 9 mm².
2. In each of the item's blocks mark a stitch hidden when it, the stitch before and the stitch after all lie inside `C`. Stitches that cross the edge stay, so the tuck is real thread.
3. For each run of hidden stitches at least 3 long or 4 mm of path: remove it. If the straight line from the last kept stitch to the next kept stitch lies inside `C`, bridge it with running stitches every `TRAVEL_STITCH_MM` (they are covered, and a machine that cannot trim has nothing to snip). Otherwise lock off (`TIE_MM`), `TRIM`, `JUMP`, lock in. Shorter hidden runs stay.
4. Notes: how many stitches went and how many trims were added.

**Tests** (same file): `test_hidden_stitches_under_a_later_design_go`, `test_edge_stitches_stay`, `test_bridge_runs_under_the_cover_without_a_trim`, `test_trim_and_locks_where_no_hidden_route`, `test_only_across_items`, `test_color_sort_keeps_the_layering`, `test_density_where_they_overlap_is_within_the_limit` (two copies of `samples/Flower.pes`, 15 mm apart), snapshot `flower_under_flower`.

**Track A is done when** its tests pass and the two existing snapshot suites are unchanged.

---

### Track B: clean-up, editing and the Repair UI

**Owns:** `repair/small.py`, `repair/clumps.py`, `repair/stats.py`, `methods/repair.py`, the insert handling in `layout/files.py`, `quality.py` (fix text only), `components/RepairDialog.tsx`, `components/FilePanel.tsx`, `feat/repair/steps.ts`, `feat/repair/tiny.ts`, `feat/repair/clumps.ts`, `feat/stitchInsert.ts`, `feat/wireframe.ts`, `components/QualityPanel.tsx` ("Fix it"), the wire drawing in `components/StitchCanvas.tsx` (`drawStitches`), `showWire` in `store.ts` and `prefs.ts`, new `engine/tests/test_repair_cleanup.py`, `test_stitch_inserts.py`, snapshot suite `repair_cleanup`.

#### P4-B1 Repair dialog and panel section

`stitch.repair` (`Mod+Alt+D`) opens "Repair this design" for the selected stitch file. It lists every registered step that is `visible` for the item, each with a tick box, its one setting, and a live result line. Below: a before/after table (stitches, trims, tiny stitches, longest stitch, densest spot against the limit) from `repair.preview`, debounced 300 ms, and "Show on the design", which highlights the `removed` ranges in red through a canvas overlay. **Accept** writes the ops in the fixed order and closes. **Cancel** changes nothing. Esc is Cancel (`holdEscape`).

The file panel gains a "Repair" fold: the button, then one line per active repair with its result and a ✕ to remove it ("Tiny stitches removed (212) ✕").

Each direct command (`stitch.filterSmall` and the rest) turns its repair on with default values for the selected stitch file, or off if it is on, and says what happened in the notice bar. It is one undo step.

In the checks list, "very short stitches", "the needle hits one spot over and over" and "thick spots in a placed stitch file" gain a **Fix it** button that opens the dialog with that step ticked. `quality.py`'s fix text for those names the command.

#### P4-B2 Remove tiny stitches

**Setting.** `min_mm` "Shorter than", default 0.4, range 0.2 to 1.0, step 0.05.

**Algorithm** (`repair/small.py`, placed stage). Within each thread run (between jumps, trims, stops and color changes), walk the stitches; drop a stitch when it is closer than `min_mm` to the last kept one, unless it is one of the run's first three or last three stitches (lock stitches), or dropping it would make the joining stitch longer than `quality.LONG_MM`. The run's first and last points never move. Running it twice changes nothing more.

#### P4-B3 Thin out needle clumps

**Setting.** `max_hits` "Most needle hits in one spot", default 5, range 3 to 10.

**Algorithm** (`repair/clumps.py`, placed stage). Count needle hits per 0.5 mm cell for the item. In each cell over `max_hits`, a stitch may go if it is not one of its run's first or last three stitches, and either it lands within 0.15 mm of another stitch among the six before it, or dropping it moves the thread path by less than 0.3 mm and leaves no stitch over `LONG_MM`. Remove such stitches, latest first, until the cell is at the limit. Never remove more than 15% of the item's stitches; if the cap stops it, say so in a note.

#### P4-B4 Insert a stitch, insert a jump, lock a jump

In Edit stitches (`edit.stitches`), with one stitch selected:

| Command | Does | Op |
| --- | --- | --- |
| `stitch.insert` `Insert` | adds a stitch halfway to the next one, selected, ready to drag | `insert_stitch` with `index` = one more than the highest stitch number in use for this item |
| `stitch.insertJump` `Shift+Insert` | the move to the next stitch becomes a jump (no thread sewn across) | `insert_jump` |
| `stitch.lockJump` `Alt+Shift+T` | at the jump after this stitch: three lock stitches before it and three after, so the thread can be cut without unravelling | `lock_jump` |

Engine (`layout/files.py`): `_apply_ops` applies the three insert ops first, in list order, so later deletes and moves can name an inserted stitch by its `index`. `insert_stitch` adds `[x, y, STITCH, item, index]` after the record whose `src` is `after` (position from `x_mm`/`y_mm` in the file's frame, else the midpoint to the next stitch). `insert_jump` adds a `JUMP` record at the next stitch's position. `lock_jump` uses the lock geometry of `dz.tie_off` and `dz.tie_in` (`TIE_MM`). An op whose `after` no longer exists is skipped with the same kind of note stale stop-inserts get.

#### P4-B5 Needle path view

`view.wireframe` (`Shift+P`): thread drawn as hairlines with a dot at every needle point, whatever the zoom, so a dense spot on the density map can be read stitch by stitch. A view switch, remembered in prefs, in the ⋯ menu's view group. Works with the density map on.

#### Track B tests

| Test (file) | Asserts |
| --- | --- |
| `test_tiny_stitches_go_ends_stay` (`test_repair_cleanup.py`) | a 60 mm line with twenty 0.1–0.2 mm stitches sprinkled in: none under 0.4 left outside the first/last three; ends unmoved |
| `test_no_long_stitch_is_created` | |
| `test_filter_small_twice_is_the_same` | idempotent |
| `test_clump_at_a_star_center_is_thinned` | 30 stitches meeting at one point: hits in that cell ≤ 5; path moved ≤ 0.3 mm |
| `test_lock_stitches_survive_declump` | |
| `test_declump_caps_at_15_percent` | with a note |
| `test_untouched_file_sews_as_before` | no repair op: identical records |
| `test_preview_reports_before_and_after` (`test_rpc.py` style) | keys present; `removed` ranges match a hand count |
| `test_snapshots` | suite `repair_cleanup`: `tiny_line`, `star_clump` |
| `test_insert_stitch_lands_midway_and_can_be_moved` (`test_stitch_inserts.py`) | a later `move_stitches` on its `index` moves it |
| `test_inserted_stitch_can_be_deleted` | |
| `test_insert_jump_makes_the_move_a_jump` | |
| `test_lock_jump_adds_three_short_stitches_each_side` | each ≤ `TIE_MM + 0.05` |
| `test_stale_insert_is_skipped_with_a_note` | |
| `test_inserts_pin_the_file_repairs_do_not` (`test_project.py` style) | `kept.has_edits` |
| `repair dialog: Accept writes ops in the fixed order` (`components/RepairDialog.dom.test.tsx`) | |
| `repair dialog: Cancel writes nothing` | |
| `a hidden step is not listed` | |
| `file panel lists active repairs and removes one` (`components/FilePanel.dom.test.tsx`) | |

---

### Track C: rebuild at a new size (Hard)

**Owns:** `repair/recognize.py`, `repair/rebuild.py`, `repair/density.py`, the limits table in `fabrics.py`, `feat/repair/rebuild.ts`, `feat/repair/density.ts`, the resize warning text in `layout/render.py`, new `engine/tests/test_repair_rebuild.py`, snapshot suite `repair_rebuild`.

#### P4-C1 Recognize fills, satins and runs

`recognize(points: list[Point]) -> list[Span]` for one thread run (millimeters, the file's frame).

```python
@dataclass
class Span:
    kind: str            # "fill" | "satin" | "run" | "other"
    start: int           # first stitch index in the run
    end: int             # one past the last
    angle_deg: float | None = None       # fill: row direction, 0..180
    spacing_mm: float | None = None      # fill: between rows; satin: between stitches on one side
    stitch_mm: float | None = None       # fill and run: typical stitch length
    outline: list[Point] | None = None   # fill: left row ends, then right row ends reversed
    rail_a: list[Point] | None = None    # satin: even stitches
    rail_b: list[Point] | None = None    # satin: odd stitches
```

Steps, in this order, each claiming stitches the earlier ones left:

1. **Satin.** At least 8 consecutive stitches whose directions alternate (each turns more than 150° from the one before), 1 to 12 mm long, neighbors within a factor of 1.6 in length, and whose midpoints advance by 0.05 to 0.6 mm a step. Rails are the alternate points.
2. **Fill.** Rows: stitches running one way within 8°, 1.5 to 7 mm long, then a short step (0.2 to 1.2 mm) and a row back the other way. At least 4 rows with the same direction and a steady step make a fill. Angle is the median row direction; spacing the median step; outline from the row ends.
3. **Run.** At least 4 stitches of 1 to 5 mm, each turning less than 60°.
4. **Other.** Everything else, including lock stitches (groups of stitches under 1 mm).

Sparse rows (spacing over 1.2 mm) under a fill are underlay; they are recognized as fills with their own spacing and rebuilt the same way.

#### P4-C2 Rebuild stitches at this size

**Behavior.** For a resized stitch file, `stitch.rebuild` (`Alt+Shift+R`) remakes its fills, satins and runs at the new size with the original spacing and stitch length, so it is neither too dense nor too sparse. The dialog shows the step when the item is scaled by 10% or more and ticks it by default past 20%. The resize warning ("Beyond about ±20%…") gains "Rebuild stitches at this size (Alt+Shift+R) fixes this." and goes away once the op is on.

**Algorithm** (`repair/rebuild.py`, local stage). With scale `(sx, sy)` from `ctx.transform`:
1. For each thread run, `recognize`.
2. **Fill span:** scale its outline; turn its angle by the scale (`atan2(sin·sy, cos·sx)`); `tatami(poly, angle, spacing, stitch, 0.0, start_near=S, end_near=E)` where S and E are the span's first and last stitches, scaled. Join S to the first new stitch and the last to E with a stitch each when they are more than 0.3 mm apart.
3. **Satin span:** scale both rails; resample each to `n = ceil(length / spacing)` points; emit alternately, starting on the side the span started on.
4. **Run span:** scale the path; `paths.resample` at the original stitch length, keeping its sharp corners.
5. **Other:** scale as it is.
6. Write the result at final size, set `ctx.transform` scale to 1 (the turn, mirror and move still apply), and add a note: "Rebuilt N% of the stitches (fills, satins and lines); the rest were resized as they are." Under 50%: add "Most of this design couldn't be rebuilt, so check the density map."

New records carry `src = -1`; records in "other" spans keep theirs.

#### P4-C3 Limit density for this fabric

**Behavior.** `stitch.densityLimit` (`Alt+Shift+L`): fills and satins in the stitch file that are denser than the chosen fabric takes are remade at that fabric's normal spacing. Uses the design's "Stitching on" preset.

**Limits** (`repair/density.py`, from each fabric's `density` factor `d` in `fabrics.py`):

| | Rebuilt when spacing is under | Rebuilt to |
| --- | --- | --- |
| Fill | 0.33 / d | 0.40 / d |
| Satin | 0.30 / d | 0.36 / d |

So on woven cotton (d = 1.0) a 0.28 mm fill becomes 0.40; on T-shirt knit (d = 0.9), 0.44. Placed stage: recognize at final size, rebuild only the spans under the limit, exactly as C2 does with scale 1. If the densest spot is still over the limit afterwards, note: "Still thick where layers overlap."

#### Track C tests (`test_repair_rebuild.py`)

Ground truth comes from LUDD's own digitizer: make stitches from a known shape, then recognize them.

| Test | Asserts |
| --- | --- |
| `test_recognizes_a_tatami_square` | angle within 2°, spacing within 5%, outline overlap (IoU) ≥ 0.9 |
| `test_recognizes_fills_at_every_angle` | 0, 30, 45, 90, 135° |
| `test_recognizes_a_satin_column` | width within 0.3 mm, spacing within 10% |
| `test_recognizes_a_curved_satin_ribbon` | |
| `test_recognizes_a_run_and_leaves_locks_as_other` | |
| `test_rebuild_at_150_keeps_row_spacing` | recognized spacing of the result within 10% of the original; stitch count 2.25× ± 15%; bounds 1.5× ± 0.5 mm |
| `test_rebuild_at_60_keeps_row_spacing` | within 10%; count 0.36× ± 20% |
| `test_rebuild_keeps_first_and_last_stitch` | at their scaled places ± 0.5 mm |
| `test_rebuild_stretched_one_way_turns_the_angle` | scale 1.5 × 1.0 on a 45° fill |
| `test_unrecognized_parts_resize_as_before` | |
| `test_rebuild_then_turn_and_mirror` | the turn and mirror still apply once |
| `test_rebuild_sample_coverage` | `samples/Flower.pes` at 150%: at least 70% rebuilt; `assert_sane(max_stitch_mm=7.15)` |
| `test_rebuilt_sample_round_trips_pes_and_jef` | export, reopen, same stitch count |
| `test_density_limit_respaces_a_dense_fill` | 0.25 mm fill on knit → 0.44 ± 10% |
| `test_density_limit_leaves_normal_fills_alone` | |
| `test_snapshots` | suite `repair_rebuild`: `square_150`, `square_60`, `satin_150`, `flower_150` |

When `fixtures/` is present (the owner's own designs, never committed), a non-asserting test writes rebuild coverage per file to `_logs/rebuild-coverage.txt`. Read it; a bought design under 50% is worth a line in the handoff.

**Track C is done when** its tests pass. If recognition cannot reach the numbers on the samples after two honest attempts, stop (two-strike rule), ship C1 with what it recognizes, mark C2 as rebuilding "fills only", and write the gap in the handoff.

## 8. Integration (session lead)

1. Merge C, then B, then A. `python scripts/check.py` after each.
2. Open `samples/Flower.pes`, scale to 150%, apply Rebuild through `repair.preview` in a test or the dev app, and paste the before/after numbers into the handoff.
3. Docs (section 9), `python scripts/kb_commands.py`, `python scripts/check.py --all`.

## 9. Docs payload

**CHANGELOG** (under the current unreleased heading): one section "Phase 4: repair bought designs", one bullet per built item, each saying what the user does and where.

**Knowledge base:**

| ID | Entry | Status |
| --- | --- | --- |
| F-1902 | Repair this design (the dialog; hidden stitches if built) | YES |
| F-1903 | Remove tiny stitches; thin out needle clumps | YES |
| F-1904 | Limit density for the fabric | YES |
| F-1905 | Rebuild stitches at a new size | YES |
| F-1906 | Insert stitches and jumps; lock a jump | YES |
| F-1207 | Don't sew what's hidden under shapes on top | YES |
| F-407 | Needle path view | YES |
| F-1104 | Resizing stitch files | PARTIAL → YES with Rebuild; say what is not rebuilt |
| F-1901 | Edit stitches | add the three inserts |
| L-020 | Resizing bought designs a lot | narrowed: only parts that are not fills, satins or lines resize as they are |
| L-030 | Hidden stitches under a merged design | NO if A1 was held, with the reason; otherwise "only across designs, not inside one" |
| L-031 | Rebuild does not recognize motif fills, cross-stitch or programmed fill patterns | new |
| T-023 | "I resized a bought design and it's stiff / shows fabric" | → Rebuild |
| T-024 | "Two designs overlap and the needle breaks" | → Repair; Don't sew what's hidden |
| T-025 | "After a repair a gap shows at the edge" | → raise Keep under the edge |

Index rows (section 2): "resize a bought design?" becomes YES (F-1905); add "fix a design that is too dense?", "insert a stitch?", "stop sewing what's hidden under another shape?". History row; *Last updated*.

**USER-MANUAL:** a new part in section 5 or its own section "Repairing bought designs". **helpdocs.py:** the same, short, with the keys.

**Stitch-out rows** ("Pending machine tests"):

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 4 | **Rebuild at a new size** | A bought design at 150% and at 60%, each with Rebuild | Coverage like the original: not stiff at 60%, no fabric showing at 150%; satin edges smooth |
| Phase 4 | **Don't sew what's hidden** | A 40 mm fill with a 20 mm fill on top, switch on | No ridge or gap at the upper shape's edge; the overlap feels as thin as the rest |
| Phase 4 | **Tiny stitches and clumps** | A dense bought design with both repairs on | No thread nests; nothing unravels where stitches were removed |
| Phase 4 | **Locked jump** | A jump locked with Alt+Shift+T, cut by hand | Neither side pulls out |
| Phase 4 | **Density limit** | A dense bought design on a T-shirt with the T-shirt preset and the limit on | Less puckering than without; fills still cover |
| Phase 4 | **Hidden stitches under a merged design** (only if A1 was built) | Two designs overlapping by a third | No lump; no gap at the edge; no thread to snip under the top design |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Recognition misses real-world fills (bought designs use patterns LUDD's tatami does not) | low coverage on `fixtures/` | Ship anyway: coverage is reported to the user, and unrecognized parts behave as today. Log the worst files for Phase 13. |
| A2's extra holes bring out L-002 (a travel line on top of a fill with holes) | a snapshot shows travel across sewn rows | The hole is covered by the upper shape, so travel inside it is hidden; route travel through the hole first. If that fails, note it under L-002. |
| `repair.preview` is slow on big designs (two renders) | over 2 s on a 50,000-stitch design | Cache the "before" render by layout hash; it is the same until the layout changes. |
| Repairs interact badly with stitch editing numbers | a moved stitch lands elsewhere after a repair | Repairs keep `src`; the test `test_inserted_stitch_can_be_deleted` and its move twin guard this. |
| Decision 1 unanswered | – | A1 held; the phase still meets done-when 1, 2, 4 and 5. |

## 11. Handoff

Write: whether A1 was built; rebuild coverage on the three samples and, if run, the range on `fixtures/`; the density limit constants as shipped; anything Phase 13 (stitches to shapes) should know about `recognize.py`.

## 12. Build notes (2026-11-25)

- Step 0 beyond the spec: a before-items pass leaves its notes under `passes.NOTES_KEY`; each repair step's id is its op's name (Fix it opens steps by id); the two ⋯ entries, `showWire` and a panel slot (`components/OverlapOptions.tsx`, given to Track A) were added up front; the "hooks start empty" tests check a fresh copy of `passes.py`, since the repairs register at import; `_logs/*.txt` is git-ignored (the coverage report names the owner's designs). The command keeps the README title; its ⋯ entry says "Don't sew what's hidden under shapes on top".
- A1 not built (decision 1 unanswered): the stubs stay; a project that asked for it says "not built yet". If A1 is built, give it its own feature flag (it sits under `stitch_repairs` now).
- Done-when 2, second half, holds only past the keep margin: both shapes sew in the margin. With a 20 mm square on a 40 mm one, 76 of 400 cells are over the limit, all in the margin (109 with the switch off, 43 past the margin); the worst is 10.8 against 7 (9.9 off). Leaving the lower fill's edge run out round the cut gives 64 cells (26 with a 0.5 mm margin); that needs the generator to know which holes are cuts. `test_density_under_the_overlap_is_within_the_limit` checks past the margin.
- A2's cuts can bring a short travel line across sewn rows (L-002; about 19 mm in the square test). The risk table's fallback (route through the hole first) isn't enough: the router already takes a straight move that stays on the fill, across sewn rows. Preferring a covered route means cost-aware routing in `digitize/stitches.py`. Noted under L-002 instead.
- A2: a fill is "completely hidden" when none of it would show or nothing sewable would be left; the note names the cover that hides most. 400 overlapping shapes draw in about 12 s the first time (3 s off).
- B: declump takes the busiest spots first and measures 0.3 mm against the path before any removal; preview numbers are the item's own, hits per 0.5 mm spot, limit 7.0 (the 2.4 in 5.3 was an example); each side of a locked jump is three stitches from `tie_in`/`tie_off`; tiny stitches and clumps start unticked; Show on the design zooms and docks the dialog at the right; one preview per ticked repair, not cached (0.7 to 1.4 s each at 50,000 stitches).
- C: LUDD's own satins sew across, step along the edge and back, so satin recognition allows that step (`Span.stepped`); fill spacing is first row to last over the gaps; "Still thick" uses the checks' 7 mm/mm²; rebuild at 100% changes nothing.
- Integration fixes: `render()` passes a note list to `_apply_ops`, so stale-insert notes reach the design; stitches numbered -1 (rebuilt or lock stitches) can't be picked while editing (`design/stitchPick.ts`), and right-click selects the stitch first; the highlight says "taken out or made again" when a repair remakes; a shape changed by a before-items pass is measured whole (a half-covered 40 mm fill read 21 mm wide). Tests also check that shortest order and color sort keep the layering with the switch on.
