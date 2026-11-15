# QA phase 4: docs (docs-a, docs-b, docs-c)

Areas: `### docs-a`, `### docs-b`, `### docs-c` under Medium and Low in docs/QA-REPORT.md. Each
claim was checked against the current code (COMMANDS in `apps/desktop/src/actions.ts`, the menus in
Toolbar.tsx and InfoPanel.tsx, the dialogs, and the engine) after phases 1-4. The docs were fixed;
where the code is wrong, the item is handed over.

Files changed: docs/USER-MANUAL.md, docs/USER-GUIDE.md, README.md, docs/release-notes.md,
docs/RELEASING.md, docs/PLAN.md, docs/CHANGELOG.md, engine/threadline_engine/ai/helpdocs.py, new
engine/tests/test_helpdocs.py (every shortcut in Help and in the manual must be in COMMANDS; Help
finds Batch convert, stops at the needle, renaming and Restart engine; no stale lines).

## 1. Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | docs-a | In-app Help is not "this same material": missing topics, wrong keys | Fixed: Help rewritten to agree with the manual (new sections: Batch convert, stops and trims at the needle, renaming, Restart engine; Text is Shift+T, no "Shape tab", rename is not the pencil); the manual now says Help searches "a shorter version" | helpdocs.py, USER-MANUAL.md intro | test_helpdocs.py (all 7) |
| Medium | docs-a | Shift+comma (machine speed) can never fire | Handed over: still dead (`matchesShortcut` only falls back to `e.code` with Alt; Shift+, sends "<"). Manual keeps the intended key | - | - |
| Medium | docs-a | Stitch-edit moves drift after a turn/resize | Already fixed (phase 2); the manual already said so | layout.py | test_layout |
| Medium | docs-a | A project with a missing font won't open | Already fixed (phase 1 stand-in font; phase 4 fonts embedded in projects); manual updated | project.py, lettering.py; USER-MANUAL.md Projects, Lettering | test_project, test_lettering |
| Medium | docs-a | Knife pieces lose recolour, group, pin | Already fixed (leftovers); manual updated | features.ts; USER-MANUAL.md Knife | leftovers.qa.test.ts |
| Medium | docs-a | Browse designs can't find past the newest 600 | Already fixed (leftovers); manual describes it | FeatureDialogs.tsx; USER-MANUAL.md Browse designs | - |
| Medium | docs-a | Text longer than its line piles up, no warning | Already fixed (phase 2, lettering); manual updated (closed lines overlap, upright text) | lettering.py; USER-MANUAL.md | test_lettering |
| Medium | docs-a | Manual overstates cut-stops | Fixed: manual and Help say "jumps the design marks for trimming" and describe "Also cut jumps the design doesn't mark"; the dialog's note came from the layout agent | USER-MANUAL.md, helpdocs.py | test_helpdocs |
| Medium | docs-b | Insert stop/trim can't target lettering | Already fixed (layout); manual updated | layout.py; USER-MANUAL.md Machine extras | test_layout |
| Medium | docs-b | Advisor "make it a satin" can't be accepted | Already fixed for lines (C10); fill to satin still can't be accepted: manual and Help now say so | USER-MANUAL.md AI, helpdocs.py | ai.test.ts |
| Medium | docs-b | Save as stitch font leads nowhere | Already fixed (lettering: saved into the fonts folder); manual and Help say where and how to fine-tune | USER-MANUAL.md Lettering, helpdocs.py | test_lettering |
| Medium | docs-b | Key matching on e.key: Shift+comma, Alt on Mac | Alt on Mac: already fixed (ui). Shift+comma: handed over (see above). Manual: "Alt is ⌥ (Option) on a Mac" | USER-MANUAL.md shortcuts intro | ui.qa.test.ts |
| Medium | docs-b | Put text on line ignores its turn/size | Already fixed (lettering); manual says turn and mirror are let go | USER-MANUAL.md Lettering | features.lettering.test.ts |
| Medium | docs-b | Text longer than line; right-to-left upside down | Already fixed (lettering); manual updated | USER-MANUAL.md | test_lettering |
| Medium | docs-b | Fabric: hand-set density doesn't win; lettering ignores fabric | Lettering: already fixed (layout). Density: manual and Help reworded (the fabric scales density, also a hand-set one; pull compensation and underlay set by hand win) | USER-MANUAL.md Stitching on, helpdocs.py | test_layout |
| Medium | docs-b | Shortest order does less than documented | Already fixed (layout); manual and Help describe the new behaviour | USER-MANUAL.md, helpdocs.py | test_connectors |
| Medium | docs-b | Knockdown thread can't be set | Already fixed (leftovers); manual and Help say how (✎ next to Knockdown in Threads) | USER-MANUAL.md, helpdocs.py | - |
| Medium | docs-b | Trim jumps only covers existing designs | Already fixed (layout); manual says it's one setting for the whole design | USER-MANUAL.md | layout.test.ts |
| Medium | docs-c | Help (F1) wrong keys, stale names, missing features | Fixed (same as the first row) | helpdocs.py | test_helpdocs.py |
| Medium | docs-c | Text on a line piles up, comment claims a warning | Already fixed (phase 2) | lettering.py | test_lettering |
| Medium | docs-c | Stitch-edit moves world-space | Already fixed (phase 2) | layout.py | test_layout |
| Medium | docs-c | Shortest order all-or-nothing, wrong message | Already fixed (layout) | layout.py | test_connectors |
| Low | docs-a | "and 40 more" formats (40 in total) | Fixed: "40 formats: … and 34 more"; README and release notes say 40 read, 9 written | USER-MANUAL.md, README.md, release-notes.md | - |
| Low | docs-a | Duplicate player ids; undocumented [ ] playback keys | Ids already fixed (ui: player.fasterAlt/slowerAlt); [ and ] now in the manual and Help | USER-MANUAL.md Watching it stitch + table, helpdocs.py | ui.qa.test.ts |
| Low | docs-a | Manual wording vs UI (rail, Repeat button, Forget guesses, Whole picture, which ⋯, samples) | Fixed: rail lists Auto-trace; Repeat is in the panel's ⋯; Forget guesses is in Settings → AI tracing; Whole picture is in the bar before you click; toolbar ⋯ vs panel ⋯ named, with the panel menu's real items; five samples, three also as PES/JEF | USER-MANUAL.md | test_helpdocs (shortcuts) |
| Low | docs-a | USER-GUIDE stale after 1.0.1 | Fixed: `LUDD_<version>_…` names and system minimums, Underlay/Advanced instead of More options, Stitching on in the Design section, My threads & charts, AI settings names, the model download, Restart engine, licences | USER-GUIDE.md | - |
| Low | docs-a | Shapes menu ignores "settings carry over" | Handed over: actions.ts `addShape` still uses `DEFAULT_PARAMS.fill` | - | - |
| Low | docs-a | Picture toast says "lock it (🔒)" | Handed over: actions.ts toast after adding a picture should say "pin it (📌)" | - | - |
| Low | docs-a | Backspace with a point selected deletes the whole shape | Handed over: needs a `node.deleteAlt` (Backspace) before `arrange.deleteAlt`. Manual unchanged (it says Delete removes the point) | - | - |
| Low | docs-a | Pinned shapes still move from the keyboard | Handed over / owner decision: arrows, R, Alt+H/V ignore `locked` on shapes (pictures honour it). The manual only promises "can't be dragged", which is true | - | - |
| Low | docs-a | Hidden pictures (B) can still be clicked and dragged | Handed over: StitchCanvas.tsx `pick()` should skip pictures when `showPictures` is off (still so) | - | - |
| Low | docs-a | Whole-picture "Spread and Points every apply" but can't change | Already fixed (autotrace: the bar has both); manual updated | ToolRail.tsx; USER-MANUAL.md | autoTrace.test.ts |
| Low | docs-a | CLAUDE.md and machine schema out of date | Owner decision / handed over: CLAUDE.md is the owner's file; `schemas/machine.schema.json` still says Threadline and `%APPDATA%\Threadline\machines` | - | - |
| Low | docs-a | Features the manual doesn't mention | Fixed: dialogs drag by their title (Esc puts back); [ ] playback; Batch convert options and target folder; "Also cut jumps…"; the first-run machine picker is in USER-GUIDE | USER-MANUAL.md | - |
| Low | docs-a | Browse designs "opens faster next time" only within a session; no refresh | Fixed in the manual ("kept while LUDD is open"; choose the folder again for new designs). A disk cache or Refresh button: owner decision | USER-MANUAL.md | - |
| Low | docs-b | Applique shows Lock stitches boxes that do nothing | Already fixed (leftovers: hidden); manual notes applique always locks round its stops | USER-MANUAL.md table | - |
| Low | docs-b | Font list shows 200 with no hint | Already fixed (lettering: hint); manual mentions it | USER-MANUAL.md | - |
| Low | docs-b | Manual vs panel names and numbers | Fixed: "Stitch as" row with Satin; Density presets vs Spacing in Advanced; Auto underlay/Edge pad (width only for satins); ribbon width 1-12 mm; satin warning from 7 mm; "Check before stitching"; "Match to mine…" | USER-MANUAL.md | - |
| Low | docs-b | helpdocs stale lines (Text T, Shape tab, rename pencil) | Fixed | helpdocs.py | test_helpdocs, test_qa_leftovers |
| Low | docs-b | AI wording: Windows-only key toast, "exactly what will go" | Toast already fixed (engine-io). Manual reworded: key per system; the preview shows what will go and where, and LUDD's fixed instructions go too. Showing those instructions in the preview: owner decision | USER-MANUAL.md AI, helpdocs.py | actions.engineio.test.ts |
| Low | docs-b | player.slower/faster registered twice | Already fixed (ui); keys documented | USER-MANUAL.md | ui.qa.test.ts |
| Low | docs-c | machine.schema.json says Threadline and the old folder; other schemas missing | Handed over / owner decision (schemas are not docs; whether to write the promised schemas is open) | - | - |
| Low | docs-c | CHANGELOG 1.0.1 contradicts itself on the Sewing order pencil; one heading covers unrelated items | Fixed: the pencil removed from "Rename"; new "### Other 1.0.1 changes" heading | CHANGELOG.md | - |
| Low | docs-c | Stitch-out log missing new stitch output | Fixed: rows for text on a line, an outline round lettering, edited stitches, shortest order (and all phase-4 output). Motif snapshots for wave, zigzag, blanket: already fixed (stitches) | stitchout-log.md | test_digitize snapshots |
| Low | docs-c | CLAUDE.md and PLAN.md describe a different stack | PLAN.md fixed (Zustand without Immer, no networkx, OpenCV region growing, MobileSAM on ONNX Runtime CPU, backlog items marked shipped, M1 note, placeholders replaced). CLAUDE.md: owner decision (networkx listed; onnxruntime is optional only on Intel Macs) | PLAN.md | - |
| Low | docs-c | Dead anchor #auto-trace-shift-a | Fixed: #auto-trace-shifta | USER-MANUAL.md | - |
| Low | docs-c | Release housekeeping (PDF step, stale root PDF, lockfiles, tsbuildinfo) | Fixed: RELEASING step 2 makes the PDF; lockfiles already in step 1 (platform); tsbuildinfo already ignored. Also: delete the key password file once the secrets are set (engine-io handover). The stale root `LUDD-User-Manual.pdf` (git-ignored, v1.0): owner decision to delete | RELEASING.md | - |
| Low | docs-c | MobileSAM called MIT | Already fixed (phase 2: Apache-2.0 everywhere) | segment.py, AISettings.tsx, docs | - |
| Low | docs-c | No third-party notices | Already fixed (platform: THIRD-PARTY-NOTICES.txt in the installer; leftovers: Settings → About → Licences…); manual and guide mention it | USER-MANUAL.md Settings, USER-GUIDE.md | release.test.ts |
| Low | docs-c | One file per name silently overwrites | Already fixed (C12, keep_existing); manual updated | USER-MANUAL.md | test_layout `test_qa_c12_*` |
| Low | docs-c | Mixed US/UK spelling | Owner decision: UI labels "Centre", "Millimetres", "Licences…" are UK while the rest is US; the manual follows the labels. Help prose made US | helpdocs.py | - |
| Low | docs-c | README and release notes lead with Trace Assist | Fixed: Auto-trace and the 1.0.1 features first; Trace Assist row replaced | README.md, release-notes.md | - |
| Low | docs-c | README "save in 40+ formats" | Fixed: opens 40, saves 9 | README.md | - |

