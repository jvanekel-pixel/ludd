# Phase 12: Machines, threads & languages

| | |
| --- | --- |
| Weight | Light for tracks A, B and D (mostly data). Track C is the largest track in the whole plan by places touched: about 1,200 strings in about 70 files. |
| Session lead | Sonnet 5.5. Data entry (machine profiles) may go to Haiku 5.5 only under the accuracy rules in Track A. |
| Audit | Top model spot-checks five machine profiles against the manual each one names, and reads the pseudo-language test output. |
| Depends on | Phase 3. If Phase 11 is built, its hints and troubleshooting are extended and translated here. |
| Changes stitches | No. |
| Closes (compendium) | Hoop library by machine (was Partial) · Brand thread charts · Thread weight guidance · Multi-needle color-to-needle assignment · Machine setup advice · Translations. Lifts `L-018`. Closes the BACKLOG item "project, fabric and thread-chart JSON Schemas". |
| Refresh first | Yes. Written against `main` at d39bbb5, months before the build. Do section 4 in a planning chat first. |

## 1. Goal and done-when

LUDD knows two machines and two thread brands, and speaks one language. This phase lets someone with a Brother, Baby Lock, Janome, Bernina, Husqvarna Viking, Pfaff or Singer find their machine by typing its name, match colors to the four thread brands hobbyists buy most, and read the app in their own language. Because a wrong hoop size ruins a stitch-out, every machine fact names the manual it came from.

**Done when:**

1. Typing a model name finds a profile for each brand above. Every built-in profile names its source; one not checked against a manual says so on screen.
2. A machine with more than one needle gets a color-to-needle plan, printed on the run sheet.
3. Four more thread brands are in Match threads, offline (if owner decision 1 allows).
4. The whole app runs in a second language. The pseudo-language test finds no bare English, and a language cannot be chosen until it is complete.
5. Three new schemas validate every sample project and every built-in data file, and the project schema's feature list equals `project.KNOWN_FEATURES`.
6. `python scripts/check.py --all` passes, and `pnpm build:engine`'s smoke check finds the data files inside the frozen engine.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P12-S1 | Data folders in the engine package, bundling, shared types and keys | No | Step 0 |
| P12-A1 | Machine profiles as one JSON file each, with `source` and `verified` | No | A |
| P12-A2 | Choose your machine from a searchable list (`machine.pick`, Alt+M) | Yes | A |
| P12-A3 | The first set of machines, entered from manuals | Yes | A |
| P12-A4 | Assign colors to needles (`threads.needles`, Alt+Shift+N), on the run sheet | Yes | A |
| P12-A5 | Machine setup advice: needle for the fabric, on screen and in print | Yes | A |
| P12-B1 | Thread chart data files, the converter that made them, credits | No | B |
| P12-B2 | Charts load on first use; each has a thread weight | Yes | B |
| P12-B3 | Thread-weight guidance (40 assumed; what to change for 60 and 30) | Yes | B |
| P12-C1 | `t()` helper, string harvest script, pseudo-language test | No | C |
| P12-C2 | Every UI string goes through `t()` | No | C |
| P12-C3 | Every engine message is a template the UI can translate | No | C |
| P12-C4 | Language choice in Settings; catalogs for the first languages | Yes | C |
| P12-C5 | The in-app guide in each language | Yes | C |
| P12-D1 | `schemas/project.schema.json`, `fabric.schema.json`, `thread-chart.schema.json` | No | D |
| P12-D2 | Schema tests, and a check that the TypeScript types agree | No | D |
| P12-Z1 | Guide sections, docs, frozen-engine check, handoff | – | Integration |

