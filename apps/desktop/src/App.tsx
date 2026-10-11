import { getCurrentWebview } from "@tauri-apps/api/webview";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useEffect, useState } from "react";
import {
  COMMANDS,
  addDesign,
  addPicture,
  checkRecovery,
  command,
  confirmDiscard,
  discardRecovery,
  isProjectPath,
  isRecoveryWaiting,
  isTauri,
  loadMachinesAndCharts,
  openDesign,
  restoreRecovery,
  startAutosave,
  startChecks,
  type RecoveryInfo,
} from "./actions";
import { dispatchKey, formatShortcut } from "./commands";
import { letGoNewest } from "./escape";
import { BatchDialog } from "./components/BatchDialog";
import { ExportDialog } from "./components/ExportDialog";
import { InfoPanel } from "./components/InfoPanel";
import { LuddMark } from "./components/Logo";
import { PanelResizer, usePanelWidth } from "./components/PanelResizer";
import { Player } from "./components/Player";
import { HelpDialog, SendPreview } from "./components/AIPanels";
import { RepeatDialog } from "./components/RepeatDialog";
import { SettingsDialog } from "./components/SettingsDialog";
import { StatusBar } from "./components/StatusBar";
import { StitchCanvas } from "./components/StitchCanvas";
import { ChartsDialog } from "./components/ThreadDialogs";
import { DrawHint, ToolRail } from "./components/ToolRail";
import { MachinePicker, Toolbar } from "./components/Toolbar";
import { ZoomControls } from "./components/ZoomControls";
import type { Formats } from "./design/types";
import { startEngine } from "./engine/sidecar";
import { startTraceAssist } from "./traceAssist";
import { installUpdate, startUpdateCheck } from "./updates";
import { startDialogDragging } from "./dragDialogs";
import { invoke } from "@tauri-apps/api/core";
import { loadPrefs, savePrefs } from "./prefs";
import { isDirty, selectCanvasDark, useStore } from "./store";

const IMAGE_FILE = /\.(png|jpe?g|gif|bmp|webp)$/i;

