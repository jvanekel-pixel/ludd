import { message, open, save } from "@tauri-apps/plugin-dialog";
import { COMMANDS, registerCommands, type Command } from "./commands";
import {
  ADD_OFFSET_MM,
  IDENTITY,
  addImage,
  addItem,
  centreItem,
  moveItem,
  addObject,
  clearRecolors,
  deleteColor,
  duplicateItem,
  repeatItem,
  setGroup,
  transformTogether,
  type RepeatSpec,
  type TogetherOp,
  insertAt,
  itemLabel,
  jumpsToTrims,
  jumpsToTrimsSetting,
  mirror,
  moveBy,
  newDoc,
  newId,
  objectCenter,
  reorder,
  pushHistory,
  shapeNodes,
  recolor,
  redo,
  removeImage,
  removeItem,
  renameItem,
  rotateBy,
  scaleBy,
  shapeNodeLists,
  undo,
  updateImage,
  updateObject,
  type History,
} from "./design/layout";
import type { ShapeId } from "./design/shapes";
import { penPoints, reversePath } from "./design/simplify";
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
  FillGeometry,
  FontInfo,
  FontRef,
  Layout,
  LayoutItem,
  Machine,
  ObjectItem,
  ObjectKind,
  PathNode,
  RefImage,
  SatinColumn,
  Thread,
  ThreadMatch,
  TextItem,
} from "./design/types";
import { isObject, isRibbon, isText } from "./design/types";
import { useContextMenu } from "./contextMenu";
import { angleOf } from "./design/direction";
import { withoutDeadCrossHatch } from "./design/fillPatterns";
import { RpcError } from "./engine/rpc";
import { isTauri } from "./engine/sidecar";
import { canAdvise, loadAISettings, runAdvisor } from "./ai";
import { checkForUpdates } from "./updates";
import { resolveResource } from "@tauri-apps/api/path";
import { printDesign } from "./print";
import { cancelTraceQueue, queueAccept, queueAcceptMany, setStep, toggleLastPoint } from "./traceAssist";
import { canFit, nextFit } from "./satinFit";
import { acceptGuess, loadTraceModel, nextGuess, setSpacing, setSpread } from "./autoTrace";
import * as feat from "./features";
import { finishAngleLine } from "./feat/angleLines";
import { cancelCarve, finishCarve } from "./feat/carve";
import { nudgeLetter, pruneLetterEdits, recolorRuns } from "./feat/letters";
import { loadPrefs, savePrefs } from "./prefs";
import { isDirty, MACHINE_SPEED, PLAYER_SPEEDS, selectHoop, selectImages, selectLayout, selectMachine, useStore, type Tool } from "./store";

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

export function engine() {
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

/** A document being opened (or started): its file and the version that counts as saved. Applied
 *  with whichever render lands first, even an edit made while it was still opening, so the window,
 *  the project path and "unsaved changes" always describe what's on screen. */
let pendingOpen: { path: string | null; doc: Doc } | null = null;

function applyOpen() {
  const open = pendingOpen;
  if (!open) return;
  pendingOpen = null;
  const s = useStore.getState();
  s.select(null);
  s.setTool("select");
  useStore.setState({ projectPath: open.path, savedDoc: open.doc });
  s.setMeasure(null);
  s.selectNode(null);
  // Per-document modes and proposals end with their document (their Esc bookings go too).
  s.setStitchEdit(null);
  s.setAdvice(null);
  s.notify(null);
}

/** Lettering just placed, whose text box should be focused as soon as its panel appears. */
let textToEdit: string | null = null;

/** True (once) if the text box for `id` should take the focus: the lettering was just placed. */
export function takeTextToEdit(id: string): boolean {
  if (textToEdit !== id) return false;
  textToEdit = null;
  return true;
}

/** One render at a time: edits made while one is on its way wait, and only the newest of them is
 *  rendered next (holding an arrow key sends a few renders, not one per key repeat). */
let rendering = false;
let queued: { history: History; fresh: boolean; seq: number; done: ((ok: boolean) => void)[] } | null = null;

/** Show `history.present`. Only the newest of overlapping edits is rendered and applied. */
async function showHistory(history: History, fresh = false): Promise<boolean> {
  const seq = ++renderSeq;
  const { setHistory, setDesign } = useStore.getState();
  const doc = history.present;
  if (!doc || doc.layout.items.length === 0) {
    // Nothing to stitch yet (a new project, or only pictures): the canvas still shows.
    pending = null;
    if (queued) {
      queued.done.forEach((d) => d(false));
      queued = null;
    }
    setHistory(history);
    setDesign(null, fresh || !!pendingOpen);
    applyOpen();
    return true;
  }
  pending = history;
  if (rendering) {
    // Wait for the render on its way; a newer edit replaces this one before it's sent.
    // (An edit it replaces is part of it, so that edit's follow-up waits for its result.)
    return new Promise<boolean>((resolve) => {
      queued = { history, fresh: fresh || !!queued?.fresh, seq, done: [...(queued?.done ?? []), resolve] };
    });
  }
  return runRender(history, fresh, seq);
}

async function runRender(history: History, fresh: boolean, seq: number): Promise<boolean> {
  const { setHistory, setDesign } = useStore.getState();
  rendering = true;
  try {
    const design = await engine().call<Design>("layout.render", { layout: history.present!.layout }, OPEN_TIMEOUT);
    if (seq !== renderSeq) {
      // A newer edit is waiting and is rendered next. Show this one meanwhile, so an edit that
      // worked is kept even if the newer one fails (not while a design is opening: the screen,
      // the file and "unsaved" must all switch together).
      if (!pending || pendingOpen) return false;
      setHistory(history);
      setDesign(design, fresh);
      return true;
    }
    pending = null;
    setHistory(history);
    setDesign(design, fresh || !!pendingOpen);
    applyOpen();
    return true;
  } catch (err) {
    // The edit didn't happen: later edits build on what's on screen.
    if (seq === renderSeq) {
      pending = null;
      pendingOpen = null;
      fail(err);
    }
    return false;
  } finally {
    rendering = false;
    const next = queued;
    queued = null;
    if (next) void runRender(next.history, next.fresh, next.seq).then((ok) => next.done.forEach((d) => d(ok)));
    else whenIdleWaiters.splice(0).forEach((w) => w());
  }
}

const whenIdleWaiters: (() => void)[] = [];

/** Resolves once no edit is rendering or waiting to (at once if none is). */
export function whenIdle(): Promise<void> {
  if (!rendering && !queued) return Promise.resolve();
  return new Promise((resolve) => whenIdleWaiters.push(resolve));
}

/** Two documents with the same content: an "edit" from one to the other changes nothing. */
function sameDoc(a: Doc, b: Doc): boolean {
  if (a === b) return true;
  const sameImages = a.images === b.images || (a.images.length === b.images.length && a.images.every((im, i) => im === b.images[i] || JSON.stringify(im) === JSON.stringify(b.images[i])));
  return sameImages && (a.layout === b.layout || JSON.stringify(a.layout) === JSON.stringify(b.layout));
}

/** Repeated small moves (an arrow key held or tapped quickly) are one undo step. */
let gesture: { key: string; until: number } | null = null;
const GESTURE_MS = 800;

/** The next edit continues the same gesture as the last one with this key (merged undo step). */
function continueGesture(key: string): Merge {
  const now = Date.now();
  const same = !!gesture && gesture.key === key && now < gesture.until;
  gesture = { key, until: now + GESTURE_MS };
  return same ? true : "start";
}

/** How an edit joins the undo history: its own step (false), the first of a gesture ("start"),
 *  or part of the gesture before it (true: merged into that step). */
type Merge = boolean | "start";

/** Apply an edit to the whole document: render it, and only then add it to the undo history.
 *  `merge`: part of the same gesture as the last edit (one undo step for the lot). */
export async function commitDoc(next: Doc, merge: Merge = false) {
  const h = latestHistory();
  if (merge === false) gesture = null; // any other edit ends a gesture
  // Nothing changed (a value set to what it was, a click that moved nothing): no undo step, and
  // the design doesn't count as changed.
  if (h.present && sameDoc(h.present, next)) return true;
  return showHistory(merge === true && h.present ? { ...h, present: next, future: [] } : pushHistory(h, next));
}

/** Apply an edit to the layout. */
export async function commit(next: Layout, merge: Merge = false) {
  const doc = currentDoc();
  return commitDoc({ layout: next, images: doc?.images ?? [] }, merge);
}

/** Apply an edit to the reference pictures (no re-render needed, but undoable). */
export function commitImages(images: RefImage[]) {
  const doc = currentDoc();
  if (!doc) return;
  // While a render is on its way, go through it so neither change overwrites the other.
  if (pending) return void commitDoc({ ...doc, images });
  const { history, setHistory } = useStore.getState();
  if (sameDoc(doc, { ...doc, images })) return;
  setHistory(pushHistory(history, { ...doc, images }));
}

/** An empty design on the fabric used last. */
function freshDoc(): Doc {
  const doc = newDoc();
  const fabric = loadPrefs().fabric;
  // New designs hide moves under later stitching: fewer jumps and trims to snip.
  const layout = { ...doc.layout, travel_under: true, ...(fabric ? { fabric } : {}) };
  return { ...doc, layout };
}

/** Start over with this document; it counts as saved (nothing to lose yet). */
async function replaceDoc(doc: Doc, path: string | null, fresh = true) {
  pendingOpen = { path, doc };
  return showHistory({ past: [], present: doc, future: [] }, fresh);
}

/** If there are unsaved changes, ask. Returns false if the user cancels. */
export async function confirmDiscard(): Promise<boolean> {
  const s = useStore.getState();
  // An edit still on its way to the screen counts as unsaved too.
  const present = latestHistory().present;
  if (!present || present === s.savedDoc) return true;
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
    else {
      // A stitch file opens in the middle of the hoop, as it will sew (the machine centres it).
      const doc = newDoc(path);
      if (await replaceDoc(doc, null)) {
        const shown = useStore.getState().design?.items?.find((it) => it.id === doc.layout.items[0]?.id);
        const layout = shown ? centreItem(doc.layout, shown.id, shown.center_mm) : doc.layout;
        if (layout !== doc.layout) await replaceDoc({ ...doc, layout }, null);
      }
    }
  } catch (err) {
    fail(err);
  } finally {
    setLoading(null);
  }
}

/** Show a project on the machine and hoop it was saved for, for now: your usual machine (the one
 *  new designs start on) stays as it is. */
export function applyProjectMachine(machine?: string | null, hoop?: string | null) {
  const m = machine ? useStore.getState().machines.find((x) => x.id === machine) : undefined;
  if (!m) return;
  const hoopId = m.hoops.some((h) => h.id === hoop) ? hoop! : (m.hoops[0]?.id ?? null);
  useStore.setState({ machineId: m.id, hoopId });
}

async function openProject(path: string) {
  const p = await engine().call<{
    layout: Layout; images: RefImage[]; machine?: string; hoop?: string; path: string; notes?: string[];
  }>("project.open", { path }, OPEN_TIMEOUT);
  applyProjectMachine(p.machine, p.hoop);
  await replaceDoc({ layout: { ...p.layout, title: stem(path) }, images: p.images ?? [] }, p.path);
  // Parts of a damaged project the engine left out (QA2 P4) are said, not silently gone.
  if (p.notes?.length) info(p.notes.join(" "));
}

