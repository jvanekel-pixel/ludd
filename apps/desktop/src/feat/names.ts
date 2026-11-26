/** Names from a list (text.names): the lettering marked "Filled from the list" is filled row by
 *  row (colors and file names from the list, long names shrunk to fit), each row previewed on
 *  the design without changing it, then saved as its own machine file. And name templates
 *  (text.saveTemplate): saved in LUDD's data folder, and started from as new designs.
 *
 *  cmd/lettering.ts imports this module: nothing here may call actions.ts while it loads. */
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { basename, commit, currentLayout, engine, exportOptions, fail, info, openDesign, whenIdle } from "../actions";
import { DEFAULT_CUT_STOPS } from "../design/machine";
import { isText, type Chart, type Design, type Doc, type ExportReport, type Layout, type LayoutItem, type TextItem, type Thread } from "../design/types";
import { isTauri } from "../engine/sidecar";
import { nameFileStem } from "../features";
import { selectHoop, selectMachine, useStore } from "../store";
import { pruneLetterEdits } from "./letters";

/** A list of names: column names, and a row of values for each file. */
export type NameList = { columns: string[]; rows: string[][]; skipped: number };
export type Template = { name: string; path: string; saved_at: number };

/** Columns that aren't words to sew: a thread for the row, and its file's name. */
export const SPECIAL_COLUMNS = ["color", "file"];
const MIN_SIZE_MM = 2;
const FIT_SLACK_MM = 0.05;
const LONG_MS = 120_000;

const message = (err: unknown) => (err instanceof Error ? err.message : String(err));

// ---------------------------------------------------------------- the list

/** One name per line, as typed in the box. */
export function typedList(typed: string): NameList {
  const rows = typed.split("\n").map((n) => n.trim()).filter(Boolean).map((n) => [n]);
  return { columns: ["name"], rows, skipped: 0 };
}

/** Pick a CSV or text file of names and read it; null if none was picked. */
export async function loadList(): Promise<(NameList & { file: string }) | null> {
  const path = isTauri()
    ? await openDialog({
        title: "Load a list of names",
        multiple: false,
        directory: false,
        filters: [
          { name: "Lists (CSV or text)", extensions: ["csv", "txt", "tsv", "CSV", "TXT", "TSV"] },
          { name: "All files", extensions: ["*"] },
        ],
      })
    : window.prompt("Load a list of names (a CSV or text file)") || null;
  if (typeof path !== "string") return null;
  const read = await engine().call<NameList>("names.read_list", { path }, LONG_MS);
  return { ...read, file: basename(path) };
}

// ---------------------------------------------------------------- which lettering is filled

/** The column a placeholder takes ("name" unless you chose another). */
export const bindOf = (t: TextItem) => t.bind || "name";

/** A few words of a lettering's text, to tell it by. */
export const snippet = (t: TextItem) => t.text.replace(/\s*\n\s*/g, " / ").slice(0, 24);

const texts = (layout: Layout) => layout.items.filter(isText) as TextItem[];

/** The lettering a list fills: what's marked "Filled from the list"; with none marked, the
 *  selected lettering (or the design's only one). */
export function textTargets(layout: Layout, selectedId: string | null): TextItem[] {
  const all = texts(layout);
  const marked = all.filter((t) => t.placeholder);
  if (marked.length) return marked;
  const selected = all.find((t) => t.id === selectedId);
  return selected ? [selected] : all.length === 1 ? all : [];
}

/** The list's column for `bind`, or -1. A list with one column of names fills "name" whatever
 *  its header calls it ("player", "first name"). */
export function columnFor(list: Pick<NameList, "columns">, bind: string): number {
  const want = bind.trim().toLowerCase();
  const exact = list.columns.indexOf(want);
  if (exact >= 0) return exact;
  const words = list.columns.filter((c) => !SPECIAL_COLUMNS.includes(c));
  return want === "name" && words.length === 1 ? list.columns.indexOf(words[0]) : -1;
}

