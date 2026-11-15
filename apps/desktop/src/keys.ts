/**
 * The app's keyboard handler: shortcuts from the command registry, Esc letting go of one thing
 * per press (see escape.ts), and Space as play / pause or the hand tool (see spacePan.ts).
 * Kept apart from App.tsx so it can be tested without a browser.
 */
import { COMMANDS } from "./actions";
import { dispatchKey } from "./commands";
import { letGoNewest } from "./escape";
import { spaceDown, spaceUp } from "./spacePan";

/** The focused element, if the event came from one (tests pass plain objects). */
function targetOf(e: KeyboardEvent): Element | null {
  const t = e.target as Element | null;
  return t && typeof t.closest === "function" ? t : null;
}

const doc = () => (typeof document === "undefined" ? null : document);

export function onKeyDown(e: KeyboardEvent) {
  const t = targetOf(e);
  // Open dialogs close themselves on Esc, and keys never reach the design behind one (even
  // when the focus has fallen back to the page, say after a button inside it went away).
  if (t?.closest("dialog") || doc()?.querySelector("dialog[open]")) return;
  const field = t?.closest<HTMLElement>("input:not([type=range]):not([type=checkbox]), select, textarea");
  if (e.key === "Escape") {
    // Esc lets go: first anything held (a drag, an open list), then the field you're typing in
    // (fields put back their old value), then the Escape commands.
    e.preventDefault();
    // Holding Esc down lets go of one thing, not one per key repeat.
    if (e.repeat) return;
    if (letGoNewest()) return;
    if (field) {
      // Number boxes save when you leave them: put the old value back first.
      // (Fields that handle Esc themselves have already let go.)
      if (doc()?.activeElement !== field) return;
      if ((field as HTMLInputElement).type === "number") (field as HTMLInputElement).value = (field as HTMLInputElement).defaultValue;
      return field.blur();
    }
    dispatchKey(e, COMMANDS);
    return;
  }
  // Let text fields keep their own keys, a focused slider its arrows, and a focused
  // button or tick box its Space and Enter.
  if (field) return;
  if (t?.matches("input[type=range]") && /^(Arrow|Home$|End$|Page)/.test(e.key)) return;
  if (t?.matches(":is(button, input[type=checkbox], summary, [role=menuitem], [role=tab], [role=button]):focus-visible") && (e.key === " " || e.key === "Enter")) return;
  // A focused panel edge takes its own arrow keys (it resizes the panel; the design stays put).
  if (t?.matches("[role=separator]") && /^Arrow/.test(e.key)) return;
  // Space: hold to pan, tap to play / pause.
  if (e.key === " " && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    spaceDown();
    return;
  }
  if (dispatchKey(e, COMMANDS)) e.preventDefault();
}

export function onKeyUp(e: KeyboardEvent) {
  if (e.key !== " ") return;
  if (spaceUp()) {
    const play = COMMANDS.find((c) => c.id === "player.toggle");
    if (play && (!play.enabled || play.enabled())) play.run();
  }
}

/** Letting go of the window (Alt+Tab while holding Space) shouldn't leave the hand tool stuck on. */
export function onWindowBlur() {
  spaceUp();
}

/** The bars round the canvas (toolbar, tools, zoom, player, status): a mouse click on one of their
 *  buttons doesn't take the keyboard focus, so the next Enter, Space or Tab still goes to the
 *  drawing (finishing a shape, playing, fitting a satin) instead of pressing that button again.
 *  Keyboard users can still Tab to them. */
export function keepFocusOffBars(e: MouseEvent) {
  const t = e.target instanceof Element ? e.target : null;
  if (t?.closest("button")?.closest(".toolbar, .tool-rail, .zoom-controls, .player, .statusbar")) e.preventDefault();
}
