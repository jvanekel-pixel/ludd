import { useEffect, useRef, useState } from "react";
import { holdEscape } from "../escape";
import { loadPrefs, savePrefs } from "../prefs";

export const PANEL_MIN = 260;
export const PANEL_DEFAULT = 300;
/** The panel can take up to this share of the window, so the design always stays in view. */
const PANEL_MAX_SHARE = 0.6;

export const clampPanel = (w: number, windowWidth: number) => Math.round(Math.min(Math.max(w, PANEL_MIN), Math.max(PANEL_MIN, windowWidth * PANEL_MAX_SHARE)));

/** The right panel's width: dragged with the handle, remembered between sessions. */
export function usePanelWidth(): [number, (w: number) => void] {
  const [w, setW] = useState(() => clampPanel(loadPrefs().panelWidth ?? PANEL_DEFAULT, window.innerWidth));
  useEffect(() => {
    const onResize = () => setW((v) => clampPanel(v, window.innerWidth));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return [w, setW];
}

/** A grip on the panel's left edge: drag to resize, double-click to reset, Esc while dragging puts it back. */
export function PanelResizer({ width, onWidth }: { width: number; onWidth: (w: number) => void }) {
  const [dragging, setDragging] = useState(false);
  const widthRef = useRef(width);
  widthRef.current = width;

  // Remember the width once a drag ends.
  useEffect(() => {
    if (!dragging) savePrefs({ panelWidth: width });
  }, [dragging, width]);

  return (
    <div
      className={`panel-resizer${dragging ? " active" : ""}`}
      role="separator"
      aria-orientation="vertical"
      aria-label="Panel width: drag to resize"
      aria-valuenow={width}
      tabIndex={0}
      title="Drag to make the panel wider or narrower; double-click to reset"
      onPointerDown={(e) => {
        e.preventDefault();
        const x0 = e.clientX;
        const w0 = widthRef.current;
        // Listeners and the Esc hold are set up and torn down together, so a quick click (or a
        // double-click) can never leave Esc pointing at a finished drag.
        // A move with no button down means the mouse came up where we didn't hear it: the drag is over.
        const move = (ev: PointerEvent) => (ev.buttons === 0 ? stop() : onWidth(clampPanel(w0 + (x0 - ev.clientX), window.innerWidth)));
        const stop = () => {
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", stop);
          window.removeEventListener("pointercancel", stop);
          window.removeEventListener("blur", stop);
          release();
          setDragging(false);
        };
        const release = holdEscape(() => {
          onWidth(w0);
          stop();
        });
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", stop);
        window.addEventListener("pointercancel", stop);
        window.addEventListener("blur", stop);
        setDragging(true);
      }}
      onDoubleClick={() => onWidth(clampPanel(PANEL_DEFAULT, window.innerWidth))}
      onKeyDown={(e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        // The arrows resize the panel only: they don't also nudge the selected design.
        e.preventDefault();
        e.stopPropagation();
        onWidth(clampPanel(width + (e.key === "ArrowLeft" ? 20 : -20), window.innerWidth));
      }}
    />
  );
}
