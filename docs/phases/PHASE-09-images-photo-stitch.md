# Phase 9: Images & photo stitch

| | |
| --- | --- |
| Weight | Heavy. Do it on the larger plan. |
| Session lead | Sonnet 5.5. Track B is **Hard: give this worker the stronger model.** |
| Audit | The usual phase gate. Photo stitch and cross-stitch output are judged on fabric in Phase 15. |
| Depends on | Phase 3 (fill registry, `methods/` groups, `cmd/`, dialogs, canvas hooks, `scripts/check.py`) |
| Changes stitches | Only new things: the `tone` and `crossgrid` fill patterns. Everything that exists sews as before (`cross_paths` is split in two with no change in output). |
| Closes (compendium) | Magic wand / smart fill by color · Color reduction before tracing · Photo stitch ★ · Cross-stitch from a picture · Export a realistic PNG · Design notes · Lighten or darken all colors. Lifts L-008. |

## 1. Goal and done-when

LUDD can trace a picture shape by shape or all at once, but it cannot pick "everything this color", let you choose the colors before digitizing, show how far a slow job has got, or turn a photo into stitches. This phase adds those, plus three small output tools: a PNG of the design for showing a customer, notes that travel with the project, and one-key lighten and darken.

**Done when:**

1. `python scripts/check.py --all` prints `RESULT: PASS`.
2. One wand click on the test picture gives a fill whose outline is within 1 mm of the true outline (`test_wand_square_matches_the_true_outline_within_1_mm`).
3. A five-color picture reduced to five colors, with two merged, digitizes to exactly four threads.
4. Whole-picture auto-digitize shows a progress bar, and Cancel stops the engine within one second.
5. A photo turned into a one-thread photo stitch sews darker where the photo is darker (coverage and darkness correlate at 0.8 or better), as ordinary fills you can reshape, and nothing is added before you press Add.
6. A 20 × 20 square picture becomes exactly the expected crosses per color.
7. Save a picture writes a PNG of the asked size; notes survive save and open and print on the thread list; lighten and darken change every color and undo in one step.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P9-S1 | Branch, stubs and shared-file edits (section 6) | No | Step 0 |
| P9-A1 | Progress and Cancel for background engine jobs; used by whole-picture auto-digitize | Yes | A |
| P9-A2 | Magic wand (`tool.wand`, `Z`) | Yes | A |
| P9-A3 | Simplify the picture's colors (`image.colors`, `Alt+C`) | Yes | A |
| P9-B1 | `tone` fill pattern: rows that open and close after a stored brightness map | Yes | B |
| P9-B2 | Photo stitch (`image.photoStitch`, `Alt+Shift+F`): one thread, or 4 to 8 threads light to dark | Yes | B |
| P9-B3 | `crossgrid` fill pattern and cross-stitch from a picture (`image.crossStitch`, `Alt+X`) | Yes | B |
| P9-C1 | Save a picture of the design as PNG (`file.exportPicture`, `Mod+Shift+G`) | Yes | C |
| P9-C2 | Design notes (`file.notes`, `Alt+N`) | Yes | C |
| P9-C3 | Lighten or darken all colors (`colors.lighten` `Alt+=`, `colors.darken` `Alt+-`) | Yes | C |
| P9-Z1 | Docs, frozen-engine smoke check, handoff | – | Integration |

**Out of scope:** PDF export (the print dialog already saves the template as PDF); half and quarter cross-stitches, French knots; random-direction "sfumato" photo stitch; cropping a picture; notes written into machine files; a true backstitch line style (Phase 7 owns it; the cross-stitch outline uses a running stitch until then).

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | `SPEC.md` lists photo stitch as out of scope. Allow it, as specified here (editable fills, preview then Add, no AI)? | Yes. It is in every large competitor, and this design keeps "objects are the source of truth". | Track B builds only P9-B3 (cross-stitch from a picture). P9-B1 and P9-B2 stay unchecked and `SPEC.md` is not touched. |
| 2 | Which threads does a color photo stitch pick from? | My threads when it holds at least as many spools as layers asked for, otherwise the chart Match used last. | That rule. |
| 3 | Largest picture a save may write? | 4,096 pixels on the long side (what every graphics card handles). | 4,096. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Phase 3 seams are in | `git ls-files engine/threadline_engine/digitize/fills/__init__.py apps/desktop/src/canvas/hooks.ts apps/desktop/src/dialogs.tsx scripts/check.py` | four paths |
| No progress or cancel yet | `grep -n "progress\|cancel" engine/threadline_engine/rpc.py` | nothing |
| The UI drops engine lines it did not ask for | `grep -n "if (!p) return" apps/desktop/src/engine/rpc.ts` | one match |
| Colors are simplified to 12 | `grep -n "SIMPLE_COLORS = 12" engine/threadline_engine/autotrace.py` | one match |
| Whole-picture preview state | `grep -n "autoAll:" apps/desktop/src/store.ts` | one match, with `shapes` and `busy` |
| Enter adds the whole-picture preview | `grep -n "autotrace.allAccept" apps/desktop/src/actions.ts` | one match |
| Cross-stitch paths are one function | `grep -n "def cross_paths" engine/threadline_engine/digitize/patterns.py` | one match |
| Shape params that move with the shape | `grep -n "start_mm" engine/threadline_engine/digitize/stitches.py apps/desktop/src/design/layout.ts` | both files (the anchors seam copies this) |
| Projects hold no notes | `grep -n "notes" engine/threadline_engine/project.py` | nothing |
| Pixi 8 | `grep -n '"pixi.js"' apps/desktop/package.json` | `^8` |
| Baseline is green | `python scripts/check.py` | `RESULT: PASS`; write the counts into the session notes |

