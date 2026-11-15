/**
 * Every dialog can be moved by dragging its title, so it never hides the part of the design you're
 * looking at (matching a thread to a color, say); a dialog that starts with tabs is dragged by the
 * empty part of its tab bar. Esc while dragging puts it back (and leaves the dialog open). Dialogs
 * open in the middle again next time.
 */

/** The part of a dialog that drags it: its title, or the empty strip of a leading tab bar. */
export function dragHandle(target: EventTarget | null): Element | null {
  if (!target || typeof (target as Element).closest !== "function") return null;
  const t = target as Element;
  const title = t.closest("dialog.modal > h2:first-child");
  if (title) return title;
  return t.matches("dialog.modal > .tabs:first-child") ? t : null;
}

export function startDialogDragging(): () => void {
  const onDown = (e: PointerEvent) => {
    const title = dragHandle(e.target);
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
      // No button down: the mouse came up where we didn't hear it, so the drag is over.
      if (ev.buttons === 0) return stop();
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
      window.removeEventListener("pointercancel", stop);
      window.removeEventListener("blur", stop);
      window.removeEventListener("keydown", onKey, true);
    };
    // Esc while dragging puts the dialog back where it was; it doesn't close it. (The app's own
    // Esc handling leaves dialogs alone, so this listens first.)
    const onKey = (ev: KeyboardEvent) => {
      if (ev.key !== "Escape") return;
      ev.preventDefault();
      ev.stopPropagation();
      place(ox, oy);
      stop();
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    window.addEventListener("blur", stop);
    window.addEventListener("keydown", onKey, true);
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
  window.addEventListener("wheel", onDialogWheel, { capture: true, passive: false });
  return () => {
    window.removeEventListener("pointerdown", onDown);
    document.removeEventListener("close", onClose, true);
    window.removeEventListener("wheel", onDialogWheel, { capture: true });
  };
}

/** The scrollable box a wheel turn over `el` should move: the nearest one inside the dialog that
 *  can still go that way (a long list first, then the dialog itself). */
export function wheelScroller(el: Element | null, dialog: Element, dy: number): Element | null {
  for (let x = el; x; x = x.parentElement) {
    const oy = getComputedStyle(x).overflowY;
    if ((oy === "auto" || oy === "scroll") && x.scrollHeight > x.clientHeight + 1) {
      const room = dy > 0 ? x.scrollHeight - x.clientHeight - x.scrollTop : x.scrollTop;
      if (room > 0.5) return x;
    }
    if (x === dialog) break;
  }
  return null;
}

/** The mouse wheel scrolls an open dialog (a tall one in a small window, like Settings): the
 *  WebView didn't always hand the wheel to a dialog, leaving its bottom out of reach. */
function onDialogWheel(e: WheelEvent) {
  if (e.defaultPrevented || e.ctrlKey) return;
  const t = e.target instanceof Element ? e.target : null;
  const dialog = t?.closest("dialog[open]");
  if (!dialog || !t) return;
  // A number field being typed in keeps the wheel's own meaning.
  if (t.matches("input[type=number]:focus")) return;
  const lines = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? dialog.clientHeight : 1;
  const dy = e.deltaY * lines;
  if (!dy) return;
  const box = wheelScroller(t, dialog, dy);
  e.preventDefault();
  box?.scrollBy({ top: dy });
}
