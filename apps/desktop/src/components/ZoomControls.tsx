import { command } from "../actions";
import { formatShortcut } from "../commands";
import { zoomPercent } from "../design/grid";
import { useStore } from "../store";

/** − 100% + Fit, bottom-right of the canvas. Clicking the percentage goes to real size. */
export function ZoomControls() {
  const scale = useStore((s) => s.zoomScale);
  const tip = (id: string) => `${command(id).title} (${formatShortcut(command(id).shortcut)})`;
  return (
    <div className="zoom-controls" role="group" aria-label="Zoom">
      <button onClick={() => command("view.zoomOut").run()} title={tip("view.zoomOut")} aria-label="Zoom out">
        −
      </button>
      <button className="pct" onClick={() => command("view.zoomActual").run()} title={tip("view.zoomActual")}>
        {zoomPercent(scale)}%
      </button>
      <button onClick={() => command("view.zoomIn").run()} title={tip("view.zoomIn")} aria-label="Zoom in">
        +
      </button>
      <button onClick={() => command("view.fit").run()} title={tip("view.fit")}>
        Fit
      </button>
    </div>
  );
}
