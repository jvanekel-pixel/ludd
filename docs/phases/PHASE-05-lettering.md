# Phase 5: Lettering & personalization

| | |
| --- | --- |
| Weight | Heavy. Do it on the larger plan. |
| Session lead | Sonnet 5.5. Step 0 here is a real refactor; do it carefully and alone before any worker starts. |
| Hard track | B (true satin letters): give its worker the stronger model |
| Depends on | Phase 3 (line and motif registry, `layout/text.py`, `methods/`, `cmd/`, dialog registry, canvas hooks) |
| Parallel-safe with | Phases 4, 6, 9, 10, 11, 12 |
| Changes stitches | Yes for new options. Existing text sews the same, except letters under 6 mm (decision 3). |
| Closes (compendium) | Multi-line text · Slant · Envelopes · Vertical baseline · Move, rotate, resize one letter · Recolor one letter · True satin-column letters · Keyboard font from single-letter files ★ · Monograms with ornaments · Drop shadow, outline · Placement templates · Small-letter underlay · Names from a CSV · Layout templates with placeholders · (BX import: investigated, see decision 1) |
| Old plan | Phase 6 |

## 1. Goal and done-when

Lettering is LUDD's largest gap (11 of 17 lettering features missing) and where hobbyists spend the most time. Embrilliance sells one piece of it, AlphaTricks, for $119.

**Done when:**

1. A two-line name, slanted, in an envelope, with one letter moved and recolored, renders from a test project and its snapshot is recorded.
2. A folder of 26 single-letter PES files becomes a stitch font, and "ABC" typed in it sews with the letters on one baseline.
3. "True satin" on the test font gives one column for I, a ring for O and two strokes for T, covering at least 97% of each letter.
4. A CSV of names with a second column fills two placeholders and writes one machine file per row.
5. Every lettering case in `engine/tests/snapshots/layout.json` is unchanged (old text sews the same).
6. `python scripts/check.py --all` prints `RESULT: PASS`.

## 2. Scope

| ID | Item | Changes stitches | Track |
| --- | --- | --- | --- |
| P5-S1 | `lettering.py` becomes a package; text render pipeline gets its seams; contracts | No | Step 0 |
| P5-A1 | Multi-line text, line spacing, left / center / right (lifts L-003) | Yes | A |
| P5-A2 | Slant | Yes | A |
| P5-A3 | Envelopes and vertical text | Yes | A |
| P5-A4 | Adjust single letters: move, turn, size, thread, stitch angle (lifts L-005) | Yes | A |
| P5-B1 | True satin columns from outline fonts (narrows L-014) | Yes | B |
| P5-B2 | Small letters: underlay left out under 6 mm; thin-stroke warning | Yes | B |
| P5-C1 | Stitch font from a folder of single-letter stitch files | Yes | C |
| P5-C2 | BX fonts: a time-boxed look, no code (decision 1) | No | C |
| P5-D1 | Names from a list (CSV) and templates with placeholders | No | D |
| P5-D2 | Monogram styles and frames | Yes | D |
| P5-D3 | Shadow and outline that follow the text | Yes | D |
| P5-D4 | Placement guides | No | D |
| P5-Z1 | Docs, stitch-out rows, handoff | – | Integration |

**Out of scope:** center-out sewing for caps (Phase 8), word art (Phase 13), kerning editor, right-to-left and complex scripts.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | BX fonts are Embrilliance's own package format. May a worker spend one hour looking inside a BX font you own, to see whether it is a plain container? | Skip it. Most sellers ship the same letters as PES or JEF files, and C1 turns those into a font. A closed or protected format must not be worked around. | Skipped. L-036 records "BX: no; use the letter files that came with the font". |
| 2 | Should "True satin" be the default for new text? | Not yet. It stays a choice beside "Satin look" until the stitch-outs in Phase 15 show it is better. | Opt-in. |
| 3 | Leaving underlay out of letters under 6 mm changes how existing small text sews. Accept? | Yes: it is the fix the warning already asks for, and it gets a stitch-out row. | Applied. |
| 4 | Six built-in monogram frames (circle, double circle, diamond, square, scallop circle, laurel). Enough to start? | Yes. | As listed. |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Lettering is still one file | `git ls-files engine/threadline_engine/lettering.py` | the path |
| Text rendering lives here | `grep -n "def text_letters\|def _text_block\|def text_to_shapes" engine/threadline_engine/layout/text.py` | three |
| The cache key | `grep -n '"text", "font", "size_mm"' engine/threadline_engine/layout/text.py` | one |
| Panel | `grep -n "export function SelectedText" apps/desktop/src/components/TextPanel.tsx` | one |
| Names | `grep -n "export async function exportNames" apps/desktop/src/features.ts` | one |
| Tests that patch lettering | `grep -rn "setattr(lettering" engine/tests` | `list_fonts`, `layout_text`, `font_dirs` |
| Lettering snapshots | `python -c "import json;print([k for k in json.load(open('engine/tests/snapshots/layout.json')) if k.startswith('lettering')])"` | five names |
| Baseline | `python scripts/check.py` | `RESULT: PASS` |

## 5. Architecture

