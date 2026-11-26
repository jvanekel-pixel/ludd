/** Monograms here (one to three letters, their style and a frame); a shadow and an outline
 *  under More options. */
import { useState } from "react";
import { setText } from "../../actions";
import type { MonogramStyle, OrnamentId, TextItem, Thread } from "../../design/types";
import { Row } from "../Accordion";
import { Stepper } from "../controls";
import { ThreadPicker } from "../ThreadDialogs";
import type { TextSlotProps } from "./slots";

const STYLES: { id: MonogramStyle; label: string; title: string }[] = [
  { id: "classic", label: "Classic", title: "A small letter, a big one and a small one" },
  { id: "block", label: "Block", title: "All the letters the same size" },
  { id: "stacked", label: "Stacked", title: "Two small letters one above the other, then a big one" },
];

const FRAMES: { id: OrnamentId; label: string }[] = [
  { id: "circle", label: "Circle" },
  { id: "double_circle", label: "Double circle" },
  { id: "diamond", label: "Diamond" },
  { id: "square", label: "Square" },
  { id: "scallop_circle", label: "Scallop circle" },
  { id: "laurel", label: "Laurel" },
];

const SHADOW: NonNullable<TextItem["shadow"]> = { dx_mm: 0.8, dy_mm: 0.8, thread: { color: "#8c8c8c", name: "Gray", brand: "", catalog: "" } };
const OUTLINE: NonNullable<TextItem["outline"]> = { gap_mm: 1, width_mm: 1.5, style: "satin", thread: { color: "#000000", name: "Black", brand: "", catalog: "" } };

const tidy = (v: number) => Math.round(v * 100) / 100;

/** An extra's thread: the one chosen, or the letters' (`own` undefined). */
function ExtraThread({ what, own, letters, onPick, onClear }: { what: string; own: Thread | undefined; letters: Thread; onPick: (t: Thread) => void; onClear?: () => void }) {
  const [picking, setPicking] = useState(false);
  const shown = own ?? letters;
  return (
    <>
      <button className="thread-button" onClick={() => setPicking(true)} title={`Change the ${what} thread`}>
        <span className="swatch" style={{ background: shown.color }} />
        <span className="tname">
          {own ? shown.name || shown.color : "Same as the letters"}
          <small>{what[0].toUpperCase() + what.slice(1)} thread</small>
        </span>
      </button>
      {own && onClear && (
        <button className="link" onClick={onClear}>
          Use the letters' thread
        </button>
      )}
      {picking && <ThreadPicker index={-1} onClose={() => setPicking(false)} onPick={onPick} current={shown} />}
    </>
  );
}

export function ExtrasControls({ item }: TextSlotProps) {
  const style = item.monogram_style ?? "classic";
  const frame = item.ornament;
  const letters = item.threads?.[0] ?? item.thread;
  const monogram = (on: boolean) => setText(item.id, on ? { monogram: true, text: item.text.replace(/\s/g, "").slice(0, 3) || "ABC" } : { monogram: false });
  return (
    <>
      <label className="check">
        <input type="checkbox" checked={item.monogram} onChange={(e) => monogram(e.target.checked)} />
        Monogram (one to three letters)
      </label>
      {item.monogram && (
        <>
          <div className="seg" role="group" aria-label="Monogram style">
            {STYLES.map((s) => (
              <button key={s.id} aria-pressed={style === s.id} title={s.title} onClick={() => setText(item.id, { monogram_style: s.id === "classic" ? undefined : s.id })}>
                {s.label}
              </button>
            ))}
          </div>
          <Row label="Frame">
            <select
              aria-label="Frame"
              value={frame?.id ?? ""}
              onChange={(e) => setText(item.id, { ornament: e.target.value ? { ...frame, id: e.target.value as OrnamentId } : undefined })}
            >
              <option value="">None</option>
              {FRAMES.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </select>
          </Row>
          {frame && (
            <>
              <Stepper
                label="Frame gap"
                value={frame.margin_mm ?? 4}
                step={0.5}
                min={2}
                max={15}
                digits={1}
                suffix="mm"
                title="Space between the letters and the frame"
                onCommit={(v) => setText(item.id, { ornament: { ...frame, margin_mm: tidy(v) } })}
              />
              <ExtraThread
                what="frame"
                own={frame.thread}
                letters={letters}
                onPick={(t) => setText(item.id, { ornament: { ...frame, thread: t } })}
                onClear={() => setText(item.id, { ornament: { ...frame, thread: undefined } })}
              />
            </>
          )}
        </>
      )}
    </>
  );
}

export function ExtrasMore({ item }: TextSlotProps) {
  // A stitched font's letters are stitches, with no outlines to copy or draw round.
  const stitched = item.font.made_of === "stitches";
  const { shadow, outline } = item;
  const letters = item.threads?.[0] ?? item.thread;
  return (
    <>
      <label className="check" title="A copy of the letters peeking out from behind them">
        <input type="checkbox" checked={!!shadow} disabled={stitched && !shadow} onChange={(e) => setText(item.id, { shadow: e.target.checked ? SHADOW : undefined })} />
        Shadow
      </label>
      {shadow && !stitched && (
        <>
          <Stepper label="Shadow right" value={shadow.dx_mm ?? 0.8} step={0.1} min={-3} max={3} digits={1} suffix="mm" title="How far the shadow sits to the right (less than 0: to the left)" onCommit={(v) => setText(item.id, { shadow: { ...shadow, dx_mm: tidy(v) } })} />
          <Stepper label="Shadow down" value={shadow.dy_mm ?? 0.8} step={0.1} min={-3} max={3} digits={1} suffix="mm" title="How far the shadow sits below (less than 0: above)" onCommit={(v) => setText(item.id, { shadow: { ...shadow, dy_mm: tidy(v) } })} />
          <ExtraThread what="shadow" own={shadow.thread} letters={letters} onPick={(t) => setText(item.id, { shadow: { ...shadow, thread: t } })} />
        </>
      )}
      <label className="check" title="A line round the letters that follows them as you change them">
        <input type="checkbox" checked={!!outline} disabled={stitched && !outline} onChange={(e) => setText(item.id, { outline: e.target.checked ? OUTLINE : undefined })} />
        Outline
      </label>
      {outline && !stitched && (
        <>
          <div className="seg" role="group" aria-label="Outline stitch">
            <button aria-pressed={outline.style !== "run"} title="A smooth satin border" onClick={() => setText(item.id, { outline: { ...outline, style: "satin" } })}>
              Satin
            </button>
            <button aria-pressed={outline.style === "run"} title="A thin line, sewn three times" onClick={() => setText(item.id, { outline: { ...outline, style: "run" } })}>
              Triple run
            </button>
          </div>
          <Stepper label="Outline gap" value={outline.gap_mm ?? 1} step={0.5} min={0} max={5} digits={1} suffix="mm" title="Space between the letters and the outline" onCommit={(v) => setText(item.id, { outline: { ...outline, gap_mm: tidy(v) } })} />
          {outline.style !== "run" && (
            <Stepper label="Outline width" value={outline.width_mm ?? 1.5} step={0.5} min={1} max={4} digits={1} suffix="mm" onCommit={(v) => setText(item.id, { outline: { ...outline, width_mm: tidy(v) } })} />
          )}
          <ExtraThread what="outline" own={outline.thread} letters={letters} onPick={(t) => setText(item.id, { outline: { ...outline, thread: t } })} />
        </>
      )}
      {stitched && <p className="hint">A stitched font's letters have no outlines, so they can't have a shadow or an outline.</p>}
    </>
  );
}
