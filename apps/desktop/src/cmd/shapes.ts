/** The shapes added after the rectangle, circle and star, and the polygon's dialog. */
import { addShape } from "../actions";
import { registerCommands } from "../commands";
import { PolygonDialog } from "../components/PolygonDialog";
import { registerDialog } from "../dialogs";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerDialog("polygon", PolygonDialog);

registerCommands([
  { id: "shape.roundedRect", title: "Add a rounded rectangle", shortcut: "Mod+Alt+4", run: () => void addShape("roundedRect"), enabled: engineReady },
  { id: "shape.ellipse", title: "Add an oval", shortcut: "Mod+Alt+5", run: () => void addShape("ellipse"), enabled: engineReady },
  { id: "shape.triangle", title: "Add a triangle", shortcut: "Mod+Alt+6", run: () => void addShape("triangle"), enabled: engineReady },
  { id: "shape.polygon", title: "Add a polygon", shortcut: "Mod+Alt+7", run: () => useStore.getState().setDialog("polygon"), enabled: engineReady },
  { id: "shape.heart", title: "Add a heart", shortcut: "Mod+Alt+8", run: () => void addShape("heart"), enabled: engineReady },
]);
