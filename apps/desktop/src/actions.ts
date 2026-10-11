import { message, open, save } from "@tauri-apps/plugin-dialog";
import type { Command } from "./commands";
import {
  IDENTITY,
  addImage,
  addItem,
  addObject,
  clearRecolors,
  deleteColor,
  duplicateItem,
  repeatItem,
  type RepeatSpec,
  insertAt,
  itemLabel,
  jumpsToTrims,
  jumpsToTrimsSetting,
  mirror,
  moveBy,
  newDoc,
  newId,
  pushHistory,
  shapeNodes,
  recolor,
  redo,
  removeImage,
  removeItem,
  rotateBy,
  undo,
  updateImage,
  updateObject,
  type History,
} from "./design/layout";
import { visibleRecords } from "./design/player";
import type {
  Chart,
  ChartSummary,
  CheckResult,
  ConvertResult,
  CutStops,
  Design,
  Doc,
  ExportOptions,
  ExportReport,
  Fabric,
  FileItem,
  FontInfo,
  FontRef,
  Layout,
  Machine,
  ObjectItem,
  ObjectKind,
  PathNode,
  RefImage,
  Thread,
  ThreadMatch,
  TextItem,
} from "./design/types";
import { isObject } from "./design/types";
import { RpcError } from "./engine/rpc";
import { isTauri } from "./engine/sidecar";
import { canAdvise, loadAISettings, runAdvisor } from "./ai";
import { checkForUpdates } from "./updates";
import { resolveResource } from "@tauri-apps/api/path";
import { printDesign } from "./print";
import { cancelTraceQueue, queueAccept, queueAcceptMany, setStep, toggleLastPoint } from "./traceAssist";
import { loadPrefs, savePrefs } from "./prefs";
import { isDirty, PLAYER_SPEEDS, selectHoop, selectMachine, useStore, type Tool } from "./store";

/** Formats listed first in pickers: the user's Brother (PES) and Janome (JEF). */
export const PREFERRED_FORMATS = ["pes", "jef"];
export const PROJECT_EXT = "ludd";
/** Projects saved before the app was renamed (Threadline) still open. */
const OLD_PROJECT_EXTS = ["thl"];
export const isProjectPath = (path: string) => [PROJECT_EXT, ...OLD_PROJECT_EXTS].some((x) => path.toLowerCase().endsWith(`.${x}`));
const IMAGE_EXTS = ["png", "jpg", "jpeg", "gif", "bmp", "webp"];

const OPEN_TIMEOUT = 60_000;
const CONVERT_TIMEOUT = 30 * 60_000;
export const NUDGE_MM = 1;
export const NUDGE_BIG_MM = 10;
export const JUMP_TRIM_MM = 3;
/** New pictures start this wide (the PE550D's 4" hoop) unless that's bigger than the hoop. */
const PICTURE_START_MM = 100;

function engine() {
  const client = useStore.getState().engine;
  if (!client) throw new Error("The engine isn't connected");
  return client;
}

function errorText(err: unknown): string {
  if (err instanceof RpcError || err instanceof Error) return err.message;
  return String(err);
}

export function fail(err: unknown) {
  useStore.getState().notify({ kind: "error", text: errorText(err) });
}

export function info(text: string) {
  useStore.getState().notify({ kind: "info", text });
}

export function sortFormats<T extends { ext: string }>(list: readonly T[]): T[] {
  const rank = (e: string) => {
    const i = PREFERRED_FORMATS.indexOf(e);
    return i < 0 ? PREFERRED_FORMATS.length : i;
  };
  return [...list].sort((a, b) => rank(a.ext) - rank(b.ext) || a.ext.localeCompare(b.ext));
}

export function basename(path: string) {
  return path.split(/[\\/]/).pop() ?? path;
}

function stem(path: string) {
  return basename(path).replace(/\.[^.]+$/, "");
}

const both = (exts: string[]) => exts.flatMap((e) => [e, e.toUpperCase()]);

async function pickDesignFile(title: string, withProjects: boolean): Promise<string | null> {
  const exts = useStore.getState().formats?.read.map((f) => f.ext) ?? PREFERRED_FORMATS;
  return open({
    title,
    multiple: false,
    directory: false,
    filters: [
      ...(withProjects ? [{ name: "LUDD projects and embroidery designs", extensions: both([PROJECT_EXT, ...OLD_PROJECT_EXTS, ...exts]) }] : []),
      { name: "Embroidery designs", extensions: both(exts) },
      { name: "All files", extensions: ["*"] },
    ],
  });
}

// ---------------------------------------------------------------- document and history

let renderSeq = 0;
/** The history being rendered right now, if any. Edits made meanwhile build on it, so a quick
 *  second edit (holding an arrow key, a recolor then a nudge) never loses the first. */
let pending: History | null = null;

function latestHistory(): History {
  return pending ?? useStore.getState().history;
}

export function currentDoc(): Doc | null {
  return latestHistory().present;
}

export function currentLayout(): Layout | null {
  return currentDoc()?.layout ?? null;
}

/** Show `history.present`. Only the latest of overlapping renders is applied. */
async function showHistory(history: History, fresh = false): Promise<boolean> {
  const seq = ++renderSeq;
  const { setHistory, setDesign } = useStore.getState();
  const doc = history.present;
  if (!doc || doc.layout.items.length === 0) {
    // Nothing to stitch yet (a new project, or only pictures): the canvas still shows.
    pending = null;
    setHistory(history);
    setDesign(null, fresh);
    return true;
  }
  pending = history;
  try {
    const design = await engine().call<Design>("layout.render", { layout: doc.layout }, OPEN_TIMEOUT);
    if (seq !== renderSeq) return false;
    pending = null;
    setHistory(history);
    setDesign(design, fresh);
    return true;
  } catch (err) {
    // The edit didn't happen: later edits build on what's on screen.
    if (seq === renderSeq) pending = null;
    fail(err);
    return false;
  }
}

/** Apply an edit to the whole document: render it, and only then add it to the undo history. */
export async function commitDoc(next: Doc) {
  return showHistory(pushHistory(latestHistory(), next));
}

/** Apply an edit to the layout. */
export async function commit(next: Layout) {
  const doc = currentDoc();
  return commitDoc({ layout: next, images: doc?.images ?? [] });
}

/** Apply an edit to the reference pictures (no re-render needed, but undoable). */
export function commitImages(images: RefImage[]) {
  const doc = currentDoc();
  if (!doc) return;
  // While a render is on its way, go through it so neither change overwrites the other.
  if (pending) return void commitDoc({ ...doc, images });
  const { history, setHistory } = useStore.getState();
  setHistory(pushHistory(history, { ...doc, images }));
}

/** An empty design on the fabric used last. */
function freshDoc(): Doc {
  const doc = newDoc();
  const fabric = loadPrefs().fabric;
  return fabric ? { ...doc, layout: { ...doc.layout, fabric } } : doc;
}

/** Start over with this document; it counts as saved (nothing to lose yet). */
async function replaceDoc(doc: Doc, path: string | null, fresh = true) {
  const ok = await showHistory({ past: [], present: doc, future: [] }, fresh);
  if (ok) {
    const s = useStore.getState();
    s.select(null);
    s.setTool("select");
    s.markSaved(path);
    s.setMeasure(null);
    s.selectNode(null);
    s.notify(null);
  }
  return ok;
}

/** If there are unsaved changes, ask. Returns false if the user cancels. */
export async function confirmDiscard(): Promise<boolean> {
  const s = useStore.getState();
  if (!s.history.present || !isDirty(s)) return true;
  const answer = await message("Save your changes first?", {
    title: "Unsaved changes",
    kind: "warning",
    buttons: { yes: "Save", no: "Don't save", cancel: "Cancel" },
  });
  if (answer === "Save" || answer === "Yes") return saveProject(false);
  return answer === "Don't save" || answer === "No";
}

