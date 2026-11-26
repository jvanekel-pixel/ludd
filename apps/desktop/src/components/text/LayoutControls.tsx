/** Lettering layout in the panel: single letters here; lines, alignment, slant, envelopes and
 *  stacked letters under More options. */
import { useEffect, useRef, useState } from "react";
import { setText } from "../../actions";
import { COMMANDS, formatShortcut } from "../../commands";
import type { Envelope, LayoutItemInfo, LetterEdit, TextItem } from "../../design/types";
import { heldCount } from "../../escape";
import { leaveLetterMode, resetLetter, resetLetters, setLetterEdit, toggleLetterMode, useLetterMode } from "../../feat/letters";
import { useStore } from "../../store";
import { Row } from "../Accordion";
import { Stepper } from "../controls";
import { ThreadPicker } from "../ThreadDialogs";
import { isStitchFont, type TextSlotProps } from "./slots";

const ALIGN: { value: NonNullable<TextItem["align"]>; label: string; title: string }[] = [
  { value: "left", label: "Left", title: "The lines start together" },
  { value: "center", label: "Center", title: "The lines are centered on each other" },
  { value: "right", label: "Right", title: "The lines end together" },
];

/** Three words side by side beside their label, at the panel's usual width. */
const TIGHT: React.CSSProperties = { fontSize: 12, paddingInline: "0.15rem" };

const ENVELOPES: { value: Envelope; label: string }[] = [
  { value: "bulge", label: "Bulge" },
  { value: "pinch", label: "Pinch" },
  { value: "pennant_right", label: "Pennant right" },
  { value: "pennant_left", label: "Pennant left" },
  { value: "wave", label: "Wave" },
  { value: "arch_top", label: "Arch top" },
  { value: "arch_bottom", label: "Arch bottom" },
];

/** " (Alt+Shift+A)", for a button's tooltip. */
function keys(id: string): string {
  const c = COMMANDS.find((x) => x.id === id);
  return c ? ` (${formatShortcut(c.shortcut)})` : "";
}

/** The letters of a text as the design shows them, first to last. */
const lettersShown = (info: LayoutItemInfo) => [...new Set((info.letters ?? []).map((p) => p.letter))].sort((a, b) => a - b);

/** The stitch angle of one letter: empty for the one LUDD chose. */
function AngleRow({ value, onCommit }: { value: number | undefined; onCommit: (v: number | undefined) => void }) {
  const shown = value === undefined ? "" : String(value);
  const [draft, setDraft] = useState(shown);
  useEffect(() => setDraft(shown), [shown]);
  const reverting = useRef(false);
  const done = () => {
    if (reverting.current) {
      reverting.current = false;
      return;
    }
    if (draft.trim() === shown) return;
    const v = draft.trim() === "" ? undefined : Number(draft);
    if (v === undefined || Number.isFinite(v)) onCommit(v);
    else setDraft(shown);
  };
  return (
    <Row label="Stitch angle" hint="The way this letter's stitches run, in degrees. Leave it empty to let LUDD choose.">
      <div className="stepper">
        <label className="num-field">
          <input
            type="number"
            step={5}
            aria-label="Stitch angle"
            placeholder="Auto"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={done}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape" && !heldCount()) {
                reverting.current = true;
                setDraft(shown);
                (e.target as HTMLInputElement).blur();
              }
            }}
          />
        </label>
        <small>°</small>
      </div>
    </Row>
  );
}

