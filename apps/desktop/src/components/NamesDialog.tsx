import { useEffect, useState } from "react";
import { defaultFormat } from "../design/machine";
import { exportNames, pickFolder } from "../features";
import { selectMachine, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

/** One machine file per name: the selected lettering with each name in turn. */
export function NamesDialog() {
  const open = useStore((s) => s.dialog === "names");
  const setDialog = useStore((s) => s.setDialog);
  const machine = useStore(selectMachine);
  const formats = useStore((s) => s.formats);
  const ref = useModal(open);
  const [names, setNames] = useState("");
  const [ext, setExt] = useState(() => defaultFormat(machine));
  // Your machine's format each time it opens (the machine may have changed since).
  useEffect(() => {
    if (open) setExt(defaultFormat(machine));
  }, [open, machine]);
  const close = () => setDialog(null);
  const list = names.split("\n").map((n) => n.trim()).filter(Boolean);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="names-title">
      <h2 id="names-title">One file per name</h2>
      <p className="hint">The selected lettering is changed to each name in turn, and each is saved as its own machine file (Emma.pes, Jack.pes…), with the rest of the design as it is.</p>
      <label className="field">
        Names, one per line
        <textarea rows={8} value={names} onChange={(e) => setNames(e.target.value)} placeholder={"Emma\nJack\nOlivia"} />
      </label>
      <label className="field">
        File type
        <select value={ext} onChange={(e) => setExt(e.target.value)}>
          {(formats?.write ?? [{ ext: "pes", description: "Brother" }]).map((f) => (
            <option key={f.ext} value={f.ext}>
              {f.ext.toUpperCase()} {f.description ? `– ${f.description}` : ""}
            </option>
          ))}
        </select>
      </label>
      <div className="actions">
        <button onClick={close}>Cancel</button>
        <button
          className="primary"
          disabled={!list.length}
          onClick={async () => {
            const folder = await pickFolder("Save the files in…");
            if (!folder) return;
            close();
            await exportNames(list, folder, ext);
          }}
        >
          Save {list.length || ""} files…
        </button>
      </div>
    </dialog>
  );
}