/** Why the list can't fill these, or null. */
export function listProblem(list: NameList, targets: TextItem[]): string | null {
  if (!targets.length) return "Select the lettering to fill, or tick it under Lettering to fill.";
  const missing = targets.find((t) => columnFor(list, bindOf(t)) < 0);
  return missing ? `The list has no “${bindOf(missing)}” column: pick the column for “${snippet(missing)}” in One file per name.` : null;
}

async function changeTexts(change: (t: TextItem) => TextItem) {
  const l = currentLayout();
  if (l) await commit({ ...l, items: l.items.map((it): LayoutItem => (isText(it) ? change(it) : it)) });
}

/** Tick or untick lettering as "Filled from the list" (at least one stays ticked). A newly
 *  ticked one takes the next column nothing else uses. */
export async function setPlaceholder(id: string, on: boolean, columns: string[]) {
  const l = currentLayout();
  if (!l) return;
  const now = textTargets(l, useStore.getState().selectedId).map((t) => t.id);
  const next = on ? [...new Set([...now, id])] : now.filter((x) => x !== id);
  if (!next.length) return;
  const used = new Set(texts(l).filter((t) => next.includes(t.id) && t.id !== id).map(bindOf));
  const free = columns.find((c) => !SPECIAL_COLUMNS.includes(c) && !used.has(c));
  await changeTexts((t) => {
    if (next.includes(t.id)) {
      const bind = t.id === id && !t.bind ? free : t.bind;
      return { ...t, placeholder: true, bind: bind && bind !== "name" ? bind : undefined };
    }
    return t.placeholder ? { ...t, placeholder: undefined } : t;
  });
}

/** Change `change` on one lettering, marking what's filled as placeholders first, so the choice
 *  stays whatever is selected next time. */
async function changePlaceholder(id: string, change: Partial<TextItem>) {
  const l = currentLayout();
  if (!l) return;
  const filled = new Set(textTargets(l, useStore.getState().selectedId).map((t) => t.id));
  await changeTexts((t) => {
    const marked = filled.has(t.id) ? { ...t, placeholder: true } : t;
    return t.id === id ? { ...marked, placeholder: true, ...change } : marked;
  });
}

export const setBind = (id: string, bind: string) => changePlaceholder(id, { bind: bind === "name" ? undefined : bind });

