# QA phase 4: leftovers group

Items handed over by the first wave (the "Area" column names the notes file they came from).
Engine tests: `engine/tests/test_qa_leftovers.py`. UI tests: `apps/desktop/src/leftovers.qa.test.ts`.

## 1. Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Low | autotrace.md | `kept.readable()` returns the live original: a picture edited elsewhere after it was added is traced and saved instead of what the canvas shows | Fixed: `readable(path, as_added=True)` prefers the private copy of the bytes that were added; tracing (trace.py, autotrace.py), the Advisor and saving (`project._pack`) use it; adding the picture again (`load_image`) still reads the file afresh. Stitch files keep following the file on disk (canvas and export both come from the engine, so they agree) | kept.py; small edits in trace.py `prepare`, autotrace.py `prepare`, project.py `_read`/`_pack` | `test_an_edited_picture_traces_and_saves_as_shown` |
| Low | autotrace.md | Advisor `_picture_under` clips 16-bit greyscale to white, decodes huge pictures at full size | Fixed: uses `trace.open_picture` (8-bit RGB on white, EXIF-turned, reduced to 2000 px early); an unreadable picture is skipped (TraceError) | ai/advisor.py | `test_advisor_reads_a_16_bit_grey_picture`, `test_advisor_skips_a_picture_it_cannot_read` |
| Low | engine-io.md | `font-index.json` holding a list breaks the font list | Fixed (not done by the lettering agent): read with `storage.read_json`, anything not a dict (or not JSON / not UTF-8) is rebuilt | lettering.py `list_fonts` | `test_font_index_holding_a_list_is_rebuilt` |
| Low | engine-io.md | `export_stitch_font` with a destination keeps any extension (the font list then never finds it) | Fixed: a destination that isn't `.luddfont`/`.tlfont` gets `.luddfont` added | lettering.py `export_stitch_font` | `test_stitch_font_saved_with_its_own_extension` |
| Low | engine-io.md | `export_stitch_font({})` is a KeyError (reported as an engine bug) | Fixed: "Pick a font to convert first" | lettering.py `export_stitch_font` | `test_stitch_font_without_a_font_is_a_plain_message` |
| Low | engine-io.md | Print template: thread colour not escaped | Fixed: only a plain `#hex` colour goes into the page (`safeColor`, else grey), in the template paths and the thread list swatch | print.ts | leftovers.qa.test.ts "Print: thread colours" |
| Medium | stitches.md | Knife pieces lose colour change (threads), stops/trims (ops), pin and group | Fixed: each piece copies `threads`, `ops` (stops/trims carry their record count, so the engine drops ones that no longer fit), `locked` and `group` | features.ts `finishKnife`, `insertObjects` | leftovers.qa.test.ts "Knife" |
| Medium | stitches.md | Knife/merge/offset report success when the commit failed | Already fixed (ui agent, phase 4): messages only after `insertObjects`/`commit` succeed. Test added | features.ts | leftovers.qa.test.ts "says nothing about pieces..." |
| Low | stitches.md | Empty negative offset says "try a bigger one" | Fixed: by sign; an inset that leaves nothing says "try a smaller inset (closer to 0)" | features.ts `addOffset` | leftovers.qa.test.ts "Outline / offset" |
| Low | stitches.md | Knife disarmed after a harmless mistake (double-click, cut that misses) | Fixed: after an engine error the knife is armed again (with its Esc booking) if the shape is still there | features.ts `finishKnife`, `armKnife` | leftovers.qa.test.ts "stays ready after a cut that missed" |
| Low | stitches.md | Merge keeps the earliest-in-sewing-order item's settings, not the first selected | Fixed: the first-selected item (the primary selection) keeps its settings, thread and sewing place; the message says so | features.ts `mergeSelected` | leftovers.qa.test.ts "Merge" |
| Low | stitches.md | Offset limit text in mm when units are inches | Skipped: FeatureDialogs offset field not in my list for this wave; small, can go with the docs pass or later | - | - |
| Low | stitches.md | Fabric spacing: one clamp for all kinds; 0 or negative turned into 0.2 | Fixed (layout agent had not done it): clamp per kind was already in (satin 0.15-3, fill 0.2-5); 0, negative or NaN now left alone so the stitch type refuses it in plain words | fabrics.py `apply` | `test_fabric_spacing_kept_within_each_stitch_type`, `test_fabric_leaves_an_impossible_spacing_for_the_stitch_type_to_refuse` |
| Low | stitches.md | Fill Length stepper allows 8 mm (loose stitches) | Fixed: max 7 (2.5 for stipple, which caps it there) | InfoPanel.tsx | none (component) |
| Low | stitches.md | Applique shows Lock stitches boxes it ignores | Fixed: hidden for applique | InfoPanel.tsx | none (component) |
| Low | stitches.md | Settings that do nothing for contour/stipple/cross | Fixed: Angle, Random, Edge pad and the Cross-hatch underlay button hidden for all three; Density and Spacing hidden for stipple and cross (kept for contour, whose hint says to use Light); Length hidden for cross; the folded heading names the pattern ("Stipple", "Contour · Light") | InfoPanel.tsx `OPEN_PATTERNS`, `objectSummary` | none (component) |
| Low | stitches.md | Ribbon widths 0.5-0.99 sew at 1.0 | Fixed: Width stepper minimum 1 mm | InfoPanel.tsx | none (component) |
| Medium | layout.md | Knockdown thread can't be set | Fixed: the knockdown block in the Threads list has a ✎ button opening the thread picker; writes `layout.knockdown.thread` (the engine already used it). `Layout.knockdown.thread` added to types.ts | InfoPanel.tsx `ThreadsSection`, design/types.ts | none (component) |
| Low | layout.md | Basting and knockdown look alike in the thread list | Fixed: shown as "Basting box: Holds the fabric; remove it afterwards" and "Knockdown: Use a thread that matches the fabric" (`addedStitching`) | InfoPanel.tsx | leftovers.qa.test.ts "Thread list" |
| Low | stitches.md | Knife clicks don't snap | Fixed: knife clicks and the knife's preview line go through `snapped()` (shape points, guides, grid) | StitchCanvas.tsx | none (canvas) |
| Medium | platform.md | Zoom/pan slow on a 40,000-stitch design | Partly fixed: wheel zoom redraws the zoom-dependent layers once per frame (was once per wheel event); needle points (P) drawn only around the screen and one per ~2 px; points and stitch-edit points brought in after a pan (stitch-edit points vanished off the original screen before). The stitches themselves were already cached and scaled, not redrawn. Not measured in the live app (no app runs in this phase) | StitchCanvas.tsx `drawPoints`, `afterPan`, `onWheel` | none (canvas) |
| Low | stitches.md | Design browser search only filters the newest 600 | Fixed: in a folder with more, typing a name searches the whole folder again (`library.scan` with `query`, 400 ms after typing stops); the hint says when even the matches are capped | FeatureDialogs.tsx `BrowseDialog` | none (component) |
| Low | platform.md, engine-io.md | No way to read the bundled THIRD-PARTY-NOTICES.txt | Fixed: Settings > About: "Licences…" opens a dialog with the file's text, read by a new Tauri command `third_party_notices` (resource dir, that one file only; no new crate or permission). The browser preview says "The licences are listed in the installed app." `cargo check --offline` clean | src-tauri/src/lib.rs, SettingsDialog.tsx, styles.css | none (component/Rust) |
| Low | layout.md | `.shrink-fit` ("Make it N% smaller") has no style | Fixed: a callout using `--info-bg` / `--accent-edge` | styles.css | - |
| Low | lettering.md | Help says the Text tool is T | Fixed: Shift+T; the Text paragraph now names Put the text on the line (Ctrl+Alt+L) and One file per name (Ctrl+Alt+N); Pin in place names Ctrl+L. Every other shortcut in the help checked against COMMANDS: all match | ai/helpdocs.py | `test_help_names_the_text_tool_and_text_commands_with_their_keys` |

