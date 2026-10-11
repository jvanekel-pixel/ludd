/** Per-user UI preferences in localStorage. Every access is guarded: storage can be unavailable. */

export type Prefs = {
  machineId?: string;
  hoopId?: string;
  showHoop?: boolean;
  showGrid?: boolean;
  realistic?: boolean;
  traceAssist?: boolean;
  traceStep?: number;
  font?: { path: string; index: number; family: string; style: string };
  units?: "in" | "mm";
  theme?: "system" | "light" | "dark";
  canvasBg?: "theme" | "light";
  /** Ask GitHub for a newer version when LUDD starts (on unless turned off). */
  checkUpdates?: boolean;
  /** The fabric picked last; new designs start with it. */
  fabric?: string;
  welcomed?: boolean;
};

const KEY = "ludd.prefs";
const OLD_KEY = "threadline.prefs"; // before the app was renamed

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY) ?? localStorage.getItem(OLD_KEY);
    return raw ? (JSON.parse(raw) as Prefs) : {};
  } catch {
    return {};
  }
}

export function savePrefs(patch: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...loadPrefs(), ...patch }));
  } catch {
    // Preferences are a convenience; ignore storage failures.
  }
}
