/** The Motifs window (Alt+Shift+M): the built-in motifs and your own. */
import { useEffect, type KeyboardEvent } from "react";
import { holdEscape, letGoNewest } from "../escape";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

export function MotifDialog() {
  const ref = useModal(true);
  // Esc closes it through the app's one list of things Esc lets go of.
  useEffect(() => holdEscape(close), []);

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    if (!e.repeat) letGoNewest();
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} onKeyDown={onKeyDown} aria-labelledby="motifs-title">
      <h2 id="motifs-title">Motifs</h2>
      <p className="hint">Not built yet.</p>
      <div className="actions">
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