## 5. Architecture

### 5.1 Engine

```
engine/threadline_engine/
  rpc.py                       + progress(), check_cancelled(), Cancelled, Dispatcher.cancel()
  autotrace.py                 + wand(), palette(), with_palette(); digitize_all(palette=…) reports progress
  picture/                     NEW package (Track B)
    photostitch.py             picture -> tone fills
    crossgrid.py               picture -> cross-stitch layers and outline runs
    maps.py                    pack and unpack maps (zlib + base64), sampling through anchors
  digitize/fills/tone.py       NEW pattern "tone"
  digitize/fills/crossgrid.py  NEW pattern "crossgrid"
  digitize/patterns.py         cross_paths split: cross_runs() + cross_paths_from_runs()
  output.py                    NEW: save a PNG the window rendered (Track C)
  methods/tracing.py           + trace.wand, trace.palette
  methods/core.py              + rpc.cancel
  methods/pictures.py          NEW group: image.photo_stitch, image.cross_stitch
  methods/output.py            NEW group: export.picture
```

### 5.2 Progress and cancel (the wire format)

- Engine to window, a line with no `id`: `{"jsonrpc":"2.0","method":"progress","params":{"id":17,"done":3,"total":12,"label":"Finding areas of color"}}`. `id` is the request it belongs to.
- Window to engine, an ordinary call: `rpc.cancel {"id": 17}` → `true` if that request was running.
- A cancelled job answers its own request with error code `-32001`, message `Cancelled`.
- Only `background=True` methods can report or be cancelled: a main-loop method finishes before the next line is read.
- The developer browser preview posts one request and reads one answer, so progress lines never reach it. Cancel still works there.

### 5.3 Data shapes

```ts
/** How dense the rows are, 0 (lightest) to 255 (densest), row by row from the top left. */
export type ToneMap = { w: number; h: number; data: string };          // data: base64 of zlib-packed bytes
/** Which squares of a cross-stitch grid this color fills: one bit per square, row by row. */
export type CrossGrid = { cols: number; rows: number; data: string };
/** Colors chosen for a picture in "Simplify the picture's colors". */
export type PicturePalette = { colors: number; merges: [number, number][]; swatches: string[];
  threads?: Record<number, Thread>; skip?: number[] };

FillParams  += tone_to_mm?: number; tone?: ToneMap; grid?: CrossGrid;
               anchors?: [number, number][];   // where the map's top-left, top-right and bottom-left corners lie, mm
RefImage    += palette?: PicturePalette;
Layout      += notes?: string;                 // up to 4,000 characters
FillPattern += "tone" | "crossgrid";
```

`anchors` are three points, so they move, turn, mirror and stretch with the shape like its nodes do. Feature flags: `fill_tone`, `fill_crossgrid`. A palette and notes do not change what is sewn, so they need no flag.

### 5.4 UI

```
apps/desktop/src/
  engine/rpc.ts                    callWithProgress(): { result, cancel }
  feat/wand.ts  feat/pictureColors.ts            Track A
  components/WandBar.tsx  components/PictureColorsDialog.tsx
  feat/pictureStitch.ts  canvas/draftOverlay.ts  Track B
  components/PhotoStitchDialog.tsx  CrossStitchDialog.tsx  PictureStitchBar.tsx
  feat/exportPicture.ts  feat/colorShift.ts  feat/notes.ts   Track C
  design/colorShift.ts  components/ExportPictureDialog.tsx  components/NotesField.tsx
  cmd/pictures.ts  cmd/pictureStitch.ts  cmd/output.ts
```

