# QA phase 4: autotrace group

Areas: `### autotrace` (Medium and Low), plus the auto-trace / AI items in `tests` (Low) and the
two items handed over by the ui agent. Detail and repros: `_salvage/area-autotrace.md`.

## 1. Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | autotrace | Busy pictures take 20-90 s, one click on line art 3-16 s, no progress/cancel, "a few seconds" label | Fixed (speed); progress/cancel skipped: needs an RPC cancel channel, too big for this phase | autotrace.py: `thin` and `_one_pixel` vectorised with neighbour-code lookup tables; skeleton of a clicked line cached per picture (`_line_skeleton`); `_simple_region` labels joined colours once per (colour, spread); per-region work cropped to the region (`_to_line_middle`, patch loop); ToolRail.tsx busy label now "a few seconds; up to a minute for a busy picture". Measured: line-art click 4.9 s -> 1.1 s first / 0.02 s after; line-art whole picture 22.6 s -> 4.4 s; 15x15 mosaic 28 s -> 7 s; 30x30 mosaic 94 s -> 20 s; 40x40 grid 6.5 s -> 5.1 s | test_autotrace.py `test_busy_line_art_is_quick_and_a_line_is_thinned_once`, `test_one_pixel_keeps_lines_connected_and_one_pixel_wide` |
| Medium | autotrace | "Fewer jumps" layout render time grows steeply with object count; Add all fails past 60 s | Already fixed (phase 1 layout.py rewrite). Re-measured with the 3,199-object grid: 2.4 s with fewer jumps on (was 97 s), 1.3 s off | layout.py (phase 1) | - |
| Medium | autotrace | Click inside a solid black / very dark shape offers nothing | Fixed | autotrace.py `region`: a click in a solid dark area adds a "Fill, this dark area" guess (shared `_solid_dark`) | `test_click_inside_a_solid_black_shape_offers_a_fill` |
| Medium | autotrace | 16-bit greyscale PNGs read as black and white in Auto-trace and Trace Assist | Fixed | trace.py `flatten` / `open_picture` (shared by both): I;16/I/F modes scaled to 8 bit | test_trace.py `test_16_bit_greyscale_keeps_its_mid_tones`; test_autotrace.py `test_16_bit_greyscale_traces_like_8_bit` |
| Medium | autotrace | AI embedding cache keyed by path and size: an edited picture gets old AI guesses | Fixed | ai/segment.py: the embedding is kept on the analysed picture (`pic._ai_embedding`), which autotrace re-analyses when the file changes; a model reload/remove invalidates it | `test_ai_reading_of_a_picture_goes_with_the_picture` |
| Medium | autotrace | Whole picture samples a colour per shape: JPEG logos get many near-identical threads | Fixed | autotrace.py `digitize_all`: all dark lines and solid dark fills use one ink colour; `_one_thread_per_color` merges colours within dE 10 into the bigger one. JPEG q50 logo: 15 colours -> 4 | `test_whole_picture_gives_one_thread_per_color_even_from_a_jpeg` (PNG, q90, q50) |
| Medium | autotrace | "Leave out the background" does nothing on dark neutral backgrounds | Fixed | autotrace.py `_background_groups` (the colour holding most of the 1-px picture edge, light or dark) applied to colour areas and to solid dark areas; fills don't grow into a dropped dark background | `test_leave_out_the_background_works_on_dark_backgrounds_too` (black, charcoal, navy, blue-grey, white) |
| Medium | autotrace | "Leave out the background" drops real shapes that touch the edge (pale, or > 45 %) | Fixed | same: only the edge colour is background, not "touches the edge and is light or big"; the paper's region only takes paper colours | `test_leave_out_the_background_keeps_shapes_that_touch_the_edge` |
| Medium | autotrace | Bold strokes 3-4.4 mm come out as a patchwork of fills and satins | Fixed | autotrace.py `_solid_dark`: a connected dark shape whose stroke width (median along its middle) is >= 2.8 mm is one fill; small wide spots where thinner lines meet no longer become fills | `test_bold_strokes_are_one_fill_each_not_a_patchwork` (2.0, 2.5, 3.0, 3.6 mm) |
| Medium | autotrace | Paper inside a shape (letter counters, rings) sewn as a white fill | Fixed | `digitize_all`: any area in the background colour is left out, wherever it is | `test_paper_inside_a_shape_is_not_sewn` |
| Medium | autotrace | Soft / anti-aliased edges become hairline ring fills; JPEG fragments 1 px outlines | Fixed (fills); improved (JPEG lines: q50 triangle outline now 3 runs, was 1 + 8 specks) | `digitize_all`: areas thinner than 1 mm (2 x area / outline length) are not sewn; thin lines are bridged over 1-px breaks before thinning; specks under 2 mm dropped | `test_soft_edges_dont_become_hairline_fills`, JPEG case in the colour test (<= 4 runs) |
| Medium | autotrace | Whole-picture ribbons stop half a line width short at free ends | Fixed | `_reach_tips` shared by single-click and whole-picture ribbons; only free line ends (not junctions) are extended; speck test measured after extending | `test_whole_picture_ribbons_reach_the_ends_of_the_line` |
| Low | autotrace | Very large pictures: 2.9 GB peak at 144 MP, raw "decompression bomb" error over 179 MP | Fixed | trace.py `open_picture`: JPEG decoded small (`draft`), others reduced (`Image.reduce`) before the RGBA composite; DecompressionBombError / ValueError give a plain TraceError ("too big to trace ... save a smaller copy") | test_trace.py `test_big_pictures_are_made_small_early_and_turned_like_on_screen`, `test_a_too_big_picture_is_a_plain_error`; test_autotrace.py `test_a_too_big_picture_is_a_plain_trace_error` |
| Low | autotrace | Unloadable AI model makes every click fail, raw ONNX error | Fixed | autotrace.py `region`: AI failure is caught, the usual guesses come back with a plain `ai_error`; autoTrace.ts shows it as a notice | `test_ai_that_cant_run_falls_back_to_the_usual_guesses`; autoTrace.test.ts "says when the AI couldn't run" |
| Low | autotrace | AI model download: no size/hash check, unpinned URLs, short bodies accepted, IncompleteRead escapes | Partly fixed: short bodies (Content-Length mismatch) and broken-off chunked bodies are errors, nothing left behind, plain messages (offline / server answered N / cut off), ONNX Runtime checked before downloading. Pinned revision + SHA-256: skipped, needs the owner (the upstream commit and hashes can't be looked up without the network) | ai/segment.py `_fetch`, `download` | `test_model_download_that_breaks_off_is_a_plain_error_and_leaves_nothing`, `test_model_download_offline_says_check_the_connection`, `test_model_download_needs_onnx_runtime_first` |
| Low | autotrace | Engine traces the live original file, not the copy the canvas shows | Handed over: project (kept.py) | - | - |
| Low | autotrace | Whole-picture preview goes stale (spacing/spread, picture moves) and an older answer can overwrite a newer run | Fixed | features.ts: request counter in `digitizeWholePicture`; the preview re-reads when point spacing, spread or the picture's place change; ToolRail.tsx: the whole-picture bar has its own Points every / Spread controls (replacing the hint about Auto-trace's bar, which is hidden then) | autoTrace.test.ts "shows only the newest run's answer", "reads the picture again when ..." |
| Low | autotrace | A picture with no light pixel crashes a click with NaN | Fixed | autotrace.py `analyse` caps the line-width map at the picture size; ribbon width capped at 10 mm before the tip extension | `test_a_picture_with_no_light_pixel_doesnt_crash` |
| Low | autotrace | Analysis time grows with px per mm (click 0.3 s -> 5.7 s) | Fixed | `_to_line_middle` uses a distance map on a crop instead of a huge dilation kernel. Logo at 100/40/20 mm: click 0.08 s each, whole picture 0.7-1.0 s (was 0.33/1.6/5.7 s and 1.0/1.5/4.4 s) | covered by the busy-picture test; timings in this table |
| Low | tests | Test collection reads (and may migrate) the real user data folder; AI-model test depends on the machine | Fixed | test_autotrace.py: the real-model test runs only when `LUDD_TEST_AI_MODEL_DIR` points at the model folder; nothing looks at the user data folder at import | (itself) |
| Low | tests | Wall-clock assertions can flake | Fixed | test_autotrace.py: limits loosened to 2 s per click and 20 s for the whole picture (measured 0.1 s and 1 s), still catching big slow-downs | (itself) |
| Low | live-state (from ui) | acceptGuess reports "Added" before the commit is known | Fixed | autoTrace.ts `acceptGuess`: waits for `addTraced` (true/false); on failure the guess stays (busy cleared) and no "Added"; the guess is marked busy while adding so a second Enter can't add it twice | autoTrace.test.ts "keeps the guess ... when the add fails", "adds, then lets go" |
| Low | live-esc (from ui) | Esc in an AI-settings box saves the half-typed value | Fixed | AISettings.tsx `Field`: Esc brings the old value back, saves nothing and keeps the dialog open; a held thing goes first (`heldCount()`) as in InfoPanel | none (component; vitest has no DOM) |

