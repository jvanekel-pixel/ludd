# Phase 14: Extensibility, accessibility & performance

| | |
| --- | --- |
| Weight | Medium |
| Session lead | Sonnet 5.5. Track A's small API is the part to get right: give its worker the stronger model if there is room. |
| Audit | The top model reads `docs/PLUGINS.md` and the plugin loader before any release: plugins run code. |
| Depends on | Phase 3. Best after 6, 7 and 10, so the plugin API covers what they added and the reader helper covers library scans. |
| Changes stitches | No. Every existing snapshot stays as it is. |
| Closes | `docs/PLAN.md` backlog: Python plugin and scripting API; pen and touch, high-DPI and screen-reader pass. `BACKLOG.md`: bundle size, slow stipple, memory guard (L-024), second Recover slot, AI key in the keychain. D-001's "revisit if" (100,000+ stitches). |
| Spec depth | Light: scope, architecture and tests are fixed. **Do section 4 first** and update this file before building. |

## 1. Goal and done-when

Three things that make LUDD last: other people can add stitch types without touching the app, people who cannot use a mouse or read small low-contrast text can use it, and it stays quick on designs far bigger than a 4 × 4 hoop.

**Done when:**

1. With plugins off (the default), nothing in the plugins folder is read or run. With them on, the two example plugins add a fill pattern and a script that work from the app.
2. A plugin that fails to load, raises, or hangs is named in the Plugins dialog and the engine keeps answering.
3. The automated accessibility test passes for the panel and every dialog, and the keyboard and screen-reader checklist is filled in for Windows.
4. A 100,000-stitch design meets the budget table in `docs/PERFORMANCE.md`, with the numbers before and after recorded.
5. The desktop build prints no chunk-size warning.
6. `python scripts/check.py --all` prints `RESULT: PASS`, no snapshot changed, and `pnpm build:engine` passes its smoke check with the new plugin and helper-process checks.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P14-S1 | Types, method stubs, preference fields, command and dialog stubs, the canvas label hook | No | Step 0 |
| P14-A1 | Plugin loader and trust rules | No | A |
| P14-A2 | The `ludd` API, version 1 | No | A |
| P14-A3 | Plugin stitch types in the panel and in project files | Yes | A |
| P14-A4 | Scripts: "run on this design" | Yes | A |
| P14-A5 | Plugins dialog (`app.plugins`, `Alt+Shift+P`) | Yes | A |
| P14-A6 | Two example plugins, `docs/PLUGINS.md`, what the frozen engine can import | Yes | A |
| P14-B1 | Keyboard reach and a visible focus ring everywhere | Yes | B |
| P14-B2 | Names, roles and announcements for screen readers | Yes | B |
| P14-B3 | More contrast, text size, reduced motion | Yes | B |
| P14-B4 | Pen and touch on the canvas | Yes | B |
| P14-B5 | High-DPI check | Yes | B |
| P14-B6 | Automated checks and the manual checklist | No | B |
| P14-C1 | Benchmark script, test designs, budget table | No | C |
| P14-C2 | Stitch records sent as typed arrays | No | C |
| P14-C3 | Engine: placed files cached after their edits; numpy transform | No | C |
| P14-C4 | Canvas: unchanged chunks kept; level of detail when zoomed out | Yes | C |
| P14-C5 | Bundle split | No | C |
| P14-C6 | Stipple speed; wave stitch-count estimate | No | C |
| P14-C7 | Memory-limited reader for risky formats (decision 3) | Yes | C |
| P14-C8 | Second Recover slot (decision 4) | Yes | C |
| P14-C9 | AI key in the system keychain (decision 5) | Yes | C |
| P14-Z1 | Docs, frozen-engine check, benchmark after, handoff | – | Integration |