**Out of scope:** translating the user manual and the knowledge base; right-to-left languages; a screen for editing machine profiles (a JSON file in the data folder stays the advanced way); closed formats (Bernina ART); sending to a machine; thread inventory (Phase 10); re-spacing stitches for thread weight (guidance only).

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Thread charts: adapt Ink/Stitch's palette files (GPL, credited; `D-005` allows it)? | Yes. The other way is today's "import your own CSV". No chart of unknown license is ever committed (`.gitignore` already blocks loose CSVs). | Track B builds B2 and B3 only and ships no new chart. |
| 2 | Which languages first, and who checks them? | Two: Spanish and German. Machine-drafted, then read by a speaker before the language is switched on. | C1 to C3 only: the app becomes ready to translate and stays English. |
| 3 | Which machines first? | The table in Track A (about 30). Add any a friend owns. | That table. |
| 4 | A profile nobody could check against a manual: ship it marked, or leave it out? | Ship it marked "check this against your manual". | Ship marked. |
| 5 | A new test-only Python package, `jsonschema`? | Yes. It is in the `dev` group with pytest, never in the installer. | A small hand-written checker for the keywords the four schemas use. |
| 6 | `D-015` says "revisit US spelling if the app is localized". | Keep US English as the source text; no UK variant. | Keep. |

## 4. Refresh this spec first (preflight)

