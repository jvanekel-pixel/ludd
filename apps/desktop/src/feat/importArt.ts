/**
 * Artwork import (P7-D1): an SVG, DXF or PDF drawing as shapes, previewed before anything is added.
 * The engine reads the file (art.preview) and answers with the shapes it would become; Add makes
 * ordinary shapes with your settings for each kind, grouped and selected, in one undo step. Cancel
 * adds nothing. The dialog is components/ImportArtDialog.tsx, registered as "importArt"; the
 * outlines on the hoop are canvas/importOverlay.ts.
 */
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { create } from "zustand";
import { addTraced, commit, currentLayout, defaultsFor, engine, fail, info, matchThreads } from "../actions";
import { showImportOutlines, type ImportOutline } from "../canvas/importOverlay";
import { addObject } from "../design/layout";
import type { ChartSummary, Doc, FillGeometry, ObjectItem, RunGeometry, SatinRibbon, Thread, Warning } from "../design/types";
import { loadPrefs, savePrefs } from "../prefs";
import { selectHoop, useStore } from "../store";

export type ArtShape = { color: string; name: string; background?: boolean } & (
  | { kind: "fill"; geometry: FillGeometry }
  | { kind: "run"; geometry: RunGeometry }
  | { kind: "satin"; geometry: SatinRibbon }
);

export type ArtPreview = {
  size_mm: [number, number];
  /** Set when the file doesn't say its real size (or units). */
  scale_note: string | null;
  shapes: ArtShape[];
  skipped: { what: string; count: number; message: string }[];
  warnings: Warning[];
  pages: number;
};

export type StrokeMode = "auto" | "lines" | "satins";

/** What art.preview is asked with. `width_mm` null: the drawing's real size. `keep_background`:
 *  the background rectangle is wanted too (and counts toward the size). */
export type ArtOptions = { width_mm: number | null; strokes: StrokeMode; closed_as_fills: boolean; page: number; keep_background: boolean };

/** Files that are artwork: dropped on the window, they open the import dialog. (.svgz too, so the
 *  engine can say how to save it instead.) */
export const ART_FILE = /\.(svg|svgz|dxf|pdf)$/i;

/** How long the app waits for a preview. The engine gives up on a drawing itself after 60 s
 *  (artimport TIME_LIMIT_S, counted from when the request comes in), well before this. */
export const PREVIEW_MS = 120_000;
const BLACK: Thread = { color: "#000000", name: "Black", brand: "", catalog: "" };

/** Said if the wait ends anyway (a stuck or very busy computer), instead of the engine client's
 *  "Engine did not answer art.preview within 120000 ms". */
export const NO_ANSWER =
  "LUDD got no answer about this drawing in time. Close this window and import it again. If it happens again, simplify the drawing in your drawing program (fewer shapes and points) and save it again.";

function previewError(err: unknown): string {
  const message = err instanceof Error ? err.message : String(err);
  return message.startsWith("Engine did not answer") ? NO_ANSWER : message;
}

type State = {
  /** The file being imported (null: no import going on). */
  path: string | null;
  options: ArtOptions;
  /** The newest answer, and the options it was asked with. */
  preview: ArtPreview | null;
  asked: string;
  busy: boolean;
  error: string | null;
  /** Pages in the file, as last heard (the page list stays while a page is read). */
  pages: number;
  /** Colors unticked. */
  off: string[];
  /** "Match colors to my threads". */
  match: boolean;
  adding: boolean;
};

const strokeMode = (v: string | undefined): StrokeMode => (v === "lines" || v === "satins" ? v : "auto");

const startOptions = (): ArtOptions => ({
  width_mm: null,
  strokes: strokeMode(loadPrefs().importArt?.strokes),
  closed_as_fills: false,
  page: 0,
  keep_background: false,
});

export const useImportArt = create<State>(() => ({
  path: null,
  options: startOptions(),
  preview: null,
  asked: "",
  busy: false,
  error: null,
  pages: 1,
  off: [],
  match: true,
  adding: false,
}));

/** My threads, once it has spools (what colors can be matched to). */
export const mySpools = (charts: readonly ChartSummary[]): string | null => charts.find((c) => c.mine && c.count > 0)?.id ?? null;

export const optionsKey = (o: ArtOptions): string => JSON.stringify(o);

/** The shapes Add would add: the ticked colors', and the background only if it's ticked. */
export function chosenShapes(s: Pick<State, "preview" | "off" | "options">): ArtShape[] {
  return (s.preview?.shapes ?? []).filter((sh) => (sh.background ? s.options.keep_background : !s.off.includes(sh.color)));
}

