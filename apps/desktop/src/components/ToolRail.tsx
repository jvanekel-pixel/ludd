import { command, penReady } from "../actions";
import type { ReactNode } from "react";
import { FillIcon, LineIcon, PictureIcon, SatinIcon, SelectIcon, ShapesIcon, TextIcon, WandIcon } from "./Icons";
import { acceptWholePicture, digitizeWholePicture, endStitchEdit } from "../features";
import { acceptGuess, dismissAutoTrace, nextGuess, setSpacing, setSpread, setTraceAI, SPACING_MAX_MM, SPACING_MIN_MM, SPREAD_MAX, SPREAD_MIN } from "../autoTrace";
import { fmtLen } from "./InfoPanel";
import { Menu } from "./Menu";
import { formatShortcut } from "../commands";
import { useStore, type Tool } from "../store";

const TOOLS: { id: string; tool: Tool; icon: ReactNode; label: string }[] = [
  { id: "tool.select", tool: "select", icon: <SelectIcon />, label: "Select" },
  { id: "tool.run", tool: "run", icon: <LineIcon />, label: "Line" },
  { id: "tool.satin", tool: "satin", icon: <SatinIcon />, label: "Satin" },
  { id: "tool.fill", tool: "fill", icon: <FillIcon />, label: "Fill" },
  { id: "tool.text", tool: "text", icon: <TextIcon />, label: "Text" },
  { id: "tool.autotrace", tool: "autotrace", icon: <WandIcon />, label: "Auto-trace" },
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
          side="right"
          className="rail-menu"
          trigger={
            <>
              <span className="icon">
                <ShapesIcon />
              </span>
              <span>Shapes</span>
            </>
          }
          items={[
            { id: "shape.rectangle", label: "▭  Rectangle" },
            { id: "shape.circle", label: "◯  Circle" },
            { id: "shape.star", label: "☆  Star" },
            { id: "shape.roundedRect", label: "▢  Rounded rectangle" },
            { id: "shape.ellipse", label: "⬭  Oval" },
            { id: "shape.triangle", label: "△  Triangle" },
            { id: "shape.polygon", label: "⬡  Polygon…" },
            { id: "shape.heart", label: "♡  Heart" },
            "separator",
            { id: "text.monogram", label: "Monogram" },
            "separator",
            { id: "object.hole", label: "Cut a hole in the selected fill" },
            { id: "object.cutOut", label: "Cut the shape on top out of the fill" },
          ]}
        />
      </div>
      <span className="rail-sep" />
      <button onClick={command("file.picture").run} disabled={!engine} title={`${command("file.picture").title} (${formatShortcut(command("file.picture").shortcut)})`}>
        <span className="icon" aria-hidden>
          <PictureIcon />
        </span>
        <span>Picture</span>
        <kbd>{formatShortcut(command("file.picture").shortcut)}</kbd>
      </button>
    </nav>
  );
}

const HINTS: Record<Exclude<Tool, "select">, string> = {
  text: "Click where the text should go, then type.",
  run: "Click along the line.",
  satin: "Click along the middle of the ribbon (its width is in the panel, and remembered).",
  autotrace: "Click inside a shape on your picture for its outline, or on one of its dark lines for a satin along it.",
  fill: "Click around the shape's edge. It closes by itself.",
};