/** Save the project. Asks for a name the first time, or always with `as`. */
export async function saveProject(as: boolean): Promise<boolean> {
  // An edit still rendering is saved too.
  await whenIdle();
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
    // The design takes the file's name (window title, panel) without counting as a change.
    const titled = doc.layout.title === stem(r.path) ? doc : { ...doc, layout: { ...doc.layout, title: stem(r.path) } };
    const now = useStore.getState();
    if (now.history.present === doc && !pending) useStore.setState({ projectPath: r.path, savedDoc: titled, history: { ...now.history, present: titled } });
    else useStore.setState({ projectPath: r.path, savedDoc: doc });
    // (Not while a crashed session's copy is waiting for Recover or Discard: that's other work.)
    if (!recoveryWaiting && !isDirty(useStore.getState())) void engine().call("project.discard_recovery").catch(() => {});
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
/** Work from a crashed session is waiting for Recover or Discard: never overwrite or delete it until then.
 *  True until checkRecovery() has asked, so a design started during startup can't delete the copy first. */
let recoveryWaiting = true;
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
      // Pictures go by path (the engine has them): not their whole contents every few seconds.
      const images = doc.images.map((im) => ({ ...im, data_url: undefined }));
      const project = { title: doc.layout.title, layout: doc.layout, images, machine: st.machineId, hoop: selectHoop(st)?.id ?? null, path: st.projectPath };
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
let checking = false;
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
    const run = async () => {
      // Checks are advice: they never hold up an edit. Wait while one is rendering, and run one
      // check at a time (the newest design, when the one before finishes).
      if (rendering || queued || checking) {
        checkTimer = setTimeout(run, CHECK_DELAY_MS);
        return;
      }
      const layout = currentLayout();
      const st = useStore.getState();
      if (!layout || !st.engine || seq !== checkSeq) return;
      checking = true;
      try {
        const r = await st.engine.call<CheckResult>("layout.check", { layout, heatmap: st.showDensity }, OPEN_TIMEOUT);
        if (seq === checkSeq) useStore.getState().setChecks(r);
      } catch {
        // Checks are advice; a failure here never interrupts the user.
      } finally {
        checking = false;
      }
    };
    checkTimer = setTimeout(run, CHECK_DELAY_MS);
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
    recoveryWaiting = false; // can't tell: keep autosaving rather than never
    return null;
  }
}

/** Put the crashed session's work back. True if it's on screen; otherwise the copy stays waiting. */
export async function restoreRecovery(): Promise<boolean> {
  try {
    const p = await engine().call<{ layout: Layout; images: RefImage[]; path: string | null; machine?: string; hoop?: string }>(
      "project.restore",
      {},
      OPEN_TIMEOUT,
    );
    applyProjectMachine(p.machine, p.hoop);
    const doc = { layout: p.layout, images: p.images ?? [] };
    // If it can't be shown (the error says why), keep the copy: the banner stays and closing won't delete it.
    if (!(await showHistory({ past: [], present: doc, future: [] }, true))) return false;
    recoveryWaiting = false;
    const s = useStore.getState();
    s.setTool("select");
    s.setMeasure(null);
    s.selectNode(null);
    // Restored work is unsaved until the user saves it.
    useStore.setState({ projectPath: p.path, savedDoc: null });
    s.select(null);
    info("Recovered your unsaved work. Save it to keep it.");
    return true;
  } catch (err) {
    fail(err);
    return false;
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
    const id = next.items[next.items.length - 1].id;
    if (await commit(next)) {
      // In the middle of the hoop (a little down and right of the last one added), in the same undo step.
      const shown = useStore.getState().design?.items?.find((it) => it.id === id);
      const n = next.items.length - 1;
      const centred = shown ? centreItem(next, id, shown.center_mm, [ADD_OFFSET_MM * n, ADD_OFFSET_MM * n]) : next;
      if (centred !== next) await commit(centred, true);
      useStore.getState().select(id);
      useStore.getState().requestFit();
    }
  } catch (err) {
    fail(err);
  }
}

/** Ctrl+Z. While drawing it removes the last point placed, like Backspace, and leaves the
 * history alone (QA2 U3: it threw the shape away and also undid the edit before it). */
export function undoEdit() {
  if (useStore.getState().pen) return penUndoPoint();
  void showHistory(undo(latestHistory()));
}