/** Size, turn, thread and stitch angle of the letter picked on the design. */
function LetterSettings({ item, info, letter }: { item: TextItem; info: LayoutItemInfo; letter: number }) {
  const [picking, setPicking] = useState(false);
  const letters = lettersShown(info);
  const edit: LetterEdit = item.letter_edits?.[letter] ?? {};
  const textThread = item.threads?.[0] ?? item.thread;
  const thread = edit.thread ?? textThread;
  const parts = (info.letters ?? []).filter((p) => p.letter === letter);
  // Only fills have an angle: not True satin columns or a stitch font's ready-made stitches.
  const angled = (item.style !== "columns" || isStitchFont(item.font.path)) && parts.some((p) => p.kind === "fill");
  const set = (patch: Partial<LetterEdit>) => void setLetterEdit(item.id, letter, patch);
  return (
    <>
      <p className="hint">
        Letter {letters.indexOf(letter) + 1} of {letters.length}: drag it on the design, or use the arrow keys.
      </p>
      <Stepper label="Size" value={Math.round((edit.scale ?? 1) * 100)} step={5} min={50} max={200} digits={0} suffix="%" onCommit={(v) => set({ scale: v / 100 })} />
      <Stepper label="Turn" value={edit.rotate ?? 0} step={5} min={-180} max={180} digits={0} suffix="°" title="Turn this letter; more than 0 is clockwise" onCommit={(v) => set({ rotate: v })} />
      <Row label="Thread">
        <button className="thread-button" onClick={() => setPicking(true)} title="This letter's thread">
          <span className="swatch" style={{ background: thread.color }} />
          <span className="tname">{edit.thread ? edit.thread.name || edit.thread.color : "Same as the text"}</span>
        </button>
      </Row>
      {angled && <AngleRow value={edit.angle_deg} onCommit={(v) => set({ angle_deg: v })} />}
      {picking && (
        <ThreadPicker
          index={-1}
          onClose={() => setPicking(false)}
          onPick={(t) => set({ thread: t })}
          current={thread}
          onReset={edit.thread ? () => set({ thread: undefined }) : undefined}
          resetLabel="the text's color"
        />
      )}
    </>
  );
}

export function LayoutControls({ item, info }: TextSlotProps) {
  const mode = useLetterMode();
  const engineReady = useStore((s) => s.engine !== null);
  const putBack = Object.keys(item.letter_edits ?? {}).length > 0 && (
    <button onClick={resetLetters} title={`Undo every change to single letters${keys("text.resetLetters")}`}>
      Put the letters back
    </button>
  );
  if (mode.id !== item.id) {
    return (
      <div className="btn-row">
        <button onClick={toggleLetterMode} disabled={!!item.locked || !engineReady} title={`Move, turn, resize or recolor one letter at a time${keys("text.letters")}`}>
          Adjust single letters
        </button>
        {putBack}
      </div>
    );
  }
  const letter = mode.letter !== null && lettersShown(info).includes(mode.letter) ? mode.letter : null;
  return (
    <div className="letter-edit">
      {letter === null ? (
        <p className="hint">
          Click a letter's dot on the design, then drag it or use the arrow keys (1 mm; with Shift, 10 mm; with {formatShortcut("Mod+").replace(/\+$/, "")}, 0.1 mm).
        </p>
      ) : (
        <LetterSettings key={`${item.id}:${letter}`} item={item} info={info} letter={letter} />
      )}
      <div className="btn-row">
        {letter !== null && (
          <button onClick={() => void resetLetter(item.id, letter)} disabled={!item.letter_edits?.[letter]}>
            Put this letter back
          </button>
        )}
        {putBack}
        <button onClick={leaveLetterMode} title="Stop adjusting single letters (Esc)">
          Done
        </button>
      </div>
    </div>
  );
}

/** How strongly the envelope bends; it takes effect when the slider is let go. */
function AmountRow({ amount, onCommit }: { amount: number; onCommit: (v: number) => void }) {
  const [shown, setShown] = useState(amount);
  useEffect(() => setShown(amount), [amount]);
  const done = (e: { currentTarget: HTMLInputElement }) => {
    const v = Number(e.currentTarget.value);
    if (Math.abs(v - amount) > 1e-9) onCommit(v);
  };
  return (
    <Row label="Amount" hint="How strongly the envelope bends the letters">
      <div className="stepper">
        <input
          type="range"
          style={{ flex: 1, minWidth: 0 }}
          min={0}
          max={1}
          step={0.05}
          value={shown}
          aria-label="Envelope amount"
          aria-valuetext={`${Math.round(shown * 100)}%`}
          onChange={(e) => setShown(Number(e.currentTarget.value))}
          onPointerUp={done}
          onKeyUp={done}
        />
        <small>{Math.round(shown * 100)}%</small>
      </div>
    </Row>
  );
}