**Out of scope:** a plugin store or any download of plugins; a sandbox; plugins that change the window (JavaScript); drawing shapes on the canvas with the keyboard alone; translations (Phase 12); replacing the canvas with hand-written WebGL (if the budget cannot be met without it, stop and ask).

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | **Plugin trust model.** A plugin is a program with all your rights on the computer. (A) Files you put in the plugins folder, off until you allow plugins, each one ticked on by hand, turned off again if its file changes. (B) No code: only motif and preset packs, which Phases 6 and 7 already import. (C) No plugins. | A. It cannot be sandboxed, so say so plainly and keep it off by default. | Track A is not built. |
| 2 | What `docs/PLUGINS.md` says about sharing plugins | "A plugin runs inside LUDD, which is GPL. If you share one, share it under a GPL-compatible license." | That sentence. |
| 3 | Read risky stitch formats in a memory-limited helper process? D-017 chose to document the risk (L-024) instead. | Yes, once the library scans whole folders of downloaded designs. | Not built; D-017 stands. |
| 4 | Second Recover slot, so autosave keeps running while the Recover banner waits? D-017 kept autosave off. | Yes; it is small and closes a real gap. | Not built; D-017 stands. |
| 5 | AI key on Mac and Linux: (A) the system keychain through the system's own tools, no new package; (B) the `keyring` package; (C) leave the private file. | A. `keyring` is MIT and its Linux parts (SecretStorage BSD-3-Clause, cryptography Apache-2.0 or BSD) are GPL-compatible, but it adds a compiled library to the frozen engine. Confirm licenses against what `uv lock` resolves; they were not checked online for this spec. | C: left as it is. |
| 6 | Add `axe-core` as a development-only dependency (MPL-2.0, never shipped) for the accessibility test? | Yes. | Hand-written checks only (names, roles, tab order). |
| 7 | Who runs the VoiceOver pass? The owner's PC is Windows. | Anyone with a Mac, later. | The Mac column of the checklist says "not run", and L-082 says so. |

## 4. Refresh this spec first

| Fact assumed | How to check | If it changed |
| --- | --- | --- |
| The fill, line and motif registries and the render hooks are as Phase 3 left them, plus what Phases 6 and 7 added | read `digitize/fills/__init__.py`, `digitize/lines/__init__.py`, `layout/passes.py` | Map the `ludd` API onto what is there; add what 6 and 7 introduced (row patterns, saved motifs). |
| `FILL_PATTERN_DEFS` and `LINE_STYLE_DEFS` are fixed lists; `FillPattern` is a closed union | `design/fillPatterns.ts`, `design/types.ts` | Step 0 adds run-time registration and widens the type. |
| The engine is frozen by PyInstaller into one file from `engine/entry.py`; `scripts/smoke_engine.py` runs it | `scripts/build_engine.py` | Adjust how extra modules are bundled and how the helper process starts. |
| The dispatcher runs one method at a time on its main loop, slow ones on threads holding `dispatcher.lock` | `rpc.Dispatcher` | A hung plugin still blocks the main loop: the crash marker rule stays. |
| `design.summarize` sends `records` as three lists of numbers | read it | If already binary, drop P14-C2. |
| Seven app files read `records.x/y/kind` | `grep -rlE "records\.(x\|y\|kind)" apps/desktop/src` | List the real readers in Track C. |
| The canvas draws a `Graphics` per chunk (`chunkBlocks`, `drawStitches`, `buildThreadChunk`) on Pixi 8 at the device pixel ratio | `StitchCanvas.tsx`, `threadRender.ts`, `package.json` | Re-plan C4 around the drawing code that exists. |
| `:focus-visible` has a global outline; 108 `font-size: Npx` rules; themes are `system`, `light`, `dark` | `styles.css`, `theme.ts` | Recount; Phase 11 may have moved Settings. |
| Autosave stops while `recoveryWaiting` is true; one recovery file | `actions.ts` `startAutosave`; `project._recovery_path` | Follow the code. |
| The key is DPAPI-protected on Windows, a private file elsewhere; `key_protection` is `windows` or `file` | `ai/settings.py` | Follow the code. |
| The backlog lines (bundle warning, stipple S8, keychain, memory guard, Recover slot) are still open and D-017 is not superseded | `BACKLOG.md`, `DECISIONS.md` | Drop what is done. |
| `Alt+Shift+P` is still free | `grep -rn "Alt+Shift+P" apps/desktop/src` | Pick from the free list in `README.md`. |

## 5. Architecture

### 5.1 Plugins

A plugin is one `.py` file in the data folder's `plugins` folder. State lives in `plugins.json` beside it: `{allowed, enabled: {id: sha256}}`.

**Trust rules** (decision 1, option A):

