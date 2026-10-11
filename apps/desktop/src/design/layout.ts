/** Pure edits on a Layout. Each returns a new layout; the store keeps the undo history. */

import {
  Kind,
  type Design,
  type Doc,
  type FileItem,
  type Layout,
  type LayoutItem,
  type LayoutOp,
  type ObjectItem,
  type RefImage,
  type Thread,
  type Transform,
} from "./types";
import { isObject, type PathNode } from "./types";
import { nodeBounds } from "./paths";

export const IDENTITY: Transform = { x: 0, y: 0, rotate: 0, scale_x: 1, scale_y: 1, flip_x: false, flip_y: false };

/** Offset for a newly added design so it doesn't sit exactly on top of the last one. */
export const ADD_OFFSET_MM = 10;
/** The engine's default fabric when a design doesn't name one. */
export const DEFAULT_FABRIC = "woven";

let counter = 0;
export const newId = () => `i${Date.now().toString(36)}${(counter++).toString(36)}`;

export function newItem(path: string, transform: Partial<Transform> = {}): FileItem {
  return { id: newId(), kind: "file", path, transform: { ...IDENTITY, ...transform }, threads: [], ops: [] };
}

/** A layout with one stitch file, or an empty one to draw on. */
export function newLayout(path?: string): Layout {
  return {
    items: path ? [newItem(path)] : [],
    merge_colors: false,
    color_sort: false,
    basting: { enabled: false, margin_mm: 5 },
  };
}

export function newDoc(path?: string): Doc {
  return { layout: newLayout(path), images: [] };
}

/** Add a drawn object at the end of the sewing order. */
export function addObject(layout: Layout, obj: Omit<ObjectItem, "id" | "transform" | "threads" | "ops">): { layout: Layout; id: string } {
  const item = { ...obj, id: newId(), transform: { ...IDENTITY }, threads: [], ops: [] } as ObjectItem;
  return { layout: { ...layout, items: [...layout.items, item] }, id: item.id };
}

export function updateObject(layout: Layout, id: string, fn: (it: ObjectItem) => ObjectItem): Layout {
  return { ...layout, items: layout.items.map((it) => (it.id === id && it.kind && it.kind !== "file" ? fn(it as ObjectItem) : it)) };
}

/** A short name for an item, as the panel and canvas show it. */
export function itemLabel(it: LayoutItem, index: number): string {
  if (it.kind === "run") return it.name || `Running stitch ${index + 1}`;
  if (it.kind === "satin") return it.name || `Satin ${index + 1}`;
  if (it.kind === "fill") return it.name || `Fill ${index + 1}`;
  if (it.kind === "applique") return it.name || `Applique ${index + 1}`;
  if (it.kind === "text") return it.name || `“${it.text.trim().slice(0, 24)}”`;
  return (it as FileItem).path.split(/[\\/]/).pop() ?? "Design";
}

/** Outline points for a ready-made shape centred on (cx, cy). */
export function shapeNodes(shape: "rectangle" | "circle" | "star", cx: number, cy: number, size: number): PathNode[] {
  const r = size / 2;
  if (shape === "rectangle") {
    const h = r * 0.7;
    return [[cx - r, cy - h, "c"], [cx + r, cy - h, "c"], [cx + r, cy + h, "c"], [cx - r, cy + h, "c"]].map(
      (n) => [round2(n[0] as number), round2(n[1] as number), n[2]] as PathNode,
    );
  }
  if (shape === "circle") {
    // Eight curve points make a smooth circle with the Catmull-Rom curve rule.
    return Array.from({ length: 8 }, (_, i) => {
      const a = (i / 8) * 2 * Math.PI;
      return [round2(cx + r * Math.cos(a)), round2(cy + r * Math.sin(a)), "s"] as PathNode;
    });
  }
  return Array.from({ length: 10 }, (_, i) => {
    const a = -Math.PI / 2 + (i / 10) * 2 * Math.PI;
    const rr = i % 2 === 0 ? r : r * 0.45;
    return [round2(cx + rr * Math.cos(a)), round2(cy + rr * Math.sin(a)), "c"] as PathNode;
  });
}

