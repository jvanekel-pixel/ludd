# Phase 11: Learnability

| | |
| --- | --- |
| Weight | Medium. Fine on Pro, one track per session. |
| Session lead | Sonnet 5.5. No hard track. |
| Audit | Top model reads the check output, then does the guided first design by hand in the installed app. |
| Depends on | Phase 3. Better after Phase 10 (pictures for recent designs) and Phase 12 (machine list), but needs neither. |
| Changes stitches | No. Nothing here may move a stitch or change a saved machine file. |
| Closes (compendium) | Beginner vs expert mode · Hint pane and F1 help · Guided first design · Startup wizard · Ghost mode · Show/hide by color · Snap to objects · Travel by object · Saved workspace layouts · Command palette and custom shortcuts |
| Refresh first | Yes. Written against `main` at d39bbb5, months before the build. Do section 4 in a planning chat before any build session. |

## 1. Goal and done-when

A steep learning curve is the most common complaint about every digitizer. LUDD already hides advanced settings in folds; this phase makes the app teach itself: one switch for how much it shows, a hint for whatever the pointer is on, a first design the user makes with their own hands, and help that opens at the right page.

**Done when:**

1. A new user picks their machine (from the list if Phase 12 is built, otherwise the two built in) and finishes the guided first design without the manual. The audit does this by hand; `tutorial.dom.test.tsx` does it in a test.
2. `F4` switches between Simple and Expert. Someone who used LUDD before this update opens it and sees the same panel as yesterday.
3. Every setting row in the shape panel has a hint; a test fails when one is missing.
4. `F1` opens Help at the section for the tool, mode or selection in use.
5. Hide, ghost mode, one color at a time, snap to shapes and travel by object pass their tests.
6. `Ctrl+K` finds and runs any command; a changed shortcut works and shows in menus and tooltips; a saved workspace comes back.
7. `python scripts/check.py --all` passes with no snapshot file changed.

## 2. Scope

| ID | Item | User sees it | Track |
| --- | --- | --- | --- |
| P11-S1 | Shared state, types, prefs keys, command files, method stubs | No | Step 0 |
| P11-A1 | Simple / Expert switch (`app.expert`, F4) | Yes | A |
| P11-A2 | Reset arrow beside a setting that is not at its standard value | Yes | A |
| P11-A3 | Hint text and pictures, written once (`design/hints.ts`) | Yes | A |
| P11-A4 | Hint pane (`app.hints`, F3) | Yes | A |
| P11-A5 | F1 opens Help at the right section; Help shows a contents list | Yes | A |
| P11-B1 | Start screen with recent designs (`app.start`, F9) | Yes | B |
| P11-B2 | Guided first design, two lessons (`app.tutorial`, Shift+F1) | Yes | B |
| P11-B3 | Troubleshooting by symptom (`app.troubleshoot`, Alt+F1) | Yes | B |
| P11-C1 | Hide, show and ghost mode (`view.hide`, `view.showAll`, `view.ghost`) | Yes | C |
| P11-C2 | Show one color, with a strip of color blocks (`view.soloColor`, F7) | Yes | C |
| P11-C3 | Snap new points to shapes' points and edges (`view.snapShapes`, F8) | Yes | C |
| P11-C4 | Travel by object in the player | Yes | C |
| P11-D1 | Find a command (`app.palette`, Mod+K) | Yes | D |
| P11-D2 | Change keyboard shortcuts (`app.shortcuts`, F10) | Yes | D |
| P11-D3 | Workspaces (`view.workspace`, Alt+W) | Yes | D |
| P11-Z1 | Docs, handoff | – | Integration |

**Out of scope:** video; a tour of every tool (one guided design, two lessons); docking or floating panels; translating the hints (Phase 12 wraps them); needle, threading and tension advice (Phase 12, `F-2503`); AI inside the tutorial.

## 3. Owner decisions

| # | Question | Recommendation | If no answer |
| --- | --- | --- | --- |
| 1 | Who starts in Simple? | New installs. Anyone who already used LUDD starts in Expert, so nothing they know disappears. | That. |
| 2 | Is a hidden shape still sewn? | Yes. Hiding is a view. Save for machine says "2 hidden things are part of this design" with a Show them button. | View only, with the note. |
| 3 | Which lesson comes first? | "Draw a shape" (needs no files). "Change a ready design" on the Flower sample is lesson 2. | That order. |
| 4 | Hint pictures: about 25 small drawn diagrams in the app's colors? | Yes; they are the part beginners read. | Text for every hint; pictures only for density, angle, underlay, edge pad, stitch length, pattern, satin width and split. |

