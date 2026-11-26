/**
 * Motifs: the built-in ones and your own, kept by the engine in LUDD's data folder (methods
 * motifs.*). A shape that uses one of yours carries a copy of it, so it sews anywhere.
 */
import { useStore } from "../store";

/** Alt+Shift+M: the Motifs window. */
export const openMotifs = () => useStore.getState().setDialog("motifs");
