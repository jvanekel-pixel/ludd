# Phase specs: index and conventions

One file per phase. Each file is the whole spec for one build session: scope, architecture, tracks that build in parallel, the tests that review the work, and the docs to write. How a session runs is in `BUILDPLAN.md` (repo root). Checkboxes live in the root `PLAN.md` (the Command Center tracker); nothing is checked off here.

Written 2026-11-24 from the competitive review (154 features, eight competitor manuals) and a read of `main` at d39bbb5. Function and file names below were true at that commit.

## The phases

| # | Phase | Spec | Weight | Tracks | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | Foundation & shipped core (v1.0.0) | done | – | – | – |
| 2 | 1.0.1 hardening | done | – | – | 1 |
| 3 | Build seams, spiral fill, more shapes | [PHASE-03](PHASE-03-build-seams.md) | Heavy (architecture) | 3 then 2 | 2 |
| 4 | Merge-safe stitch files | [PHASE-04](PHASE-04-merge-safe-stitch-files.md) | Heavy | 3 | 3 |
| 5 | Lettering & personalization | [PHASE-05](PHASE-05-lettering.md) | Heavy | 4 | 3 |
| 6 | Fills & stitch quality | [PHASE-06](PHASE-06-fills-and-stitch-quality.md) | Heavy | 3 | 3 |
| 7 | Lines, sequencing & drawing tools | [PHASE-07](PHASE-07-lines-sequencing-drawing.md) | Heavy | 4 | 3, 6 |
| 8 | Specialty & in-the-hoop | [PHASE-08](PHASE-08-specialty-in-the-hoop.md) | Medium | 3 | 3, 6 |
| 9 | Images & photo stitch | [PHASE-09](PHASE-09-images-photo-stitch.md) | Heavy | 3 | 3 |
| 10 | Design library, OS thumbnails, thread inventory | [PHASE-10](PHASE-10-library-thumbnails-inventory.md) | Heavy (platform code) | 4 | 3 |
| 11 | Learnability | [PHASE-11](PHASE-11-learnability.md) | Medium | 4 | 3 |
| 12 | Machines, threads & languages | [PHASE-12](PHASE-12-machines-threads-languages.md) | Light data, then a wide language pass | 3 then 1 | 3 |
| 13 | Long-tail stitch features | [PHASE-13](PHASE-13-long-tail-stitch-features.md) | Heavy | 3 | 4, 6, 7 (10 for the parts library's thumbnails; it has a fallback) |
| 14 | Extensibility, accessibility & performance | [PHASE-14](PHASE-14-extensibility-accessibility-performance.md) | Medium | 3 | 3 (best after 6, 7 and 10, so plugins and the benchmark see the full app) |
| 15 | Stitch-out verification on the PE550D | [PHASE-15](PHASE-15-stitch-out-verification.md) | Owner's hands | – | all build phases the owner wants in 2.0 |
| 16 | Fixes, public manual & 2.0 release | [PHASE-16](PHASE-16-fixes-manual-release.md) | Medium | 2 | 15 |

Phases 4, 5, 6, 9, 10, 11 and 12 only depend on Phase 3, so any two of them can run at the same time in separate sessions if the owner wants to go faster (see "Two phases at once" in `BUILDPLAN.md`). One exception: Phase 12's language track rewrites the text in nearly every UI file, so it runs alone, with nothing else in flight.

## Old plan → new plan

The competitive review and the manual outline (both Claude Docs) use the phase numbers from the plan as it was on 2026-11-24. This table translates them.

| Old | Old title | Now |
| --- | --- | --- |
| 3 | Stitch-out verification | 15 (testing waits until the features are built) |
| 4 | v1.x features & launch polish | Split: SVG/DXF/PDF import → 7 · push compensation → 6 · sewing time and thread estimate → built (PR #23) · thread inventory → 10 · tutorial, hints, F1 help → 11 · JSON Schemas → 12 · name check → 16 |
| 5 | Merge-safe stitch files | 4 |
| 6 | Lettering & personalization | 5 |
| 7 | Stitch engine depth | 6 (fills, blend, push comp, emboss, hand-stitch, angles) and 7 (branching, craft stitches, buttonholes, freehand, arrangements, presets) · spiral fill and basic shapes → 3 |
| 8 | Specialty & in-the-hoop | 8 |
| 9 | Images & design library | 9 (pictures, photo stitch, PNG export) and 10 (organizer, OS thumbnails) |
| 10 | Learnability & machine coverage | 11 (learning, views, palette) and 12 (machines, charts, languages) |
| "Later" | String/chain stitch, cutwork, word art, stitches to objects, shared underlay | 13 |
| – | Plugin API, accessibility, performance (from `docs/PLAN.md` backlog) | 14 |

## How deep each spec goes

Phases 3 to 6 are specified to the function: they are built first, while the code still matches. Phases 7 to 10 name modules, data shapes, algorithms and tests. Phases 11 to 14 fix scope, architecture and tests, and say "refresh this spec first": before one of those is built, spend one cheap planning chat checking its Preflight section against the code as it then is, and update the file. Line numbers are never used; anchors are function and file names.

## What every phase file contains

1. **Header**: weight, model, dependencies, the compendium rows it closes.
2. **Goal and done-when**: the same "done when" as `PLAN.md`.
3. **Scope**: an items table (`P<phase>-<track><n>`), then what is out of scope.
4. **Owner decisions**: questions only the owner can answer, each with a recommendation and what the build does if there is no answer.
5. **Preflight**: facts to confirm with a grep before any edit. If one is false, the spec is stale: stop and say so.
6. **Architecture**: data model, engine modules, RPC methods, UI.
7. **Step 0**: edits to shared files, made once and committed before workers start.
8. **Tracks**: for each, the files it owns, each item's behavior, algorithm, settings and defaults, and its tests.
9. **Integration**: merge order and the full check.
10. **Docs payload**: knowledge-base IDs, changelog lines, manual sections, stitch-out rows.
11. **Risks and fallbacks**, then **Handoff**.

## Naming and IDs

**Items**: `P4-A2` is Phase 4, track A, item 2. `S` items are Step 0; `Z` items are integration.

**Branches**: `phase-04/merge-safe-stitch-files` for the phase; workers branch from it as `phase-04/track-a`.

**Knowledge-base IDs are assigned here so parallel workers never collide.** Feature IDs (`F-`) are listed in each phase's docs payload. Limits (`L-`) and troubleshooting (`T-`) come in blocks; unused numbers in a block stay unused.

| Phase | L- block | T- block |
| --- | --- | --- |
| 3 | L-026 to L-029 | T-021 to T-022 |
| 4 | L-030 to L-034 | T-023 to T-026 |
| 5 | L-035 to L-039 | T-027 to T-030 |
| 6 | L-040 to L-044 | T-031 to T-034 |
| 7 | L-045 to L-049 | T-035 to T-038 |
| 8 | L-050 to L-054 | T-039 to T-042 |
| 9 | L-055 to L-059 | T-043 to T-046 |
| 10 | L-060 to L-064 | T-047 to T-050 |
| 11 | L-065 to L-069 | T-051 to T-054 |
| 12 | L-070 to L-074 | T-055 to T-058 |
| 13 | L-075 to L-079 | T-059 to T-062 |
| 14 | L-080 to L-084 | T-063 to T-066 |

New knowledge-base sections (added by the phase that first needs them): 27 Specialty (`F-22xx`, Phase 8), 28 Design library (`F-23xx`, Phase 10), 29 Learning (`F-24xx`, Phase 11), 30 Machines (`F-25xx`, Phase 12), 31 Plugins (`F-26xx`, Phase 14). `F-406` is taken by the sewing time estimate (PR #23). `F-902`, `F-903` and `F-1201` were never used; leave them alone.

**Decisions** (`D-`): the next free number in `DECISIONS.md`, assigned by the session lead during integration, never by a worker.

**Project feature flags**: every new thing a project file can hold *that changes what is sewn* gets a name in `project.KNOWN_FEATURES` and a detector in `_features()`. Names are listed in each phase's Step 0. Something an older version can safely ignore (a hidden mark, notes, a needle plan) gets no flag: a flag makes older versions refuse the project.

## Reserved keyboard shortcuts

Every command needs a shortcut (project rule). These are reserved so phases built months apart do not collide. All were free on 2026-11-24; a build session still greps `COMMANDS` before using one. Single digits are taken (`view.zoom2` to `view.zoom9`).

| Phase | Command id | Title | Shortcut |
| --- | --- | --- | --- |
| 3 | `shape.roundedRect` | Add a rounded rectangle | `Mod+Alt+4` |
| 3 | `shape.ellipse` | Add an oval | `Mod+Alt+5` |
| 3 | `shape.triangle` | Add a triangle | `Mod+Alt+6` |
| 3 | `shape.polygon` | Add a polygon | `Mod+Alt+7` |
| 3 | `shape.heart` | Add a heart | `Mod+Alt+8` |
| 4 | `stitch.repair` | Repair this design… | `Mod+Alt+D` |
| 4 | `stitch.removeHidden` | Remove stitches hidden under what's on top | `Alt+Shift+H` |
| 4 | `stitch.declump` | Thin out dense spots | `Alt+Shift+D` |
| 4 | `stitch.filterSmall` | Remove tiny stitches | `Alt+Shift+S` |
| 4 | `stitch.densityLimit` | Limit density for this fabric | `Alt+Shift+L` |
| 4 | `stitch.rebuild` | Rebuild stitches at this size | `Alt+Shift+R` |
| 4 | `stitch.insert` | Insert a stitch here | `Insert` |
| 4 | `stitch.insertJump` | Insert a jump here | `Shift+Insert` |
| 4 | `stitch.lockJump` | Lock both sides of this jump | `Alt+Shift+T` |
| 4 | `object.removeOverlap` | Remove stitching hidden under shapes on top | `Alt+Shift+O` |
| 4 | `view.wireframe` | Needle path only | `Shift+P` |
| 5 | `text.letters` | Adjust single letters | `Alt+Shift+A` |
| 5 | `text.resetLetters` | Put the letters back | `Alt+Shift+Z` |
| 5 | `text.fontFromFiles` | Make a stitch font from letter files… | `Mod+Alt+F` |
| 5 | `text.saveTemplate` | Save this layout as a name template… | `Mod+Alt+P` |
| 5 | `text.placement` | Placement guides… | `Alt+Shift+G` |
| 6 | `object.addAngle` | Add another stitch angle line | `Shift+I` |
| 6 | `object.carve` | Carve a line into the fill | `Shift+C` |
| 6 | `motif.library` | Motifs… | `Alt+Shift+M` |
| 7 | `tool.freehand` | Draw freehand | `Y` |
| 7 | `layout.branch` | Branch: sew the selected shapes as one path | `Alt+Shift+B` |
| 7 | `layout.unbranch` | Take the selected shapes out of their branch | `Alt+Shift+U` |
| 7 | `presets.open` | Stitch presets… | `Alt+P` |
| 7 | `file.importArt` | Import artwork (SVG, DXF, PDF)… | `Mod+Alt+I` |
| 7 | `object.buttonhole` | Add a buttonhole | `Alt+B` |
| 7 | `object.eyelet` | Add an eyelet | `Alt+E` |
| 8 | `tool.patch` | Make a patch… | `Alt+Shift+C` |
| 8 | `applique.fromSelection` | Make an applique from the selection | `Alt+Shift+Q` |
| 8 | `applique.fcm` | Save applique cut file (FCM)… | `Mod+Alt+U` |
| 8 | `file.printStickers` | Print positioning stickers… | `Mod+Alt+K` |
| 8 | `layout.centerOut` | Sew from the center out (caps) | `Alt+Shift+K` |
| 9 | `tool.wand` | Magic wand: click a color in a picture to fill it | `Z` |
| 9 | `image.colors` | Simplify the picture's colors… | `Alt+C` |
| 9 | `image.photoStitch` | Photo stitch… | `Alt+Shift+F` |
| 9 | `image.crossStitch` | Cross-stitch from a picture… | `Alt+X` |
| 9 | `file.exportPicture` | Save a picture of the design (PNG)… | `Mod+Shift+G` |
| 9 | `file.notes` | Design notes… | `Alt+N` |
| 9 | `colors.lighten` | Lighten all colors | `Alt+=` |
| 9 | `colors.darken` | Darken all colors | `Alt+-` |
| 10 | `library.find` | Find a design… | `Mod+F` |
| 10 | `library.duplicates` | Find duplicate designs… | `Mod+Alt+Y` |
| 10 | `library.tags` | Tag the selected designs… | `Alt+G` |
| 10 | `threads.inventory` | Thread inventory and shopping list… | `Mod+Alt+S` |
| 11 | `app.palette` | Find a command… | `Mod+K` |
| 11 | `app.hints` | Hints beside the settings | `F3` |
| 11 | `app.expert` | Simple or Expert settings | `F4` |
| 11 | `view.ghost` | Ghost mode | `F6` |
| 11 | `view.soloColor` | Show only the selected color | `F7` |
| 11 | `view.snapShapes` | Snap new points to shapes | `F8` |
| 11 | `app.start` | Start screen | `F9` |
| 11 | `app.shortcuts` | Change keyboard shortcuts… | `F10` |
| 11 | `app.tutorial` | Guided first design | `Shift+F1` |
| 11 | `app.troubleshoot` | Something sewed wrong? | `Alt+F1` |
| 11 | `view.hide` | Hide the selected things | `Shift+H` |
| 11 | `view.showAll` | Show everything | `Shift+U` |
| 11 | `view.workspace` | Workspaces… | `Alt+W` |
| 11 | `player.prevObject` / `player.nextObject` | Previous / next object | `Alt+PageUp` / `Alt+PageDown` |
| 12 | `machine.pick` | Choose your machine and hoop… | `Alt+M` |
| 12 | `threads.needles` | Assign colors to needles… | `Alt+Shift+N` |
| 13 | `stitch.toShapes` | Turn stitches into shapes… | `Alt+Shift+X` |
| 13 | `text.wordArt` | Fill a shape with words… | `Alt+Shift+W` |
| 13 | `file.parts` | Parts library… | `Alt+L` |
| 13 | `layout.sharedUnderlay` | One underlay under touching shapes | `Alt+Shift+Y` |
| 14 | `app.plugins` | Plugins… | `Alt+Shift+P` |

Still free after all of the above, for anything a build turns up: `Shift+E/F/J/L/M/Q/S/V/Y/Z`, `Alt+F/I/J/K/O/Q/R/S/U/Y/Z`, `Alt+0` to `Alt+9`, `Mod+J`, `Mod+Shift+F/H/Q/V/W/X/Y`, `Mod+Alt+A/C/H/Q/V/Z/9/0`, `Alt+Shift+E/I/J/V`. Avoid `Mod+H`, `Mod+Q`, `Mod+W` (the operating system's), `Alt+Arrow` (history in the web view) and `F5`, `F11`, `F12`.

## Rules every phase inherits

From `AGENTS.md`; repeated here because workers read this file, not that one.

- Millimeters everywhere; 0.1 mm only at export. Objects are the source of truth; stitches are derived and cached by object hash.
- The default view shows what a beginner needs. Every new setting goes behind "More options", a fold, or the ⋯ menu unless the spec says it is a headline control.
- The core makes no network calls. Nothing from AI or tracing is applied without a preview and an accept.
- Every command is in the registry with a shortcut. Every engine function has a pytest. Every stitch type has snapshot tests and passes the invariants in `engine/tests/invariants.py` (built in Phase 3).
- PES first, JEF must export correctly; golden tests cover both.
- A change that alters stitches adds a row to "Pending machine tests" in `docs/stitchout-log.md`. No stitch-outs happen before Phase 15.
- Old projects keep opening: `.thl`, `.tlfont`, and every `.ludd` saved by an earlier version. A project that uses a new feature names it in `features` so older versions say so instead of sewing it wrong.
- US spelling in everything a user reads. Plain words: "Edge pad", not "pull compensation", on the surface; the technical word goes in the hint.
- GPL-3.0-or-later. Code adapted from Ink/Stitch or another GPL-compatible project is credited in a comment with its copyright notice.
- A new dependency is an owner decision in the phase's spec, with its license checked against GPL-3.0-or-later and the frozen engine's size noted in the handoff.
- Once Phase 12 has shipped: every string a user reads goes through `t()` (UI) or a message template (engine), and every new project field goes into `schemas/project.schema.json`.

## Notes from writing the specs

- The canvas hook kinds in Phase 3 (`overlay`, `tool`, `snap`) are a starting set. Phase 11 adds one (`registerRecordMask`) and moves the existing point snapping into a snap source. A phase may add a hook kind in its Step 0; it may not reach around the hooks.
- `F3`, `F6`, `F7` and `F10` may be taken by Windows or the web view before the app sees them (the app uses only `F1` and `F2` today). Phase 11's preflight tests this and falls back to the free list above.
- Phase 9's photo-stitch `tone` pattern is an open-kind pattern, not a rows-kind one: its rows bend with the picture.
- Phase 10 replaces "Browse designs" (F-207 is marked superseded, not deleted) and its Track D reads the sewing estimate from PR #23.
- `digitize/fills/lattice.py` is shared by Phase 7 (blackwork) and Phase 8 (lace). Whichever is built first creates it; each spec says so.
- Phase 7 adds an optional `recs` field to `LineStyle` (French knots need jumps, which a list of points cannot carry).
- Phase 6 and Phase 8 both edit the top of `satin_from_pairs` (hand-sewn look and End trim; puff). Phase 8's Step 0 adds a hand-off there, so build 6 before 8 as the index says.
- Phase 8's multi-position hoop spacing (36 mm) is worked out from the hoop's size, not read from a manual. It ships marked unverified until the owner checks the hoop's own sheet.
- In `PLAN.md`, Phase 3's seam items are grouped by track (P3-A, P3-B, P3-C), and P5-C2 (a look inside BX fonts) has no checkbox because it ships no code and is skipped by default.
