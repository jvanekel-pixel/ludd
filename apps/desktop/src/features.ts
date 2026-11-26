/**
 * Features that came from comparing LUDD with Hatch: whole-picture auto-digitize, outlines &
 * offsets, the knife and merge, fewer jumps (travel under, shortest order), stitch editing of
 * placed stitch files, text along a drawn line, one file per name, color sets (colorways),
 * and guides.
 */

import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { addTraced, commit, currentDoc, currentLayout, defaultsFor, engine, fail, info } from "./actions";
import { holdEscape } from "./escape";
import { exportList, typedList } from "./feat/names";
import { addObject, IDENTITY, newId } from "./design/layout";
import type { Colorway, Guide, Layout, LayoutItem, LayoutOp, ObjectItem, PathNode, TextItem, Thread } from "./design/types";
import { isObject, isText } from "./design/types";
import { isTauri } from "./engine/sidecar";
import { loadPrefs } from "./prefs";
import { useStore, type TracedShape } from "./store";

const BLACK: Thread = { color: "#000000", name: "Black", brand: "", catalog: "" };
const LONG_MS = 120_000;

const threadOf = (color: string): Thread => ({ color, name: "", brand: "", catalog: "" });

function selectionIds(): string[] {
  const s = useStore.getState();
  return s.selectedId ? [s.selectedId, ...s.extraIds] : [];
}

function selectedItems(): LayoutItem[] {
  const l = currentLayout();
  const ids = new Set(selectionIds());
  return l ? l.items.filter((it) => ids.has(it.id)) : [];
}

type NewObject = Omit<ObjectItem, "id" | "transform" | "threads" | "ops"> & Partial<Pick<ObjectItem, "threads" | "ops">>;

/** Add objects right after `afterId` in the sewing order (or at the end), as one undo step.
 *  An object may bring its own colour changes (`threads`) and `ops`, as a knife piece does. */
async function insertObjects(objs: NewObject[], afterId?: string, remove: string[] = []) {
  let l = currentLayout();
  if (!l) return [];
  const ids: string[] = [];
  for (const o of objs) {
    const { threads, ops, ...rest } = o;
    const r = addObject(l, rest);
    l = r.layout;
    if (threads || ops)
      l = { ...l, items: l.items.map((it) => (it.id === r.id ? ({ ...it, threads: structuredClone(threads ?? []), ops: structuredClone(ops ?? []) } as ObjectItem) : it)) };
    ids.push(r.id);
  }
  const added = l.items.slice(l.items.length - objs.length);
  let rest = l.items.slice(0, l.items.length - objs.length);
  const at = afterId ? rest.findIndex((it) => it.id === afterId) : -1;
  rest = at >= 0 ? [...rest.slice(0, at + 1), ...added, ...rest.slice(at + 1)] : [...rest, ...added];
  if (remove.length) rest = rest.filter((it) => !remove.includes(it.id));
  if (await commit({ ...l, items: rest })) {
    useStore.getState().select(ids[ids.length - 1] ?? null);
    return ids;
  }
  return [];
}

// ---------------------------------------------------------------- 1. whole-picture auto-digitize

let releaseAll: (() => void) | null = null;
useStore.subscribe((s, prev) => {
  if (s.autoAll && !prev.autoAll) releaseAll ??= holdEscape(() => useStore.getState().setAutoAll(null));
  if (!s.autoAll && prev.autoAll) {
    releaseAll?.();
    releaseAll = null;
  }
  // The preview follows point spacing, spread and the picture's place: read it again.
  const a = s.autoAll;
  if (a && prev.autoAll && !a.busy) {
    const place = (doc: typeof s.history.present) => {
      const im = doc?.images.find((i) => i.id === a.imageId);
      return im && `${im.x} ${im.y} ${im.width_mm} ${im.height_mm} ${im.rotate} ${im.path}`;
    };
    const moved = s.history.present !== prev.history.present && place(s.history.present) !== place(prev.history.present);
    if (moved || s.autoSpacing !== prev.autoSpacing || s.autoSpread !== prev.autoSpread) void digitizeWholePicture({ imageId: a.imageId });
  }
});