| Low | security (from engine-io) | Tracing works on huge pictures at full size (image.load now refuses > 120 MP, but up to that tracing allocated full-size copies) | Fixed | trace.py `open_picture` / `flatten`: reduced while decoding (JPEG `draft`) or with `Image.reduce` before any RGBA copy | test_trace.py `test_big_pictures_are_made_small_early_and_turned_like_on_screen` |
| Low | fuzz-rpc (from engine-io) | AI-trace embedding cache keyed on size only | Fixed (same as the Medium autotrace row above) | ai/segment.py | `test_ai_reading_of_a_picture_goes_with_the_picture` |
| Low | security (from engine-io) | AI model download not pinned or hash-checked | Skipped: pinning needs the upstream commit id and SHA-256 of both files, which can't be looked up without the network (a local copy's hash is not proof of the upstream file). Size check against Content-Length and broken-download handling are in (see the Low autotrace row) | - | - |

Counts: 22 fixed (2 of them partly), 1 already fixed, 1 handed over; skipped parts: progress/cancel for whole picture, pinned model revision + hash.

## 2. Changelog lines
- Auto-trace is much faster on busy pictures: clicking a line in detailed line art takes about a second the first time and is instant after that; whole-picture digitizing of busy pictures is 3 to 5 times faster, and small placements (badges, patches) no longer slow it down.
- Clicking inside a solid black or very dark shape with Auto-trace now offers "Fill, this dark area".
- Whole picture: a JPEG logo now gets one thread per real colour (all dark outlines share one black), instead of a slightly different shade per piece.
- Whole picture: "Leave out the background" now works on dark backgrounds too, keeps coloured shapes that touch the picture's edge, and no longer sews the paper inside letters and rings.
- Whole picture: bold lettering becomes one fill per letter instead of a patchwork; soft edges and glows no longer give thin ring fills; satin outlines now reach the ends of the lines.
- Whole picture: the preview follows changes to point spacing, spread and the picture's place, and has its own Points every and Spread controls.
- 16-bit greyscale PNGs now trace correctly (mid-tones were lost) in Auto-trace and Trace Assist.
- Very large pictures use far less memory when traced; a picture too big to trace says so in plain words.
- If the AI tracing model can't run, Auto-trace says so and still shows its usual guesses; a broken-off model download now says what went wrong and leaves nothing half-done behind.
- Auto-trace only says "Added" when the shape was really added; otherwise the guess stays on screen.
- Esc in an AI-settings box puts back what was there before typing.