Counts: 23 fixed (1 partly), 1 already fixed (test added), 1 skipped.

## 2. Changelog lines
- A picture changed in another program after you added it no longer gets traced or saved in place of the one you see.
- The Stitch Advisor reads 16-bit greyscale and very large pictures properly.
- A damaged font list file no longer stops fonts from showing; "Save as stitch font" always saves a .luddfont.
- Cutting with the knife keeps each piece's colour, stops and trims, pin and group. A cut that misses leaves the knife ready to try again. Knife clicks snap to points, guides and the grid.
- Merge keeps the settings of the shape you selected first.
- An inset outline that leaves nothing says to come closer to 0.
- Shape panel: only the settings each fill pattern uses are shown; fill stitch length goes up to 7 mm; satin ribbons are at least 1 mm wide; applique no longer shows lock-stitch boxes it doesn't use.
- Knockdown stitches: pick their thread from the Threads list; the basting box and knockdown are labelled there.
- Finding a design by name searches the whole folder, not just the newest 600.
- Settings > About shows the licences of the software LUDD includes.
- Zooming a big design is smoother; needle points stay visible after moving around.
- Printed templates can't be broken by an odd thread colour value.

## 3. Manual changes needed (docs/USER-MANUAL.md)
- "The knife, and merging": Merge keeps "the settings of the one you selected first" (now says "the first one's settings"). Knife pieces also keep colour changes, stops/trims, pin and group; a cut that misses keeps the knife ready; clicks snap.
- Stitch settings table: Lock stitches don't apply to Applique (column note); Length for fills goes to 7 mm. Fill patterns: contour, stipple and cross-stitch have no Angle, Random, Edge pad or Cross-hatch underlay; stipple and cross-stitch have no Density.
- Knockdown stitches: "Set its thread to match the fabric": say how (✎ next to Knockdown in the Threads list).
- Settings: an About section with Licences….
- Outline / offset: negative distances (insets) exist; if nothing is left, use a smaller inset.

## 4. Stitch output changed
- Fabric presets: a fill or satin with spacing 0 or negative is no longer sewn at the densest spacing; it now gets the plain "spacing must be between..." error. No change for valid spacings.
- Knife: pieces keep the original's thread overrides and stops/trims (previously reverted to the shape's own thread, stops lost). Test design: a fill recoloured in the Threads list, with a stop inserted, cut in two.
- Nothing else changes sewn output.

## 5. Handed over
- **FeatureDialogs offset field / features.ts**: the offset limit message ("between -10 and 30 mm") in the current unit (stitches.md item, not in this wave's list).
- **ExportDialog.tsx owner**: `.shrink-fit` is a `<p>` holding a `<label>` with `SplitMap`; if SplitMap renders a block element this is invalid nesting (a `<div className="shrink-fit">` would be safer). The new style works with either.

## Notes
- Files outside my list touched with small targeted edits: trace.py, autotrace.py, project.py (one keyword each, for item 1), design/types.ts (`knockdown.thread`).
- Test results: engine `CI=1 uv run pytest`: 581 passed, 1 skipped. UI: `pnpm typecheck` clean; `vitest run`: 29 files, 155 tests passed. `cargo check --offline`: clean.