let allSeq = 0;

/** The picture to work on: the selected one, else the only (or topmost visible) one. */
function targetPicture() {
  const s = useStore.getState();
  const imgs = s.history.present?.images ?? [];
  return imgs.find((im) => im.id === s.selectedId) ?? imgs.filter((im) => im.visible).at(-1) ?? null;
}

/** Turn the whole picture into shapes (a preview first: nothing is added until you say). */
export async function digitizeWholePicture(opts: { outlines?: boolean; skipBackground?: boolean; imageId?: string } = {}) {
  const s = useStore.getState();
  const img = (opts.imageId && s.history.present?.images.find((im) => im.id === opts.imageId)) || targetPicture();
  if (!img) return info("Add a picture first (Ctrl+I): the whole picture is turned into shapes.");
  const outlines = opts.outlines ?? s.autoAll?.outlines ?? true;
  const skipBackground = opts.skipBackground ?? s.autoAll?.skipBackground ?? true;
  s.setAutoTrace(null);
  s.setAutoAll({ imageId: img.id, shapes: s.autoAll?.imageId === img.id ? s.autoAll.shapes : [], busy: true, outlines, skipBackground });
  const my = ++allSeq; // only the newest run's answer is shown
  try {
    const r = await engine().call<{ shapes: TracedShape[] }>(
      "trace.digitize_all",
      {
        path: img.path,
        placement: { x: img.x, y: img.y, width_mm: img.width_mm, height_mm: img.height_mm, rotate: img.rotate },
        spacing_mm: s.autoSpacing,
        spread: s.autoSpread,
        outlines,
        skip_background: skipBackground,
      },
      LONG_MS,
    );
    if (my !== allSeq || !useStore.getState().autoAll) return; // a newer run, or dismissed while working
    if (!r.shapes.length) {
      useStore.getState().setAutoAll(null);
      return info("Couldn't find shapes in that picture. Try more Spread, or Auto-trace one shape at a time.");
    }
    useStore.getState().setAutoAll({ imageId: img.id, shapes: r.shapes, busy: false, outlines, skipBackground });
  } catch (err) {
    if (my !== allSeq) return;
    useStore.getState().setAutoAll(null);
    fail(err);
  }
}

/** Add everything from the whole-picture preview (one undo step), each in the picture's color. */
export async function acceptWholePicture() {
  const a = useStore.getState().autoAll;
  if (!a || a.busy || !a.shapes.length) return;
  const shapes = a.shapes.map((sh) =>
    sh.kind === "fill"
      ? { kind: "fill" as const, outline: sh.outline, holes: sh.holes, thread: threadOf(sh.color) }
      : sh.kind === "satin"
        ? { kind: "satin" as const, nodes: sh.nodes, width_mm: sh.width_mm, closed: sh.closed, thread: threadOf(sh.color) }
        : { kind: "run" as const, nodes: sh.nodes, closed: sh.closed, thread: threadOf(sh.color) },
  );
  // If they couldn't be added (the error says why), the preview stays so you can try again.
  if (!(await addTraced(shapes, BLACK))) return;
  useStore.getState().setAutoAll(null);
  info(`Added ${shapes.length} shapes. Fix any by dragging their points; Order & colors → Match… picks real threads for the colors.`);
}

// ---------------------------------------------------------------- 2. outlines & offsets

export type OffsetSpec = { distance_mm: number; as: "satin" | "run" | "triple"; width_mm: number; holes: boolean };

