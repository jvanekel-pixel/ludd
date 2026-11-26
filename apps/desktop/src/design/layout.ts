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
  type TextItem,
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
  if (it.kind === "text") return it.name || `“${it.text.trim().replace(/\s*[\r\n]+\s*/g, " ").slice(0, 24)}”`;
  return (it as FileItem).name || ((it as FileItem).path.split(/[\\/]/).pop() ?? "Design");
}

/** Give an item your own name (an empty name puts the standard one back). */
export function renameItem(layout: Layout, id: string, name: string): Layout {
  const n = name.trim().slice(0, 80);
  return updateItem(layout, id, (it) => {
    const { name: _old, ...rest } = it as LayoutItem & { name?: string };
    return (n ? { ...rest, name: n } : rest) as LayoutItem;
  });
}

/** Outline points for a ready-made shape (see shapes.ts). */
export { shapeNodes } from "./shapes";

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

/** Move an item so its middle (`center`, mm, as the engine reports it) lands on `at` (the hoop's
 *  middle by default). Stitch files keep the place their maker gave them, which is often not the
 *  middle of the hoop (many PES files start at a corner). Unchanged if it's already there. */
export function centreItem(layout: Layout, id: string, center: [number, number], at: [number, number] = [0, 0]): Layout {
  const dx = at[0] - center[0];
  const dy = at[1] - center[1];
  if (Math.hypot(dx, dy) < 0.5) return layout;
  return updateItem(layout, id, (it) => ({ ...it, transform: { ...it.transform, x: round2(it.transform.x + dx), y: round2(it.transform.y + dy) } }));
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
  if (o.kind === "satin") return "nodes" in o.geometry ? [o.geometry.nodes] : [o.geometry.rail_a, o.geometry.rail_b];
  return [o.geometry.outline, ...(o.geometry.holes ?? [])];
}

export function objectCenter(o: ObjectItem): [number, number] {
  const b = nodeBounds(objectNodeLists(o));
  return b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : [0, 0];
}

/** Apply `fn` to every point of a drawn object, and to the points kept in its settings (where it
 *  starts and ends, its direction dots), so they move, turn and resize with it. */
export function mapObjectNodes(o: ObjectItem, fn: (x: number, y: number) => [number, number]): ObjectItem {
  const moved = mapObjectPoints(o, fn);
  const p = moved.params as Record<string, unknown>;
  const pt = (v: unknown) => (Array.isArray(v) && v.length >= 2 && typeof v[0] === "number" && typeof v[1] === "number" ? (fn(v[0], v[1]).map(round2) as [number, number]) : undefined);
  const patch: Record<string, unknown> = {};
  for (const k of ["start_mm", "end_mm"]) if (pt(p[k])) patch[k] = pt(p[k]);
  const line = p.angle_line as [number, number][] | undefined;
  if (Array.isArray(line) && line.length === 2 && pt(line[0]) && pt(line[1])) patch.angle_line = [pt(line[0]), pt(line[1])];
  return Object.keys(patch).length ? ({ ...moved, params: { ...moved.params, ...patch } } as ObjectItem) : moved;
}

function mapObjectPoints(o: ObjectItem, fn: (x: number, y: number) => [number, number]): ObjectItem {
  const m = (ns: PathNode[]) => ns.map((n) => [...fn(n[0], n[1]).map(round2), n[2]] as PathNode);
  if (o.kind === "run") return { ...o, geometry: { ...o.geometry, nodes: m(o.geometry.nodes) } };
  if (o.kind === "satin")
    return "nodes" in o.geometry
      ? { ...o, geometry: { ...o.geometry, nodes: m(o.geometry.nodes) } }
      : { ...o, geometry: { rail_a: m(o.geometry.rail_a), rail_b: m(o.geometry.rail_b) } };
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
      const out = mapObjectNodes(o, (x, y) => [cx + (x - cx) * fx, cy + (y - cy) * fy]);
      // A satin ribbon gets wider and narrower with it.
      if (out.kind === "satin" && "nodes" in out.geometry)
        return { ...out, geometry: { ...out.geometry, width_mm: round2(Math.min(12, Math.max(0.5, out.geometry.width_mm * Math.sqrt(Math.abs(fx * fy))))) } };
      return out;
    },
  );
}