1. Nothing in the folder is read until "Allow plugins" is on. The switch shows: "A plugin is a program. It can do anything you can do on this computer, including reading, changing or deleting your files and using the internet. LUDD cannot limit it. Only add plugins from people you trust."
2. Each plugin is off until ticked. LUDD remembers the file's SHA-256; a file that changed is turned off and says so.
3. Only files directly in that folder. Never from a project, a part, a font or a picture, and LUDD never downloads one.
4. Loaded with `importlib` as `ludd_plugin_<id>`, with `sys.dont_write_bytecode` set so nothing is written beside it.
5. An import error or exception marks the plugin "failed" with the first line of the error. The engine keeps serving.
6. Crash marker: before plugin code runs, the engine writes `plugins/.running` with the plugin's id and removes it after. A marker found at start-up means the engine died or was restarted inside that plugin: it is turned off and named in the dialog.
7. Ids are `<plugin>.<name>`, so a plugin can never replace a built-in.

**The `ludd` module, API version 1** (the whole promise; anything imported from `threadline_engine` may change):

| Name | What it does |
| --- | --- |
| `PLUGIN = {"name", "version", "api": 1, "author"}` | every plugin file has it; a higher `api` than the app's is refused with a plain message |
| `@ludd.fill(name, label, params={})` | `fn(shape, settings, start) -> list of lines`; shape is a shapely Polygon in mm; registered as an open fill pattern |
| `@ludd.line(name, label, params={})` | `fn(points, settings, closed) -> list of (x, y)` |
| `ludd.motif(name, label, unit)` | one repeat: x 0..1 along the line, y -0.5..0.5 across |
| `@ludd.stitch_op(name, label, stage="placed", params={})` | `fn(stitches, settings) -> stitches` on one color of a placed stitch file; stitches are `(x_mm, y_mm, kind)` |
| `@ludd.design_pass(name, label)` | `fn(colors) -> colors` after every item is rendered; runs only in designs that list it |
| `@ludd.script(name, label)` | `fn(design) -> design or None`; the layout as plain dictionaries, as a project file holds it |
| `ludd.Param(default, lo, hi, label)` | a number setting with a range |
| `ludd.STITCH`, `JUMP`, `TRIM`, `STOP`; `ludd.resample`, `ludd.inside`, `ludd.offset`; `ludd.Error` | kinds, three helpers, and an error whose message is shown on the shape |

A plugin may import `ludd`, `shapely`, `numpy` and these standard modules: `math`, `random`, `itertools`, `functools`, `collections`, `dataclasses`, `json`, `re`, `statistics`, `typing`, `bisect`, `heapq`, `copy`, `enum`, `fractions`. The frozen engine holds only what is bundled, so `build_engine.py` bundles that list and the smoke check imports each.

**Projects.** A shape that uses `honeycomb.cells` adds `plugin:honeycomb` to the project's `features`. A project is never refused for a `plugin:` feature: it opens, shapes whose plugin is missing sew as plain tatami, and a warning (also shown at Save for machine) names the plugin.

### 5.2 Accessibility settings

