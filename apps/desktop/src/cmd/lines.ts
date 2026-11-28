/** Small objects made from a few sizes: buttonholes and eyelets, and their dialogs. */
import { registerCommands } from "../commands";
import { ButtonholeDialog, EyeletDialog } from "../components/SmallObjectDialog";
import { registerDialog } from "../dialogs";
import { openButtonhole, openEyelet } from "../feat/smallObjects";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerDialog("buttonhole", ButtonholeDialog);
registerDialog("eyelet", EyeletDialog);

registerCommands([
  { id: "object.buttonhole", title: "Add a buttonhole", shortcut: "Alt+B", run: openButtonhole, enabled: engineReady },
  { id: "object.eyelet", title: "Add an eyelet", shortcut: "Alt+E", run: openEyelet, enabled: engineReady },
]);