export async function newProject() {
  if (!(await confirmDiscard())) return;
  await replaceDoc(freshDoc(), null);
  info("New design: draw with the tools on the left, or add a picture to trace (Ctrl+I).");
}

/** The sample designs that come with LUDD: opened as new, unsaved designs (saving asks for a name). */
export async function openSample() {
  if (!isTauri()) return info("The samples come with the installed app (the samples folder in the project).");
  if (!(await confirmDiscard())) return;
  const dir = await resolveResource("samples");
  const picked = await open({
    title: "Open a sample design",
    defaultPath: dir,
    multiple: false,
    directory: false,
    filters: [{ name: "Sample designs", extensions: [PROJECT_EXT, "pes", "jef"] }],
  });
  if (!picked) return;
  await openDesign(picked, true);
  // Don't save over the sample in the app's folder: Save will ask where.
  if (isProjectPath(picked)) useStore.setState({ projectPath: null });
}

export async function openDesign(path?: string, skipConfirm = false) {
  const { setLoading } = useStore.getState();
  try {
    if (!skipConfirm && !(await confirmDiscard())) return;
    if (!path) {
      const picked = await pickDesignFile("Open", true);
      if (!picked) return;
      path = picked;
    }
    setLoading(`Opening ${basename(path)}…`);
    if (isProjectPath(path)) await openProject(path);
    else await replaceDoc(newDoc(path), null);
  } catch (err) {
    fail(err);
  } finally {
    setLoading(null);
  }
}

async function openProject(path: string) {
  const p = await engine().call<{ layout: Layout; images: RefImage[]; machine?: string; hoop?: string; path: string }>(
    "project.open",
    { path },
    OPEN_TIMEOUT,
  );
  const s = useStore.getState();
  if (p.machine && s.machines.some((m) => m.id === p.machine)) {
    s.setMachine(p.machine);
    if (p.hoop) s.setHoop(p.hoop);
  }
  await replaceDoc({ layout: { ...p.layout, title: stem(path) }, images: p.images ?? [] }, p.path);
}

/** Save the project. Asks for a name the first time, or always with `as`. */
export async function saveProject(as: boolean): Promise<boolean> {
  const s = useStore.getState();
  const doc = s.history.present;
  if (!doc) return false;
  let path = s.projectPath;
  if (!path || as) {
    const firstFile = doc.layout.items.find((it): it is FileItem => !it.kind || it.kind === "file");
    const suggested = doc.layout.title || (firstFile ? stem(firstFile.path) : "My design");
    const picked = await save({
      title: "Save project",
      defaultPath: path ?? `${suggested}.${PROJECT_EXT}`,
      filters: [{ name: "LUDD project", extensions: [PROJECT_EXT] }],
    });
    if (!picked) return false;
    path = picked;
  }
  s.setLoading(`Saving ${basename(path)}…`);
  try {
    const project = {
      title: stem(path),
      layout: { ...doc.layout, title: stem(path) },
      images: doc.images,
      machine: s.machineId,
      hoop: selectHoop(s)?.id ?? null,
    };
    const r = await engine().call<{ path: string; images: number; designs: number }>(
      "project.save",
      { path, project_data: project },
      OPEN_TIMEOUT,
    );
    // What was saved is what was sent: an edit made while saving still counts as unsaved.
    useStore.setState({ projectPath: r.path, savedDoc: doc });
    if (!isDirty(useStore.getState())) void engine().call("project.discard_recovery").catch(() => {});
    const extra = r.images ? ` with ${r.images} picture${r.images > 1 ? "s" : ""} included` : "";
    info(`Saved ${basename(r.path)}${extra}`);
    return true;
  } catch (err) {
    fail(err);
    return false;
  } finally {
    s.setLoading(null);
  }
}

// ---------------------------------------------------------------- autosave and recovery

let autosaveTimer: ReturnType<typeof setTimeout> | undefined;
/** Work from a crashed session is waiting for Recover or Discard: never overwrite or delete it until then. */
let recoveryWaiting = false;
export const isRecoveryWaiting = () => recoveryWaiting;
const AUTOSAVE_DELAY_MS = 3000;

/** Keep a recovery copy a few seconds after each change (pictures and designs included). */
export function startAutosave() {
  return useStore.subscribe((s, prev) => {
    if (s.history === prev.history && s.savedDoc === prev.savedDoc) return;
    clearTimeout(autosaveTimer);
    if (!s.engine || !s.history.present || recoveryWaiting) return;
    if (!isDirty(s)) {
      void s.engine.call("project.discard_recovery").catch(() => {});
      return;
    }
    autosaveTimer = setTimeout(() => {
      const st = useStore.getState();
      const doc = st.history.present;
      if (!doc || !st.engine || !isDirty(st) || recoveryWaiting) return;
      const project = { title: doc.layout.title, layout: doc.layout, images: doc.images, machine: st.machineId, path: st.projectPath };
      st.engine.call("project.autosave", { project_data: project }).catch(() => {
        // Autosave is a safety net; a failure must never interrupt the user.
      });
    }, AUTOSAVE_DELAY_MS);
  });
}

// ---------------------------------------------------------------- fabric and quality checks

/** Choose what the design is stitched on. New designs start on the same fabric. */
export function setFabric(id: string) {
  const layout = currentLayout();
  if (!layout || layout.fabric === id) return;
  savePrefs({ fabric: id });
  void commit({ ...layout, fabric: id });
}

let checkTimer: ReturnType<typeof setTimeout> | undefined;
let checkSeq = 0;
const CHECK_DELAY_MS = 500;

/** Re-run the quality checks (and the density map, when shown) a moment after the design changes. */
export function startChecks() {
  return useStore.subscribe((s, prev) => {
    if (s.design === prev.design && s.showDensity === prev.showDensity && s.engine === prev.engine) return;
    clearTimeout(checkTimer);
    const seq = ++checkSeq;
    if (!s.design || !s.engine) {
      if (s.checks) s.setChecks(null);
      return;
    }
    checkTimer = setTimeout(async () => {
      const layout = currentLayout();
      const st = useStore.getState();
      if (!layout || !st.engine) return;
      try {
        const r = await st.engine.call<CheckResult>("layout.check", { layout, heatmap: st.showDensity }, OPEN_TIMEOUT);
        if (seq === checkSeq) useStore.getState().setChecks(r);
      } catch {
        // Checks are advice; a failure here never interrupts the user.
      }
    }, CHECK_DELAY_MS);
  });
}

/** Select the shape a check is about and centre the view on the spot. */
export function showCheck(check: { at?: [number, number]; item_id?: string }) {
  const s = useStore.getState();
  if (check.item_id && currentLayout()?.items.some((it) => it.id === check.item_id)) s.select(check.item_id);
  if (check.at) s.requestCenter(check.at);
}

export type RecoveryInfo = { saved_at: number; title: string; items: number; images: number; path: string | null };

export async function checkRecovery(): Promise<RecoveryInfo | null> {
  try {
    const r = await engine().call<RecoveryInfo | null>("project.recovery");
    recoveryWaiting = r !== null;
    return r;
  } catch {
    return null;
  }
}

export async function restoreRecovery() {
  try {
    const p = await engine().call<{ layout: Layout; images: RefImage[]; path: string | null }>("project.restore", {}, OPEN_TIMEOUT);
    recoveryWaiting = false;
    const doc = { layout: p.layout, images: p.images ?? [] };
    await showHistory({ past: [], present: doc, future: [] }, true);
    const s = useStore.getState();
    s.setTool("select");
    s.setMeasure(null);
    s.selectNode(null);
    // Restored work is unsaved until the user saves it.
    useStore.setState({ projectPath: p.path, savedDoc: null });
    s.select(null);
    info("Recovered your unsaved work. Save it to keep it.");
  } catch (err) {
    fail(err);
  }
}