/** Ctrl+Y. Does nothing while drawing, so it can't change the design under a half-drawn shape. */
export function redoEdit() {
  if (useStore.getState().pen) return;
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

/** The selected designs and shapes (several with Shift+click, Ctrl+A or a group), else the target. */
export function selectionIds(): string[] {
  const s = useStore.getState();
  const l = currentLayout();
  if (!l) return [];
  const ids = [s.selectedId, ...s.extraIds].filter((id): id is string => !!id && l.items.some((it) => it.id === id));
  if (ids.length) return ids;
  const t = targetId();
  return t ? [t] : [];
}

/** Each selected item's centre on screen, and the centre of them all. */
export function selectionGeometry(ids: string[]): { centers: Record<string, [number, number]>; box: [number, number, number, number] | null; center: [number, number] } {
  const s = useStore.getState();
  const l = currentLayout();
  const shown = s.history.present?.layout;
  const centers: Record<string, [number, number]> = {};
  let box: [number, number, number, number] | null = null;
  for (const id of ids) {
    const it = l?.items.find((x) => x.id === id);
    const i = shown?.items.findIndex((x) => x.id === id) ?? -1;
    const b0 = i >= 0 ? s.design?.items?.[i]?.bounds_mm : null;
    // The bounds on screen are from the last render: shift them by any move made since (a quick
    // second R or arrow press), so the group turns and flips about where things really are.
    const was = i >= 0 ? shown!.items[i] : undefined;
    const [dx, dy] = it && was ? centreShift(was, it) : [0, 0];
    const b = b0
      ? ([b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy] as [number, number, number, number])
      : it && isObject(it)
        ? objectBox(it)
        : null;
    if (!b) continue;
    centers[id] = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
    box = box ? [Math.min(box[0], b[0]), Math.min(box[1], b[1]), Math.max(box[2], b[2]), Math.max(box[3], b[3])] : [b[0], b[1], b[2], b[3]];
  }
  return { centers, box, center: box ? [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2] : [0, 0] };
}

/** How far an item's centre moved between two versions of it (turns and flips keep the centre). */
function centreShift(was: LayoutItem, now: LayoutItem): [number, number] {
  if (isObject(was) && isObject(now)) {
    const [a, b] = [objectCenter(was), objectCenter(now)];
    return [b[0] - a[0], b[1] - a[1]];
  }
  return [now.transform.x - was.transform.x, now.transform.y - was.transform.y];
}

/** The point a side stretch of one drawn shape keeps still: the middle of the opposite side of its
 *  outline (its stitches sit a fixed margin inside the outline, which doesn't stretch). Null for
 *  anything else (stitch files, lettering, several things): the frame's side is right for those. */
export function shapeStretchAnchor(ids: string[], side: "n" | "e" | "s" | "w"): [number, number] | null {
  if (ids.length !== 1) return null;
  const o = currentLayout()?.items.find((it) => it.id === ids[0]);
  if (!o || !isObject(o)) return null;
  const t = o.transform;
  if (t.rotate || t.scale_x !== 1 || t.scale_y !== 1 || t.flip_x || t.flip_y) return null;
  const b = objectBox(o);
  if (!b) return null;
  const [x0, y0, x1, y1] = [b[0] + t.x, b[1] + t.y, b[2] + t.x, b[3] + t.y];
  return side === "e" ? [x0, (y0 + y1) / 2] : side === "w" ? [x1, (y0 + y1) / 2] : side === "s" ? [(x0 + x1) / 2, y0] : [(x0 + x1) / 2, y1];
}

function objectBox(o: ObjectItem): [number, number, number, number] | null {
  const pts = shapeNodeLists(o).flat();
  if (!pts.length) return null;
  const xs = pts.map((n) => n[0]);
  const ys = pts.map((n) => n[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

const PINNED_STAYS_PUT = "That's pinned (📌), so it stays put. Unpin it to move, turn or resize it.";

/** Turn, mirror, resize or move everything selected, as one. */
export function editSelection(op: TogetherOp, merge: Merge = false) {
  const l = currentLayout();
  const ids = selectionIds();
  if (!l || !ids.length) return;
  // A pinned shape stays where it is: no arrow keys, R, Alt+H/V or resizing until it is unpinned.
  if (ids.some((id) => l.items.find((it) => it.id === id)?.locked)) return info(PINNED_STAYS_PUT);
  if (ids.length === 1 && !op.move) {
    // One item turns, flips and grows about its own centre.
    const id = ids[0];
    return void commit(op.rotate ? rotateBy(l, id, op.rotate) : op.mirror ? mirror(l, id, op.mirror) : op.scale ? scaleBy(l, id, op.scale) : l);
  }
  const g = selectionGeometry(ids);
  void commit(transformTogether(l, ids, g.centers, g.center, op), merge);
}

/** Click on an item: select it, and the rest of its group. Shift+click adds or removes it. */
export function pickItem(id: string, add: boolean) {
  const s = useStore.getState();
  const l = currentLayout();
  const it = l?.items.find((x) => x.id === id);
  if (!l || !it) return s.select(id);
  const members = it.group ? l.items.filter((x) => x.group === it.group).map((x) => x.id) : [id];
  const current = [s.selectedId, ...s.extraIds].filter((x): x is string => !!x && l.items.some((y) => y.id === x));
  if (add) {
    const on = current.includes(id);
    const next = on ? current.filter((x) => !members.includes(x)) : [...current, ...members.filter((x) => !current.includes(x))];
    return s.setSelection(next[0] ?? null, next.slice(1));
  }
  // Clicking something already selected keeps the whole selection (so a drag moves it all).
  if (current.includes(id)) return;
  s.setSelection(id, members.filter((x) => x !== id));
}

/** Ctrl+A: select every design and shape. */
function selectAll() {
  const l = currentLayout();
  if (!l?.items.length) return;
  useStore.getState().setSelection(l.items[0].id, l.items.slice(1).map((it) => it.id));
}

/** Ctrl+G / Ctrl+U: group the selection (it selects and moves as one) or ungroup it. */
function groupSelection(on: boolean) {
  const l = currentLayout();
  const ids = selectionIds();
  if (!l || (on && ids.length < 2)) return info("Select two or more things first (Shift+click, or Ctrl+A for everything).");
  void commit(setGroup(l, ids, on ? `g${Date.now().toString(36)}` : null)).then((ok) =>
    ok && info(on ? `Grouped ${ids.length} things: they now select and move together.` : "Ungrouped."),
  );
}

/** Remove the selected design, drawn object or picture. */
export function removeSelected() {
  const s = useStore.getState();
  const doc = currentDoc();
  if (!doc || !s.selectedId) return;
  if (doc.images.some((im) => im.id === s.selectedId)) {
    commitImages(removeImage(doc.images, s.selectedId));
    s.select(null);
    return;
  }
  removeItems(selectionIds());
}

/** Remove these items (one undo step). Nothing stays selected, so the next Delete can't act on
 *  them again; if the edit fails (the error says why), the selection comes back to try again. */
function removeItems(ids: string[]) {
  const s = useStore.getState();
  let l = currentLayout();
  if (!l) return;
  for (const id of ids) l = removeItem(l, id);
  const { selectedId, extraIds } = s;
  void commit(l).then((ok) => {
    const now = useStore.getState();
    if (!ok && !now.selectedId && selectedId) now.setSelection(selectedId, extraIds);
  });
  s.select(null);
}

/** Ctrl+D: a copy of everything selected (one undo step); the copies end up selected. */
export function duplicateSelected() {
  let l = currentLayout();
  const ids = selectionIds();
  if (!l || !ids.length) return;
  const copies: string[] = [];
  for (const id of ids) {
    const r = duplicateItem(l, id);
    l = r.layout;
    copies.push(r.id);
  }
  const out = l;
  void commit(out).then((ok) => ok && useStore.getState().setSelection(copies[0], copies.slice(1)));
}

/** Drag and drop in Order & colors: sew `id` at position `to`. */
export function moveItemTo(id: string, to: number) {
  const l = currentLayout();
  if (l) void commit(moveItem(l, id, to));
}

/** Sew an item one place earlier (-1) or later (1), building on the newest version. */
export function reorderItem(id: string, dir: -1 | 1) {
  const l = currentLayout();
  if (l) void commit(reorder(l, id, dir));
}

/** Whether the selected item can be sewn earlier (-1) or later (1). */
function canMoveInOrder(dir: -1 | 1): boolean {
  const l = currentLayout();
  const id = targetId();
  if (!l || !id || !canEdit() || drawing() || useStore.getState().extraIds.length) return false;
  const i = l.items.findIndex((it) => it.id === id);
  return dir < 0 ? i > 0 : i >= 0 && i < l.items.length - 1;
}

/** Sew the selected item one place earlier or later, or first or last. */
function sewAt(to: -1 | 1 | "first" | "last") {
  const l = currentLayout();
  const id = targetId();
  if (!l || !id) return;
  if (to === "first") moveItemTo(id, 0);
  else if (to === "last") moveItemTo(id, l.items.length - 1);
  else reorderItem(id, to);
}

/** Move what's selected so its middle is the hoop's middle. */
function centreSelection() {
  const g = selectionGeometry(selectionIds());
  if (!g.box) return;
  const cx = (g.box[0] + g.box[2]) / 2;
  const cy = (g.box[1] + g.box[3]) / 2;
  if (Math.hypot(cx, cy) < 0.05) return info("It's already in the middle of the hoop.");
  editSelection({ move: [round2(-cx), round2(-cy)] });
}

/** Whether the selected item (the target) is a drawn shape for which `test` holds. */
function targetIs(test: (o: ObjectItem) => boolean): boolean {
  const it = currentLayout()?.items.find((x) => x.id === targetId());
  return !!it && isObject(it) && test(it);
}

/** A placed stitch file sewn in one color (several selected can take one thread together). */
function singleColorFile(id: string): boolean {
  const l = currentLayout();
  const i = l?.items.findIndex((x) => x.id === id) ?? -1;
  if (!l || i < 0 || l.items[i].kind !== "file") return false;
  const blocks = (useStore.getState().design?.blocks ?? []).flatMap((b) => (b.sources ?? []).filter((src) => src.item === i).map((src) => src.block));
  return new Set(blocks).size === 1;
}

/** Drawn shapes and text have one thread to change here; a stitch file's colors are changed one by one in Order & colors. */
function recolorable(id: string | null): boolean {
  const it = id ? currentLayout()?.items.find((x) => x.id === id) : undefined;
  return !!it && (isObject(it) || isText(it));
}

/** Put the cursor in the selected text's words, in the panel. */
function editTextWords() {
  const id = targetId();
  if (!id) return;
  textToEdit = id;
  window.dispatchEvent(new CustomEvent("ludd:edit-text", { detail: id }));
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
    info("Picture added. Move and size it, then pin it (📌) so you can trace over it.");
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

/** Settings a new shape of this kind starts with: the standard ones, then whatever you set
 *  last on a shape of that kind (so a fill made denser makes the next fill denser too). */
function deleteSelectedNode() {
  const n = useStore.getState().selectedNode;
  if (n) {
    deleteNode(n.id, n.list as NodeList, n.index);
    useStore.getState().selectNode(null);
  }
}

export function defaultsFor(kind: ObjectKind): Record<string, unknown> {
  return withoutDeadCrossHatch<Record<string, unknown>>({ ...DEFAULT_PARAMS[kind], ...(loadPrefs().objectDefaults?.[kind] ?? {}) });
}

/** Settings that belong to one shape, not to the next one you draw. */
const NOT_REMEMBERED = new Set(["angle_deg", "reverse", "angle_lines", "ripple_center", "blend_flip"]);

function rememberDefaults(kind: ObjectKind, patch: Record<string, unknown>) {
  const all = { ...(loadPrefs().objectDefaults ?? {}) };
  const mine: Record<string, unknown> = { ...(all[kind] ?? {}) };
  for (const [k, v] of Object.entries(patch)) {
    if (NOT_REMEMBERED.has(k)) continue;
    if (v === undefined) delete mine[k];
    else mine[k] = v;
  }
  all[kind] = mine;
  savePrefs({ objectDefaults: all });
}

/** Has this kind of shape got settings of your own for new shapes? */
export function hasOwnDefaults(kind: ObjectKind): boolean {
  return Object.keys(loadPrefs().objectDefaults?.[kind] ?? {}).length > 0;
}

/** Back to the standard settings for new shapes of this kind (shapes already drawn keep theirs). */
export function resetDefaults(kind: ObjectKind) {
  const all = { ...(loadPrefs().objectDefaults ?? {}) };
  delete all[kind];
  savePrefs({ objectDefaults: all });
  if (kind === "satin") {
    savePrefs({ satinWidth: undefined });
    useStore.getState().setSatinWidth(3);
  }
  info(`New ${KIND_PLURAL[kind]} will start with the standard settings.`);
}

const KIND_PLURAL: Record<ObjectKind, string> = { run: "lines", satin: "satins", fill: "fills", applique: "appliques" };

/** Points each shape needs before it can be finished. */
export const MIN_POINTS: Record<ObjectKind, number> = { run: 2, satin: 2, fill: 3, applique: 3 };

export function penReady(): boolean {
  const pen = useStore.getState().pen;
  if (!pen) return false;
  return pen.a.length >= MIN_POINTS[pen.kind];
}

/** Clicks closer than this to the last point are the same point. */
const SAME_POINT_MM = 0.3;

export function penAdd(node: PathNode) {
  const s = useStore.getState();
  const tool = s.tool;
  if (tool === "select" || tool === "text" || tool === "autotrace") return;
  const pen = s.pen ?? { kind: tool, a: [], b: [] };
  // A double-click (to finish) also clicks twice: don't add the same spot again.
  const last = pen.a[pen.a.length - 1];
  if (last && Math.hypot(node[0] - last[0], node[1] - last[1]) < SAME_POINT_MM) return;
  s.setPen({ ...pen, a: [...pen.a, node] });
}

export function penUndoPoint() {
  const s = useStore.getState();
  const pen = s.pen;
  if (!pen) return;
  if (pen.a.length > 1) s.setPen({ ...pen, a: pen.a.slice(0, -1) });
  else s.setPen(pen.carveFor ? { ...pen, a: [] } : null); // carving goes on until Esc
}

export function penCancel() {
  cancelTraceQueue();
  const pen = useStore.getState().pen;
  if (pen?.carveFor) return cancelCarve(pen);
  useStore.getState().setPen(null);
  if (pen?.holeFor) {
    // A hole (O) dropped: back to the tool used before, with its fill still selected.
    useStore.getState().setTool(pen.holeBack ?? "select");
    useStore.getState().select(pen.holeFor);
    return info("Hole dropped.");
  }
  // Say so: a single point can be hard to see, and nobody should wonder whether Esc worked.
  if (pen && (pen.a.length || pen.b.length)) info("Shape dropped. Click to start again, or press Esc again for Select.");
}

/** Turn the pen's points into an object, add it to the layout and select it. */
export async function penFinish(opts: { close?: boolean } = {}) {
  const s = useStore.getState();
  const pen = s.pen;
  if (!pen || !penReady()) {
    if (pen) info(`Keep clicking: this shape needs at least ${MIN_POINTS[pen.kind]} points.`);
    return;
  }
  // A line carved into a fill (Shift+C): Ctrl+right-click closes it, like any line.
  if (pen.carveFor) return finishCarve(opts.close ? { ...pen, closed: true } : pen);
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  const layout = currentLayout()!;
  const thread = s.drawThread;
  // A satin fitted all the way round an edge is closed too.
  const closed = opts.close || pen.closed ? { closed: true } : {};
  // Continued from its first point (K), the line keeps its direction, with the new points before its
  // old start: exactly the points the canvas has been drawing.
  const points = penPoints(pen.a, pen.prepend);
  const obj =
    pen.kind === "run"
      ? { kind: "run" as const, geometry: { nodes: points, ...closed }, params: defaultsFor("run"), thread }
      : pen.kind === "satin"
        ? { kind: "satin" as const, geometry: { nodes: points, width_mm: s.satinWidth, ...closed }, params: defaultsFor("satin"), thread }
        : { kind: "fill" as const, geometry: { outline: points }, params: defaultsFor("fill"), thread };
  s.setPen(null);
  // A hole (O): add it to the fill it was drawn in.
  if (pen.holeFor && layout.items.some((it) => it.id === pen.holeFor)) {
    const id = pen.holeFor;
    const next = updateObject(layout, id, (o) =>
      o.kind === "fill" || o.kind === "applique" ? ({ ...o, geometry: { ...o.geometry, holes: [...(o.geometry.holes ?? []), pen.a] } } as ObjectItem) : o,
    );
    // Back to the tool used before O (the tool you chose stays chosen).
    useStore.getState().setTool(pen.holeBack ?? "select");
    if (await commit(next)) useStore.getState().select(id);
    return;
  }
  // Continuing an object replaces its points and keeps its thread and settings.
  if (pen.replaceId && layout.items.some((it) => it.id === pen.replaceId)) {
    const id = pen.replaceId;
    // Keep what the pen doesn't draw (a fill's holes, a closed line, a satin's width).
    const drawn = pen.kind === "fill" ? { outline: points } : { nodes: points, ...closed };
    const next = updateObject(layout, id, (o) => ({ ...o, geometry: { ...o.geometry, ...drawn } }) as ObjectItem);
    if (await commit(next)) useStore.getState().select(id);
    return;
  }
  const { layout: next, id } = addObject(layout, obj as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
  if (await commit(next)) useStore.getState().select(id);
  // It couldn't be made (the error says why): the clicked points come back, to fix and try again.
  else if (!useStore.getState().pen && useStore.getState().tool === pen.kind) useStore.getState().setPen(pen);
}

/** Pick the selected shape back up in the pen to add more points ("continue digitizing"): at its
 *  end, or, for an open line or ribbon with its first point selected, before its start. */
export function continueDrawing() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || !isObject(o)) return;
  if (o.kind === "satin" && !isRibbon(o)) return info("This satin was made by clicking both of its sides: drag its points to change it.");
  const a = o.kind === "run" || o.kind === "satin" ? (o.geometry as { nodes: PathNode[] }).nodes : o.geometry.outline;
  const b: PathNode[] = [];
  // An applique is drawn like a fill (a closed outline); it stays an applique.
  const kind = o.kind === "applique" ? "fill" : o.kind;
  const open = (o.kind === "run" || o.kind === "satin") && !(o.geometry as { closed?: boolean }).closed;
  const fromStart = open && a.length > 1 && s.selectedNode?.id === o.id && s.selectedNode.list === "nodes" && s.selectedNode.index === 0;
  s.setTool(kind); // (lets go of the selected point, so it's looked at first)
  s.setPen({ kind, a: fromStart ? reversePath(a) : [...a], b: [...b], replaceId: o.id, ...(fromStart ? { prepend: true } : {}) });
  s.setDrawThread(o.thread);
  info(fromStart ? "Keep clicking to add points before this shape's start; Enter when done." : "Keep clicking to add points to this shape; Enter when done.");
}

/** Add a ready-made shape (as a fill) in the middle of the hoop, selected, ready to reshape.
 *  `opts.sides` is for the polygon. */
export async function addShape(shape: ShapeId, opts?: { sides?: number }) {
  const s = useStore.getState();
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  const hoop = selectHoop(useStore.getState());
  const size = Math.min(60, (hoop?.width_mm ?? 100) * 0.6);
  const { layout: next, id } = addObject(currentLayout()!, {
    kind: "fill",
    geometry: { outline: shapeNodes(shape, 0, 0, size, opts) },
    params: defaultsFor("fill"), // your remembered fill settings, like a drawn fill
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
  return { path: pick.path, index: pick.index, family: pick.family, style: pick.style, ...(pick.made_of ? { made_of: pick.made_of } : {}) };
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
      // The Text tool stays chosen (click another spot for more text; click a text to pick it).
      useStore.getState().select(item.id);
      // Ask the panel to focus the text box so typing replaces the placeholder. The panel for the
      // new text isn't there yet: it takes the request when it appears (or now, if it already is).
      textToEdit = item.id;
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
  // New words, font, size or look make new letters: the starts and ends chosen for the old ones go.
  const before = l.items.find((it) => it.id === id);
  const newLetters =
    !!before &&
    isText(before) &&
    (["text", "font", "size_mm", "spacing_mm", "style", "shape", "monogram", "align", "line_spacing", "slant_deg", "envelope", "vertical", "monogram_style"] as const).some(
      (k) => k in patch && JSON.stringify(patch[k]) !== JSON.stringify(before[k]),
    );
  const changed = (it: TextItem): TextItem => {
    const next = { ...it, ...patch, ...(patch.thread ? { threads: [] } : {}), ...(newLetters ? { letters: undefined } : {}) };
    return "text" in patch ? pruneLetterEdits(next) : next;
  };
  void commit({ ...l, items: l.items.map((it) => (it.id === id && it.kind === "text" ? changed(it) : it)) });
}

/** A letter's green (start) or red (end) dot dragged to `at` (mm, as shown): kept on the text in
 *  its own frame, so it stays put on the letter when the text is moved, turned or resized. */
export async function setLetterEnd(id: string, part: number, which: "start" | "end", at: [number, number]) {
  const it = currentLayout()?.items.find((x) => x.id === id);
  if (!it || !isText(it)) return;
  try {
    const local = await engine().call<[number, number]>("text.letter_frame", { item: it, at: [round2(at[0]), round2(at[1])] });
    const l = currentLayout();
    const now = l?.items.find((x) => x.id === id);
    // Moved, turned, retyped or undone meanwhile: the point no longer fits it.
    if (!l || !now || !isText(now) || now !== it) return;
    const letters = { ...(now.letters ?? {}) };
    letters[String(part)] = { ...letters[String(part)], [which === "start" ? "start_mm" : "end_mm"]: local };
    await commit({ ...l, items: l.items.map((x) => (x.id === id ? { ...now, letters } : x)) });
  } catch (err) {
    info(err instanceof Error ? err.message : String(err));
  }
}

/** Lettering into drawn shapes, one per letter part, grouped, in its place in the sewing order:
 *  each can then be edited like any shape. */
export async function textToShapes() {
  const id = targetId();
  const l = currentLayout();
  const it = l?.items.find((x) => x.id === id);
  if (!l || !it || !isText(it)) return info("Select some lettering first.");
  try {
    const r = await engine().call<{ objects: Omit<ObjectItem, "id" | "transform" | "threads" | "ops">[] }>("text.to_shapes", { item: it }, OPEN_TIMEOUT);
    if (!r.objects.length) return info("There are no letters to break apart.");
    // Changed or removed meanwhile: these letters are out of date.
    const now = currentLayout();
    if (!now || !unchanged(it.id, it)) return;
    // The letters stay together: in the text's own group if it had one, else a new group.
    const group = it.group ?? (r.objects.length > 1 ? `g${Date.now().toString(36)}` : undefined);
    const shapes = r.objects.map(
      (o) => ({ ...o, id: newId(), transform: { ...IDENTITY }, threads: [], ops: [], ...(group ? { group } : {}), ...(it.locked ? { locked: true } : {}) }) as ObjectItem,
    );
    const at = now.items.indexOf(it);
    const items = [...now.items.slice(0, at), ...shapes, ...now.items.slice(at + 1)];
    if (await commit({ ...now, items })) {
      useStore.getState().setSelection(shapes[0].id, shapes.slice(1).map((x) => x.id));
      const lost = it.ops?.length ? " The stops and trims you'd added to the lettering were left out: add them again on the shapes if you need them." : "";
      info(`Broke "${it.text.replace(/\s*[\r\n]+\s*/g, " ")}" into ${shapes.length} shapes (grouped). Each is an ordinary shape now: click one (Ctrl+U ungroups) to change its points, stitches, direction or dots.${lost}`);
    }
  } catch (err) {
    info(err instanceof Error ? err.message : String(err));
  }
}

/** Convert a font into an editable LUDD stitch font (.luddfont). */
export async function saveStitchFont(font: FontRef, style: TextItem["style"]) {
  try {
    info("Making the stitch font…");
    // Empty dest and chars: every letter the font has (with accents), saved in LUDD's fonts folder,
    // where the font list finds it.
    const r = await engine().call<{ path: string; glyphs: number; folder: string }>(
      "fonts.export_stitch_font",
      { font, dest: "", chars: "", cap_height_mm: 12, style },
      OPEN_TIMEOUT,
    );
    useStore.setState({ fonts: null });
    info(`Saved the stitch font ${basename(r.path)} (${r.glyphs} letters) in ${r.folder}. It's in the font list now; open the file in a text editor to fine-tune it.`);
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- object editing

export function editObject(id: string, fn: (o: ObjectItem) => ObjectItem): Promise<boolean> {
  const l = currentLayout();
  return l ? commit(updateObject(l, id, fn)) : Promise.resolve(false);
}

/** Whether an item is still exactly as it was before an engine call: if it was changed, undone or
 *  removed meanwhile, the engine's answer (worked out from the old one) is dropped, so it can't
 *  overwrite the newer edit. */
function unchanged(id: string, before: LayoutItem): boolean {
  return currentLayout()?.items.find((it) => it.id === id) === before;
}

/** Change a shape's stitch settings. They also become the settings new shapes of its kind start with. */
export function setObjectParams(id: string, patch: Record<string, unknown>) {
  const o = currentLayout()?.items.find((it) => it.id === id);
  if (o && isObject(o)) rememberDefaults(o.kind, patch);
  editObject(id, (x) => ({ ...x, params: withoutDeadCrossHatch<Record<string, unknown>>({ ...x.params, ...patch }) }) as ObjectItem);
}

/** A satin ribbon's width; new ribbons start with it too. */
export function setSatinWidth(id: string, mm: number) {
  const w = Math.min(12, Math.max(0.5, Math.round(mm * 100) / 100));
  savePrefs({ satinWidth: w });
  useStore.getState().setSatinWidth(w);
  editObject(id, (o) => (isRibbon(o) ? ({ ...o, geometry: { ...o.geometry, width_mm: w } } as ObjectItem) : o));
}

/** Rename a design, shape, lettering or picture (an empty name puts the standard one back). */
export function renameThing(id: string, name: string) {
  const doc = currentDoc();
  if (!doc) return;
  if (doc.images.some((im) => im.id === id)) {
    if (name.trim()) setPicture(id, { name: name.trim().slice(0, 80) });
    return;
  }
  const l = currentLayout();
  if (l) void commit(renameItem(l, id, name));
}

/** A satin ribbon around a fill's (or applique's) edge, sewn right after it: the fill-then-outline look. */
export async function addSatinBorder(id?: string) {
  const s = useStore.getState();
  const l = currentLayout();
  const o = l?.items.find((it) => it.id === (id ?? s.selectedId));
  if (!l || !o || !isObject(o)) return;
  const outline = o.kind === "fill" || o.kind === "applique" ? o.geometry.outline : o.kind === "run" && o.geometry.closed ? o.geometry.nodes : null;
  if (!outline) return info("Select a fill (or a closed line) first, then add a satin border to it.");
  // The border's thread: the last satin's, so a design's outlines match.
  const lastSatin = [...l.items].reverse().find((it) => it.kind === "satin") as ObjectItem | undefined;
  const thread = lastSatin?.thread ?? { color: "#000000", name: "Black", brand: "", catalog: "" };
  const { layout: withBorder, id: nid } = addObject(l, {
    kind: "satin",
    geometry: { nodes: outline, width_mm: s.satinWidth, closed: true },
    params: defaultsFor("satin"),
    thread,
  } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
  // Sew it straight after its fill.
  const added = withBorder.items[withBorder.items.length - 1];
  const items = withBorder.items.slice(0, -1);
  items.splice(items.findIndex((it) => it.id === o.id) + 1, 0, added);
  if (await commit({ ...withBorder, items })) useStore.getState().select(nid);
}

/** Add shapes from Auto-trace (one undo step), selecting the last. Satins get `border` if given. */
export async function addTraced(
  shapes: ((
    | { kind: "fill"; outline: PathNode[]; holes: PathNode[][] }
    | { kind: "satin"; nodes: PathNode[]; width_mm: number; closed: boolean }
    | { kind: "column"; rail_a: PathNode[]; rail_b: PathNode[]; widest_mm: number }
    | { kind: "run"; nodes: PathNode[]; closed: boolean }
  ) & { thread?: Thread })[],
  thread: Thread,
  border?: Thread,
) {
  const s = useStore.getState();
  if (!s.history.present) await replaceDoc(freshDoc(), null);
  let l = currentLayout()!;
  let last = "";
  for (const sh of shapes) {
    const obj =
      sh.kind === "fill"
        ? { kind: "fill" as const, geometry: { outline: sh.outline, ...(sh.holes.length ? { holes: sh.holes } : {}) }, params: defaultsFor("fill"), thread: sh.thread ?? thread }
        : sh.kind === "satin"
          ? { kind: "satin" as const, geometry: { nodes: sh.nodes, width_mm: sh.width_mm, ...(sh.closed ? { closed: true } : {}) }, params: defaultsFor("satin"), thread: sh.thread ?? border ?? thread }
          : sh.kind === "column"
            ? { kind: "satin" as const, geometry: { rail_a: sh.rail_a, rail_b: sh.rail_b }, params: satinFillParams(sh), thread: sh.thread ?? thread }
            : { kind: "run" as const, geometry: { nodes: sh.nodes, ...(sh.closed ? { closed: true } : {}) }, params: defaultsFor("run"), thread: sh.thread ?? thread };
    const r = addObject(l, obj as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
    l = r.layout;
    last = r.id;
  }
  const ok = await commit(l);
  if (ok) useStore.getState().select(last);
  return ok;
}

export function setObjectThread(id: string, thread: Thread) {
  useStore.getState().setDrawThread(thread);
  editObject(id, (o) => ({ ...o, thread, threads: otherColors(o) }));
}

/** The colors given to an item's other parts (a blend's), kept when its own thread changes. */
const otherColors = (it: LayoutItem): (Thread | null)[] => (isObject(it) && it.threads.length > 1 ? [null, ...it.threads.slice(1)] : []);

/** Which list of nodes in an object's geometry: a key, a hole number for fills, or a carved line. */
export type NodeList = "nodes" | "rail_a" | "rail_b" | "outline" | number | `carve:${number}`;

/** A carved line's number in its list ("carve:2" is the third), or -1 for any other list. */
const carveIndex = (key: NodeList) => (typeof key === "string" && key.startsWith("carve:") ? Number(key.slice(6)) : -1);

export function nodeLists(o: ObjectItem): { key: NodeList; nodes: PathNode[]; closed: boolean }[] {
  if (o.kind === "run") return [{ key: "nodes", nodes: o.geometry.nodes, closed: !!o.geometry.closed }];
  if (isRibbon(o)) return [{ key: "nodes", nodes: o.geometry.nodes, closed: !!o.geometry.closed }];
  if (o.kind === "satin") {
    const g = o.geometry as SatinColumn;
    return [
      { key: "rail_a", nodes: g.rail_a, closed: false },
      { key: "rail_b", nodes: g.rail_b, closed: false },
    ];
  }
  return [
    { key: "outline", nodes: o.geometry.outline, closed: true },
    ...(o.geometry.holes ?? []).map((h, i) => ({ key: i as NodeList, nodes: h, closed: true })),
    ...(o.geometry.carve ?? []).map((c, i) => ({ key: `carve:${i}` as NodeList, nodes: c, closed: false })),
  ];
}

function withNodes(o: ObjectItem, key: NodeList, fn: (nodes: PathNode[]) => PathNode[]): ObjectItem {
  const g = o.geometry as unknown as Record<string, PathNode[] | PathNode[][]>;
  const c = carveIndex(key);
  if (c >= 0) {
    const carve = [...((g.carve as PathNode[][]) ?? [])];
    carve[c] = fn(carve[c]);
    return { ...o, geometry: { ...o.geometry, carve } } as ObjectItem;
  }
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

/** The green (start) or red (end) dot dragged to `at` (mm): the engine works out the change
 *  (a fill's start edge or end, a border's first point, or a line turned round), then it's one undo step. */
export async function moveStitchEnd(id: string, which: "start" | "end", at: [number, number]) {
  const o = currentLayout()?.items.find((it) => it.id === id);
  if (!o || !isObject(o)) return;
  // An open running line's dots sit on its end points: dragging one moves that end point, unless
  // it's dropped by the other end, which turns the line round. (A satin starts and stops anywhere.)
  const g = o.geometry as { nodes?: PathNode[]; closed?: boolean };
  if (o.kind === "run" && g.nodes && g.nodes.length >= 2 && !g.closed) {
    const ns = g.nodes;
    const [here, other] = which === "start" ? [ns[0], ns[ns.length - 1]] : [ns[ns.length - 1], ns[0]];
    const d = (n: PathNode) => Math.hypot(n[0] - at[0], n[1] - at[1]);
    if (d(other) >= d(here)) return moveNode(id, "nodes", which === "start" ? 0 : ns.length - 1, at[0], at[1]);
  }
  try {
    const next = await engine().call<ObjectItem>("shape.set_end", { obj: o, which, at: [round2(at[0]), round2(at[1])] });
    if (!unchanged(id, o)) return;
    await editObject(id, () => next);
  } catch (err) {
    info(err instanceof Error ? err.message : String(err));
  }
}

/** The purple dots of a fill dragged: its rows run along the line between them. (Not remembered for
 *  new fills: it belongs to this shape.) */
export function setFillDirection(id: string, line: [[number, number], [number, number]]): Promise<boolean> {
  const r = (q: [number, number]): [number, number] => [round2(q[0]), round2(q[1])];
  const a = r(line[0]);
  const b = r(line[1]);
  if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5) {
    info("Drag the dots further apart: their line sets the stitch direction.");
    return Promise.resolve(false);
  }
  return editObject(id, (o) => ({ ...o, params: { ...o.params, angle_deg: angleOf(a, b), angle_line: [a, b] } }) as unknown as ObjectItem);
}

/** The purple dots of a satin column dragged round its outline: the satin runs from one to the
 *  other, its stitches across the shape between them. */
export async function setSatinTips(id: string, tips: [[number, number], [number, number]]) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o || o.kind !== "satin" || isRibbon(o)) return;
  try {
    const r = await engine().call<SatinFill>(
      "shape.satin_fill",
      { outline: columnOutline(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] }), tips: tips.map((t) => [round2(t[0]), round2(t[1])]) },
      OPEN_TIMEOUT,
    );
    if (!unchanged(id, o)) return;
    await editObject(id, (it) => withSatinRails(it, r));
  } catch (err) {
    info(err instanceof Error ? err.message : String(err));
  }
}

/** Right-click on a point (or C while drawing) cycles curve → line → cusp. */
export const nextKind = (k: PathNode[2]): PathNode[2] => (k === "s" ? "l" : k === "l" ? "c" : "s");

export function toggleNodeKind(id: string, key: NodeList, index: number) {
  editObject(id, (o) => withNodes(o, key, (ns) => ns.map((n, i) => (i === index ? [n[0], n[1], nextKind(n[2])] : n))));
}

export function deleteNode(id: string, key: NodeList, index: number) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o) return;
  // Satin rails stay paired: removing a point removes its partner on the other side.
  if (o.kind === "satin" && !("nodes" in o.geometry)) {
    if (o.geometry.rail_a.length <= 2) return info("A satin needs at least two points on each side.");
    editObject(id, (x) => ({
      ...x,
      geometry: {
        rail_a: (o.geometry as SatinColumn).rail_a.filter((_, i) => i !== index),
        rail_b: (o.geometry as SatinColumn).rail_b.filter((_, i) => i !== index),
      },
    }) as ObjectItem);
    return;
  }
  const list = nodeLists(o).find((l) => l.key === key);
  const carved = carveIndex(key);
  if (carved >= 0 && list && list.nodes.length <= 2) {
    // A carved line with too few points left: delete the line.
    useStore.getState().selectNode(null);
    editObject(id, (x) => {
      const carve = ((x.geometry as FillGeometry).carve ?? []).filter((_, i) => i !== carved);
      return { ...x, geometry: { ...x.geometry, carve: carve.length ? carve : undefined } } as ObjectItem;
    });
    info("Carved line removed.");
    return;
  }
  const min = o.kind === "run" || o.kind === "satin" || carved >= 0 ? 2 : 3;
  if (list && typeof key === "number" && list.nodes.length <= min) {
    // A hole with too few points left to be a hole: delete the hole (as in Embrilliance).
    useStore.getState().selectNode(null);
    editObject(id, (x) => {
      const g = x.geometry as { holes?: PathNode[][] };
      const holes = (g.holes ?? []).filter((_, i) => i !== key);
      return { ...x, geometry: { ...x.geometry, holes: holes.length ? holes : undefined } } as ObjectItem;
    });
    info("Hole removed.");
    return;
  }
  if (!list || list.nodes.length <= min)
    return info(`This shape needs at least ${min} points. To delete the whole shape, select it and press Delete.`);
  editObject(id, (x) => withNodes(x, key, (ns) => ns.filter((_, i) => i !== index)));
}

/** Insert a corner point after `index` (between it and the next point). */
export function insertNode(id: string, key: NodeList, index: number, x: number, y: number) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o) return;
  if (o.kind === "satin" && !("nodes" in o.geometry)) {
    // Add a matching rung: the new point on this side and the midpoint on the other.
    const g = o.geometry;
    const other = key === "rail_a" ? g.rail_b : g.rail_a;
    const a = other[index];
    const b = other[Math.min(index + 1, other.length - 1)];
    const partner: PathNode = [round2((a[0] + b[0]) / 2), round2((a[1] + b[1]) / 2), "c"];
    const mine: PathNode = [round2(x), round2(y), "c"];
    const ins = (ns: PathNode[], n: PathNode) => [...ns.slice(0, index + 1), n, ...ns.slice(index + 1)];
    editObject(id, () => ({
      ...o,
      geometry: key === "rail_a" ? { rail_a: ins(g.rail_a, mine), rail_b: ins(g.rail_b, partner) } : { rail_a: ins(g.rail_a, partner), rail_b: ins(g.rail_b, mine) },
    }) as ObjectItem);
    return;
  }
  editObject(id, (x0) => withNodes(x0, key, (ns) => [...ns.slice(0, index + 1), [round2(x), round2(y), "c"], ...ns.slice(index + 1)]));
}

/** The same points sewn another way: a line, a satin ribbon, a fill or an applique. */
/** A satin filling a shape, from the engine: the outline split at its tips into two sides. */
type SatinFill = { rail_a: PathNode[]; rail_b: PathNode[]; widest_mm: number; ways: number };

/** Which way (tips) each satin fill uses now, for Shift+W. */
const satinWays = new Map<string, number>();

/** The outline of a two-sided satin: side a, then side b back to the start (the tips are shared). */
export function columnOutline(g: { rail_a: PathNode[]; rail_b: PathNode[] }): PathNode[] {
  const back = [...g.rail_b].reverse();
  const same = (p: PathNode, q: PathNode) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 0.05;
  const b = back.filter((n, i) => !((i === 0 && same(n, g.rail_a[g.rail_a.length - 1])) || (i === back.length - 1 && same(n, g.rail_a[0]))));
  return [...g.rail_a, ...b];
}

/** Satin settings for a satin fill: wide ones split their long stitches. */
const satinFillParams = (r: { widest_mm: number }) => ({ ...defaultsFor("satin"), ...(r.widest_mm > SPLIT_FROM_MM ? { split_mm: 7 } : {}) });
/** A satin fill wider than this has its long stitches split (pull compensation makes them longer still). */
const SPLIT_FROM_MM = 6.5;

async function satinFillFor(outline: PathNode[], way: number): Promise<SatinFill | null> {
  try {
    return await engine().call<SatinFill>("shape.satin_fill", { outline, way }, OPEN_TIMEOUT);
  } catch (err) {
    fail(err);
    return null;
  }
}

/** Change how a drawn shape is stitched. A closed shape (a fill or applique) set to Satin is filled
 *  with one satin that turns and changes width with the shape (as in Embrilliance); Shift+W turns
 *  its stitches another way. A satin fill set back to Fill gets its outline back. */
export async function convertObject(id: string, to: ObjectKind) {
  const o = currentLayout()?.items.find((it) => it.id === id) as ObjectItem | undefined;
  if (!o || o.kind === to) return;
  if (o.kind === "satin" && !isRibbon(o)) {
    const outline = columnOutline(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] });
    editObject(id, () =>
      to === "run"
        ? ({ ...o, kind: "run", geometry: { nodes: outline, closed: true }, params: defaultsFor("run") } as ObjectItem)
        : ({ ...o, kind: to, geometry: { outline }, params: defaultsFor(to) } as ObjectItem),
    );
    return;
  }
  // A closed shape set to Satin is filled with one satin column (as in Embrilliance): a fill, or a
  // line drawn all the way round (closed, or ending where it began). Add satin border (Shift+B)
  // still makes a satin outline round it.
  const loop = o.kind === "run" ? closedLoop(o.geometry.nodes, !!o.geometry.closed) : null;
  if (to === "satin" && (o.kind === "fill" || o.kind === "applique" || loop)) {
    if ((o.kind === "fill" || o.kind === "applique") && o.geometry.holes?.length) {
      return info("A satin can't go round holes, so this stays a fill. For a satin edge round it, use Add satin border (Shift+B).");
    }
    const outline = loop ?? (o.geometry as { outline: PathNode[] }).outline;
    const r = await satinFillFor(outline, 0);
    if (!r || !unchanged(id, o)) return;
    satinWays.set(id, 0);
    editObject(id, () => ({ ...o, kind: "satin", geometry: { rail_a: r.rail_a, rail_b: r.rail_b }, params: satinFillParams(r) }) as ObjectItem);
    return info(
      `Filled with one satin that follows the shape (widest stitch ${round2(r.widest_mm)} mm${r.widest_mm > SPLIT_FROM_MM ? ", split so it can't snag" : ""}). ` +
        `Shift+W or the purple dots turn the stitches another way; Add satin border (Shift+B) on the ${loop ? "line" : "fill"} edges it with satin instead.`,
    );
  }
  const line = o.kind === "run" || o.kind === "satin";
  const pts = line ? (o.geometry as { nodes: PathNode[] }).nodes : (o.geometry as { outline: PathNode[] }).outline;
  // A fill's outline is closed; a line or ribbon keeps whether it was.
  const closed = line ? !!(o.geometry as { closed?: boolean }).closed : true;
  const holes = o.kind === "fill" || o.kind === "applique" ? o.geometry.holes : undefined;
  const width = isRibbon(o) ? o.geometry.width_mm : useStore.getState().satinWidth;
  editObject(id, () =>
    to === "run"
      ? ({ ...o, kind: "run", geometry: { nodes: pts, ...(closed ? { closed: true } : {}) }, params: defaultsFor("run") } as ObjectItem)
      : to === "satin"
        ? ({ ...o, kind: "satin", geometry: { nodes: pts, width_mm: width, ...(closed ? { closed: true } : {}) }, params: defaultsFor("satin") } as ObjectItem)
        : ({ ...o, kind: to, geometry: { outline: pts, ...(holes ? { holes } : {}) }, params: defaultsFor(to) } as ObjectItem),
  );
}