export function LayoutMore({ item }: TextSlotProps) {
  // A monogram lays out its own letters: no shape to follow, no lines.
  const shape = item.monogram ? "line" : item.shape.type;
  const straight = shape === "line";
  const stacked = straight && !item.monogram && !!item.vertical;
  const lines = item.text.split("\n").filter((l) => l.trim()).length;
  const several = !item.monogram && lines > 1 && shape !== "circle" && shape !== "path"; // those take one line
  const follows = shape === "path" ? "is on a line you drew" : shape === "circle" ? "goes round a circle" : shape === "arc_up" ? "is on an arch" : "is on a curve";
  const envelopeOff = !straight
    ? `Envelopes work on straight text only, and this text ${follows}.`
    : stacked
      ? "Stacked letters can't be bent into an envelope. Untick Stack the letters to use one."
      : null;
  const stackOff = straight ? null : `Letters can only be stacked on straight text, and this text ${follows}.`;
  const align = item.align ?? "center";
  const spacing = item.line_spacing ?? 1.3;
  const slant = item.slant_deg ?? 0;
  const envelopeTip = envelopeOff ?? "Bend the whole text into a shape";
  return (
    <>
      {several && !stacked && (
        <Row label="Align">
          <div className="seg" role="group" aria-label="Align the lines">
            {ALIGN.map((a) => (
              <button key={a.value} style={TIGHT} aria-pressed={align === a.value} title={a.title} onClick={() => a.value !== align && setText(item.id, { align: a.value })}>
                {a.label}
              </button>
            ))}
          </div>
        </Row>
      )}
      {several && (
        <Stepper
          label="Line spacing"
          value={spacing}
          step={0.1}
          min={0.8}
          max={3}
          digits={1}
          suffix="×"
          title={`From one ${stacked ? "column" : "line"} to the next, in letter heights`}
          onCommit={(v) => {
            const to = Math.round(v * 100) / 100;
            if (to !== spacing) setText(item.id, { line_spacing: to });
          }}
        />
      )}
      <Stepper
        label="Slant"
        value={slant}
        step={1}
        min={-30}
        max={30}
        digits={0}
        suffix="°"
        title="Lean the letters: more than 0 leans them right"
        onCommit={(v) => v !== slant && setText(item.id, { slant_deg: v || undefined })}
      />
      <Row label="Envelope" hint={envelopeTip}>
        <select
          aria-label="Envelope"
          style={{ width: "100%" }}
          disabled={!!envelopeOff}
          title={envelopeTip}
          value={item.envelope?.type ?? ""}
          onChange={(e) => {
            const type = e.target.value as Envelope | "";
            setText(item.id, { envelope: type ? { type, amount: item.envelope?.amount ?? 0.5 } : undefined });
          }}
        >
          <option value="">None</option>
          {ENVELOPES.map((v) => (
            <option key={v.value} value={v.value}>
              {v.label}
            </option>
          ))}
        </select>
      </Row>
      {item.envelope && !envelopeOff && (
        <AmountRow amount={item.envelope.amount ?? 0.5} onCommit={(amount) => setText(item.id, { envelope: { type: item.envelope!.type, amount } })} />
      )}
      {!item.monogram && (
        <label className="check" title={stackOff ?? "Letters one under another, top to bottom; each line is a column"}>
          <input type="checkbox" checked={!!item.vertical} disabled={!!stackOff} onChange={(e) => setText(item.id, { vertical: e.target.checked || undefined })} />
          Stack the letters (vertical)
        </label>
      )}
    </>
  );
}
