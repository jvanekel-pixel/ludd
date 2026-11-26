/** Adjusting single letters (text.letters): the dots on the letters, picking, dragging and
 *  nudging one, and what a color chosen in Order & colors does to a text's color runs.
 *
 *  actions.ts calls nudgeLetter, recolorRuns and pruneLetterEdits; the canvas hides a text's
 *  start and end dots, and redraws, when useLetterMode changes. Nothing here may call actions.ts
 *  while the module loads (the two import each other). */
import { create } from "zustand";
import { currentLayout, info, targetId } from "../actions";
import { recolor } from "../design/layout";
import type { Design, Layout, TextItem, Thread } from "../design/types";
import { useStore } from "../store";

/** Single-letter mode: the text whose letters are being adjusted and the letter picked. */
export type LetterMode = { id: string | null; letter: number | null };
export const useLetterMode = create<LetterMode>(() => ({ id: null, letter: null }));

function selectedText(): TextItem | null {
  if (useStore.getState().extraIds.length) return null;
  const it = currentLayout()?.items.find((x) => x.id === targetId());
  return it?.kind === "text" ? it : null;
}

export function canAdjustLetters(): boolean {
  const text = selectedText();
  return !!text && !text.locked && useStore.getState().engine !== null;
}

export const hasLetterEdits = (): boolean => Object.keys(selectedText()?.letter_edits ?? {}).length > 0;

export function toggleLetterMode(): void {
  info("Adjusting single letters isn't built yet.");
}

export function resetLetters(): void {
  info("Adjusting single letters isn't built yet.");
}

/** An arrow key while a letter is picked: true if the letter took it. */
export function nudgeLetter(_dx: number, _dy: number): boolean {
  return false;
}

/** The layout with `thread` chosen in Order & colors (null: back to as it was) for the color
 *  blocks `sources`. `design` is the design as drawn, whose items say what each run holds. */
export function recolorRuns(layout: Layout, sources: { item: number; block: number }[], thread: Thread | null, _design: Design | null): Layout {
  return recolor(layout, sources, thread);
}

/** A text whose words changed, without the changes to letters it no longer has. */
export function pruneLetterEdits(item: TextItem): TextItem {
  return item;
}
