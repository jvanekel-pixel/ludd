/**
 * Every dialog can be moved by dragging its title, so it never hides the part of the design you're
 * looking at (matching a thread to a color, say). Esc while dragging puts it back. Dialogs open in
 * the middle again next time.
 */
import { holdEscape } from "./escape";

export function startDialogDragging(): () => void {
  const onDown = (e: PointerEvent) => {
    const title = e.target instanceof Element ? e.target.closest("dialog.modal > h2:first-child") : null;
    if (!title || e.button !== 0) return;
    const dialog = title.parentElement as HTMLDialogElement;
    e.preventDefault();
    const [x0, y0] = [e.clientX, e.clientY];
    const [ox, oy] = [Number(dialog.dataset.dx ?? 0), Number(dialog.dataset.dy ?? 0)];
    const place = (dx: number, dy: number) => {
      dialog.dataset.dx = String(dx);
      dialog.dataset.dy = String(dy);
      dialog.style.translate = `${dx}px ${dy}px`;
    };
    const move = (ev: PointerEvent) => {
      // Keep the title on screen.
      const r = dialog.getBoundingClientRect();
      const dx = ox + ev.clientX - x0;
      const dy = oy + ev.clientY - y0;
      const minX = ox - (r.left + r.width - 80);
      const maxX = ox + (window.innerWidth - r.left - 80);
      const minY = oy - r.top;
      const maxY = oy + (window.innerHeight - r.top - 40);
      place(Math.min(maxX, Math.max(minX, dx)), Math.min(maxY, Math.max(minY, dy)));
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      release();
    };
    const release = holdEscape(() => {
      place(ox, oy);
      stop();
    });
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  };
  // Back to the middle whenever a dialog closes.
  const onClose = (e: Event) => {
    const d = e.target as HTMLElement;
    if (d instanceof HTMLDialogElement) {
      delete d.dataset.dx;
      delete d.dataset.dy;
      d.style.translate = "";
    }
  };
  window.addEventListener("pointerdown", onDown);
  document.addEventListener("close", onClose, true);
  return () => {
    window.removeEventListener("pointerdown", onDown);
    document.removeEventListener("close", onClose, true);
  };
}
