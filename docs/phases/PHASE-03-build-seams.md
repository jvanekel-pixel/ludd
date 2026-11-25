# Phase 3: Build seams, spiral fill, more shapes

| | |
| --- | --- |
| Weight | Heavy (architecture). Do it on the larger plan. |
| Session lead | Sonnet 5.5. Track A moves the most code: give its worker the stronger model if there is room. |
| Audit | Required, by the top model, before Phase 4 starts. Every later phase stands on this one. |
| Depends on | Phase 2 done; PR #23 (sewing time estimate) merged into `main` |
| Changes stitches | Only the new spiral fill. Everything that exists must sew exactly as before. |
| Closes (compendium) | Spiral fill; Basic shapes (was Partial) |

## 1. Goal and done-when

Today a new fill pattern means editing `stitches.py`, `patterns.py`, `types.ts`, `InfoPanel.tsx` and `actions.ts`, each over 1,000 lines. Two workers cannot do that at once. This phase puts a seam at each of those places, so a later feature is a new file plus one registry line, and three or four workers can build side by side. It then proves the seams by building two real features through them.

**Done when:**

1. Every test that passed before still passes, and `engine/tests/snapshots/digitize.json` and `layout.json` are byte-for-byte unchanged (`git diff --stat main -- engine/tests/snapshots/digitize.json engine/tests/snapshots/layout.json` prints nothing).
2. `python scripts/check.py --all` prints `RESULT: PASS` in 30 lines or fewer.
3. A fill set to Spiral sews one line from the middle out (tests in section 8).
4. Five new shapes add from the Shapes menu and by shortcut.
5. The spiral commit touches no existing file except the registry lines named in section 7, Track D. That is the proof the seams work.
6. `pnpm build:engine` passes its smoke check (the engine's packages moved).

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P3-S1 | Branch, baseline check, changelog heading | No | Step 0 |
| P3-A1 | `layout.py` becomes the `layout/` package | No | A |
| P3-A2 | Render hooks: item ops and cross-item passes | No | A |
| P3-A3 | Fill pattern registry (`digitize/fills/`) | No | A |
| P3-A4 | Line style and motif registry (`digitize/lines/`) | No | A |
| P3-A5 | `methods.py` becomes the `methods/` package, with a method list test | No | A |
| P3-A6 | Project feature flags as a table | No | A |
| P3-B1 | Command registry that feature files add to (`cmd/`) | No | B |
| P3-B2 | Panel split: `controls.tsx`, `FilePanel.tsx`, `ObjectPanel.tsx` | No | B |
| P3-B3 | Fill pattern and line style descriptors drive the panel | No | B |
| P3-B4 | Dialog registry | No | B |
| P3-B5 | Canvas hooks: overlays, tools, snap sources | No | B |
| P3-C1 | `scripts/check.py`: one quiet command for every check | No | C |
| P3-C2 | `scripts/kb_commands.py` reads `cmd/*.ts`; `--check` mode | No | C |
| P3-C3 | Snapshot files per suite (`snapshot_util.py`) | No | C |
| P3-C4 | Stitch invariants (`invariants.py`) | No | C |
| P3-D1 | Spiral fill | Yes | D (wave 2) |
| P3-E1 | Rounded rectangle, oval, triangle, polygon, heart | Yes | E (wave 2) |
| P3-Z1 | Docs, frozen-engine smoke check, handoff | – | Integration |

**Out of scope:** splitting `actions.ts` or `StitchCanvas.tsx` into parts (new code goes in new files instead; see the rules in section 7), any change to existing stitch output, version bumps, schemas.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Tag v1.0.1 before this phase merges, so 1.0.1 is the hardening release alone? | Yes. Tag from the commit that merges PR #23. | The phase leaves version numbers alone and writes its changelog under a new `## Next (unreleased)` heading above `## 1.0.1`. |
| 2 | May workers commit on `phase-03/*` branches? | Yes; the kickoff prompt says so. Nothing is pushed until the owner says. | Without it the session builds one track at a time in the working tree and commits nothing. |

## 4. Preflight

Run these before any edit. If one fails, stop and report it.

| Check | Command | Expect |
| --- | --- | --- |
| PR #23 is in | `git ls-files apps/desktop/src/design/estimate.ts` | prints the path |
| Clean tree | `git status --short` | empty |
| Layout is still one file | `git ls-files engine/threadline_engine/layout.py` | prints the path |
| Method count | `grep -c "@dispatcher.method" engine/threadline_engine/methods.py` | 60 |
| Commands live in actions.ts | `grep -n "export const COMMANDS: Command\[\] = \[" apps/desktop/src/actions.ts` | one match |
| Baseline is green | AGENTS.md verification commands (engine tests, typecheck, UI tests) | all pass; write the counts into the session notes |

## 5. Architecture

### 5.1 Engine after this phase

```
engine/threadline_engine/
  layout/                 was layout.py (1,174 lines)
    __init__.py           re-exports every name the old module had
    model.py              LayoutError, Transform, Block, small helpers
    files.py              placed stitch files: load, ops, transform
    objects.py            drawn shapes -> blocks
    text.py               lettering -> blocks
    joins.py              same-thread joins, cover, footprint, color sort
    order.py              optimize_order
    extras.py             basting, knockdown, applique SVG
    passes.py             NEW: render hooks (empty lists)
    render.py             render, render_summary, check
    export.py             export, preview_export, split
  digitize/
    fills/__init__.py     NEW: FillPattern, REGISTRY, register, get
    fills/builtin.py      NEW: the six patterns, registered
    fills/spiral.py       NEW (Track D)
    lines/__init__.py     NEW: LineStyle, REGISTRY, MOTIF_UNITS
    lines/builtin.py      NEW: single, triple, bean, motif + four motifs
  methods/                was methods.py (390 lines)
    __init__.py           imports each group below, re-exports dispatcher
    registry.py           dispatcher = Dispatcher()
    core.py designs.py machines.py threads.py layouts.py projects.py
    tracing.py shapes.py text.py ai.py help.py
```

### 5.2 UI after this phase

```
apps/desktop/src/
  commands.ts             + COMMANDS (the one shared list) and registerCommands()
  actions.ts              core list renamed CORE_COMMANDS, registered at import
  cmd/index.ts            NEW: side-effect imports of every feature command file
  cmd/shapes.ts           NEW (Track E)
  dialogs.tsx             NEW: registerDialog(), <DialogHost />
  canvas/hooks.ts         NEW: registerOverlay(), registerCanvasTool(), registerSnap()
  design/fillPatterns.ts  NEW: FILL_PATTERN_DEFS
  design/lineStyles.ts    NEW: LINE_STYLE_DEFS, MOTIF_DEFS
  design/shapes.ts        NEW (Track E): shapeNodes for eight shapes
  components/controls.tsx NEW: Stepper, NumberField, Check, Cmd, DensitySlider, UnderlayButtons, SizeFields
  components/FilePanel.tsx    NEW: FileSections (moved)
  components/ObjectPanel.tsx  NEW: ObjectSections and friends (moved, now data-driven)
  components/InfoPanel.tsx    keeps Order & colors, Design, Pictures, Inspector
```

### 5.3 Rules the seams create (later phases follow these)

- A new **fill pattern** is `digitize/fills/<name>.py` + one import line in `fills/__init__.py` + one entry in `design/fillPatterns.ts` + one name in the `FillPattern` union in `types.ts` + one feature flag. Nothing else.
- A new **line style or motif** is the same with `digitize/lines/` and `design/lineStyles.ts`.
- A new **RPC method** goes in the `methods/` group file for its area and its name goes in `engine/tests/snapshots/rpc_methods.json`.
- A new **command** goes in `cmd/<area>.ts` with `registerCommands([...])`. `actions.ts` gets no new commands.
- New **feature logic** goes in a new file (`src/feat/<area>.ts` or beside its component), never appended to `actions.ts` or `features.ts`.
- A new **dialog** is a component registered with `registerDialog(id, Component)` and opened with `setDialog(id)`.
- New **canvas drawing or pointer handling** registers an overlay, tool or snap source in `canvas/hooks.ts`. `StitchCanvas.tsx` is edited only to add a hook call site that does not exist yet.
- A new **edit on a placed stitch file** is an item op registered in `layout/passes.py`; a step that looks across items is a pass.
- New **stitch snapshots** go in their own suite file, named after the feature.

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-03/build-seams` from `main`.
2. Add the changelog heading per decision 1.
3. Commit ("Phase 3: start"). Workers branch from this commit.

There are no shared-file stubs to seed in wave 1: tracks A, B and C own disjoint files (section 7 lists them). Wave 2's two registry lines are listed under Tracks D and E.

## 7. Tracks

Wave 1 runs A, B and C together. Wave 2 runs D and E together, after wave 1 is merged and `python scripts/check.py` is green.

Every worker follows "Worker rules" in `BUILDPLAN.md`: tests first, own files only, no edits to docs, return 20 lines or fewer.

---

### Track A: engine seams

**Owns:** `engine/threadline_engine/layout.py` → `layout/**`, `digitize/stitches.py`, `digitize/patterns.py`, `digitize/fills/**`, `digitize/lines/**`, `methods.py` → `methods/**`, `project.py` (the features part only), new `engine/tests/test_seams_engine.py`, new `engine/tests/snapshots/rpc_methods.json`. May change the patch target in three existing tests (listed in A1). **Must not touch** `test_digitize.py`, `test_layout_snapshots.py`, anything under `scripts/` or `apps/`.

**The one rule:** no stitch moves. Do not "tidy" logic while moving it. If a snapshot changes, the move is wrong.

#### P3-A1 `layout/` package

Move each name to the module below. Function bodies move unchanged.

| Module | Names |
| --- | --- |
| `model.py` | `LayoutError`, `Transform`, `Block`, `SCALE_WARN`, `_thread_dict`, `_thread_key`, `_stitch_bounds`, `_index`, `_mm`, `_record_count` |
| `files.py` | `_cache`, `_CACHE_MAX`, `_load`, `_split_blocks`, `_apply_ops`, `_move_stitches`, `_jumps_to_trims`, `_transform` |
| `objects.py` | `OBJECT_KINDS`, `OBJECT_LABEL`, `DEFAULT_THREAD`, `_object_cache`, `_OBJECT_CACHE_MAX`, `_generate_cached`, `_object_blocks` |
| `text.py` | `_text_cache`, `_letter_ring`, `text_letters`, `_text_block`, `text_to_shapes` |
| `joins.py` | `_join`, `_merge_same`, `_join_objects`, `COVER_CLOSE_MM`, `_cover_cache`, `_cover`, `_join_same_thread_objects`, `_footprint_cache`, `_footprint`, `_blocks_overlap`, `_sort_by_thread` |
| `order.py` | `optimize_order` |
| `extras.py` | `BASTING_STITCH_MM`, `BASTING_MIN_MM`, `BASTING_THREAD`, `_basting`, `KNOCKDOWN_THREAD`, `KNOCKDOWN_SPACING_MM`, `_stitched_area`, `_knockdown`, `applique_svg`, `_xml`, `export_applique_svg` |
| `render.py` | `Rendered`, `render`, `render_summary`, `_names`, `check` |
| `export.py` | `split_plan`, `export_split`, `preview_export`, `export` |

Import direction, with no cycles: `model` imports nothing from the package; `files`, `objects`, `text`, `joins`, `extras`, `passes` import `model`; `render` imports those; `order` and `export` import `render`.

`layout/__init__.py` re-exports every name in the table (the same objects, so `layout._text_cache` is the dict `text.py` uses). Find every other user first: `grep -rnE "layout(_module)?\.[A-Za-z_]+|from \.layout import|from threadline_engine\.layout" engine scripts`.

Three tests patch a module global and must patch the module that now reads it. Change the target only:
- `test_layout.py`: `monkeypatch.setattr(layout, "_CACHE_MAX", 3)` → `layout.files`
- `test_project.py`: `monkeypatch.setattr(layout, "_cache", {})` → `layout.files`
- `test_qa4_coverage.py`: `monkeypatch.setattr(layout, "_blocks_overlap", …)` → `layout.joins`

Delete `layout.py` in the same commit that adds the package (a module and a package of one name cannot coexist).

#### P3-A2 Render hooks

New `layout/passes.py`:

```python
@dataclass
class OpContext:
    item: dict            # the layout item
    index: int            # its position in layout["items"]
    transform: Transform  # an op may replace it (e.g. to take over the scaling)
    center: tuple[float, float]   # in 0.1 mm, as _transform takes it
    fabric: str | None
    notes: list[str]      # plain-words notes; render turns them into warnings

ItemOp = Callable[[list[Block], dict, OpContext], list[Block]]   # (blocks, op, ctx) -> blocks
Pass   = Callable[[list[Block], dict, list[dict]], list[Block]]  # (blocks, layout, warnings) -> blocks

ITEM_OPS_LOCAL:  dict[str, ItemOp] = {}   # run before the item's transform (the file's own frame)
ITEM_OPS_PLACED: dict[str, ItemOp] = {}   # run after it (hoop millimeters x 10)
AFTER_ITEMS: list[tuple[str, Pass]] = []  # after every item is rendered, before color sort
AFTER_ORDER: list[tuple[str, Pass]] = []  # after sort, join and merge; before knockdown and basting

def register_item_op(name: str, fn: ItemOp, *, stage: str) -> None: ...   # "local" | "placed"; a name twice raises
def register_pass(stage: str, name: str, fn: Pass) -> None: ...           # "after_items" | "after_order"
```

In `render()`, file branch: after `_apply_ops` and the local `_move_stitches`, run each op in `it["ops"]` whose name is in `ITEM_OPS_LOCAL`, in list order; call `_transform` with `ctx.transform`; after the non-local `_move_stitches`, run those in `ITEM_OPS_PLACED`. After the item loop run `AFTER_ITEMS`, then the existing "drop empty blocks" filter. After the sort/join/merge block run `AFTER_ORDER`. With the registries empty the output is identical. Unknown op names stay ignored, as now.

Notes from `ctx.notes` become warnings with code `item_<index>_<n>`.

#### P3-A3 Fill pattern registry

New `digitize/fills/__init__.py`:

```python
@dataclass(frozen=True)
class Param:
    default: float
    lo: float
    hi: float
    label: str            # for the error text: "<label> must be between <lo> and <hi> mm"

@dataclass(frozen=True)
class FillPattern:
    name: str
    kind: str                                   # "rows" (tatami rows) | "open" (lines over the shape)
    params: dict[str, Param] = field(default_factory=dict)   # settings beyond FillParams' own fields
    paths: Callable | None = None               # open: (poly, params, pos) -> (list[list[Point]], list[str])
    rows: Callable | None = None                # rows: (params) -> extra keyword arguments for tatami()
    step_mm2: Callable | None = None            # (params) -> fabric area per stitch, for the MAX_STITCHES guard
    tatami_underlay: bool = True                # may it have the cross-hatch underlay?
    auto_underlay: Callable | None = None       # (level) -> list[str]; None = today's rule

REGISTRY: dict[str, FillPattern] = {}
def register(p: FillPattern) -> None: ...       # a name twice raises
def get(name: str) -> FillPattern: ...          # unknown -> DigitizeError(f"Unknown fill pattern: {name}")
from . import builtin  # noqa: E402  (registers the six, in today's order)
```

`fills/builtin.py` registers, in this order, `tatami`, `gradient`, `wave`, `contour`, `stipple`, `cross`:

| Name | Kind | `rows` / `paths` | `step_mm2` | Notes |
| --- | --- | --- | --- | --- |
| tatami | rows | `{}` | spacing × stitch | |
| gradient | rows | `{"sparse_to": p.gradient_to_mm}` | spacing × stitch | `tatami_underlay=False` |
| wave | rows | `{"wave": (p.wave_mm, p.wave_length_mm)}` | spacing × stitch | |
| contour | open | `contour_paths(poly, p.spacing_mm, p.stitch_mm, pos)` | spacing × stitch | |
| stipple | open | today's stipple branch of `_open_paths`, bare-area warning included | spacing × min(stitch, 2.5) | |
| cross | open | today's cross branch, with the `_subdivide` step | cross_mm² / 4 | |

`builtin.py` imports from `..patterns` at the top and from `..stitches` only inside function bodies (`stitches` imports `fills`; the other way round would be a cycle).

Changes in `stitches.py`, and only these:
- `FillParams` gains `extra: dict[str, float] = field(default_factory=dict)` and a method `value(key)` (field if it is one, else `extra[key]`).
- `FillParams.from_dict`: read `pattern` first; `spec = fills.get(pattern)` replaces the `FILL_PATTERNS` membership test (same error text); when `underlay == "auto"` and `spec.auto_underlay` is set, use it; for each `key, param` in `spec.params`, read with `_finite(d, key, param.default)`, check the range, store in `extra`. Every existing check and message stays word for word.
- `_fill_part`: `open_pattern = spec.kind == "open"`; open paths come from `spec.paths`; the cross-hatch underlay condition becomes `"tatami" in params.underlay and spec.kind == "rows" and spec.tatami_underlay`; the `tatami(...)` call takes `**spec.rows(params)` in place of the two inline conditionals.
- `fill()`: the guard's `step` comes from `spec.step_mm2(params)`.
- `OPEN_PATTERNS` keeps its name and becomes `tuple(n for n, p in fills.REGISTRY.items() if p.kind == "open")`.
- `_open_paths` is deleted (its three branches now live in `builtin.py`).

`patterns.FILL_PATTERNS` stays as a constant for any importer, with a comment pointing to the registry.

#### P3-A4 Line style and motif registry

New `digitize/lines/__init__.py`:

```python
@dataclass(frozen=True)
class LineStyle:
    name: str
    params: dict[str, Param] = field(default_factory=dict)   # Param from digitize.fills
    points: Callable = None     # (nodes, params, closed, start) -> list[Point]: the needle points, in order

REGISTRY: dict[str, LineStyle] = {}
MOTIF_UNITS: dict[str, list[tuple[float, float]]] = {}   # one repeat: x 0..1 along the line, y -0.5..0.5 across
def register(s: LineStyle) -> None: ...
def register_motif(name: str, unit: list[tuple[float, float]]) -> None: ...
```

`lines/builtin.py` registers `single`, `triple`, `bean`, `motif` with exactly the point lists `running()` builds today, and the four motif units that `patterns._motif_unit` returns today (`wave`, `zigzag`, `scallop`, `blanket`). `running()` becomes a lookup plus `stitch_run(...)`. `_motif_unit(name)` reads `MOTIF_UNITS`. `RunParams` gains `extra` like `FillParams`. Messages unchanged.

#### P3-A5 `methods/` package

`methods/registry.py` holds `dispatcher = Dispatcher()`. Each group file does `from .registry import dispatcher` and holds its methods, bodies unchanged. Imports that are inside a method body today stay inside it (they keep the frozen engine's start-up fast).

| File | Methods |
| --- | --- |
| `core.py` | `ping`, `engine.info`, `engine.shutdown`, `formats.list` |
| `designs.py` | `design.open`, `design.preview_export`, `design.export`, `design.convert_folder`, `library.scan` |
| `machines.py` | `machines.list`, `fabrics.list` |
| `threads.py` | `threads.charts`, `threads.chart`, `threads.import_csv`, `threads.delete_chart`, `threads.my_add`, `threads.my_remove`, `threads.match` |
| `layouts.py` | `layout.render`, `layout.preview_export`, `layout.export`, `layout.check`, `layout.split_plan`, `layout.export_split`, `layout.optimize_jumps`, `layout.optimize_order`, `applique.export_svg` |
| `projects.py` | `image.load`, `project.save`, `project.open`, `project.autosave`, `project.recovery`, `project.restore`, `project.discard_recovery` |
| `tracing.py` | `trace.info`, `trace.suggest`, `trace.digitize_all`, `trace.region`, `ai.trace_model`, `ai.trace_model_download`, `ai.trace_model_remove` |
| `shapes.py` | `shape.offset`, `shape.split`, `shape.cut_out`, `shape.satin_fill`, `shape.merge`, `shape.set_end` |
| `text.py` | `text.to_shapes`, `text.letter_frame`, `fonts.list`, `fonts.export_stitch_font` |
| `ai.py` | `ai.settings`, `ai.save_settings`, `ai.set_key`, `ai.test`, `ai.advisor_preview`, `ai.advise` |
| `help.py` | `help.search`, `help.preview`, `help.ask` |

That is 60. `methods/__init__.py` imports the eleven files by name (no `pkgutil` scanning: PyInstaller must see the imports) and re-exports `dispatcher`, so `from threadline_engine.methods import dispatcher` and `methods.dispatcher._methods` keep working.

`engine/tests/snapshots/rpc_methods.json` holds the sorted list of the 60 names. From now on a phase adds a name there in Step 0 with a stub that raises `APP_ERROR` "not built yet", and the worker fills it in.

#### P3-A6 Project feature flags as a table

In `project.py`, `_features()` becomes two tables and a loop; `KNOWN_FEATURES` is derived and must equal today's seven names.

```python
LAYOUT_FEATURES: dict[str, Callable[[dict], bool]] = {"travel_under": …, "trim_jumps_all": …}
ITEM_FEATURES: dict[str, Callable[[dict, dict, dict], bool]] = {   # (item, params, geometry)
    "fill_patterns": …, "motif_lines": …, "satin_ribbons": …, "text_on_path": …, "stitch_edits": …}
KNOWN_FEATURES = set(LAYOUT_FEATURES) | set(ITEM_FEATURES)
```

Naming rule for later phases: a pattern or style added after 1.0.1 gets its own flag (`fill_spiral`, `line_backstitch`). 1.0.1 knows `fill_patterns` and would try to sew a pattern it has never heard of; with its own flag, 1.0.1 says "update LUDD to open it".

#### Track A tests (`engine/tests/test_seams_engine.py`)

| Test | Proves |
| --- | --- |
| `test_layout_package_keeps_every_old_name` | each name in the A1 table is an attribute of `threadline_engine.layout` |
| `test_layout_caches_are_shared_objects` | `layout._text_cache is layout.text._text_cache`, same for `_object_cache`, `_cover_cache`, `_footprint_cache`, `files._cache` |
| `test_render_hooks_start_empty` | all four registries are empty on import |
| `test_placed_item_op_runs_after_the_transform` | a test op registered for the test sees coordinates already scaled; unregistered again in teardown |
| `test_local_item_op_can_take_over_scaling` | an op that sets `ctx.transform` scale to 1 leaves the stitches unscaled |
| `test_after_items_pass_can_drop_a_block` | and the layout still renders without that color |
| `test_six_fill_patterns_registered_in_order` | `list(fills.REGISTRY)` is the six, in order |
| `test_unknown_fill_pattern_message_unchanged` | `Unknown fill pattern: nope` |
| `test_registered_pattern_params_are_range_checked` | a throwaway pattern with `Param(1, 0.5, 2, "Test size")` rejects 3 with `Test size must be between 0.5 and 2 mm` |
| `test_line_styles_and_motifs_registered` | four styles, four motifs |
| `test_rpc_method_list_matches_the_manifest` | sorted `dispatcher._methods` equals `rpc_methods.json` |
| `test_known_features_unchanged` | the seven names |
| `test_feature_tables_match_old_detector` | for a layout using each feature, `_features()` returns the same set as before |

**Track A is done when** those pass, the whole engine suite passes, and the two snapshot files are unchanged.

---

### Track B: UI seams

**Owns:** `apps/desktop/src/commands.ts`, the `COMMANDS` declaration and the two lines after it in `actions.ts`, `cmd/**`, `dialogs.tsx`, `canvas/**`, `design/fillPatterns.ts`, `design/lineStyles.ts`, `components/InfoPanel.tsx`, `components/controls.tsx`, `components/FilePanel.tsx`, `components/ObjectPanel.tsx`, hook call sites in `components/StitchCanvas.tsx`, the `dialog` field in `store.ts`, `App.tsx` (one line), `main.tsx` (one line), `knowledgeBase.test.ts`, new tests. **Must not touch** `engine/`, `scripts/`, `design/types.ts`.

**The one rule:** the app looks and behaves the same. `InfoPanel.dom.test.tsx` passes without edits.

#### P3-B1 Command registry

`commands.ts` gains:

```ts
/** Every command, in dispatch order. actions.ts registers the core list; cmd/*.ts add theirs. */
export const COMMANDS: Command[] = [];
export function registerCommands(list: Command[], opts: { first?: boolean } = {}): void
// throws `Command registered twice: <id>`; opts.first puts them ahead of the core list
```

`actions.ts`: the array literal is renamed `export const CORE_COMMANDS: Command[] = [` (Track C's script looks for exactly this text), followed by `registerCommands(CORE_COMMANDS);` and `export { COMMANDS } from "./commands";`. `command(id)` searches `COMMANDS`. Every existing importer of `COMMANDS` or `command` from `./actions` keeps working.

`cmd/index.ts` is a list of side-effect imports, one per feature file, alphabetical (empty until Track E). `main.tsx` imports `./cmd` once. `actions.ts` never imports `cmd/` (that would be a cycle); a `cmd` file may import `actions.ts`.

A new mode that needs Esc uses `holdEscape`, as now, not a new Escape command. `first: true` is for a mode that must claim Enter, Tab or Delete ahead of the core commands.

`knowledgeBase.test.ts` adds `import "./cmd";` so it checks feature commands too.

#### P3-B2 Panel split

Pure moves out of `InfoPanel.tsx`:

| To | What |
| --- | --- |
| `controls.tsx` | `Cmd`, `NumberField`, `Check`, `toggled`, `DensitySlider`, `Stepper`, `UnderlayButtons`, `SizeFields`, `fmtLen`, `toUnits`, `fromUnits` |
| `FilePanel.tsx` | `FileSections` |
| `ObjectPanel.tsx` | `DENSITY`, `KIND_TITLE`, `KIND_PLURAL`, `UNDERLAY_KINDS`, `PatternRows`, `RememberedNote`, `AdvisorButton`, `objectSummary`, `ObjectSections`, `ThreadPickerFor` |

`InfoPanel.tsx` re-exports `fmtLen`, `objectSummary` and anything else another file imports from it today (`grep -rn "from \"./InfoPanel\"\|from \"./components/InfoPanel\"" apps/desktop/src`).

#### P3-B3 Descriptors

`design/fillPatterns.ts`:

```ts
export type Field = { key: string; label: string; def: number; min: number; max: number; step: number; digits?: number; suffix?: string; title?: string };
export type FillPatternDef = {
  id: string; label: string; title: string;
  open?: boolean;        // lines over the shape: no Angle, Random, Edge pad or cross-hatch underlay
  noSpacing?: boolean;   // ignores row spacing too: Density, slider and Spacing are hidden
  noLength?: boolean;    // no stitch Length field
  maxStitch?: number;    // longest Length offered (default 7)
  fields: Field[];
  hint?: string;
  summary?: "label" | "label+density";   // folded heading for open patterns
};
export const FILL_PATTERN_DEFS: FillPatternDef[];
export const fillPatternDef: (id?: string) => FillPatternDef;   // unknown or missing -> tatami
```

The six entries, copied from today's `PatternRows` and `ObjectSections`:

| id | label | flags | fields (key, label, default, min–max, step, digits) |
| --- | --- | --- | --- |
| tatami | Tatami | – | – |
| gradient | Gradient | – | `gradient_to_mm` Sparse end 1.6, 0.3–5, 0.1, 1 |
| wave | Wave | – | `wave_mm` Wave height 1.5, 0.3–6, 0.25 · `wave_length_mm` Wave length 8, 2–40, 1, 0 |
| contour | Contour | open, summary label+density, hint as today | – |
| stipple | Stipple | open, noSpacing, maxStitch 2.5, summary label | `stipple_mm` Loop size 3, 1–10, 0.5, 1 |
| cross | Cross-stitch | open, noSpacing, noLength, summary label | `cross_mm` Square 2.5, 1–8, 0.5, 1 |

Titles are the strings in today's `PATTERNS` and `Stepper` calls. `ObjectPanel.tsx` reads these instead of its `PATTERNS`, `OPEN_PATTERNS` and per-pattern JSX; `objectSummary` reads `summary`.

`design/lineStyles.ts`: `LINE_STYLE_DEFS` (single "Single", triple "Triple", bean "Bean", motif "Motif", with today's tooltips) and `MOTIF_DEFS` (wave, zigzag, scallop, blanket "Blanket stitch (applique edge)") plus the two motif fields (`motif_mm` Repeat 4, 1.5–20, 0.5, 1; `motif_width_mm` Width 2.5, 0.5–10, 0.5, 1). The Style row stays four buttons.

#### P3-B4 Dialog registry

`dialogs.tsx`: `registerDialog(id: string, C: ComponentType)` and `<DialogHost />`, which renders the component registered for `store.dialog`, mounted only while open. `store.dialog` widens to `string | null`. The three existing dialogs (`offset`, `browse`, `names`) stay as they are. `App.tsx` renders `<DialogHost />` beside them.

#### P3-B5 Canvas hooks

`canvas/hooks.ts`:

```ts
export type CanvasCtx = { toMm(e: { clientX: number; clientY: number }): [number, number]; pxMm(): number; redraw(): void };
export type Overlay = { id: string; draw(g: Graphics, px: number, ctx: CanvasCtx): void };
export type CanvasTool = { id: string; active(): boolean; cursor?: string;
  down?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean;   // true = handled, the canvas does nothing more
  move?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean;
  up?(p: [number, number], e: PointerEvent, ctx: CanvasCtx): boolean };
export type SnapSource = { id: string; snap(p: [number, number], radiusMm: number): [number, number] | null };
export function registerOverlay(o: Overlay): () => void;       // each returns an "unregister"
export function registerCanvasTool(t: CanvasTool): () => void;
export function registerSnap(s: SnapSource): () => void;
```

Call sites in `StitchCanvas.tsx`, each one added line: overlays at the end of `drawOverlay`; the active tool first in the pointer down, move and up handlers; snap sources after grid snapping where a new point's position is decided. With nothing registered, nothing changes. These are internal: the first phase that uses one may adjust its shape.

#### Track B tests

| Test (file) | Proves |
| --- | --- |
| `registerCommands refuses a duplicate id` (`commands.test.ts`) | throws |
| `every command has a title and a shortcut` (`commands.test.ts`) | over `COMMANDS` after `import "./cmd"` |
| `core commands keep their order` (`commands.test.ts`) | first id is `stitch.deleteSelected`, `COMMANDS.length` ≥ 167 |
| `the six fill patterns show the fields they showed before` (`components/ObjectPanel.dom.test.tsx`) | for each pattern, the list of row labels equals a fixed list written from today's UI |
| `stipple hides Density; cross hides Length` (same) | flags work |
| `objectSummary is unchanged` (same) | "Normal · 45°", "Contour · Light", "Stipple", "3 mm wide · Normal" |
| `fillPatternDef falls back to tatami` (`design/fillPatterns.test.ts`) | unknown id |
| `a registered dialog mounts only while open` (`dialogs.dom.test.tsx`) | |
| `hooks register and unregister` (`canvas/hooks.test.ts`) | |

**Track B is done when** those pass with `pnpm typecheck`, `pnpm test` and the desktop build.

---

### Track C: tooling

**Owns:** `scripts/check.py`, `scripts/kb_commands.py`, `engine/tests/snapshot_util.py`, `engine/tests/invariants.py`, `engine/tests/test_invariants.py`, `engine/tests/test_check_script.py`, the snapshot helper lines in `engine/tests/test_digitize.py` and `test_layout_snapshots.py`, any other reader of `actions.ts` outside the app (`grep -rn "actions.ts" scripts engine/tests`).

#### P3-C1 `scripts/check.py`

One command that runs the checks and prints a verdict a session can read in a glance. Standard library only.

| Flag | Runs |
| --- | --- |
| (none) | engine tests, typecheck, UI tests, knowledge-base command table check |
| `--all` | the above plus the desktop build and the Rust tests |
| `--engine` / `--ui` | only that side |
| `-k EXPR` | passed to pytest `-k` and vitest `-t` |
| `--record a,b` | sets `UPDATE_SNAPSHOTS=a,b` for those suites (and does not set `CI`) |
| `--json` | the same results as JSON |

Stage commands: `uv run --locked pytest -q -rf` in `engine/`; `pnpm typecheck`; `pnpm test`; `python scripts/kb_commands.py --check`; `pnpm --filter @threadline/desktop build`; `cargo test --locked --lib --manifest-path apps/desktop/src-tauri/Cargo.toml` (skipped with a note when `cargo` or the sidecar binary is missing). `CI=1` is set unless recording, so a missing snapshot fails instead of being written. Resolve `pnpm` and `uv` with `shutil.which` (on Windows `pnpm` is `pnpm.cmd`). Decode output as UTF-8 with `errors="replace"`.

Output, 30 lines at most:

```
LUDD check  (phase-03/build-seams @ 1a2b3c4)
engine  PASS   712 passed, 1 skipped          41 s
types   PASS                                   9 s
ui      FAIL   243 passed, 2 failed           22 s
          components/ObjectPanel.dom.test.tsx > stipple hides Density
            expected [ 'Pattern', 'Loop size' ] to equal [ 'Pattern' ]
          …
kb      PASS
RESULT: FAIL (ui)   full output: _logs/check-ui.log
```

At most six failing tests per stage, two lines each. Full output goes to `_logs/check-<stage>.log` (already git-ignored). Exit code 0 or 1. The parsing functions (`parse_pytest`, `parse_vitest`, `parse_tsc`, `render`) are pure and tested with canned output in `test_check_script.py`, including a 300-failure run that still renders in 30 lines.

#### P3-C2 `scripts/kb_commands.py`

Reads the core block (starts at `export const CORE_COMMANDS: Command[] = [`; falls back to the old `COMMANDS` text so it works before Track B merges) and then every `apps/desktop/src/cmd/*.ts` in name order, each file's `registerCommands([` block. `--check` writes nothing and exits 1 with "run python scripts/kb_commands.py" when the table would change. Any other reader of `actions.ts` found by the grep gets the same two sources.

#### P3-C3 `engine/tests/snapshot_util.py`

```python
def check(suite: str, name: str, got: dict) -> None      # compare with snapshots/<suite>.json or record
def digest_recs(recs) -> dict                             # records, stitches, jumps, trims, sha1 (as test_digitize does)
def digest_pattern(pattern) -> dict                       # the same plus thread colors (as test_layout_snapshots does)
```

Same file format as today (`indent=1`, `sort_keys=True`, trailing newline), so the two existing files do not change. Missing entry with `CI` set fails with today's message. `UPDATE_SNAPSHOTS` is `1` or `all` for every suite, or a comma list of suite names. `test_digitize.py` and `test_layout_snapshots.py` call `check("digitize", …)` and `check("layout", …)`; their own `_digest` functions stay.

#### P3-C4 `engine/tests/invariants.py`

Checks every stitch type must pass, so a reviewer reads numbers, not code.

```python
def stitch_points(recs) -> list[tuple[float, float]]
def longest_stitch(recs) -> float
def count(recs, kind) -> int
def assert_sane(recs, *, inside=None, tolerance_mm=0.6, max_stitch_mm=7.15, max_jumps=None, max_trims=None,
                starts_near=None, ends_near=None, near_mm=1.0) -> None
def assert_deterministic(make) -> None                 # make() twice gives identical records
def assert_moves_with_shape(obj, dx, dy) -> None       # generate(moved obj) == generate(obj) shifted, to 0.01 mm
def coverage(recs, poly, reach_mm) -> float            # share of poly within reach_mm of a stitch line
def thread_per_mm2(recs, poly) -> float
```

`test_invariants.py` runs `assert_sane` and `assert_deterministic` over the 27 cases in `test_digitize.SNAPSHOT_CASES`. A case that breaks an invariant today is not "fixed": it gets a named exemption with a one-line reason, so the helper stays strict for new work.

**Track C is done when** `python scripts/check.py` runs green on the phase branch and its own tests pass.

---

### Track D (wave 2): spiral fill

**Owns:** new `digitize/fills/spiral.py`, new `engine/tests/test_fill_spiral.py`, new `engine/tests/snapshots/fills_spiral.json`. **Registry lines it may add, and nothing else in these files:** one import in `fills/__init__.py`; one entry in `design/fillPatterns.ts`; `"spiral"` in the `FillPattern` union and `spiral_mm?: number` in `FillParams` in `design/types.ts`; one line in `project.ITEM_FEATURES`.

**Behavior.** Pattern "Spiral": one line that winds from the middle of the shape out to its edge. An open pattern: no Angle, Random, Edge pad or cross-hatch underlay. On automatic underlay it has none (an edge run would need a cut to get from the edge to the middle); the user can still pick Edge.

**Setting.** `spiral_mm` "Ring spacing", default 1.5, range 0.4 to 6, step 0.1, one decimal. Stitch length as for other fills, capped at 4 mm in the panel (`maxStitch: 4`). Flags in the descriptor: `open`, `noSpacing`, summary "label".

**Algorithm.**

1. Middle `c`: `shapely.maximum_inscribed_circle(poly)` center if shapely has it, else `poly.representative_point()`.
2. `R` = greatest distance from `c` to an exterior vertex, plus `spiral_mm`.
3. Archimedean spiral `r = a·θ`, `a = spiral_mm / 2π`, from `r = spiral_mm / 2`. Sample by arc length every 0.5 mm: `θ += 0.5 / sqrt(r² + a²)`, until `r > R`.
4. Clip to the shape: `LineString(points).intersection(poly)`. Keep pieces longer than 1 mm, in order along the spiral.
5. Needle points on each piece: walk the 0.5 mm samples and drop a stitch whenever the length since the last one reaches `clamp(2·sqrt(0.3·r), 0.8, stitch_mm)`. Tight turns near the middle get short stitches; outer rings get full ones.
6. Return the pieces as paths. The existing `_sew_paths` joins them with travel inside the shape.

Registration: `FillPattern("spiral", "open", params={"spiral_mm": Param(1.5, 0.4, 6.0, "Ring spacing")}, paths=…, step_mm2=lambda p: p.value("spiral_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: [])`.

Warning when `spiral_mm < 0.6`: "Rings this close sew like a solid fill and can pucker in the middle; 1 mm or more is safer."

Feature flag: `fill_spiral` (item is a fill or applique with `pattern == "spiral"`).

**Tests** (`test_fill_spiral.py`; 40 mm square at (0,0)–(40,40) unless said):

| Test | Asserts |
| --- | --- |
| `test_spiral_is_registered_as_open` | `fills.get("spiral").kind == "open"` |
| `test_square_is_one_line_from_the_middle` | first stitch within 1.5 mm of (20, 20); no jumps, no trims; `assert_sane(inside=square, tolerance_mm=0.3, max_stitch_mm=stitch_mm + 0.05)` |
| `test_rings_are_evenly_spaced` | crossings of the ray from the middle at 0° are `spiral_mm` ± 0.15 apart |
| `test_it_reaches_the_corners` | each corner has a stitch within `spiral_mm + 0.5` |
| `test_short_stitches_near_the_middle_long_ones_outside` | mean stitch within 3 mm of the middle < mean stitch beyond 15 mm; none under `MIN_STITCH_MM` apart from ties |
| `test_a_hole_stays_empty` | donut: no stitch inside the hole shrunk by 0.3 mm |
| `test_ring_spacing_is_checked` | 0.2 → `Ring spacing must be between 0.4 and 6 mm` |
| `test_tight_rings_warn` | 0.5 → the warning above |
| `test_no_underlay_on_automatic` | with `underlay: "auto"` the first stitch is at the middle |
| `test_moves_with_the_shape`, `test_deterministic` | the invariants |
| `test_snapshots` | suite `fills_spiral`: `square_40`, `donut`, `star`, `tight_0_6` |
| `test_project_names_the_feature` | `_features()` includes `fill_spiral` |

UI: `design/fillPatterns.test.ts` gains "spiral has Ring spacing 1.5 (0.4 to 6)"; `ObjectPanel.dom.test.tsx` gains "Spiral shows Ring spacing and hides Density and Angle".

**Done when** those pass and `git diff --stat phase-03/build-seams` for this track shows only the files named above.

---

### Track E (wave 2): more shapes

**Owns:** new `design/shapes.ts`, `design/shapes.test.ts`, `cmd/shapes.ts`, `components/PolygonDialog.tsx`; the Shapes menu items in `components/ToolRail.tsx`; the shape items in `contextMenu.ts`; the `addShape` signature in `actions.ts`; `shapeNodes` in `design/layout.ts` (moved out, re-exported); one import line in `cmd/index.ts`; `polygonSides?: number` in `prefs.ts`.

**Behavior.** The Shapes menu gains five entries under Star. Each adds a fill in the middle of the hoop, selected, like the three it has.

| Command | Shape | Nodes |
| --- | --- | --- |
| `shape.roundedRect` `Mod+Alt+4` | Rounded rectangle, `size` wide, 0.7 × `size` tall, corner radius 0.15 × `size` | three curve points on each corner arc, straight sides between |
| `shape.ellipse` `Mod+Alt+5` | Oval, `size` wide, 0.7 × `size` tall | eight curve points |
| `shape.triangle` `Mod+Alt+6` | Equal-sided, point up, `size` wide | three corners |
| `shape.polygon` `Mod+Alt+7` | Regular polygon, asks how many sides | `n` corners, first at the top |
| `shape.heart` `Mod+Alt+8` | Heart, `size` wide | curve points round the lobes, corners at the dip and the tip |

`shape.polygon` opens a small dialog registered through `registerDialog("polygon", PolygonDialog)`: "Sides" (3 to 12, starts at the last value used, 6 the first time), Add, Cancel. Enter adds; Esc closes through `holdEscape`. This is the first user of the dialog seam.

`design/shapes.ts` exports `type ShapeId` (the eight) and `shapeNodes(shape, cx, cy, size, opts?: { sides?: number })`. The three existing shapes move here unchanged; `design/layout.ts` re-exports `shapeNodes`.

**Tests** (`design/shapes.test.ts`):

| Test | Asserts |
| --- | --- |
| `each shape is centered and the right width` | bounding box center within 0.01 mm of (cx, cy); width `size` ± 0.5 |
| `the three old shapes are unchanged` | equal to fixed node lists copied from today's output |
| `a polygon has n corners, first at the top` | n = 3, 6, 12 |
| `the rounded rectangle stays within 0.35 mm of a true one` | flatten with the helper in `design/paths.ts`, compare with the ideal outline |
| `no shape repeats a point` | consecutive nodes differ |
| `the five commands are registered with their reserved shortcuts` (`cmd/shapes.test.ts`) | |
| `the polygon dialog adds a hexagon on Enter` (`components/PolygonDialog.dom.test.tsx`) | |

**Done when** those pass and the knowledge-base command check passes after `python scripts/kb_commands.py`.

## 8. Integration (session lead)

1. Merge wave 1 in the order C, A, B. Run `python scripts/check.py`. Confirm the two old snapshot files are unchanged.
2. Run `python scripts/kb_commands.py --check` (it now reads `CORE_COMMANDS`).
3. Start wave 2 from the merged branch. Merge D then E. Run `python scripts/check.py --all`.
4. Run `pnpm build:engine` once (slow). Its smoke check must pass: the engine's packages moved, and the frozen build is the only place a missed import shows.
5. Write the docs (section 9). Run `python scripts/kb_commands.py`.
6. `python scripts/check.py --all` one last time, then the stop contract in `BUILDPLAN.md`.

Expected conflicts: none. If two tracks did edit one file, the track that does not own it was wrong; take the owner's version and re-apply the other change by hand.

## 9. Docs payload

**`docs/CHANGELOG.md`**, under the heading from Step 0:

```
### Phase 3: spiral fill, more shapes (YYYY-MM-DD)
- **Spiral fill**: a new fill pattern that winds one line from the middle of the shape out to its edge. Set how far apart the rings are (Ring spacing).
- **More shapes**: the Shapes menu adds a rounded rectangle, an oval, a triangle, a polygon (you choose 3 to 12 sides) and a heart (Ctrl+Alt+4 to 8).
- **Behind the scenes**: the stitch engine and the panel were rearranged so new stitch types and tools can be added without touching the old ones; one command (`python scripts/check.py`) runs every check. Nothing that already existed sews differently.
```

**`docs/LUDD-KNOWLEDGE-BASE.md`:**
- `F-1305 Fill patterns`: add Spiral (what it is, Ring spacing 0.4 to 6 mm, default 1.5, no underlay unless chosen).
- `F-501 Drawing tools`: the Shapes menu's eight shapes and their keys.
- Section 2 index: the "fill patterns" row gains spiral; add "ready-made shapes (rectangle, oval, star, heart, polygon…)? YES, F-501".
- `L-022` (end point on open patterns): add Spiral to its list.
- Section 23 history: one row. Bump *Last updated*. Section 25 is regenerated by the script.

**`docs/USER-MANUAL.md`:** section 4 (Shapes menu) and section 6 (fill patterns table). **`engine/threadline_engine/ai/helpdocs.py`:** the same two facts, with the shortcuts.

**`AGENTS.md`**, Verification Commands: add `python scripts/check.py` ("every check, quiet, 30 lines; `--all` adds the build and the Rust tests") as the first line, and note that the layout and methods modules are now packages in the Layout section. These are static facts, so they belong there.

**`docs/stitchout-log.md`**, one row in "Pending machine tests":

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 3 | **Spiral fill** | A 40 mm circle and a 40 mm star in Spiral at 1.5 mm; the circle again at 0.8 mm | One unbroken line from the middle out; rings evenly spaced; no pucker in the middle at 0.8 mm |

No new `L-` or `T-` entries are expected; the phase's blocks (L-026 to L-029, T-021 to T-022) stay unused unless a build surprise needs one.

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| The `layout/` split changes behavior through a missed module global | a test fails or a snapshot moves | Find the global with the failing test; the fix is always "read it from the module that owns it". Never re-record a snapshot in this phase. |
| The frozen engine misses a new submodule | `pnpm build:engine` smoke check fails with `ModuleNotFoundError` | Make the import explicit in the package's `__init__.py`. |
| The descriptor-driven panel differs subtly from the hand-written one | the fixed label lists in `ObjectPanel.dom.test.tsx` fail | Fix the descriptor, not the test's expected list. |
| Canvas hooks cannot be tested in jsdom | no failing test, but nothing proves the call sites | They are additive and empty. Phase 5 or 7 is their first real use; say so in the handoff. |
| `maximum_inscribed_circle` is missing in the locked shapely | AttributeError | The fallback in step 1 of the spiral algorithm. |
| Wave 1 takes the whole session | context or time runs out | Stop after integration step 2 with wave 1 merged and green. Wave 2 (D and E) is a short session of its own; say so in `HANDOFF.md`. |

## 11. Handoff

Write in `HANDOFF.md`: the test counts before and after; whether `pnpm build:engine` was run; whether the canvas hooks have a real user yet (no); any spec deviation, one line each. Set `project.json` `phase` to 4 only after the owner has merged this phase and the top-model audit has passed.

## 12. Build notes

- Two UI spots outside Track B's files also listed the open patterns by name, so a new open pattern needed more than its registry lines: the fixed red end dot (`components/StitchCanvas.tsx`) and the purple direction dots (`design/direction.ts`). After wave 1 the lead made both read the descriptors (`fixedFillEnd`, `hasDirectionDots` in `design/fillPatterns.ts`). The descriptor gained `directionDots`, set only on cross-stitch so it keeps the dots it has always shown. The six old patterns behave as before.
- Some wave 1 tests would have stopped wave 2: they allowed only the six patterns and seven feature names (`test_seams_engine.py`, `ObjectPanel.dom.test.tsx`), and `contextMenu.test.ts` did not import `./cmd`, so a menu could not offer a `cmd/` command. Before wave 2 the lead changed them: the old items must still be there, in the old order, and the menu test registers the feature commands.
- Track A: `layout.render` and `layout.export` stay the functions (the submodules of those names are reached by import); `text.py` also imports `objects.py` (no cycle); a local item op that replaces `ctx.transform` also changes `center_mm` and the resize warning.
- Track B: canvas overlays run in a wrapper around `drawOverlay` (the old body, now `drawOwnOverlay`, returns early on several paths); `CanvasTool.cursor` is declared but not applied yet; `registerDialog` replaces a repeated id instead of throwing.
- Track C: with `-k`, the UI stage runs vitest through node (`pnpm.cmd` mangles the filter), and an engine run that matches no test counts as skipped.
- Track D: needle points go exactly where the target length is reached (snapping to the next sample made 3.95 mm stitches at 3.5), pieces under 0.3 mm apart are joined, the spiral is built in the shape's own frame so a moved shape sews the same, and `test_it_reaches_the_corners` measures to the sewn thread (needle points alone can't come within 2.0 mm of a square's corners).
- Step 1 of the spiral: a rectangle has many equally wide spots, so the inscribed-circle search could start it well off-center (13 mm on 48 × 24 mm), against "Done when" 3. Where the centroid is inside the shape and as wide as that circle (within 0.1 mm), it is now the middle. This also removes most travel over sewn rings on rectangles.
- Step 6 of the spiral, changed with the owner's approval (2026-11-24): the shared joining went straight across rings already sewn (the ready-made Heart and Oval, ring shapes), so `fills/spiral.py` now joins the pieces itself, along the edge that cut them apart (`_way_round`; never across a ring's band to reach a shorter edge). The shared joining is unchanged.
- Step 4 of the spiral, changed with the owner's approval (2026-11-24): joined in spiral order, the thread piled up on the edge (up to 27 threads in one spot on the Heart). After the first piece, each time comes the piece with an end nearest along the same edge, sewn from that end (`_sewing_order`). A choice that would force a later join across the shape is passed over (Fleury's rule: without it, 16 of 17,036 joins on 49 shapes at 10 spacings left their edge; with it, none). Pieces of 1 mm or less are kept when they are the only way from one edge to another.
- Track E: the rounded rectangle has 20 points (12 were 0.354 mm off at 60 mm); the width test checks the unchanged star's tips on the circle (the star is 57.1 mm wide at 60); the polygon dialog handles Enter and Esc itself, since `keys.ts` ignores keys while a dialog is open.
