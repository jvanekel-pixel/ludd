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
  const start = useRef<{ x: number; w: number; release: () => void } | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!dragging) return;
    const move = (e: PointerEvent) => {
      const s = start.current;
      if (s) onWidth(clampPanel(s.w + (s.x - e.clientX), window.innerWidth));
    };
    const up = () => {
      start.current?.release();
      start.current = null;
      setDragging(false);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [dragging, onWidth]);

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
        const w0 = width;
        start.current = {
          x: e.clientX,
          w: w0,
          release: holdEscape(() => {
            onWidth(w0);
            start.current = null;
            setDragging(false);
          }),
        };
        setDragging(true);
      }}
      onDoubleClick={() => onWidth(clampPanel(PANEL_DEFAULT, window.innerWidth))}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") onWidth(clampPanel(width + 20, window.innerWidth));
        if (e.key === "ArrowRight") onWidth(clampPanel(width - 20, window.innerWidth));
      }}
    />
  );
}
