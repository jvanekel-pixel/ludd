# QA phase 4: ui group (live-esc, live-state, UI tests and shortcuts)

## 1. Findings

| Sev | Area | Finding (short) | Outcome | Where fixed | Test |
|---|---|---|---|---|---|
| Medium | live-esc | Window blur mid-drag leaves a stale Esc hold | Fixed | StitchCanvas.tsx `cancelDrag` releases its hold; `onBlur` | none (canvas needs a DOM; reviewed by code) |
| Medium | live-esc | "One file per name" defaults to PES on a JEF machine | Already fixed | FeatureDialogs.tsx `NamesDialog` (format reset on open) | - |
| Medium | live-esc | Knife then tool change / New / Open leaves a stale Esc hold | Fixed | features.ts store subscription releases the knife and stitch-edit holds | ui.qa.test.ts |
| Medium | live-esc | Modal dialog open + focus on body: Esc runs the commands behind it | Fixed | keys.ts (new; App.tsx key handler moved there): skip while any `dialog[open]` | ui.qa.test.ts |
| Medium | live-esc | Stitch-edit mode survives New / Open / deleting the file | Fixed | actions.ts `applyOpen`; store.ts `setHistory` drops modes whose item is gone | ui.qa.test.ts |
| Medium | live-esc | Focused panel edge: arrows resize AND nudge the design | Fixed | PanelResizer.tsx (stopPropagation), keys.ts skips `[role=separator]` | ui.qa.test.ts |
| Medium | live-esc | Wheel zoom during a move/scale/rotate drag misplaces the shape | Fixed | StitchCanvas.tsx: drag keeps the grabbed point in mm (`startW`), ghost placed in mm | none (canvas) |
| Medium | live-esc | No pointer identity: second pointer, other pointer's up, pointercancel commits | Fixed | StitchCanvas.tsx: only `dragPointer` moves/ends a drag; second pointer or cancel reverts via `cancelDrag` | none (canvas) |
| Medium | live-esc | Re-render during a drag drops the drag (C17) | Already fixed | phase 2 | - |
| Medium | live-state | Duplicate copies only the primary of several selected | Fixed | actions.ts `duplicateSelected` | ui.qa.test.ts |
| Medium | live-state | Stitch-edit and knife leak (dead id, live Delete, phantom hold) | Fixed | as the two live-esc items above | ui.qa.test.ts |
| Medium | live-state | Stitch-edit moves stored in world space | Already fixed | features.ts `toDesignFrame` + engine `local` moves | features.qa.test.ts |
| Medium | live-state | One move_stitch op per stitch per drag | Already fixed | another agent: one `move_stitches` op per drag | (theirs) |
| Medium | live-state | Stitch-edit overlay redraws every needle point per move | Fixed | StitchCanvas.tsx `drawStitchEdit`: only points on screen, at most one per 3 px | none (canvas) |
| Medium | live-state | Quality check queues on the serial engine after every edit | Fixed (UI side); engine side handed over | actions.ts `startChecks`: never starts while an edit renders or waits, one check at a time | - |
| Medium | live-state | Engine death: no restart | Already fixed | C25 (phase 3) | - |
| Medium | live-state | Lettering box reverts keystrokes while an update lands | Already fixed | TextPanel.tsx (lettering agent) | - |
| Medium | live-state | Clearing a number box commits 0 | Fixed | InfoPanel.tsx `NumberField`: empty box puts the old value back | none (component) |
| Medium | live-state | Design browser: slower earlier scan overwrites the newer folder | Fixed | FeatureDialogs.tsx `BrowseDialog` scan counter | none (component) |
| Medium | live-state | Autosave off while the recovery banner is unanswered | Handed over: engine/project owner + lead decision | needs a second recovery slot in project.autosave/recovery | - |
| Medium | live-state | Edits from a stale snapshot lose a concurrent edit (Delete, Sew earlier/later, shortest order) | Fixed | actions.ts `removeSelected`, new `reorderItem`; features.ts `shortestOrder` applies the order to the newest layout | ui.qa.test.ts |
| Medium | live-state | Failed newest render throws away an earlier edit that worked; overtaken commits skip follow-ups | Fixed | actions.ts `runRender` shows an overtaken reply that worked; overtaken edits resolve with the final result | ui.qa.test.ts |
| Medium | live-state | Recover claims success when the design can't be shown; copy then deleted | Fixed | actions.ts `restoreRecovery` returns ok; App.tsx keeps the banner on failure | ui.qa.test.ts |
| Medium | live-state | Success messages shown when the edit failed | Fixed (features.ts, actions.ts); autoTrace.ts handed over | `acceptWholePicture` (preview kept until added), `addOffset`, `finishKnife`, `mergeSelected`, `shortestOrder`, `saveColorway`, `textOnLine`, `groupSelection`; `addTraced` returns ok | covered by the overlap tests only |
| Medium | live-state | Quick repeated Rotate/Mirror/Scale of several things scatters the group | Fixed | actions.ts `selectionGeometry` shifts rendered bounds by moves made since; unrendered shapes use their points | ui.qa.test.ts |
| Medium | live-state | Tool switch leaves hidden selected ids | Fixed | store.ts `setTool` clears extraIds and selectedNode | ui.qa.test.ts |
| Low | live-esc | Esc auto-repeat releases several things | Fixed | keys.ts ignores `e.repeat` | ui.qa.test.ts |
| Low | live-esc | Space on a focused role=button name also plays | Fixed | keys.ts | ui.qa.test.ts |
| Low | live-esc | Esc in the lettering box doesn't bring back the text from before typing | Handed over: lettering | TextPanel.tsx | - |
| Low | live-esc | Esc in an AI-settings box saves the half-typed value | Handed over: AISettings owner | AISettings.tsx | - |
| Low | live-esc | Click that closes a menu / font list also acts on the canvas | Fixed (Menu); FontPicker handed over: lettering | Menu.tsx closes in the capture phase and stops the click reaching the canvas | none (component) |
| Low | live-esc | Auto-pan keeps scrolling after the window loses focus | Fixed | StitchCanvas.tsx `onBlur` stops auto-pan | none (canvas) |
| Low | live-esc | One Esc reverts a field and also drops a held mode | Fixed (InfoPanel); TextPanel handed over: lettering | InfoPanel.tsx number boxes and rename leave Esc to a held thing first (`heldCount()`) | ui.qa.test.ts (order) |
| Low | live-esc | Snap to grid makes points ignore guides | Fixed | StitchCanvas.tsx `snapped`: a guide wins on its axis, grid on the other | none (canvas) |
| Low | live-esc | Dialog drag: Esc closes instead of putting back; charts dialog can't be dragged | Fixed | dragDialogs.ts (Esc listener while dragging; drag by the empty part of a leading tab bar), styles.css | ui.qa.test.ts (`dragHandle`) |
| Low | live-esc | Export/Batch busy guard defeated by a second Esc | Handed over: layout agent | ExportDialog/BatchDialog | - |
| Low | live-esc | Panel resizer / dialog drags keep following after blur, cancel, lost mouse-up | Fixed | PanelResizer.tsx, dragDialogs.ts (buttons===0, blur, pointercancel) | none (DOM) |
| Low | live-state | No-op edits add undo steps and mark the design changed | Fixed | actions.ts `commitDoc`/`commitImages` skip content-equal docs; InfoPanel opacity slider compares | ui.qa.test.ts |
| Low | live-state | Close/New/Open ignore an edit still rendering | Fixed | actions.ts `confirmDiscard` checks the newest version; `saveProject` waits (`whenIdle`) | ui.qa.test.ts |
| Low | live-state | After Save the title keeps the old name | Fixed | actions.ts `saveProject` sets the title (no undo step, not dirty) | ui.qa.test.ts |
| Low | live-state | Drawing tool chosen with no design resets to Select | Fixed | actions.ts `tool()` starts the design first | ui.qa.test.ts |
| Low | live-state | Per-document UI state outlives its document (trace guess, advisor, pen points) | Fixed | store.ts `setHistory` (autoTrace/autoAll of a removed picture), actions.ts `applyOpen` (advice), `penFinish` keeps points on failure | ui.qa.test.ts (pen) |
| Low | live-state | Missing project reported as damaged | Already fixed | project.py ("Couldn't find ...") | - |
| Low | live-state | One file per name overwrites colliding names | Already fixed | features.ts `exportNames` (another agent) | (theirs) |
| Low | live-state | player.faster / player.slower registered twice | Fixed | actions.ts: second pair is `player.fasterAlt` / `player.slowerAlt` | ui.qa.test.ts (registry) |
| Low | live-state | Extra colour change in the preview after deleting a colour's stitches | Already fixed | C4; checked: Flower.pes, block 0 deleted: colors 3, color_changes 2 | - |
| Medium | tests | Alt shortcuts can't match on macOS (Option changes `key`) | Fixed | commands.ts `matchesShortcut` falls back to `e.code` for Alt shortcuts | ui.qa.test.ts |
| Medium | tests | New UI has almost no tests; vitest has no DOM | Partly fixed | ui.qa.test.ts (23 tests, fake engine); key handler moved to keys.ts so it is testable without a DOM. jsdom not added (no installs in this phase) | - |
| Low | tests | No registry invariant test; duplicate ids | Fixed | ui.qa.test.ts: unique ids, every command has a shortcut | ui.qa.test.ts |