// ---------------------------------------------------------------- reference pictures

export function addImage(images: RefImage[], img: Omit<RefImage, "id">): { images: RefImage[]; id: string } {
  const id = newId();
  return { images: [...images, { ...img, id }], id };
}

export function updateImage(images: RefImage[], id: string, patch: Partial<RefImage>): RefImage[] {
  return images.map((im) => (im.id === id ? { ...im, ...patch } : im));
}

export function removeImage(images: RefImage[], id: string): RefImage[] {
  return images.filter((im) => im.id !== id);
}

/**
 * Scale a picture so that two points on it, `measuredMm` apart now, become `realMm` apart.
 * The picture's centre stays put.
 */
export function scaleImageByMeasure(img: RefImage, measuredMm: number, realMm: number): RefImage {
  if (measuredMm <= 0 || realMm <= 0) return img;
  const f = realMm / measuredMm;
  return { ...img, width_mm: img.width_mm * f, height_mm: img.height_mm * f };
}

export function addItem(layout: Layout, path: string): Layout {
  const n = layout.items.length;
  return { ...layout, items: [...layout.items, newItem(path, { x: ADD_OFFSET_MM * n, y: ADD_OFFSET_MM * n })] };
}

export function updateItem(layout: Layout, id: string, fn: (it: LayoutItem) => LayoutItem): Layout {
  return { ...layout, items: layout.items.map((it) => (it.id === id ? fn(it) : it)) };
}

export function updateTransform(layout: Layout, id: string, patch: Partial<Transform>): Layout {
  return updateItem(layout, id, (it) => ({ ...it, transform: { ...it.transform, ...patch } }));
}

// Drawn objects are edited like any vector shape: moving, turning, resizing and mirroring change
// their points (so node editing always works on what you see). Stitch files keep a transform,
// because their stitches can only be moved, not regenerated.

/** All point lists of a drawn object. */
export function objectNodeLists(o: ObjectItem): PathNode[][] {
  if (o.kind === "run") return [o.geometry.nodes];
  if (o.kind === "satin") return [o.geometry.rail_a, o.geometry.rail_b];
  return [o.geometry.outline, ...(o.geometry.holes ?? [])];
}

export function objectCenter(o: ObjectItem): [number, number] {
  const b = nodeBounds(objectNodeLists(o));
  return b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : [0, 0];
}

/** Apply `fn` to every point of a drawn object. */
export function mapObjectNodes(o: ObjectItem, fn: (x: number, y: number) => [number, number]): ObjectItem {
  const m = (ns: PathNode[]) => ns.map((n) => [...fn(n[0], n[1]).map(round2), n[2]] as PathNode);
  if (o.kind === "run") return { ...o, geometry: { ...o.geometry, nodes: m(o.geometry.nodes) } };
  if (o.kind === "satin") return { ...o, geometry: { rail_a: m(o.geometry.rail_a), rail_b: m(o.geometry.rail_b) } };
  return { ...o, geometry: { outline: m(o.geometry.outline), holes: o.geometry.holes?.map(m) } };
}

/** A fill with its stitch angle changed (kept in 0..179°); other objects as they are. */
function withFillAngle(o: ObjectItem, f: (deg: number) => number): ObjectItem {
  if (o.kind !== "fill") return o;
  const a = f(o.params.angle_deg ?? 45);
  return { ...o, params: { ...o.params, angle_deg: Math.round((((a % 180) + 180) % 180) * 100) / 100 } };
}

function onItem(layout: Layout, id: string, file: (it: LayoutItem) => LayoutItem, obj: (o: ObjectItem) => ObjectItem): Layout {
  return updateItem(layout, id, (it) => (isObject(it) ? obj(it) : file(it)));
}

export function moveBy(layout: Layout, id: string, dx: number, dy: number): Layout {
  return onItem(
    layout,
    id,
    (it) => ({ ...it, transform: { ...it.transform, x: round2(it.transform.x + dx), y: round2(it.transform.y + dy) } }),
    (o) => mapObjectNodes(o, (x, y) => [x + dx, y + dy]),
  );
}