/** What to do next while drawing, in plain words. */
export function DrawHint() {
  const tool = useStore((s) => s.tool);
  const pen = useStore((s) => s.pen);
  const measure = useStore((s) => s.measure);
  const ghost = useStore((s) => s.ghost);
  const edgeFit = useStore((s) => s.edgeFit);
  const step = useStore((s) => s.traceStep);
  const autoAll = useStore((s) => s.autoAll);
  const knife = useStore((s) => s.knife);
  const stitchEdit = useStore((s) => s.stitchEdit);
  const ruler = useStore((s) => s.ruler);
  const units = useStore((s) => s.units);
  if (autoAll) return <WholePictureBar />;
  if (ruler) {
    const [a, b] = ruler;
    return (
      <div className="draw-hint" role="status">
        📏{" "}
        {b ? (
          <>
            <b>{fmtLen(Math.hypot(b[0] - a[0], b[1] - a[1]), units)}</b> ({fmtLen(Math.abs(b[0] - a[0]), units)} across,{" "}
            {fmtLen(Math.abs(b[1] - a[1]), units)} down) · click again to measure something else
          </>
        ) : a ? (
          "Click the second point."
        ) : (
          "Click two points to see the distance between them."
        )}{" "}
        <kbd>Esc</kbd> puts the tool away.
      </div>
    );
  }
  if (knife) {
    return (
      <div className="draw-hint" role="status">
        🔪 Click two points: the knife cuts along that line, across the whole shape. <kbd>Esc</kbd> cancels.
      </div>
    );
  }
  if (stitchEdit) {
    return (
      <div className="draw-hint auto-trace" role="status">
        <b>Editing stitches</b> · click a stitch (<kbd>Shift</kbd>+click for more) or drag a box round some · drag them to move ·{" "}
        <kbd>Insert</kbd> adds one after it ·{" "}
        <kbd>Delete</kbd> removes {stitchEdit.selected.length ? `the ${stitchEdit.selected.length} selected` : "selected ones"} · <kbd>Ctrl</kbd>+<kbd>Z</kbd> undoes
        <button onClick={endStitchEdit}>
          Done <kbd>Esc</kbd>
        </button>
      </div>
    );
  }
  if (measure) {
    return (
      <div className="draw-hint" role="status">
        📏 Click two points on the picture whose real distance you know. <kbd>Esc</kbd> cancels.
      </div>
    );
  }
  if (tool === "select") return null;
  if (edgeFit && pen?.kind === "satin") {
    const n = edgeFit.options.length;
    const fit = edgeFit.options[edgeFit.index];
    return (
      <div className="draw-hint auto-trace" role="status">
        {edgeFit.original ? (
          <>
            Fitted <b>{fit.label}</b>
            {n > 1 ? ` (${edgeFit.index + 1} of ${n})` : ""} · {n > 1 ? <><kbd>Tab</kbd> tries the next way · </> : null}
            <kbd>Enter</kbd> keeps it · <kbd>Esc</kbd> puts your points back
          </>
        ) : (
          <>
            Following an edge? <kbd>Tab</kbd> fits the satin <b>{fit.label}</b>
            {n > 1 ? " (press again for other ways)" : ""}. Or keep clicking.
          </>
        )}
      </div>
    );
  }
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
  if (tool === "autotrace") return <AutoTraceBar />;
  if (tool === "text") {
    return (
      <div className="draw-hint" role="status">
        {HINTS.text} <kbd>Esc</kbd> goes back to Select.
      </div>
    );
  }
  const next = pen?.carveFor ? "Click along the line to carve." : HINTS[tool];
  const placed = pen ? pen.a.length + pen.b.length : 0;
  const ready = penReady();
  // Carving goes on line after line: Esc drops the line being drawn, then stops.
  const esc = pen?.carveFor ? (placed ? "drops this line" : "stops carving") : pen ? "drops the shape" : "goes back to Select";
  return (
    <div className="draw-hint" role="status">
      {next} <span className="kinds">Click = <b>curve</b> · <kbd>Ctrl</kbd>+click = <b>straight</b> · <kbd>Shift</kbd>+click = <b>sharp corner</b> · <kbd>Alt</kbd> = 15° steps</span>{" "}
      {ready ? <>Finish: <kbd>Enter</kbd> or right-click{tool === "run" ? <> (<kbd>Ctrl</kbd>+right-click closes it)</> : null}.</> : null} <kbd>Backspace</kbd> undoes a point, <kbd>Esc</kbd> {esc}.
      {placed > 0 && (
        <strong className="placed">
          {" "}
          {placed} point{placed === 1 ? "" : "s"} placed: <kbd>Esc</kbd> drops {placed === 1 ? "it" : "them"}.
        </strong>
      )}
    </div>
  );
}

/** Auto-trace's bar: which guess is shown, the next one, point spacing, and how to use it. */
function AutoTraceBar() {
  const a = useStore((s) => s.autoTrace);
  const spacing = useStore((s) => s.autoSpacing);
  const spread = useStore((s) => s.autoSpread);
  const model = useStore((s) => s.traceModel);
  const ai = useStore((s) => s.traceAI);
  const g = a?.guesses[a.index];
  const spreadControl = <SpreadControl spread={spread} />;
  const aiControl = model?.installed && model.runtime ? (
    <label className="at-ai" title="Ask the AI tracing model too (it runs on this computer)">
      <input type="checkbox" checked={ai} onChange={(e) => setTraceAI(e.target.checked)} /> AI
    </label>
  ) : null;
  const more = (
    <span className="at-more">
      <kbd>Shift</kbd>+click adds an area, <kbd>Alt</kbd>+click cuts one out.
    </span>
  );
  const spacingControl = <SpacingControl spacing={spacing} />;
  if (!a || (!g && !a.busy)) {
    return (
      <div className="draw-hint auto-trace" role="status">
        {HINTS.autotrace} {spacingControl} {spreadControl} {aiControl}
        <button onClick={() => void digitizeWholePicture()} title="Every shape in the picture at once: fills for the colors, satins for the dark lines (Alt+A)">
          Whole picture… <kbd>Alt+A</kbd>
        </button>{" "}
        <kbd>Esc</kbd> goes back to Select.
      </div>
    );
  }
  return (
    <div className="draw-hint auto-trace" role="status">
      {a.busy && !g ? (
        ai && model?.installed && model.runtime ? "Looking… (the AI reads a new picture first: a second or two)" : "Looking…"
      ) : g ? (
        <>
          <b>
            Guess {a.index + 1} of {a.guesses.length}:
          </b>{" "}
          {g.label}
          {a.guesses.length > 1 && (
            <button onClick={() => nextGuess(1)}>
              Next guess <kbd>Tab</kbd>
            </button>
          )}
          {spacingControl}
          {g.kind === "fill" && spreadControl}
          {aiControl}
          {g.kind === "fill" && more}
          <span className="at-use">
            {g.kind === "fill" ? (
              <>
                <button className="primary" onClick={() => void acceptGuess("fill")}>
                  Fill <kbd>Enter</kbd>
                </button>
                <button onClick={() => void acceptGuess("fillAndBorder")} title="A fill, and a satin ribbon around its edge sewn after it">
                  Fill + satin border <kbd>Shift+Enter</kbd>
                </button>
                <button onClick={() => void acceptGuess("satin")} title="Fill the area with one satin that turns and changes width with it">
                  Satin fill
                </button>
              </>
            ) : (
              <>
                <button className="primary" onClick={() => void acceptGuess("satin")}>
                  Satin <kbd>Enter</kbd>
                </button>
                <button onClick={() => void acceptGuess("run")}>Line</button>
              </>
            )}
          </span>
          <button onClick={dismissAutoTrace} title="Throw this guess away (Esc)">
            ✕ Dismiss <kbd>Esc</kbd>
          </button>
        </>
      ) : null}
    </div>
  );
}

