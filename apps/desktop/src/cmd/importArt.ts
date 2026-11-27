/** Importing vector artwork (SVG, DXF, PDF) as editable shapes. */
import { registerCommands } from "../commands";
import { importArtwork } from "../feat/importArt";
import { useStore } from "../store";

const engineReady = () => useStore.getState().engine !== null;

registerCommands([
  { id: "file.importArt", title: "Import artwork (SVG, DXF, PDF)…", shortcut: "Mod+Alt+I", run: importArtwork, enabled: engineReady },
]);