## 2. Changelog lines
- Esc: holding the key down lets go of one thing, not several; Esc while a dialog is open only closes the dialog; a window switch mid-drag no longer makes the next Esc do nothing; the knife and stitch editing always give Esc back when they end.
- Stitch editing ends when its design is deleted or another design is opened.
- Duplicate (Ctrl+D) copies everything selected.
- Quick edits in a row no longer lose each other: Delete, Sew earlier/later and Sew in the shortest order keep an edit that was still updating, and an edit that worked is kept even if the next one fails.
- Turning or flipping several things twice quickly lands where two slow presses would.
- A change that changes nothing (tabbing past a slider, a value set to what it was) is no longer an undo step or an unsaved change.
- Closing or opening asks about an edit that is still updating; Save waits for it.
- After Save as, the window title shows the new name.
- Recover only says "recovered" when the work is back; otherwise the banner stays and the copy is kept.
- Messages like "Merged into one shape" or "Added N shapes" only appear when it worked; the whole-picture preview stays if adding failed.
- Choosing a drawing tool before there is a design keeps that tool.
- A shape that can't be made keeps its clicked points.
- Emptying a number box puts the old value back (it no longer moves the design to 0).
- Design browser: choosing a second folder while the first is still being read shows the right folder.
- Arrow keys on the panel edge only resize the panel; Space on a focused name doesn't start the stitch-out.
- Zooming during a drag keeps the shape under the pointer; a second finger or a cancelled touch puts the drag back.
- Points snap to guides also with Snap to grid on.
- Switching windows stops drawing auto-scroll and ends panel and dialog drags.
- A click that closes a menu no longer also draws or selects on the design.
- Esc while dragging a dialog puts it back; My threads can be dragged by its tab bar.
- Stitch editing stays smooth on very large stitch files.
- Option-key shortcuts (Alt+A, Alt+H, Alt+V, Alt+D, Alt+[ ]) work on a Mac.
- Quality checks no longer hold up edits.