## 4. Refresh this spec first (preflight)

Each line is a fact this spec assumes. Check them in a planning chat, fix the spec where one is false, then build.

| Check | Command | Expect, or what to change |
| --- | --- | --- |
| Phase 3 seams exist | `git ls-files apps/desktop/src/cmd/index.ts apps/desktop/src/dialogs.tsx apps/desktop/src/canvas/hooks.ts apps/desktop/src/components/controls.tsx` | four paths |
| The start card is still `EmptyState` | `grep -n "function EmptyState" apps/desktop/src/App.tsx` | one match; its first card (machine + update tick box) stays |
| Help guide headings | `grep -n "^## " engine/threadline_engine/ai/helpdocs.py` | 32 on 2026-11-24; rebuild the topic map in A5 from the list as it is now |
| Every fold in the panel | `grep -rn "<Sub " apps/desktop/src/components` | the list A1 sorts into Simple and Expert; phases 4 to 10 will have added some |
| Where points snap today | `grep -n "const snapped" apps/desktop/src/components/StitchCanvas.tsx`; `grep -rn "registerSnap(" apps/desktop/src` | `snapped()` snaps to guides, grid and other shapes' points inline. If an earlier phase already moved point snapping into a snap source, C3 only adds edges. |
| A name the store already uses | `grep -n "ghost" apps/desktop/src/store.ts` | `ghost` is Trace Assist's suggested point. The new flag is `ghostMode`. |
| Who reads a command's key | `grep -rn "\.shortcut\b" apps/desktop/src --include=*.ts --include=*.tsx \| grep -v "\.test\."` | about 16 places on 2026-11-24; D2 changes every one |
| Keys with a letter typed into a label | `grep -rnE "label=\"[^\"]*\([A-Z][A-Za-z+]*\)\"" apps/desktop/src/components` | Step 0 removes these |
| Reserved keys still free | `grep -nE "\| \`(F3\|F4\|F6\|F7\|F8\|F9\|F10\|Mod\+K\|Shift\+H\|Shift\+U\|Alt\+W\|Shift\+F1\|Alt\+F1\|Alt\+PageUp\|Alt\+PageDown)\` \|" docs/LUDD-KNOWLEDGE-BASE.md` | no match |
| Do F-keys reach the page? | In the installed app, press F3, F6, F7, F10 with a throwaway command on each | all four run it. If Windows or the web view takes one, pick from the free list in `docs/phases/README.md` and record it there. |
| Phases 10 and 12 | `grep -n "library\." engine/tests/snapshots/rpc_methods.json`; `git ls-files apps/desktop/src/components/MachineDialog.tsx` | a single-file thumbnail method means B1 shows pictures (else names only); the machine dialog decides the wording of done-when 1 |

## 5. Architecture

### 5.1 What is stored where

| Thing | Where | Why there |
| --- | --- | --- |
| `expert`, `hints`, `ghostMode`, `snapShapes`, `tutorialDone` | `prefs.ts`, mirrored in the store | per user, survive restarts |
| `recent: { path, name, at }[]` (12 at most) | `prefs.ts` | local only; a "Clear the list" link empties it |
| `keys: Record<commandId, shortcut>` | `prefs.ts` | only the changed ones |
| `workspaces: Record<name, Workspace>` | `prefs.ts` | |
| `hidden?: boolean` on every layout item | the layout (saved in the project, one undo step, like `locked`) | a long job stays tidy after a save. Older versions ignore the key, so no feature flag. |
| `soloBlocks`, `helpTopic`, `tutorial` | the store only | views of the moment |

### 5.2 New files

All under `apps/desktop/src/`. `design/`: `hints.ts`, `hintPictures.tsx`, `defaults.ts`. `feat/`: `help.ts`, `helpTopics.ts`, `recent.ts`, `tutorial.ts`, `troubleshoot.ts`, `visibility.ts`, `snapShapes.ts`, `palette.ts`, `shortcuts.ts`, `workspaces.ts`. `cmd/`: `learn.ts`, `start.ts`, `views.ts`, `workspace.ts`. `components/`: `HintPane`, `StartScreen`, `TutorialCoach`, `Troubleshoot`, `ColorFilm`, `CommandPalette`, `ShortcutsDialog`, `WorkspacesDialog`. Each track's "Owns" line says whose they are.

