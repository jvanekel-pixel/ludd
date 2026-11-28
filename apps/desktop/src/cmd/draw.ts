/** Drawing tools: freehand drawing and stitch presets. */
import "../canvas/freehandTool"; // the canvas side of freehand drawing
import { registerCommands } from "../commands";
import { PresetsDialog } from "../components/PresetsDialog";
import { registerDialog } from "../dialogs";
import { toggleFreehand } from "../feat/freehand";
import { openPresets } from "../feat/presets";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerDialog("presets", PresetsDialog);

registerCommands([
  { id: "tool.freehand", title: "Draw freehand", shortcut: "Y", run: toggleFreehand, enabled: engineReady },
  { id: "presets.open", title: "Stitch presets…", shortcut: "Alt+P", run: openPresets, enabled: engineReady },
]);
