import { getCurrentWebview } from "@tauri-apps/api/webview";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useEffect, useState } from "react";
import {
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
import { formatShortcut } from "./commands";
import { keepFocusOffBars, onKeyDown, onKeyUp, onWindowBlur } from "./keys";
import { BatchDialog } from "./components/BatchDialog";
import { ExportDialog } from "./components/ExportDialog";
import { InfoPanel } from "./components/InfoPanel";
import { LuddMark } from "./components/Logo";
import { PanelResizer, usePanelWidth } from "./components/PanelResizer";
import { Player } from "./components/Player";
import { HelpDialog, SendPreview } from "./components/AIPanels";
import { RepeatDialog } from "./components/RepeatDialog";
import { BrowseDialog, NamesDialog, OffsetDialog } from "./components/FeatureDialogs";
import { SettingsDialog } from "./components/SettingsDialog";
import { StatusBar } from "./components/StatusBar";
import { StitchCanvas } from "./components/StitchCanvas";
import { ChartsDialog } from "./components/ThreadDialogs";
import { DrawHint, ToolRail } from "./components/ToolRail";
import { MachinePicker, Toolbar } from "./components/Toolbar";
import { ZoomControls } from "./components/ZoomControls";
import type { Formats } from "./design/types";
import { connectEngine, shutdownEngine, stopEngine } from "./engine/manager";
import { listen } from "@tauri-apps/api/event";
import { startTraceAssist } from "./traceAssist";
import { startSatinFit } from "./satinFit";
import { installUpdate, startUpdateCheck } from "./updates";
import { startDialogDragging } from "./dragDialogs";
import { ContextMenu } from "./components/ContextMenu";
import { invoke } from "@tauri-apps/api/core";
import { loadPrefs, savePrefs } from "./prefs";
import { isDirty, selectCanvasDark, useStore } from "./store";

const IMAGE_FILE = /\.(png|jpe?g|gif|bmp|webp)$/i;

/** Start the engine (and start it again if it stops); `onReady` runs after the first start. */
function useEngine(onReady: () => void) {
  useEffect(() => {
    connectEngine(async (first) => {
      const client = useStore.getState().engine;
      if (!client) return;
      useStore.getState().setFormats(await client.call<Formats>("formats.list"));
      await loadMachinesAndCharts();
      if (first) onReady();
    });
    return () => {
      stopEngine();
      useStore.getState().setEngine({ state: "starting" }, null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

function useShortcuts() {
  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onWindowBlur);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onWindowBlur);
    };
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
        if (!(await confirmDiscard())) return e.preventDefault();
        // Unanswered recovery from a crash stays for next time.
        if (!isRecoveryWaiting()) await discardRecovery();
        // Let the engine stop by itself, so it deletes its unpacked files from the temp folder.
        await shutdownEngine();
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
/** A .ludd double-clicked while LUDD is already open: the running window opens it (see lib.rs). */
function useOpenFromOtherLaunches() {
  useEffect(() => {
    if (!isTauri()) return;
    let unlisten: (() => void) | undefined;
    let gone = false;
    void listen<string>("ludd:open-file", (e) => void openDesign(e.payload)).then((u) => (gone ? u() : (unlisten = u)));
    return () => {
      gone = true;
      unlisten?.();
    };
  }, []);
}

function RecoveryPrompt({ info, onDone }: { info: RecoveryInfo; onDone: (recovered: boolean) => void }) {
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
          // If it couldn't be shown, the banner stays (the error says why) and the copy is kept.
          void restoreRecovery().then((ok) => ok && onDone(true));
        }}
      >
        Recover
      </button>
      <button
        onClick={() => {
          void discardRecovery().then(() => onDone(false));
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
  const [launchFile, setLaunchFile] = useState<string | null>(null);
  useEngine(() => {
    void checkRecovery().then(async (r) => {
      setRecovery(r);
      // Opened by double-clicking a .ludd project: open it, after the choice about work to recover.
      const file = isTauri() ? await invoke<string | null>("launch_file").catch(() => null) : null;
      if (file && !r) void openDesign(file);
      else setLaunchFile(file);
    });
  });
  useOpenFromOtherLaunches();
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
  useEffect(() => startSatinFit(), []);
  useEffect(() => {
    document.addEventListener("mousedown", keepFocusOffBars, true);
    return () => document.removeEventListener("mousedown", keepFocusOffBars, true);
  }, []);
  const dragging = useFileDrop();
  const hasDoc = useStore((s) => s.history.present !== null);
  const hasDesign = useStore((s) => s.design !== null);

  return (
    <div className="app">
      <Toolbar />
      <Notice />
      {recovery && (
        <RecoveryPrompt
          info={recovery}
          onDone={(recovered) => {
            setRecovery(null);
            if (!launchFile) return;
            if (!recovered) void openDesign(launchFile, true);
            else useStore.getState().notify({ kind: "info", text: `Your work is back. To open ${launchFile.split(/[\\/]/).pop()} too, press Ctrl+O.` });
            setLaunchFile(null);
          }}
        />
      )}
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
      <ContextMenu />
      <SettingsDialog />
      <RepeatDialog />
      <OffsetDialog />
      <BrowseDialog />
      <NamesDialog />
      <HelpDialog />
      <SendPreview />
    </div>
  );
}