### 5.1 Data model (`design/types.ts`, all optional, so old projects are untouched)

```ts
export type TextItem = {
  // …existing fields…
  text: string;                               // may now hold line breaks ("\n")
  style: "satin" | "columns" | "fill";        // "columns" = true satin (B1)
  align?: "left" | "center" | "right";        // default "center"
  line_spacing?: number;                      // x letter height; default 1.3; 0.8 to 3
  slant_deg?: number;                         // -30 to 30; positive leans right
  envelope?: { type: Envelope; amount: number };   // amount 0 to 1, default 0.5
  vertical?: boolean;                         // letters stacked top to bottom
  /** Changes to single letters, by letter number (0 = the first character that draws something). */
  letter_edits?: Record<string, { dx_mm?: number; dy_mm?: number; rotate?: number; scale?: number; thread?: Thread; angle_deg?: number }>;
  monogram_style?: "classic" | "block" | "stacked";
  ornament?: { id: OrnamentId; margin_mm?: number; thread?: Thread };
  shadow?: { dx_mm: number; dy_mm: number; thread: Thread };
  outline?: { gap_mm: number; width_mm: number; style: "satin" | "run"; thread: Thread };
  /** Name templates: this text is filled from a list; `bind` is the column it takes. */
  placeholder?: boolean;
  bind?: string;                              // default "name"
  fit_width_mm?: number;                      // long names shrink to this width
};
export type Envelope = "bulge" | "pinch" | "pennant_right" | "pennant_left" | "wave" | "arch_top" | "arch_bottom";
export type OrnamentId = "circle" | "double_circle" | "diamond" | "square" | "scallop_circle" | "laurel";
export type FontRef = { path: string; index: number; family: string; style: string; made_of?: "stitches" };
```

`LayoutItemInfo.letters[]` gains `letter: number` (which character the part belongs to), `line: number` and `run: number` (which thread run), so the UI can group parts into letters without another call.

### 5.2 Engine after Step 0

```
engine/threadline_engine/
  lettering/               was lettering.py (868 lines)
    __init__.py            re-exports every old name; TEXT_SPEC_KEYS
    fonts.py               font_dirs, list_fonts, resolve_font, substitute_font, LoadedFont, _load, kerning, _glyph_shapes
    glyphs.py              Glyph, _Missing, _outline_glyphs, _fill_object, _satin_angle, _stitch_font_glyphs   (Track B)
    place.py               _clean_text, layout_text, _along_path, _centre, _move, turn_with                    (Track A)
    envelope.py            NEW  slant and envelope maps                                                         (Track A)
    satin.py               NEW  true satin columns                                                              (Track B)
    fontfile.py            stitch_font_dir, _load_stitch_font, export_stitch_font                               (Track C)
    fontbuild.py           NEW  font from letter files                                                          (Track C)
    stitchglyphs.py        NEW  letters made of stitches                                                        (Track C)
    monogram.py            the monogram branch of layout_text, moved                                            (Track D)
    ornaments.py           NEW  frames                                                                          (Track D)
    extras.py              NEW  shadow and outline                                                              (Track D)
  names.py                 NEW  read a list of names                                                            (Track D)
  layout/text.py           letters -> blocks, now a small pipeline                                              (Track A)
  methods/fonts.py         NEW group: fonts.scan_letter_files, fonts.build_from_files                           (Track C)
  methods/names.py         NEW group: names.read_list                                                           (Track D)
```

The text pipeline in `layout/text.py` after Step 0 (each step a function, so tracks touch different ones):

1. `objects, warnings = lettering.layout_text(spec)`: letter parts, each tagged `letter`, `line`.
2. `before, after = lettering.extras.build(spec, objects)`: extra objects sewn before the letters (shadow) and after (outline, frame), each with its thread. Empty lists until Track D.
3. `_apply_letter_edits(objects, spec)`: identity until Track A.
4. `_part_stitches(o)`: `stitchglyphs.records(o)` for `kind == "stitches"`, else `_generate_cached(o)`.
5. `_blocks(parts)`: one block per run of letters in the same thread. One block until Track A adds letter threads.

`_text_block` returns a list of blocks; `render()` extends with it.

### 5.3 UI after Step 0

```
apps/desktop/src/
  components/TextPanel.tsx            SelectedText renders the three slots below in order
  components/text/LayoutControls.tsx  Track A: lines, alignment, slant, envelope, vertical, single letters
  components/text/StyleControls.tsx   Track B: Satin look / True satin / Fill, small-letter notes
  components/text/ExtrasControls.tsx  Track D: monogram style, frame, shadow, outline
  components/FontFromFilesDialog.tsx  Track C, dialog "fontFromFiles"
  components/NamesDialog.tsx          Track D (moved out of FeatureDialogs.tsx)
  components/PlacementDialog.tsx      Track D, dialog "placement"
  feat/letters.ts                     Track A: single-letter mode, canvas tool and overlay
  feat/names.ts                       Track D: lists, placeholders, templates
  design/placements.ts                Track D: the guide data
  cmd/lettering.ts                    the five commands (Step 0, stub handlers)
```

### 5.4 RPC

