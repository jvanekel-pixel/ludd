/** Names from a list (text.names): placeholders filled row by row, and name templates
 *  (text.saveTemplate). */
import { currentLayout, info } from "../actions";
import { useStore } from "../store";

export function canSaveTemplate(): boolean {
  return useStore.getState().engine !== null && !!currentLayout()?.items.some((it) => it.kind === "text");
}

export async function saveTemplate(): Promise<void> {
  info("Saving name templates isn't built yet.");
}