**One preview for everything.** The whole-picture preview (`store.autoAll`) already means "shapes waiting to be added or dismissed", with Enter to add and Esc to dismiss. The wand, photo stitch and cross-stitch all show their result there, so no new accept or dismiss commands are needed. Step 0 widens it to carry ready-made objects and a rendered preview.

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-09/images-photo-stitch` from `main`.
2. If decision 1 is yes: in `SPEC.md`, take "photo stitch" out of the out-of-scope line and add "photo stitch as editable fills" to what is in scope.
3. Engine seeds:
   - `rpc.py`: `class Cancelled(Exception)` with `rpc_code = -32001`; `progress(done, total, label="")` and `check_cancelled()` as functions that do nothing yet.
   - New `methods/pictures.py` and `methods/output.py`, imported by name in `methods/__init__.py`. Stubs that raise "not built yet": `rpc.cancel` (`core.py`), `trace.wand`, `trace.palette` (`tracing.py`), `image.photo_stitch`, `image.cross_stitch` (`pictures.py`), `export.picture` (`output.py`). The six names go in `rpc_methods.json`.
   - `digitize/fills/__init__.py`: `FillPattern.data_keys: tuple[str, ...] = ()`. `stitches.py`: `FillParams.data: dict[str, Any]`, filled in `from_dict` with the dict's values for the pattern's `data_keys`, untouched; `transform_geometry` maps each point of `params["anchors"]` the way it maps `start_mm`.
   - `project.ITEM_FEATURES`: `fill_tone`, `fill_crossgrid` (a fill or applique with that pattern).
4. UI seeds:
   - `design/types.ts`: everything in 5.3.
   - `design/layout.ts`: `mapObjectPoints` maps `params.anchors` too.
   - `design/fillPatterns.ts`: `FillPatternDef` gains `angle?: boolean` (an open pattern that keeps its Angle row) and `hidden?: boolean` (not offered in the Pattern list unless the shape already has it). `ObjectPanel.tsx` honors both.
   - `store.ts`: `autoAll` gains `source?: "whole" | "wand" | "photo" | "cross"`, `objects?` (ready-made shapes with their settings), `preview?: Design | null`, `title?: string`, `progress?: { done: number; total: number; label: string } | null`, `cancel?: (() => void) | null`. New `wand: { tolerance: number; everywhere: boolean } | null` with `setWand`.
   - `features.ts`: `acceptWholePicture()` adds `autoAll.objects` when present (one undo step, one group id); `endOtherModes` accepts `"wand"`.
   - `actions.ts`, one line: `autotrace.allAccept` is enabled when the preview has shapes **or objects**.
   - `engine/rpc.ts`: `callWithProgress(method, params, { timeoutMs?, onProgress? })` returning `{ result: Promise<T>; cancel(): void }`, for now a wrapper round `call`.
   - `components/ToolRail.tsx`: `DrawHint` picks the bar by `wand` and `autoAll.source`; stub files `WandBar.tsx` and `PictureStitchBar.tsx`.
   - `cmd/index.ts`: imports `./pictures`, `./pictureStitch`, `./output` (created empty).
5. Tests for the seeds, in `test_seams_engine.py` and `design/layout.test.ts`: `test_anchors_move_with_the_shape`, `test_data_keys_pass_through_untouched`, "moving a shape moves its anchors".
6. `python scripts/check.py`, then commit ("Phase 9: start"). Workers branch from this commit.

## 7. Tracks

A, B and C run together. Every worker follows "Worker rules" in `BUILDPLAN.md`.

---

### Track A: picture tools

**Owns:** `engine/threadline_engine/autotrace.py`, `rpc.py`, the `rpc.cancel`, `trace.wand` and `trace.palette` bodies, `apps/desktop/src/engine/rpc.ts`, `autoTrace.ts`, the whole-picture part of `features.ts`, `feat/wand.ts`, `feat/pictureColors.ts`, `components/WandBar.tsx`, `components/PictureColorsDialog.tsx`, `AutoTraceBar` and `WholePictureBar` in `components/ToolRail.tsx`, `cursors.ts`, `pictureMenu` in `contextMenu.ts`, `cmd/pictures.ts`, new tests. **Must not touch** `digitize/`, `picture/`, `components/InfoPanel.tsx`, `StitchCanvas.tsx`.

#### P9-A1 Progress and Cancel

Engine (`rpc.py`):
- `Dispatcher` keeps `_running: dict[id, threading.Event]` for background requests and sets a thread-local "current request" around the call in `handle_line`.
- `progress(done, total, label)` writes the notification through the same lock answers use (move the write lock from `serve` onto the dispatcher). At most one line per request every 100 ms; the last one (`done == total`) is always sent. With no writer attached (tests, main-loop methods) it does nothing.
- `check_cancelled()` raises `Cancelled` when the current request's event is set. `Dispatcher.cancel(id)` sets it and returns whether the request was running.
- `autotrace.digitize_all` reports three stages ("Reading the picture", "Finding areas of color" per patch, "Tracing the dark lines" per line) and calls `check_cancelled()` once per patch and per line.

Window (`engine/rpc.ts`): a line with `method: "progress"` goes to the pending call named by `params.id` and restarts that call's timeout; unknown ids are ignored. `cancel()` sends `rpc.cancel`; if no answer comes in 2 seconds the call is rejected locally.

`WholePictureBar` shows a progress bar with its label and a **Cancel** button while busy (the old sentence stays as the fallback when no progress arrives). Esc cancels the running job as well as dismissing.

#### P9-A2 Magic wand

**Behavior.** `Z` (or "Wand" in the Auto-trace bar and a picture's right-click menu) turns the pointer into a wand. Click a color in a picture: every pixel of that color joined to the click becomes a fill, shown as a preview. Shift+click adds another color or area; Alt+click drops the area under the pointer. Enter adds, Esc dismisses. It is a mode like the knife (`store.wand`), driven by `registerCanvasTool`, not a new entry in the tool rail.

**Settings (in the bar).** Tolerance 1 to 10, default 5 (− and + buttons). "Every area of this color" (off). "Up to the middle of dark outlines" (on).

**Engine.** `trace.wand(path, placement, at: [[x, y], …], subtract=[], tolerance=5, everywhere=False, to_line=True, spacing_mm=3.0, taken=None, palette=None)` → `{"shapes": [fill…], "areas": n, "color": "#rrggbb", "ms"}`; shapes are the whole-picture kind (`outline`, `holes`, `color`). Background method.

1. `pic = prepare(path)`, with the picture's palette applied when one is given (P9-A3).
2. For each click: on a dark pixel, the solid dark area under it (`_solid_dark`, as `region` does). Otherwise the clicked color group `g0` and every group within `3 + 2.5 × tolerance` of it (`_delta_e` on the group colors); mask = those groups, dark lines excluded.
3. Without `everywhere`: the connected piece under the click. With it: every piece of at least 4 mm².
4. Close specks (5 × 5), grow to the middle of bordering lines (`_to_line_middle`) when `to_line`, cut away `subtract` pieces, and fit around shapes already drawn (`_taken_mask`, tucked 0.3 mm) unless the click is on one.
5. Each piece through `_fill_candidate`. More than 400 pieces: `TraceError("This color is in more than 400 separate places. Raise Tolerance, or untick Every area of this color.")`

#### P9-A3 Simplify the picture's colors

**Behavior.** `Alt+C` opens a dialog for the selected picture (else the top visible one). Left: the picture in its simplified colors, with "Show the original" to compare. Right: "Colors" 2 to 24 (default 8) and one swatch per color with its share of the picture. Per swatch: a thread button (the thread picker), "Leave out" (background), and merge by dragging one swatch onto another. Buttons: **Digitize the whole picture** (the usual preview, then Add), **Use for Auto-trace and the wand**, Reset, Close. The choice is saved on the picture (`RefImage.palette`) and so in the project.

**Engine.** `trace.palette(path, colors=8, merges=[])` → `{"colors": [{"id", "color", "share", "ink": bool, "edge": bool}], "preview": "data:image/png;base64,…", "ms"}`. `preview` is at most 512 px on its long side. It is `simplify_colors(smooth, colors)` (already seeded, so ids repeat), then each `[from, into]` merge relabels a group; dark lines are one extra entry with `ink: true` that cannot be merged; `edge` marks the color that fills most of the picture's border.

`with_palette(pic, colors, merges, skip)` returns a copy of the `Pic` with those groups and none of the private caches (`_simple`, `_links`, `_solid`); copies are kept for the last four palettes. `trace.digitize_all`, `trace.region` and `trace.wand` take `palette={"colors", "merges", "skip"}`. With a palette, `digitize_all` gives each fill its palette color exactly and a `"palette": id` field, treats `skip` ids as background, and leaves the "one thread per close color" merge to the dark lines only. On Add, a shape whose palette id has a chosen thread gets that thread.

If a saved palette's swatches no longer match what the engine computes (a different OpenCV), merges and threads are re-attached by nearest color and the user is told once.

#### Track A tests

| Test (file) | Proves |
| --- | --- |
| `test_progress_lines_carry_the_request_id` (`test_rpc_progress.py`) | format in 5.2 |
| `test_progress_is_rate_limited_and_sends_the_last` | 100 ms rule |
| `test_cancel_stops_a_background_method_within_a_second` | a looping fake method ends with `-32001` |
| `test_cancel_of_an_unknown_id_answers_false`, `test_main_loop_methods_ignore_progress` | edges |
| `test_digitize_all_reports_progress_and_can_be_cancelled` (`test_autotrace.py`) | the three stages |
| `test_wand_square_matches_the_true_outline_within_1_mm` (`test_wand.py`) | a drawn 600 px picture placed 80 mm wide; Hausdorff distance ≤ 1.0 |
| `test_wand_takes_one_area_unless_asked_for_every_area` | 1, then 3 |
| `test_wand_tolerance_joins_two_shades` | tolerance 2 → one shade, 8 → both |
| `test_wand_fits_around_shapes_already_drawn`, `test_wand_on_a_dark_area_fills_it` | steps 2 and 4 |
| `test_wand_refuses_more_than_400_areas`, `test_wand_outside_the_picture_finds_nothing` | limits |
| `test_palette_is_the_same_every_time`, `test_palette_shares_add_up_to_one` (`test_palette.py`) | determinism |
| `test_merging_two_colors_gives_one_fewer` | merges |
| `test_five_colors_two_merged_digitize_to_four_threads` | done-when 3 |
| `a progress line reaches the call and restarts its timeout`; `cancel sends rpc.cancel with the call's id`; `progress for an unknown id is ignored` (`engine/rpc.test.ts`) | window side |
| `Shift+click adds, Alt+click subtracts`; `the wand preview is added by the whole-picture accept` (`feat/wand.test.ts`) | mode |
| `Cancel calls the engine and clears the preview`; `progress shows in the bar` (`features.autoall.test.ts`) | bar |
| `dragging one swatch onto another asks the engine with the merge`; `Digitize passes the palette` (`components/PictureColorsDialog.dom.test.tsx`) | dialog |

