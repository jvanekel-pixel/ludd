/** "Make a stitch font from letter files…" (text.fontFromFiles). */
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

export function FontFromFilesDialog() {
  const ref = useModal(true);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="font-files-title">
      <h2 id="font-files-title">Make a stitch font from letter files</h2>
      <p className="hint">Not built yet.</p>
      <div className="actions">
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
