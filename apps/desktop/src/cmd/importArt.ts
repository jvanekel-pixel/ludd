/** Importing vector artwork (SVG, DXF, PDF) as editable shapes. */
import { registerCommands } from "../commands";
import { ImportArtDialog } from "../components/ImportArtDialog";
import { registerDialog } from "../dialogs";
import { importArtwork } from "../feat/importArt";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerDialog("importArt", ImportArtDialog);

registerCommands([
  { id: "file.importArt", title: "Import artwork (SVG, DXF, PDF)…", shortcut: "Mod+Alt+I", run: () => void importArtwork(), enabled: engineReady },
]);
