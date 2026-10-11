/**
 * Updates from the GitHub Releases page. The one network request LUDD makes outside the AI
 * add-on, and only if the user leaves "Check for new versions" on: it asks GitHub whether a
 * newer version exists; nothing about the user or their designs is sent. Updates are signed;
 * the updater refuses anything not signed with LUDD's key.
 */
import { getVersion } from "@tauri-apps/api/app";
import { relaunch } from "@tauri-apps/plugin-process";
import { check, type Update } from "@tauri-apps/plugin-updater";
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
    // Offline, or GitHub unreachable: say nothing unless the user asked.
    if (manual) notify({ kind: "error", text: `Couldn't check for updates: ${err instanceof Error ? err.message : String(err)}` });
  }
}

/** Download, install and restart. Unsaved work is offered back by recovery after the restart. */
export async function installUpdate(): Promise<void> {
  if (!pending) return;
  const { setUpdate, setLoading } = useStore.getState();
  try {
    setLoading(`Downloading LUDD ${pending.version}…`);
    await pending.downloadAndInstall();
    await relaunch();
  } catch (err) {
    setLoading(null);
    setUpdate(null);
    useStore.getState().notify({ kind: "error", text: `The update didn't install: ${err instanceof Error ? err.message : String(err)}` });
  }
}

/** On start, if the user allows it (on unless they turned it off), and only in the installed app. */
export function startUpdateCheck(): () => void {
  if (!isTauri() || import.meta.env.DEV || loadPrefs().checkUpdates === false) return () => {};
  const t = setTimeout(() => void checkForUpdates(false), 8000);
  return () => clearTimeout(t);
}