### 5.3 Where hint text lives

`design/hints.ts` is the only place a setting is explained. Ids are `<kind>.<setting>`: `fill.spacing_mm`, `satin.pull_comp_mm`, `run.style`, `text.size_mm`, `tool.fill`. Each hint is a title (the label), up to 240 characters that say what it does on fabric and when to change it, an optional picture id and the Help section to read next.

- **The pane** shows the hint for the row under the pointer or with keyboard focus.
- **The tooltip**: the `title` strings that `Row` and `Stepper` carry today move into `hints.ts`; a row given `hintId` takes its tooltip from there.
- **Help** shows the hint as a card above the guide section, and searches hint titles and text beside the guide. The engine's guide (`ai/helpdocs.py`) is not generated from hints: it stays the longer text, and a hint points to its section.

### 5.4 Engine

Two methods in `methods/help.py`, bodies in `ai/help.py`: `help.topics() -> list[str]` (the guide's headings, in order) and `help.section(title) -> {title, text} | None`. No other engine code changes.

## 6. Step 0 (session lead, before any worker)

1. `git switch -c phase-11/learnability`.
2. `prefs.ts`: add the keys in 5.1. `store.ts`: add `expert`, `hints`, `ghostMode`, `snapShapes`, `soloBlocks`, `helpTopic`, `tutorial` with setters. `design/types.ts`: `hidden?: boolean` on `FileItem`, `ObjectBase` and `TextItem`.
3. `feat/help.ts` with `openHelp()` doing what F1 does today; point the `app.help` command's `run` at it (the one edit to `actions.ts`).
4. `cmd/index.ts`: four import lines; create the four `cmd` files empty. `rpc_methods.json`: add `help.section` and `help.topics`, with stubs.
5. Empty components mounted once, so no track edits `App.tsx` or `InfoPanel`'s frame later: `<HintPane />` at the foot of the panel, `<ColorFilm />` above `<Player />`, `<TutorialCoach />` over the canvas, `<StartScreen />` in place of `EmptyState`'s second card (rendering that card's content for now).
6. `Cmd` in `controls.tsx` appends the command's key itself; remove the keys typed into labels (preflight row 8).
7. `canvas/hooks.ts`: add `registerRecordMask(fn: (design) => Uint8Array | null)` (0 draw, 1 hide, 2 faint) and its call sites: `drawStitches`' `keep()`, the realistic renderer, and one faint pass on its own layer under the stitches.
8. Commit. Workers branch from here.

## 7. Tracks

A, B, C and D run together. Worker rules are in `BUILDPLAN.md`.

---

### Track A: the panel

**Owns:** `components/controls.tsx`, `components/Accordion.tsx`, `components/ObjectPanel.tsx`, `components/FilePanel.tsx`, `components/TextPanel.tsx`, `components/HintPane.tsx`, `components/AIPanels.tsx` (`HelpDialog` only), `design/hints.ts`, `design/hintPictures.tsx`, `design/defaults.ts`, `feat/help.ts`, `feat/helpTopics.ts`, `cmd/learn.ts`, `engine/threadline_engine/ai/help.py`, `methods/help.py`, the Look section of `SettingsDialog.tsx`.

#### P11-A1 Simple / Expert
A two-button switch, Simple | Expert, at the top of the panel, always on screen (the project rule is "never removed": the way to everything is one click away). `F4` and Settings do the same.

- `Sub` gains `expert?: boolean`. In Simple an expert `Sub` is not drawn; its section ends with one link, "More settings are in Expert (F4)".
- **Stays in Simple:** thread, Stitch as, line Style, satin Width, the three Density buttons, Pattern and its own fields, Angle and Draw the angle, Add a satin border, the applique steps, border and tack-down; for lettering the words, font, size, spacing, shape and look. **Expert:** the density slider and exact Spacing, Underlay, Advanced stitch settings, and every fold a later phase added unless its spec called it a headline control.
- First run after the update: `expert = prefs.expert ?? prefs.welcomed === true`, saved at once so it never flips by itself.

#### P11-A2 Reset arrows
`Stepper`, `Row` and `Check` accept `reset?: { isDefault: boolean; run(): void }` and show `↺` ("Back to the standard value") only when the value is not standard. `standardValue(kind, key)` reads `DEFAULT_PARAMS`, then the descriptor's `def` (`fillPatterns.ts`, `lineStyles.ts`), then a small table for the rest. For Edge pad and Underlay the standard value is Auto. It is the factory value, not the "settings you set last".

#### P11-A3 Hints and pictures
Write a hint for every row the shape, lettering and stitch-file panels can show, one per tool (the strings in `ToolRail`'s `HINTS` move here) and one per pattern field. Pictures are 120 × 64 SVGs using `currentColor` and the CSS tokens, with no words inside them (so Phase 12 has nothing to translate there).

#### P11-A4 Hint pane
A strip at the foot of the panel, about five lines tall with the picture at its left. One `mouseover` and one `focusin` listener on the panel find the nearest `[data-hint]`. With nothing pointed at, it shows the current tool's hint. `F3` or its × turns it off (the first time, a notice says F3 brings it back). On for new installs.

#### P11-A5 F1 opens the right page
`currentTopic()` looks, in order, at: the setting under the pointer; a mode (stitch editing, knife, ruler, angle line, whole-picture trace, auto-trace); the tool if it is not Select; the kind of thing selected; else "Getting started". `feat/helpTopics.ts` maps each to a guide heading. `HelpDialog` opens on that section with an "All topics" link, and with an empty search box lists the topics (today it shows nothing). Dialogs do not pass keys through, so each dialog gets a small `?` that opens Help at its section.

#### Track A tests

| Test (file) | Proves |
| --- | --- |
| `someone who used LUDD before starts in Expert` (`feat/expert.test.ts`) | `welcomed: true` and no `expert` → true, and it is saved |
| `Simple hides Underlay and Advanced and shows the link` (`components/ObjectPanel.dom.test.tsx`) | for run, satin, fill, applique |
| `Expert shows the same rows as before this phase` (same) | the fixed label lists written in Phase 3 still pass |
| `the reset arrow shows only off-standard and puts the value back` (`components/controls.dom.test.tsx`) | Spacing 0.25 → arrow → 0.4; Edge pad set → arrow → Auto |
| `every setting row has a hint` (`design/hints.test.ts`) | render each kind and pattern in Expert; every `.acc-row` has `data-hint` and the id is in `HINTS`; so has every field in `FILL_PATTERN_DEFS`, `LINE_STYLE_DEFS` and `MOTIF_DEFS` |
| `hints are short and say something` (same) | 20 to 240 characters; none repeats its title |
| `the pane follows the pointer and the focus` (`components/HintPane.dom.test.tsx`) | |
| `F1 picks the section for the fill tool, stitch editing, selected text, nothing` (`feat/helpTopics.test.ts`) | |
| `test_help_topics_and_section` (`engine/tests/test_help.py`) | topics equal the guide's headings; an unknown title gives None |
| `test_every_ui_help_topic_is_a_guide_heading` (same) | each heading named in `feat/helpTopics.ts` and `design/hints.ts` exists |

---

### Track B: start and learn

**Owns:** `components/StartScreen.tsx`, `components/TutorialCoach.tsx`, `components/Troubleshoot.tsx`, `feat/recent.ts`, `feat/tutorial.ts`, `feat/troubleshoot.ts`, `cmd/start.ts`, new sections in `engine/threadline_engine/ai/helpdocs.py`, the welcome card's second half in `App.tsx`.

#### P11-B1 Start screen
Shown when no design is open, after the welcome card. New and Open as big buttons with their keys; **Recent**, up to 12 rows (name, folder, when); **Samples**, listed by asking `library.scan` for the bundled samples folder; **Learn**: Guided first design, Help, Something sewed wrong?; the drag-a-file line. `F9` with a design open shows the same thing as a dialog (`start`); New and Open there still ask before dropping unsaved work. `feat/recent.ts` watches the store (`projectPath`, `design.path`) instead of editing `actions.ts`. It skips samples, recovered work and unsaved designs. A row whose file is gone is greyed, says so, and has an × to remove it.

#### P11-B2 Guided first design
A small card at the bottom left of the canvas: step n of N, one sentence, **Skip this step**, **Leave**. It outlines the control the step is about. It never clicks for the user, never blocks a click, and never takes Esc (no `holdEscape`: that would swallow the Esc that cancels a shape).

```ts
type Step = { id: string; text: string; target?: string; done(now: State, atStepStart: State): boolean };   // a Lesson is a title, steps and an optional setup()
```

Lesson 1, "Draw a shape": pick the Fill tool (`tool === "fill"`) → click four or more points (`pen.a.length >= 4`) → press Enter (a fill exists that did not) → press Space to watch it stitch (`playing` went true) → pick a Density (its `spacing_mm` changed) → say what it will be stitched on (`layout.fabric` changed; Skip keeps cotton) → open Save for machine (`exportOpen`). The last card says the next button writes the file the machine reads, and offers Save project.

Lesson 2, "Change a ready design" (installed app only): opens the Flower sample as `openSample` does → select a petal → change its thread → move or resize it → watch it stitch → open Save for machine.

#### P11-B3 Something sewed wrong?
A dialog (`troubleshoot`) driven by data in `feat/troubleshoot.ts`: symptom → likely causes → what to change, each fix with a button that goes there.

```ts
type Fix = { text: string; go?: { command?: string; hint?: string; section?: string } };
type Symptom = { id: string; title: string; looksLike: string; causes: { why: string; fixes: Fix[] }[] };
```

First set: thread keeps breaking · fabric puckers · gaps between shapes · outline does not meet the fill · lettering wobbles or small letters fill in · loops on top · needle breaks · stiff as a patch · jump threads everywhere · bobbin thread shows on top. `go.hint` opens the fold holding that setting (switching to Expert if it must), scrolls to the row and flashes it; with nothing suitable selected it says "Select a fill first, then press this again." Machine-side causes (needle, threading, tension) get one line each here; Phase 12 writes them out. Written in LUDD's own words from standard practice; the idea is Embrilliance's "Correcting sewing issues" chapter and Melco's thread-break causes, not their text. The same symptoms go into the guide as one section, "When something sews wrong", so search and AI help find them.

#### Track B tests

| Test (file) | Proves |
| --- | --- |
| `recent keeps 12, newest first, one row per file` (`feat/recent.test.ts`) | paths compared without case on Windows; samples and unsaved designs are left out |
| `a missing file is greyed and can be removed` (`components/StartScreen.dom.test.tsx`) | |
| `lesson 1 advances only on the user's own action` (`feat/tutorial.test.ts`) | each step false before and true after its state change |
| `the coach takes no Esc and no clicks` (`components/tutorial.dom.test.tsx`) | `heldCount()` unchanged; the card has `pointer-events` only on itself; Skip and Leave work at every step |
| `a new user finishes lesson 1` (same) | drives the store through the seven steps to the closing card |
| `every fix points at something real` (`feat/troubleshoot.test.ts`) | each `go.command` is in `COMMANDS`, each `go.hint` in `HINTS` |
| `test_troubleshooting_symptoms_are_in_the_guide` (`engine/tests/test_help.py`) | each symptom title appears in the guide section |

---

### Track C: views

**Owns:** `feat/visibility.ts`, `feat/snapShapes.ts`, `components/ColorFilm.tsx`, `cmd/views.ts`, `design/player.ts` (one new function), the Order & colors list in `components/InfoPanel.tsx`, `hitTest` in `design/layout.ts`, the point-snapping block inside `snapped()` in `StitchCanvas.tsx`, one note in `components/ExportDialog.tsx`.

#### P11-C1 Hide, show, ghost
`Shift+H` hides what is selected; `Shift+U` shows everything; each row in Order & colors gets the eye button pictures already have. A hidden thing is not drawn and cannot be clicked on the canvas. **Ghost mode** (`F6`) draws hidden and pinned things faint (alpha 0.18, flat lines) under everything else; they still cannot be clicked, which is the point: you work over them. `feat/visibility.ts` builds the per-record mask from `records.item` and registers it. Save for machine shows the note from decision 2.

#### P11-C2 One color at a time
`F7` shows only the color block of the selected thing, or the block under the player's needle; `F7` again shows all. `ColorFilm` is a 22-pixel strip above the player: one swatch per block in sewing order. Click one to see only it, Shift+click to add or remove, **All** to go back. The same mask does the work (ghost mode makes the rest faint instead of gone). The strip is not shown for a one-color design.

#### P11-C3 Snap to shapes
Today a new point lands on another shape's point if it is within 7 pixels, always. This item adds **edges** (the nearest place on another drawn shape's outline, and on lettering's letter outlines from `items[].letters[].ring`), puts both behind one switch (`F8`, on by default so nothing changes for anyone), and moves them into a snap source. Order stays: guides, then grid, then a point, then an edge. A small mark shows what was caught (a square for a point, a cross for an edge), drawn through `registerOverlay`.

#### P11-C4 Travel by object
`objectStartStitches(design, stitchIdx)` returns the stitch count where each object begins, in sewing order (a change of `records.item`, ignoring −1). `Alt+PageUp` / `Alt+PageDown` move the player there, and the player shows that object's name beside the count.

#### Track C tests

| Test (file) | Proves |
| --- | --- |
| `a hidden item's records are masked, the rest are not` (`feat/visibility.test.ts`) | 1 normally, 2 in ghost mode; ghost mode makes pinned things faint too |
| `one color masks every other block` (same) | also after Sort colors |
| `clicks pass through hidden and faint things` (`design/layout.test.ts`) | `hitTest` skips them |
| `hide is one undo step and survives save and open` (`features.layout.test.ts`) | |
| `the export note counts hidden things` (`components/ExportDialog.dom.test.tsx`) | |
| `a point wins over an edge; out of reach gives nothing` (`feat/snapShapes.test.ts`) | pure function, fixed shapes |
| `with the switch off nothing snaps to shapes; guides and grid still do` (same) | |
| `object starts are in sewing order` (`design/player.test.ts`) | three items, one split by a color change |

---

### Track D: workspace

**Owns:** `feat/palette.ts`, `feat/shortcuts.ts`, `feat/workspaces.ts`, `components/CommandPalette.tsx`, `components/ShortcutsDialog.tsx`, `components/WorkspacesDialog.tsx`, `cmd/workspace.ts`, `commands.ts` (`keyOf`, `dispatchKey`), every reader of a command's key outside Track A's files.

#### P11-D1 Find a command
`Ctrl+K` opens a box: type any words, see every command whose title has them all, with its key. Arrows move, Enter runs and closes, Esc closes. Commands with one title (Redo, Zoom in) show as one row with all their keys. Ones that cannot run now are grey and last. With nothing typed, the last five used this session.

#### P11-D2 Change keyboard shortcuts
`commands.ts` gains `keyOf(command)` (the user's key, else the standard one) and `setKeyOverrides(map)`; `dispatchKey` matches on `keyOf`. `commands.ts` stays a leaf: `feat/shortcuts.ts` reads prefs and hands the map in at start. Every place that shows a key calls `keyOf`.

The dialog (`F10`): a searchable list of title and key; Change, then "Press the new key". It refuses, in plain words: a key another command has ("Ctrl+K is used by Find a command. Change that one first, or pick another key."); Esc, Enter, Tab, Space, Delete, Backspace, arrows, Home, End and Page keys (several commands share those by design, so those commands are listed as fixed); and the system's own (`Mod+Q`, `Mod+W`, `Mod+H`, `Alt+Arrow`, F5, F11, F12). "Back to the standard key" per row, and for all. The knowledge-base table keeps listing standard keys: `kb_commands.py` reads the source, not prefs.

#### P11-D3 Workspaces
A workspace is which panel sections are open, the panel's width, Simple or Expert, hints on or off, and the view switches (hoop, grid, rulers, realistic thread, see-through, jumps, density map, ghost mode, snap to shapes). `Alt+W` lists them: Use, Save the current one as…, Rename, Delete. None ships built in.

#### Track D tests

| Test (file) | Proves |
| --- | --- |
| `search needs every word and ranks word starts first` (`feat/palette.test.ts`) | |
| `same-title commands are one row; disabled ones are last and do not run` (same) | |
| `Enter runs the command and closes` (`components/CommandPalette.dom.test.tsx`) | |
| `a changed key runs the command and the old key does not` (`feat/shortcuts.test.ts`) | through `dispatchKey` |
| `shortcutFromEvent and matchesShortcut agree` (same) | a table of events, Windows and Mac |
| `a taken, fixed or system key is refused with its reason` (same) | |
| `menus and tooltips show the changed key` (`components/Menu.dom.test.tsx`) | |
| `the knowledge-base check still passes with keys changed` (`knowledgeBase.test.ts`) | it reads `shortcut`, not `keyOf` |
| `a workspace round-trips` (`feat/workspaces.test.ts`) | capture, change everything, apply |

## 8. Integration (session lead)

1. Merge in the order A, C, D, B (B's tutorial and troubleshooting point at A's hint ids and C's and D's commands). Run `python scripts/check.py`: the cross-track tests now mean something (every `go.hint`, every tutorial `target`, every workspace field resolves).
2. Docs (section 9), then `python scripts/kb_commands.py`.
3. `python scripts/check.py --all`. In the installed app: F3, F4, F6 to F10 each do their job; lesson 1 start to finish; `Ctrl+K`.
4. Stop contract in `BUILDPLAN.md`.

## 9. Docs payload

**`docs/CHANGELOG.md`:** one section, a line per item, in the user's words ("**Simple and Expert**: one switch at the top of the panel…"). End with "Nothing sews differently."

**`docs/LUDD-KNOWLEDGE-BASE.md`**, new section 29 "Learning": `F-2401` Simple and Expert · `F-2402` Hints · `F-2403` F1 help for what you're using · `F-2404` Start screen · `F-2405` Guided first design · `F-2406` Troubleshooting by symptom · `F-2407` Workspaces · `F-2408` Find a command · `F-2409` Custom shortcuts. In section 6: `F-408` Hide, show and ghost mode · `F-409` Show one color · `F-410` Snap to shapes (`F-403` points to it) · `F-411` Travel by object (`F-404` points to it).

Limits: `L-065` Help, the manual and some messages name the standard keys after you change one (PARTIAL: menus, buttons and Find a command show yours). `L-066` hidden things are still sewn (by design). `L-067` snapping to the stitches of a placed stitch file (NO). `L-068` lesson 2 without the bundled samples (NO). `L-069` unused.

Troubleshooting: `T-051` "settings I used to see are gone" → Expert (F4). `T-052` "a shape sews but I can't see it" → Show everything (Shift+U). `T-053` "a key does something else now" → F10, back to the standard keys. `T-054` "new points jump onto another shape" → Snap to shapes (F8). Also: section 2 index rows for each; section 23 history; *Last updated*; section 25 by the script.

**`docs/USER-MANUAL.md`:** section 1 (the switch, hint pane, start screen), section 3 (hide, ghost, one color, snap, travel by object), section 13 (Help at the right page, the guided design, Something sewed wrong?, Find a command, shortcuts, workspaces). **`ai/helpdocs.py`:** the same as six short sections plus "When something sews wrong".

**`docs/stitchout-log.md`:** no rows.

## 10. Risks and fallbacks

| Risk | Sign | Fallback |
| --- | --- | --- |
| Windows or the web view keeps F6, F7 or F10 for itself | the preflight key test fails | Use free keys from the README list; update its table in the same change. |
| Simple mode hides something a returning user relies on | the audit's "same panel as yesterday" check | Decision 1's rule; if in doubt, mark the fold not expert. |
| The mask slows drawing on big designs | the player stutters on a 100,000-stitch file | Build the mask once per render and per change of hidden or solo state, never per frame. |
| Hints go stale as later phases add settings | `every setting row has a hint` fails in that phase | Good: that phase writes the hint. Phases 13 and 14 inherit the test. |
| The tutorial breaks when a control it points at moves | `a new user finishes lesson 1` fails | Steps test the store, not the screen; only `target` can go stale, and a missing target just draws no outline. |
| A changed key collides with a key a later phase reserves | the later phase's command is unreachable for that user | On start, a command whose standard key is taken by a user's override keeps working from Find a command, and F10 shows it flagged. |

## 11. Handoff

Write in `HANDOFF.md`: which F-keys were kept or replaced; whether recent designs show pictures; whether done-when 1 was tried by hand and by whom; any hint left as text only. Tell Phase 12: every string added here goes through `t()` there, and `feat/troubleshoot.ts` is where its machine-side advice plugs in.