export async function discardRecovery() {
  recoveryWaiting = false;
  await engine().call("project.discard_recovery").catch(() => {});
}

// ---------------------------------------------------------------- designs

/** Add another design to the current one (merge), and select it. */
export async function addDesign(path?: string) {
  const layout = currentLayout();
  if (!layout) return openDesign(path);
  try {
    if (!path) {
      const picked = await pickDesignFile("Add a design", false);
      if (!picked) return;
      path = picked;
    }
    const next = addItem(layout, path);
    if (await commit(next)) {
      useStore.getState().select(next.items[next.items.length - 1].id);
      useStore.getState().requestFit();
    }
  } catch (err) {
    fail(err);
  }
}

export function undoEdit() {
  useStore.getState().setPen(null);
  void showHistory(undo(latestHistory()));
}

export function redoEdit() {
  void showHistory(redo(latestHistory()));
}

/** The selected item, or the only one if there's just one (pictures aren't items). */
export function targetId(): string | null {
  const s = useStore.getState();
  const layout = s.history.present?.layout;
  if (!layout) return null;
  if (s.selectedId && layout.items.some((it) => it.id === s.selectedId)) return s.selectedId;
  return layout.items.length === 1 && !s.history.present?.images.some((im) => im.id === s.selectedId) ? layout.items[0].id : null;
}

function editTarget(fn: (l: Layout, id: string) => Layout) {
  const l = currentLayout();
  const id = targetId();
  if (l && id) void commit(fn(l, id));
}

/** Remove the selected design, drawn object or picture. */
export function removeSelected() {
  const s = useStore.getState();
  const doc = s.history.present;
  if (!doc || !s.selectedId) return;
  if (doc.images.some((im) => im.id === s.selectedId)) {
    commitImages(removeImage(doc.images, s.selectedId));
    s.select(null);
    return;
  }
  void commit(removeItem(doc.layout, s.selectedId));
  s.select(null);
}

function duplicateSelected() {
  const l = currentLayout();
  const id = targetId();
  if (!l || !id) return;
  const { layout, id: copy } = duplicateItem(l, id);
  void commit(layout).then((ok) => ok && useStore.getState().select(copy));
}

// ---------------------------------------------------------------- pictures

/** Read a picture's pixel size so it can be placed with the right proportions. */
function imageSize(dataUrl: string): Promise<{ w: number; h: number }> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.onerror = () => reject(new Error("That picture couldn't be read"));
    img.src = dataUrl;
  });
}

export async function addPicture(path?: string) {
  const s = useStore.getState();
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  try {
    if (!path) {
      const picked = await open({
        title: "Add a picture to trace",
        multiple: false,
        directory: false,
        filters: [{ name: "Pictures", extensions: both(IMAGE_EXTS) }],
      });
      if (!picked) return;
      path = picked;
    }
    const img = await engine().call<{ name: string; path: string; data_url: string }>("image.load", { path }, OPEN_TIMEOUT);
    const { w, h } = await imageSize(img.data_url);
    const hoop = selectHoop(useStore.getState());
    const fit = Math.min(PICTURE_START_MM, hoop?.width_mm ?? PICTURE_START_MM, hoop?.height_mm ?? PICTURE_START_MM);
    const width = w >= h ? fit : (fit * w) / h;
    const doc = currentDoc()!;
    const { images, id } = addImage(doc.images, {
      name: img.name,
      path: img.path,
      data_url: img.data_url,
      x: 0,
      y: 0,
      width_mm: width,
      height_mm: (width * h) / w,
      rotate: 0,
      opacity: 0.5,
      locked: false,
      visible: true,
    });
    commitImages(images);
    useStore.getState().select(id);
    useStore.getState().requestFit();
    info("Picture added. Move and size it, then lock it (🔒) so you can trace over it.");
  } catch (err) {
    fail(err);
  }
}

export function setPicture(id: string, patch: Partial<RefImage>) {
  const doc = currentDoc();
  if (doc) commitImages(updateImage(doc.images, id, patch));
}

// ---------------------------------------------------------------- drawing

export const DEFAULT_PARAMS = {
  run: { style: "single", stitch_mm: 2.5 },
  // Pull compensation and underlay are left automatic: the fabric and the shape's width choose them.
  satin: { spacing_mm: 0.4 },
  fill: { angle_deg: 45, spacing_mm: 0.4, stitch_mm: 3.5 },
  applique: { cover_width_mm: 3, tack: "zigzag" },
} as const;

/** Points each shape needs before it can be finished. */
export const MIN_POINTS: Record<ObjectKind, number> = { run: 2, satin: 4, fill: 3, applique: 3 };

export function penReady(): boolean {
  const pen = useStore.getState().pen;
  if (!pen) return false;
  if (pen.kind === "satin") return pen.a.length >= 2 && pen.a.length === pen.b.length;
  return pen.a.length >= MIN_POINTS[pen.kind];
}

/** Add a click to the shape being drawn. A satin's clicks alternate between its sides. */
/** Clicks closer than this to the last point are the same point. */
const SAME_POINT_MM = 0.3;

export function penAdd(node: PathNode) {
  const s = useStore.getState();
  const tool = s.tool;
  if (tool === "select" || tool === "text") return;
  const pen = s.pen ?? { kind: tool, a: [], b: [] };
  // A double-click (to finish) also clicks twice: don't add the same spot again, or onto the other satin side.
  const last = pen.kind === "satin" && pen.b.length === pen.a.length ? pen.b[pen.b.length - 1] : pen.a[pen.a.length - 1];
  if (last && Math.hypot(node[0] - last[0], node[1] - last[1]) < SAME_POINT_MM) return;
  if (pen.kind === "satin" && pen.a.length > pen.b.length) s.setPen({ ...pen, b: [...pen.b, node] });
  else s.setPen({ ...pen, a: [...pen.a, node] });
}

export function penUndoPoint() {
  const s = useStore.getState();
  const pen = s.pen;
  if (!pen) return;
  if (pen.kind === "satin" && pen.b.length === pen.a.length && pen.b.length) s.setPen({ ...pen, b: pen.b.slice(0, -1) });
  else if (pen.a.length > 1) s.setPen({ ...pen, a: pen.a.slice(0, -1) });
  else s.setPen(null);
}

export function penCancel() {
  cancelTraceQueue();
  useStore.getState().setPen(null);
}