---

### Track B: photo stitch and cross-stitch — Hard

**Owns:** `engine/threadline_engine/picture/**`, `digitize/fills/tone.py`, `digitize/fills/crossgrid.py`, the `cross_paths` split in `digitize/patterns.py`, the `image.*` bodies in `methods/pictures.py`, `feat/pictureStitch.ts`, `canvas/draftOverlay.ts`, `components/PhotoStitchDialog.tsx`, `CrossStitchDialog.tsx`, `PictureStitchBar.tsx`, `cmd/pictureStitch.ts`, new tests and the snapshot suites `fills_tone` and `fills_crossgrid`. **Registry lines it may add:** two imports in `fills/__init__.py`; two entries in `design/fillPatterns.ts`.

**The rule:** the result is shapes, never loose stitches. Every layer is a fill a user can reshape, recolor, re-space, reorder or delete.

#### P9-B1 `tone` fill pattern

**What it is.** Rows of running stitches that bunch together where the stored map is dark and open out where it is light: Gradient, but following a picture in both directions. Each row is one unbroken line from edge to edge, so there are no trims inside a shape.

**Settings.** `spacing_mm` (row spacing at the darkest, the existing field; default 0.45); `tone_to_mm` "Lightest spacing" `Param(3.0, 0.8, 8.0)`; `stitch_mm` (default 2.5); `angle_deg` (default 45). No underlay on automatic, no Edge pad, no Random. Descriptor: `open`, `angle: true`, `hidden: true`, `noSpacing: false`, `maxStitch: 4`, summary "label+density". Registry: `FillPattern("tone", "open", params={"tone_to_mm": …}, data_keys=("tone", "anchors"), paths=…, step_mm2=…, auto_underlay=lambda level: [])`. (It is registered `open` because it lays its own rows: tatami's rows are straight and these bend.)

**Algorithm** (`paths(poly, params, pos)`):

1. Unpack the map (`picture/maps.py`; refuse a missing or damaged one with "This fill has lost its picture. Make the photo stitch again."). Darkness `d` is 0 to 1.
2. Turn the shape by `-angle_deg` about its center. Lay a sampling grid over its bounds: 0.5 mm along the rows, 0.25 mm across them. Sample `d` at each grid point through the anchors (bilinear; outside the map is 0).
3. Weight `ρ = ρmin + (1 − ρmin)·d`, with `ρmin = spacing_mm / tone_to_mm`. Sum `ρ` across the rows in each column to get `V`.
4. Row `k` is where `V = (k + 0.5) × spacing_mm`: one `np.interp` per column. Where the map is black the rows are `spacing_mm` apart; where it is white, `tone_to_mm`. A row ends where its column runs out, which is always on the far edge.
5. Smooth each row with a three-sample average, turn it back, clip it to the shape, keep pieces longer than 1.5 mm.
6. Sew rows in order, every other one reversed. Needle points every `stitch_mm`, each row shifted by a third of a stitch (brick). `_sew_paths` joins the pieces along the edge.

`step_mm2 = spacing_mm × stitch_mm / mean(ρ)` (the map is unpacked once and cached by its `data` string).

#### P9-B2 Photo stitch

**Behavior.** `Alt+Shift+F` on a placed picture opens a dialog:

| Setting | Choices | Default |
| --- | --- | --- |
| Look | One thread (a sketch) · Colors | One thread |
| Colors (Colors look) | 4 to 8 | 6 |
| Detail | Light · Normal · Rich → darkest spacing 0.6 / 0.45 / 0.35 mm | Normal |
| Leave the lightest areas bare | on / off | on |
| More options: Brightness −2 to +2, Contrast −2 to +2, Row angle, Stitch length | | 0, 0, 45°, 2.5 mm |

Threads are listed with a swatch each and can be changed before the preview. **Preview** closes the dialog and shows the layers on the canvas over the picture, with the stitch count and sewing time in the bar; **Add** (Enter) adds them as one group in one undo step; Dismiss (Esc) adds nothing; "Change settings…" reopens the dialog. The photo stitch is made at the size the picture is placed.

**Engine.** `image.photo_stitch(path, placement, look="one", colors=6, threads=None, detail="normal", bare=True, brightness=0, contrast=0, angle_deg=45, stitch_mm=2.5, fabric_color="#f4f1ea", chart=None)` → `{"objects": [...], "threads": [...], "stitches": n, "warnings": [...], "ms"}`. Background; reports progress per layer and can be cancelled.

1. Read with `trace.open_picture(path, 480)`. Stretch lightness (2nd to 98th percentile → 4 to 96), then apply brightness (± 8 L per step) and contrast (± 25% per step).
2. Map size: 2 pixels per placed millimeter, long side clamped to 48–160.
3. **One thread:** `d = 1 − L/100`. With `bare`, `d < 0.06` becomes 0 and such areas over 25 mm² are cut out of the outline. One fill; `tone_to_mm` 3.0; thread = the one given, else the darkest spool in My threads, else black.
4. **Colors:** k-means in Lab (seeded) for `colors` groups, plus one for the fabric when `bare`. Each group's color → the nearest real thread (decision 2); two groups landing on one thread merge. Share of each thread at each pixel: `w = exp(−ΔE² / 200)` to each thread color (and to `fabric_color`), divided by the sum, blurred 0.6 mm. A thread's map is its share × 255. Threads under 1.5% of the picture are dropped. `tone_to_mm` 6.0.
5. Each layer's outline: where its map is 20 or more, closed 3 × 3, pieces of at least 12 mm² (at most 40 per layer; fewer, with a warning, if there are more), traced with `cv2.findContours` and `shapeops.to_nodes`. One fill per piece, all sharing the layer's map and anchors.
6. Layers are returned lightest thread first, with angles 45, 135, 0, 90, 60, 150, 30, 120 in turn, `underlay: []`, `pull_comp_mm: 0`, named "Photo: <thread>", one `group`.
7. Estimated stitches over 150,000: `TraceError("This photo stitch would need about N stitches. Make the picture smaller or choose Light detail.")` Over 60,000: a warning with the sewing time.

#### P9-B3 `crossgrid` pattern and cross-stitch from a picture

**Pattern.** `crossgrid` sews one X in every square its bitmask marks. `data_keys=("grid", "anchors")`; setting `cross_mm` (the existing field). Squares whose four corners are not inside the shape's outline are skipped, so reshaping the outline crops the crosses. Paths are built in grid units by the run code split out of `cross_paths` (`cross_paths_from_runs(runs, size)`: out along a run laying one diagonal per square, one step up the last square's side, back laying the other) and then placed through the anchors, so a turned or mirrored grid still sews right. A diagonal longer than 7 mm gets a middle point. Descriptor: `open`, `noSpacing`, `noLength`, `hidden`. The split must leave the `fill_cross*` snapshots unchanged.

