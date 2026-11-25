/** "Add a polygon": asks how many sides, starting with the number used last. */
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { addShape } from "../actions";
import { clampSides, MAX_SIDES, MIN_SIDES } from "../design/shapes";
import { holdEscape, letGoNewest } from "../escape";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

export function PolygonDialog() {
  const ref = useModal(true);
  const box = useRef<HTMLInputElement>(null);
  const [start] = useState(() => clampSides(loadPrefs().polygonSides));
  const [text, setText] = useState(String(start));

  // Esc closes it through the app's one list of things Esc lets go of.
  useEffect(() => holdEscape(close), []);
  // The number is selected, ready to be typed over.
  useEffect(() => {
    box.current?.focus();
    box.current?.select();
  }, []);

  const add = () => {
    // An empty box means the number it started with.
    const sides = clampSides(text.trim() ? Number(text) : start);
    savePrefs({ polygonSides: sides });
    close();
    void addShape("polygon", { sides });
  };

  // The app's keyboard handler leaves open dialogs alone, so Esc and Enter are handled here, and
  // go no further, so nothing else acts on them as well.
  const onKeyDown = (e: KeyboardEvent) => {
    const esc = e.key === "Escape";
    // On a button, Enter presses that button (the browser's own click).
    if (!esc && (e.key !== "Enter" || e.target instanceof HTMLButtonElement)) return;
    e.preventDefault(); // (nor does the browser close the dialog a second way)
    e.stopPropagation();
    if (e.repeat) return;
    if (esc) letGoNewest();
    else add();
  };

  return (
    <dialog ref={ref} className="modal" onClose={close} onKeyDown={onKeyDown} aria-labelledby="polygon-title">
      <h2 id="polygon-title">Add a polygon</h2>
      <label className="field">
        Sides
        <span className="row">
          <input ref={box} type="number" min={MIN_SIDES} max={MAX_SIDES} step={1} value={text} onChange={(e) => setText(e.target.value)} />
          <small>
            {MIN_SIDES} to {MAX_SIDES}
          </small>
        </span>
      </label>
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button className="primary" onClick={add}>
          Add
        </button>
      </div>
    </dialog>
  );
}