/** Turn the pen's points into an object, add it to the layout and select it. */
export async function penFinish() {
  const s = useStore.getState();
  const pen = s.pen;
  if (!pen || !penReady()) {
    if (pen) info(pen.kind === "satin" ? "A satin needs at least two clicks on each side, alternating sides." : `Keep clicking: this shape needs at least ${MIN_POINTS[pen.kind]} points.`);
    return;
  }
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  const layout = currentLayout()!;
  const thread = s.drawThread;
  const obj =
    pen.kind === "run"
      ? { kind: "run" as const, geometry: { nodes: pen.a }, params: { ...DEFAULT_PARAMS.run }, thread }
      : pen.kind === "satin"
        ? { kind: "satin" as const, geometry: { rail_a: pen.a, rail_b: pen.b }, params: { ...DEFAULT_PARAMS.satin }, thread }
        : { kind: "fill" as const, geometry: { outline: pen.a }, params: { ...DEFAULT_PARAMS.fill }, thread };
  s.setPen(null);
  // Continuing an object replaces its points and keeps its thread and settings.
  if (pen.replaceId && layout.items.some((it) => it.id === pen.replaceId)) {
    const id = pen.replaceId;
    // Keep what the pen doesn't draw (a fill's holes, a closed line).
    const next = updateObject(layout, id, (o) => ({ ...o, geometry: { ...o.geometry, ...obj.geometry } }) as ObjectItem);
    if (await commit(next)) useStore.getState().select(id);
    return;
  }
  const { layout: next, id } = addObject(layout, obj as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
  if (await commit(next)) useStore.getState().select(id);
}

/** Pick the selected shape back up in the pen to add more points ("continue digitizing"). */
export function continueDrawing() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || !isObject(o)) return;
  const a = o.kind === "run" ? o.geometry.nodes : o.kind === "satin" ? o.geometry.rail_a : o.geometry.outline;
  const b = o.kind === "satin" ? o.geometry.rail_b : [];
  // An applique is drawn like a fill (a closed outline); it stays an applique.
  const kind = o.kind === "applique" ? "fill" : o.kind;
  s.setTool(kind);
  s.setPen({ kind, a: [...a], b: [...b], replaceId: o.id });
  s.setDrawThread(o.thread);
  info("Keep clicking to add points to this shape; Enter when done.");
}

/** Add a ready-made shape (as a fill) in the middle of the hoop, selected, ready to reshape. */
export async function addShape(shape: "rectangle" | "circle" | "star") {
  const s = useStore.getState();
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  const hoop = selectHoop(useStore.getState());
  const size = Math.min(60, (hoop?.width_mm ?? 100) * 0.6);
  const { layout: next, id } = addObject(currentLayout()!, {
    kind: "fill",
    geometry: { outline: shapeNodes(shape, 0, 0, size) },
    params: { ...DEFAULT_PARAMS.fill },
    thread: s.drawThread,
  } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
  if (await commit(next)) {
    useStore.getState().setTool("select");
    useStore.getState().select(id);
  }
}

// ---------------------------------------------------------------- lettering

export async function loadFonts(): Promise<FontInfo[]> {
  const s = useStore.getState();
  if (s.fonts) return s.fonts;
  const fonts = await engine().call<FontInfo[]>("fonts.list", {}, OPEN_TIMEOUT);
  useStore.getState().setFonts(fonts);
  return fonts;
}

/** The font for new text: the last one used, else a clear everyday font. */
async function defaultFont(): Promise<FontRef> {
  const remembered = loadPrefs().font;
  const fonts = await loadFonts();
  if (remembered && fonts.some((f) => f.path === remembered.path && f.index === remembered.index)) return remembered;
  const pick =
    fonts.find((f) => f.family === "Arial" && f.style === "Regular") ??
    fonts.find((f) => /^(Helvetica|Liberation Sans|DejaVu Sans|Segoe UI)$/.test(f.family) && f.style === "Regular") ??
    fonts.find((f) => f.kind === "outline");
  if (!pick) throw new Error("No fonts were found on this computer");
  return { path: pick.path, index: pick.index, family: pick.family, style: pick.style };
}

/** Add text (or a three-letter monogram) at a point, selected and ready to type over. */
export async function addText(x: number, y: number, monogram = false) {
  const s = useStore.getState();
  try {
    if (!s.history.present) await replaceDoc(freshDoc(), null);
    const font = await defaultFont();
    const item: TextItem = {
      id: newId(),
      kind: "text",
      text: monogram ? "ABC" : "Text",
      font,
      size_mm: monogram ? 25 : 15,
      spacing_mm: 0,
      style: "satin",
      shape: { type: "line" },
      monogram,
      thread: s.drawThread,
      transform: { ...IDENTITY, x: round2(x), y: round2(y) },
      threads: [],
      ops: [],
    };
    const layout = currentLayout()!;
    if (await commit({ ...layout, items: [...layout.items, item] })) {
      useStore.getState().setTool("select");
      useStore.getState().select(item.id);
      // Ask the panel to focus the text box so typing replaces the placeholder.
      window.dispatchEvent(new CustomEvent("ludd:edit-text", { detail: item.id }));
    }
  } catch (err) {
    fail(err);
  }
}

export function setText(id: string, patch: Partial<TextItem>) {
  const l = currentLayout();
  if (!l) return;
  if (patch.font) savePrefs({ font: patch.font });
  if (patch.thread) useStore.getState().setDrawThread(patch.thread);
  void commit({ ...l, items: l.items.map((it) => (it.id === id && it.kind === "text" ? { ...it, ...patch, ...(patch.thread ? { threads: [] } : {}) } : it)) });
}

/** Convert a font into an editable LUDD stitch font (.luddfont). */
export async function saveStitchFont(font: FontRef, style: "satin" | "fill") {
  const dest = await save({
    title: "Save as stitch font",
    defaultPath: `${font.family} ${style}.luddfont`,
    filters: [{ name: "LUDD stitch font", extensions: ["luddfont"] }],
  });
  if (!dest) return;
  try {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789&.,'!?-";
    const r = await engine().call<{ path: string; glyphs: number }>("fonts.export_stitch_font", { font, dest, chars, cap_height_mm: 12, style }, OPEN_TIMEOUT);
    useStore.setState({ fonts: null });
    info(`Saved ${basename(r.path)} with ${r.glyphs} letters. Put it in LUDD's fonts folder to use it.`);
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- object editing

export function editObject(id: string, fn: (o: ObjectItem) => ObjectItem) {
  const l = currentLayout();
  if (l) void commit(updateObject(l, id, fn));
}

export function setObjectParams(id: string, patch: Record<string, unknown>) {
  editObject(id, (o) => ({ ...o, params: { ...o.params, ...patch } }) as ObjectItem);
}

export function setObjectThread(id: string, thread: Thread) {
  useStore.getState().setDrawThread(thread);
  editObject(id, (o) => ({ ...o, thread, threads: [] }));
}

/** Which list of nodes in an object's geometry: a key, or a hole number for fills. */
export type NodeList = "nodes" | "rail_a" | "rail_b" | "outline" | number;

export function nodeLists(o: ObjectItem): { key: NodeList; nodes: PathNode[]; closed: boolean }[] {
  if (o.kind === "run") return [{ key: "nodes", nodes: o.geometry.nodes, closed: !!o.geometry.closed }];
  if (o.kind === "satin")
    return [
      { key: "rail_a", nodes: o.geometry.rail_a, closed: false },
      { key: "rail_b", nodes: o.geometry.rail_b, closed: false },
    ];
  return [
    { key: "outline", nodes: o.geometry.outline, closed: true },
    ...(o.geometry.holes ?? []).map((h, i) => ({ key: i as NodeList, nodes: h, closed: true })),
  ];
}

function withNodes(o: ObjectItem, key: NodeList, fn: (nodes: PathNode[]) => PathNode[]): ObjectItem {
  const g = o.geometry as unknown as Record<string, PathNode[] | PathNode[][]>;
  if (typeof key === "number") {
    const holes = [...((g.holes as PathNode[][]) ?? [])];
    holes[key] = fn(holes[key]);
    return { ...o, geometry: { ...o.geometry, holes } } as ObjectItem;
  }
  return { ...o, geometry: { ...o.geometry, [key]: fn(g[key] as PathNode[]) } } as ObjectItem;
}

export function moveNode(id: string, key: NodeList, index: number, x: number, y: number) {
  editObject(id, (o) => withNodes(o, key, (ns) => ns.map((n, i) => (i === index ? [round2(x), round2(y), n[2]] : n))));
}

export function toggleNodeKind(id: string, key: NodeList, index: number) {
  editObject(id, (o) => withNodes(o, key, (ns) => ns.map((n, i) => (i === index ? [n[0], n[1], n[2] === "c" ? "s" : "c"] : n))));
}

export function deleteNode(id: string, key: NodeList, index: number) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o) return;
  // Satin rails stay paired: removing a point removes its partner on the other side.
  if (o.kind === "satin") {
    if (o.geometry.rail_a.length <= 2) return info("A satin needs at least two points on each side.");
    editObject(id, (x) => ({
      ...x,
      geometry: {
        rail_a: (x as typeof o).geometry.rail_a.filter((_, i) => i !== index),
        rail_b: (x as typeof o).geometry.rail_b.filter((_, i) => i !== index),
      },
    }) as ObjectItem);
    return;
  }
  const list = nodeLists(o).find((l) => l.key === key);
  const min = o.kind === "run" ? 2 : 3;
  if (!list || list.nodes.length <= min) return info(`This shape needs at least ${min} points.`);
  editObject(id, (x) => withNodes(x, key, (ns) => ns.filter((_, i) => i !== index)));
}

/** Insert a corner point after `index` (between it and the next point). */
export function insertNode(id: string, key: NodeList, index: number, x: number, y: number) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o) return;
  if (o.kind === "satin") {
    // Add a matching rung: the new point on this side and the midpoint on the other.
    const other = key === "rail_a" ? o.geometry.rail_b : o.geometry.rail_a;
    const a = other[index];
    const b = other[Math.min(index + 1, other.length - 1)];
    const partner: PathNode = [round2((a[0] + b[0]) / 2), round2((a[1] + b[1]) / 2), "c"];
    const mine: PathNode = [round2(x), round2(y), "c"];
    const ins = (ns: PathNode[], n: PathNode) => [...ns.slice(0, index + 1), n, ...ns.slice(index + 1)];
    editObject(id, () => ({
      ...o,
      geometry: key === "rail_a" ? { rail_a: ins(o.geometry.rail_a, mine), rail_b: ins(o.geometry.rail_b, partner) } : { rail_a: ins(o.geometry.rail_a, partner), rail_b: ins(o.geometry.rail_b, mine) },
    }));
    return;
  }
  editObject(id, (x0) => withNodes(x0, key, (ns) => [...ns.slice(0, index + 1), [round2(x), round2(y), "c"], ...ns.slice(index + 1)]));
}