Settings gains an "Accessibility" group: **More contrast** (`prefs.moreContrast`; follows the system's `prefers-contrast: more` until set) and **Text size** (`prefs.textScale`: Small 12.5, Normal 14, Large 16, Larger 18 px at the root). Brand colors are unchanged in the normal light and dark themes.

### 5.3 Performance data flow

`records` travels as `{enc: "b64", n, x, y, kind, item?, src?}`: each column the base64 of a little-endian array (`float32` millimeters, `uint8` kind, `int32` item and src). `design/records.ts` decodes to typed arrays and still accepts plain number lists.

### 5.4 RPC methods (names go into `rpc_methods.json` in Step 0)

| Method | Parameters | Returns |
| --- | --- | --- |
| `plugins.status` | – | `{allowed, folder, api, plugins: [{id, name, version, author, state, error, adds}]}`; `state` is on, off, failed or changed; `adds` lists fills, lines, motifs, ops, passes and scripts with labels and params |
| `plugins.allow` | `on` | status |
| `plugins.enable` | `id, on` | status |
| `plugins.reload` | – | status |
| `plugins.run_script` | `id, name, layout` | `{layout}` or `{unchanged: true}` |

New files are named in each track's "Owns" list in section 7.

## 6. Step 0 (session lead)

1. `git switch -c phase-14/extensibility-accessibility-performance`.
2. `design/types.ts`: record columns typed `ArrayLike<number>`; `FillPattern` and the line style type accept any string beside the built-in names.
3. `design/fillPatterns.ts`, `design/lineStyles.ts`: `registerFillPattern(def)` and `registerLineStyle(def)` (a name twice throws).
4. `rpc_methods.json` and stubs for the five methods in 5.4; `methods/__init__.py` imports `plugins`.
5. `project.py`: `feature_known(name)` replaces the direct `KNOWN_FEATURES` test in `open_project` and accepts `plugin:` names; `layout/objects.py`: a hook `missing_pattern(obj)` that Track A fills in.
6. `prefs.ts`: `moreContrast?`, `textScale?`. `a11y.ts`: `canvasLabel()` returning "Design area", wired to the canvas element in `StitchCanvas.tsx` (`role="img"`, `aria-label`).
7. `cmd/plugins.ts` and `registerDialog("plugins", …)` as stubs; a "Plugins…" button in Settings that runs the command.
8. `python scripts/check.py`; commit. Workers branch from here.

## 7. Tracks

A, B and C run together. Every worker follows "Worker rules" in `BUILDPLAN.md`. Tracks whose decision was "no" are skipped whole (A) or by item (C7, C8, C9).

---

### Track A: plugins and scripts

**Owns:** `plugins.py`, `pluginapi.py`, `methods/plugins.py`, the `missing_pattern` hook body, `scripts/build_engine.py` (the bundled-module list), `scripts/smoke_engine.py` (two checks), `feat/plugins.ts`, `components/PluginsDialog.tsx`, `cmd/plugins.ts`, `examples/plugins/**`, `docs/PLUGINS.md`, `engine/tests/test_plugins.py`.

- **A1 Loader.** Rules 1 to 7 in 5.1. Plugins load at engine start when allowed, and on `plugins.reload`. Registrations go through the Phase 3 registries (`fills.register`, `lines.register`, `register_motif`, `register_item_op`, `register_pass`), wrapped so plugin code sees only plain lists and dictionaries and so its errors become `ludd.Error` text on the shape.
- **A2 API.** `pluginapi.py` is installed as `sys.modules["ludd"]` before a plugin is loaded. `ludd.__all__` is the table in 5.1 and a test pins it.
- **A3 In the panel and in files.** After start-up and after Reload the window registers each plugin pattern and style from `plugins.status` (open kind, fields from its `Param`s). The feature name and the missing-plugin fallback are as in 5.1.
- **A4 Scripts.** Run from the Plugins dialog on the open design. The returned layout is checked as a project is on open, then applied as one undo step; `None` or an equal layout says "Nothing changed".
- **A5 Dialog.** The Allow switch with its warning; the list with on/off, state, what each adds and any error; Open the plugins folder; Reload; a Scripts list with Run.
- **A6 Examples.** `honeycomb.py`: a fill pattern `honeycomb.cells` with `Param(4, 2, 10, "Cell size")`. `rainbow.py`: a script that gives each shape the next thread from the design's own colors. Both are copied into a scratch plugins folder by the tests, and `docs/PLUGINS.md` walks through them.

| Test (`test_plugins.py`) | Asserts |
| --- | --- |
| `test_nothing_is_read_while_plugins_are_off` | a plugin that writes a file on import leaves no file |
| `test_a_plugin_is_off_until_ticked`, `test_a_changed_file_is_turned_off` | states `off`, `changed` |
| `test_a_broken_plugin_is_reported_and_the_engine_answers` | syntax error → `failed`; `ping` still answers |
| `test_a_plugin_that_raises_names_itself_on_the_shape` | the message has the plugin's name |
| `test_crash_marker_turns_the_plugin_off` | a leftover `.running` |
| `test_a_plugin_cannot_replace_a_built_in`, `test_a_newer_api_is_refused` | |
| `test_honeycomb_fills_a_square` | through `dz.generate`; `assert_sane`, `assert_deterministic` |
| `test_param_ranges_are_enforced` | "Cell size must be between 2 and 10 mm" |
| `test_rainbow_script_recolors_and_is_valid` | result passes the project checks |
| `test_a_script_returning_rubbish_is_refused` | the design is untouched |
| `test_opening_a_project_never_loads_a_plugin` | |
| `test_missing_plugin_sews_plain_fill_with_a_warning` | render does not fail |
| `test_api_surface_is_pinned` | `ludd.__all__` equals the documented list |
| `the dialog shows the warning before plugins can be allowed` (`PluginsDialog.dom.test.tsx`) | |

---

### Track B: accessibility

**Owns:** `styles.css`, `theme.ts`, `a11y.ts`, `canvas/touch.ts`, the Accessibility group in `SettingsDialog.tsx`, attribute-only edits (names, roles, tab order) in `components/*.tsx` except `StitchCanvas.tsx`, `cursors.ts`, `docs/ACCESSIBILITY-CHECKLIST.md`, new `a11y.dom.test.tsx`, `styles.contrast.test.ts`, `canvas/touch.test.ts`.

- **B1 Keyboard.** Every button, tab, menu item, list row, thread swatch and fold heading can be reached with Tab and worked with Enter or Space. Arrow keys move inside menus, the tool rail, thread grids and button groups (one tab stop each). Focus returns to the opener when a menu or dialog closes. No rule removes the focus outline. Drawing points and dragging handles still need a pointer (L-081).
- **B2 Screen readers.** Icon-only buttons have names; toggles say pressed or not; fold headings say open or closed; notices use `role="status"`, errors `role="alert"`; Order & colors rows read as "Fill 2, navy, sews third"; `canvasLabel()` describes the design ("Design area. 3 shapes, 5,240 stitches. Selected: Fill 2, 30 by 20 millimeters").
- **B3 Contrast, size, motion.** Tokens under `:root[data-contrast="more"]` for light and dark: text 7:1, control borders 3:1 and 2 px. Under the system's forced colors, thread swatches keep their color and focus uses the system highlight. The 108 pixel font sizes become `rem`, so Text size scales them; ruler labels scale too. With `prefers-reduced-motion`, no transitions.
- **B4 Pen and touch.** `canvas/touch.ts` registers a canvas tool that is active while two touch points are down: pinch zooms about the midpoint, two fingers pan, and nothing is drawn or selected until both lift. One finger or a pen works as the mouse does. Handles and points get a 16 px hit area for touch and pen (9 px for a mouse). Press and hold for half a second, or the pen's side button, opens the right-click menu.
- **B5 High-DPI.** The canvas already draws at the device pixel ratio. Check pointers and ruler text at 150% and 200%; add 2× pointer images where they look soft.
- **B6 Checks.** The checklist has fifteen tasks (open a design, pick the machine, recolor a thread, change a fill's density, add text, reorder, read a quality check, save for machine, each dialog, undo) done once by keyboard alone and once with NVDA, recording what its speech viewer printed. Decision 7 covers the Mac column.

| Test | Asserts |
| --- | --- |
| `every focusable thing in the panel has a name` (`a11y.dom.test.tsx`) | for each kind of selection |
| `every dialog has a label and returns focus to its opener` (same) | all registered and built-in dialogs |
| `no positive tabindex anywhere`; `axe finds no violations` (same; the second needs decision 6) | color contrast is checked below, not by axe |
| `text meets 4.5 to 1 in light and dark; 7 to 1 with More contrast` (`styles.contrast.test.ts`) | computed from the tokens in `styles.css` |
| `borders meet 3 to 1 with More contrast` (same) | |
| `no font size is in pixels` (same) | |
| `two fingers zoom and pan and draw nothing` (`canvas/touch.test.ts`) | |
| `a long press opens the menu; a short tap does not` (same) | |
| `Text size and More contrast are saved and applied at start` (`ui.a11y.test.ts`) | |

---

### Track C: performance and robustness

**Owns:** `scripts/bench.py`, `scripts/make_bench_designs.py`, `docs/PERFORMANCE.md`, `design.py` (`summarize`, `load`), `layout/files.py`, `digitize/patterns.py` (`stipple_paths` only), the wave entry's estimate in `fills/builtin.py`, `reader.py`, `engine/entry.py`, the recovery functions in `project.py`, `ai/keystore.py`, `ai/settings.py`, `design/records.ts`, `canvas/lod.ts`, `components/StitchCanvas.tsx`, `components/threadRender.ts`, the autosave part of `actions.ts`, `components/AISettings.tsx`, `vite.config.ts`, lazy imports in `App.tsx`.

**C1 Measure first.** `make_bench_designs.py` writes 30k, 100k, 250k and 500k-stitch PES files and a 1,000-shape project into `_logs/bench/` (never committed). `bench.py` times the engine and prints a table; the dev server with `?bench=1` runs five seconds of scripted pan and zoom and logs the average and 95th-percentile frame time. Record the baseline in `docs/PERFORMANCE.md` before changing anything. Starting budgets (where the baseline is already better, the baseline becomes the budget):

| Measure | 30k stitches | 100k | 250k |
| --- | --- | --- | --- |
| Open a stitch file, to first picture | 0.5 s | 1.5 s | 3 s |
| One edit (move a design), to new picture | 150 ms | 400 ms | 1 s |
| Pan and zoom, 95th-percentile frame | 16 ms | 16 ms | 33 ms |
| Engine memory | 250 MB | 400 MB | 700 MB |
| Window memory | 250 MB | 400 MB | 700 MB |

Then fix the worst first, in this likely order:

- **C2 Typed records** (5.3). Readers use index and `length` only; fix any `map` or spread on a column.
- **C3 Engine.** A placed file's blocks after its ops and transform are cached by file stamp, ops, threads and transform (32 kept, like `_CACHE_MAX`), so an edit elsewhere does not redo them; `_transform` and `summarize` use numpy for blocks over 5,000 records. Output identical.
- **C4 Canvas.** Keep a chunk's `Graphics` when its records did not change. `canvas/lod.ts` thins each chunk's path at two levels (0.15 mm and 0.5 mm); below 8 px per mm draw level 1, below 3 px per mm level 2 as flat lines; realistic thread only at full detail; switch when zooming settles, not every frame.
- **C5 Bundle.** `manualChunks` for Pixi and React; dialogs load with `React.lazy`. The build stage of `check.py` fails on Vite's chunk-size warning.
- **C6 Stipple.** Profile `stipple_paths` on a 100 mm square at 1 mm loops. One `shapely.contains_xy` call replaces the per-cell `contains`; geometry is prepared; repeated buffers go. Target under 1.5 s. The stipple snapshots must not change: if they must, stop, because that is a stitch change. The wave estimate uses the wave's real stitch length.
- **C7 Memory-limited reader** (decision 3). Formats in `RISKY_FORMATS` (`vp3`, `hus`, and any other whose reader unpacks compressed data) are read in one long-lived helper process (`multiprocessing`, spawn; `freeze_support()` in `entry.py`). The parent stops it past 1.5 GB or 30 seconds and says "This file is damaged or was made to use up memory; LUDD stopped reading it." A hard limit too where the system offers one (a Windows job object, `RLIMIT_AS` on Linux). `design.load` routes through it, so batch convert and library scans are covered.
- **C8 Second Recover slot** (decision 4). At start-up a found `recovery.ludd` becomes `recovery-waiting.ludd` and autosave writes `recovery.ludd` again at once. The banner offers the waiting copy. If a waiting copy is already there, the older one is set aside by `_set_aside` and the newer becomes the waiting one. Nothing is deleted without being asked.
- **C9 Keychain** (decision 5, option A). Windows as now. Mac: `/usr/bin/security -i` with the command on standard input, so the key is never in a command line. Linux: `secret-tool store` with the key on standard input when it is installed, else the private file as now. The first read moves an old key file into the keychain and deletes it. `key_protection` gains `keychain`.

| Test | Asserts |
| --- | --- |
| `test_records_round_trip_as_typed_columns` (`test_design.py`) | decode equals the old lists to 0.01 mm |
| `decodes typed columns and plain lists alike` (`design/records.test.ts`) | |
| `test_cached_placed_file_gives_identical_blocks`, `test_cache_misses_when_ops_or_transform_change` (`test_layout.py`) | |
| `test_numpy_transform_matches_the_loop` (`test_layout.py`) | to 1e-6 |
| `lod never moves a point more than its tolerance; keeps first and last` (`canvas/lod.test.ts`) | |
| `an unchanged chunk keeps its hash` (same) | |
| `test_stipple_snapshots_unchanged`, `test_stipple_hoop_sized_is_fast` (`test_patterns.py`) | under 3 s in tests (1.5 s target on the owner's PC) |
| `test_wave_estimate_counts_short_stitches` | |
| `test_reader_stops_a_file_that_eats_memory`, `test_reader_survives_and_reads_the_next_file`, `test_safe_formats_do_not_use_the_helper` (`test_reader.py`) | with a fake reader that allocates |
| `test_waiting_copy_is_never_overwritten_by_autosave`, `test_second_crash_sets_the_older_copy_aside` (`test_project.py`) | |
| `autosave runs while the Recover banner is open` (`actions.qa.test.ts`) | |
| `test_key_moves_from_file_to_keychain`, `test_no_tool_keeps_the_private_file`, `test_key_never_appears_in_a_command_line` (`test_ai.py`) | with a fake runner |
| `bench.py --check` | fails when a measure passes its budget by more than 20% |

## 8. Integration (session lead)

1. Merge C, then B, then A (A touches the freeze script last). Run `python scripts/check.py --all`; no snapshot may have changed.
2. `pnpm build:engine`. The smoke check now also imports every module promised to plugins, loads `honeycomb.py` from a scratch data folder, and reads a `.vp3` through the helper process. Frozen `multiprocessing` is where this breaks.
3. Run the benchmark again and add the "after" column to `docs/PERFORMANCE.md`.
4. Write the docs (section 9); run `python scripts/kb_commands.py`; check again; then the stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**Knowledge base.** New section 31 Plugins: `F-2601` Plugins and scripts. Also `F-2106` Accessibility options · `F-2107` Large designs · `F-2108` AI key in the system keychain. `F-203` (autosave and recovery) gains the second slot. `L-024` becomes FIXED if C7 is built. Index rows for each.

| ID | Entry |
| --- | --- |
| L-080 | Plugins are not sandboxed, by design: a plugin can do anything you can |
| L-081 | Drawing points and dragging handles need a mouse, pen or touch; there is no keyboard-only drawing |
| L-082 | The VoiceOver pass has not been run (if so); a screen reader cannot describe the stitches themselves |
| L-083 | Above about 500,000 stitches LUDD draws simplified thread when zoomed out and realistic thread is slow |
| L-084 | On Linux without a secret service the AI key stays in a private file |
| T-063 | "LUDD stopped answering after I turned a plugin on": restart; the plugin is turned off and named |
| T-064 | "My plugin doesn't show up": Allow plugins, tick it, a changed file, a failed load, the API number |
| T-065 | "LUDD is slow with a big design": realistic thread off, density map off, what the budgets are |
| T-066 | "The text is too small" / "my screen reader doesn't read a control": Text size, More contrast, how to report |

**Other docs:** `docs/PLUGINS.md` (the API table, the two examples, the trust rules, decision 2's sentence), `docs/PERFORMANCE.md`, `docs/ACCESSIBILITY-CHECKLIST.md`; changelog lines per user-visible item; manual section 11 (Accessibility, Plugins), section 2 (recovery) and section 12 (the key); the same facts in `ai/helpdocs.py`. `DECISIONS.md`: one entry for the plugin trust model, and one that supersedes the two D-017 items if decisions 3 and 4 were yes (numbers assigned by the session lead).

**Stitch-out rows:** none. No built-in stitch output changes in this phase.

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| The helper process does not start in the frozen engine | the smoke check hangs or errors | Ship C7 off (`RISKY_FORMATS` empty) and keep L-024; do not block the phase. |
| A plugin loops forever | the window reports the engine not answering | The crash marker turns it off at the next start (T-063). There is no way to stop a thread; say so in `PLUGINS.md`. |
| Typed columns break a reader that used a list method | a UI test fails or a view is blank | Fix the reader; never convert back to lists on the hot path. |
| Level of detail shows a visible "pop" | seen in the dev server | Raise the zoom thresholds; keep full detail for the selected item. |
| Moving font sizes to `rem` shifts the layout | `InfoPanel.dom.test.tsx` passes but the panel looks off | Normal (14 px) must look exactly as before: compare screenshots at Normal before merging. |
| Identical stipple output is impossible at the target speed | a stipple snapshot changes | Keep the old code path, take the smaller safe gains, and leave the backlog line open. |
| More contrast clashes with the brand | the owner dislikes it | It is an opt-in mode; tune its tokens only. |
| Nobody can run NVDA with a person listening | the checklist has no "heard" column | The speech viewer's text is the record. |

## 11. Handoff

Write in `HANDOFF.md`: each owner decision and its answer; the benchmark table before and after; which of C7, C8, C9 and Track A were built; whether `pnpm build:engine` ran with the new smoke checks; the checklist's state (Windows done, Mac run or not); every spec deviation, one line each.