**Behavior.** `Alt+X` on a placed picture: Square size 1 to 8 mm (default 2; the hint shows the count per inch), Colors 2 to 16 (default 8), "Outline the color areas" (off), "Leave the background bare" (on). Preview, Add and Dismiss work as for photo stitch.

**Engine.** `image.cross_stitch(path, placement, square_mm=2.0, colors=8, outline=False, bare=True, chart=None)` → `{"objects", "threads", "cols", "rows", "crosses": [{"color", "count"}], "warnings", "ms"}`. Shrink the picture to `cols × rows` cells by area average; k-means to `colors`; drop the border color when `bare`; one `crossgrid` fill per color, its outline the bounding rectangle of its squares; with `outline`, closed running-stitch objects along the cell edges of each color area in the darkest thread, sewn last. Limits: 200 cells a side; over 40,000 crosses is refused with "Use bigger squares or a smaller picture."

**Preview drawing.** `feat/pictureStitch.ts` renders the returned objects with `layout.render` on their own and puts the result in `autoAll.preview`; `canvas/draftOverlay.ts` registers an overlay that draws it as flat colored lines.

#### Track B tests

| Test (file) | Proves |
| --- | --- |
| `test_tone_is_registered_with_its_data_keys` (`test_fill_tone.py`) | registry |
| `test_all_dark_map_matches_spacing`, `test_all_light_map_matches_lightest_spacing` | rows 0.45 ± 0.05 and 3.0 ± 0.2 apart |
| `test_dark_half_is_denser_than_light_half` | `thread_per_mm2` ratio within 25% of `tone_to_mm / spacing_mm` |
| `test_rows_never_cross`, `test_no_trims_in_a_convex_shape` | continuity |
| `test_stays_inside_the_shape` | `assert_sane(inside=shape, tolerance_mm=0.3, max_stitch_mm=stitch_mm + 0.05)` |
| `test_angle_turns_the_rows`, `test_moves_with_the_shape`, `test_mirror_flips_the_picture` | anchors |
| `test_missing_or_damaged_map_is_refused_in_plain_words`, `test_lightest_spacing_is_checked` | messages |
| `test_stitch_count_guard_uses_the_map`, `test_deterministic`, `test_snapshots` | suite `fills_tone`: `half_dark`, `radial`, `donut_radial`, `angle_30` |
| `test_project_names_the_feature` | `fill_tone`, `fill_crossgrid` |
| `test_one_cross_per_marked_square`, `test_squares_outside_the_outline_are_skipped` (`test_fill_crossgrid.py`) | pattern |
| `test_no_bars_between_crosses`, `test_turned_grid_follows_its_anchors`, `test_big_squares_get_a_middle_point`, `test_snapshots` | suite `fills_crossgrid` |
| `test_one_thread_gives_grouped_tone_fills` (`test_photostitch.py`) | objects pass `FillParams.from_dict` |
| `test_colors_gives_layers_light_to_dark`, `test_shares_add_up`, `test_bare_fabric_is_left_out` | layering |
| `test_coverage_follows_darkness` | render the objects; 5 mm cell coverage against picture darkness, r ≥ 0.8 |
| `test_estimate_is_within_20_percent`, `test_refuses_over_150000_stitches`, `test_map_is_at_most_160_px` | limits |
| `test_same_picture_same_result`, `test_reports_progress_and_can_be_cancelled` | determinism, A1 |
| `test_20_by_20_picture_gives_the_expected_crosses` (`test_crossstitch_picture.py`) | done-when 6 |
| `test_background_is_left_bare`, `test_outline_follows_cell_edges`, `test_refuses_over_40000_crosses` | options, limits |
| `Preview asks the engine and adds nothing`; `Add puts the layers in one group in one undo step`; `Dismiss adds nothing` (`feat/pictureStitch.test.ts`) | preview rule |
| `Colors offers 4 to 8` (`components/PhotoStitchDialog.dom.test.tsx`) | dialog |