/** The same closed shape as a running stitch line, a fill or an applique. */
export function convertObject(id: string, to: ObjectKind) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o || o.kind === to || o.kind === "satin" || to === "satin") return;
  const outline = o.kind === "run" ? o.geometry.nodes : o.geometry.outline;
  const holes = o.kind === "fill" || o.kind === "applique" ? o.geometry.holes : undefined;
  editObject(id, () =>
    to === "run"
      ? ({ ...o, kind: "run", geometry: { nodes: outline, closed: true }, params: { ...DEFAULT_PARAMS.run } } as ObjectItem)
      : ({ ...o, kind: to, geometry: { outline, ...(holes ? { holes } : {}) }, params: { ...DEFAULT_PARAMS[to] } } as ObjectItem),
  );
}

const round2 = (v: number) => Math.round(v * 100) / 100;

// ---------------------------------------------------------------- colors and stitches

/** Recolor the displayed color block `block` (all of its sources). null puts the file's thread back. */
export function recolorBlock(block: number, thread: Thread | null) {
  const l = currentLayout();
  const sources = useStore.getState().design?.blocks[block]?.sources;
  if (l && sources?.length) void commit(recolor(l, sources, thread));
}

/** Recolor several blocks at once (one undo step). */
export function recolorBlocks(changes: { block: number; thread: Thread | null }[]) {
  let l = currentLayout();
  const blocks = useStore.getState().design?.blocks;
  if (!l || !blocks) return;
  for (const c of changes) {
    const sources = blocks[c.block]?.sources;
    if (sources?.length) l = recolor(l, sources, c.thread);
  }
  void commit(l);
}

export function resetColors() {
  const l = currentLayout();
  if (l) void commit(clearRecolors(l));
}

export function deleteColorBlock(block: number) {
  const l = currentLayout();
  const s = useStore.getState();
  const sources = s.design?.blocks[block]?.sources;
  if (!l || !sources?.length) return;
  if ((s.design?.blocks.length ?? 0) <= 1) {
    s.notify({ kind: "info", text: "A design needs at least one color." });
    return;
  }
  // A drawn object is one color: removing its color removes the object.
  const objects = sources.filter((src) => l.items[src.item] && l.items[src.item].kind !== "file" && l.items[src.item].kind);
  let next = deleteColor(l, sources.filter((src) => !objects.includes(src)));
  for (const src of objects) next = removeItem(next, l.items[src.item].id);
  void commit(next);
}

function toggleLayout(key: "merge_colors" | "color_sort") {
  const l = currentLayout();
  if (l) void commit({ ...l, [key]: !l[key] });
}

function toggleKnockdown() {
  const l = currentLayout();
  if (l) void commit({ ...l, knockdown: { margin_mm: 2, ...l.knockdown, enabled: !l.knockdown?.enabled } });
}

/** Copies of the selected design in a row, round a circle or mirrored four ways. */
export function repeatSelected(spec: RepeatSpec) {
  const s = useStore.getState();
  const l = currentLayout();
  const id = targetId();
  const index = l?.items.findIndex((it) => it.id === id) ?? -1;
  const info = index >= 0 ? s.design?.items?.[index] : undefined;
  if (!l || !id || !info?.bounds_mm) return;
  const [x0, y0, x1, y1] = info.bounds_mm;
  const { layout } = repeatItem(l, id, [(x0 + x1) / 2, (y0 + y1) / 2], [x1 - x0, y1 - y0], spec);
  void commit(layout).then((ok) => ok && useStore.getState().requestFit());
}

/** Save the applique pieces' cutting lines as an SVG for a cutting machine (or to print). */
export async function saveAppliqueSvg() {
  const layout = currentLayout();
  if (!layout) return;
  const dest = await save({
    title: "Save applique cut file",
    defaultPath: `${layout.title || "applique"} cut.svg`,
    filters: [{ name: "Cut file (SVG)", extensions: ["svg"] }],
  });
  if (!dest) return;
  try {
    const r = await engine().call<{ path: string; pieces: number }>("applique.export_svg", { layout, dest }, OPEN_TIMEOUT);
    info(`Saved ${basename(r.path)}: ${r.pieces} piece${r.pieces === 1 ? "" : "s"} at real size. Cut on the lines.`);
  } catch (err) {
    fail(err);
  }
}

function toggleBasting() {
  const l = currentLayout();
  if (l) void commit({ ...l, basting: { ...l.basting, enabled: !l.basting.enabled } });
}

function toggleJumpsToTrims() {
  const l = currentLayout();
  if (l) void commit(jumpsToTrims(l, jumpsToTrimsSetting(l) === null ? JUMP_TRIM_MM : null));
}

function insertAtNeedle(cmd: "stop" | "trim") {
  const s = useStore.getState();
  const l = currentLayout();
  if (!l || !s.design) return;
  const r = visibleRecords(s.stitchIdx, s.playhead, s.design.records.kind.length) - 1;
  const next = insertAt(l, s.design, r, cmd);
  if (!next) {
    s.notify({ kind: "info", text: "Play or scrub to a stitch first, then insert there." });
    return;
  }
  void commit(next).then((ok) => ok && info(`Added a ${cmd} at stitch ${s.playhead.toLocaleString()}`));
}

// ---------------------------------------------------------------- export

/** Options for saving the layout for the current machine and hoop. Recolors live in the layout. */
export function exportOptions(cutStops: CutStops): ExportOptions {
  const s = useStore.getState();
  return { machine: s.machineId, hoop: selectHoop(s)?.id ?? null, threads: [], cut_stops: cutStops };
}