/** Add waits for the preview of what's asked for now, with something ticked. */
export function canAdd(s: State): boolean {
  return !!s.path && !!s.preview && !s.busy && !s.adding && s.asked === optionsKey(s.options) && chosenShapes(s).length > 0;
}

/** The drawing's colors, in the order they're first sewn, with how many shapes each has (the
 *  background has its own tick). */
export function previewColors(preview: ArtPreview | null): { color: string; count: number }[] {
  const found = new Map<string, number>();
  for (const sh of preview?.shapes ?? []) if (!sh.background) found.set(sh.color, (found.get(sh.color) ?? 0) + 1);
  return [...found].map(([color, count]) => ({ color, count }));
}

/** "12 fills, 4 lines, 2 satins". */
export function countWords(shapes: readonly ArtShape[]): string {
  const words: [ArtShape["kind"], string][] = [["fill", "fill"], ["run", "line"], ["satin", "satin"]];
  const parts = words.flatMap(([kind, word]) => {
    const n = shapes.filter((s) => s.kind === kind).length;
    return n ? [`${n} ${word}${n === 1 ? "" : "s"}`] : [];
  });
  return parts.join(", ") || "Nothing ticked";
}

// ---------------------------------------------------------------- the preview

/** Counts requests: only the answer to the newest one is used. */
let asking = 0;
/** The size the view was last fitted to, so ticking colors doesn't move it. */
let framed = "";
/** The empty design made so the outlines have a hoop to show on (taken away if nothing's added). */
let madeDoc: Doc | null = null;

async function requestPreview(): Promise<void> {
  const { path, options } = useImportArt.getState();
  if (!path) return;
  const mine = ++asking;
  const asked = optionsKey(options);
  useImportArt.setState({ busy: true, error: null });
  try {
    const preview = await engine().call<ArtPreview>("art.preview", { path, options }, PREVIEW_MS);
    // A newer request (or Cancel) since: this answer is for something else.
    if (mine !== asking) return;
    useImportArt.setState({ preview, asked, busy: false, pages: preview.pages });
    frame(preview.size_mm);
  } catch (err) {
    if (mine !== asking) return;
    useImportArt.setState({ preview: null, asked: "", busy: false, error: previewError(err) });
  }
}

/** Show the hoop and the artwork, with room on the right where the dialog sits. */
function frame([w, h]: [number, number]): void {
  const key = `${w} ${h}`;
  if (key === framed || (!w && !h)) return;
  framed = key;
  const hoop = selectHoop(useStore.getState());
  const halfW = Math.max(w, hoop?.width_mm ?? 0) / 2;
  const halfH = Math.max(h, hoop?.height_mm ?? 0) / 2;
  useStore.getState().requestZoom("box", { box: [-halfW, -halfH, halfW + halfW * 0.7, halfH] });
}

export function setArtOptions(patch: Partial<ArtOptions>): void {
  const s = useImportArt.getState();
  if (!s.path) return;
  const options = { ...s.options, ...patch };
  if (optionsKey(options) === optionsKey(s.options) && !s.error) return;
  if (patch.strokes) savePrefs({ importArt: { ...loadPrefs().importArt, strokes: patch.strokes } });
  // Another page has its own colors.
  useImportArt.setState({ options, ...(options.page !== s.options.page ? { off: [] } : {}) });
  void requestPreview();
}

export function toggleColor(color: string, on: boolean): void {
  useImportArt.setState((s) => ({ off: on ? s.off.filter((c) => c !== color) : [...s.off.filter((c) => c !== color), color] }));
}

export function setMatch(match: boolean): void {
  savePrefs({ importArt: { ...loadPrefs().importArt, match } });
  useImportArt.setState({ match });
}

// ---------------------------------------------------------------- the outlines on the hoop

function outlineOf(sh: ArtShape): ImportOutline {
  if (sh.kind === "fill") return { color: sh.color, paths: [sh.geometry.outline, ...(sh.geometry.holes ?? [])].map((nodes) => ({ nodes, closed: true })) };
  const paths = [{ nodes: sh.geometry.nodes, closed: !!sh.geometry.closed }];
  return sh.kind === "satin" ? { color: sh.color, width_mm: sh.geometry.width_mm, paths } : { color: sh.color, paths };
}

useImportArt.subscribe((s, prev) => {
  if (s.preview === prev.preview && s.off === prev.off && s.path === prev.path && s.options === prev.options) return;
  showImportOutlines(s.path ? chosenShapes(s).map(outlineOf) : []);
});

// ---------------------------------------------------------------- opening and closing