export function rotateBy(layout: Layout, id: string, deg: number): Layout {
  return onItem(
    layout,
    id,
    (it) => ({ ...it, transform: { ...it.transform, rotate: normDeg(it.transform.rotate + deg) } }),
    (o) => {
      const [cx, cy] = objectCenter(o);
      const a = (deg * Math.PI) / 180;
      const [ca, sa] = [Math.cos(a), Math.sin(a)];
      // A fill's stitch direction turns with it.
      return withFillAngle(
        mapObjectNodes(o, (x, y) => [cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca]),
        (ang) => ang + deg,
      );
    },
  );
}

/** Mirror as seen on screen. After a rotation, a screen mirror also flips the rotation direction. */
export function mirror(layout: Layout, id: string, axis: "x" | "y"): Layout {
  return onItem(
    layout,
    id,
    (it) => {
      const t = it.transform;
      return {
        ...it,
        transform: axis === "x" ? { ...t, flip_x: !t.flip_x, rotate: normDeg(-t.rotate) } : { ...t, flip_y: !t.flip_y, rotate: normDeg(-t.rotate) },
      };
    },
    (o) => {
      const [cx, cy] = objectCenter(o);
      // A mirrored fill's rows mirror too.
      return withFillAngle(
        mapObjectNodes(o, (x, y) => (axis === "x" ? [2 * cx - x, y] : [x, 2 * cy - y])),
        (ang) => -ang,
      );
    },
  );
}

export function scaleBy(layout: Layout, id: string, fx: number, fy = fx): Layout {
  return onItem(
    layout,
    id,
    (it) => ({ ...it, transform: { ...it.transform, scale_x: round4(it.transform.scale_x * fx), scale_y: round4(it.transform.scale_y * fy) } }),
    (o) => {
      const [cx, cy] = objectCenter(o);
      return mapObjectNodes(o, (x, y) => [cx + (x - cx) * fx, cy + (y - cy) * fy]);
    },
  );
}

export function removeItem(layout: Layout, id: string): Layout {
  return { ...layout, items: layout.items.filter((it) => it.id !== id) };
}

export function duplicateItem(layout: Layout, id: string): { layout: Layout; id: string } {
  const src = layout.items.find((it) => it.id === id);
  if (!src) return { layout, id };
  const copy: LayoutItem = {
    ...structuredClone(src),
    id: newId(),
    transform: { ...src.transform, x: src.transform.x + ADD_OFFSET_MM, y: src.transform.y + ADD_OFFSET_MM },
  };
  const i = layout.items.indexOf(src);
  return { layout: { ...layout, items: [...layout.items.slice(0, i + 1), copy, ...layout.items.slice(i + 1)] }, id: copy.id };
}

export type RepeatSpec =
  /** Copies in a grid, `step` apart centre to centre (mm). */
  | { kind: "row"; columns: number; rows: number; step_x: number; step_y: number }
  /** Copies round a circle below the original (a carousel), each turned to face out if `turn`. */
  | { kind: "circle"; count: number; radius: number; turn: boolean }
  /** Four-way mirror: copies mirrored left-right, top-bottom and both, `gap` apart. */
  | { kind: "mirror4"; gap: number };

/** Copies of one item placed by a repeat pattern, inserted after it in the sewing order.
 *  `center` and `size` are the item's on-screen centre and size (mm). */