/** Auto-trace's point spacing, − and + ([ and ]). */
function SpacingControl({ spacing, disabled }: { spacing: number; disabled?: boolean }) {
  return (
    <span className="at-spacing" title="How far apart the points are ([ and ])">
      Points every
      <button onClick={() => setSpacing(spacing - 0.5)} disabled={disabled || spacing <= SPACING_MIN_MM} aria-label="Points closer together">
        −
      </button>
      <b>{spacing} mm</b>
      <button onClick={() => setSpacing(spacing + 0.5)} disabled={disabled || spacing >= SPACING_MAX_MM} aria-label="Points further apart">
        +
      </button>
    </span>
  );
}

/** How far an Auto-trace area spreads into similar colors, − and + (Alt+[ and Alt+]). */
function SpreadControl({ spread, disabled }: { spread: number; disabled?: boolean }) {
  return (
    <span className="at-spacing" title="How far a guess spreads: less stops at the faintest change of color, more joins shades together (Alt+[ and Alt+])">
      Spread
      <button onClick={() => setSpread(spread - 1)} disabled={disabled || spread <= SPREAD_MIN} aria-label="Spread less">
        −
      </button>
      <b>{spread}</b>
      <button onClick={() => setSpread(spread + 1)} disabled={disabled || spread >= SPREAD_MAX} aria-label="Spread more">
        +
      </button>
    </span>
  );
}

/** "Whole picture": what was found, two choices, and add all or dismiss. */
function WholePictureBar() {
  const a = useStore((s) => s.autoAll)!;
  const setAutoAll = useStore((s) => s.setAutoAll);
  const spacing = useStore((s) => s.autoSpacing);
  const spread = useStore((s) => s.autoSpread);
  const n = (k: string) => a.shapes.filter((sh) => sh.kind === k).length;
  return (
    <div className="draw-hint auto-trace" role="status">
      {a.busy ? (
        <b>Reading the whole picture… (a few seconds; up to a minute for a busy picture)</b>
      ) : (
        <b>
          Found {n("fill")} fill{n("fill") === 1 ? "" : "s"}, {n("satin")} satin outline{n("satin") === 1 ? "" : "s"}
          {n("run") ? `, ${n("run")} thin line${n("run") === 1 ? "" : "s"}` : ""}
        </b>
      )}
      <label className="at-ai">
        <input type="checkbox" checked={a.outlines} onChange={(e) => void digitizeWholePicture({ outlines: e.target.checked })} disabled={a.busy} /> Satin
        outlines on the dark lines
      </label>
      <label className="at-ai">
        <input type="checkbox" checked={a.skipBackground} onChange={(e) => void digitizeWholePicture({ skipBackground: e.target.checked })} disabled={a.busy} />{" "}
        Leave out the background
      </label>
      <SpacingControl spacing={spacing} disabled={a.busy} /> <SpreadControl spread={spread} disabled={a.busy} />
      <span className="at-use">
        <button className="primary" onClick={() => void acceptWholePicture()} disabled={a.busy || !a.shapes.length}>
          Add all <kbd>Enter</kbd>
        </button>
        <button onClick={() => setAutoAll(null)}>
          ✕ Dismiss <kbd>Esc</kbd>
        </button>
      </span>
    </div>
  );
}