| Method | Parameters | Returns | Track |
| --- | --- | --- | --- |
| `fonts.scan_letter_files` | `folder: str` (or `files: list`) | `{ files: [{ path, name, guess, thumb, width_mm, height_mm, stitches, colors }], common: { prefix, suffix } }` | C |
| `fonts.build_from_files` | `letters: [{ path, char, dy_mm? }]`, `name: str`, `gap_pct: float = 8`, `dest: str = ""` | `{ path, glyphs, cap_height_mm, folder }` | C |
| `names.read_list` | `path: str` | `{ columns: [str], rows: [[str]], skipped: int }` | D |

## 6. Step 0 (session lead, committed before workers start)

This is the phase's risky part. No stitch may move: the five lettering snapshots and `test_lettering.py` are the proof.

1. `git switch -c phase-05/lettering`.
2. Split `lettering.py` into the package in 5.2, moving function bodies unchanged. `__init__.py` re-exports every name the module had (find users with `grep -rnE "lettering\.[A-Za-z_]+" engine scripts`). Three tests patch a module global; point each at the module that now reads it (`lettering.fonts` for `list_fonts` and `font_dirs`; `layout_text` is looked up through the package by `layout/text.py`, so keep calling it as `lettering.layout_text(spec)`).
3. Move the monogram branch of `layout_text` into `monogram.layout(letters, size, spacing, glyphs_for)`; `layout_text` calls it.
4. `layout_text` tags every returned object with `letter` and `line` (both 0-based; `line` is 0 for now). `_text_cache` keys must ignore nothing new: define `TEXT_SPEC_KEYS` in `lettering/__init__.py` with the old seven keys plus every new field in 5.1, and build the spec from it.
5. Restructure `layout/text.py` into the five-step pipeline in 5.2 with pass-through stubs (`extras.build` returns two empty lists; `_apply_letter_edits` returns its input; `stitchglyphs.records` raises "not built yet"). `_text_block` returns a list; adapt `render()` and `text_to_shapes`.
6. `design/types.ts`: the additions in 5.1.
7. `project.py` flags: `text_layout_2` (text has a line break, or any of `align`, `line_spacing`, `slant_deg`, `envelope`, `vertical`, `letter_edits`), `text_columns` (`style == "columns"`), `text_extras` (`shadow`, `outline`, `ornament`, or `monogram_style` other than classic), `font_stitch_glyphs` (`font.made_of == "stitches"`).
8. `methods/fonts.py` and `methods/names.py` with stubs; names in `rpc_methods.json`.
9. UI: split `TextPanel.tsx` into the three slot components (current controls move into whichever slot holds them today: font, size, spacing and shape stay in `SelectedText`; the Satin/Fill choice moves to `StyleControls`); stub dialogs; `cmd/lettering.ts` with the five reserved commands; move `NamesDialog` to its own file unchanged.
10. `python scripts/kb_commands.py`, `python scripts/check.py` (snapshots unchanged), commit "Phase 5: contracts".

## 7. Tracks

A, B, C and D run together. Worker rules are in `BUILDPLAN.md`.

---

### Track A: layout and single letters

**Owns:** `lettering/place.py`, `lettering/envelope.py`, `layout/text.py`, `components/text/LayoutControls.tsx`, `feat/letters.ts`, the text field in `TextPanel.tsx` (it becomes multi-line), new `engine/tests/test_lettering_layout.py`, snapshot suite `lettering_layout`.

#### P5-A1 Lines and alignment

`_clean_text` keeps line breaks (`\r\n` and `\r` become `\n`; tabs still become spaces). Each line is laid out as today; line `j`'s baseline is `j × line_spacing × size` below the first; lines are aligned left, center or right against the widest. On an arch the lines sit on concentric arcs (radius changed by the same step). On a circle or a drawn line only the first line is used, with a warning: "Text on a circle or a drawn line uses the first line only."

Panel: the text box becomes a three-row text area; Enter starts a new line; it commits as today (after a pause, on blur, or Ctrl+Enter). Below it, under More options: Align (three buttons), Line spacing (stepper 0.8 to 3, step 0.1), shown only when there is more than one line.

#### P5-A2 Slant

`slant_deg` −30 to 30 (stepper, step 1, under More options). Each glyph is sheared about its baseline before it is placed: `x' = x − y·tan(slant)` (y is down, so tops move right for a positive slant). For outline fonts the shear is applied to the glyph's shape before `_fill_object`, so the satin-look angle is chosen for the slanted letter. For stitch fonts the nodes are sheared and each fill's angle is carried through the same shear.

#### P5-A3 Envelopes and vertical

Envelopes apply to straight text (one line or several). On an arch, circle or drawn line the control is disabled with the reason as its tooltip. With the laid-out text's box `[x0, x1] × [y0, y1]`, `u = (x − x0)/(x1 − x0)`, `h = y1 − y0`, middle `ym`, amount `a`:

| Type | Map |
| --- | --- |
| bulge | `y' = ym + (y − ym)·(1 + 0.8·a·sin(πu))` |
| pinch | `y' = ym + (y − ym)·(1 − 0.6·a·sin(πu))` |
| pennant_right | `y' = ym + (y − ym)·(1 − 0.7·a·u)` |
| pennant_left | `y' = ym + (y − ym)·(1 − 0.7·a·(1 − u))` |
| wave | `y' = y + 0.35·a·h·sin(2πu)` |
| arch_top | `y' = y1 − (y1 − y)·(1 + 0.8·a·sin(πu))` |
| arch_bottom | `y' = y0 + (y − y0)·(1 + 0.8·a·sin(πu))` |

Outlines are densified first so no segment is longer than 1 mm (a straight stem must be able to bend). For satin-look letters the stitch angle is chosen again on the mapped shape.

Vertical: letters stacked top to bottom, each centered on the column, step `size × 1.15 + spacing`; several lines become columns left to right. Not combined with an arch, circle, drawn line or envelope.

Panel: Envelope (a select with "None" first, and an Amount slider when one is chosen) and "Stack the letters (vertical)", both under More options.

#### P5-A4 Adjust single letters

`text.letters` (`Alt+Shift+A`) on a selected text turns on single-letter mode: each letter shows a dot at its middle. Click a dot to select the letter (its outline lights up); drag to move it; arrow keys nudge it (1 mm, Shift 10 mm, Ctrl 0.1 mm, as for shapes). The panel then shows, for that letter: Size (50 to 200%), Turn (−180 to 180°), Thread, Stitch angle (satin-look and fill letters), and "Put this letter back". `text.resetLetters` (`Alt+Shift+Z`) clears every letter's changes. Esc leaves the mode (`holdEscape`).

Engine (`_apply_letter_edits`): for each letter with an edit, after placement and envelope: scale about the middle of its parts' box, turn about the same point (and turn its fill angles with `turn_with`), then move by `(dx_mm, dy_mm)`, all in the text's own unturned frame. `angle_deg` replaces the fill angle of that letter's parts. `thread` sets that letter's thread; `_blocks` then starts a new block wherever the thread changes, in letter order.

UI (`feat/letters.ts`): a canvas tool and an overlay through `canvas/hooks.ts` (their first real user). The drag is converted to the text's frame with the existing `text.letter_frame` call. In Order & colors a text's several runs show as separate colors; recoloring one sets `thread` on the letters in that run.

Editing the words keeps edits by letter number; when the text gets shorter, edits past the end are dropped.

#### Track A tests (`test_lettering_layout.py`, using the tiny font from `test_lettering.py`)

| Test | Asserts |
| --- | --- |
| `test_two_lines_are_one_line_spacing_apart` | baseline gap = `line_spacing × size` ± 0.05 |
| `test_alignment_left_center_right` | line starts, middles or ends line up within 0.05 mm |
| `test_line_break_survives_cleaning`, `test_crlf_is_one_break` | |
| `test_arch_lines_are_concentric` | |
| `test_circle_uses_first_line_with_a_warning` | |
| `test_slant_moves_tops_right_and_keeps_baseline` | bottom points unchanged; top moved by `cap·tan(slant)` ± 0.05 |
| `test_slanted_satin_look_angle_is_rechosen` | angle differs from the upright letter's for an I at 20° |
| `test_each_envelope_keeps_width_and_changes_height_as_specified` | parametrized over the seven; checks the box at u = 0, 0.5, 1 |
| `test_envelope_bends_a_straight_stem` | the I's side has points off the straight line |
| `test_vertical_stacks_letters` | same x middle; y step as specified |
| `test_letter_move_turn_size` | the letter's box moves, turns, scales; its neighbors do not |
| `test_letter_thread_makes_a_new_block_in_order` | three blocks for "IOI" with the O recolored |
| `test_letter_angle_override` | |
| `test_edits_past_the_end_are_dropped` | |
| `test_old_text_item_renders_exactly_as_before` | a 1.0.1 text dict: same records |
| `test_snapshots` | suite `lettering_layout`: `two_lines_left`, `slant_15`, `bulge`, `pennant_right`, `wave`, `vertical`, `letter_moved_recolored`, `done_when_1` (two lines, slant 12, bulge 0.5, letter 1 moved and recolored) |

UI: `components/text/LayoutControls.dom.test.tsx` (controls appear only when they apply; envelope disabled on an arch with its reason), `feat/letters.test.ts` (drag → `letter_edits`; reset clears).

---

### Track B: true satin letters (Hard)

**Owns:** `lettering/glyphs.py`, `lettering/satin.py`, `components/text/StyleControls.tsx`, new `engine/tests/test_lettering_satin.py`, snapshot suite `lettering_satin`.

#### P5-B1 True satin columns

**Behavior.** A third choice beside "Satin look" and "Fill": **True satin**. Each stroke of a letter is sewn as a satin column that follows the stroke, as hand-digitized fonts are, instead of rows across the whole letter. Outline fonts only (a stitch font already has its own columns). Parts that are not strokes (blobs wider than a satin can span, dots, slivers) stay satin-look fills, so a letter is never left half sewn.

**Algorithm** (`satin.columns(shape: Polygon, size_mm: float) -> list[object]`). LUDD already turns drawn lines in pictures into satin ribbons; this is the same idea on a glyph.