const round2 = (v: number) => Math.round(v * 100) / 100;

/** A line's points as a closed outline, if it goes all the way round: closed, or ending within
 *  half a millimetre of where it began (the repeated last point is dropped). Null if it's open. */
export function closedLoop(nodes: PathNode[], closed: boolean): PathNode[] | null {
  if (nodes.length < 3) return null;
  if (closed) return nodes;
  const a = nodes[0];
  const b = nodes[nodes.length - 1];
  return Math.hypot(a[0] - b[0], a[1] - b[1]) <= 0.5 && nodes.length >= 4 ? nodes.slice(0, -1) : null;
}

/** Shift+W: turn a satin fill's stitches another way (it's split at other tips). */
export async function satinOtherWay() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId) as ObjectItem | undefined;
  if (!o || o.kind !== "satin" || isRibbon(o)) return info("Select a satin that fills a shape first.");
  const way = (satinWays.get(o.id) ?? 0) + 1;
  const r = await satinFillFor(columnOutline(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] }), way);
  if (!r || !unchanged(o.id, o)) return;
  satinWays.set(o.id, way % r.ways);
  void editObject(o.id, (it) => withSatinRails(it, r));
  info(`Way ${(way % r.ways) + 1} of ${r.ways} (widest stitch ${round2(r.widest_mm)} mm). Shift+W again for the next.`);
}

