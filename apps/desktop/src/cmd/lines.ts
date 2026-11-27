/** Small objects made from a few sizes: buttonholes and eyelets. */
import { registerCommands } from "../commands";
import { openButtonhole, openEyelet } from "../feat/smallObjects";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerCommands([
  { id: "object.buttonhole", title: "Add a buttonhole", shortcut: "Alt+B", run: openButtonhole, enabled: engineReady },
  { id: "object.eyelet", title: "Add an eyelet", shortcut: "Alt+E", run: openEyelet, enabled: engineReady },
]);