Test pictures are drawn in the tests with numpy and Pillow; no image files are committed.

---

### Track C: output and color tools

**Owns:** `engine/threadline_engine/output.py`, the `export.picture` body, `feat/exportPicture.ts`, `components/ExportPictureDialog.tsx`, `design/colorShift.ts`, `feat/colorShift.ts`, `feat/notes.ts`, `components/NotesField.tsx`, the Design section of `components/InfoPanel.tsx`, `print.ts`, a renderer accessor in `canvas/hooks.ts` and its one call site in `StitchCanvas.tsx`, `cmd/output.ts`, new tests.

#### P9-C1 Save a picture of the design

**Behavior.** `Mod+Shift+G` opens a dialog: What (the design alone · on the garment chosen in "Preview on"); Background (transparent · the fabric color · white); Size, long side 1,000 / 2,000 / 4,000 px (default 2,000); Thread (realistic · flat lines). Save asks where and writes a PNG.

**How.** `canvas/hooks.ts` gains `setRenderer(app)` / `getRenderer()`; `StitchCanvas` calls `setRenderer` once after it starts. `feat/exportPicture.ts` builds a separate container (never the live scene: no grid, hoop, rulers or handles): the garment outline from `garmentShape` when asked, then each color block with `buildThreadChunk` (realistic) or plain lines. Frame: the design's bounds plus 5 mm, or the garment's outline. Scale = asked pixels ÷ the frame's long side, capped at 4,096 px. Render with Pixi 8's `renderer.extract` (confirm the option names in the Pixi 8 docs when building). The window cannot write files, so the PNG goes to the engine: `export.picture(dest, png_base64)` checks the PNG signature, a 64 MB limit and at most 8,192 px a side (Pillow), adds `.png` if missing, writes to a temporary file and renames.

