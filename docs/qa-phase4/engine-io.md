# QA phase 4: engine-io (fuzz-rpc, project, security; RPC/project tests)

## Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | fuzz-rpc | Text on a line longer than the line: no warning | Already fixed (phase 2: "Text on a line warns") | lettering.py | test_lettering |
| Medium | fuzz-rpc | "Fewer jumps" uncached and quadratic | Already fixed (C3) | layout.py | test_connectors `test_qa_c3_*` |
| Medium | fuzz-rpc | travel_under + sort by colour sews travel on top | Already fixed (C6) | layout.py | test_connectors `test_qa_c6_*` |
| Medium | fuzz-rpc | One bad input line / unsendable result kills the engine | Fixed: number over 4300 digits, deep nesting, a stray non-UTF-8 byte, NaN/numpy results, odd ids all become error answers; the engine keeps serving. (UI restart: already C25) | rpc.py (`handle_line`, new `respond`, `_valid_id`), `__main__.py` (stdin `errors="replace"`) | test_rpc `test_qa_numbers_too_long…`, `…results_json_cant_carry…`, `…stray_byte…`, `…ids_of_the_wrong_kind…` |
| Medium | fuzz-rpc | JEF export splits stitches over 12.7 mm into jumps | Handed over: export/prepare owner (prepare.py, design.py) | | |
| Medium | fuzz-rpc | Stitch-edit moves are world-space deltas | Already fixed (phase 2: moves turn and resize with the design) | layout.py | |
| Medium | fuzz-rpc | Stop/trim in a drawn shape keyed by stitch index | Handed over: layout-ops owner (layout.py `_apply_ops`) | | |
| Medium | project | Fonts not embedded: lettering project won't open elsewhere | Fixed: the font file is embedded as `fonts/<sha>.<ext>` and extracted on open (C7's stand-in stays as the fallback for fonts too big to embed, over 64 MB) | project.py `_pack_font`, `open_project` | test_project `test_qa_fonts_travel_with_the_project…` |
| Medium | project | One recovery slot, no single-instance guard | Already fixed (C24) | lib.rs | |
| Medium | project | Failed Recover leaves autosave off; undrawable recovery reported as recovered | Already fixed by the ui agent (restoreRecovery returns false, banner stays, copy kept). Engine side added: an unreadable recovery copy is moved aside (`unrecovered-<time>.ludd`) instead of erroring every launch; `project.discard_recovery {keep: true}` moves it aside | project.py `recovery`, `_set_aside`, `discard_recovery(keep)` | test_project `test_qa_an_unreadable_recovery_copy…` |
| Medium | project | Reopened designs named by cache hash; resave loses the name | Fixed: `original_name` kept for files already in the cache; on open the item gets `name = original_name` | project.py `_pack`, `open_project` | test_project `test_qa_reopened_designs_keep_their_own_name…` |
| Medium | project | Project version never bumped: 1.0.0 sews new projects wrong | Fixed: project stamped `version 1` unless it uses something 1.0.0 didn't know (fill patterns, motif lines, satin ribbons, stitch edits, text on a line, fewer jumps), then `version 2` plus a `features` list; open refuses unknown features ("update LUDD to open it"). Add new features to `_features`/`KNOWN_FEATURES` in project.py | project.py | test_project `test_qa_projects_say_what_they_need…` |
| Medium | project | Stitch-edit moves world-space | Already fixed (phase 2) | | |
| Medium | project | Machine files written in place | Already fixed by another agent (design.write is atomic now) | design.py | |
| Medium | project | One bad user JSON file breaks charts/machines; non-atomic writes | Fixed for thread charts, My threads and AI settings (atomic `storage.write_json`, BOM-tolerant `read_json`, wrong-shaped files skipped, a damaged My threads is kept aside as `my-threads.damaged.json.bak` and a fresh list starts). Machine profiles: already hardened by another agent (a UTF-8-with-BOM profile is still skipped: profiles.py could use `storage.read_json`). font-index.json: handed over to lettering owner | storage.py, threads.py, ai/settings.py | test_threads `test_qa_a_broken_user_file…`, `test_qa_user_files_are_written_whole…` |
| Medium | project | open_project: raw errors, missing/locked shown as damaged, wrong shapes open, NaN hangs 60 s | Fixed: separate messages for missing, in use, folder, damaged, too new; shapes checked; NaN/Infinity refused; data-folder write errors explained | project.py `open_project`, `_read_member` | test_project `test_qa_wrong_shaped_projects…` (6 cases), `test_qa_missing_locked_and_odd_files…` |
| Medium | security | No single-instance guard | Already fixed (C24) | | |
| Medium | security | One file per name overwrites/drops names | Handed over: features.ts owner (also in ui/platform notes; C12 fixed overwriting) | | |
| Medium | security | Dev engine bridge open to any page | Already fixed by the platform agent | vite-engine-bridge.ts | |
| Medium | security | API key only base64 on macOS/Linux, toast says encrypted | Fixed: `ai.settings` returns `key_protection` ("windows"/"file"); the toast says "Key saved in a file only your user account can read." off Windows | ai/settings.py `public`, ai.ts `keySavedText` | test_ai `test_qa_settings_say_how_the_key_is_kept`, actions.engineio.test.ts |
| Medium | security | .ludd trusted for local paths (re-save embeds any file, UNC) | Fixed: on open, every path not coming from the project's own embedded files is dropped (designs, pictures, font paths). Only LUDD's own recovery file keeps links | project.py `open_project(trust_paths)` | test_project `test_qa_a_project_names_no_file_outside_itself` |
| Medium | tests | RPC method wiring untested | Fixed: every registered method called through the dispatcher with sample params (only the model download is left out); every method name the UI calls must exist | | test_rpc `test_qa_every_engine_method_answers…`, `test_qa_every_method_the_ui_calls_exists` |
| Low | fuzz-rpc | Lettering ignores the fabric | Handed over: layout/lettering owner | | |
| Low | fuzz-rpc | Engine start-up 10 s ping, no retry | Already fixed (C25) | sidecar.ts | |
| Low | fuzz-rpc | Raw Python messages; TypeErrors mislabelled invalid params, not logged | Fixed: parameters are checked against the method's signature first (-32602 only for those); a bug inside a method is -32603 "Something went wrong in LUDD's engine (method: …). Please report this." with the traceback on stderr | rpc.py | test_rpc `test_qa_a_bug_inside_a_method…` |
| Low | fuzz-rpc | AI-trace embedding cache keyed on size only | Handed over: ai/segment.py owner (autotrace) | | |
| Low | fuzz-rpc | Source-file cache trusts mtime, never evicted | Handed over: layout.py owner | | |
| Low | fuzz-rpc | Blank PES with every stitch removed | Already fixed (C4: deleting everything is refused) / rest handed over to layout owner | | |
| Low | fuzz-rpc | Object cache capped at 512 (FIFO) | Handed over: layout.py owner | | |
| Low | fuzz-rpc | Text cache stale when a .luddfont changes | Handed over: layout.py owner | | |
| Low | fuzz-rpc | Autosave re-sends every picture's base64 | Fixed: autosave sends pictures by path (no `data_url`); Save still sends it, and the engine now uses it when the picture file is gone | actions.ts `startAutosave`, project.py `_pack` | actions.engineio.test.ts, test_project `test_qa_autosave_keeps_the_rest…` |
| Low | project | Save brittle: no retry on a held file, temp files left, long paths fail | Fixed: replace retried for about 4 s; message says "in use by another program"; `.ludd-*.tmp` older than an hour swept (project folder and recovery folder); extended-length paths on Windows; fsync before replace | project.py `_replace`, `_sweep_temps`, `_long`, `_write_zip` | test_project `test_qa_save_waits_for_a_file_held…`, `test_qa_long_paths_save_and_open` (fails without the fix) |
| Low | project | Double-clicked file dropped while recovery pending | Already fixed (C24) | App.tsx | |
| Low | project | Recovery copy deleted by a startup race | Fixed: `recoveryWaiting` starts true until the recovery check answers (a failed check turns it off); close already awaits the discard | actions.ts | actions.engineio.test.ts |
| Low | project | Autosave all-or-nothing on unreadable pictures; recovery only tolerates bad zips | Fixed: autosave leaves out a picture it can't read (or keeps a design linked); a wrong-shaped recovery is set aside | project.py `_pack(autosave)`, `recovery` | test_project `test_qa_autosave_keeps_the_rest…`, `test_qa_an_unreadable_recovery…` |
| Low | project | Zip bomb: unbounded member reads | Fixed: member sizes checked before reading (project.json 32 MB, pictures 40 MB, designs and fonts 64 MB); `load_image` checks the file size before reading | project.py `MAX_MEMBER_BYTES`, `_read_member`, `load_image` | test_project `test_qa_oversized_members…` |
| Low | project | project-files cache never pruned, trusted by name | Fixed: members must match their hash; a cached copy that doesn't is rewritten; copies unused for 90 days are deleted at engine start (opening touches them); `kept.keep` is best effort | project.py `extract`, kept.py `prune`, `__main__.py` | test_project `test_qa_members_must_match…`, `test_qa_private_copies_unused…` |
| Low | project | Threadline data never merged when both folders exist | Fixed: once, files missing from Ludd are copied over (never replacing); a marker stops it repeating; a failed rename copies instead of running on the old folder | storage.py `_carry_over` | test_project `test_qa_old_data_is_copied_over…` |
| Low | project | No project schema; machine schema stale | Skipped: needs the owner's decision (write schemas + codegen, or change CLAUDE.md); open_project now validates the shape it needs | | |
| Low | project | Chart ids used as file names; delete_chart('my-threads') | Fixed: ids must be `[a-z0-9-]`; My threads can't be deleted as a chart | threads.py `_check_id`, `delete_chart` | test_threads `test_qa_chart_ids_cant_reach…` |
| Low | project | Opening a project overwrites the saved machine/hoop | Fixed: a project's machine and hoop apply to the session only (also on Recover; autosave now carries the hoop) | actions.ts `applyProjectMachine`, `openProject`, `restoreRecovery` | actions.engineio.test.ts |
| Low | project | One file per name: device names, duplicates | Handed over: features.ts owner | | |
| Low | security | Huge-pixel pictures: GBs in tracing, raw Pillow bomb message | Fixed at the door: `image.load` refuses over 120 megapixels (header only) with a plain message, and unreadable pictures. Tracing's full-size allocation: handed over to trace.py owner | project.py `_check_pixels` | test_project `test_qa_pictures_with_too_many_pixels…` |
| Low | security | Crafted .vp3/.hus allocates GBs | Handed over: design.py owner | | |
| Low | security | No bound on shape size / stitch count | Handed over: digitize/stitches.py owner | | |
| Low | security | Chart id path traversal; export_stitch_font writes anywhere | Fixed (chart ids, see above); export_stitch_font: handed over to lettering owner | threads.py | test_threads |
| Low | security | Project cache trusts member names | Fixed (hash check, see above) | project.py | test_project `test_qa_members_must_match…` |
| Low | security | Update check fires before the user's choice | Already fixed by the platform agent | updates.ts | updates.test.ts |
| Low | security | Release workflow hardening | Already fixed by the platform agent (except SHA pinning) | | |
| Low | security | Updater key and password side by side; RELEASING.md | Handed over: docs owner / lead | | |
| Low | security | Windows account name in the font path | Fixed: the font path isn't saved (the font is embedded) | project.py `_pack_font` | test_project `test_qa_fonts_travel…` (asserts no folder name) |
| Low | security | project-files kept forever, undocumented | Fixed (90-day tidy-up); docs: see "Manual changes needed" | kept.py | |
| Low | security | AI settings accept wrong types and break every AI call | Fixed: settings of the wrong kind are ignored when read and refused when saved | ai/settings.py `_merge`, `_fits`, `save` | test_ai `test_qa_settings_of_the_wrong_kind…` |
| Low | security | Print template: unescaped colour | Handed over: print.ts owner | | |
| Low | security | Local AI accepts any address and skips the preview; cloud may be http; dialog never names the host | Fixed: a model not on this computer counts as leaving it (the "before you send" preview shows); cloud addresses must be https unless on this computer; the preview says where it goes ("Send this to Anthropic at api.anthropic.com?") | ai/providers.py `on_this_computer`, `estimate` (`host`), ai/settings.py, ai.ts `sendTitle`, AIPanels.tsx | test_ai `test_qa_a_model_on_another_machine…`, `test_qa_a_cloud_address_must_be_https…`, actions.engineio.test.ts |
| Low | security | AI model download not pinned or hash-checked | Handed over: ai/segment.py owner (needs the model's commit and sha256: a network lookup) | | |
| Low | security | Project members read with no size limit | Fixed (see zip bomb) | project.py | test_project |
| Low | security | Design browser follows junction loops | Fixed in the design browser (links and junctions not followed, each folder once, at most 5000 folders). Batch convert (design.convert_folder): handed over to design.py owner | library.py `_walk` | test_library `test_qa_junction_loops_are_not_followed` (Windows) |
| Low | tests | TypeError reported as invalid params, not logged | Fixed (see fuzz-rpc) | rpc.py | test_rpc |
| Handover (ui) | | layout.check off the engine's main loop | Fixed: `layout.check` runs in the background; only its render takes the dispatcher's lock (every main-loop method holds it), so the shared render caches are never used by two threads at once, and the checks themselves never hold up a render | rpc.py `Dispatcher.lock`, methods.py `layout_check`, layout.py `check(rendered=)` (one-line change) | test_rpc `test_qa_a_slow_quality_check_doesnt_hold_up_a_render` |
| Handover (platform) | | Prune project-files; don't resend pictures on autosave | Fixed (rows above) | kept.py, actions.ts | |
| Handover (platform) | | Settings "About / Licences" showing THIRD-PARTY-NOTICES.txt | Skipped: where the installer puts the file can't be checked without a build, and the app has no file-read permission; a small Tauri command in lib.rs that returns the text would be simplest (lead/platform) | | |

## Changelog lines
- **The engine no longer stops** on a damaged request or an unexpected answer; unexpected problems now say "Something went wrong in LUDD's engine … Please report this." instead of a cryptic message.
- **Fonts travel with your project**: lettering looks the same on a PC that doesn't have the font. Projects no longer contain your Windows user name.
- **Opening a project** tells you plainly when the file is missing, in use by another program, damaged, or from a newer LUDD. Projects can't make LUDD read files outside them, and damaged or oversized projects are refused safely.
- **Reopened projects keep the real names** of placed designs (not a long code), also after saving again.
- **Projects say what they need**: an older LUDD asks you to update instead of sewing a newer project wrong.
- **Saving** waits a moment when another program (antivirus, OneDrive) is holding the file, works in very long folder paths, and cleans up after a save that was interrupted.
- **Crash recovery**: a recovery copy is never deleted before you're asked about it; one that can't be read is kept aside instead of erroring at every start; autosave keeps your work even if a picture's file is gone, and no longer sends whole pictures to the engine every few seconds.
- **Opening a project** uses its machine and hoop for that project only; your usual machine stays your default.
- **My threads and imported charts** are saved safely (a crash mid-save can't damage them); one broken chart file no longer hides all the others.
- **Copies of added pictures and designs** that haven't been used for 90 days are deleted from LUDD's data folder.
- Data from the old Threadline folder is brought over even when a Ludd folder already exists.
- **Design browser** no longer loops forever through folder shortcuts (junctions).
- **Very large pictures** (over 120 megapixels) are refused with a plain message instead of running out of memory.
- **AI**: an AI model on another computer now shows "what will be sent" first, like the cloud; the dialog names where it goes; internet AI addresses must use https; on Mac and Linux the key message no longer says "encrypted for your Windows account". Broken AI settings no longer stop every AI feature.
- Quality checks run alongside editing, so a check never holds up the next redraw.

## Manual changes needed
- Projects embed the lettering's font file as well as designs and pictures (USER-MANUAL "projects"; C7's note that fonts aren't embedded is now wrong). The help text in ai/helpdocs.py (if it says fonts aren't embedded) too.
- API key storage: "encrypted for your Windows account" is Windows only; on macOS/Linux it's a file only your account can read.
- AI "On this computer" with an address of another machine now shows the before-you-send preview; cloud service addresses must start with https://.
- Data folder (`%APPDATA%\Ludd`): mention `project-files` (private copies of added pictures and designs, deleted after 90 days unused) and `recovery` (`unrecovered-*.ludd` files are crash copies that couldn't be opened).
- Pictures: at most 40 MB and about 120 megapixels.
- Opening a project no longer changes your usual machine.

## Stitch output changed
None.

## Handed over
- **layout.py owner**: stops/trims inserted into drawn shapes keyed by stitch index; lettering ignores the fabric; source-file cache (mtime only, never evicted); object cache 512 FIFO; text cache stale on .luddfont edits; blank-design export warning. Optional: show `original_name` in `render` / `itemLabel` for file items (open now sets `name`, so only "rename back to empty" shows the hash).
- **prepare.py / design.py owner**: JEF over-length stitches; crafted .vp3/.hus memory; `convert_folder` following junction loops (could reuse `library._walk`).
- **lettering.py owner**: `font-index.json` holding a list breaks fonts.list (use `storage.read_json` + shape check); `export_stitch_font` should force the `.luddfont` extension; `export_stitch_font({})` is a KeyError (now reported as an engine bug).
- **profiles.py owner**: read profiles with `storage.read_json` so a UTF-8-with-BOM profile (Notepad) isn't silently skipped.
- **trace.py / autotrace owner**: downscale before converting huge pictures; ai/segment.py: embedding cache keyed on size only; model download pin + sha256.
- **digitize/stitches.py owner**: upper bound on shape size / stitch count.
- **features.ts owner**: One file per name (device names, duplicates, case).
- **print.ts owner**: escape the colour in the print template.
- **docs owner / lead**: RELEASING.md (delete the key password file), manual items above, project schema decision (schemas/ vs CLAUDE.md).
- **App.tsx (ui)**: nothing required; `project.discard_recovery` now takes `{keep: true}` to move a copy aside instead of deleting, if the Recover banner ever wants a "Set aside" choice.

## Test results
- Engine, my files: test_rpc (17), test_project (32), test_threads, test_ai, test_library, test_cleanup: all pass.
- Full engine suite: 374 passed, 1 skipped, 5 failed: `test_digitize.py::test_snapshot[fill_contour|fill_cross|fill_donut|fill_square_45|fill_stipple]`, fill-stitch snapshots changed by another agent's work in progress (not touched here). test_golden: 69 passed.
- UI: `pnpm typecheck` clean; vitest actions.engineio.test.ts (4), actions.qa.test.ts, ai.test.ts pass.