/** A satin column given new rails (another way, or tips moved): wide ones split their stitches; a
 *  start and end chosen on the old rails go, since the new tips are where it starts and ends. */
function withSatinRails(it: ObjectItem, r: SatinFill): ObjectItem {
  const { start_mm: _s, end_mm: _e, ...params } = it.params as Record<string, unknown>;
  void _s;
  void _e;
  const split = r.widest_mm > SPLIT_FROM_MM && !(it.params as { split_mm?: number }).split_mm ? { split_mm: 7 } : {};
  return { ...it, geometry: { rail_a: r.rail_a, rail_b: r.rail_b }, params: { ...params, ...split } } as ObjectItem;
}

const isSatinFill = () => {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  return !!o && isObject(o) && o.kind === "satin" && !isRibbon(o);
};

// ---------------------------------------------------------------- colors and stitches

/** Recolor the displayed color block `block` (all of its sources). null puts the file's thread back. */
export function recolorBlock(block: number, thread: Thread | null) {
  const l = currentLayout();
  const design = useStore.getState().design;
  const sources = design?.blocks[block]?.sources;
  if (l && sources?.length) void commit(recolorRuns(l, sources, thread, design));
}

/** Recolor some of the design's color stops (an item's own color, by item and block): one undo step. */
export function recolorSources(sources: { item: number; block: number }[], thread: Thread | null) {
  const l = currentLayout();
  if (l && sources.length) void commit(recolorRuns(l, sources, thread, useStore.getState().design));
}

