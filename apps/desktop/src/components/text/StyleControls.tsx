/** How the letters are stitched: Satin look, True satin or Fill (a stitch font sews its own stitches), what
 *  each letter does, and the buttons for their starts and ends. */
import { command, setText } from "../../actions";
import { formatShortcut } from "../../commands";
import type { TextItem } from "../../design/types";
import { selectLayout, useStore } from "../../store";
import { isStitchFont, type TextSlotProps } from "./slots";

/** Shown under the buttons while True satin is chosen. */
export const TRUE_SATIN_HINT = "Each stroke is its own satin column. New: check the preview, and switch to Satin look if a letter looks wrong.";

/** The look in a few words, for the panel section's summary. */
export const styleLabel = (item: TextItem) => (item.style === "satin" ? "Satin" : item.style === "columns" ? "True satin" : "Fill");

/** How the letters are stitched, in plain words, and what you can do with each one. */
function LetterNotes({ item, stitchFont }: { item: TextItem; stitchFont: boolean }) {
  const design = useStore((s) => s.design);
  const layout = useStore(selectLayout);
  const i = layout?.items.findIndex((it) => it.id === item.id) ?? -1;
  const parts = i >= 0 ? design?.items?.[i]?.letters : undefined;
  const chosen = Object.keys(item.letters ?? {}).length;
  const how = stitchFont
    ? "each letter sews the stitches its stitch font was made with"
    : item.style === "satin"
      ? "each letter is filled with long, smooth satin stitches across its strokes, at the angle that crosses them best"
      : item.style === "columns"
        ? "each stroke of a letter is its own satin column that follows the stroke, as hand-digitized fonts are; parts too wide or too small for a column are sewn in Satin look first"
        : "each letter is a woven (tatami) fill";
  return (
    <div className="letter-notes">
      <p className="hint">
        {parts ? `${parts.length} letter part${parts.length === 1 ? "" : "s"}: ` : ""}
        {how}. Each one starts by where the one before ended. Drag a letter's green (start) or red (end) dot on the design to move it
        along the letter's edge{chosen ? ` (${chosen} chosen)` : ""}.
      </p>
      <div className="btn-row">
        {chosen > 0 && (
          <button onClick={() => command("text.resetEnds").run()} title={`Let every letter start and end where LUDD puts them again (${formatShortcut(command("text.resetEnds").shortcut)})`}>
            Reset starts and ends
          </button>
        )}
        <button disabled={!(command("text.toShapes").enabled?.() ?? true)} onClick={() => command("text.toShapes").run()} title={`Turn the letters into ordinary shapes, to change their points, stitch type, density and direction one by one (${formatShortcut(command("text.toShapes").shortcut)}). The words can't be retyped after.`}>
          Break into shapes…
        </button>
      </div>
    </div>
  );
}

export function StyleControls({ item }: TextSlotProps) {
  const stitchFont = isStitchFont(item.font.path);
  return (
    <>
      {stitchFont ? (
        <p className="hint">A stitch font sews the stitches it was made with.</p>
      ) : (
        <>
          <div className="seg" role="group" aria-label="Stitch look">
            <button aria-pressed={item.style === "satin"} onClick={() => setText(item.id, { style: "satin" })} title="Smooth, shiny stitches across each stroke: best for names and small text">
              Satin look
            </button>
            <button aria-pressed={item.style === "columns"} onClick={() => setText(item.id, { style: "columns" })} title="A satin column for each stroke that follows it, as hand-digitized fonts are">
              True satin
            </button>
            <button aria-pressed={item.style === "fill"} onClick={() => setText(item.id, { style: "fill" })} title="Woven fill: best for big, bold letters">
              Fill
            </button>
          </div>
          {item.style === "columns" && <p className="hint">{TRUE_SATIN_HINT}</p>}
        </>
      )}
      <LetterNotes item={item} stitchFont={stitchFont} />
    </>
  );
}
