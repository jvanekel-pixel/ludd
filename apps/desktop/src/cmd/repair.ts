/** Merge-safe stitch files: repairs, stitch inserts, "Don't sew what's hidden" and the needle
 *  path view. */
import { registerCommands } from "../commands";
import { RepairDialog } from "../components/RepairDialog";
import { registerDialog } from "../dialogs";
import { toggleRemoveOverlap } from "../feat/overlap";
import { declump } from "../feat/repair/clumps";
import { densityLimit } from "../feat/repair/density";
import { removeHidden } from "../feat/repair/hidden";
import { rebuild } from "../feat/repair/rebuild";
import { openRepair } from "../feat/repair/steps";
import { filterSmall } from "../feat/repair/tiny";
import { insertJump, insertStitch, lockJump } from "../feat/stitchInsert";
import { toggleWireframe } from "../feat/wireframe";
import { useStore } from "../store";

const hasDesign = () => useStore.getState().design !== null;
const canEdit = () => hasDesign() && useStore.getState().engine !== null;
// Only while editing stitches, so Shift+Insert still pastes everywhere else.
const editingStitches = () => canEdit() && useStore.getState().stitchEdit !== null;

registerDialog("repair", RepairDialog);

registerCommands([
  { id: "stitch.repair", title: "Repair this design…", shortcut: "Mod+Alt+D", run: () => openRepair(), enabled: canEdit },
  { id: "stitch.removeHidden", title: "Remove stitches hidden under what's on top", shortcut: "Alt+Shift+H", run: () => removeHidden(), enabled: canEdit },
  { id: "stitch.declump", title: "Thin out dense spots", shortcut: "Alt+Shift+D", run: () => declump(), enabled: canEdit },
  { id: "stitch.filterSmall", title: "Remove tiny stitches", shortcut: "Alt+Shift+S", run: () => filterSmall(), enabled: canEdit },
  { id: "stitch.densityLimit", title: "Limit density for this fabric", shortcut: "Alt+Shift+L", run: () => densityLimit(), enabled: canEdit },
  { id: "stitch.rebuild", title: "Rebuild stitches at this size", shortcut: "Alt+Shift+R", run: () => rebuild(), enabled: canEdit },
  { id: "stitch.insert", title: "Insert a stitch here", shortcut: "Insert", run: () => insertStitch(), enabled: editingStitches },
  { id: "stitch.insertJump", title: "Insert a jump here", shortcut: "Shift+Insert", run: () => insertJump(), enabled: editingStitches },
  { id: "stitch.lockJump", title: "Lock both sides of this jump", shortcut: "Alt+Shift+T", run: () => lockJump(), enabled: editingStitches },
  { id: "object.removeOverlap", title: "Remove stitching hidden under shapes on top", shortcut: "Alt+Shift+O", run: () => toggleRemoveOverlap(), enabled: canEdit },
  { id: "view.wireframe", title: "Needle path only", shortcut: "Shift+P", run: () => toggleWireframe(), enabled: hasDesign },
]);
