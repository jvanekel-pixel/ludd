import { create } from "zustand";
import type { Advice, AIEstimate, AISettings } from "./ai";
import type { Units } from "./design/grid";
import type { History } from "./design/layout";
import { blockStartStitches, stitchRecordIndex } from "./design/player";
import type { ChartSummary, CheckResult, Design, Doc, Fabric, FontInfo, Formats, Layout, Machine, ObjectKind, PathNode, RefImage, Thread } from "./design/types";
import type { RpcClient } from "./engine/rpc";
import type { EngineStatus } from "./engine/sidecar";
import { loadPrefs, savePrefs } from "./prefs";
import { applyTheme, resolveTheme, type ThemeChoice } from "./theme";

/** Stitch-out speeds, stitches per second. 12 is a home machine at full speed (about 710 a minute). */
export const PLAYER_SPEEDS = [2, 5, 12, 25, 50, 100, 200, 500, 1000, 2000, 5000] as const;
export const MACHINE_SPEED = 12;

export type Notice = { kind: "error" | "info"; text: string };

/** What a click on the canvas does: select and move, or draw a new object. */
export type Tool = "select" | "run" | "satin" | "fill" | "text";
export type ZoomRequest = {
  kind: "in" | "out" | "actual" | "scale" | "box";
  n: number;
  /** "scale": a multiple of real size. */
  factor?: number;
  /** "box": the area to show, mm. */
  box?: [number, number, number, number];
};

/** Trace Assist's proposal for the next point (mm). */
export type Ghost = {
  point: [number, number];
  alternatives: [number, number][];
  confidence: number;
  corner: boolean;
  close: boolean;
  rails: [[number, number], [number, number]] | null;
};

/** A selected point of a drawn object: which object, which list of points, which point. */
export type NodeRef = { id: string; list: string | number; index: number };

/** A shape being drawn: clicks so far. A satin's clicks alternate between its two sides. */
export type Pen = { kind: ObjectKind; a: PathNode[]; b: PathNode[]; replaceId?: string; /** Drawing a hole in this fill (O). */ holeFor?: string };