export async function previewExport(options: ExportOptions, ext: string) {
  const layout = currentLayout();
  if (!layout) throw new Error("No design open");
  return engine().call<ExportReport & Pick<Design, "info">>("layout.preview_export", { layout, options, ext }, OPEN_TIMEOUT);
}

export type SplitPlan = {
  cols: number;
  rows: number;
  sections: { index: number; window_mm: number[]; stitches: number; colors: number; marks: number[][] }[];
};

/** How the open design would be split across hoopings of the current hoop. */
export async function splitPlan(overlap_mm: number): Promise<SplitPlan> {
  const layout = currentLayout();
  const hoop = selectHoop(useStore.getState());
  if (!layout || !hoop) throw new Error("No design open");
  return engine().call<SplitPlan>("layout.split_plan", { layout, hoop, overlap_mm }, OPEN_TIMEOUT);
}

/** Ask where to save, then export. With `split`, one file per hooping. Returns the report, or null if cancelled. */
export async function saveExport(
  options: ExportOptions,
  ext: string,
  split?: { overlap_mm: number },
): Promise<(ExportReport & { path: string; paths?: string[] }) | null> {
  const { formats, setLoading, projectPath } = useStore.getState();
  const layout = currentLayout();
  if (!layout) return null;
  const firstFile = layout.items.find((it): it is FileItem => !it.kind || it.kind === "file");
  const base = projectPath ?? firstFile?.path ?? "";
  const dir = base ? base.slice(0, base.length - basename(base).length) : "";
  const name = layout.title || (firstFile ? (layout.items.length > 1 || hasEdits(layout) ? `${stem(firstFile.path)} edited` : stem(firstFile.path)) : "My design");
  const known = formats?.write.find((f) => f.ext === ext);
  const dest = await save({
    title: "Save for machine",
    defaultPath: `${dir}${name}.${ext}`,
    filters: [{ name: `${ext.toUpperCase()}${known?.description ? ` – ${known.description}` : ""}`, extensions: [ext] }],
  });
  if (!dest) return null;
  setLoading(`Saving ${basename(dest)}…`);
  try {
    if (split) {
      const hoop = selectHoop(useStore.getState());
      const r = await engine().call<ExportReport & { paths: string[] }>(
        "layout.export_split",
        { layout, dest, hoop, overlap_mm: split.overlap_mm, options },
        OPEN_TIMEOUT,
      );
      return { ...r, path: r.paths[0], warnings: r.warnings ?? [] };
    }
    return await engine().call<ExportReport & { path: string }>("layout.export", { layout, dest, options }, OPEN_TIMEOUT);
  } finally {
    setLoading(null);
  }
}

function hasEdits(l: Layout) {
  return (
    l.merge_colors ||
    l.color_sort ||
    l.basting.enabled ||
    l.items.some((it) => it.ops.length || it.threads.some(Boolean) || JSON.stringify(it.transform) !== JSON.stringify(IDENTITY))
  );
}

// ---------------------------------------------------------------- threads and machines

export async function loadMachinesAndCharts() {
  const { setMachines, setCharts } = useStore.getState();
  try {
    setMachines(await engine().call<Machine[]>("machines.list"));
    useStore.getState().setFabrics(await engine().call<Fabric[]>("fabrics.list"));
    await loadAISettings();
    setCharts(await engine().call<ChartSummary[]>("threads.charts"));
  } catch (err) {
    fail(err);
  }
}

export async function getChart(id: string) {
  return engine().call<Chart>("threads.chart", { id });
}

export async function matchThreads(colors: string[], chart: string, count = 3) {
  return engine().call<ThreadMatch[][]>("threads.match", { colors, chart, count });
}

export async function importChart(name: string, brand: string): Promise<ChartSummary | null> {
  const path = await open({
    title: "Import thread chart (CSV)",
    multiple: false,
    directory: false,
    filters: [{ name: "CSV", extensions: ["csv", "CSV", "txt"] }],
  });
  if (!path) return null;
  const chart = await engine().call<ChartSummary>("threads.import_csv", { path, name, brand });
  useStore.getState().setCharts(await engine().call<ChartSummary[]>("threads.charts"));
  return chart;
}

/** Add spools to My threads. */
export async function addMyThreads(spools: { code?: string; name?: string; color: string; brand?: string }[]) {
  await engine().call("threads.my_add", { spools });
  useStore.getState().setCharts(await engine().call<ChartSummary[]>("threads.charts"));
}

export async function removeMyThreads(spools: { code: string; brand: string; color: string }[]) {
  await engine().call("threads.my_remove", { spools });
  useStore.getState().setCharts(await engine().call<ChartSummary[]>("threads.charts"));
}

export async function deleteChart(id: string) {
  await engine().call("threads.delete_chart", { id });
  useStore.getState().setCharts(await engine().call<ChartSummary[]>("threads.charts"));
}

export function currentMachine(): Machine | null {
  return selectMachine(useStore.getState());
}

export async function pickFolder(title: string): Promise<string | null> {
  const picked = await open({ title, directory: true, multiple: false });
  return picked ?? null;
}

export async function convertFolder(
  srcDir: string,
  destDir: string,
  ext: string,
  recursive: boolean,
  options: Pick<ExportOptions, "machine" | "cut_stops"> | null,
) {
  return engine().call<ConvertResult>("design.convert_folder", { src_dir: srcDir, dest_dir: destDir, ext, recursive, options }, CONVERT_TIMEOUT);
}

// ---------------------------------------------------------------- player

/** Step the player to the start of the previous/next color block. */
function jumpColor(dir: 1 | -1) {
  const { playhead, blockStarts, stitchIdx, setPlayhead, setPlaying } = useStore.getState();
  setPlaying(false);
  const ends = [...blockStarts.slice(1), stitchIdx.length];
  if (dir > 0) setPlayhead(ends.find((e) => e > playhead) ?? stitchIdx.length);
  else setPlayhead([...blockStarts].reverse().find((s) => s < playhead) ?? 0);
}

function step(n: number) {
  const { playhead, setPlayhead, setPlaying } = useStore.getState();
  setPlaying(false);
  setPlayhead(playhead + n);
}

// ---------------------------------------------------------------- commands

const hasDoc = () => useStore.getState().history.present !== null;
const hasDesign = () => useStore.getState().design !== null;
const hasApplique = () => engineReady() && !!currentLayout()?.items.some((it) => it.kind === "applique");
const engineReady = () => useStore.getState().engine !== null;
const canEdit = () => hasDesign() && engineReady();
const hasTarget = () => canEdit() && !drawing() && targetId() !== null;
const hasSelection = () => engineReady() && useStore.getState().selectedId !== null;
const noSelection = () => hasDesign() && useStore.getState().selectedId === null;
const canUndo = () => engineReady() && latestHistory().past.length > 0;
const canRedo = () => engineReady() && latestHistory().future.length > 0;
const drawing = () => useStore.getState().pen !== null;
// Letter keys don't switch tools mid-shape (A sits by Tab and Shift); the tool buttons still do.
const notDrawing = () => engineReady() && !drawing();
const nudge = (dx: number, dy: number) => () => {
  const s = useStore.getState();
  const img = s.history.present?.images.find((im) => im.id === s.selectedId);
  if (img) {
    if (!img.locked) setPicture(img.id, { x: img.x + dx, y: img.y + dy });
    return;
  }
  editTarget((l, id) => moveBy(l, id, dx, dy));
};
const tool = (t: Tool) => async () => {
  // Switching tools mid-shape keeps the shape if it's complete enough, rather than losing it.
  if (useStore.getState().pen) {
    if (penReady()) await penFinish();
    else penCancel();
  }
  useStore.getState().setTool(t);
  if (!hasDoc()) void replaceDoc(freshDoc(), null);
};