## 3. Manual changes needed (docs/USER-MANUAL.md)
- Auto-trace steps (around line 219): add that clicking inside a solid dark shape offers "Fill, this dark area".
- Whole picture (around lines 260-262): "**Spread** and **Points every** (from Auto-trace's bar) apply too" -> the whole-picture bar has its own **Points every** and **Spread** controls ([ ] and Alt+[ ] while Auto-trace is the tool), and the preview is read again when they change or when the picture is moved.
- Whole picture: say what "Leave out the background" leaves out: the colour around the picture's edge, light or dark, wherever it shows (also inside letters and rings); shapes touching the edge are kept.
- Whole picture: dark lines and solid dark areas share one thread colour; nearly equal colours become one thread; bold dark lettering becomes one fill per letter.
- AI tracing: if the model can't run, Auto-trace says so and shows its usual guesses (removing and downloading it again in Settings may help).
- Optional: busy pictures can take up to a minute in Whole picture.

## 4. Stitch output changed
Whole-picture digitize (Alt+A) produces different shapes and colours: shared ink colour and merged
near-identical colours; dark backgrounds, edge-colour areas inside shapes and sub-1 mm areas
left out; bold strokes (median width >= 2.8 mm) as one fill; small wide spots on thinner lines no
longer split into fills; ribbons extended to free line ends; thin JPEG lines bridged. Single-click
guesses: a new "dark area" fill guess; ribbon tips unchanged except the width cap. No stitch
generation code changed (no snapshot re-recorded).
Test design for a stitch-out: a logo saved as JPEG (quality 50-90) with black outlines, a bold
word (stems about 3-4 mm at the chosen size) and a red ring, digitized with Whole picture and
"Leave out the background" on; check: one black thread, no white fills in the counters or the
ring's middle, satin outline ends reach the line ends, letters sew as one fill each.

## 5. Handed over
- **project (engine/threadline_engine/kept.py)**: `kept.readable()` returns the live original whenever it exists, so after the picture file is edited elsewhere, tracing (and saving) use the new file while the canvas shows the old one. Fix: prefer the kept copy of the bytes that were added (keyed by content hash), or invalidate/reload the picture when the file changes.
- **ai/advisor.py owner**: `_picture_under` does `ImageOps.exif_transpose(src).convert("RGB")`, which clips 16-bit greyscale PNGs to white and decodes huge pictures at full size. Use `trace.open_picture(Path(kept.readable(path)), max_side)` (returns 8-bit RGB on white, EXIF-turned, reduced early, plain TraceError on unreadable / too big).
- **Owner decision**: pin the MobileSAM download to a Hugging Face revision and add per-file SHA-256 and size in `ai/segment.py` FILES (needs the upstream commit id and hashes, which need the network). `_fetch` is the place to verify while streaming.

## Notes
- Tests: test_autotrace.py 45 passed, 1 skipped (real AI model, opt-in); test_trace.py 11 passed; autoTrace.test.ts 7 passed; full vitest 144/144; typecheck clean.
- Full engine suite: 460 passed, 5 failed, all `test_digitize.py::test_snapshot[fill_*]` (fill_contour, fill_cross, fill_donut, fill_square_45, fill_stipple): fill stitch output, another agent's area (work in progress); nothing in my changes touches stitch generation.
- Not checked in the running app (the preview is shared; the brief says not to start one). The WholePictureBar / AISettings changes are typechecked only.
