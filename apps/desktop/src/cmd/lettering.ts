/** Lettering and personalization: single letters, stitch fonts from letter files, name
 *  templates and placement guides. */
import { registerCommands } from "../commands";
import { FontFromFilesDialog } from "../components/FontFromFilesDialog";
import { PlacementDialog } from "../components/PlacementDialog";
import { registerDialog } from "../dialogs";
import { canAdjustLetters, hasLetterEdits, resetLetters, toggleLetterMode } from "../feat/letters";
import { canSaveTemplate, saveTemplate } from "../feat/names";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerDialog("fontFromFiles", FontFromFilesDialog);
registerDialog("placement", PlacementDialog);

registerCommands([
  { id: "text.letters", title: "Adjust single letters", shortcut: "Alt+Shift+A", run: toggleLetterMode, enabled: canAdjustLetters },
  { id: "text.resetLetters", title: "Put the letters back", shortcut: "Alt+Shift+Z", run: resetLetters, enabled: hasLetterEdits },
  { id: "text.fontFromFiles", title: "Make a stitch font from letter files…", shortcut: "Mod+Alt+F", run: () => useStore.getState().setDialog("fontFromFiles"), enabled: engineReady },
  { id: "text.saveTemplate", title: "Save this layout as a name template…", shortcut: "Mod+Alt+P", run: () => void saveTemplate(), enabled: canSaveTemplate },
  { id: "text.placement", title: "Placement guides…", shortcut: "Alt+Shift+G", run: () => useStore.getState().setDialog("placement") },
]);