Counts (53 items): 17 fixed (in the docs), 27 already fixed in the code by phases 1-4 (the docs
brought in line), 9 handed over or for the owner to decide. A few rows are mixed (key matching:
Alt fixed, Shift+comma handed over; AI preview and browser cache: docs fixed, the rest a decision).

## 2. Changelog lines
- In-app Help (F1) matches the manual again: right keys, renaming, batch convert, stops and trims at the needle, Restart engine.
- The manual, user guide, README and release notes describe 1.0.1 as it is now.

## 3. Manual changes needed
None left: done in this pass, together with every other phase-4 notes file's "Manual changes
needed" (merged into USER-MANUAL.md, USER-GUIDE.md and the in-app Help).

## 4. Stitch output changed
None (docs only).

## 5. Handed over
- **commands.ts / actions.ts**: Shift+comma (machine speed) never fires: `matchesShortcut` should also try `e.code` ("Comma") when Shift is held (Shift+, gives "<"), or give machine speed another key. A test in ui.qa.test.ts with `{key: "<", code: "Comma", shiftKey: true}`.
- **actions.ts**: `addShape` should start from `defaultsFor("fill")` like every other new shape; the toast after adding a picture should say "pin it (📌)", not "lock it (🔒)"; Backspace with a point selected should delete the point (a `node.deleteAlt` command before `arrange.deleteAlt`).
- **actions.ts (owner decision)**: whether pinned shapes should also ignore the arrow keys, R and Alt+H/V, as pinned pictures do.
- **StitchCanvas.tsx**: `pick()` should skip pictures while pictures are hidden (B).
- **schemas/machine.schema.json**: title/$id still "Threadline", folder `%APPDATA%\Threadline\machines` (now `%APPDATA%\Ludd\machines`).
- **AIPanels.tsx**: the hint for a fill-to-satin suggestion could point to Add a satin border (Shift+B).

## Notes
- Tests at the end: engine `CI=1 uv run pytest`: 588 passed, 1 skipped (the opt-in real AI model test); UI `corepack pnpm test`: 29 files, 155 tests passed.
- Every shortcut written in the manual, the user guide, README and Help was checked against COMMANDS (test_helpdocs.py now does this for the manual and Help on every run).