const hasJunction = () => (useStore.getState().ghost?.alternatives.length ?? 0) > 0;

// Order matters: the first enabled command for a key wins (drawing keys first, then a selection
// is nudged by the arrows, otherwise they step the player).
export const COMMANDS: Command[] = [
  // While drawing, Tab always belongs to Trace Assist (never moves keyboard focus).
  { id: "trace.accept", title: "Accept the suggested point", shortcut: "Tab", run: () => queueAccept(), enabled: drawing },
  { id: "trace.acceptMany", title: "Keep accepting points", shortcut: "Shift+Tab", run: queueAcceptMany, enabled: drawing },
  { id: "trace.pick1", title: "Take branch 1", shortcut: "1", run: () => queueAccept(1), enabled: hasJunction },
  { id: "trace.pick2", title: "Take branch 2", shortcut: "2", run: () => queueAccept(2), enabled: hasJunction },
  { id: "trace.shorter", title: "Shorter steps", shortcut: "[", run: () => setStep(useStore.getState().traceStep - 0.5), enabled: drawing },
  { id: "trace.longer", title: "Longer steps", shortcut: "]", run: () => setStep(useStore.getState().traceStep + 0.5), enabled: drawing },
  { id: "pen.toggleKind", title: "Make the last point a corner / curve", shortcut: "C", run: toggleLastPoint, enabled: drawing },
  {
    id: "trace.toggle",
    title: "Trace Assist (suggest the next point)",
    shortcut: "Mod+Shift+A",
    run: () => useStore.getState().toggleTraceAssist(),
  },
  { id: "pen.finish", title: "Finish the shape", shortcut: "Enter", run: () => void penFinish(), enabled: drawing },
  { id: "pen.undoPoint", title: "Remove the last point", shortcut: "Backspace", run: penUndoPoint, enabled: drawing },
  { id: "pen.cancel", title: "Cancel the shape", shortcut: "Escape", run: penCancel, enabled: drawing },
  // Esc lets go of one thing per press (see escape.ts): these follow drawing, in this order.
  {
    id: "measure.cancel",
    title: "Stop measuring",
    shortcut: "Escape",
    run: () => useStore.getState().setMeasure(null),
    enabled: () => useStore.getState().measure !== null,
  },

  { id: "app.settings", title: "Settings…", shortcut: "Mod+,", run: () => useStore.getState().setSettingsOpen(true) },
  { id: "app.help", title: "Help", shortcut: "F1", run: () => useStore.getState().setHelpOpen(true) },
  { id: "ai.advisor", title: "Stitch Advisor (AI)…", shortcut: "Mod+Shift+I", run: () => void runAdvisor(), enabled: canAdvise },
  { id: "file.new", title: "New design", shortcut: "Mod+N", run: () => void newProject(), enabled: engineReady },
  { id: "file.open", title: "Open…", shortcut: "Mod+O", run: () => void openDesign(), enabled: engineReady },
  { id: "file.save", title: "Save project", shortcut: "Mod+S", run: () => void saveProject(false), enabled: () => engineReady() && hasDoc() },
  { id: "file.saveAs", title: "Save project as…", shortcut: "Mod+Shift+S", run: () => void saveProject(true), enabled: () => engineReady() && hasDoc() },
  { id: "file.add", title: "Add another design…", shortcut: "Mod+Shift+O", run: () => void addDesign(), enabled: () => engineReady() && hasDoc() },
  { id: "file.picture", title: "Add a picture to trace…", shortcut: "Mod+I", run: () => void addPicture(), enabled: engineReady },
  { id: "file.samples", title: "Open a sample design…", shortcut: "Mod+Shift+E", run: () => void openSample(), enabled: engineReady },
  { id: "app.updates", title: "Check for updates", shortcut: "Mod+Shift+F1", run: () => void checkForUpdates(true) },
  {
    id: "file.export",
    title: "Save for machine…",
    shortcut: "Mod+E",
    run: () => useStore.getState().setExportOpen(true),
    enabled: canEdit,
  },
  { id: "file.print", title: "Print template & thread list…", shortcut: "Mod+P", run: () => printDesign(), enabled: hasDesign },
  {
    id: "file.batch",
    title: "Batch convert folder…",
    shortcut: "Mod+B",
    run: () => useStore.getState().setBatchOpen(true),
    enabled: engineReady,
  },

  { id: "edit.undo", title: "Undo", shortcut: "Mod+Z", run: undoEdit, enabled: canUndo },
  { id: "edit.redo", title: "Redo", shortcut: "Mod+Y", run: redoEdit, enabled: canRedo },
  { id: "edit.redoAlt", title: "Redo", shortcut: "Mod+Shift+Z", run: redoEdit, enabled: canRedo },

  { id: "tool.select", title: "Select and move", shortcut: "V", run: tool("select"), enabled: notDrawing },
  { id: "tool.run", title: "Draw a running stitch line", shortcut: "L", run: tool("run"), enabled: notDrawing },
  { id: "tool.satin", title: "Draw a satin column", shortcut: "C", run: tool("satin"), enabled: notDrawing },
  { id: "tool.fill", title: "Draw a fill shape", shortcut: "A", run: tool("fill"), enabled: notDrawing },
  { id: "tool.text", title: "Add text (click where it goes)", shortcut: "T", run: tool("text"), enabled: notDrawing },
  { id: "text.monogram", title: "Add a monogram", shortcut: "Mod+Alt+M", run: () => void addText(0, 0, true), enabled: engineReady },
  { id: "shape.rectangle", title: "Add a rectangle", shortcut: "Mod+Alt+1", run: () => void addShape("rectangle"), enabled: engineReady },
  { id: "shape.circle", title: "Add a circle", shortcut: "Mod+Alt+2", run: () => void addShape("circle"), enabled: engineReady },
  { id: "shape.star", title: "Add a star", shortcut: "Mod+Alt+3", run: () => void addShape("star"), enabled: engineReady },
  {
    id: "draw.continue",
    title: "Continue drawing this shape",
    shortcut: "K",
    run: continueDrawing,
    enabled: () => {
      const s = useStore.getState();
      const it = s.history.present?.layout.items.find((x) => x.id === s.selectedId);
      return !!it && isObject(it) && s.tool === "select";
    },
  },
  {
    id: "tool.escape",
    title: "Back to Select",
    shortcut: "Escape",
    run: () => useStore.getState().setTool("select"),
    enabled: () => useStore.getState().tool !== "select",
  },

  { id: "arrange.rotateCw", title: "Rotate 90° right", shortcut: "R", run: () => editTarget((l, id) => rotateBy(l, id, 90)), enabled: hasTarget },
  { id: "arrange.rotateCcw", title: "Rotate 90° left", shortcut: "Shift+R", run: () => editTarget((l, id) => rotateBy(l, id, -90)), enabled: hasTarget },
  { id: "arrange.mirrorX", title: "Mirror left–right", shortcut: "M", run: () => editTarget((l, id) => mirror(l, id, "x")), enabled: hasTarget },
  { id: "arrange.mirrorY", title: "Mirror top–bottom", shortcut: "Shift+M", run: () => editTarget((l, id) => mirror(l, id, "y")), enabled: hasTarget },
  { id: "arrange.duplicate", title: "Duplicate", shortcut: "Mod+D", run: duplicateSelected, enabled: hasTarget },
  {
    id: "node.delete",
    title: "Remove the selected point",
    shortcut: "Delete",
    run: () => {
      const n = useStore.getState().selectedNode;
      if (n) {
        deleteNode(n.id, n.list as NodeList, n.index);
        useStore.getState().selectNode(null);
      }
    },
    enabled: () => useStore.getState().selectedNode !== null,
  },
  { id: "arrange.delete", title: "Remove", shortcut: "Delete", run: removeSelected, enabled: hasSelection },
  { id: "arrange.deleteAlt", title: "Remove", shortcut: "Backspace", run: removeSelected, enabled: hasSelection },
  {
    id: "node.deselect",
    title: "Let go of the point",
    shortcut: "Escape",
    run: () => useStore.getState().selectNode(null),
    enabled: () => useStore.getState().selectedNode !== null,
  },
  { id: "arrange.deselect", title: "Deselect", shortcut: "Escape", run: () => useStore.getState().select(null), enabled: () => useStore.getState().selectedId !== null },
  {
    id: "player.stop",
    title: "Stop playing",
    shortcut: "Escape",
    run: () => useStore.getState().setPlaying(false),
    enabled: () => useStore.getState().playing,
  },
  { id: "arrange.left", title: "Nudge left", shortcut: "ArrowLeft", run: nudge(-NUDGE_MM, 0), enabled: hasSelection },
  { id: "arrange.right", title: "Nudge right", shortcut: "ArrowRight", run: nudge(NUDGE_MM, 0), enabled: hasSelection },
  { id: "arrange.up", title: "Nudge up", shortcut: "ArrowUp", run: nudge(0, -NUDGE_MM), enabled: hasSelection },
  { id: "arrange.down", title: "Nudge down", shortcut: "ArrowDown", run: nudge(0, NUDGE_MM), enabled: hasSelection },
  { id: "arrange.leftBig", title: "Nudge left 1 cm", shortcut: "Shift+ArrowLeft", run: nudge(-NUDGE_BIG_MM, 0), enabled: hasSelection },
  { id: "arrange.rightBig", title: "Nudge right 1 cm", shortcut: "Shift+ArrowRight", run: nudge(NUDGE_BIG_MM, 0), enabled: hasSelection },
  { id: "arrange.upBig", title: "Nudge up 1 cm", shortcut: "Shift+ArrowUp", run: nudge(0, -NUDGE_BIG_MM), enabled: hasSelection },
  { id: "arrange.downBig", title: "Nudge down 1 cm", shortcut: "Shift+ArrowDown", run: nudge(0, NUDGE_BIG_MM), enabled: hasSelection },

  { id: "colors.merge", title: "Combine same colors next to each other", shortcut: "Mod+Shift+C", run: () => toggleLayout("merge_colors"), enabled: canEdit },
  { id: "colors.sort", title: "Sort colors (fewest thread changes)", shortcut: "Mod+Shift+L", run: () => toggleLayout("color_sort"), enabled: canEdit },
  { id: "colors.reset", title: "Put back the original colors", shortcut: "Mod+Shift+R", run: resetColors, enabled: canEdit },

  { id: "stitch.stop", title: "Insert a stop at the needle", shortcut: "Mod+Shift+P", run: () => insertAtNeedle("stop"), enabled: canEdit },
  { id: "stitch.trim", title: "Insert a trim at the needle", shortcut: "Mod+Shift+T", run: () => insertAtNeedle("trim"), enabled: canEdit },
  { id: "stitch.jumpsToTrims", title: `Trim jumps longer than ${JUMP_TRIM_MM} mm`, shortcut: "Mod+Shift+J", run: toggleJumpsToTrims, enabled: canEdit },
  { id: "stitch.basting", title: "Add a basting box", shortcut: "Mod+Shift+B", run: toggleBasting, enabled: canEdit },
  { id: "stitch.knockdown", title: "Knockdown stitches (towels, fleece)", shortcut: "Mod+Shift+N", run: toggleKnockdown, enabled: canEdit },
  { id: "arrange.repeat", title: "Repeat, carousel or mirror…", shortcut: "Mod+Shift+D", run: () => useStore.getState().setRepeatOpen(true), enabled: hasTarget },
  { id: "applique.svg", title: "Save applique cut file (SVG)…", shortcut: "Mod+Shift+U", run: () => void saveAppliqueSvg(), enabled: hasApplique },

  { id: "view.density", title: "Density map", shortcut: "Shift+D", run: () => useStore.getState().toggleDensity(), enabled: hasDesign },
  { id: "view.fit", title: "Fit design to window", shortcut: "F", run: () => useStore.getState().requestFit(), enabled: hasDoc },
  { id: "view.jumps", title: "Show trims, jumps and stops", shortcut: "J", run: () => useStore.getState().toggleJumps() },
  { id: "view.realistic", title: "Realistic thread", shortcut: "Shift+T", run: () => useStore.getState().toggleRealistic() },
  { id: "view.hoop", title: "Show hoop", shortcut: "H", run: () => useStore.getState().toggleHoop() },
  { id: "view.grid", title: "Show grid", shortcut: "G", run: () => useStore.getState().toggleGrid() },
  { id: "view.units", title: "Measure in millimetres", shortcut: "U", run: () => useStore.getState().toggleUnits() },
  { id: "view.zoomIn", title: "Zoom in", shortcut: "=", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomInPlus", title: "Zoom in", shortcut: "Shift++", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomInPad", title: "Zoom in", shortcut: "+", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomOut", title: "Zoom out", shortcut: "-", run: () => useStore.getState().requestZoom("out"), enabled: hasDoc },
  { id: "view.zoomActual", title: "Zoom to real size (100%)", shortcut: "1", run: () => useStore.getState().requestZoom("actual"), enabled: hasDoc },
  {
    id: "threads.charts",
    title: "My threads & charts…",
    shortcut: "Mod+T",
    run: () => useStore.getState().setChartsOpen(true),
    enabled: engineReady,
  },

  {
    id: "player.toggle",
    title: "Play / pause",
    shortcut: "Space",
    run: () => {
      const s = useStore.getState();
      s.setPlaying(!s.playing);
    },
    enabled: hasDesign,
  },
  { id: "player.back", title: "Back one stitch", shortcut: "ArrowLeft", run: () => step(-1), enabled: noSelection },
  { id: "player.forward", title: "Forward one stitch", shortcut: "ArrowRight", run: () => step(1), enabled: noSelection },
  { id: "player.back100", title: "Back 100 stitches", shortcut: "Shift+ArrowLeft", run: () => step(-100), enabled: noSelection },
  { id: "player.forward100", title: "Forward 100 stitches", shortcut: "Shift+ArrowRight", run: () => step(100), enabled: noSelection },
  { id: "player.prevColor", title: "Previous color", shortcut: "PageUp", run: () => jumpColor(-1), enabled: hasDesign },
  { id: "player.nextColor", title: "Next color", shortcut: "PageDown", run: () => jumpColor(1), enabled: hasDesign },
  { id: "player.start", title: "Go to start", shortcut: "Home", run: () => step(-Infinity), enabled: hasDesign },
  { id: "player.end", title: "Show whole design", shortcut: "End", run: () => step(Infinity), enabled: hasDesign },
  {
    id: "player.faster",
    title: "Faster playback",
    shortcut: "]",
    run: () => {
      const s = useStore.getState();
      s.setSpeed(PLAYER_SPEEDS.find((v) => v > s.speed) ?? s.speed);
    },
  },
  {
    id: "player.slower",
    title: "Slower playback",
    shortcut: "[",
    run: () => {
      const s = useStore.getState();
      s.setSpeed([...PLAYER_SPEEDS].reverse().find((v) => v < s.speed) ?? s.speed);
    },
  },
];

export const command = (id: string) => COMMANDS.find((c) => c.id === id)!;

export { isTauri, itemLabel };