export function repeatItem(layout: Layout, id: string, center: [number, number], size: [number, number], spec: RepeatSpec): { layout: Layout; ids: string[] } {
  const src = layout.items.find((it) => it.id === id);
  if (!src) return { layout, ids: [] };
  const [cx, cy] = center;
  // Each copy: (where its centre goes, how much to turn it, which way to mirror it).
  const places: { at: [number, number]; turn: number; flip: ("x" | "y")[] }[] = [];
  if (spec.kind === "row") {
    for (let r = 0; r < Math.max(1, spec.rows); r++)
      for (let c = 0; c < Math.max(1, spec.columns); c++) if (r || c) places.push({ at: [cx + c * spec.step_x, cy + r * spec.step_y], turn: 0, flip: [] });
  } else if (spec.kind === "circle") {
    const ox = cx;
    const oy = cy + spec.radius;
    for (let k = 1; k < Math.max(2, spec.count); k++) {
      const a = (2 * Math.PI * k) / spec.count;
      const [ca, sa] = [Math.cos(a), Math.sin(a)];
      places.push({ at: [ox + (cx - ox) * ca - (cy - oy) * sa, oy + (cx - ox) * sa + (cy - oy) * ca], turn: spec.turn ? (360 * k) / spec.count : 0, flip: [] });
    }
  } else {
    const ox = cx + size[0] / 2 + spec.gap / 2;
    const oy = cy + size[1] / 2 + spec.gap / 2;
    places.push({ at: [2 * ox - cx, cy], turn: 0, flip: ["x"] });
    places.push({ at: [cx, 2 * oy - cy], turn: 0, flip: ["y"] });
    places.push({ at: [2 * ox - cx, 2 * oy - cy], turn: 0, flip: ["x", "y"] });
  }
  let out = layout;
  const ids: string[] = [];
  let after = layout.items.indexOf(src);
  for (const pl of places) {
    const copy: LayoutItem = { ...structuredClone(src), id: newId() };
    after += 1;
    out = { ...out, items: [...out.items.slice(0, after), copy, ...out.items.slice(after)] };
    if (pl.turn) out = rotateBy(out, copy.id, pl.turn);
    for (const axis of pl.flip) out = mirror(out, copy.id, axis);
    out = moveBy(out, copy.id, round2(pl.at[0] - cx), round2(pl.at[1] - cy));
    ids.push(copy.id);
  }
  return { layout: out, ids };
}

export type TogetherOp = { rotate?: number; mirror?: "x" | "y"; scale?: number; move?: [number, number] };

/** Turn, mirror, resize or move several items as one, about their common centre `c` (mm).
 *  `centers` are the items' own centres on screen. Each item turns (or flips, or grows) about its
 *  own centre, then moves so the whole set keeps its arrangement. */
export function transformTogether(layout: Layout, ids: string[], centers: Record<string, [number, number]>, c: [number, number], op: TogetherOp): Layout {
  let out = layout;
  for (const id of ids) {
    const p = centers[id];
    if (!p) continue;
    let q: [number, number] = p;
    if (op.rotate) {
      out = rotateBy(out, id, op.rotate);
      const a = (op.rotate * Math.PI) / 180;
      const [dx, dy] = [p[0] - c[0], p[1] - c[1]];
      q = [c[0] + dx * Math.cos(a) - dy * Math.sin(a), c[1] + dx * Math.sin(a) + dy * Math.cos(a)];
    }
    if (op.mirror) {
      out = mirror(out, id, op.mirror);
      q = op.mirror === "x" ? [2 * c[0] - p[0], p[1]] : [p[0], 2 * c[1] - p[1]];
    }
    if (op.scale) {
      out = scaleBy(out, id, op.scale);
      q = [c[0] + (p[0] - c[0]) * op.scale, c[1] + (p[1] - c[1]) * op.scale];
    }
    if (op.move) q = [p[0] + op.move[0], p[1] + op.move[1]];
    if (q[0] !== p[0] || q[1] !== p[1]) out = moveBy(out, id, round2(q[0] - p[0]), round2(q[1] - p[1]));
  }
  return out;
}

/** Put items in a group (they select and move as one), or take them out (group null). */
export function setGroup(layout: Layout, ids: string[], group: string | null): Layout {
  return { ...layout, items: layout.items.map((it) => (ids.includes(it.id) ? ({ ...it, group: group ?? undefined } as LayoutItem) : it)) };
}

/** Move a design earlier or later in the sewing order. */
export function reorder(layout: Layout, id: string, dir: -1 | 1): Layout {
  const i = layout.items.findIndex((it) => it.id === id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= layout.items.length) return layout;
  const items = [...layout.items];
  [items[i], items[j]] = [items[j], items[i]];
  return { ...layout, items };
}

type Sources = { item: number; block: number }[];

