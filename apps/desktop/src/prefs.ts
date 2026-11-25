/** Per-user UI preferences in localStorage. Every access is guarded: storage can be unavailable. */

export type Prefs = {
  machineId?: string;
  hoopId?: string;
  showHoop?: boolean;
  showGrid?: boolean;
  realistic?: boolean;
  seeThrough?: boolean;
  traceAssist?: boolean;
  traceStep?: number;
  font?: { path: string; index: number; family: string; style: string };
  units?: "in" | "mm";
  theme?: "system" | "light" | "dark";
  canvasBg?: "theme" | "light";
  /** Ask GitHub for a newer version when LUDD starts (on unless turned off). */
  checkUpdates?: boolean;
  /** Stitch-out speed, stitches per second. */
  playSpeed?: number;
  /** Width of the right panel, px. */
  panelWidth?: number;
  /** Right-panel sections open (true) or folded, keyed "section@selection-kind" or "sub:id". */
  sections?: Record<string, boolean>;
  /** Your last stitch settings per kind of shape: new shapes start with them. */
  objectDefaults?: Partial<Record<"run" | "satin" | "fill" | "applique", Record<string, unknown>>>;
  /** Width of new satin ribbons, mm. */
  satinWidth?: number;
  /** Auto-trace: how far apart its points are, mm. */
  traceSpacing?: number;
  /** Auto-trace: how readily a guess spreads into similar colors (1-10). */
  traceSpread?: number;
  /** Auto-trace: use the AI tracing model when it's downloaded. */
  traceAI?: boolean;
  /** Auto-trace: how often you've used each kind of guess, so your usual one comes first. */
  guessPicks?: Record<string, number>;
  /** Preview on a garment, and its color. */
  previewGarment?: "none" | "tshirt" | "tote" | "towel" | "bodysuit" | "cap";
  previewColor?: string;
  showRulers?: boolean;
  /** The design browser's last folder. */
  browseFolder?: string;
  /** The fabric picked last; new designs start with it. */
  fabric?: string;
  /** Sides asked for last in "Add a polygon". */
  polygonSides?: number;
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