type State = {
  engineStatus: EngineStatus;
  engine: RpcClient | null;
  formats: Formats | null;

  /** The open document (layout and pictures) with undo history. `design` is the layout's last render. */
  history: History;
  design: Design | null;
  /** A selected layout item or picture (ids are unique across both). */
  selectedId: string | null;
  /** Other selected designs and shapes, with `selectedId` (Shift+click, Ctrl+A, a group). */
  extraIds: string[];
  /** Where the open project is saved, if it has been. */
  projectPath: string | null;
  /** The document as last saved; anything else means unsaved changes. */
  savedDoc: Doc | null;
  tool: Tool;
  /** Thread for newly drawn objects: the last one used. */
  drawThread: Thread;
  pen: Pen | null;
  /** Trace Assist: on/off, its proposal, and how far ahead it looks (mm). */
  traceAssist: boolean;
  ghost: Ghost | null;
  traceStep: number;
  selectedNode: NodeRef | null;
  /** Measuring a picture: the points clicked so far (two needed). */
  measure: { imageId: string; points: [number, number][] } | null;
  /** Record index of each stitch; derived from `design`. */
  stitchIdx: Int32Array;
  /** Stitch count where each color block starts; derived from `design`. */
  blockStarts: number[];
  loading: string | null;

  /** Stitches sewn so far in the player; equals info.stitches when showing the whole design. */
  playhead: number;
  playing: boolean;
  speed: number;
  showJumps: boolean;
  /** Bumped to ask the canvas to fit the design to the window. */
  fitRequest: number;

  batchOpen: boolean;
  exportOpen: boolean;
  repeatOpen: boolean;
  helpOpen: boolean;
  /** A newer version is ready to install. */
  update: { version: string; notes: string } | null;
  /** AI add-on settings (null until the engine answers). */
  ai: AISettings | null;
  /** A cloud request waiting for the user's Send or Cancel. */
  aiPreview: { estimate: AIEstimate; resolve: (send: boolean) => void } | null;
  /** Stitch Advisor proposals waiting to be accepted or dismissed. */
  advice: (Advice & { busy: boolean }) | null;
  /** Hoopings to show on the canvas while saving a split design (windows in mm, numbered). */
  splitPreview: { window_mm: number[]; marks: number[][] }[] | null;
  chartsOpen: boolean;
  notice: Notice | null;

  machines: Machine[];
  machineId: string | null;
  hoopId: string | null;
  showHoop: boolean;
  showGrid: boolean;
  /** Shaded thread instead of flat lines. */
  realistic: boolean;
  units: Units;
  /** Light or dark mode, or follow the computer. */
  theme: ThemeChoice;
  /** The computer is in dark mode (kept up to date). */
  systemDark: boolean;
  /** Design background: follow light/dark mode, or always light fabric. */
  canvasBg: "theme" | "light";
  settingsOpen: boolean;
  /** Current canvas zoom in px per mm, for the zoom readout. */
  zoomScale: number;
  /** Bumped to ask the canvas to zoom; `kind` says how. */
  zoomRequest: ZoomRequest;
  /** View toggles from Embrilliance's hotkeys: stitch points (P), stitches (N), pictures (B), crosshairs (E). */
  showPoints: boolean;
  showStitches: boolean;
  showPictures: boolean;
  crosshair: boolean;
  /** The drawing tool used last (D and X go back to it). */
  lastTool: Exclude<Tool, "select">;
  /** Measuring tool (M): the points clicked, in mm. */
  ruler: [number, number][] | null;
  /** Inclination tool (I): drawing a line to set a fill's stitch angle. */
  angleFor: { id: string; points: [number, number][] } | null;
  charts: ChartSummary[];
  /** Installed fonts (loaded the first time lettering is used). */
  fonts: FontInfo[] | null;
  fabrics: Fabric[];
  /** Quality checks for the current design (refreshed after each change). */
  checks: CheckResult | null;
  /** Show the density map over the design. */
  showDensity: boolean;
  /** New points land on the grid's lines. */
  snapGrid: boolean;
  /** Bumped to ask the canvas to centre on a spot (mm). */
  centerRequest: { at: [number, number]; n: number } | null;
};

type Actions = {
  setEngine: (status: EngineStatus, client?: RpcClient | null) => void;
  setFormats: (f: Formats) => void;
  setHistory: (h: History) => void;
  setTool: (t: Tool) => void;
  setDrawThread: (t: Thread) => void;
  setPen: (p: Pen | null) => void;
  setGhost: (g: Ghost | null) => void;
  setTraceStep: (mm: number) => void;
  toggleTraceAssist: () => void;
  selectNode: (n: NodeRef | null) => void;
  setMeasure: (m: { imageId: string; points: [number, number][] } | null) => void;
  markSaved: (path: string | null) => void;
  /** Show a new render. `fresh` (a newly opened design) resets the player and fits the view. */
  setDesign: (d: Design | null, fresh?: boolean) => void;
  select: (id: string | null) => void;
  /** Select several designs and shapes: `primary` is the one the panel shows. */
  setSelection: (primary: string | null, extras: string[]) => void;
  setLoading: (what: string | null) => void;
  setPlayhead: (n: number) => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (s: number) => void;
  toggleJumps: () => void;
  requestFit: () => void;
  setBatchOpen: (open: boolean) => void;
  setExportOpen: (open: boolean) => void;
  setRepeatOpen: (open: boolean) => void;
  setHelpOpen: (open: boolean) => void;
  setUpdate: (u: { version: string; notes: string } | null) => void;
  setAI: (ai: AISettings) => void;
  setAIPreview: (p: { estimate: AIEstimate; resolve: (send: boolean) => void } | null) => void;
  setAdvice: (a: (Advice & { busy: boolean }) | null) => void;
  setSplitPreview: (p: { window_mm: number[]; marks: number[][] }[] | null) => void;
  setChartsOpen: (open: boolean) => void;
  notify: (n: Notice | null) => void;
  setMachines: (m: Machine[]) => void;
  setMachine: (id: string | null) => void;
  setHoop: (id: string) => void;
  toggleHoop: () => void;
  toggleGrid: () => void;
  toggleRealistic: () => void;
  toggleUnits: () => void;
  setUnits: (u: Units) => void;
  setTheme: (t: ThemeChoice) => void;
  setSystemDark: (dark: boolean) => void;
  setCanvasBg: (bg: "theme" | "light") => void;
  setSettingsOpen: (open: boolean) => void;
  setZoomScale: (s: number) => void;
  requestZoom: (kind: ZoomRequest["kind"], extra?: { factor?: number; box?: [number, number, number, number] }) => void;
  toggleView: (key: "showPoints" | "showStitches" | "showPictures" | "crosshair") => void;
  setRuler: (r: [number, number][] | null) => void;
  setAngleFor: (a: { id: string; points: [number, number][] } | null) => void;
  setCharts: (c: ChartSummary[]) => void;
  setFonts: (f: FontInfo[]) => void;
  setFabrics: (f: Fabric[]) => void;
  setChecks: (c: CheckResult | null) => void;
  toggleDensity: () => void;
  toggleSnapGrid: () => void;
  requestCenter: (at: [number, number]) => void;
};

