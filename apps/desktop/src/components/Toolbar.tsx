import { command } from "../actions";
import { formatShortcut } from "../commands";
import { jumpsToTrimsSetting } from "../design/layout";
import { selectLayout, selectMachine, useStore } from "../store";
import { LuddLogo } from "./Logo";
import { Menu } from "./Menu";

function CommandButton({ id, label, primary, aria }: { id: string; label: string; primary?: boolean; aria?: string }) {
  const cmd = command(id);
  // Re-render when state that `enabled` depends on changes.
  useStore((s) => s.engine);
  useStore((s) => s.design);
  useStore((s) => s.history);
  const enabled = cmd.enabled ? cmd.enabled() : true;
  return (
    <button
      className={primary ? "primary" : undefined}
      onClick={cmd.run}
      disabled={!enabled}
      title={`${cmd.title} (${formatShortcut(cmd.shortcut)})`}
      aria-label={aria}
    >
      {label}
    </button>
  );
}

export function MachinePicker() {
  const machines = useStore((s) => s.machines);
  const machine = useStore(selectMachine);
  const hoopId = useStore((s) => s.hoopId);
  const setMachine = useStore((s) => s.setMachine);
  const setHoop = useStore((s) => s.setHoop);
  if (!machines.length) return null;
  return (
    <div className="machine-picker">
      <select
        value={machine?.id ?? ""}
        onChange={(e) => setMachine(e.target.value || null)}
        aria-label="Your machine"
        title="Your machine: sets the hoop, file format and cutting"
      >
        {machines.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
      {machine && machine.hoops.length > 1 && (
        <select value={hoopId ?? ""} onChange={(e) => setHoop(e.target.value)} aria-label="Hoop">
          {machine.hoops.map((h) => (
            <option key={h.id} value={h.id}>
              {h.name}
            </option>
          ))}
        </select>
      )}
      {machine && machine.hoops.length === 1 && <span className="hoop-name">{machine.hoops[0].name}</span>}
    </div>
  );
}

export function Toolbar() {
  const showJumps = useStore((s) => s.showJumps);
  const showDensity = useStore((s) => s.showDensity);
  const showHoop = useStore((s) => s.showHoop);
  const showGrid = useStore((s) => s.showGrid);
  const realistic = useStore((s) => s.realistic);
  const traceAssist = useStore((s) => s.traceAssist);
  const units = useStore((s) => s.units);
  const layout = useStore(selectLayout);
  const jumpsTrimmed = layout ? jumpsToTrimsSetting(layout) !== null : false;
  const basting = layout?.basting.enabled ?? false;
  const knockdown = layout?.knockdown?.enabled ?? false;
  return (
    <header className="toolbar">
      <span className="brand">
        <LuddLogo size={24} />
      </span>
      <CommandButton id="file.new" label="New" />
      <CommandButton id="file.open" label="Open" />
      <CommandButton id="file.save" label="Save" />
      <CommandButton id="file.add" label="Add design" />
      <span className="sep" />
      <CommandButton id="edit.undo" label="↶" aria="Undo" />
      <CommandButton id="edit.redo" label="↷" aria="Redo" />
      <span className="sep" />
      <CommandButton id="file.export" label="Save for machine" primary />
      <span className="spacer" />
      <MachinePicker />
      <CommandButton id="app.help" label="?" aria="Help" />
      <CommandButton id="app.settings" label="⚙" aria="Settings" />
      <Menu
        items={[
          { id: "file.saveAs" },
          { id: "file.samples" },
          { id: "file.picture" },
          { id: "threads.charts", label: "My threads & charts…" },
          { id: "file.print" },
          { id: "file.batch" },
          "separator",
          { id: "stitch.stop" },
          { id: "stitch.trim" },
          { id: "stitch.jumpsToTrims", checked: jumpsTrimmed },
          { id: "stitch.basting", checked: basting },
          { id: "stitch.knockdown", checked: knockdown },
          { id: "arrange.repeat" },
          { id: "ai.advisor" },
          { id: "applique.svg" },
          "separator",
          { id: "view.hoop", checked: showHoop },
          { id: "view.grid", checked: showGrid },
          { id: "view.units", checked: units === "mm" },
          { id: "trace.toggle", checked: traceAssist },
          { id: "view.realistic", checked: realistic },
          { id: "view.jumps", checked: showJumps },
          { id: "view.density", checked: showDensity },
          { id: "view.fit" },
          "separator",
          { id: "app.help" },
          { id: "app.updates" },
          { id: "app.settings" },
        ]}
      />
    </header>
  );
}
