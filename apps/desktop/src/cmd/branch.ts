/** Branching: sew the selected shapes as one path, or take shapes out of their branch. */
import "../canvas/branchOverlay"; // the branch's dots, registered when the app loads
import { registerCommands } from "../commands";
import { branchSelected, unbranchSelected } from "../feat/branch";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerCommands([
  { id: "layout.branch", title: "Branch: sew the selected shapes as one path", shortcut: "Alt+Shift+B", run: branchSelected, enabled: engineReady },
  { id: "layout.unbranch", title: "Take the selected shapes out of their branch", shortcut: "Alt+Shift+U", run: unbranchSelected, enabled: engineReady },
]);