const prefs = loadPrefs();

export const selectMachine = (s: State): Machine | null => s.machines.find((m) => m.id === s.machineId) ?? null;
export const selectHoop = (s: State) => {
  const m = selectMachine(s);
  return m ? (m.hoops.find((h) => h.id === s.hoopId) ?? m.hoops[0]) : null;
};
export const selectLayout = (s: State): Layout | null => s.history.present?.layout ?? null;
export const selectImages = (s: State): RefImage[] => s.history.present?.images ?? [];
/** Index of the selected item in the layout, or -1. */
export const selectedIndex = (s: State): number =>
  s.history.present?.layout.items.findIndex((it) => it.id === s.selectedId) ?? -1;
export const selectedImage = (s: State): RefImage | null =>
  s.history.present?.images.find((im) => im.id === s.selectedId) ?? null;
/** The design area is dark: dark mode is showing and the user hasn't asked for light fabric. */
export const selectCanvasDark = (s: State): boolean => s.canvasBg !== "light" && resolveTheme(s.theme, s.systemDark) === "dark";
/** Every selected design and shape (the panel's one first), in sewing order of selection. */
export const selectedIds = (s: State): string[] => (s.selectedId ? [s.selectedId, ...s.extraIds] : []);
export const isDirty = (s: State): boolean => s.history.present !== s.savedDoc;

