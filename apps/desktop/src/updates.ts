/**
 * Updates from the GitHub Releases page. The one network request LUDD makes outside the AI
 * add-on, and only if the user leaves "Check for new versions" on: it asks GitHub whether a
 * newer version exists; nothing about the user or their designs is sent. Updates are signed;
 * the updater refuses anything not signed with LUDD's key.
 */
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type Update } from "@tauri-apps/plugin-updater";
import { restartEngine, shutdownEngine } from "./engine/manager";
import { isTauri } from "./engine/sidecar";
import { loadPrefs } from "./prefs";
import { useStore } from "./store";

let pending: Update | null = null;

export async function appVersion(): Promise<string> {
  return isTauri() ? getVersion() : "dev";
}

/** Look for a newer version. `manual`: the user asked, so say so when there's none. */
export async function checkForUpdates(manual = false): Promise<void> {
  const { notify, setUpdate } = useStore.getState();
  if (!isTauri()) {
    if (manual) notify({ kind: "info", text: "Updates are checked in the installed app." });
    return;
  }
  try {
    const update = await check();
    if (update) {
      pending = update;
      setUpdate({ version: update.version, notes: update.body ?? "" });
    } else if (manual) {
      notify({ kind: "info", text: `You have the newest LUDD (${await getVersion()}).` });
    }
  } catch (err) {
    // Offline, or GitHub unreachable: say nothing unless the user asked, and then in plain words.
    console.warn("Update check failed:", err);
    if (manual) notify({ kind: "error", text: updateCheckError(err) });
  }
}

/** Download, install and restart. Unsaved work is offered back by recovery after the restart. */
export async function installUpdate(): Promise<void> {
  if (!pending) return;
  const { setUpdate, setLoading } = useStore.getState();
  let stopped = false;
  try {
    setLoading(`Downloading LUDD ${pending.version}…`);
    await pending.download();
    // Stop the engine cleanly first: the installer replaces it, and stopping by itself lets it
    // delete its unpacked files.
    await shutdownEngine();
    stopped = true;
    await pending.install();
    await relaunch();
  } catch (err) {
    if (stopped) restartEngine();
    setLoading(null);
    setUpdate(null);
    useStore.getState().notify({ kind: "error", text: `The update didn't install: ${err instanceof Error ? err.message : String(err)}` });
  }
}

/** What a failed check tells the user: the raw error only when it isn't about the connection. */
export function updateCheckError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  if (/send|request|connect|network|dns|resolve|timed? ?out|offline|unreachable|tls|certificate/i.test(raw))
    return "Couldn't reach the update server. Check your internet connection and try again.";
  return `Couldn't check for updates: ${raw}`;
}

/** Whether the start-up check may run now: the first-run question is answered and the user didn't turn it off. */
export function mayCheckOnStart(): "yes" | "no" | "later" {
  const prefs = loadPrefs();
  if (prefs.checkUpdates === false) return "no";
  return prefs.welcomed ? "yes" : "later";
}

/** On start, if the user allows it (on unless they turned it off), and only in the installed app.
 *  The choice is read again when the check is due, and nothing is asked before the first-run
 *  card ("Tell me when a new version is out") has been answered. */
export function startUpdateCheck(delay = 8000): () => void {
  if (!isTauri() || import.meta.env.DEV) return () => {};
  let t: ReturnType<typeof setTimeout>;
  const due = () => {
    const may = mayCheckOnStart();
    if (may === "yes") void checkForUpdates(false);
    else if (may === "later") t = setTimeout(due, delay);
  };
  t = setTimeout(due, delay);
  return () => clearTimeout(t);
}