/** Import artwork: pick a file (or take the one dropped), and preview it in the dialog. */
export async function importArtwork(path?: string): Promise<void> {
  if (!useStore.getState().engine) return info("LUDD's engine is still starting. Try again in a moment.");
  try {
    if (!path) {
      const picked = await openDialog({
        title: "Import artwork",
        multiple: false,
        directory: false,
        filters: [
          { name: "Artwork (SVG, DXF, PDF)", extensions: ["svg", "dxf", "pdf", "SVG", "DXF", "PDF"] },
          { name: "All files", extensions: ["*"] },
        ],
      });
      if (!picked) return;
      path = picked;
    }
    if (!useStore.getState().history.present) {
      // The outlines show on the hoop, so there has to be a design to show them on. With none
      // open, an empty new one is made here, and taken away again if nothing is added.
      await addTraced([], BLACK); // (adds nothing: it just starts a new design, as drawing does)
      madeDoc = useStore.getState().history.present;
      useStore.getState().select(null);
    }
  } catch (err) {
    return fail(err);
  }
  asking++;
  framed = "";
  const match = (loadPrefs().importArt?.match ?? true) && mySpools(useStore.getState().charts) !== null;
  useImportArt.setState({ path, options: startOptions(), preview: null, asked: "", busy: true, error: null, pages: 1, off: [], match, adding: false });
  useStore.getState().setDialog("importArt");
  await requestPreview();
}

/** The dialog closed (Cancel, Esc, another dialog, or after Add): forget the preview. */
function endImport(): void {
  asking++; // an answer still on its way is dropped
  useImportArt.setState({ path: null, preview: null, asked: "", busy: false, error: null, off: [], adding: false });
  const s = useStore.getState();
  const h = s.history;
  if (madeDoc && h.present === madeDoc && !h.past.length && !h.future.length) {
    // Nothing was added to the design made for the outlines: back to no design open.
    s.setHistory({ past: [], present: null, future: [] });
    s.setDesign(null);
    useStore.setState({ savedDoc: null, projectPath: null });
  }
  madeDoc = null;
}

useStore.subscribe((s, prev) => {
  if (prev.dialog === "importArt" && s.dialog !== "importArt") endImport();
});

// ---------------------------------------------------------------- Add

/** A thread for each color: the closest of your own spools if asked, else the file's color. */
async function threadsFor(shapes: readonly ArtShape[], match: boolean): Promise<Map<string, Thread>> {
  const colors = [...new Set(shapes.map((s) => s.color))];
  const chart = match ? mySpools(useStore.getState().charts) : null;
  const found = chart ? await matchThreads(colors, chart, 1) : null;
  return new Map(
    colors.map((color, i) => {
      const spool = found?.[i]?.[0];
      return [color, spool ? { color: spool.color, name: spool.name, catalog: spool.code, brand: spool.brand ?? "" } : { color, name: "", catalog: "", brand: "" }];
    }),
  );
}

/** Add the ticked shapes: ordinary shapes with your settings for each kind, in the file's order,
 *  grouped and selected, as one undo step. */
export async function addImported(): Promise<boolean> {
  const s = useImportArt.getState();
  if (!canAdd(s)) return false;
  const shapes = chosenShapes(s);
  const mine = asking;
  useImportArt.setState({ adding: true });
  try {
    const threads = await threadsFor(shapes, s.match);
    // Cancelled, or another file, while the threads were matched: nothing is added.
    if (mine !== asking) return false;
    let layout = currentLayout();
    if (!layout) return false;
    const group = shapes.length > 1 ? `g${Date.now().toString(36)}` : undefined;
    const ids: string[] = [];
    for (const sh of shapes) {
      const obj = {
        kind: sh.kind,
        geometry: sh.geometry,
        params: defaultsFor(sh.kind),
        thread: threads.get(sh.color)!,
        ...(sh.name ? { name: sh.name.slice(0, 80) } : {}),
        ...(group ? { group } : {}),
      } as unknown as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">;
      const added = addObject(layout, obj);
      layout = added.layout;
      ids.push(added.id);
    }
    // If they can't be sewn (the error says why), the dialog stays, to change and try again.
    if (!(await commit(layout))) return false;
    useStore.getState().setDialog(null);
    useStore.getState().setTool("select");
    useStore.getState().setSelection(ids[0], ids.slice(1));
    info(ids.length === 1 ? "Added 1 shape. Ctrl+Z takes it out." : `Added ${ids.length} shapes, grouped (Ctrl+U ungroups them). Ctrl+Z takes them out.`);
    return true;
  } catch (err) {
    fail(err);
    return false;
  } finally {
    if (useImportArt.getState().adding) useImportArt.setState({ adding: false });
  }
}
