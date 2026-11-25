/** Needle path view (P4-B5): thread as hairlines with a dot at every needle point. A view switch,
 *  remembered (components/StitchCanvas.tsx draws it). */
import { useStore } from "../store";

export const toggleWireframe = (): void => useStore.getState().toggleWire();