export const useStore = create<State & Actions>()((set) => ({
  engineStatus: { state: "starting" },
  engine: null,
  formats: null,
  history: { past: [], present: null, future: [] },
  design: null,
  selectedId: null,
  extraIds: [],
  projectPath: null,
  savedDoc: null,
  tool: "select",
  drawThread: { color: "#1f3a93", name: "Navy", catalog: "", brand: "" },
  pen: null,
  traceAssist: prefs.traceAssist ?? true,
  ghost: null,
  traceStep: prefs.traceStep ?? 3,
  selectedNode: null,
  measure: null,
  stitchIdx: new Int32Array(0),
  blockStarts: [],
  loading: null,
  playhead: 0,
  playing: false,
  speed: prefs.playSpeed ?? 200,
  showJumps: false,
  fitRequest: 0,
  batchOpen: false,
  exportOpen: false,
  repeatOpen: false,
  helpOpen: false,
  update: null,
  ai: null,
  aiPreview: null,
  advice: null,
  splitPreview: null,
  chartsOpen: false,
  notice: null,
  machines: [],
  machineId: prefs.machineId ?? null,
  hoopId: prefs.hoopId ?? null,
  showHoop: prefs.showHoop ?? true,
  showGrid: prefs.showGrid ?? true,
  realistic: prefs.realistic ?? true,
  units: prefs.units ?? "in",
  theme: prefs.theme ?? "system",
  systemDark: typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches,
  canvasBg: prefs.canvasBg ?? "theme",
  settingsOpen: false,
  zoomScale: 1,
  zoomRequest: { kind: "actual", n: 0 },
  showPoints: false,
  showStitches: true,
  showPictures: true,
  crosshair: false,
  lastTool: "fill",
  ruler: null,
  angleFor: null,
  charts: [],
  fonts: null,
  fabrics: [],
  checks: null,
  showDensity: false,
  snapGrid: false,
  centerRequest: null,

  setEngine: (engineStatus, client) =>
    set((s) => ({ engineStatus, engine: client === undefined ? s.engine : client })),
  setFormats: (formats) => set({ formats }),
  setHistory: (history) =>
    set((s) => {
      const doc = history.present;
      // Drop a selection whose item or picture no longer exists (e.g. after undoing an add).
      const exists = doc && (doc.layout.items.some((it) => it.id === s.selectedId) || doc.images.some((im) => im.id === s.selectedId));
      // Measuring a picture or holding a point that's gone would leave clicks doing nothing.
      const measure = s.measure && doc?.images.some((im) => im.id === s.measure!.imageId) ? s.measure : null;
      const selectedNode = s.selectedNode && doc?.layout.items.some((it) => it.id === s.selectedNode!.id) ? s.selectedNode : null;
      const extraIds = exists && doc ? s.extraIds.filter((id) => doc.layout.items.some((it) => it.id === id)) : [];
      return { history, selectedId: exists ? s.selectedId : null, extraIds, measure, selectedNode };
    }),
  setTool: (tool) =>
    set((s) => ({
      tool,
      pen: null,
      selectedId: tool === "select" ? s.selectedId : null,
      lastTool: tool === "select" ? s.lastTool : tool,
      ruler: null,
      angleFor: null,
    })),
  setDrawThread: (drawThread) => set({ drawThread }),
  // Any change to the drawing makes the old suggestion stale.
  setPen: (pen) => set({ pen, ghost: null }),
  setGhost: (ghost) => set({ ghost }),
  setTraceStep: (traceStep) => set({ traceStep }),
  toggleTraceAssist: () =>
    set((s) => {
      savePrefs({ traceAssist: !s.traceAssist });
      return { traceAssist: !s.traceAssist, ghost: null };
    }),
  selectNode: (selectedNode) => set({ selectedNode }),
  setMeasure: (measure) => set({ measure }),
  markSaved: (projectPath) => set((s) => ({ projectPath, savedDoc: s.history.present })),
  setDesign: (design, fresh = false) =>
    set((s) => {
      const stitchIdx = design ? stitchRecordIndex(design) : new Int32Array(0);
      const atEnd = s.playhead >= s.stitchIdx.length;
      return {
        design,
        stitchIdx,
        blockStarts: design ? blockStartStitches(design, stitchIdx) : [],
        // Keep the player where it was while editing, unless it was showing everything.
        playhead: fresh || atEnd ? stitchIdx.length : Math.min(s.playhead, stitchIdx.length),
        playing: fresh ? false : s.playing,
        fitRequest: fresh ? s.fitRequest + 1 : s.fitRequest,
      };
    }),
  select: (selectedId) => set((s) => ({ selectedId, extraIds: [], selectedNode: s.selectedNode?.id === selectedId ? s.selectedNode : null })),
  setSelection: (selectedId, extras) =>
    set((s) => ({
      selectedId,
      extraIds: selectedId ? extras.filter((x) => x !== selectedId) : [],
      selectedNode: s.selectedNode?.id === selectedId ? s.selectedNode : null,
    })),
  setLoading: (loading) => set({ loading }),
  setPlayhead: (n) =>
    set((s) => ({ playhead: Math.max(0, Math.min(Math.round(n), s.stitchIdx.length)) })),
  setPlaying: (playing) =>
    set((s) => ({
      playing,
      // Pressing play at the end restarts from the beginning.
      playhead: playing && s.playhead >= s.stitchIdx.length ? 0 : s.playhead,
    })),
  setSpeed: (speed) => {
    savePrefs({ playSpeed: speed });
    set({ speed });
  },
  toggleJumps: () => set((s) => ({ showJumps: !s.showJumps })),
  requestFit: () => set((s) => ({ fitRequest: s.fitRequest + 1 })),
  setBatchOpen: (batchOpen) => set({ batchOpen }),
  setExportOpen: (exportOpen) => set(exportOpen ? { exportOpen } : { exportOpen, splitPreview: null }),
  setRepeatOpen: (repeatOpen) => set({ repeatOpen }),
  setHelpOpen: (helpOpen) => set({ helpOpen }),
  setUpdate: (update) => set({ update }),
  setAI: (ai) => set({ ai }),
  setAIPreview: (aiPreview) => set({ aiPreview }),
  setAdvice: (advice) => set({ advice }),
  setSplitPreview: (splitPreview) => set({ splitPreview }),
  setChartsOpen: (chartsOpen) => set({ chartsOpen }),
  notify: (notice) => set({ notice }),
  setMachines: (machines) =>
    set((s) => {
      // Keep the saved machine if it still exists; otherwise pick the first (the user's PE550D).
      const machineId = machines.some((m) => m.id === s.machineId) ? s.machineId : (machines[0]?.id ?? null);
      const m = machines.find((x) => x.id === machineId);
      const hoopId = m?.hoops.some((h) => h.id === s.hoopId) ? s.hoopId : (m?.hoops[0]?.id ?? null);
      return { machines, machineId, hoopId };
    }),
  setMachine: (machineId) =>
    set((s) => {
      const hoopId = s.machines.find((m) => m.id === machineId)?.hoops[0]?.id ?? null;
      savePrefs({ machineId: machineId ?? undefined, hoopId: hoopId ?? undefined });
      return { machineId, hoopId };
    }),
  setHoop: (hoopId) => {
    savePrefs({ hoopId });
    set({ hoopId });
  },
  toggleHoop: () =>
    set((s) => {
      savePrefs({ showHoop: !s.showHoop });
      return { showHoop: !s.showHoop };
    }),
  toggleGrid: () =>
    set((s) => {
      savePrefs({ showGrid: !s.showGrid });
      return { showGrid: !s.showGrid };
    }),
  toggleRealistic: () =>
    set((s) => {
      savePrefs({ realistic: !s.realistic });
      return { realistic: !s.realistic };
    }),
  toggleUnits: () =>
    set((s) => {
      const units = s.units === "in" ? "mm" : "in";
      savePrefs({ units });
      return { units };
    }),
  setUnits: (units) => {
    savePrefs({ units });
    set({ units });
  },
  setTheme: (theme) => {
    savePrefs({ theme });
    applyTheme(theme);
    set({ theme });
  },
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setSystemDark: (systemDark) => set({ systemDark }),
  setCanvasBg: (canvasBg) => {
    savePrefs({ canvasBg });
    set({ canvasBg });
  },
  setZoomScale: (zoomScale) => set({ zoomScale }),
  requestZoom: (kind, extra) => set((s) => ({ zoomRequest: { kind, n: s.zoomRequest.n + 1, ...extra } })),
  toggleView: (key) => set((s) => ({ [key]: !s[key] }) as Partial<State>),
  setRuler: (ruler) => set({ ruler }),
  setAngleFor: (angleFor) => set({ angleFor }),
  setCharts: (charts) => set({ charts }),
  setFonts: (fonts) => set({ fonts }),
  setFabrics: (fabrics) => set({ fabrics }),
  setChecks: (checks) => set({ checks }),
  toggleDensity: () => set((s) => ({ showDensity: !s.showDensity })),
  toggleSnapGrid: () => set((s) => ({ snapGrid: !s.snapGrid })),
  requestCenter: (at) => set((s) => ({ centerRequest: { at, n: (s.centerRequest?.n ?? 0) + 1 } })),
}));

// Dev-only handle for debugging in the browser preview (no engine there).
if (import.meta.env.DEV && typeof window !== "undefined") {
  (window as unknown as { __ludd: typeof useStore }).__ludd = useStore;
}