/** Rings around the selection, `distance_mm` out, sewn after it. */
export async function addOffset(spec: OffsetSpec) {
  const l = currentLayout();
  const ids = selectionIds();
  if (!l || !ids.length) return info("Select what to put an outline around first.");
  try {
    const r = await engine().call<{ rings: PathNode[][] }>("shape.offset", {
      layout: l,
      ids,
      distance_mm: spec.distance_mm,
      spacing: useStore.getState().autoSpacing,
      holes: spec.holes,
    }, LONG_MS); // a second or two round a whole dense design; more on a slow computer
    if (!stillSame(l.items.filter((it) => ids.includes(it.id)))) return info("The design changed while adding the outline: try again.");
    if (!r.rings.length)
      return info(
        spec.distance_mm < 0
          ? "Nothing is left that far inside the shape; try a smaller inset (closer to 0)."
          : "No outline came out at that distance; try a bigger one.",
      );
    const thread = useStore.getState().drawThread;
    const objs = r.rings.map((nodes) =>
      spec.as === "satin"
        ? ({ kind: "satin", geometry: { nodes, width_mm: spec.width_mm, closed: true }, params: defaultsFor("satin"), thread } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">)
        : ({ kind: "run", geometry: { nodes, closed: true }, params: { ...defaultsFor("run"), style: spec.as === "triple" ? "triple" : "single" }, thread } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">),
    );
    const last = l.items.filter((it) => ids.includes(it.id)).at(-1)?.id;
    if ((await insertObjects(objs, last)).length)
      info(`Added ${objs.length === 1 ? "an outline" : `${objs.length} outlines`}. Change its thread in its panel.`);
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- 3. knife & merge

let releaseKnife: (() => void) | null = null;

// However the knife or stitch editing ends (Esc, Done, a tool key, New or Open, the shape deleted
// or undone), its Esc booking goes with it, so the next Esc press does something you can see.
useStore.subscribe((s, prev) => {
  if (!s.knife && prev.knife) {
    releaseKnife?.();
    releaseKnife = null;
  }
  if (!s.stitchEdit && prev.stitchEdit) {
    releaseEdit?.();
    releaseEdit = null;
  }
});

/** A shape's settings without the points chosen on it (start, end, direction dots), for pieces cut from it. */
function withoutDots<T extends object>(params: T): T {
  const { start_mm: _s, end_mm: _e, angle_line: _a, ...rest } = params as Record<string, unknown>;
  void [_s, _e, _a];
  return rest as T;
}

/** Only one of the knife, stitch editing, the ruler and the angle line is on at a time (the canvas
 *  gives clicks to just one, and Esc lets go of the newest): starting one ends the others. */
export function endOtherModes(keep: "knife" | "stitchEdit" | "ruler" | "angle") {
  const s = useStore.getState();
  if (keep !== "knife" && s.knife) s.setKnife(null);
  if (keep !== "stitchEdit" && s.stitchEdit) endStitchEdit();
  if (keep !== "ruler" && s.ruler) s.setRuler(null);
  if (keep !== "angle" && s.angleFor) s.setAngleFor(null);
}

/** Whether these items are still exactly as they were before an engine call (not changed, undone
 *  or removed meanwhile): if not, the engine's answer was worked out for the old ones. */
function stillSame(before: LayoutItem[]): boolean {
  const now = currentLayout();
  return !!now && before.every((b) => now.items.find((it) => it.id === b.id) === b);
}

/** The knife: draw a line across the selected shape to cut it there. */
export function startKnife() {
  const s = useStore.getState();
  const o = currentLayout()?.items.find((it) => it.id === s.selectedId);
  if (!o || !isObject(o) || (o.kind === "satin" && !("nodes" in o.geometry)))
    return info("Select a fill, line or satin ribbon first, then use the knife and draw a line across it.");
  endOtherModes("knife");
  if (s.tool !== "select") s.setTool("select");
  armKnife(o.id);
  info("Click two points: the knife cuts along that line (extended across the shape). Esc cancels.");
}

function armKnife(id: string) {
  useStore.getState().setKnife({ id, points: [] });
  releaseKnife?.();
  releaseKnife = holdEscape(() => useStore.getState().setKnife(null));
}

/** Called by the canvas once the knife line is drawn. */
export async function finishKnife(a: [number, number], b: [number, number]) {
  const s = useStore.getState();
  const k = s.knife;
  s.setKnife(null);
  releaseKnife?.();
  releaseKnife = null;
  const o = currentLayout()?.items.find((it) => it.id === k?.id);
  if (!o || !isObject(o)) return;
  try {
    const r = await engine().call<{ geometries: Record<string, unknown>[] }>("shape.split", { obj: o, a, b, spacing: s.autoSpacing });
    // The shape changed meanwhile (an undo, a nudge): the cut was worked out for the old one.
    if (!stillSame([o])) return info("The design changed while cutting: try the cut again.");
    // Each piece keeps everything of the original but its shape and name: colour changes, stops
    // and trims (left out by the engine if they no longer fit), pin and group.
    const parts = r.geometries.map(
      (g, i) =>
        ({
          kind: o.kind,
          name: o.name ? `${o.name} ${i + 1}` : undefined,
          geometry: o.kind === "run" ? { ...g, closed: false } : g,
          // The start, end and direction dots were placed on the whole shape: each piece gets its
          // own (its start nearest the piece before, rows across the middle at the same angle).
          params: withoutDots(o.params),
          thread: o.thread,
          threads: o.threads,
          ops: o.ops,
          ...(o.locked ? { locked: true } : {}),
          ...(o.group ? { group: o.group } : {}),
        }) as NewObject,
    );
    if ((await insertObjects(parts, o.id, [o.id])).length) info(`Cut into ${parts.length} pieces.`);
  } catch (err) {
    fail(err);
    // A cut that missed (too short, not across the shape) changed nothing: the knife stays ready.
    if (currentLayout()?.items.some((it) => it.id === o.id) && !useStore.getState().knife) armKnife(o.id);
  }
}

/** Merge the selected fills into one, with the settings, thread and sewing place of the one
 *  selected first. The engine joins them as they're shown (moved, turned, resized), so the merged
 *  shape has no transform of its own. */
export async function mergeSelected() {
  const items = selectedItems().filter(isObject);
  if (items.length < 2) return info("Select two or more fills that touch (Shift+click), then merge them.");
  try {
    const r = await engine().call<{ geometry: Record<string, unknown> }>("shape.merge", { objs: items, spacing: useStore.getState().autoSpacing });
    if (!stillSame(items)) return info("The design changed while merging: try again.");
    const primary = useStore.getState().selectedId;
    const first = items.find((it) => it.id === primary) ?? items[0];
    const l = currentLayout()!;
    const others = new Set(items.filter((it) => it.id !== first.id).map((it) => it.id));
    const next: Layout = {
      ...l,
      items: l.items.filter((it) => !others.has(it.id)).map((it) => (it.id === first.id ? ({ ...it, geometry: r.geometry, transform: { ...IDENTITY } } as ObjectItem) : it)),
    };
    if (await commit(next)) {
      useStore.getState().setSelection(first.id, []);
      info("Merged into one shape, with the settings of the one you selected first.");
    }
  } catch (err) {
    fail(err);
  }
}

/** Cut the selected shapes out of the selected fill (the one sewn first): a hole where one sits
 *  inside it, a bite where it overlaps the edge. The cutters stay (selected), for Delete if they
 *  were only for cutting. */
export async function cutOutSelected() {
  const before = currentLayout();
  const l = before;
  const items = selectedItems().filter(isObject);
  if (!l || items.length < 2) return info("Select the fill and the shapes to cut out of it (Shift+click them), then cut.");
  const order = (id: string) => l.items.findIndex((it) => it.id === id);
  const target = [...items].sort((a, b) => order(a.id) - order(b.id)).find((it) => it.kind === "fill" || it.kind === "applique");
  if (!target) return info("One of the selected shapes must be a fill (or applique) to cut out of.");
  const cutters = items.filter((it) => it.id !== target.id);
  try {
    const r = await engine().call<{ geometries: Record<string, unknown>[] }>("shape.cut_out", { target, cutters, spacing: useStore.getState().autoSpacing });
    // Anything changed meanwhile (an undo, a nudge): the cut was worked out for the old shapes.
    if (currentLayout() !== before) return info("The design changed while cutting: try the cut again.");
    const [main, ...more] = r.geometries;
    let next: Layout = { ...l, items: l.items.map((it) => (it.id === target.id ? ({ ...it, geometry: main, transform: { ...IDENTITY } } as ObjectItem) : it)) };
    // A cut right across leaves more than one piece: each is its own fill, sewn where the fill was.
    const extra: ObjectItem[] = [];
    for (const g of more) {
      const add = addObject(next, { kind: target.kind, name: target.name, geometry: g, params: withoutDots(target.params), thread: target.thread } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
      const piece = { ...(add.layout.items[add.layout.items.length - 1] as ObjectItem), threads: target.threads, ...(target.locked ? { locked: true } : {}), ...(target.group ? { group: target.group } : {}) } as ObjectItem;
      next = { ...add.layout, items: add.layout.items.map((it) => (it.id === piece.id ? piece : it)) };
      extra.push(piece);
    }
    if (extra.length) {
      const items2 = next.items.filter((it) => !extra.some((e) => e.id === it.id));
      items2.splice(order(target.id) + 1, 0, ...extra);
      next = { ...next, items: items2 };
    }
    if (await commit(next)) {
      useStore.getState().setSelection(cutters[0].id, cutters.slice(1).map((c) => c.id));
      info(`Cut out${extra.length ? `, leaving ${extra.length + 1} pieces` : ""}. The shape${cutters.length > 1 ? "s" : ""} you cut with ${cutters.length > 1 ? "are" : "is"} still there (selected): press Delete if ${cutters.length > 1 ? "they were" : "it was"} only for cutting.`);
    }
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- 4. fewer jumps and trims

export function toggleTravelUnder() {
  const l = currentLayout();
  if (l) void commit({ ...l, travel_under: !l.travel_under });
}

/** Reorder separate same-thread shapes so each starts near where the last ended. */
export async function shortestOrder() {
  const l = currentLayout();
  if (!l) return;
  try {
    const r = await engine().call<{ order: string[]; saved_mm: number }>("layout.optimize_order", { layout: l });
    if (r.saved_mm <= 0) return info("The sewing order is already about as short as it gets.");
    const now = currentLayout();
    if (!now) return;
    const byId = new Map(now.items.map((it) => [it.id, it]));
    const ordered = r.order.map((id) => byId.get(id)!).filter(Boolean);
    // Anything added while the order was worked out keeps its place at the end.
    const rest = now.items.filter((it) => !r.order.includes(it.id));
    if (await commit({ ...now, items: [...ordered, ...rest] })) info(`Reordered: about ${Math.round(r.saved_mm)} mm less travel between shapes.`);
  } catch (err) {
    fail(err);
  }
}

/** Optimize jumps: each piece's start and end chosen so the jumps between pieces in the same
 *  thread are as short as possible (the sewing order stays as it is: it decides what's on top). */
export async function optimizeJumps() {
  const l = currentLayout();
  if (!l) return;
  try {
    const r = await engine().call<{ changes: Record<string, { geometry?: unknown; params?: Record<string, unknown> }>; before_mm: number; after_mm: number }>(
      "layout.optimize_jumps",
      { layout: l },
      LONG_MS,
    );
    const ids = Object.keys(r.changes);
    // Starts and ends were chosen for the whole design as it was (each next to its neighbours).
    if (currentLayout() !== l) return info("The design changed while optimizing jumps: try again.");
    if (!ids.length || r.after_mm >= r.before_mm - 0.5) return info("The jumps between same-color pieces are already as short as this can make them.");
    const now = currentLayout();
    if (!now) return;
    const next: Layout = {
      ...now,
      items: now.items.map((it) => {
        const c = r.changes[it.id];
        if (!c || !isObject(it)) return it;
        return { ...it, ...(c.geometry ? { geometry: c.geometry } : {}), ...(c.params ? { params: c.params } : {}) } as ObjectItem;
      }),
    };
    if (await commit(next)) {
      info(`Jumps between same-color pieces: ${Math.round(r.before_mm)} mm → ${Math.round(r.after_mm)} mm (${ids.length} piece${ids.length === 1 ? "" : "s"} now start or end somewhere else). Ctrl+Z undoes it.`);
    }
  } catch (err) {
    fail(err);
  }
}

// ---------------------------------------------------------------- 6. stitch editing

let releaseEdit: (() => void) | null = null;

export function startStitchEdit() {
  const s = useStore.getState();
  const it = currentLayout()?.items.find((x) => x.id === s.selectedId);
  if (!it || isObject(it) || isText(it)) return info("Select a placed stitch file first (drawn shapes are edited by their points).");
  endOtherModes("stitchEdit");
  if (s.tool !== "select") s.setTool("select");
  s.setStitchEdit({ id: it.id, selected: [] });
  releaseEdit?.();
  releaseEdit = holdEscape(endStitchEdit);
  // The stitches Rebuild and Limit density make aren't the file's, so no edit can name them.
  const remade = it.ops.some((o) => o.op === "rebuild" || o.op === "density_limit");
  info(
    "Editing stitches: click a stitch (Shift+click for more, or drag a box), drag to move, Delete removes. Esc when done." +
      (remade ? " Stitches that Rebuild or Limit density remade can't be picked: take those repairs off to edit them." : ""),
  );
}

export function endStitchEdit() {
  useStore.getState().setStitchEdit(null);
  releaseEdit?.();
  releaseEdit = null;
}

function addOps(id: string, ops: LayoutOp[]) {
  const l = currentLayout();
  if (!l) return;
  void commit({ ...l, items: l.items.map((it) => (it.id === id ? { ...it, ops: [...it.ops, ...ops] } : it)) });
}

export function deleteSelectedStitches() {
  const e = useStore.getState().stitchEdit;
  if (!e || !e.selected.length) return;
  addOps(e.id, [{ op: "delete_stitches", indices: e.selected }]);
  useStore.getState().setStitchEdit({ ...e, selected: [] });
}

/** Stitches dragged by (dx, dy) mm on screen. The move is kept in the design's own frame (`local`),
 *  so it turns, resizes and mirrors with the design afterwards. */
export function moveSelectedStitches(dx: number, dy: number) {
  const e = useStore.getState().stitchEdit;
  if (!e || !e.selected.length || (!dx && !dy)) return;
  const t = currentLayout()?.items.find((it) => it.id === e.id)?.transform;
  const [lx, ly] = t ? toDesignFrame(t, dx, dy) : [dx, dy];
  const r = (v: number) => Math.round(v * 1000) / 1000;
  // One op per drag, however many stitches move (one op per stitch made big drags megabytes).
  addOps(e.id, [{ op: "move_stitches", indices: [...e.selected], dx_mm: r(lx), dy_mm: r(ly), local: true }]);
}

/** A move on screen as a move in a design's own frame (undoing its turn, mirror and resize). Pure, for tests. */
export function toDesignFrame(t: { rotate: number; scale_x: number; scale_y: number; flip_x: boolean; flip_y: boolean }, dx: number, dy: number): [number, number] {
  const a = (-t.rotate * Math.PI) / 180;
  const rx = dx * Math.cos(a) - dy * Math.sin(a);
  const ry = dx * Math.sin(a) + dy * Math.cos(a);
  return [(rx / (t.scale_x || 1)) * (t.flip_x ? -1 : 1), (ry / (t.scale_y || 1)) * (t.flip_y ? -1 : 1)];
}

// ---------------------------------------------------------------- 8. lettering: on a line, one file per name

/** Put the selected lettering on the selected line (the line is used up). */
export async function textOnLine() {
  const items = selectedItems();
  const text = items.find(isText) as TextItem | undefined;
  const line = items.find((it) => isObject(it) && (it.kind === "run" || (it.kind === "satin" && "nodes" in it.geometry))) as ObjectItem | undefined;
  if (!text || !line) return info("Select the lettering and a line (Shift+click both), then put the text on the line.");
  const g = line.geometry as { nodes: PathNode[]; closed?: boolean };
  const placed = textOnLineItem(text, g.nodes, !!g.closed);
  if (typeof placed === "string") return info(placed);
  const l = currentLayout()!;
  const next: Layout = { ...l, items: l.items.filter((it) => it.id !== line.id).map((it) => (it.id === text.id ? placed : it)) };
  if (await commit(next)) {
    useStore.getState().setSelection(text.id, []);
    info("The text now follows the line. Straight, Arch and the other shapes in its panel put it back.");
  }
}

/** Lettering moved onto a line (its points on the canvas), or why it can't be. The text's turn,
 *  mirror and resize are let go of (the resize is kept in the letter height), and its position
 *  moves to the middle of the line, so turning or resizing it later pivots there. Pure, for tests. */
export function textOnLineItem(text: TextItem, nodes: PathNode[], closed: boolean): TextItem | string {
  if (text.monogram) return "A monogram can't follow a line. Untick Monogram in the Lettering panel first.";
  if (nodes.length < 2) return "Draw a line with at least two points for the text to follow.";
  const r2 = (v: number) => Math.round(v * 100) / 100;
  const xs = nodes.map((n) => n[0]);
  const ys = nodes.map((n) => n[1]);
  const cx = r2((Math.min(...xs) + Math.max(...xs)) / 2);
  const cy = r2((Math.min(...ys) + Math.max(...ys)) / 2);
  const t = text.transform;
  const scale = Math.sqrt(Math.abs((t.scale_x || 1) * (t.scale_y || 1)));
  const size = Math.min(200, Math.max(2, r2(text.size_mm * scale)));
  return {
    ...text,
    size_mm: size,
    transform: { ...IDENTITY, x: cx, y: cy },
    shape: { type: "path", nodes: nodes.map((n) => [r2(n[0] - cx), r2(n[1] - cy), n[2]] as PathNode), closed },
    letters: undefined, // the letters are laid out anew along the line
  };
}

/** A name as a file name: no characters Windows or macOS refuse, no device names (CON, NUL...). */
export function nameFileStem(name: string): string {
  // eslint-disable-next-line no-control-regex
  const s = name.trim().replace(/[\\/:*?"<>|\x00-\x1f]/g, "_").replace(/[. ]+$/, "");
  if (!s) return "_";
  return /^(con|prn|aux|nul|com\d|lpt\d)$/i.test(s) ? `_${s}` : s;
}

/** One machine file per name typed in: the lettering filled with each in turn (feat/names.ts). */
export async function exportNames(names: string[], folder: string, ext: string) {
  await exportList(typedList(names.join("\n")), folder, ext);
}

/** Pick a folder (the installed app), or type one in the browser preview. */
export async function pickFolder(title: string): Promise<string | null> {
  if (!isTauri()) return window.prompt(title, loadPrefs().browseFolder ?? "") || null;
  const r = await openDialog({ directory: true, title });
  return typeof r === "string" ? r : null;
}

// ---------------------------------------------------------------- 9. color sets (colorways)

export async function saveColorway(name: string) {
  const l = currentLayout();
  if (!l || !name.trim()) return;
  const items: Colorway["items"] = {};
  for (const it of l.items) items[it.id] = { thread: isObject(it) || isText(it) ? it.thread : undefined, threads: it.threads };
  const rest = (l.colorways ?? []).filter((c) => c.name !== name.trim());
  if (await commit({ ...l, colorways: [...rest, { name: name.trim(), items }] })) info(`Saved the colors as "${name.trim()}".`);
}

export async function applyColorway(name: string) {
  const l = currentLayout();
  const cw = l?.colorways?.find((c) => c.name === name);
  if (!l || !cw) return;
  await commit({
    ...l,
    items: l.items.map((it) => {
      const saved = cw.items[it.id];
      if (!saved) return it;
      return { ...it, threads: saved.threads, ...(saved.thread && (isObject(it) || isText(it)) ? { thread: saved.thread } : {}) } as LayoutItem;
    }),
  });
}

export async function deleteColorway(name: string) {
  const l = currentLayout();
  if (l) await commit({ ...l, colorways: (l.colorways ?? []).filter((c) => c.name !== name) });
}

// ---------------------------------------------------------------- 10. guides

export async function setGuides(guides: Guide[]) {
  const l = currentLayout();
  if (l) await commit({ ...l, guides });
}

export const guidesOf = (): Guide[] => currentLayout()?.guides ?? [];

export function clearGuides() {
  if (guidesOf().length) void setGuides([]);
}

export { newId, currentDoc };