/** One thread for several things at once (everything selected): drawn shapes and lettering take
 *  it as their thread; a stitch file with one color is recolored. One undo step. Returns how many
 *  multicolor stitch files were left as they are. */
export function setItemsThread(ids: string[], thread: Thread): number {
  let l = currentLayout();
  const design = useStore.getState().design;
  if (!l) return 0;
  let skipped = 0;
  const fileSources: { item: number; block: number }[] = [];
  l.items.forEach((it, i) => {
    if (!ids.includes(it.id) || isObject(it) || isText(it)) return;
    const srcs = (design?.blocks ?? []).flatMap((b) => (b.sources ?? []).filter((src) => src.item === i));
    if (new Set(srcs.map((src) => src.block)).size === 1) fileSources.push(...srcs);
    else skipped++;
  });
  l = { ...l, items: l.items.map((it) => (ids.includes(it.id) && (isObject(it) || isText(it)) ? ({ ...it, thread, threads: otherColors(it) } as LayoutItem) : it)) };
  if (fileSources.length) l = recolor(l, fileSources, thread);
  useStore.getState().setDrawThread(thread);
  void commit(l);
  if (skipped) info(`${skipped === 1 ? "A stitch file with several colors keeps its" : `${skipped} stitch files with several colors keep their`} colors: change them one by one in Order & colors.`);
  return skipped;
}

/** Recolor several blocks at once (one undo step). */
export function recolorBlocks(changes: { block: number; thread: Thread | null }[]) {
  let l = currentLayout();
  const design = useStore.getState().design;
  const blocks = design?.blocks;
  if (!l || !blocks) return;
  for (const c of changes) {
    const sources = blocks[c.block]?.sources;
    if (sources?.length) l = recolorRuns(l, sources, c.thread, design);
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

// ---------------------------------------------------------------- Embrilliance-style create, view and clipboard keys

/** D: switch between Select and the drawing tool used last. */
async function toggleCreate() {
  const s = useStore.getState();
  if (s.tool === "select") await tool(s.lastTool)();
  else await tool("select")();
}

/** Q / W: draw another shape of the same kind as the last object (or the one before it). */
function drawLike(back: 0 | 1) {
  const items = (currentLayout()?.items ?? []).filter(isObject);
  const o = items[items.length - 1 - back];
  if (!o) return info(back ? "There's no earlier shape to copy the kind of." : "Draw a shape first.");
  void tool(o.kind === "applique" ? "fill" : o.kind)();
}

/** O: draw a hole in the selected fill. */
function startHole() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || (o.kind !== "fill" && o.kind !== "applique")) return info("Select a fill first, then press O to draw a hole in it.");
  const back = s.tool;
  s.setTool("fill");
  s.setPen({ kind: "fill", a: [], b: [], holeFor: o.id, holeBack: back });
  info("Click around the hole; Enter or right-click finishes it.");
}

/** I: draw a line across a fill to set its stitch angle (Embrilliance's inclination line). */
function startAngle() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || o.kind !== "fill") return info("Select a fill first, then press I and draw a line the stitches should follow.");
  feat.endOtherModes("angle");
  s.setAngleFor({ id: o.id, points: [] });
}

/** Called by the canvas when the inclination line is done. */
export function finishAngle(id: string, a: [number, number], b: [number, number]) {
  const add = !!useStore.getState().angleFor?.add;
  useStore.getState().setAngleFor(null);
  // A turning fill's lines (feat/angleLines.ts) take it: another line, or the first of several.
  if (finishAngleLine(id, a, b, add)) return;
  const deg = (((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180) / Math.PI) % 180 + 180) % 180;
  setObjectParams(id, { angle_deg: Math.round(deg) });
}

/** M: the measuring tool. Click two points to see the distance; press M or Esc to put it away. */
function toggleRuler() {
  const s = useStore.getState();
  if (s.ruler) return s.setRuler(null);
  feat.endOtherModes("ruler");
  if (s.tool !== "select") void tool("select")();
  s.setRuler([]);
}

/** S: zoom to the selection. */
function zoomSelected() {
  const s = useStore.getState();
  const l = currentLayout();
  const img = s.history.present?.images.find((im) => im.id === s.selectedId);
  if (img) return s.requestZoom("box", { box: [img.x - img.width_mm / 2, img.y - img.height_mm / 2, img.x + img.width_mm / 2, img.y + img.height_mm / 2] });
  const ids = selectionIds();
  if (ids.length > 1) {
    const box = selectionGeometry(ids).box;
    if (box) return s.requestZoom("box", { box });
  }
  const id = targetId();
  const i = l && id ? l.items.findIndex((it) => it.id === id) : -1;
  const b = i >= 0 ? s.design?.items?.[i]?.bounds_mm : null;
  if (b) s.requestZoom("box", { box: b });
}

/** 0: zoom to the hoop. */
function zoomHoop() {
  const h = selectHoop(useStore.getState());
  if (h) useStore.getState().requestZoom("box", { box: [-h.width_mm / 2, -h.height_mm / 2, h.width_mm / 2, h.height_mm / 2] });
}

let clipboard: LayoutItem[] = [];

/** Ctrl+C / Ctrl+X: copy (or cut) the selected design or shape. */
function copySelected(cut: boolean) {
  const l = currentLayout();
  const ids = selectionIds();
  const items = l?.items.filter((x) => ids.includes(x.id)) ?? [];
  if (!items.length) return;
  clipboard = items.map((it) => structuredClone(it));
  // What was copied is what goes (with nothing selected, that's the design's only item).
  if (cut) removeItems(items.map((it) => it.id));
  else info("Copied. Ctrl+V pastes it.");
}

/** Ctrl+V: paste a copy, a little down and to the right of where it was. */
function pasteClipboard() {
  const l = currentLayout();
  if (!l || !clipboard.length) return;
  let out = l;
  const pasted: string[] = [];
  // Pasted copies keep their own group, apart from the originals.
  const group = clipboard.some((it) => it.group) ? `g${Date.now().toString(36)}` : undefined;
  for (const src of clipboard) {
    const copy = { ...structuredClone(src), id: newId(), group: src.group ? group : undefined } as LayoutItem;
    out = { ...out, items: [...out.items, copy] };
    out = moveBy(out, copy.id, ADD_OFFSET_MM, ADD_OFFSET_MM);
    pasted.push(copy.id);
  }
  void commit(out).then((ok) => ok && useStore.getState().setSelection(pasted[0], pasted.slice(1)));
}

/** Step the stitch-out speed up or down the speed scale. */
function changeSpeed(dir: -1 | 1) {
  const s = useStore.getState();
  const i = PLAYER_SPEEDS.findIndex((v) => v >= s.speed);
  const next = PLAYER_SPEEDS[Math.min(PLAYER_SPEEDS.length - 1, Math.max(0, (i < 0 ? PLAYER_SPEEDS.length - 1 : i) + dir))];
  s.setSpeed(next);
  info(`Stitch-out speed: ${next === MACHINE_SPEED ? "machine speed" : `${next} stitches a second`}.`);
}

