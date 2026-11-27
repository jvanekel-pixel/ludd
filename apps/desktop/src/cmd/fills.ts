/** Fill commands: another angle line (a turning fill), carving lines into a fill, and the Motifs
 *  window. */
import { registerCommands } from "../commands";
import { MotifDialog } from "../components/MotifDialog";
import { registerDialog } from "../dialogs";
import { startAddAngle } from "../feat/angleLines";
import { startCarve } from "../feat/carve";
import { openMotifs } from "../feat/motifs";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

/** A drawn fill selected, with no shape half drawn. */
const fillSelected = () => {
  const s = useStore.getState();
  const it = s.history.present?.layout.items.find((x) => x.id === s.selectedId);
  return engineReady() && !s.pen && it?.kind === "fill";
};

registerDialog("motifs", MotifDialog);

registerCommands([
  { id: "object.addAngle", title: "Add another angle line (a turning fill)", shortcut: "Shift+I", run: () => startAddAngle(), enabled: fillSelected },
  { id: "object.carve", title: "Carve lines into the fill (grooves)", shortcut: "Shift+C", run: () => startCarve(), enabled: fillSelected },
  { id: "motif.library", title: "Motifs…", shortcut: "Alt+Shift+M", run: () => openMotifs(), enabled: engineReady },
]);