#### P9-C2 Design notes

`Layout.notes` (so notes undo, autosave and save with the project). The Design section gains a folded "Notes" with a text box (4,000 characters; typing is one undo step, committed on leaving the box). `Alt+N` opens the fold and puts the cursor there. `printHtml` takes the notes and prints them under the thread list, escaped, line breaks kept. On open, anything that is not a string is dropped.

#### P9-C3 Lighten or darken all colors

Each press of `Alt+=` or `Alt+-` moves every sewn color 6 steps lighter or darker in Lab lightness (hue and strength kept, clamped to 2–98), as one undo step. `design/colorShift.ts`: `shiftHex(hex, dL)` and `shiftLayout(layout, design, dL, snap?)`, built on the existing recolor helpers so placed stitch files, shapes and lettering all change. Color options (the Order & colors ⋯ menu) gains "Pick the nearest real thread when lightening or darkening" (on when a match chart is set): each shifted color snaps to the nearest thread in that chart (`threads.match`); if that is the thread it already had, the step is widened to 12, then 18; if it still does not change it is left, and the notice says how many colors had no lighter (or darker) thread. With the option off, shifted colors lose their thread name and number.

#### Track C tests

| Test (file) | Proves |
| --- | --- |
| `test_saves_a_png_through_a_temporary_file` (`test_output.py`) | atomic write |
| `test_refuses_data_that_is_not_a_png`, `test_refuses_over_64_mb`, `test_adds_the_png_extension` | checks |
| `the frame is the design plus 5 mm`; `the mock-up frame is the garment`; `the scale stops at 4096 px` (`feat/exportPicture.test.ts`) | pure parts |
| `test_notes_survive_save_and_open` (`test_notes.py`) | project round trip |
| `typing notes is one undo step`; `notes that are not text are dropped on open` (`feat/notes.test.ts`) | UI |
| `notes print under the thread list, escaped` (`print.test.ts`) | print |
| `shiftHex keeps the hue`; `it stops at black and white`; `gray stays gray` (`design/colorShift.test.ts`) | math |
| `every color block changes once`; `one press is one undo step`; `snapping widens the step until the thread changes` (`feat/colorShift.test.ts`) | layout |
| `the four commands are registered with their reserved shortcuts` (`cmd/output.test.ts`) | registry |

The picture itself cannot be drawn in the test environment (no graphics card): it is on the manual list in section 8.

## 8. Integration (session lead)

1. Merge A, then B, then C. Run `python scripts/check.py`.
2. `python scripts/kb_commands.py` (eight new commands), then `--check`.
3. `pnpm build:engine`: the new `picture/` package must load in the frozen engine.
4. `python scripts/check.py --all`.
5. By hand, in the app (say in the handoff which were done): the wand pointer and a wand fill; progress and Cancel on a busy picture; a photo stitch preview over its picture; a saved PNG, realistic and flat, with a transparent background.
6. Docs (section 9). If decision 1 was yes, add the decision to `DECISIONS.md` under the next free number. Then the stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**`docs/CHANGELOG.md`**, under the current unreleased heading:

