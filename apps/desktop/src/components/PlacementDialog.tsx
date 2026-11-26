/** "Placement guides…" (text.placement): where a design goes on common things. */
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

export function PlacementDialog() {
  const ref = useModal(true);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="placement-title">
      <h2 id="placement-title">Placement guides</h2>
      <p className="hint">Not built yet.</p>
      <div className="actions">
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