/** "Shrink long names to fit": at the lettering's width now, until you type another. */
export async function setFitWidth(id: string, on: boolean | number) {
  if (on === false) return changePlaceholder(id, { fit_width_mm: undefined });
  if (typeof on === "number") return changePlaceholder(id, { fit_width_mm: on });
  const l = currentLayout();
  const t = l && texts(l).find((x) => x.id === id);
  if (!l || !t) return;
  try {
    const width = await widthOf(t, l);
    await changePlaceholder(id, { fit_width_mm: width ? Math.ceil(width) : 80 });
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- one row

/** The thread a color cell names: a thread number from the chart, or a hex color; else null. */
export function rowThread(value: string, chart: Chart | null): Thread | null {
  const v = value.trim();
  const hex = (s: string) => {
    let h = s.replace(/^#/, "");
    if (h.length === 3) h = [...h].map((c) => c + c).join("");
    return /^[0-9a-f]{6}$/i.test(h) ? { color: `#${h.toLowerCase()}`, name: "", brand: "", catalog: "" } : null;
  };
  if (!v) return null;
  if (v.startsWith("#")) return hex(v);
  const digits = (s: string) => (/^\d+$/.test(s) ? String(Number(s)) : null);
  // A spreadsheet drops leading zeros, so 5 also finds thread 005.
  const found =
    chart?.threads.find((t) => t.code.trim().toLowerCase() === v.toLowerCase()) ??
    (digits(v) !== null ? chart?.threads.find((t) => digits(t.code.trim()) === digits(v)) : undefined);
  if (found && chart) return { color: found.color, name: found.name, brand: found.brand || chart.brand, catalog: found.code };
  return v.length === 6 ? hex(v) : null;
}

export type Row = { layout: Layout; stem: string; notes: string[]; empty: boolean };

/** The design with row `i` of the list in its lettering (without the shrinking). */
function filledRow(layout: Layout, targets: TextItem[], list: NameList, i: number, chart: Chart | null, ext: string): Row {
  const cell = (c: number) => (c >= 0 ? (list.rows[i]?.[c] ?? "").trim() : "");
  const notes: string[] = [];
  const values = new Map(targets.map((t) => [t.id, cell(columnFor(list, bindOf(t)))]));
  const first = [...values.values()].find(Boolean) ?? "";
  const asked = cell(list.columns.indexOf("file")).replace(new RegExp(`\\.${ext || "pes"}$`, "i"), "");
  const stem = nameFileStem((asked || cell(columnFor(list, "name")) || first || `Row ${i + 1}`).replace(/\s*\n\s*/g, " "));
  if (!first) return { layout, stem, notes: [`Row ${i + 1} is empty for the filled lettering, so it has no file.`], empty: true };
  const color = cell(list.columns.indexOf("color"));
  const thread = color ? rowThread(color, chart) : null;
  if (color && !thread) notes.push(`Row ${i + 1}: “${color}” isn't a hex color or a thread number in the chosen chart, so the lettering keeps its color.`);
  const items = layout.items.flatMap((it): LayoutItem[] => {
    const value = values.get(it.id);
    if (value === undefined) return [it];
    const t = it as TextItem;
    if (!value) {
      // Never sew the sample's own words for someone else.
      notes.push(`Row ${i + 1} has no ${bindOf(t)}, so “${snippet(t)}” is left out of its file.`);
      return [];
    }
    // New words are new letters: chosen starts and ends belong to the old ones.
    return [pruneLetterEdits({ ...t, text: value, letters: undefined, ...(thread ? { thread, threads: [] } : {}) })];
  });
  return { layout: { ...layout, items }, stem, notes, empty: false };
}

/** A lettering's width as it will be sewn, measured by itself and unturned (mm). */
async function widthOf(t: TextItem, layout: Layout): Promise<number | null> {
  const alone: Layout = {
    ...layout,
    items: [{ ...t, transform: { ...t.transform, x: 0, y: 0, rotate: 0, flip_x: false, flip_y: false } }],
    basting: { enabled: false, margin_mm: 0 },
    knockdown: undefined,
    merge_colors: false,
    color_sort: false,
  };
  const d = await engine().call<Design>("layout.render", { layout: alone }, LONG_MS);
  const b = d.items?.[0]?.bounds_mm;
  return b ? b[2] - b[0] : null;
}

/** A lettering narrowed to its fit width, size and spacing scaled together. */
async function shrunk(t: TextItem, layout: Layout): Promise<{ item: TextItem; note?: string }> {
  const fit = t.fit_width_mm;
  if (!fit || fit <= 0) return { item: t };
  let item = t;
  for (let tries = 0; ; tries++) {
    const width = await widthOf(item, layout);
    if (width === null || width <= fit + FIT_SLACK_MM) return { item };
    if (tries >= 4 || item.size_mm <= MIN_SIZE_MM) {
      return { item, note: `“${snippet(t)}” is still ${width.toFixed(1)} mm wide at ${item.size_mm} mm letters (it should fit ${fit} mm).` };
    }
    // Rounded down, so it fits: the edge pad doesn't shrink with the letters, so it may take two goes.
    const size = Math.max(MIN_SIZE_MM, Math.floor(item.size_mm * (fit / width) * 100) / 100);
    item = { ...item, size_mm: size, spacing_mm: Math.round(item.spacing_mm * (size / item.size_mm) * 1000) / 1000 };
  }
}

/** The design with row `i` of the list in its lettering, long names shrunk to fit. */
export async function fillRow(layout: Layout, targets: TextItem[], list: NameList, i: number, chart: Chart | null, ext = "pes"): Promise<Row> {
  const row = filledRow(layout, targets, list, i, chart, ext);
  if (row.empty) return row;
  const filled = new Set(targets.map((t) => t.id));
  const items: LayoutItem[] = [];
  for (const it of row.layout.items) {
    if (!filled.has(it.id) || !isText(it)) {
      items.push(it);
      continue;
    }
    const { item, note } = await shrunk(it, row.layout);
    if (note) row.notes.push(note);
    items.push(item);
  }
  return { ...row, layout: { ...row.layout, items } };
}

// ---------------------------------------------------------------- preview: shown, never saved

/** The newest preview asked for (older ones still on their way are dropped). */
let turn = 0;
/** What to show again when the preview ends: the document as it is, as it was drawn. */
let saved: { doc: Doc; design: Design | null } | null = null;

async function redraw() {
  const doc = useStore.getState().history.present;
  if (!doc) return;
  const design = await engine().call<Design>("layout.render", { layout: doc.layout }, LONG_MS);
  if (useStore.getState().history.present === doc) useStore.getState().setDesign(design);
}

function putBack() {
  const was = saved;
  saved = null;
  if (!was) return;
  const s = useStore.getState();
  if (s.history.present === was.doc) s.setDesign(was.design);
  else void redraw().catch(fail);
}

/** Show row `i` on the design without changing it: nothing is saved and there's no undo step.
 *  Returns the row's notes, or null if the preview has moved on meanwhile. */
export async function showRow(list: NameList, i: number, chart: Chart | null): Promise<string[] | null> {
  const mine = ++turn;
  await whenIdle();
  if (mine !== turn) return null;
  const s = useStore.getState();
  const doc = s.history.present;
  if (!doc || !s.engine) return null;
  const targets = textTargets(doc.layout, s.selectedId);
  const problem = listProblem(list, targets);
  if (problem) {
    putBack();
    return [problem];
  }
  try {
    const row = await fillRow(doc.layout, targets, list, i, chart);
    if (mine !== turn) return null;
    if (row.empty) {
      putBack();
      return row.notes;
    }
    const design = await engine().call<Design>("layout.render", { layout: row.layout }, LONG_MS);
    const now = useStore.getState();
    if (mine !== turn || now.history.present !== doc) return null;
    if (saved?.doc !== doc) saved = { doc, design: now.design };
    now.setDesign(design);
    return row.notes;
  } catch (err) {
    if (mine !== turn) return null;
    putBack();
    return [`Row ${i + 1}: ${message(err)}`];
  }
}

/** The design as saved again (the list's window closed). */
export function endPreview() {
  turn++;
  putBack();
}

// ---------------------------------------------------------------- one file per row

/** One machine file per row, prepared as Save for machine would (your machine and hoop,
 *  cut-stops for machines that only cut at color changes). Existing files are never replaced;
 *  repeated names get "(1)", "(2)". The design on screen isn't changed. */
export async function exportList(list: NameList, folder: string, ext: string, chart: Chart | null = null) {
  await whenIdle();
  const layout = currentLayout();
  const targets = layout ? textTargets(layout, useStore.getState().selectedId) : [];
  const problem = !layout ? "Open a design with lettering first." : !list.rows.length ? "Type at least one name, or load a list." : listProblem(list, targets);
  if (!layout || problem) return info(problem!);
  const machine = selectMachine(useStore.getState());
  const options = exportOptions({ ...DEFAULT_CUT_STOPS, enabled: machine?.cuts === "color_change" });
  const sep = folder.includes("\\") ? "\\" : "/";
  const total = list.rows.length;
  const tooBig: string[] = [];
  const warnings = new Set<string>();
  const renamed: string[] = [];
  const failed: string[] = [];
  const rowNotes: string[] = [];
  let firstError: unknown = null;
  let done = 0;
  let leftOut = 0;
  const { setLoading } = useStore.getState();
  try {
    for (let i = 0; i < total; i++) {
      setLoading(`Saving file ${i + 1} of ${total}…`);
      let stem = list.rows[i].find(Boolean) ?? `Row ${i + 1}`;
      try {
        const row = await fillRow(layout, targets, list, i, chart, ext);
        rowNotes.push(...row.notes);
        if (row.empty) {
          leftOut++;
          continue;
        }
        stem = row.stem;
        const dest = `${folder}${sep}${stem}.${ext}`;
        // keep_existing: never replace a file; a name already taken is saved as "Name (1)" and so on.
        const r = await engine().call<ExportReport & { path: string }>("layout.export", { layout: row.layout, dest, options, keep_existing: true }, LONG_MS);
        if (r.path && basename(r.path).toLowerCase() !== basename(dest).toLowerCase()) renamed.push(basename(r.path));
        for (const w of r.warnings ?? []) {
          if (w.code === "hoop_too_big") tooBig.push(stem);
          else if (w.level !== "info") warnings.add(w.message);
        }
        done++;
      } catch (err) {
        // One row that can't be saved doesn't stop the others.
        failed.push(stem);
        firstError ??= err;
      }
    }
  } finally {
    setLoading(null);
  }
  const notes = [
    tooBig.length ? `${tooBig.length === 1 ? `"${tooBig[0]}" doesn't` : `${tooBig.length} names don't`} fit your hoop (make the letters smaller, or shrink long names to fit).` : "",
    rowNotes.length ? `${rowNotes.slice(0, 3).join(" ")}${rowNotes.length > 3 ? ` (and ${rowNotes.length - 3} more like these)` : ""}` : "",
    warnings.size ? `Check: ${[...warnings][0]}` : "",
    renamed.length
      ? `${renamed.length === 1 ? "One file" : `${renamed.length} files`} got a number added because the name was already taken (like "${renamed[0]}").`
      : "",
    list.skipped ? `The list is longer than LUDD reads: ${list.skipped} rows at the end weren't saved.` : "",
  ].filter(Boolean);
  const count = total - leftOut;
  if (failed.length) {
    fail(firstError);
    info(`Saved ${done} of ${count} files in ${folder}. Not saved: ${failed.map((n) => `"${n}"`).join(", ")}.${notes.length ? ` ${notes.join(" ")}` : ""}`);
  } else {
    info(`Saved ${done} file${done === 1 ? "" : "s"} (one per row) in ${folder}.${notes.length ? ` ${notes.join(" ")}` : ""}`);
  }
}

// ---------------------------------------------------------------- name templates

export function canSaveTemplate(): boolean {
  return useStore.getState().engine !== null && !!currentLayout()?.items.some((it) => it.kind === "text");
}

/** "Save this layout as a name template…": asks for its name (components/NamesDialog.tsx). */
export async function saveTemplate(): Promise<void> {
  useStore.getState().setDialog("saveTemplate");
}

export const listTemplates = () => engine().call<Template[]>("names.list_templates");

/** Save the design as a template named `name`. Returns why it couldn't, or null. The open
 *  project, and what counts as saved, stay as they were. */
export async function saveTemplateAs(name: string, replace: boolean): Promise<string | null> {
  await whenIdle();
  const s = useStore.getState();
  const doc = s.history.present;
  if (!doc) return "There's no design to save.";
  const project_data = { title: name, layout: doc.layout, images: doc.images, machine: s.machineId, hoop: selectHoop(s)?.id ?? null };
  try {
    const r = await engine().call<{ name: string; path: string }>("names.save_template", { name, project_data, replace }, LONG_MS);
    info(`Saved the name template “${r.name}”. To start from it, open One file per name.`);
    return null;
  } catch (err) {
    return message(err);
  }
}

/** A new design from a saved template (asking about unsaved changes first). Saving it asks for
 *  a name, so the template stays as it is. */
export async function openTemplate(path: string): Promise<void> {
  endPreview();
  const before = useStore.getState().history.present;
  await openDesign(path);
  await whenIdle();
  if (useStore.getState().history.present !== before) useStore.setState({ projectPath: null });
}