| Check | Command | Expect, or what to change |
| --- | --- | --- |
| Built-in machines | `grep -n "\"id\":" engine/threadline_engine/profiles.py` | `brother-pe550d`, `janome-generic`. These ids, and hoop ids `4x4`, `sq14`, `a`, `re20b`, `sq20b`, are in saved settings and must never change. |
| Schemas so far, and profile keys added since | `ls schemas`; `cat schemas/machine.schema.json` | only the machine schema; it has gained `speed_spm` (PR #23) and, if Phase 8 is built, hoop positions. Keep them. |
| The project's manifest | `grep -n "MAX_MEMBER_BYTES\|VERSION =\|KNOWN_FEATURES" engine/threadline_engine/project.py` | the member is `project.json`; note the version and the feature names as they are now |
| Formats LUDD writes | `grep -n "Saves for machines" docs/LUDD-KNOWLEDGE-BASE.md` | includes EXP, VP3, XXX |
| How the engine is frozen | `grep -n "add-data\|collect" scripts/build_engine.py` | Step 0 adds the data folder the same way |
| Engine error shape | `grep -n "def _error" engine/threadline_engine/rpc.py` | `{code, message}`; C3 adds `data` |
| Ink/Stitch palettes | open its `palettes/` folder upstream | which of Madeira, Isacord, Robison-Anton and Sulky exist, their file format, the license that covers them. Decision 1 rests on this. |
| How many strings | UI: `grep -rhoE ">[[:space:]]*[A-Z][^<>{}=]{2,}<" apps/desktop/src --include=*.tsx \| wc -l` and the same idea for `title=`, `label=`, `aria-label=`, `placeholder=`, `info(`, `fail(`. Engine: `grep -rhoE "raise [A-Za-z]+Error\(" engine/threadline_engine \| wc -l` | On 2026-11-24: about 430 in markup and attributes, 260 labels and titles in data (167 command titles), 125 notices; about 850 to 900 in 45 UI files. Engine: 215 raises, 35 warnings, 8 checks of three sentences, about 300 in 25 files. The guide is about 5,000 words. Phases 4 to 11 will have added to all of these: count again and size the sessions. |
| Phase 11 | `git ls-files apps/desktop/src/design/hints.ts apps/desktop/src/feat/troubleshoot.ts` | if present, C2 wraps them and A5 adds its advice to the troubleshooting data |
| Reserved keys | `grep -nE "\| \`(Alt\+M\|Alt\+Shift\+N)\` \|" docs/LUDD-KNOWLEDGE-BASE.md` | no match |

## 5. Architecture

### 5.1 New files

- In `engine/threadline_engine/`: `data/machines/<id>.json` (one machine each), `data/threads/<id>.json` (one chart each) with `data/threads/index.json` (id, name, brand, weight and count, so listing reads one small file), `datafiles.py` (finds the data, frozen or not), `messages.py` (`msg()`, `msgn()`), `ai/helpdocs_<code>.py` (the guide in another language).
- In `schemas/`: project, fabric and thread-chart. In `scripts/`: `i18n_extract.py`, `import_inkstitch_palettes.py`.
- In `apps/desktop/src/`: `i18n.ts`, `locales/` (`template.json`, `<code>.json`, `<code>.meta.json`), `feat/needles.ts`, `cmd/machines.ts`, `components/MachineDialog.tsx`, `components/NeedlesDialog.tsx`.

### 5.2 A machine profile

```json
{ "id": "brother-pe550d", "name": "Brother PE550D", "brand": "Brother", "aliases": [], "formats": ["pes"], "needles": 1,
  "cuts": "color_change", "hoops": [{ "id": "4x4", "name": "4\" × 4\" (10 × 10 cm)", "width_mm": 100, "height_mm": 100 }],
  "notes": "Cuts only at the end of each color.", "source": "Brother Operation Manual 888-M36, p. 26", "verified": true }
```

New keys: `source` (text, required for built-ins), `verified` (true only when read from the maker's manual or specification), `aliases` (other model names a search should find). Profiles in the user's data folder keep working without them.

### 5.3 Languages: English is the key

`t("Open a design…")` returns the sentence in the chosen language, or the English it was given. There are no invented key names: the English text is the key, so wrapping a string is mechanical and the app reads the same until a catalog exists. A note for translators goes after a bar and is never shown: `t("Fill|the stitch type")`. Values go in braces: `t("{n} stitches", { n })`. Plurals use `tn(one, other, n)` and the browser's own `Intl.PluralRules`. No package is added. Text held as data (command titles, pattern labels, hints) stays plain English in the source, so `kb_commands.py` and the knowledge base are untouched; it passes through `t()` where it is shown.

Engine messages: `msg("Fill spacing must be between {lo} and {hi} mm", lo=0.2, hi=5)` is a `str` that also carries its template and values. Raised in an error it reads as today (every existing test still passes); `rpc._error` adds `data: {template, params}`. Warnings and checks gain a `message_t` beside `message`. A value may itself be a message (`"{name}: {text}"`). The UI translates the template and puts the values back; with no translation it shows `message`. Catalogs are JSON bundled with the app and loaded on demand. Nothing is downloaded.

### 5.4 Needle plan

`assignNeedles(blocks, needles, pins)`: colors take needles in order of first use; a thread that comes back keeps its needle; when every needle is taken, the one whose thread is needed latest (or never again) is re-threaded, which gives the fewest stops. The user can pin a thread to a needle. Only pins are saved, in the layout as `needles: { "<thread key>": 3 }`. The plan is shown and printed; it never changes the machine file, so an older LUDD opens the project and sews it the same (no feature flag).

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-12/machines-threads-languages`.
2. Create `engine/threadline_engine/data/` with empty `machines/` and `threads/`, and `datafiles.py` (reads through `importlib.resources`). Bundle the folder in `scripts/build_engine.py`; `scripts/smoke_engine.py` asks the frozen engine for `machines.list` and fails on an empty answer.
3. `schemas/machine.schema.json`: add `source`, `verified`, `aliases` as optional keys (tracks A and D both read it).
4. `design/types.ts`: `Machine.source?`, `verified?`, `aliases?`; `ChartSummary.weight?`; `Layout.needles?`; `Fabric.needle?`. `prefs.ts`: `language?`. `store.ts`: `language`. `cmd/index.ts`: one import; create `cmd/machines.ts` empty.
5. Commit. Wave 1 branches from here.

## 7. Tracks

**Wave 1** runs A, B and D together. **Wave 2** is C alone, after wave 1 is merged: it edits nearly every UI and engine file, so nothing else may be in flight, in this session or another. Worker rules are in `BUILDPLAN.md`. Workers do not edit the guide (`ai/helpdocs.py`); the session lead writes it from section 9.

---

### Track A: machines and hoops

**Owns:** `engine/threadline_engine/profiles.py`, `data/machines/**`, `fabrics.py`, `schemas/machine.schema.json` (after Step 0), `components/MachineDialog.tsx`, `components/NeedlesDialog.tsx`, `MachinePicker` in `components/Toolbar.tsx`, the machine block of `SettingsDialog.tsx` and of the welcome card in `App.tsx`, `feat/needles.ts`, `cmd/machines.ts`, `print.ts`, `engine/tests/test_machines.py`.

#### P12-A1 Profiles as data
`BUILTIN_MACHINES` becomes the files in `data/machines/`, read once and cached; `_validate` gives each the defaults it gives today. The two existing profiles move unchanged. `list_machines()` still lets a user file with the same id replace a built-in.

#### P12-A2 The list
`MachinePicker` becomes a button with the machine's name, and the hoop choice beside it as now. The button opens **Choose your machine** (`Alt+M`): a search box that matches brand, model and other names in any order; results grouped by brand; the chosen machine's hoops; its file type and whether it cuts jump threads, in a sentence. A profile with `verified: false` shows "Not checked against the manual. Check the hoop size against yours." At the foot: "Not listed? Pick one with your hoop size and file type, or add your own" (opens Help at the profile-file section).

#### P12-A3 The first machines
**Accuracy rules.** These are for whoever enters the data, person or model.

1. A value comes only from the maker's manual or published specification for that model. `source` names the document and page, or the maker's page and the date it was read.
2. `width_mm` and `height_mm` are the sewing field, not the hoop's outside.
3. `cuts` is `trim` only when the manual says the machine cuts jump threads by itself. When the manual does not say: `color_change` and `verified: false`. (Wrongly saying `trim` leaves threads on the fabric; wrongly saying `color_change` only offers cut-stops nobody needed.)
4. Anything from a shop page, a forum or memory is `verified: false`, and `source` says where it came from.
5. Never fill a value from memory. A machine whose manual cannot be found is left out and named in the worker's report.
6. A sibling model goes in `aliases` only when its own manual was read and agrees on every value.

Starting list. Confirm each model still exists; every number comes from its manual at build time, none from this table.

| Brand | LUDD saves | Models to cover first |
| --- | --- | --- |
| Brother | PES | PE535, PE550D (have), SE600, SE630, SE700, PE770, PE800, PE900, SE1900, SE2000, NQ1700E; PR680W and PR1055X (multi-needle) |
| Baby Lock | PES | the single-needle embroidery models sold now; Array and Valiant (multi-needle) |
| Janome | JEF | Memory Craft 400E, 500E, 550E, with their real hoops (the generic profile stays); MB-4Se and MB-7 (multi-needle) |
| Bernina | EXP | 500 E, 535, 570 QE E, 590 E, 700 E, 770 QE E, 790 PRO |
| Husqvarna Viking | VP3 | Jade 35, Designer Topaz 50, Designer Ruby 90 |
| Pfaff | VP3 | creative 1.5, creative 4.5, creative icon 2 |
| Singer | XXX | Futura XL-400 and XL-580, Legacy SE300 |

#### P12-A4 Needles
`Alt+Shift+N`, enabled when the machine has more than one needle (otherwise a notice: "Your machine has one needle, so it stops for every color."). The dialog lists needle → thread, lets a thread be pinned to a needle, and lists any re-threading ("Before color 9: put Navy on needle 3"). The run sheet gains a Needle column and a "Before you start" list.

#### P12-A5 Setup advice
Each fabric preset gains `needle` (size and point for that fabric with 40-weight thread), shown with the stabilizer advice and printed on the run sheet. The values come from a needle maker's published guide, named in a comment. If Phase 11 is built, the machine-side causes of thread breaks (thread path, needle, tension, then the design) are added to `feat/troubleshoot.ts`.

#### Track A tests

| Test (file) | Proves |
| --- | --- |
| `test_every_builtin_profile_is_valid_and_sourced` (`test_machines.py`) | passes `_validate`; `source` not empty; `verified` is true or false |
| `test_ids_are_unique_and_the_old_ones_remain` | the two machine ids and five hoop ids in the preflight |
| `test_every_machine_has_a_format_ludd_writes` | against `design.formats()["write"]` |
| `test_a_user_profile_still_replaces_a_builtin` | and needs no `source` |
| `test_unverified_never_claims_trim` | rule 3 |
| `search finds a machine by brand, model or other name` (`components/MachineDialog.dom.test.tsx`) | words in any order; an unverified profile shows the warning |
| `a thread that comes back keeps its needle` (`feat/needles.test.ts`) | and a pin is kept and saved with the project |
| `with more colors than needles the fewest re-threads are planned` (same) | 8 colors, 6 needles, a fixed case |
| `the run sheet shows needles only for a multi-needle machine` (`print.test.ts`) | |

---

### Track B: thread charts

**Owns:** `engine/threadline_engine/threads.py`, `data/threads/**`, `scripts/import_inkstitch_palettes.py`, the chart list and picker notes in `components/ThreadDialogs.tsx`, the credit lines gathered by `scripts/make_notices.py`, `engine/tests/test_thread_charts.py`.

#### P12-B1 Data
`scripts/import_inkstitch_palettes.py <folder>` is a developer's tool: it reads palette files from a local copy of Ink/Stitch and writes one JSON per chart plus `index.json`. The app and the tests never run it and never fetch anything; the JSON files are what is committed. Each chart carries `source`, `license` and `weight`. Ids start with `lib-` (`lib-isacord-40`), so they cannot collide with a chart the user imported earlier under the brand's plain name. Ink/Stitch's copyright notice goes into the third-party notices, with one more line: thread names and numbers belong to their makers, and colors on screen are approximate.

Charts: the 40-weight lines of Madeira (Polyneon, Rayon), Isacord, Robison-Anton (polyester, rayon) and Sulky (rayon), as far as upstream has them.

#### P12-B2 Loading
`list_charts()` reads `index.json` only. A chart's threads are read the first time it is opened or matched against, then cached: engine start-up must not slow down. The two pyembroidery palettes stay as they are.

#### P12-B3 Thread weight
A chart whose `weight` is not 40 says so in the picker, in LUDD's own controls: thinner thread (60) covers less, so use Dense for fills and a finer needle; thicker thread (30) covers more, so use Light and a larger needle. The needle sizes come from the thread maker's sheet, named in a comment. LUDD does not re-space stitches for weight by itself (`L-074`).

#### Track B tests

| Test (file) | Proves |
| --- | --- |
| `test_index_matches_the_chart_files` (`test_thread_charts.py`) | ids, names and counts; every chart has `source`, `license` and `weight` |
| `test_listing_reads_no_chart_file` | patch the loader; `list_charts()` opens only the index |
| `test_a_user_chart_with_the_brand_name_is_not_hidden` | import "Isacord" by CSV; both are listed |
| `test_match_works_against_a_library_chart` | nearest thread to `#ff0000` has a code |
| `test_palette_converter_reads_a_sample_file` | a three-color palette written in the test |
| `a 60-weight chart shows the note` (`components/ThreadDialogs.dom.test.tsx`) | |

---

### Track D: schemas

**Owns:** `schemas/project.schema.json`, `schemas/fabric.schema.json`, `schemas/thread-chart.schema.json`, `engine/tests/test_schemas.py`, `apps/desktop/src/design/schema.test.ts`, the `dev` group in `engine/pyproject.toml` and `engine/uv.lock`.

The schemas describe what is saved; they do not replace the engine's own checks in `open_project`, which stay the reference at run time. Draft 2020-12, the same `$id` pattern as the machine schema (an identifier only; nothing fetches it).

- **Project:** the `project.json` manifest as `project._pack` writes it: format, version, `features` (an enum equal to `KNOWN_FEATURES`), the layout, its items (`oneOf` by `kind`), pictures, embedded fonts. `required` is strict; unknown extra keys are allowed everywhere, so a newer project does not fail an older schema.
- **Fabric:** one preset as in `fabrics.FABRICS`. **Thread chart:** one chart file, color as `#rrggbb`.

**TypeScript types are not generated from the schemas.** The types carry comments and unions the schemas cannot, and a generator is one more tool to keep working. Instead `design/schema.test.ts` builds a layout, one item of every kind and a picture with the app's own constructors, and checks, with no validator package, that every key they hold is declared for that kind and every required key is there.

#### Track D tests

| Test (file) | Proves |
| --- | --- |
| `test_each_schema_is_a_valid_schema` (`test_schemas.py`) | all four |
| `test_every_sample_project_validates` | each `samples/*.ludd` manifest |
| `test_a_project_with_one_of_everything_validates` | saved by `project.save` in the test |
| `test_feature_enum_equals_known_features` | so a later phase that adds a flag must add it here |
| `test_builtin_fabrics_charts_and_machines_validate` | includes a chart written by `import_csv` |
| `test_bad_data_is_refused` | a fill with no outline; a color `red`; a hoop 0 wide |
| `the app's own objects fit the project schema` (`design/schema.test.ts`) | the agreement check above |

---

### Track C (wave 2, alone): languages

**Owns:** `apps/desktop/src/i18n.ts`, `locales/**`, `scripts/i18n_extract.py`, `engine/threadline_engine/messages.py`, the error shape in `rpc.py`, an `i18n` stage in `scripts/check.py`, the Language row in `SettingsDialog.tsx`, `ai/helpdocs_<code>.py`, and then every file with a string a user reads.

**Order of work.** Each step ends green, and the app never shows two languages at once.

1. **C1.** `i18n.ts` (`t`, `tn`, `setLanguage`, `LANGUAGES`); `i18n_extract.py`, which harvests `t(…)`, `tn(…)`, command titles, descriptor labels, hints and engine `msg(…)` templates into `locales/template.json`, and with `--check` fails when the template is stale or a catalog lacks a key or changes its `{values}`. The pseudo-language: `setLanguage("zz")` wraps every string as `⟦…⟧`.
2. **C2.** Wrap UI strings file by file until the pseudo-language test is green. English only; nothing looks different; no existing test changes.
3. **C3.** Engine messages become `msg()` / `msgn()` until the source scan is green. Existing engine tests pass untouched, because the English is the same.
4. **C4.** Draft the catalogs. Add Language to Settings: "Same as my computer" and each complete language.
5. **C5.** The guide in each language: same sections, same shortcuts.

A language is offered only when all three hold: its catalog has every key with the same `{values}`; its guide exists; a speaker has read it (`locales/<code>.meta.json` has `"checked": true`, set by the owner). A test builds `LANGUAGES` from those facts. On Pro, C2 is two sessions (about 45 files) and C3 one.

#### Track C tests

| Test (file) | Proves |
| --- | --- |
| `t returns English with no catalog, fills values, drops the translator's note` (`i18n.test.ts`) | and `tn` follows the language's plural rule |
| `no bare English in the pseudo-language` (`i18n.pseudo.dom.test.tsx`) | renders the toolbar, tool rail, the panel for each kind of selection, and every dialog under `zz`; each text node, `title`, `aria-label` and `placeholder` is wrapped or on a short allow-list (numbers, units, "LUDD", thread and file names, keys). **This is the test that fails on a missing string.** |
| `every catalog has every key with the same values` (`python scripts/i18n_extract.py --check`, run by `check.py`) | |
| `a language without a checked catalog and a guide is not offered` (`i18n.test.ts`) | |
| `test_user_facing_messages_are_templates` (`engine/tests/test_messages.py`) | scans the engine's source: a `raise …Error("…")` or a string added to a warnings or checks list that is not `msg()` fails, apart from a short allow-list |
| `test_message_reads_the_same_and_keeps_its_parts` (same) | `str(msg(...))` equals today's sentence; nested messages keep their tree |
| `test_rpc_error_carries_the_template` (`test_rpc.py`) | `error.data.template` and `params` |
| `test_each_guide_has_the_same_sections_and_keys` (`test_help.py`) | per language |
| `an engine warning shows in the chosen language, or in English when untranslated` (`i18n.engine.test.ts`) | |

## 8. Integration (session lead)

1. Merge wave 1 in the order D, B, A. Run `python scripts/check.py`. Re-run D's tests: A's machine files and fabric `needle` values and B's charts must validate.
2. Write the guide sections from section 9 (wave 2 will wrap and translate them).
3. Start Track C from the merged branch. Stop after C2 or C3 if the session is long; each is a complete, shippable state.
4. `pnpm build:engine`: the smoke check must list more than two machines.
5. Docs (section 9), `python scripts/kb_commands.py`, `python scripts/check.py --all`. In the installed app: find a machine by typing; print a run sheet for a multi-needle machine; switch language and back without restarting.
6. Stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**`docs/CHANGELOG.md`:** a line per item in the user's words, ending "Nothing sews differently."

**`docs/LUDD-KNOWLEDGE-BASE.md`**, new section 30 "Machines": `F-2501` Machine list and hoops (how to search, what "not checked" means, adding your own) · `F-2502` Needle assignment · `F-2503` Machine setup advice (needle by fabric, thread breaks on the machine's side). Elsewhere: `F-1610` More thread charts and thread weight (section 14) · `F-2105` Languages (section 19). `L-018` is marked lifted by `F-2501`. Limits: `L-070` the manual and this knowledge base are English only. `L-071` Help search is tuned for English words. `L-072` a profile marked "not checked" may have the wrong hoop size or cutting behavior. `L-073` the needle plan is advice; the machine's own screen still decides. `L-074` thread weight is guidance; LUDD does not re-space stitches for it.

Troubleshooting: `T-055` "my machine isn't listed" → the closest hoop and file type, or your own profile. `T-056` "the hoop in LUDD is a different size from mine" → LUDD shows the sewing field; check the manual; report it. `T-057` "some words are still in English" → thread, file and font names always are; anything else is a bug to report. `T-058` "the matched thread looks different on the spool" → screens and thread differ; charts are approximate.

Also: section 1 rows "Machines built in" and "Saves for machines"; section 2 index rows; section 23; *Last updated*; section 25 by the script.

**`docs/USER-MANUAL.md`:** section 2 (choosing a machine), section 9 (charts, weight, needles), section 11 (Language). **`ai/helpdocs.py`** (session lead): "Choosing your machine and hoop", "Adding your own machine", "Needles for multi-needle machines", "Needle and thread for your fabric", "Thread weight", "Language".

**`AGENTS.md`:** its Layout paragraph says only the machine schema exists. With the owner's OK, the session lead changes that one sentence.

**`docs/stitchout-log.md`**, pending rows that need a machine the owner does not have (mark "needs a volunteer"):

| Milestone | Test | File | What to check |
| --- | --- | --- | --- |
| Phase 12 | EXP on a Bernina; VP3 on a Husqvarna Viking or Pfaff; XXX on a Singer | Key.PES saved in that format for a listed machine | Opens centered at the right size; colors, order and stops as that machine's manual says |
| Phase 12 | Needle plan on a multi-needle machine | A six-color design, the printed plan | The plan matches what the machine's own screen asks for |

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| A wrong hoop size or cutting claim | the audit's spot check, or a user report | The accuracy rules; `verified: false` and the on-screen note; a correction is a one-file change. |
| The palettes' license is not what this spec assumes | preflight row 7 | Decision 1's "if no answer" path: ship no chart, keep CSV import. |
| A half-translated app | English in the middle of another language | The three-part rule in Track C; the language stays hidden until all three hold. |
| English wording edited later orphans its translations | `i18n_extract.py --check` fails in that phase | Intended. That phase updates the catalogs or the language drops off the list until it does. |
| Longer words break the layout (German runs about 30% longer) | buttons clip under `zz` | The pseudo-language pads each string by 30%; fix the styles in C2, not the words. |
| Track C collides with other work | merge conflicts in dozens of files | It runs alone, last, and "two phases at once" is off while it runs. |
| Data files missing from the frozen engine | smoke check lists two machines or fails | Step 0's bundling line; never ship without the smoke check. |
| Engine messages built from pieces (plurals, optional clauses) | the source scan flags them | Rewrite as `msgn()` or two whole templates. Never translate fragments. |

## 11. Handoff

Write in `HANDOFF.md`: how many machines were entered, how many are unverified, and which were left out for want of a manual; which charts shipped; which of C1 to C5 are done and which languages are complete; the string counts measured. Tell every later phase: text a user reads goes through `t()` or `msg()`; a new project key or feature flag goes into `schemas/project.schema.json` in the same change; a new machine or chart file follows the accuracy rules and carries its source.