function useEngine(onReady: () => void) {
  useEffect(() => {
    const { setEngine, setFormats } = useStore.getState();
    let stop: (() => void) | undefined;
    let cancelled = false;
    void startEngine((s) => setEngine(s)).then(async (h) => {
      if (cancelled) return h.stop();
      stop = h.stop;
      setEngine(useStore.getState().engineStatus, h.client);
      if (h.client) {
        setFormats(await h.client.call<Formats>("formats.list"));
        await loadMachinesAndCharts();
        onReady();
      }
    });
    return () => {
      cancelled = true;
      stop?.();
      setEngine({ state: "starting" }, null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

function useShortcuts() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target instanceof Element ? e.target : null;
      // Open dialogs close themselves on Esc.
      if (t?.closest("dialog")) return;
      const field = t?.closest<HTMLElement>("input:not([type=range]):not([type=checkbox]), select, textarea");
      if (e.key === "Escape") {
        // Esc lets go: first anything held (a drag, an open list), then the field you're typing in
        // (fields put back their old value), then the Escape commands.
        e.preventDefault();
        if (letGoNewest()) return;
        if (field) {
          // Number boxes save when you leave them: put the old value back first.
          // (Fields that handle Esc themselves have already let go.)
          if (document.activeElement !== field) return;
          if (field instanceof HTMLInputElement && field.type === "number") field.value = field.defaultValue;
          return field.blur();
        }
        dispatchKey(e, COMMANDS);
        return;
      }
      // Let text fields keep their own keys, a focused slider its arrows, and a focused
      // button or tick box its Space and Enter.
      if (field) return;
      if (t?.matches("input[type=range]") && /^(Arrow|Home$|End$|Page)/.test(e.key)) return;
      if (t?.matches(":is(button, input[type=checkbox], summary, [role=menuitem], [role=tab]):focus-visible") && (e.key === " " || e.key === "Enter")) return;
      if (dispatchKey(e, COMMANDS)) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

/** Files dropped onto the window: pictures are added to trace, designs open (or are added to an open one). */
function useFileDrop() {
  const [over, setOver] = useState(false);
  useEffect(() => {
    if (!isTauri()) return;
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    void getCurrentWebview()
      .onDragDropEvent((e) => {
        const p = e.payload;
        if (p.type === "enter" || p.type === "over") setOver(true);
        else if (p.type === "leave") setOver(false);
        else if (p.type === "drop") {
          setOver(false);
          const path = p.paths[0];
          if (!path) return;
          if (IMAGE_FILE.test(path)) void addPicture(path);
          // Dropping onto an open design adds to it (Ctrl+Z takes it out again); otherwise it opens.
          else if (useStore.getState().history.present && !isProjectPath(path)) void addDesign(path);
          else void openDesign(path);
        }
      })
      .then((u) => (cancelled ? u() : (unlisten = u)));
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);
  return over;
}

/** Window title shows the project and a dot for unsaved changes; closing asks before losing work. */
function useWindowTitle() {
  const title = useStore((s) => s.history.present?.layout.title || s.design?.name || "");
  const dirty = useStore(isDirty);
  const hasDoc = useStore((s) => s.history.present !== null);
  useEffect(() => {
    const text = hasDoc ? `${dirty ? "• " : ""}${title || "New design"} – LUDD` : "LUDD";
    document.title = text;
    if (isTauri()) void getCurrentWindow().setTitle(text).catch(() => {});
  }, [title, dirty, hasDoc]);
  useEffect(() => {
    if (!isTauri()) return;
    let unlisten: (() => void) | undefined;
    void getCurrentWindow()
      .onCloseRequested(async (e) => {
        if (!(await confirmDiscard())) e.preventDefault();
        // Unanswered recovery from a crash stays for next time.
        else if (!isRecoveryWaiting()) void discardRecovery();
      })
      .then((u) => (unlisten = u));
    return () => unlisten?.();
  }, []);
}

function Notice() {
  const notice = useStore((s) => s.notice);
  const notify = useStore((s) => s.notify);
  useEffect(() => {
    if (notice?.kind !== "info") return;
    const t = setTimeout(() => notify(null), 5000);
    return () => clearTimeout(t);
  }, [notice, notify]);
  if (!notice) return null;
  return (
    <div className={`notice notice-${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
      <span>{notice.text}</span>
      <button onClick={() => notify(null)} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}

/** Offer back work an unclosed session left behind (crash, power cut, forced restart). */
function RecoveryPrompt({ info, onDone }: { info: RecoveryInfo; onDone: () => void }) {
  const when = info.saved_at ? new Date(info.saved_at * 1000).toLocaleString() : "recently";
  const what = [info.title && `“${info.title}”`, `${info.items} design part${info.items === 1 ? "" : "s"}`, info.images ? `${info.images} picture${info.images === 1 ? "" : "s"}` : ""]
    .filter(Boolean)
    .join(", ");
  return (
    <div className="notice notice-recover" role="alert">
      <span>
        LUDD closed without saving your work from {when} ({what}). Get it back?
      </span>
      <button
        className="primary"
        onClick={() => {
          onDone();
          void restoreRecovery();
        }}
      >
        Recover
      </button>
      <button
        onClick={() => {
          onDone();
          void discardRecovery();
        }}
      >
        Discard
      </button>
    </div>
  );
}

/** A newer version is ready: install it (and restart) now, or later. */
function UpdateBanner() {
  const update = useStore((s) => s.update);
  const setUpdate = useStore((s) => s.setUpdate);
  if (!update) return null;
  return (
    <div className="notice notice-info" role="status">
      <span>
        LUDD {update.version} is ready.{update.notes ? ` ${update.notes.split("\n")[0].slice(0, 160)}` : ""}
      </span>
      <button
        className="primary"
        onClick={async () => {
          if (await confirmDiscard()) void installUpdate();
        }}
      >
        Install and restart
      </button>
      <button onClick={() => setUpdate(null)}>Later</button>
    </div>
  );
}

function EmptyState() {
  const engine = useStore((s) => s.engine);
  const machines = useStore((s) => s.machines);
  const [welcomed, setWelcomed] = useState(() => loadPrefs().welcomed ?? false);
  const [checkUpdates, setCheckUpdates] = useState(true);
  const sample = command("file.samples");
  const open = command("file.open");
  const fresh = command("file.new");

  if (!welcomed && machines.length > 0) {
    return (
      <div className="empty">
        <div className="card">
          <LuddMark size={72} />
          <h1>Welcome to LUDD</h1>
          <p className="tagline">Free + open-source embroidery</p>
          <p>Which embroidery machine do you have?</p>
          <MachinePicker />
          <p className="hint">Not listed? Pick the closest. You can change it any time in Settings (⚙).</p>
          <label className="check">
            <input type="checkbox" checked={checkUpdates} onChange={(e) => setCheckUpdates(e.target.checked)} /> Tell me when a new version of LUDD is out
            <small>LUDD asks GitHub, where it's published, when it starts. Nothing about you or your designs is sent.</small>
          </label>
          <button
            className="primary"
            onClick={() => {
              savePrefs({ welcomed: true, checkUpdates, machineId: useStore.getState().machineId ?? undefined });
              setWelcomed(true);
            }}
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="empty">
      <div className="card">
        <LuddMark size={72} />
        <h1 className="ludd-word">LUDD</h1>
        <p>Open a design to see it, change it and save it for your machine, or draw your own.</p>
        <div className="row-buttons">
          <button className="primary big" onClick={open.run} disabled={!engine}>
            Open a design… <kbd>{formatShortcut(open.shortcut)}</kbd>
          </button>
          <button className="big" onClick={fresh.run} disabled={!engine}>
            Start a new design <kbd>{formatShortcut(fresh.shortcut)}</kbd>
          </button>
        </div>
        <button className="link" onClick={sample.run} disabled={!engine}>
          Or try one of the sample designs
        </button>
        <p className="hint">
          Or drag an embroidery file (PES, JEF, DST…), a LUDD project, or a picture to trace into this window.
        </p>
      </div>
    </div>
  );
}

export function App() {
  const [recovery, setRecovery] = useState<RecoveryInfo | null>(null);
  useEngine(() => {
    void checkRecovery().then(async (r) => {
      setRecovery(r);
      // Opened by double-clicking a .ludd project: open it (unless there's work to recover first).
      if (!r && isTauri()) {
        const file = await invoke<string | null>("launch_file").catch(() => null);
        if (file) void openDesign(file);
      }
    });
  });
  useEffect(() => startUpdateCheck(), []);
  useEffect(() => startDialogDragging(), []);
  useShortcuts();
  useWindowTitle();
  useEffect(() => startAutosave(), []);
  useEffect(() => startChecks(), []);
  useEffect(() => {
    const q = matchMedia("(prefers-color-scheme: dark)");
    const on = () => useStore.getState().setSystemDark(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, []);
  const canvasDark = useStore(selectCanvasDark);
  const [panelWidth, setPanelWidth] = usePanelWidth();
  useEffect(() => startTraceAssist(), []);
  const dragging = useFileDrop();
  const hasDoc = useStore((s) => s.history.present !== null);
  const hasDesign = useStore((s) => s.design !== null);

  return (
    <div className="app">
      <Toolbar />
      <Notice />
      {recovery && <RecoveryPrompt info={recovery} onDone={() => setRecovery(null)} />}
      <UpdateBanner />
      <div className="workspace">
        {hasDoc && <ToolRail />}
        <main className={`stage${canvasDark ? " dark" : ""}${dragging ? " drop-target" : ""}`}>
          <StitchCanvas />
          {!hasDoc && <EmptyState />}
          {hasDoc && <ZoomControls />}
          {hasDoc && <DrawHint />}
        </main>
        {hasDoc && (
          <>
            <PanelResizer width={panelWidth} onWidth={setPanelWidth} />
            <div className="info-panel-wrap" style={{ width: panelWidth }}>
              <InfoPanel />
            </div>
          </>
        )}
      </div>
      {hasDesign && <Player />}
      <StatusBar />
      <BatchDialog />
      <ExportDialog />
      <ChartsDialog />
      <SettingsDialog />
      <RepeatDialog />
      <HelpDialog />
      <SendPreview />
    </div>
  );
}
