# QA phase 4: lettering

Files changed: `engine/threadline_engine/lettering.py`, `engine/tests/test_lettering.py` (16 new tests),
`apps/desktop/src/components/TextPanel.tsx`, `apps/desktop/src/features.ts` (`textOnLine`, new
`textOnLineItem`, `nameFileStem`, `exportNames` note), new `apps/desktop/src/features.lettering.test.ts`.
Small targeted edits outside my files: `engine/threadline_engine/layout.py` `_text_block` (3 lines: font
file in the cache key, stitch angle turned with the text, letters stitched at the origin and then moved),
`apps/desktop/src/actions.ts` (`saveStitchFont`; `text.names` enabled only when lettering is selected).

## 1. Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | lettering | Missing characters silently become '?' or vanish; nothing drawable gives an empty design | Fixed: left out with a warning naming them; nothing drawable is refused with a message; symbol fonts listed last | lettering.py `_Missing`, `_outline_glyphs`, `layout_text.done`, `list_fonts` (`symbol`, index v3) | test_qa_missing_characters_are_named_and_nothing_drawable_is_refused |
| Medium | lettering | Save as stitch font: 69 characters, no case/accent fallback, Satin/Fill does nothing, saved where LUDD doesn't look | Fixed: all Latin letters with accents and punctuation the font has; kerning kept (`kern` map); other case, then the plain letter, with a warning; Satin/Fill hidden for stitch fonts (a hint instead); no save dialog: saved straight into LUDD's fonts folder (never over an existing file), the message gives the folder; refused for a stitch font | lettering.py `export_stitch_font`, `_stitch_font_glyphs`, `_near_letter`; actions.ts `saveStitchFont`; TextPanel.tsx | test_qa_stitch_font_case_and_accent_fallback, test_qa_save_as_stitch_font_goes_where_ludd_looks |
| Medium | lettering | Damaged stitch fonts give raw Python errors; a wrong-typed name breaks the font list | Fixed | lettering.py `_load_stitch_font`, `_check_letter_object`, `list_fonts` | test_qa_damaged_stitch_fonts_give_a_clear_message |
| Medium | lettering | Edited/replaced font file not picked up until restart | Fixed: file date and size in the text cache key and the loaded-font cache | lettering.py `font_stamp`, `_load`; layout.py `_text_block` key | test_qa_an_edited_stitch_font_shows_at_once |
| Medium | lettering | Fabric has no effect on lettering | Already fixed (another agent: `fabrics.apply` in `_text_block`; spacing follows the fabric. Pull compensation and underlay stay the lettering's own) | layout.py | (theirs) |
| Medium | lettering | Letter height wrong for some fonts (trusts sCapHeight) | Fixed: the H is measured (whole H, also when it dips below the line); sCapHeight only without an H. Segoe Script, Ink Free, Comic now 20.0 mm for 20 | lettering.py `_load` | test_qa_letter_height_is_the_drawn_capital_not_the_fonts_claim |
| Medium | lettering | One file per name overwrites / merges colliding names, wrong count | Already fixed (phase 1, `keep_existing`: "Name (1).pes"); now also says which files got a number; device names and trailing dots handled in `nameFileStem` | features.ts `exportNames`, `nameFileStem` | features.lettering.test.ts |
| Medium | lettering | Text longer than its line: no warning | Already fixed (phase 2); message now says "overlap" for closed lines; a line under 1 mm is refused | lettering.py | test_text_longer_than_its_line_warns, test_qa_text_on_a_line_reads_upright... |
| Medium | lettering, compat | Put the text on the line ignores the text's turn/scale/flip; later turn/resize pivots off the line | Fixed: turn and mirror let go of, resize kept in the letter height, position moved to the middle of the line (so later turns pivot there) | features.ts `textOnLineItem` | features.lettering.test.ts |
| Medium | lettering, visual | Satin angle not turned with the letters (arcs, circle, path, Turn handle) | Fixed: placement on curves and paths turns each letter's angle; the item's turn/mirror/stretch too (`turn_with` in `_text_block`; only for text, drawn fills already do this in layout.ts) | lettering.py `turn_with`; layout.py `_text_block` | test_qa_stitch_angle_turns_with_the_letters |
| Medium | lettering | Winding rule approximate: islands in holes and opposite-wound parts dropped | Fixed: true non-zero winding fill (contours split into faces, each kept when the contours round it don't cancel) | lettering.py `_glyph_shapes`, `_winding` | test_qa_letters_follow_the_non_zero_winding_rule |
| Medium | lettering | 'Circle' is the same as 'Arch' | Fixed: Circle spreads the letters evenly all the way round | lettering.py `layout_text` | test_qa_circle_goes_all_the_way_round |
| Medium | lettering | Smile letters overlap; V-shaped line overlaps | Fixed for Smile (spaced along the circle at the letter tops: WOW MOM and MWMWMW now 0 overlap). V-shaped drawn lines: Skipped, letters are rigid; the inside of a sharp corner can still touch (rare, needs per-letter bending) | lettering.py | test_qa_smile_letters_do_not_collide |
| Medium | lettering, live-state | Text box loses keys typed while a render lands | Fixed: the saved text only replaces the box when you aren't typing in it (or another text is selected) | TextPanel.tsx | none (component; no DOM in vitest) |
| Medium | visual | Rotated lettering keeps the upright stitch angle | Fixed (same as above) | | test_qa_stitch_angle_turns_with_the_letters |
| Medium | visual, fill, fuzz | False "long loose stitches (up to 7.0 mm)" on satin-look letters from ~18 mm | Fixed on the lettering side: satin-look rows longest 6.8 mm (was 7.0, which float noise pushed over the 7 mm check). quality.py untouched | lettering.py `SATIN_MAX_STITCH_MM` | test_satin_look_crosses_strokes (6.5 <= stitch < 7) |
| Medium | tests | Curve flattening, kerning, cap-height fallback untested (test font only rectangles) | Partly fixed: kerning (GPOS) and cap height now tested with a second test font; curved glyphs still not (rectangles only) | test_lettering.py | test_qa_gpos_kerning_is_used, test_qa_letter_height... |
| Medium | tests | No lettering snapshot tests | Skipped: belongs to the tests agent's snapshot work; lettering geometry is pinned by test_lettering.py | - | - |
| Low | lettering | Kerning only from the legacy 'kern' table | Fixed: GPOS pair kerning (formats 1 and 2, extension lookups) used when the font has it, as shapers do; else the kern table. Roboto AV now -87 | lettering.py `LoadedFont.kern_pair`, `_gpos_pair` | test_qa_gpos_kerning_is_used |
| Low | lettering | Text centred on its ink: a descender moves the baseline | Fixed for straight text and monograms (centred side to side only; baseline fixed). Arcs and circle still centre on the ink | lettering.py `_centre(vertical=)` | test_qa_straight_text_keeps_its_baseline |
| Low | lettering | Decomposed accents beside the letter; newline/tab as '?' gap | Fixed: text composed (NFC), line breaks and tabs become spaces, invisible marks dropped. Multi-line text: Skipped (needs a design decision) | lettering.py `_clean_text` | test_qa_text_is_cleaned_before_layout |
| Low | lettering | Small-text warning coarse; monogram side letters unchecked | Fixed: warns below 6 mm (dots start dropping at 5); a monogram is checked by its side letters (0.7x). Thin-stroke font warning: Skipped (needs a stroke-width measure; low value) | lettering.py `SMALL_TEXT_MM`, `layout_text` | test_qa_small_monogram_side_letters_warn, test_validation_and_small_text_warning |
| Low | lettering | Text on a line: no choice of side/direction; right-to-left lines upside down; closed lines start opposite | Fixed without a new control: a line drawn right to left still reads left to right, upright; on a closed line the text stands outside, centred at the top | lettering.py `_along_path` | test_qa_text_on_a_line_reads_upright_whichever_way_it_was_drawn |
| Low | lettering | Put the text on the line destroys the line for a monogram | Fixed: refused with a message, line kept | features.ts `textOnLineItem` | features.lettering.test.ts |
| Low | lettering | Help says Text tool is T | Handed over: helpdocs.py owner (docs agent); it should say Shift+T | engine/threadline_engine/ai/helpdocs.py | - |
| Low | lettering | Moving/nudging lettering regenerates every letter | Fixed: letters are stitched at the text's origin and then moved, so a move reuses the cached stitches (43-character line: 0.34 s -> 0.02 s per nudge) | layout.py `_text_block` | test_qa_moving_text_moves_the_same_stitches |
| Low | lettering | Panel polish: font list capped at 200 silently; emptied box keeps old design; bad height kept | Fixed: "Showing 200 of N fonts: type part of a name" hint; an emptied box gets its text back; height outside 2-200 mm is put back with a message in your units; extra spacing follows the inch setting; One file per name (Ctrl+Alt+N) only enabled with lettering selected; curve size no longer shown for text on a line | TextPanel.tsx, actions.ts | none (component) |
| Low | visual | Lettering ignores the fabric | Already fixed (see Medium) | | |
| Low | visual | Missing characters silently swapped | Fixed (see Medium) | | |
| Low | tests, live-state | One file per name: duplicates overwrite | Already fixed (phase 1, `keep_existing`) | | |
| Low | tests | Nothing detects a field dropped from the text-cache key | Skipped: the key is now the whole spec plus the font file stamp; a key-completeness test belongs to the tests agent | | |
| Low | live-esc (from ui) | Esc in the lettering box doesn't bring back the text from before typing | Fixed: Esc restores the text from when the box was clicked into (and undoes a typing pause that already updated the design) | TextPanel.tsx | none (component) |
| Low | live-esc (from ui) | One Esc reverts the text box and also drops a held mode | Fixed: like InfoPanel, the box leaves Esc to a held thing first (`heldCount()`) | TextPanel.tsx | none (component) |
| Low | live-esc (from ui) | Click that closes the font list also acts on the canvas | Fixed: closes in the capture phase and stops the click reaching the canvas (as Menu.tsx) | TextPanel.tsx `FontPicker` | none (component) |

## 2. Changelog lines
- Lettering: characters a font doesn't have are left out with a message naming them (no more stitched question marks); a font with none of the letters says so.
- Letter height is now the real height of a capital H in every font (some script and Asian fonts came out up to a fifth too tall or short).
- Letters with an island inside a hole (©, ®) and symbols with separate parts stitch completely.
- Kerning now works in modern fonts that keep it in their OpenType tables (Roboto, Bahnschrift, Segoe Print...).
- Satin-look stitches stay across the strokes when lettering is turned, mirrored, curved, put round a circle or on a line.
- "Circle" now spreads the letters all the way round; "Smile" letters no longer bump into each other.
- Straight text keeps its baseline: names with and without a g or y line up from file to file.
- Text on a line reads upright even if the line was drawn right to left; on a closed shape it stands outside, centred at the top. Putting text on a line now keeps it on the line whatever its turn or size, and turning it afterwards pivots on the line. Monograms can't be put on a line (the line is kept).
- Big satin-look letters no longer trigger a false "long loose stitches" warning.
- Moving or nudging lettering is instant (no re-stitching of every letter).
- Save as stitch font now saves every letter with its accents and the kerning, straight into LUDD's fonts folder, ready in the font list; stitch fonts use the other case or the plain letter when a letter is missing, and damaged stitch fonts give a clear message instead of breaking the font list. An edited stitch font shows at once.
- Lettering panel: typing is never undone by a slow update; Esc brings back the text from before you typed; a cleared text box gets its text back; a letter height outside 2-200 mm is refused with a message; spacing follows the inch setting; the font list says when it's showing only the first 200.

## 3. Manual changes needed
- Small text: the advice is now 6 mm (was 5 mm).
- Circle shape: letters spread evenly all the way round (use Arch for a short curve).
- Text on a line: drawing direction no longer matters; closed shapes put the text outside at the top. Putting text on a line resets its turn and mirror (its size is kept as letter height). Monograms can't follow a line.
- Save this font as a stitch font: no file dialog; it goes into LUDD's fonts folder (`%APPDATA%\Ludd\fonts` on Windows, the data folder's `fonts` elsewhere), the message shows where; it contains all Latin letters with accents and the kerning. Satin look / Fill aren't offered for stitch fonts.
- Stitch fonts: a missing letter is drawn in the other case or without its accent, with a message.
- Lettering does not do multi-line text: line breaks become spaces (one text per line).

## 4. Stitch output changed (stitch-out log)
- Satin-look lettering: longest row stitch 6.8 mm (was 7.0). Test: "Hello Ag", Arial 25 mm, satin look.
- Turned lettering and lettering on Arch/Smile/Circle/line: satin angle follows each letter. Test: "Emma" Arial 20 mm satin, turned 45 degrees; "HAPPY BIRTHDAY" on Arch radius 40.
- Letter size for fonts whose cap-height field was wrong (Segoe Script, Segoe Print, Ink Free, MV Boli, Comic Sans, MS Gothic, Yu Gothic UI...): now true size. Test: "Hi" in Segoe Script 20 mm; measure the H.
- Kerning in GPOS fonts (Roboto, Bahnschrift...). Test: "AVATAR" Roboto 20 mm.
- Circle shape layout; Smile spacing (letters a little further apart along the baseline). Test: "WOW MOM" Smile 15 mm radius 40.
- Straight text with descenders sits 1-2 mm differently (baseline fixed instead of ink centre): existing projects may shift slightly on reopen.
- Letters are generated at the text origin then moved: fill rows can sit up to one row spacing differently than before (no visible change expected).
- Glyphs with islands (©, ®) and opposite-wound parts (±, ≤ in Comic Sans) now stitch completely.

## 5. Handed over
- `engine/threadline_engine/ai/helpdocs.py` (docs agent): "The Text tool (T)" should be "(Shift+T)"; mention Put the text on the line (Ctrl+Alt+L) and One file per name (Ctrl+Alt+N).
- quality.py owner: the long-stitch check `lengths > LONG_MM` still flags any other object that sews exactly 7.0 mm stitches (float noise); a small tolerance (`> LONG_MM + 0.05`) would fix it generally. Lettering no longer depends on it.
- tests agent: lettering snapshot test and a text-cache key-completeness test.