/** Pin a design or shape in place (it can't be dragged; its settings still change). */
export function setItemPinned(id: string, pinned: boolean) {
  const l = currentLayout();
  if (!l) return;
  void commit({ ...l, items: l.items.map((it) => (it.id === id ? ({ ...it, locked: pinned || undefined } as LayoutItem) : it)) });
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
  if (!l) return;
  // Remember the hoop, so the box comes in closer rather than making the design too big for it.
  const h = selectHoop(useStore.getState());
  void commit({ ...l, basting: { ...l.basting, enabled: !l.basting.enabled, ...(h ? { fit_mm: [h.width_mm, h.height_mm] as [number, number] } : {}) } });
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
    await loadTraceModel();
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
const guessing = () => !!useStore.getState().autoTrace?.guesses.length && !useStore.getState().autoTrace?.busy;
const guessingFill = () => guessing() && useStore.getState().autoTrace!.guesses[useStore.getState().autoTrace!.index]?.kind === "fill";
const hasTarget = () => canEdit() && !drawing() && targetId() !== null;
const hasSelection = () => engineReady() && useStore.getState().selectedId !== null;
const noSelection = () => hasDesign() && useStore.getState().selectedId === null;
const drawing = () => useStore.getState().pen !== null;
const canUndo = () => drawing() || (engineReady() && latestHistory().past.length > 0);
const canRedo = () => !drawing() && engineReady() && latestHistory().future.length > 0;
// Letter keys don't switch tools mid-shape (A sits by Tab and Shift); the tool buttons still do.
const notDrawing = () => engineReady() && !drawing();
const nudge = (dx: number, dy: number) => () => {
  if (nudgeLetter(dx, dy)) return; // a letter picked in single-letter mode moves instead
  const s = useStore.getState();
  const img = currentDoc()?.images.find((im) => im.id === s.selectedId);
  if (img) {
    if (img.locked) return info(PINNED_STAYS_PUT);
    setPicture(img.id, { x: img.x + dx, y: img.y + dy });
    return;
  }
  // Tapping or holding an arrow key is one move: one undo step, renders as fast as the engine goes.
  editSelection({ move: [dx, dy] }, continueGesture(`nudge:${[s.selectedId, ...s.extraIds].join(",")}`));
};
const tool = (t: Tool) => async () => {
  // Switching tools mid-shape keeps the shape if it's complete enough, rather than losing it.
  if (useStore.getState().pen) {
    if (penReady()) await penFinish();
    else penCancel();
  }
  // No design yet: start one first (starting one goes back to Select), then pick the tool.
  if (!hasDoc()) await replaceDoc(freshDoc(), null);
  useStore.getState().setTool(t);
};

const hasJunction = () => (useStore.getState().ghost?.alternatives.length ?? 0) > 0;

// Order matters: the first enabled command for a key wins (drawing keys first, then a selection
// is nudged by the arrows, otherwise they step the player).
export const CORE_COMMANDS: Command[] = [
  // While drawing, Tab always belongs to Trace Assist (never moves keyboard focus).
  // Stitch editing: Delete removes the selected stitches (before the other Delete commands).
  {
    id: "stitch.deleteSelected",
    title: "Delete the selected stitches",
    shortcut: "Delete",
    run: () => feat.deleteSelectedStitches(),
    // On whenever stitches are being edited (doing nothing if none is selected), so the key never
    // falls through to "delete the design".
    enabled: () => !!useStore.getState().stitchEdit,
  },
  {
    id: "stitch.deleteSelectedAlt",
    title: "Delete the selected stitches",
    shortcut: "Backspace",
    run: () => feat.deleteSelectedStitches(),
    // On whenever stitches are being edited (doing nothing if none is selected), so the key never
    // falls through to "delete the design".
    enabled: () => !!useStore.getState().stitchEdit,
  },
  {
    id: "autotrace.allAccept",
    title: "Add every shape found in the picture",
    shortcut: "Enter",
    run: () => void feat.acceptWholePicture(),
    enabled: () => { const a = useStore.getState().autoAll; return !!a && !a.busy && a.shapes.length > 0; },
  },
  { id: "autotrace.next", title: "Auto-trace: next guess", shortcut: "Tab", run: () => nextGuess(1), enabled: guessing },
  { id: "autotrace.prev", title: "Auto-trace: previous guess", shortcut: "Shift+Tab", run: () => nextGuess(-1), enabled: guessing },
  { id: "autotrace.accept", title: "Auto-trace: use this guess", shortcut: "Enter", run: () => void acceptGuess(), enabled: guessing },
  { id: "autotrace.fillBorder", title: "Auto-trace: use as a fill with a satin border", shortcut: "Shift+Enter", run: () => void acceptGuess("fillAndBorder"), enabled: guessingFill },
  { id: "autotrace.closer", title: "Auto-trace: points closer together", shortcut: "[", run: () => setSpacing(useStore.getState().autoSpacing - 0.5), enabled: () => useStore.getState().tool === "autotrace" },
  { id: "autotrace.further", title: "Auto-trace: points further apart", shortcut: "]", run: () => setSpacing(useStore.getState().autoSpacing + 0.5), enabled: () => useStore.getState().tool === "autotrace" },
  { id: "autotrace.spreadLess", title: "Auto-trace: spread less (stop at fainter changes)", shortcut: "Alt+[", run: () => setSpread(useStore.getState().autoSpread - 1), enabled: () => useStore.getState().tool === "autotrace" },
  { id: "autotrace.spreadMore", title: "Auto-trace: spread more (join similar shades)", shortcut: "Alt+]", run: () => setSpread(useStore.getState().autoSpread + 1), enabled: () => useStore.getState().tool === "autotrace" },
  // Drawing a satin along a shape's edge: Tab fits it to the edge (before Trace Assist's Tab).
  { id: "satin.fitEdge", title: "Fit the satin along the edge (again: the next way)", shortcut: "Tab", run: () => nextFit(1), enabled: canFit },
  { id: "satin.fitEdgeBack", title: "Fit the satin along the edge: the way before", shortcut: "Shift+Tab", run: () => nextFit(-1), enabled: () => !!useStore.getState().edgeFit?.original },
  { id: "trace.accept", title: "Accept the suggested point", shortcut: "Tab", run: () => queueAccept(), enabled: drawing },
  { id: "trace.acceptMany", title: "Keep accepting points", shortcut: "Shift+Tab", run: queueAcceptMany, enabled: drawing },
  { id: "trace.pick1", title: "Take branch 1", shortcut: "1", run: () => queueAccept(1), enabled: hasJunction },
  { id: "trace.pick2", title: "Take branch 2", shortcut: "2", run: () => queueAccept(2), enabled: hasJunction },
  { id: "trace.shorter", title: "Shorter steps", shortcut: "[", run: () => setStep(useStore.getState().traceStep - 0.5), enabled: drawing },
  { id: "trace.longer", title: "Longer steps", shortcut: "]", run: () => setStep(useStore.getState().traceStep + 0.5), enabled: drawing },
  { id: "pen.toggleKind", title: "Switch the last point: curve, straight, sharp corner", shortcut: "C", run: toggleLastPoint, enabled: drawing },
  {
    id: "trace.toggle",
    title: "Trace Assist (suggest the next point)",
    shortcut: "Mod+Shift+A",
    run: () => useStore.getState().toggleTraceAssist(),
  },
  // While drawing, the arrow keys move the view 1 cm (as in Embrilliance), so you can keep going off-screen.
  ...(
    [
      ["Left", -10, 0],
      ["Right", 10, 0],
      ["Up", 0, -10],
      ["Down", 0, 10],
    ] as const
  ).map(([k, dx, dy]) => ({
    id: `view.pan${k}`,
    title: `Move the view ${k.toLowerCase()} 1 cm`,
    shortcut: `Arrow${k}`,
    run: () => useStore.getState().requestZoom("pan", { pan: [dx, dy] }),
    enabled: () => drawing() || (useStore.getState().tool !== "select" && !hasSelection()),
  })),
  { id: "pen.finish", title: "Finish the shape", shortcut: "Enter", run: () => void penFinish(), enabled: drawing },
  { id: "pen.undoPoint", title: "Remove the last point", shortcut: "Backspace", run: penUndoPoint, enabled: drawing },
  { id: "pen.cancel", title: "Cancel the shape", shortcut: "Escape", run: penCancel, enabled: drawing },
  // Esc lets go of one thing per press (see escape.ts): these follow drawing, in this order.
  { id: "ruler.cancel", title: "Put the measuring tool away", shortcut: "Escape", run: () => useStore.getState().setRuler(null), enabled: () => useStore.getState().ruler !== null },
  { id: "angle.cancel", title: "Stop setting the angle", shortcut: "Escape", run: () => useStore.getState().setAngleFor(null), enabled: () => useStore.getState().angleFor !== null },
  {
    id: "measure.cancel",
    title: "Stop measuring",
    shortcut: "Escape",
    run: () => useStore.getState().setMeasure(null),
    enabled: () => useStore.getState().measure !== null,
  },

  { id: "app.settings", title: "Settings…", shortcut: "Mod+,", run: () => useStore.getState().setSettingsOpen(true) },
  { id: "app.help", title: "Help", shortcut: "F1", run: () => useStore.getState().setHelpOpen(true) },
  { id: "ai.advisor", title: "Stitch Advisor (AI)…", shortcut: "Mod+Shift+I", run: () => void runAdvisor(), enabled: () => canAdvise() },
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
  { id: "tool.satin", title: "Draw a satin ribbon", shortcut: "C", run: tool("satin"), enabled: notDrawing },
  { id: "tool.autotrace", title: "Auto-trace a shape in a picture", shortcut: "Shift+A", run: tool("autotrace"), enabled: notDrawing },
  {
    id: "autotrace.all",
    title: "Auto-digitize the whole picture…",
    shortcut: "Alt+A",
    run: () => void feat.digitizeWholePicture(),
    enabled: () => notDrawing() && !!useStore.getState().history.present?.images.length,
  },
  { id: "tool.knife", title: "Knife: cut the selected shape in two", shortcut: "Shift+K", run: () => feat.startKnife(), enabled: () => hasTarget() && targetIs((o) => o.kind === "fill" || o.kind === "applique" || o.kind === "run" || isRibbon(o)) },
  { id: "object.merge", title: "Merge the selected fills into one", shortcut: "Mod+M", run: () => void feat.mergeSelected(), enabled: () => hasTarget() && useStore.getState().extraIds.length > 0 },
  { id: "object.offset", title: "Outline / offset around the selection…", shortcut: "Mod+Shift+K", run: () => useStore.getState().setDialog("offset"), enabled: () => hasTarget() },
  { id: "layout.travelUnder", title: "Hide moves under later stitching (fewer jumps & trims)", shortcut: "Mod+Alt+T", run: () => feat.toggleTravelUnder(), enabled: canEdit },
  { id: "layout.shortestOrder", title: "Sew in the shortest order", shortcut: "Mod+Alt+O", run: () => void feat.shortestOrder(), enabled: canEdit },
  { id: "layout.optimizeJumps", title: "Optimize jumps (where each piece starts and ends)", shortcut: "Mod+Alt+J", run: () => void feat.optimizeJumps(), enabled: canEdit },
  { id: "file.browse", title: "Browse designs…", shortcut: "Mod+Alt+B", run: () => useStore.getState().setDialog("browse"), enabled: engineReady },
  { id: "edit.stitches", title: "Edit stitches of the selected design", shortcut: "Mod+Alt+E", run: () => feat.startStitchEdit(), enabled: () => hasTarget() },
  { id: "text.onLine", title: "Put the text on the selected line", shortcut: "Mod+Alt+L", run: () => void feat.textOnLine(), enabled: () => hasTarget() && useStore.getState().extraIds.length > 0 },
  { id: "text.names", title: "One file per name…", shortcut: "Mod+Alt+N", run: () => useStore.getState().setDialog("names"), enabled: () => hasTarget() && currentLayout()?.items.find((it) => it.id === targetId())?.kind === "text" },
  { id: "view.rulers", title: "Rulers (drag from them for guides)", shortcut: "Mod+R", run: () => useStore.getState().setShowRulers(!useStore.getState().showRulers), enabled: () => true },
  { id: "view.clearGuides", title: "Remove all guides", shortcut: "Mod+Alt+G", run: () => feat.clearGuides(), enabled: () => feat.guidesOf().length > 0 },
  { id: "object.border", title: "Add a satin border", shortcut: "Shift+B", run: () => void addSatinBorder(), enabled: () => canEdit() && !drawing() && targetIs((o) => o.kind === "fill" || o.kind === "applique" || (o.kind === "run" && !!o.geometry.closed)) },
  { id: "tool.fill", title: "Draw a fill shape", shortcut: "F", run: tool("fill"), enabled: notDrawing },
  { id: "tool.text", title: "Add text (click where it goes)", shortcut: "Shift+T", run: tool("text"), enabled: notDrawing },
  // Embrilliance's create keys.
  { id: "create.toggle", title: "Switch between Create and Select", shortcut: "D", run: () => void toggleCreate(), enabled: notDrawing },
  { id: "create.again", title: "Draw again with the last tool", shortcut: "X", run: () => void tool(useStore.getState().lastTool)(), enabled: notDrawing },
  { id: "create.line", title: "Draw a line (running stitch)", shortcut: "Shift+X", run: tool("run"), enabled: notDrawing },
  { id: "create.same", title: "Draw a shape like the last one", shortcut: "Q", run: () => drawLike(0), enabled: notDrawing },
  { id: "create.prior", title: "Draw a shape like the one before the last", shortcut: "W", run: () => drawLike(1), enabled: notDrawing },
  { id: "object.hole", title: "Cut a hole in the selected fill (draw round it)", shortcut: "O", run: startHole, enabled: () => notDrawing() && targetIs((o) => o.kind === "fill" || o.kind === "applique") },
  { id: "object.cutOut", title: "Cut the shapes on top out of the fill (select the fill and them)", shortcut: "Shift+O", run: () => void feat.cutOutSelected(), enabled: () => notDrawing() && useStore.getState().extraIds.length > 0 && selectionIds().some((id) => { const it = currentLayout()?.items.find((x) => x.id === id); return !!it && (it.kind === "fill" || it.kind === "applique"); }) },
  { id: "satin.otherWay", title: "Turn a satin fill's stitches another way", shortcut: "Shift+W", run: () => void satinOtherWay(), enabled: () => notDrawing() && isSatinFill() },
  { id: "object.angle", title: "Set the stitch angle with a line", shortcut: "I", run: startAngle, enabled: () => notDrawing() && targetIs((o) => o.kind === "fill") },
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
      return !!it && isObject(it) && !it.locked && !drawing();
    },
  },
  {
    id: "tool.escape",
    title: "Back to Select",
    shortcut: "Escape",
    run: () => useStore.getState().setTool("select"),
    enabled: () => useStore.getState().tool !== "select",
  },

  { id: "arrange.rotateCw", title: "Rotate 90° right", shortcut: "R", run: () => editSelection({ rotate: 90 }), enabled: hasTarget },
  { id: "arrange.rotateCcw", title: "Rotate 90° left", shortcut: "Shift+R", run: () => editSelection({ rotate: -90 }), enabled: hasTarget },
  { id: "edit.selectAll", title: "Select everything", shortcut: "Mod+A", run: selectAll, enabled: () => hasDoc() && !drawing() },
  { id: "arrange.group", title: "Group (select and move together)", shortcut: "Mod+G", run: () => groupSelection(true), enabled: hasTarget },
  { id: "arrange.ungroup", title: "Ungroup", shortcut: "Mod+U", run: () => groupSelection(false), enabled: hasTarget },
  { id: "arrange.mirrorX", title: "Mirror left–right", shortcut: "Alt+H", run: () => editSelection({ mirror: "x" }), enabled: hasTarget },
  { id: "arrange.mirrorY", title: "Mirror top–bottom", shortcut: "Alt+V", run: () => editSelection({ mirror: "y" }), enabled: hasTarget },
  { id: "arrange.duplicate", title: "Duplicate", shortcut: "Mod+D", run: duplicateSelected, enabled: hasTarget },
  {
    id: "node.delete",
    title: "Remove the selected point",
    shortcut: "Delete",
    run: deleteSelectedNode,
    enabled: () => useStore.getState().selectedNode !== null,
  },
  // Backspace too: with a point selected it removes the point, never the whole shape.
  { id: "node.deleteAlt", title: "Remove the selected point", shortcut: "Backspace", run: deleteSelectedNode, enabled: () => useStore.getState().selectedNode !== null },
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
  {
    // Pin (or unpin) what's selected: a pinned shape can't be dragged; a pinned picture lets clicks through.
    id: "arrange.pin",
    title: "Pin in place / unpin",
    shortcut: "Mod+L",
    run: () => {
      const st = useStore.getState();
      const id = st.selectedId;
      if (!id) return;
      const img = selectImages(st).find((im) => im.id === id);
      if (img) return setPicture(id, { locked: !img.locked });
      const it = selectLayout(st)?.items.find((x) => x.id === id);
      if (it) setItemPinned(id, !it.locked);
    },
    enabled: hasSelection,
  },
  {
    id: "arrange.rename",
    title: "Rename",
    shortcut: "F2",
    run: () => window.dispatchEvent(new CustomEvent("ludd:rename", { detail: useStore.getState().selectedId })),
    enabled: () => hasSelection() && !useStore.getState().extraIds.length,
  },
  // Sewing order, from the keyboard or a right-click (the list's arrows and grip do the same).
  { id: "arrange.earlier", title: "Sew earlier", shortcut: "Mod+[", run: () => sewAt(-1), enabled: () => canMoveInOrder(-1) },
  { id: "arrange.later", title: "Sew later", shortcut: "Mod+]", run: () => sewAt(1), enabled: () => canMoveInOrder(1) },
  { id: "arrange.first", title: "Sew first", shortcut: "Mod+Shift+[", run: () => sewAt("first"), enabled: () => canMoveInOrder(-1) },
  { id: "arrange.last", title: "Sew last", shortcut: "Mod+Shift+]", run: () => sewAt("last"), enabled: () => canMoveInOrder(1) },
  { id: "arrange.centre", title: "Center in the hoop", shortcut: "Mod+Shift+M", run: centreSelection, enabled: () => hasTarget() && !!selectionGeometry(selectionIds()).box },
  // With several selected, the thread chosen goes to all of them.
  { id: "object.thread", title: "Change thread…", shortcut: "Alt+T", run: () => useContextMenu.setState({ threadFor: selectionIds().find(recolorable) ?? selectionIds()[0] ?? null }), enabled: () => hasTarget() && (selectionIds().some(recolorable) || (selectionIds().length > 1 && selectionIds().some(singleColorFile))) },
  { id: "text.toShapes", title: "Break the lettering into shapes", shortcut: "Mod+Alt+X", run: () => void textToShapes(), enabled: () => hasTarget() && currentLayout()?.items.find((it) => it.id === targetId())?.kind === "text" },
  {
    id: "text.resetEnds",
    title: "Reset the letters' starts and ends",
    shortcut: "Mod+Alt+R",
    run: () => {
      const id = targetId();
      if (id) setText(id, { letters: undefined });
    },
    enabled: () => {
      const it = currentLayout()?.items.find((x) => x.id === targetId());
      return hasTarget() && !!it && isText(it) && Object.keys(it.letters ?? {}).length > 0;
    },
  },
  { id: "text.edit", title: "Change the words", shortcut: "Mod+Alt+W", run: editTextWords, enabled: () => hasTarget() && currentLayout()?.items.find((it) => it.id === targetId())?.kind === "text" },
  { id: "arrange.repeat", title: "Repeat, carousel or mirror…", shortcut: "Mod+Shift+D", run: () => useStore.getState().setRepeatOpen(true), enabled: hasTarget },
  { id: "applique.svg", title: "Save applique cut file (SVG)…", shortcut: "Mod+Shift+U", run: () => void saveAppliqueSvg(), enabled: hasApplique },

  { id: "file.newAlt", title: "New design", shortcut: "Shift+D", run: () => void newProject(), enabled: engineReady },
  { id: "view.density", title: "Density map", shortcut: "Alt+D", run: () => useStore.getState().toggleDensity(), enabled: hasDesign },
  { id: "view.fit", title: "Zoom to all", shortcut: "A", run: () => useStore.getState().requestFit(), enabled: hasDoc },
  { id: "view.jumps", title: "Show trims, jumps and stops", shortcut: "J", run: () => useStore.getState().toggleJumps() },
  { id: "view.realistic", title: "Realistic thread (3D)", shortcut: "T", run: () => useStore.getState().toggleRealistic() },
  { id: "view.hoop", title: "Show hoop", shortcut: "H", run: () => useStore.getState().toggleHoop() },
  { id: "view.grid", title: "Show grid", shortcut: "G", run: () => useStore.getState().toggleGrid() },
  { id: "view.units", title: "Measure in millimeters", shortcut: "U", run: () => useStore.getState().toggleUnits() },
  { id: "view.zoomIn", title: "Zoom in", shortcut: "=", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomInPlus", title: "Zoom in", shortcut: "Shift++", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomInPad", title: "Zoom in", shortcut: "+", run: () => useStore.getState().requestZoom("in"), enabled: hasDoc },
  { id: "view.zoomOut", title: "Zoom out", shortcut: "-", run: () => useStore.getState().requestZoom("out"), enabled: hasDoc },
  { id: "view.zoomSelected", title: "Zoom to the selection", shortcut: "S", run: zoomSelected, enabled: () => hasDesign() && (targetId() !== null || hasSelection()) },
  { id: "view.zoomHoop", title: "Zoom to the hoop", shortcut: "0", run: zoomHoop, enabled: hasDoc },
  ...[2, 3, 4, 5, 6, 7, 8, 9].map((k) => ({
    id: `view.zoom${k}`,
    title: `Zoom to ${k}× real size`,
    shortcut: String(k),
    run: () => useStore.getState().requestZoom("scale", { factor: k }),
    enabled: hasDoc,
  })),
  { id: "view.measure", title: "Measure (click two points)", shortcut: "M", run: toggleRuler, enabled: () => hasDoc() && !drawing() },
  { id: "view.points", title: "Show stitch points", shortcut: "P", run: () => useStore.getState().toggleView("showPoints"), enabled: hasDesign },
  { id: "view.stitches", title: "Show stitches", shortcut: "N", run: () => useStore.getState().toggleView("showStitches"), enabled: hasDoc },
  { id: "view.seeThrough", title: "See-through stitches (to work over a picture)", shortcut: "Shift+N", run: () => useStore.getState().toggleSeeThrough(), enabled: hasDoc },
  { id: "view.pictures", title: "Show pictures", shortcut: "B", run: () => useStore.getState().toggleView("showPictures"), enabled: hasDoc },
  { id: "view.crosshair", title: "Crosshairs", shortcut: "E", run: () => useStore.getState().toggleView("crosshair"), enabled: hasDoc },
  { id: "view.snap", title: "Snap new points to the grid", shortcut: "Shift+G", run: () => useStore.getState().toggleSnapGrid(), enabled: hasDoc },
  { id: "edit.copy", title: "Copy", shortcut: "Mod+C", run: () => copySelected(false), enabled: hasTarget },
  { id: "edit.cut", title: "Cut", shortcut: "Mod+X", run: () => copySelected(true), enabled: hasTarget },
  { id: "edit.paste", title: "Paste", shortcut: "Mod+V", run: pasteClipboard, enabled: () => canEdit() && clipboard.length > 0 },
  { id: "arrange.leftFine", title: "Nudge left 0.1 mm", shortcut: "Mod+ArrowLeft", run: nudge(-0.1, 0), enabled: hasSelection },
  { id: "arrange.rightFine", title: "Nudge right 0.1 mm", shortcut: "Mod+ArrowRight", run: nudge(0.1, 0), enabled: hasSelection },
  { id: "arrange.upFine", title: "Nudge up 0.1 mm", shortcut: "Mod+ArrowUp", run: nudge(0, -0.1), enabled: hasSelection },
  { id: "arrange.downFine", title: "Nudge down 0.1 mm", shortcut: "Mod+ArrowDown", run: nudge(0, 0.1), enabled: hasSelection },
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
    title: "Play / pause (tap Space; hold Space and drag to move around)",
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
  {
    id: "player.slower",
    title: "Stitch out slower",
    shortcut: ",",
    run: () => changeSpeed(-1),
    enabled: hasDesign,
  },
  { id: "player.faster", title: "Stitch out faster", shortcut: ".", run: () => changeSpeed(1), enabled: hasDesign },
  { id: "player.machineSpeed", title: "Stitch out at machine speed", shortcut: "Shift+,", run: () => useStore.getState().setSpeed(MACHINE_SPEED), enabled: hasDesign },
  { id: "player.start", title: "Go to start", shortcut: "Home", run: () => step(-Infinity), enabled: hasDesign },
  { id: "player.end", title: "Show whole design", shortcut: "End", run: () => step(Infinity), enabled: hasDesign },
  {
    id: "player.fasterAlt",
    title: "Faster playback",
    shortcut: "]",
    run: () => {
      const s = useStore.getState();
      s.setSpeed(PLAYER_SPEEDS.find((v) => v > s.speed) ?? s.speed);
    },
  },
  {
    id: "player.slowerAlt",
    title: "Slower playback",
    shortcut: "[",
    run: () => {
      const s = useStore.getState();
      s.setSpeed([...PLAYER_SPEEDS].reverse().find((v) => v < s.speed) ?? s.speed);
    },
  },
];
registerCommands(CORE_COMMANDS);
export { COMMANDS } from "./commands";

export const command = (id: string) => COMMANDS.find((c) => c.id === id)!;

export { isTauri, itemLabel };
