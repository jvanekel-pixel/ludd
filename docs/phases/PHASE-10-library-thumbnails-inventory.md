# Phase 10: Design library, OS thumbnails, thread inventory

| | |
| --- | --- |
| Weight | Heavy (platform code). Do it on the larger plan. |
| Session lead | Sonnet 5.5. Track C is **Hard: give this worker the stronger model.** |
| Audit | The usual phase gate, plus a security read of Track C by the top model: its code runs inside Windows on files from strangers. |
| Depends on | Phase 3. Track D also needs the sewing estimate (`design/estimate.ts`, PR #23). Nothing here needs Phase 9. |
| Changes stitches | No. |
| Closes (compendium) | OS file-explorer thumbnails ★ · Tags, collections, search by size/colors/stitches · Duplicate finder · Thumbnail cache kept between sessions · Thread inventory and shopping list |

## 1. Goal and done-when

Browse designs reads a folder afresh each time, stops at 600 files, and forgets its thumbnails when LUDD closes. Windows shows every PES as the same blank icon. And LUDD knows which spools you own but not which are nearly empty. Embrilliance and Hatch each sell the first two as separate products. This phase builds a real library, thumbnails in the file manager, and a shopping list.

**Done when:**

1. `python scripts/check.py --all` prints `RESULT: PASS`, and `cargo test --locked --manifest-path apps/thumbs/Cargo.toml` passes on Windows and Linux.
2. A folder of 1,000 designs shows tagged thumbnails: the second time it is opened no design file is read again and the first page arrives in under 2 seconds (`test_thousand_designs_second_open_is_fast`), and the grid draws fewer than 80 cards however many designs there are.
3. Tags, a collection and the filters (fits my hoop, colors, stitches, format) each narrow that folder.
4. The duplicate finder groups an exact copy, the same design saved as PES and as DST, and a copy resized 110%.
5. On Windows, Explorer shows thumbnails for `.ludd` projects and for PES, JEF and DST, proven in CI by asking the built DLL for a bitmap the way Explorer does, and by hand on the owner's PC.
6. On Linux, the `.deb` installs a thumbnailer whose command writes a PNG.
7. For the open design, the shopping list names every thread that is missing, out or too low, and saves as CSV.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P10-S1 | Branch, package skeleton, stubs (section 6) | No | Step 0 |
| P10-A1 | Library index (sqlite) and incremental scan | No | A |
| P10-A2 | Thumbnails kept on disk | Yes | A |
| P10-A3 | Search, filters, paging | No | A |
| P10-A4 | Tags and collections | No | A |
| P10-A5 | Duplicate finder | No | A |
| P10-B1 | Organizer window replaces Browse designs | Yes | B |
| P10-B2 | Find (`library.find`, `Mod+F`), tags (`library.tags`, `Alt+G`), duplicates (`library.duplicates`, `Mod+Alt+Y`) | Yes | B |
| P10-C1 | Thumbnail crate: bounded readers for PES, JEF, DST and `.ludd`; drawing | No | C |
| P10-C2 | Windows Explorer thumbnail handler, registered per user | Yes | C |
| P10-C3 | Linux thumbnailer in the `.deb` | Yes | C |
| P10-C4 | A preview picture inside every saved `.ludd` | No | C |
| P10-D1 | How much is left on each spool | Yes | D |
| P10-D2 | Thread inventory and shopping list (`threads.inventory`, `Mod+Alt+S`) | Yes | D |
| P10-Z1 | Docs, frozen-engine smoke check, installer check, handoff | – | Integration |

**Out of scope:** macOS Finder thumbnails (decision 1); deleting or moving the user's files; indexing a whole disk; thumbnails in Explorer for formats beyond PES, JEF and DST; measuring thread in meters per spool; cloud or shared libraries.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Finder thumbnails on a Mac need a signed Quick Look extension, and LUDD's installers are not signed (L-015). Wait for code signing? | Yes, wait. | Not built; recorded as L-060. |
| 2 | If another program (for example Embrilliance's Thumbnailer) already draws thumbnails for PES, JEF or DST, should LUDD take over? | No. LUDD always handles `.ludd`, and a stitch format only where nothing else does. A switch in Settings lets you take them over. | That. |
| 3 | Turn Explorer thumbnails on at install, with a switch in Settings to turn them off? | Yes. | On, with the switch. |
| 4 | May the duplicate finder delete or move files? | No. It shows the groups and opens their folders; you decide. | Show and reveal only (L-063). |

## 4. Preflight

| Check | Command | Expect |
| --- | --- | --- |
| Phase 3 seams are in | `git ls-files engine/threadline_engine/methods/designs.py apps/desktop/src/dialogs.tsx apps/desktop/src/cmd/index.ts scripts/check.py` | four paths |
| The library is one file with the 600 limit | `grep -n "MAX_FILES = 600" engine/threadline_engine/library.py` | one match |
| One library method | `grep -c "library\." engine/tests/snapshots/rpc_methods.json` | 1 |
| Browse designs is still the old dialog | `grep -n "export function BrowseDialog" apps/desktop/src/components/FeatureDialogs.tsx` | one match |
| The sewing estimate is in | `git ls-files apps/desktop/src/design/estimate.ts` | prints the path (if not, Track D waits for PR #23) |
| Spools have no amount yet | `grep -n '"left"' engine/threadline_engine/threads.py` | nothing |
| Only `.ludd` is associated; the installer is per user | `grep -n '"ludd"\|"installMode": "currentUser"' apps/desktop/src-tauri/tauri.conf.json` | both |
| A project holds no preview yet | `grep -n "preview.png" engine/threadline_engine/project.py` | nothing |
| Opening a project ignores files it does not name | read `open_project`: it reads `project.json` and the members that names | true |
| sqlite is in the engine's Python | `cd engine && uv run --locked python -c "import sqlite3; print(sqlite3.sqlite_version)"` | a version number |
| Tauri config keys (Track C reads the Tauri 2 docs first) | `bundle.windows.nsis.installerHooks`, `bundle.linux.deb.files`, `tauri.windows.conf.json` / `tauri.linux.conf.json` | all three exist under those names |
| Baseline is green | `python scripts/check.py` | `RESULT: PASS`; counts into the session notes |

## 5. Architecture

### 5.1 Engine

```
engine/threadline_engine/
  library/                  was library.py
    __init__.py             re-exports scan, entry, thumbnail, LibraryError, THUMB_PX, MAX_FILES
    browse.py               the old one-shot scan (kept working; the organizer stops using it)
    thumbs.py               drawing; png_bytes(pattern, size); PNG files on disk
    index.py                sqlite: schema, open, upgrade, rebuild
    scanner.py              incremental scan in steps
    query.py                search, filters, paging
    tags.py                 tags and collections
    dupes.py                stitch hash, signature, duplicate groups
  methods/library.py        NEW group (library.scan moves here from designs.py)
  threads.py                + spool amounts, save a list
  project.py                + preview.png in a saved project
```

Everything lives in LUDD's data folder: `library/index.db` and `library/thumbs/<aa>/<content hash>.png`. Nothing is ever written beside the user's designs.

### 5.2 The index

```sql
PRAGMA user_version = 1;
CREATE TABLE roots(id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, added_at REAL, last_scan REAL);
CREATE TABLE designs(
  id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
  path TEXT UNIQUE NOT NULL, name TEXT NOT NULL, name_key TEXT NOT NULL, ext TEXT NOT NULL,
  size INTEGER NOT NULL, mtime REAL NOT NULL, ok INTEGER NOT NULL, error TEXT,
  width_mm REAL, height_mm REAL, stitches INTEGER, colors INTEGER, color_list TEXT,
  content_hash TEXT,   -- sha1 of the file: the thumbnail's name, and what tags hang on
  stitch_hash TEXT,    -- sha1 of the stitch points, to 0.1 mm, moved to start at (0, 0)
  signature BLOB,      -- 256 bytes: a 16 x 16 picture of where the thread lies
  seen_scan INTEGER);
CREATE INDEX designs_root ON designs(root_id);
CREATE INDEX designs_stitch ON designs(stitch_hash);
CREATE INDEX designs_name ON designs(name_key);
CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL COLLATE NOCASE);
CREATE TABLE design_tags(content_hash TEXT NOT NULL, tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY(content_hash, tag_id));
CREATE TABLE collections(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL COLLATE NOCASE, created_at REAL);
CREATE TABLE collection_items(collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  content_hash TEXT NOT NULL, added_at REAL, PRIMARY KEY(collection_id, content_hash));
```

Tags and collections hang on the file's contents, not its path: a design that is renamed or moved keeps them, and exact copies share them. One connection per call, `journal_mode=WAL`, all writes behind one lock. No full-text extension (it is not in every sqlite build): search is `LIKE` on `name_key`.

### 5.3 RPC methods (all in `methods/library.py` unless noted)

| Method | Parameters → result |
| --- | --- |
| `library.roots` | → `[{id, path, count, last_scan}]` |
| `library.add_root` / `library.remove_root` | `path` → root · `id` → nothing (index rows only; files are never touched) |
| `library.scan_start` / `library.scan_step` / `library.scan_stop` | `root_id` → `{scan}` · `scan, budget_ms=400` → `{seen, read, removed, current, finished}` · `scan` |
| `library.query` | `filter, sort="newest", offset=0, limit=200` → `{total, designs: [{id, path, name, format, ok, error, width_mm, height_mm, stitches, colors, color_list, tags}]}` |
| `library.thumbs` | `ids` → `{"<id>": "data:image/png;base64,…"}` (at most 200 ids) |
| `library.tags` / `library.tag` / `library.rename_tag` / `library.delete_tag` | → `[{id, name, count}]` · `ids, add=[], remove=[]` · `id, name` · `id` |
| `library.collections` / `library.collection_create` / `library.collection_delete` / `library.collection_add` / `library.collection_remove` | as named; add and remove take `id, design_ids` |
| `library.duplicates_start` / `library.duplicates_step` | `root_ids=None, near=True` → `{job}` · `job, budget_ms=400` → `{finished, done, total, groups?}` |
| `library.reveal` | `id` → opens the design's folder in the file manager (only for paths in the index) |
| `library.rebuild` | → empties the design rows and thumbnails; tags and collections stay |
| `threads.my_set` (`methods/threads.py`) | `spools: [{brand, code, color, left}]` → the My threads chart |
| `threads.save_list` (`methods/threads.py`) | `dest, format, rows` → `{path}` |

`filter` is `{root_ids?, text?, tags?, collection?, fits?: {width_mm, height_mm}, colors_max?, stitches_max?, formats?, ok_only?}`. Scans and the duplicate search run in steps the window keeps asking for, so a long one shows a count and stops the moment the window stops asking. That is why this phase does not need Phase 9's progress and cancel.

Thumbnails reach the window as data URLs for the visible designs only. The app's content security policy and file access stay as they are.

### 5.4 Window

```
apps/desktop/src/
  components/library/LibraryDialog.tsx  LibrarySidebar.tsx  LibraryGrid.tsx  LibraryFilters.tsx
                     TagEditor.tsx  DuplicatesView.tsx  library.css
  feat/library.ts                 its own small store, the scan loop, the thumbnail cache
  components/InventoryDialog.tsx  feat/inventory.ts  feat/shoppingList.ts
  cmd/library.ts  cmd/inventory.ts
```

### 5.5 Thumbnail crate

```
apps/thumbs/                      its own Cargo.toml and Cargo.lock; not part of the app's crate
  src/lib.rs                      render(bytes, kind, size, background) -> Rgba   (safe Rust only)
  src/formats/pes.rs jef.rs dst.rs ludd.rs
  src/draw.rs                     lines into a pixel buffer
  src/win.rs                      Windows only: the COM class (the one file with `unsafe`)
  src/bin/ludd-thumbnailer.rs     ludd-thumbnailer <input> <output.png> [size]
  tests/
apps/desktop/src-tauri/
  src/thumbs.rs                   turning Explorer thumbnails on and off (per user)
  tauri.windows.conf.json  tauri.linux.conf.json  installer/hooks.nsh
scripts/build_thumbs.py           builds the crate and copies its output into src-tauri/binaries/
```

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-10/library-thumbnails-inventory` from `main`.
2. Library skeleton, pure moves: `library.py` → `library/browse.py` (`scan`, `entry`, `_walk`, `_thumbs`, `MAX_FILES`, `MAX_FOLDERS`) and `library/thumbs.py` (`thumbnail`, `_png`, `_hex_rgb`, `THUMB_PX`, plus `png_bytes(pattern, size) -> bytes`, which `thumbnail` now calls). `library/__init__.py` re-exports the old names. `test_library.py` passes unchanged.
3. New `methods/library.py`, imported by name in `methods/__init__.py`; `library.scan` moves into it; the other 21 `library.*` names and the two `threads.*` names in 5.3 are stubs that raise "not built yet". All 23 go in `rpc_methods.json`.
4. `design/types.ts`: `export type SpoolLeft = "full" | "half" | "low" | "out"` and `ChartThread.left?: SpoolLeft`.
5. `prefs.ts`: `explorerThumbs?: boolean`, `thumbFormats?: string[]`, `thumbTakeOver?: boolean`, `spoolMeters?: number`, `librarySort?: string`.
6. `cmd/index.ts`: imports `./library` and `./inventory` (created empty). `.gitignore`: `apps/thumbs/target/`.
7. `python scripts/check.py`, then commit ("Phase 10: start"). Workers branch from this commit.

## 7. Tracks

A, B, C and D run together. B builds against the method list in 5.3 with a fake engine in its tests, so it does not wait for A. Every worker follows "Worker rules" in `BUILDPLAN.md`.

---

### Track A: library index

**Owns:** `engine/threadline_engine/library/**`, the `library.*` bodies in `methods/library.py`, new tests. **Must not touch** `project.py`, `threads.py`, anything under `apps/`.

#### P10-A1 Index and incremental scan

`index.py` opens `library/index.db`, creating the schema in 5.2. An index from a newer LUDD (`user_version` above 1) or a damaged one is renamed aside (`index.newer.db`, `index.damaged.db`) and a fresh one is started, with a plain note.

`scanner.py` walks a root with the existing `_walk` (links and junctions are not followed; 5,000 folders at most). For each file LUDD can read: if the index has that path with the same size and date, mark it seen and move on. Otherwise read it once: content hash, `design.load` and `design.summarize` for the facts, stitch hash, signature, thumbnail. A file that cannot be read is listed with its error. Files over 64 MB are listed as "too big to read". Rows are written 50 to a transaction. `scan_step` works until its time budget is used and returns where it is; the walker is kept in memory between steps and dropped after 5 minutes without one. When a scan finishes, rows of that root it did not see are removed, and thumbnails no design uses are deleted. A root holds 50,000 designs at most.

#### P10-A2 Thumbnails on disk

`thumbs.py` writes each 160 px PNG once, named by content hash, through a temporary file. `library.thumbs` reads them back as data URLs. A missing file is redrawn from the design.

#### P10-A3 Search, filters, paging

`query.py` builds one SQL statement from `filter`. `text` matches any part of the name, ignoring case. `fits` keeps designs no wider and no taller than the hoop. `tags` needs every tag named. Sorts: newest, name, size, stitches. `total` is the count before paging.

#### P10-A4 Tags and collections

`tags.py`. Tag names ignore case and are trimmed; an empty name is refused. Removing a root leaves tags and collections in place, so adding the folder again brings them back.

#### P10-A5 Duplicate finder

Three kinds of group, strongest first:

| Kind | Rule |
| --- | --- |
| Exact copy | same content hash |
| Same stitches | same stitch hash (the same design in another format or under another name) |
| Look alike | signatures at least 92% alike, in any of the eight turns and mirrors, with width-to-height ratios within 5% |

The signature: stitch lines drawn into a 16 × 16 grid over the design's bounds (shape kept, centered), each cell the share of thread in it, as bytes. Likeness is `1 − Σ|a − b| / (Σa + Σb)`. To keep the search quick, designs are sorted by width-to-height ratio and only neighbors within 5% are compared, in numpy blocks, inside `duplicates_step`'s budget. Each look-alike group carries its likeness as a percentage. Nothing is ever acted on automatically.

#### Track A tests

| Test (file) | Proves |
| --- | --- |
| `test_old_names_still_import` (`test_library_index.py`) | `scan`, `entry`, `thumbnail`, `THUMB_PX`, `MAX_FILES`, `LibraryError` |
| `test_schema_is_version_1`, `test_a_newer_index_is_set_aside`, `test_a_damaged_index_is_set_aside` | P10-A1 |
| `test_first_scan_reads_every_file_once`, `test_second_scan_reads_nothing` (`test_library_scan.py`) | counts calls to `design.load` |
| `test_a_changed_file_is_read_again`, `test_a_deleted_file_leaves_the_index`, `test_a_damaged_file_is_listed_with_its_error` | upkeep |
| `test_scan_step_keeps_to_its_budget`, `test_over_64_mb_is_listed_not_read`, `test_links_out_of_the_folder_are_not_followed` | limits |
| `test_thousand_designs_second_open_is_fast` | 1,000 small DST files made in the test; second scan plus first page under 2 s |
| `test_thumbnails_are_kept_by_content_hash`, `test_a_missing_thumbnail_is_redrawn` | P10-A2 |
| `test_text_matches_part_of_a_name_any_case`, `test_fits_the_hoop`, `test_color_and_stitch_limits`, `test_format_filter`, `test_every_tag_is_needed`, `test_paging_is_stable`, `test_sorts` (`test_library_query.py`) | P10-A3 |
| `test_tags_follow_a_renamed_file`, `test_tag_names_ignore_case`, `test_delete_tag_removes_it_everywhere`, `test_collection_add_and_remove`, `test_removing_a_folder_keeps_its_tags` (`test_library_tags.py`) | P10-A4 |
| `test_a_copied_file_is_an_exact_copy`, `test_pes_and_dst_of_one_design_are_same_stitches`, `test_a_resized_copy_looks_alike`, `test_a_mirrored_copy_looks_alike`, `test_different_designs_are_not_grouped`, `test_duplicates_step_keeps_to_its_budget` (`test_library_dupes.py`) | P10-A5 |
| `test_reveal_refuses_a_path_not_in_the_index` (`test_library_index.py`) | safety |

---

### Track B: organizer

**Owns:** `apps/desktop/src/components/library/**`, `feat/library.ts`, `cmd/library.ts`, removing `BrowseDialog` from `components/FeatureDialogs.tsx` and its line in `App.tsx`, new tests. Styles go in `components/library/library.css`, not `styles.css`.

#### P10-B1 Organizer window

`Mod+Alt+B` (the existing `file.browse`) opens it: the new window is registered as the dialog `"browse"`, and the old `BrowseDialog` is deleted in the same commit. It fills most of the app window.

| Area | What it holds |
| --- | --- |
| Left | Folders (add, remove, refresh), Collections, Tags, Duplicates |
| Top | Find box · "Fits my hoop" (names the chosen hoop) · Colors up to · Stitches up to · format chips · sort |
| Middle | The grid: a picture, name, size, stitches and colors per design, its tags as chips |
| Bottom | "1,240 designs · 3 selected", scan progress with Stop |

Click selects (Ctrl and Shift for more). Double-click or Enter opens the design. "+ Add" adds it to the open design. Right-click: Open, Add to the design, Tag…, Add to collection, Show in folder. The first time, the folder Browse designs used last becomes the first library folder.

The grid stays fast by drawing only the rows in view, two rows either side: cards are a fixed 148 × 190 px, positions come from the scroll offset, no new dependency. Designs arrive 200 at a time as the user scrolls. Thumbnails are asked for the visible designs only, 80 ms after scrolling stops, and the last 2,000 are kept in memory.

A scan is a loop in `feat/library.ts`: `scan_start`, then `scan_step` until `finished`, updating the count; Stop or closing the window ends the loop and calls `scan_stop`.

#### P10-B2 Find, tags, duplicates

| Command | Does |
| --- | --- |
| `library.find` `Mod+F` | opens the organizer with the cursor in the Find box |
| `library.tags` `Alt+G` | opens the tag editor for the selected designs: tick existing tags, type a new one, Enter |
| `library.duplicates` `Mod+Alt+Y` | opens the Duplicates view and starts the search |

The Duplicates view lists groups under three headings (the kinds in P10-A5), each design with its picture, folder, size and date, and "Show in folder". There is no delete button (decision 4).

#### Track B tests

| Test (file) | Proves |
| --- | --- |
| `a thousand designs draw fewer than 80 cards` (`components/library/LibraryGrid.dom.test.tsx`) | windowing |
| `scrolling asks for the next 200`; `thumbnails are asked only for designs in view` | paging |
| `the last browse folder becomes the first library folder` (`feat/library.test.ts`) | first run |
| `filters become the engine's filter`; `fits my hoop uses the chosen hoop` | query |
| `a scan loops until finished and stops when told` | scan loop |
| `double-click opens the design`; `Add adds it to the open design`; `tagging two designs is one call` (`components/library/LibraryDialog.dom.test.tsx`) | actions |
| `groups show their kind and likeness`; `there is no delete button` (`components/library/DuplicatesView.dom.test.tsx`) | decision 4 |
| `the three commands are registered with their reserved shortcuts` (`cmd/library.test.ts`) | registry |

---

### Track C: thumbnails in the file manager — Hard

**Owns:** `apps/thumbs/**`, `scripts/build_thumbs.py`, the `build:thumbs` script in the root `package.json`, `apps/desktop/src-tauri/src/thumbs.rs` and its two lines in `lib.rs`, `src-tauri/Cargo.toml`, `tauri.windows.conf.json`, `tauri.linux.conf.json`, `installer/hooks.nsh`, the thumbnail steps in `.github/workflows/ci.yml` and `release.yml`, the rust stage's skip rule in `scripts/check.py`, the `preview.png` part of `engine/threadline_engine/project.py`, the Explorer switch in `components/SettingsDialog.tsx`, new tests.

#### P10-C1 The crate

`render(bytes, kind, size, background)` returns `size × size` RGBA: the design's stitch lines in its thread colors, fitted with a 6% margin. Each reader is a port of the matching pyembroidery reader (`PecReader`, `JefReader`, `DstReader`; MIT, credited in a comment) cut down to stitches, color breaks and colors. PES colors come from the machine palette index, JEF from Janome's table; DST has none, so its color blocks cycle through six fixed threads. `.ludd` is a zip: read only `preview.png` through a reader that seeks (no whole-file read), decode it and scale it; a project without one draws the LUDD mark.

**Safety rules, each with a test:**

- `#![forbid(unsafe_code)]` everywhere but `win.rs`.
- No `unwrap`, `expect` or indexing that can panic in a reader; all arithmetic on file values is checked or saturating.
- Every count read from a file is clamped: 2,000,000 stitches, 1,000 colors, 32 MB read from a stitch file.
- Drawing stops after 400,000 line segments (longer designs draw every nth), so no file can hold the host.
- Every COM method and export catches a panic and returns a failure code.
- The crate opens no file and no network connection: it reads the stream it is handed and nothing else.

Dependencies: `windows` (Windows only), `zip` (deflate only), `png`. All MIT or Apache; `scripts/make_notices.py` is run again.

#### P10-C2 Windows

`win.rs` implements `IThumbnailProvider` with `IInitializeWithStream`. Taking the file as a stream is what lets Windows run the handler in its own helper process instead of inside Explorer; `DisableProcessIsolation` is never set. `GetThumbnail(cx)` clamps `cx` to 16–1,024 and returns a 32-bit bitmap with alpha. The class id is generated once, written into `apps/thumbs/README.md` and `DECISIONS.md`, and never changed.

Turning it on is the app's job, not the installer's (`src-tauri/src/thumbs.rs`, commands `explorer_thumbnails_status` and `explorer_thumbnails_set`). On start, if the setting is on:

1. Copy the bundled DLL to the app's local data folder as `thumbs/ludd_thumbs_<first 8 of its sha256>.dll` if that copy is missing. Explorer may hold the copy open; it never holds the installer's own file, so updates are not blocked. Older copies are deleted when they can be.
2. Write under `HKCU\Software\Classes` only: `CLSID\{id}\InprocServer32` = that path, `ThreadingModel = Apartment`; `.ludd\ShellEx\{e357fccd-a995-4576-b01f-234630154e96}` = `{id}`; and for each chosen stitch format, `SystemFileAssociations\.<ext>\ShellEx\{e357fccd-…}` = `{id}`, but only if no other handler is registered for that format in any of the three places Windows looks (decision 2), unless "take over" is on.
3. Tell the shell associations changed.

Turning it off removes exactly the keys it wrote. `installer/hooks.nsh` removes the same keys and the copied DLLs on uninstall. Settings gains "Show design thumbnails in Windows Explorer", a list of formats, a note naming any format another program owns, and the take-over tick.

#### P10-C3 Linux

The `.deb` installs `/usr/bin/ludd-thumbnailer`, `/usr/share/thumbnailers/ludd.thumbnailer` (`Exec=ludd-thumbnailer %i %o %s`) and `/usr/share/mime/packages/ludd-embroidery.xml` (types for `*.ludd`, `*.pes`, `*.jef`, `*.dst`). The AppImage cannot install these (L-061).

#### P10-C4 A preview inside every project

`project.save` adds `preview.png` to the zip: the design on white, 256 px, from `library.thumbs.png_bytes`. An autosave has none. If the design cannot be drawn, the save goes ahead without one. Opening ignores it. Older LUDD versions open such a project as before, so no feature flag.

**Build and CI.** `pnpm build:thumbs` builds the crate in release mode and copies `ludd_thumbs.dll` (Windows) or `ludd-thumbnailer` (Linux) into `src-tauri/binaries/` (already git-ignored). The platform config files name them as resources. CI gains a job that runs the crate's tests on Windows and Linux; the Windows installer job and the release workflow run `pnpm build:thumbs` before the app is built. Actions stay pinned by commit, as D-014 says.

#### Track C tests

| Test (file) | Proves |
| --- | --- |
| `pes_renders`, `jef_renders`, `dst_renders` (`apps/thumbs/tests/render.rs`) | not blank; colors as expected; on `samples/Flower.pes`, `Flower.jef` and a DST made from it |
| `ludd_uses_its_preview`, `ludd_without_a_preview_draws_the_mark` | P10-C4's reader |
| `output_is_exactly_the_asked_size` | 16, 256, 1,024 |
| `every_truncation_is_survived` (`tests/hostile.rs`) | each prefix of each sample: an error or a picture, never a panic |
| `random_bytes_never_panic_or_hang` | 10,000 cases, each under 50 ms |
| `huge_counts_are_clamped`, `a_zip_bomb_preview_is_refused` | limits |
| `cli_writes_a_png` (`tests/cli.rs`) | the Linux thumbnailer command |
| `com_provider_returns_a_bitmap` (`tests/com.rs`, Windows only) | loads the DLL, creates the class, gives it a memory stream, asks for 256 px |
| `keys_are_all_under_hkcu`, `another_programs_handler_is_left_alone`, `turning_off_removes_what_was_written` (`src-tauri/src/thumbs.rs`) | on the pure plan of registry writes; CI writes no registry |
| `test_save_writes_a_preview`, `test_autosave_has_none`, `test_a_design_that_cannot_be_drawn_still_saves`, `test_open_ignores_the_preview` (`engine/tests/test_project_preview.py`) | P10-C4 |
| `the switch shows formats another program owns` (`components/SettingsDialog.dom.test.tsx`) | Settings |

---

### Track D: thread inventory and shopping list

**Owns:** `engine/threadline_engine/threads.py`, the `threads.my_set` and `threads.save_list` bodies, `MyThreadsTab` in `components/ThreadDialogs.tsx`, `components/InventoryDialog.tsx`, `feat/inventory.ts`, `feat/shoppingList.ts`, `cmd/inventory.ts`, exporting `esc` from `print.ts`, the "A full spool holds about" field in Settings' threads part (if Settings has none, in the inventory dialog), new tests.

#### P10-D1 How much is left

Each spool in My threads gains `left`: full, half, low or out (missing means full). `threads.my_set` changes it for spools already owned; anything else is refused in plain words. Adding a spool that is already owned keeps its amount. My threads shows four small buttons per spool and a "Low or out" filter.

#### P10-D2 Inventory and shopping list

`Mod+Alt+S` opens a dialog with two tabs.

**For this design.** One row per thread: swatch, name, brand and number, "needs about 38 m" (from `estimate(design, machine).perThread`), what you have, and a status.

| Status | Rule |
| --- | --- |
| OK | you own it and it is enough |
| Low | you own it, but the need × 1.15 is more than what is left |
| Out | you own it and it is marked out |
| Missing | you do not own it |

"Own" means the same brand and number; for a thread with no number, a spool whose color is within 3 (CIEDE2000, from `threads.match` against My threads). What is left = the spool size (a setting, 500 m to start) × 1.0, 0.5, 0.15 or 0. A line for bobbin thread follows (a third of the top thread).

**My spools.** My threads with the four-step control and the "Low or out" filter: the list to shop from whatever the design.

**Shopping list** = the Low, Out and Missing rows (or, on My spools, the low and out spools). Buttons: Copy, Save as CSV…, Save as text…, Print. Saving goes through `threads.save_list` (the window cannot write files): CSV is UTF-8 with a byte-order mark so spreadsheets read accents; the extension is added if missing; at most 5,000 rows; written through a temporary file. Print uses the same hidden-frame method as the thread list, every value escaped.

#### Track D tests

| Test (file) | Proves |
| --- | --- |
| `test_amount_defaults_to_full`, `test_setting_an_amount_keeps_the_spool`, `test_a_bad_amount_is_refused`, `test_adding_an_owned_spool_keeps_its_amount` (`test_threads_inventory.py`) | P10-D1 |
| `test_csv_has_a_bom_and_a_header_row`, `test_extension_is_added`, `test_a_folder_as_destination_is_refused`, `test_over_5000_rows_is_refused` | `threads.save_list` |
| `a thread with a number matches that brand and number`; `a thread without one matches by color within 3` (`feat/inventory.test.ts`) | owning |
| `missing, out and low all reach the list`; `a full spool covers a small design`; `a low spool does not cover a big fill`; `bobbin thread is a third` | status rules |
| `the list saves as rows of plain text` (`feat/shoppingList.test.ts`) | CSV rows; print HTML is escaped |
| `the four steps set the amount` (`components/InventoryDialog.dom.test.tsx`) | UI |
| `threads.inventory is registered with its reserved shortcut` (`cmd/inventory.test.ts`) | registry |

## 8. Integration (session lead)

1. Merge A, D, B, then C (C last: it changes workflows and the installer). Run `python scripts/check.py`.
2. `python scripts/kb_commands.py` (four new commands), then `--check`.
3. `cargo test --locked --manifest-path apps/thumbs/Cargo.toml`, then `pnpm build:thumbs`.
4. `pnpm build:engine`: the frozen engine must load `sqlite3` and the `library/` package. Add `library.roots` to what `scripts/smoke_engine.py` calls.
5. `python scripts/check.py --all`.
6. The installer is built by CI, not on this PC (the local NSIS step is known to fail here). After the owner pushes: install the CI artifact, open the samples folder in Explorer, check thumbnails for `.ludd`, PES and JEF, turn the switch off and on, uninstall and confirm the registry keys are gone.
7. Docs (section 9). Record the class id and decisions 1 to 4 in `DECISIONS.md` under the next free numbers. Then the stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**`docs/CHANGELOG.md`**, under the current unreleased heading:

```
### Phase 10: design library, thumbnails, thread inventory (YYYY-MM-DD)
- **Design library** (Ctrl+Alt+B) replaces Browse designs: add your design folders once; LUDD remembers each design's picture, size, colors and stitch count, so opening the library again is instant, with no 600-design limit.
- **Find and filter** (Ctrl+F): by name, by what fits your hoop, by colors, stitches and format. **Tags** (Alt+G) and **collections** stay with a design even if you rename or move it.
- **Find duplicate designs** (Ctrl+Alt+Y): exact copies, the same design in another format, and look-alikes. LUDD only shows them; it never deletes anything.
- **Thumbnails in Windows Explorer** for LUDD projects and PES, JEF and DST files (Settings turns them off). On Linux, the .deb adds them to the file manager.
- **Thread inventory and shopping list** (Ctrl+Alt+S): mark each spool full, half, low or out; see what the open design needs and what to buy; save or print the list.
```

**`docs/LUDD-KNOWLEDGE-BASE.md`:** new section 28 "Design library" with `F-2301` Library (tags, collections, filters), `F-2302` Duplicate finder, `F-2303` Thumbnails kept between sessions, `F-2304` Thumbnails in Explorer and file managers. New `F-1609` Thread inventory and shopping list in section 14. `F-207` Browse designs is marked superseded by `F-2301` (not deleted). Update `F-1604` (spool amounts), `F-203` (a project carries a preview picture), `F-2101` (the Explorer switch). Section 1: the data folder gains `library`. Section 2 index: a row per new entry. History row; *Last updated*; section 25 from the script.

| ID | Entry |
| --- | --- |
| L-060 | No thumbnails in Finder on a Mac: it needs a signed extension (see L-015) |
| L-061 | On Linux, file-manager thumbnails come with the .deb, not the AppImage |
| L-062 | Explorer thumbnails cover LUDD projects, PES, JEF and DST; other formats show in LUDD's library. Colors are the machine palette's, so they can be a shade off |
| L-063 | The duplicate finder shows and opens folders; it does not delete or move files |
| L-064 | Spool amounts are four steps, not measured meters |
| T-047 | No thumbnails in Explorer: the Settings switch; Explorer's "Always show icons, never thumbnails"; another program owns that format; clear Windows' thumbnail cache |
| T-048 | A design is missing from the library or shown twice: Refresh the folder; removed drives; Rebuild the library |
| T-049 | Tags vanished after a design was edited in another program: tags follow the file's contents, so a changed file is a new design |
| T-050 | The shopping list says a thread I own is missing: it has no number and its color is not close enough; add the spool from its brand chart |

**`docs/USER-MANUAL.md`:** section 2 (the library replaces Browse designs), section 9 (inventory), section 11 (the Explorer switch). **`ai/helpdocs.py`:** the same, with the shortcuts.

**`docs/stitchout-log.md`:** no rows. Nothing in this phase changes stitches.

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| The thumbnail handler misbehaves on someone's PC | Explorer slow or its helper process crashing on a folder | The Settings switch removes it at once. If it happens in testing, ship with the switch off by default and say so in the release notes. |
| Antivirus dislikes an unsigned DLL copied into the user's data folder and registered | the copy is quarantined; thumbnails vanish | Register the installer's own file instead and let `hooks.nsh` unregister before an update; record which was shipped. Signing (D-009) is the real fix. |
| Tauri's config keys differ from the three named in Preflight | the build rejects the config | Use what the Tauri 2 docs say. If the Windows resource cannot be platform-specific, ship the DLL through `externalBin`'s folder and copy from there. |
| sqlite is locked between a scan and a query | `database is locked` | One writer lock and WAL are specified; if it still happens, queries retry for up to 2 seconds. |
| The first scan of a big folder is slow (each design is read once) | 1,000 real designs take minutes | Expected the first time; the count and Stop are there. The 2-second promise is for the second open. |
| Look-alike groups are wrong | unrelated designs grouped | Raise the 92% bar; groups are advice only. |
| Track C fills the session | time or context runs out | Merge A, B and D, stop, and run Track C as its own session from the same branch. P10-C4 (the preview in `.ludd`) is small and can go with the others. |

## 11. Handoff

Write in `HANDOFF.md`: test counts before and after; whether `pnpm build:thumbs` and `pnpm build:engine` ran; which parts of integration step 6 the owner still has to do by hand; the answers to the four decisions; which way the DLL was registered (copied, or the installer's own file); any spec deviation, one line each.