1. Rasterize the glyph polygon at 20 px per mm (holes included). Distance transform gives the half-width at every pixel.
2. Skeleton by thinning (`autotrace.thin`, then prune spurs shorter than the local width). Split it at junctions and ends into segments.
3. Classify each segment by its median width `w`: under `SATIN_MIN_WIDTH_MM` (0.8) → dropped into a fill part; over `SATIN_MAX_WIDTH_MM` (7) → fill part; otherwise a stroke.
4. For each stroke build two rails: center line points (smoothed over 5 samples, resampled every 0.5 mm) moved along the normal by the local half-width on each side, then snapped to the nearest point of the true outline when that point is within 0.4 mm (so edges follow the font, not the raster).
5. Junctions: the longest stroke through a junction runs straight through it; the others stop 0.4 mm inside it, so the later stroke covers the join.
6. A closed stroke (O, the bowl of a) is one closed column.
7. Order: strokes left to right by their start, each started at the end nearest where the last one finished. Moves between strokes of one letter are left to the existing hand-over rules.
8. What is left of the glyph after subtracting the columns' area (shrunk by 0.2 mm), if more than 0.5 mm², becomes satin-look fill parts sewn first.

Each column is an ordinary `satin` object (`rail_a`, `rail_b`) with `underlay: "auto"`, spacing 0.36, `comp_by_width` on, so fabric presets, splitting of long stitches and the dots all work, and "Break into shapes" gives editable columns.

**Panel.** Three buttons: Satin look, True satin, Fill. A hint under True satin: "Each stroke is its own satin column. New: check the preview, and switch to Satin look if a letter looks wrong."

#### P5-B2 Small letters

In `_fill_object` and the column builder: when the letter height is under `SMALL_TEXT_MM` (6), underlay is left out. The small-text warning becomes: "Letters N mm tall are hard to stitch clearly; underlay is left out so they stay thin. 6 mm or more is safer."

Thin strokes: when a glyph's median stroke width at this size is under 0.8 mm, warn once per text: "This font's strokes are only N mm wide at this size, so they sew as a single line. Use a bolder font or bigger letters."

#### Track B tests (`test_lettering_satin.py`; glyphs I, O, T, L, X built in the test font)

| Test | Asserts |
| --- | --- |
| `test_I_is_one_column_as_wide_as_its_stem` | one satin object; rail distance = stem width ± 0.2 mm |
| `test_O_is_one_closed_column` | first and last rail points meet within 0.3 mm |
| `test_T_is_two_strokes_and_the_join_is_covered` | two columns; union of their areas has no gap at the junction |
| `test_L_keeps_its_corner_full` | no uncovered triangle over 0.3 mm² at the corner |
| `test_X_crossing_is_covered_once_through` | one stroke runs through, the other meets it |
| `test_columns_cover_the_letter` | for each glyph: union of column and fill areas ≥ 97% of the glyph, and nothing more than 0.3 mm outside it |
| `test_wide_blob_stays_a_fill` | a 10 mm square glyph: no column |
| `test_columns_pass_the_invariants` | `assert_sane` on the generated stitches, longest stitch ≤ 7.15 mm |
| `test_break_into_shapes_gives_satin_objects` | |
| `test_stitch_font_ignores_columns` | style "columns" on a `.luddfont` behaves as "satin" |
| `test_small_letters_have_no_underlay`, `test_small_letter_warning_text` | 5 mm |
| `test_thin_stroke_warning` | |
| `test_snapshots` | suite `lettering_satin`: `I_12`, `O_12`, `T_12`, `IOT_columns`, `small_5mm` |

If, after two honest attempts, junction handling cannot meet the cover test on T or X, stop (two-strike rule): ship columns for letters without junctions, fall back to satin look per letter when a junction fails its check, and write the gap in the handoff. A letter is never left partly sewn.

---

### Track C: stitch font from letter files

**Owns:** `lettering/fontfile.py`, `lettering/fontbuild.py`, `lettering/stitchglyphs.py`, `methods/fonts.py`, `components/FontFromFilesDialog.tsx`, the `made_of` field where the font list is built (`lettering/fonts.py`, `list_fonts` only), new `engine/tests/test_fontbuild.py`.

#### P5-C1 Make a stitch font from letter files

**Behavior.** `text.fontFromFiles` (`Mod+Alt+F`), also in the font picker's menu. Steps in one dialog:

1. Choose a folder (or files) of single-letter designs in any format LUDD opens.
2. LUDD shows every file as a thumbnail with the character it guessed, in an editable box. Unassigned files are flagged; a character used twice is flagged.
3. Name the font. Letter gap (percent of the capital height, default 8). A preview line ("Hamburg 123" from whatever characters exist) with a baseline drawn through it; a letter can be nudged up or down.
4. Save. The font appears in the font list at once, marked as a stitched font.

A note at the bottom: "Only make fonts from designs you're allowed to use this way."

**Guessing the character** (`fontbuild.guess_char`), after removing the prefix and suffix every file shares:

| File name is | Character |
| --- | --- |
| one character | that character |
| `upper_a`, `uc_a`, `cap_a`, `a_upper`, `a_cap` (any separator, any case) | `A` |
| `lower_a`, `lc_a`, `small_a`, `a_lower`, `a_small` | `a` |
| `zero` … `nine` | `0` … `9` |
| `ampersand`, `and` · `period`, `dot` · `comma` · `exclam`, `exclamation` · `question` · `apostrophe` · `hyphen`, `dash` · `colon` · `semicolon` · `quote` · `slash` · `at` · `hash`, `number` · `heart` | `&` `.` `,` `!` `?` `'` `-` `:` `;` `"` `/` `@` `#` `♥` |
| all names are numbers 33 to 126 | that ASCII character |
| anything else | unassigned |

**Lining the letters up.** Letter files are usually centered on themselves, so the baseline is worked out: capital height = median height of the capitals and digits present; the baseline is each letter's own bottom, except: `g j p q y` hang (their top is put at the median top of `a c e m n o r s u v w x z`, or at 68% of capital height if none exist); `, ;` hang by 15% of capital height; `' " ^ *` sit at the top; `- + = ~` sit at the middle. `dy_mm` from the dialog overrides.

**The font file** (`.luddfont`, `"version": 2`): each glyph holds `advance_mm` and `stitches` (`[[x, y, k], …]` in mm from the glyph's origin on the baseline, `k` one of `"s"`, `"j"`, `"t"`), `blocks` (`[[start, end, color], …]`) and the font holds `threads`. Version 1 fonts (shapes per glyph) still load. A text using a stitched font carries `font.made_of = "stitches"`.

**Rendering** (`stitchglyphs.py`): a stitched glyph is a letter part of `kind: "stitches"` whose `geometry.nodes` are its stitches, so placement, slant, envelopes and single-letter edits move it like any part. `records(o)` returns them as stitches. Colors: a one-color font sews in the text's thread; a font with several colors sews color by color across the whole text, and `threads[k]` on the text item recolors color `k`.

**Limits, stated to the user:** stitched letters resize like stitch files (a warning past ±20% of the font's own height; if Phase 4's rebuild is present, call it instead of warning); "Break into shapes" answers "Letters from a stitched font have no outlines to edit."

#### P5-C2 BX fonts

Only if decision 1 says yes: one hour with a BX font the owner supplies, to see whether it is a plain container (zip, SQLite) holding ordinary stitch data. Write what was found in the handoff (five lines). Protected or obfuscated means stop. No code ships from this item in this phase.

#### Track C tests (`test_fontbuild.py`)

The test makes its own letter files: each of 26 capitals from the test font is rendered and exported as PES into a temp folder.

| Test | Asserts |
| --- | --- |
| `test_guess_char_table` | every row of the table above, plus prefix/suffix stripping (`Curly_A_4in.pes` → `A`) |
| `test_26_letter_files_become_a_font` | `build_from_files` returns 26 glyphs; the file loads; **done-when 2** |
| `test_ABC_sits_on_one_baseline` | bottoms of A, B, C within 0.2 mm |
| `test_descenders_hang` | a `g` built from a taller-bottomed file sits lower than `a` |
| `test_letter_gap_sets_the_advance` | |
| `test_duplicate_and_unassigned_are_reported_not_built` | |
| `test_stitched_text_moves_slants_and_bends_like_any_text` | with Track A's functions if present, else placement only |
| `test_two_color_font_sews_color_by_color` | |
| `test_version_1_fonts_still_load` | |
| `test_project_embeds_a_stitched_font_and_reopens` | save, delete the font file, reopen |
| `test_break_into_shapes_says_why_not` | |

UI: `components/FontFromFilesDialog.dom.test.tsx` (flags, editing a character, Save disabled while a duplicate exists).

---

### Track D: names, monograms, extras, placement

**Owns:** `lettering/monogram.py`, `lettering/ornaments.py`, `lettering/extras.py`, `names.py`, `methods/names.py`, `components/text/ExtrasControls.tsx`, `components/NamesDialog.tsx`, `components/PlacementDialog.tsx`, `feat/names.ts`, `design/placements.ts`, one motif unit (`leaf`) registered in `digitize/lines/`, new `engine/tests/test_lettering_extras.py`, `test_names.py`, snapshot suite `lettering_extras`.

#### P5-D1 Names from a list, and templates

The "One file per name" dialog (`text.names`) gains:

- **Load a list…**: a CSV or text file. `names.read_list` handles a byte-order mark, commas, semicolons or tabs, quoted fields, and up to 2,000 rows. A first row whose cells are all words like `name`, `line2`, `number`, `color`, `file` is a header; otherwise the first column is `name`.
- **Placeholders**: any text in the design can be marked "Filled from the list" and bound to a column (default `name`). Two placeholders give a name and a number (team shirts).
- **Shrink long names to fit**: a placeholder with `fit_width_mm` set is narrowed (size and spacing scaled together) when a name runs wider.
- **Preview**: ◀ ▶ step through the rows with each one shown in place on the design before anything is saved.
- A `color` column (a hex color or a thread code from the chosen chart) sets the placeholder's thread for that row; a `file` column names the output file.
- **Save this layout as a name template…** (`text.saveTemplate`, `Mod+Alt+P`): saves the project into the data folder's `templates` folder; the dialog lists saved templates under "Start from a template".

#### P5-D2 Monogram styles and frames

A monogram takes one, two or three letters (today exactly three). Styles: **Classic** (small, big, small: today's), **Block** (all the same size), **Stacked** (two small letters one above the other, then a big one). A frame can be added: circle, double circle, diamond, square, scallop circle (a scallop motif line round a circle) or laurel (two arcs with a leaf motif). The frame is sized to the monogram plus a margin (default 4 mm, 2 to 15) and sews after the letters in its own thread (the text's by default). Frames are ordinary line objects built in `ornaments.py`, so "Break into shapes" hands them over as editable lines.

#### P5-D3 Shadow and outline

- **Shadow**: the letters' outlines moved by `(dx_mm, dy_mm)` (default 0.8, 0.8; each −3 to 3), minus the letters themselves, sewn first in the shadow thread as satin-look fills. Only the part that shows is sewn, so nothing doubles up under the letters. Pieces under 0.5 mm² are dropped.
- **Outline**: a line round the letters at `gap_mm` (default 1.0, 0 to 5), as a satin `width_mm` wide (default 1.5, 1 to 4) or a triple run, sewn last in the outline thread. Built from the union of the letter outlines grown by the gap, with `shapeops`' outline-to-nodes code. It follows the text as it is edited (the Outline / offset tool makes a separate shape that does not).

Both are in `ExtrasControls`, under More options, each a tick box that reveals its settings.

#### P5-D4 Placement guides

`text.placement` (`Alt+Shift+G`): a dialog listing common items (bath towel, hand towel, pillowcase, sheet hem, adult left chest, child left chest, tote bag, napkin corner, cap front), each with where the design goes in inches and centimeters, a small diagram, and "Print a placement sheet" (the existing print template with the item's measurements and crosshair). The measurements are common practice written in our own words; each entry says "a starting point: check on your item". No stitches change.

#### Track D tests

| Test (file) | Asserts |
| --- | --- |
| `test_read_list_plain_names` (`test_names.py`) | one column, no header |
| `test_read_list_header_semicolons_quotes_bom` | |
| `test_read_list_stops_at_2000_and_says_so` | `skipped` |
| `test_monogram_one_two_three_letters` (`test_lettering_extras.py`) | each lays out; four letters still refused in plain words |
| `test_classic_monogram_is_unchanged` | same objects as before |
| `test_block_and_stacked_layouts` | sizes and positions as specified |
| `test_each_frame_surrounds_the_monogram` | parametrized over six: every letter point inside the frame, margin within 0.5 mm |
| `test_shadow_is_only_the_part_that_shows` | shadow ∩ letters area < 0.2 mm² |
| `test_shadow_sews_before_outline_after` | block order |
| `test_outline_follows_the_gap` | distance from letters = `gap_mm` ± 0.2 |
| `test_snapshots` | suite `lettering_extras`: `monogram_block`, `monogram_scallop_frame`, `shadow`, `outline_satin` |
| `placeholders are filled per row and two columns fill two texts` (`feat/names.test.ts`) | **done-when 4** |
| `a long name shrinks to fit_width_mm` | |
| `a color column sets the thread` | |
| `placement dialog lists items with both units` (`components/PlacementDialog.dom.test.tsx`) | |

## 8. Integration (session lead)

1. Merge A, then C, then D, then B (B last: it is the likeliest to need a second look). `python scripts/check.py` after each.
2. After all four: add one test, `test_done_when_1` already covers A; add `test_extras_and_columns_together` (a True satin text with a shadow, an outline and a moved letter renders and passes `assert_sane`).
3. Confirm the five old lettering snapshots are unchanged, except any whose letters are under 6 mm (none are: they use 12 mm).
4. Docs (section 9), `python scripts/kb_commands.py`, `python scripts/check.py --all`.

## 9. Docs payload

**Knowledge base:**

| ID | Entry |
| --- | --- |
| F-1410 | Lines and alignment |
| F-1411 | Slant |
| F-1412 | Envelopes and vertical text |
| F-1413 | Adjust single letters |
| F-1414 | True satin letters |
| F-1415 | Make a stitch font from letter files |
| F-1416 | Names from a list; templates |
| F-1417 | Monogram styles and frames |
| F-1418 | Shadow and outline |
| F-1419 | Placement guides |
| F-1420 | Small letters |
| F-1404, F-1406, F-1408 | Monogram, One file per name, Stitch fonts: updated |
| L-003 | Multi-line text: now YES (keep the ID, mark lifted) |
| L-005 | Per-letter stitch angle: now YES |
| L-014 | True satin from TrueType: YES with limits (junction fallbacks) |
| L-035 | A single letter's own thread is not part of Color sets |
| L-036 | BX fonts: NO; use the seller's letter files with F-1415 |
| L-037 | Several lines on a circle or drawn line: first line only |
| L-038 | Stitched fonts: resize ±20%, cannot be broken into shapes |
| T-027 | "A letter looks wrong in True satin" → Satin look, or Break into shapes |
| T-028 | "My letter files came in with the wrong letters" → fix the character boxes |
| T-029 | "Letters don't sit on one line in my new font" → nudge in the dialog |
| T-030 | "Long names run off the design" → Shrink long names to fit |

Index rows for each new "Can LUDD…" question; the "multi-line text" and "change a letter's stitch angle" rows flip to YES. History row; *Last updated*.

**USER-MANUAL** section 7 (Lettering) gains a part for each item. **helpdocs.py** likewise, short.

**Stitch-out rows:**

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 5 | **Two lines, slanted, in an envelope** | "Happy / Birthday", Arial 12 mm, slant 12°, Bulge | Even letters; no puckering where the envelope stretches them |
| Phase 5 | **True satin against satin look** | "Emma" at 10 mm and 20 mm, both ways, side by side | True satin is smoother along strokes; joins (m, a) have no gap or lump |
| Phase 5 | **Small letters without underlay** | A name at 5 mm | Thinner and more legible than with underlay; nothing unravels |
| Phase 5 | **Stitched font** | A name typed in a font made from bought letter files | Letters on one line, evenly spaced; sews like the originals |
| Phase 5 | **One letter moved and recolored** | A name with one letter raised, turned and in a second color | The color change is clean; no long thread between letters |
| Phase 5 | **Monogram in a scallop frame** | Three letters, Classic, scallop circle | Frame round and evenly scalloped; letters centered |
| Phase 5 | **Shadow and outline** | "WOW" 25 mm with a 0.8 mm shadow; the same with a 1.5 mm satin outline | Shadow shows only at the edge, no lump under letters; outline evenly spaced round the word |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Step 0's split moves a stitch | a lettering snapshot changes | Undo and move in smaller steps; never re-record in Step 0 |
| True satin fails on real fonts with serifs and thin joins | cover test fails beyond the five test glyphs | Per-letter fallback to satin look when its own cover check fails (built in); say how many letters fell back in a warning |
| Letter files from sellers have no usable naming | many unassigned in the grid | The grid is the fallback: every box is editable. Log common naming patterns met on the owner's files for a later table update |
| Envelope plus satin-look angle looks wrong on extreme amounts | visual only | Amount is capped at 1; the stitch-out row covers it |
| Single-letter thread runs confuse Order & colors | recolor hits the wrong letters | The `run` number in item info is the single source; `feat/letters.test.ts` covers recolor by run |
| Four tracks is too much for one session | context runs short | Run A and C first (they meet the done-when), then B and D in a second session; say so in `HANDOFF.md` |

## 11. Handoff

Write: whether decision 1's look happened and what it found; how many letters of the test fonts fell back from True satin; naming patterns that the guess table missed; whether Phase 4's rebuild is wired into stitched fonts or only the warning.

## 12. Build notes (2026-11-25)

- Step 0 was two commits (the split, with every function body proven unchanged, then the contracts). Extras are built from the letters after single-letter changes (5.2 lists them first, which would leave a moved letter's shadow behind). From Step 0, color runs split wherever the thread changes, a stitched font sews color by color, and each run tells the UI which letters and color slots it holds. The panel's "Advanced" fold is "More options". A fifth project flag, `motif_leaf` (every new motif gets one).
- A: a slanted satin-look letter takes its upright angle, leaned with it (on the sheared shape alone a leaning I keeps flat rows, so the re-chosen-angle test could not pass); envelopes choose on the bent shape. A curve drops stacking and the envelope, stacking drops the envelope (each says so); monograms ignore stacking. Align also works on arches. Single-letter changes apply after the cached layout (the cache key leaves out `letter_edits`, which `layout_text` never reads).
- B: raster 20 px/mm halved until at most 480 px; bends over 50 degrees count as junctions; leftover = letter minus columns, shrunk then grown by 0.2 mm (read literally, every column would gain strips along its sides); stroke width comes from the biggest part's area and outline length. Fall-backs: test fonts 0; Arial A-Z, a-z, 0-9: 0 of 62 at 12 mm, 1 at 25 mm, 27 at 60 mm (mostly sides crossing near 7 mm).
- C: Phase 4's rebuild is used past 20% (on Arial letters at 250%, coverage 78-84% stretched, 93-99% rebuilt), with a plain resize if it fails. One color per file makes a one-color font. Spec flaw built as written: a dotted j sits too low (T-029).
- D: four monogram letters are now refused (before, the first three were sewn silently, so "still refused" was not true of the old code); the old two-letters-refused test now checks four. Frames only on monograms; the outline skips holes; stitched fonts get frames but no shadow or outline. Fill choices are ticked in the names window; an empty cell leaves that lettering out of that file. Two more RPC methods, `names.list_templates` and `names.save_template`.
- Integration: a default 0.8 mm shadow hit an exact tie in the satin-angle choice (moving an I's shadow flipped it between 0 and 30 degrees, so Macs could differ): widths are rounded first. True satin columns take the fabric's underlay amount. Stitched letters resized with the handles say they aren't rebuilt, show no start/end dots and can't be broken into shapes (the panel says why). Two-line texts are named on one line; "Put back the original colors" clears single letters' colors; one-letter monograms no longer warn early; Placement guides is also in the toolbar's ⋯ menu; the old names export runs the new code.
- BX fonts (decision 1): not looked into.