/** The whole design made `s` times its size about the middle of its stitches (every item resized
 *  and moved in towards that middle), e.g. to fit a hoop it's a hair too big for. */
export function scaleDesign(layout: Layout, design: Design, s: number): Layout {
  const b = design.info.bounds_mm;
  const cx = (b[0] + b[2]) / 2;
  const cy = (b[1] + b[3]) / 2;
  let out = layout;
  layout.items.forEach((it, i) => {
    const c = design.items?.[i]?.center_mm;
    if (!c) return;
    out = scaleBy(out, it.id, s);
    out = moveBy(out, it.id, (cx + (c[0] - cx) * s) - c[0], (cy + (c[1] - cy) * s) - c[1]);
  });
  return out;
}

/** How much smaller (a factor under 1) the design must be to fit the hoop, if it's only a little too
 *  big (at most `maxOver`, 5%); null if it fits already or is too far over for a quiet resize. */
export function shrinkToFit(info: { width_mm: number; height_mm: number }, hoop: { width_mm: number; height_mm: number }, maxOver = 0.05): number | null {
  const s = Math.min(hoop.width_mm / info.width_mm, hoop.height_mm / info.height_mm);
  if (!(s < 1) || s < 1 / (1 + maxOver)) return null;
  // A little under, so rounding to 0.1 mm stitches can't push it back over.
  return Math.floor(s * 0.998 * 1000) / 1000;
}

export function removeItem(layout: Layout, id: string): Layout {
  return { ...layout, items: layout.items.filter((it) => it.id !== id) };
}

export function duplicateItem(layout: Layout, id: string): { layout: Layout; id: string } {
  const src = layout.items.find((it) => it.id === id);
  if (!src) return { layout, id };
  const copy: LayoutItem = { ...structuredClone(src), id: newId() };
  const i = layout.items.indexOf(src);
  const next = { ...layout, items: [...layout.items.slice(0, i + 1), copy, ...layout.items.slice(i + 1)] };
  // Offset the copy the way a move does: drawn shapes move their points (so they keep no transform
  // of their own), stitch files and lettering move their transform.
  return { layout: moveBy(next, copy.id, ADD_OFFSET_MM, ADD_OFFSET_MM), id: copy.id };
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

/** `stretch`: [across, down] factors on the design's axes, about `c` (a side handle: c is the
 *  opposite side, which stays put). */
export type TogetherOp = { rotate?: number; mirror?: "x" | "y"; scale?: number; stretch?: [number, number]; move?: [number, number] };

/** Stretch an item across (fx) and down (fy) as it's shown. A drawn shape's points stretch on the
 *  design's axes; a stitch file or lettering stretches its own axes, so one turned on its side
 *  swaps them (turned at another angle, the nearer axis stretches). */
export function stretchItem(layout: Layout, id: string, fx: number, fy: number): Layout {
  const it = layout.items.find((x) => x.id === id);
  if (!it) return layout;
  if (it.kind && it.kind !== "file" && it.kind !== "text") return scaleBy(layout, id, fx, fy);
  const turn = ((((it.transform.rotate % 180) + 180) % 180) + 180) % 180;
  const sideways = turn > 45 && turn < 135;
  return sideways ? scaleBy(layout, id, fy, fx) : scaleBy(layout, id, fx, fy);
}

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
    // Where the item's centre is once it's resized: a drawn shape grows about the middle of its
    // points, which can sit a little off the middle of its stitches (`p`).
    let at: [number, number] = p;
    const grow = op.scale ? [op.scale, op.scale] : op.stretch;
    if (grow) {
      const it = out.items.find((x) => x.id === id);
      const o = it && isObject(it) ? objectCenter(it) : p;
      out = op.scale ? scaleBy(out, id, op.scale) : stretchItem(out, id, grow[0], grow[1]);
      at = [o[0] + (p[0] - o[0]) * grow[0], o[1] + (p[1] - o[1]) * grow[1]];
      q = [c[0] + (p[0] - c[0]) * grow[0], c[1] + (p[1] - c[1]) * grow[1]];
    }
    if (op.move) q = [p[0] + op.move[0], p[1] + op.move[1]];
    if (q[0] !== at[0] || q[1] !== at[1]) out = moveBy(out, id, round2(q[0] - at[0]), round2(q[1] - at[1]));
  }
  return out;
}