```
### Phase 9: pictures (YYYY-MM-DD)
- **Magic wand (Z)**: click a color in a picture to fill that area. Tolerance sets how close a color must be; "Every area of this color" takes them all. Shift+click adds, Alt+click takes away. Nothing is added until you press Enter.
- **Simplify the picture's colors (Alt+C)**: choose how many colors a picture has, merge two, pick a thread for each, then digitize from that.
- **Progress and Cancel** when the whole picture is digitized.
- **Photo stitch (Alt+Shift+F)**: a photo as a one-thread sketch, or in 4 to 8 threads sewn light to dark. Each layer is a fill you can reshape and recolor.
- **Cross-stitch from a picture (Alt+X)**: a grid of crosses per color, with an optional outline.
- **Save a picture of the design (Ctrl+Shift+G)** as a PNG, alone or on the garment, with a see-through background if you want.
- **Design notes (Alt+N)**, saved in the project and printed with the thread list.
- **Lighten or darken all colors (Alt+= and Alt+-)**, optionally keeping to real threads.
```

**`docs/LUDD-KNOWLEDGE-BASE.md`:** new entries `F-906` Magic wand, `F-907` Simplify the picture's colors, `F-1002` Progress and cancel for auto-digitize, `F-1003` Photo stitch, `F-1004` Cross-stitch from a picture, `F-211` Save a picture of the design, `F-212` Design notes, `F-1608` Lighten or darken all colors. Update `F-1305` (two patterns that only pictures make) and `F-205` (notes on the print). `L-008` becomes YES, pointing to `F-1003`. Section 2 index: a row per new entry. History row; *Last updated*; section 25 from the script.

| ID | Entry |
| --- | --- |
| L-055 | A photo stitch is a sketch or flat blended colors, not a photograph; best under about 100 mm with a plain background |
| L-056 | A photo stitch does not follow the picture afterwards: change the picture, make it again |
| L-057 | Cross-stitch from a picture: whole crosses only; the outline is a running stitch |
| L-058 | Saved pictures are PNG only, at most 4,096 px |
| L-059 | The wand needs flat colors; on photos and shaded art use Auto-trace (with AI if installed) |
| T-043 | The wand takes too much or too little: change Tolerance, or simplify the colors first |
| T-044 | A photo stitch looks muddy or too dark: Brightness up, fewer colors, Light detail, a plainer picture |
| T-045 | Stray single crosses: fewer colors or bigger squares |
| T-046 | The saved picture is blank or cut off: choose a smaller size, or Flat lines |

**`docs/USER-MANUAL.md`:** section 4 (wand, colors, photo stitch, cross-stitch), section 2 (save a picture, notes), section 9 (lighten and darken). **`ai/helpdocs.py`:** the same, with the shortcuts.

**`docs/stitchout-log.md`**, four rows in "Pending machine tests":

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 9 | **Photo stitch, one thread** | A portrait at 90 mm, One thread, Normal detail, woven cotton | The face reads at arm's length; dark areas lie flat; light areas show even, open rows; no thread nests at row ends |
| Phase 9 | **Photo stitch, colors** | The same portrait, 6 colors | Colors blend with no bare gaps and no stiff piles where layers meet |
| Phase 9 | **Cross-stitch from a picture** | A 40 × 40 square picture at 2 mm, 6 colors, outline on | Crisp crosses with no bars between them; the outline sits on the square edges |
| Phase 9 | **Wand fill beside an outline** | A logo color filled with the wand, next to a satin outline | The fill tucks under the outline with no gap |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Tone rows look streaky, cross, or spend thread travelling along the far edge | `test_rows_never_cross` fails, or more than 5% of the thread is travel | Keep the pattern's name, settings and data; change only how rows are laid: straight rows at a fixed pitch whose zigzag width follows the map. Record the change in the handoff. |
| Soft color shares sew muddy | the stitch-out row; before that, `test_shares_add_up` passes but layers overlap everywhere | Sharpen the shares (`ΔE² / 50`); the layers then meet with a narrow blend. |
| Progress lines upset the developer browser preview | its test fails | The bridge must drop lines whose id it is not waiting for; fix it there, not in the engine. |
| Pixi's extract call differs from memory, or a 4,000 px render fails on an old graphics card | blank PNG | Check the Pixi 8 docs; fall back to 2,000 px and say so in the dialog. |
| Palette ids differ on another computer | a saved palette's swatches do not match | The re-attach by nearest color in P9-A3. |
| Track B fills the session | time or context runs out | Merge A and C, stop, and run Track B as its own session from the same phase branch. |

## 11. Handoff

Write in `HANDOFF.md`: test counts before and after; which of the manual checks in section 8 were done; whether `pnpm build:engine` ran; the answer to decision 1; any spec deviation, one line each (above all, whether the tone rows shipped as specified or as the fallback). Queue nothing for the machine beyond the four rows above.
