import { useEffect, useState } from "react";
import { loadPrefs, savePrefs } from "../prefs";
import type { ThemeChoice } from "../theme";
import { appVersion, checkForUpdates } from "../updates";
import { useStore } from "../store";
import { AISettingsSection } from "./AISettings";
import { LuddLogo } from "./Logo";
import { useModal } from "./ThreadDialogs";
import { MachinePicker } from "./Toolbar";

const THEMES: { id: ThemeChoice; label: string }[] = [
  { id: "system", label: "Automatic" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

/** Settings: the everyday choices in one place. Each one is also in the ⋯ menu or the toolbar. */
export function SettingsDialog() {
  const open = useStore((s) => s.settingsOpen);
  const setOpen = useStore((s) => s.setSettingsOpen);
  const theme = useStore((s) => s.theme);
  const units = useStore((s) => s.units);
  const showGrid = useStore((s) => s.showGrid);
  const showHoop = useStore((s) => s.showHoop);
  const realistic = useStore((s) => s.realistic);
  const traceAssist = useStore((s) => s.traceAssist);
  const canvasBg = useStore((s) => s.canvasBg);
  const [checkUpdates, setCheckUpdates] = useState(() => loadPrefs().checkUpdates !== false);
  const [version, setVersion] = useState("");
  useEffect(() => {
    if (open) void appVersion().then(setVersion);
  }, [open]);
  const st = useStore.getState();
  const ref = useModal(open);

  return (
    <dialog ref={ref} className="modal settings" onClose={() => setOpen(false)} aria-labelledby="settings-title">
      <h2 id="settings-title">Settings</h2>

      <h3>Look</h3>
      <div className="seg" role="radiogroup" aria-label="Light or dark">
        {THEMES.map((t) => (
          <button key={t.id} role="radio" aria-checked={theme === t.id} aria-pressed={theme === t.id} onClick={() => st.setTheme(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <p className="hint">Automatic follows your computer's light or dark setting.</p>
      <label className="check">
        <input type="checkbox" checked={canvasBg === "light"} onChange={(e) => st.setCanvasBg(e.target.checked ? "light" : "theme")} /> Always show the
        design on light fabric
        <small>Dark threads (black, navy) are easier to judge on light fabric.</small>
      </label>

      <h3>My machine</h3>
      <MachinePicker />

      <h3>Measurements</h3>
      <div className="seg" role="radiogroup" aria-label="Units">
        <button role="radio" aria-checked={units === "in"} aria-pressed={units === "in"} onClick={() => st.setUnits("in")}>
          Inches
        </button>
        <button role="radio" aria-checked={units === "mm"} aria-pressed={units === "mm"} onClick={() => st.setUnits("mm")}>
          Millimetres
        </button>
      </div>

      <h3>Workspace</h3>
      <label className="check">
        <input type="checkbox" checked={showHoop} onChange={st.toggleHoop} /> Show the hoop
      </label>
      <label className="check">
        <input type="checkbox" checked={showGrid} onChange={st.toggleGrid} /> Show the grid
      </label>
      <label className="check">
        <input type="checkbox" checked={realistic} onChange={st.toggleRealistic} /> Realistic thread
        <small>Shaded, rounded stitches. Off shows plain lines, which can be easier for editing.</small>
      </label>
      <label className="check">
        <input type="checkbox" checked={traceAssist} onChange={st.toggleTraceAssist} /> Trace Assist
        <small>While drawing over a picture, suggests the next point. Tab takes it.</small>
      </label>

      <AISettingsSection />

      <h3>Updates</h3>
      <label className="check">
        <input
          type="checkbox"
          checked={checkUpdates}
          onChange={(e) => {
            setCheckUpdates(e.target.checked);
            savePrefs({ checkUpdates: e.target.checked });
          }}
        />{" "}
        Tell me when a new version is out
        <small>When LUDD starts it asks GitHub whether there's a newer version. Nothing about you or your designs is sent.</small>
      </label>
      <div className="btn-row">
        <button onClick={() => void checkForUpdates(true)}>Check now</button>
        <span className="hint">You have LUDD {version}.</span>
      </div>

      <div className="actions">
        <span className="about">
          <LuddLogo size={20} /> <small>Free + open-source embroidery</small>
        </span>
        <button className="primary" onClick={() => setOpen(false)}>
          Done
        </button>
      </div>
    </dialog>
  );
}
