import { command, penReady } from "../actions";
import { Menu } from "./Menu";
import { formatShortcut } from "../commands";
import { useStore, type Tool } from "../store";

const TOOLS: { id: string; tool: Tool; icon: string; label: string }[] = [
  { id: "tool.select", tool: "select", icon: "➤", label: "Select" },
  { id: "tool.run", tool: "run", icon: "〰", label: "Line" },
  { id: "tool.satin", tool: "satin", icon: "▥", label: "Satin" },
  { id: "tool.fill", tool: "fill", icon: "⬟", label: "Fill" },
  { id: "tool.text", tool: "text", icon: "A", label: "Text" },
];

/** Big, labelled tools down the left: what a beginner needs to start drawing. */
export function ToolRail() {
  const tool = useStore((s) => s.tool);
  const engine = useStore((s) => s.engine);
  return (
    <nav className="tool-rail" aria-label="Tools">
      {TOOLS.map((t) => {
        const c = command(t.id);
        return (
          <button
            key={t.id}
            aria-pressed={tool === t.tool}
            onClick={c.run}
            disabled={c.enabled ? !c.enabled() : false}
            title={`${c.title} (${formatShortcut(c.shortcut)})`}
          >
            <span className="icon" aria-hidden>
              {t.icon}
            </span>
            <span>{t.label}</span>
            <kbd>{formatShortcut(c.shortcut)}</kbd>
          </button>
        );
      })}
      <div className="rail-shapes">
        <Menu
          label="Shapes"
          items={[
            { id: "shape.rectangle", label: "Rectangle" },
            { id: "shape.circle", label: "Circle" },
            { id: "shape.star", label: "Star" },
            "separator",
            { id: "text.monogram", label: "Monogram" },
          ]}
        />
        <span>Shapes</span>
      </div>
      <span className="rail-sep" />
      <button onClick={command("file.picture").run} disabled={!engine} title={`${command("file.picture").title} (${formatShortcut(command("file.picture").shortcut)})`}>
        <span className="icon" aria-hidden>
          🖼
        </span>
        <span>Picture</span>
      </button>
    </nav>
  );
}

const HINTS: Record<Exclude<Tool, "select">, string> = {
  text: "Click where the text should go, then type.",
  run: "Click to place corners; right-click for curves.",
  satin: "Click one side, then the other, then back again, all along the column. Right-click for curves.",
  fill: "Click around the shape's edge; right-click for curves. It closes by itself.",
};

/** What to do next while drawing, in plain words. */
export function DrawHint() {
  const tool = useStore((s) => s.tool);
  const pen = useStore((s) => s.pen);
  const measure = useStore((s) => s.measure);
  const ghost = useStore((s) => s.ghost);
  const step = useStore((s) => s.traceStep);
  if (measure) {
    return (
      <div className="draw-hint" role="status">
        📏 Click two points on the picture whose real distance you know. <kbd>Esc</kbd> cancels.
      </div>
    );
  }
  if (tool === "select") return null;
  if (ghost) {
    return (
      <div className="draw-hint" role="status">
        <kbd>Tab</kbd> takes the suggested point, <kbd>Shift</kbd>+<kbd>Tab</kbd> keeps going
        {ghost.alternatives.length ? (
          <>
            {" "}· fork: <kbd>1</kbd> blue or <kbd>2</kbd> orange
          </>
        ) : null}
        {" "}· <kbd>[</kbd> <kbd>]</kbd> step {step} mm · or just click.
        {penReady() ? <> <kbd>Enter</kbd> finishes.</> : null}
      </div>
    );
  }
  if (tool === "text") {
    return (
      <div className="draw-hint" role="status">
        {HINTS.text} <kbd>Esc</kbd> goes back to Select.
      </div>
    );
  }
  let next = HINTS[tool];
  if (pen && tool === "satin") next = pen.a.length > pen.b.length ? "Now click the other side of the column." : "Next point on the first side.";
  const ready = penReady();
  return (
    <div className="draw-hint" role="status">
      {next} {ready ? <>Press <kbd>Enter</kbd> or double-click to finish.</> : null} <kbd>Backspace</kbd> undoes a point, <kbd>Esc</kbd>{" "}
      {pen ? "cancels" : "goes back to Select"}. Hold <kbd>Shift</kbd> to snap to the grid.
    </div>
  );
}