## 3. Manual changes needed
- Snap/guides (USER-MANUAL.md around line 140): with Snap to grid on, a point near a guide lands on the guide (the grid still applies on the other axis).
- If the manual lists commands by id or shows "[" / "]" twice for playback speed: the second pair is now separate commands (same keys).
- Dialogs: "drag a dialog by its title" also holds for My threads & charts (drag the empty part of its tab bar); Esc while dragging puts it back without closing.

## 4. Stitch output changed
None.

## 5. Handed over
- **lettering (TextPanel.tsx)**: (a) Esc in the text box should restore the text from when the box was focused (remember it on focus; on Esc call setText with it if different). (b) In the text box's Esc handler, do nothing when `heldCount() > 0` (from ../escape), so a held mode is let go first, as InfoPanel now does. (c) FontPicker: close on pointerdown in the capture phase and `stopPropagation()` when the target is inside `.stitch-canvas` (see Menu.tsx).
- **AISettings owner**: Field saves on blur, so Esc (dialog close blurs) saves a half-typed value. Handle Escape in Field: reset the value and set a flag that onBlur checks.
- **layout agent (ExportDialog/BatchDialog)**: `onCancel={(e) => busy && e.preventDefault()}` is beaten by a second Esc (Chromium sends the second cancel uncancelable). While busy, also preventDefault Escape in the dialog's onKeyDown, or reopen from onClose.
- **autotrace agent (autoTrace.ts `acceptGuess`)**: dismisses the guess and shows its info before knowing the commit worked; gate on `await addTraced(...)` (it now returns true/false) and dismiss only on success.
- **engine (methods.py / layout.py)**: `layout.check` still runs inline on the serial loop and costs about 2x a render; once started it delays the next render. Consider `background=True` (if the layout caches are thread-safe) or reusing the render's result. The UI now never starts a check while an edit is rendering or waiting.
- **engine project + lead decision**: autosave stays off while the recovery banner is unanswered. Needs a second recovery slot (`project.autosave` with a slot, `project.recovery` listing both); then actions.ts `startAutosave` can write to it while `recoveryWaiting`.

## Notes
- Tests: `corepack pnpm exec vitest run src/ui.qa.test.ts` 23/23 pass; typecheck clean. Full vitest run: one failure in src/design/layout.test.ts ("jumps-to-trims is one setting across designs"), in another agent's area (I didn't touch design/layout.ts).
- Canvas changes (StitchCanvas.tsx) have no unit tests: vitest has no DOM and PixiJS needs one. The preview had no design open, and making one would have changed the shared preview, so I didn't drive it.
- keys.ts is new: App.tsx's `useShortcuts` now only wires `onKeyDown` / `onKeyUp` / `onWindowBlur` from it.