/** Put items in a group (they select and move as one), or take them out (group null). */
export function setGroup(layout: Layout, ids: string[], group: string | null): Layout {
  return { ...layout, items: layout.items.map((it) => (ids.includes(it.id) ? ({ ...it, group: group ?? undefined } as LayoutItem) : it)) };
}

/** Move a design earlier or later in the sewing order. */
/** Move an item to position `to` in the sewing order (0 = sewn first). */
export function moveItem(layout: Layout, id: string, to: number): Layout {
  const from = layout.items.findIndex((it) => it.id === id);
  const at = Math.max(0, Math.min(layout.items.length - 1, Math.round(to)));
  if (from < 0 || at === from) return layout;
  const items = [...layout.items];
  const [it] = items.splice(from, 1);
  items.splice(at, 0, it);
  return { ...layout, items };
}

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

/** Lettering without the colors given to single letters (their moves and turns stay). */
function withoutLetterThreads(text: TextItem): TextItem {
  if (!Object.values(text.letter_edits ?? {}).some((e) => e.thread)) return text;
  const edits = Object.entries(text.letter_edits!)
    .map(([letter, { thread: _own, ...rest }]) => [letter, rest] as const)
    .filter(([, rest]) => Object.keys(rest).length);
  const { letter_edits: _old, ...plain } = text;
  return edits.length ? { ...plain, letter_edits: Object.fromEntries(edits) } : plain;
}

export function clearRecolors(layout: Layout): Layout {
  return { ...layout, items: layout.items.map((it) => ({ ...(it.kind === "text" ? withoutLetterThreads(it) : it), threads: [] })) };
}

export function hasRecolors(layout: Layout): boolean {
  return layout.items.some((it) => it.threads.some(Boolean) || (it.kind === "text" && Object.values(it.letter_edits ?? {}).some((e) => e.thread)));
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
      const it = layout.items[item[r]];
      const op: LayoutOp = { op: "insert", after: src[r], command };
      // Drawn shapes and lettering: remember how many records the item has, so the stop is left
      // out (with a note) rather than landing somewhere else once the shape is changed.
      if (it && it.kind && it.kind !== "file") {
        let n = 0;
        for (let k = 0; k < kind.length; k++) if (item[k] === item[r] && src[k] >= n) n = src[k] + 1;
        op.n = n;
      }
      return addOps(layout, [[item[r], op]]);
    }
  }
  return null;
}

/** Add trims to long untrimmed jumps in every design, including ones added later (null: off). */
export function jumpsToTrims(layout: Layout, minMm: number | null): Layout {
  return {
    ...layout,
    jumps_to_trims: minMm,
    // Older projects kept it as an op on each design: the layout-wide setting replaces those.
    items: layout.items.map((it) => (it.ops.some((o) => o.op === "jumps_to_trims") ? { ...it, ops: it.ops.filter((o) => o.op !== "jumps_to_trims") } : it)),
  };
}

export function jumpsToTrimsSetting(layout: Layout): number | null {
  if (layout.jumps_to_trims != null) return layout.jumps_to_trims;
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
