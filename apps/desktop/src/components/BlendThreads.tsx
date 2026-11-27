/** A blend's other colors: their thread buttons, adding a third, swapping them and the balance. */
import { useEffect, useState } from "react";
import { editObject } from "../actions";
import { addBlendColor, MAX_BLEND_COLORS, removeBlendColor, setBlendColor, slotThreads, swapBlendColors } from "../design/blend";
import type { FillParams, ObjectItem, Thread } from "../design/types";
import { Row } from "./Accordion";
import { ThreadPicker } from "./ThreadDialogs";

const ORDINAL = ["", "Second", "Third", "Fourth"];

function ThreadButton({ thread, label, onClick }: { thread: Thread; label: string; onClick: () => void }) {
  return (
    <button className="thread-button" onClick={onClick} title={`Change the ${label.toLowerCase()}`} aria-label={label}>
      <span className="swatch" style={{ background: thread.color }} />
      <span className="tname">
        {thread.name || thread.color}
        <small>{[thread.brand, thread.catalog].filter(Boolean).join(" ") || "Click to choose a thread"}</small>
      </span>
    </button>
  );
}

/** Balance: -1 (the first color takes more of the shape) to 1 (the last does). */
function BalanceSlider({ value, onCommit }: { value: number; onCommit: (v: number) => void }) {
  const [shown, setShown] = useState(value);
  useEffect(() => setShown(value), [value]);
  const read = (el: HTMLInputElement) => Math.round(Number(el.value) * 10) / 10;
  const commit = (e: { currentTarget: HTMLInputElement }) => {
    const v = read(e.currentTarget);
    if (v !== value) onCommit(v);
  };
  return (
    <Row label="Balance" hint="Which color takes more of the shape">
      <span className="density-slider">
        <span aria-hidden>First</span>
        <input
          type="range"
          min={-1}
          max={1}
          step={0.1}
          value={shown}
          aria-label="Balance"
          aria-valuetext={shown === 0 ? "Even" : shown < 0 ? "More of the first color" : "More of the last color"}
          onChange={(e) => setShown(read(e.currentTarget))}
          onPointerUp={commit}
          onKeyUp={commit}
        />
        <span aria-hidden>Last</span>
      </span>
    </Row>
  );
}

export function BlendThreads({ item }: { item: ObjectItem }) {
  const [picking, setPicking] = useState<number | null>(null);
  const sewn = slotThreads(item);
  const edit = (fn: (o: ObjectItem) => ObjectItem) => editObject(item.id, fn);
  const balance = (item.params as FillParams).blend_balance ?? 0;
  return (
    <div className="blend-threads">
      {sewn.slice(1).map((t, i) => {
        const k = i + 1;
        return (
          <Row key={k} label={`${ORDINAL[k] ?? "Next"} color`}>
            <ThreadButton thread={t} label={`${ORDINAL[k] ?? "Next"} color`} onClick={() => setPicking(k)} />
            {k >= 2 && (
              <button className="link" onClick={() => edit((o) => removeBlendColor(o, k))} title="Sew the blend in fewer colors">
                Remove
              </button>
            )}
          </Row>
        );
      })}
      {sewn.length < 2 && <p className="hint">Add a second color to make the fill fade.</p>}
      <div className="btn-row">
        {sewn.length < MAX_BLEND_COLORS && <button onClick={() => edit(addBlendColor)}>Add a color</button>}
        {sewn.length >= 2 && (
          <button onClick={() => edit(swapBlendColors)} title="The fade runs the other way">
            Swap the colors
          </button>
        )}
      </div>
      {sewn.length >= 2 && <BalanceSlider value={balance} onCommit={(v) => edit((o) => ({ ...o, params: { ...o.params, blend_balance: v } }) as ObjectItem)} />}
      <ThreadPicker
        index={picking !== null ? -1 : null}
        current={picking !== null ? sewn[picking] : undefined}
        onPick={(t) => picking !== null && edit((o) => setBlendColor(o, picking, t))}
        onClose={() => setPicking(null)}
      />
    </div>
  );
}