/** Recolor every source block behind a displayed color (several after combining colors). */
export function recolor(layout: Layout, sources: Sources, thread: Thread | null): Layout {
  const items = layout.items.map((it, i) => {
    const mine = sources.filter((s) => s.item === i);
    if (!mine.length) return it;
    const threads = [...it.threads];
    for (const s of mine) {
      while (threads.length <= s.block) threads.push(null);
      threads[s.block] = thread;
    }
    return { ...it, threads };
  });
  return { ...layout, items };
}

export function clearRecolors(layout: Layout): Layout {
  return { ...layout, items: layout.items.map((it) => ({ ...it, threads: [] })) };
}

export function hasRecolors(layout: Layout): boolean {
  return layout.items.some((it) => it.threads.some(Boolean));
}

export function deleteColor(layout: Layout, sources: Sources): Layout {
  return addOps(layout, sources.map((s) => [s.item, { op: "delete_block", block: s.block } as LayoutOp]));
}

/**
 * Insert a stop or trim after the stitch at the player position. Added records (ties, basting)
 * have no source, so we use the nearest earlier real stitch.
 */
export function insertAt(layout: Layout, design: Design, record: number, command: "stop" | "trim"): Layout | null {
  const { item, src, kind } = design.records;
  if (!item || !src) return null;
  for (let r = Math.min(record, kind.length - 1); r >= 0; r--) {
    if (src[r] >= 0 && item[r] >= 0 && kind[r] === Kind.Stitch) {
      return addOps(layout, [[item[r], { op: "insert", after: src[r], command }]]);
    }
  }
  return null;
}

/** Add trims to long untrimmed jumps in every design (replaces an earlier setting). */
export function jumpsToTrims(layout: Layout, minMm: number | null): Layout {
  return {
    ...layout,
    items: layout.items.map((it) => {
      const ops = it.ops.filter((o) => o.op !== "jumps_to_trims");
      return { ...it, ops: minMm === null ? ops : [...ops, { op: "jumps_to_trims", min_mm: minMm }] };
    }),
  };
}

export function jumpsToTrimsSetting(layout: Layout): number | null {
  for (const it of layout.items) {
    const o = it.ops.find((x) => x.op === "jumps_to_trims");
    if (o && o.op === "jumps_to_trims") return o.min_mm;
  }
  return null;
}

function addOps(layout: Layout, add: [number, LayoutOp][]): Layout {
  return {
    ...layout,
    items: layout.items.map((it, i) => {
      const mine = add.filter(([k]) => k === i).map(([, op]) => op);
      return mine.length ? { ...it, ops: [...it.ops, ...mine] } : it;
    }),
  };
}

/** Topmost design whose box contains the point (mm), or null. Later designs are drawn on top. */
export function hitTest(design: Design, x: number, y: number, padMm = 0): number | null {
  const items = design.items ?? [];
  for (let i = items.length - 1; i >= 0; i--) {
    const b = items[i].bounds_mm;
    if (b && x >= b[0] - padMm && x <= b[2] + padMm && y >= b[1] - padMm && y <= b[3] + padMm) return i;
  }
  return null;
}

// ---------------------------------------------------------------- undo history

export type History = { past: Doc[]; present: Doc | null; future: Doc[] };
export const HISTORY_LIMIT = 100;

export function pushHistory(h: History, next: Doc): History {
  if (h.present === next) return h;
  const past = h.present ? [...h.past, h.present].slice(-HISTORY_LIMIT) : h.past;
  return { past, present: next, future: [] };
}

export function undo(h: History): History {
  if (!h.past.length || !h.present) return h;
  return { past: h.past.slice(0, -1), present: h.past[h.past.length - 1], future: [h.present, ...h.future] };
}

export function redo(h: History): History {
  if (!h.future.length) return h;
  return { past: h.present ? [...h.past, h.present] : h.past, present: h.future[0], future: h.future.slice(1) };
}

// "+ 0" turns -0 into 0, so rotated points compare and serialise cleanly.
const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
const round4 = (v: number) => Math.round(v * 10000) / 10000;
const normDeg = (d: number) => {
  const r = ((d % 360) + 360) % 360;
  return r > 180 ? r - 360 : r;
};
