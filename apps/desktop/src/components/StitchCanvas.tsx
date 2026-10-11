import { Application, Container, Graphics, Sprite, Text, Texture } from "pixi.js";
import { useEffect, useRef } from "react";
import {
  addText,
  commit,
  currentDoc,
  currentLayout,
  finishAngle,
  pickItem,
  selectionGeometry,
  insertNode,
  moveNode,
  nodeLists,
  penAdd,
  penFinish,
  setPicture,
  toggleNodeKind,
  type NodeList,
} from "../actions";
import { gridLines, gridSpacing, PX_PER_MM_ACTUAL } from "../design/grid";
import { hitTest, moveBy, rotateBy, scaleBy, transformTogether } from "../design/layout";
import { heatColor } from "../design/heat";
import { hoopFit } from "../design/machine";
import { flatten, spanAt, type Pt } from "../design/paths";
import { chunkBlocks, visibleRecords, type Chunk } from "../design/player";
import { threadLayers } from "../design/threadLook";
import { buildThreadChunk, showUpTo, type ThreadChunk } from "./threadRender";
import { isObject, Kind, type Design, type Heatmap, type Hoop, type NodeKind, type ObjectItem, type PathNode, type RefImage } from "../design/types";
import { clamp, fitView, MAX_SCALE, MIN_SCALE, zoomAt, type View } from "../design/view";
import { holdEscape } from "../escape";
import { selectCanvasDark, selectHoop, useStore, type Ghost, type Pen } from "../store";

const TRAVEL_COLOR = 0x8a8a8a; // trimmed travel: the thread is cut, nothing is left
const JUMP_COLOR = 0xe08a00; // untrimmed jump: a thread is left across the fabric
const TRIM_COLOR = 0xd9381e;
const STOP_COLOR = 0xd9381e;
const HOOP_BAD_COLOR = 0xc0392b;
const HANDLE_FILL = 0xc8ff2e;
const ENTRY_COLOR = 0x2f8f4e;
const EXIT_COLOR = 0xd9381e;

/** Lines drawn over the design: ink on light fabric, bone and yellow on dark. */
const PALETTES = {
  light: {
    select: 0x121114,
    hoop: 0x6b665e,
    ghost: 0x4f7300, // a deep yellow-green that reads on light fabric
    gridMinor: { color: 0x8f877a, alpha: 0.18 },
    gridMajor: { color: 0x6b6357, alpha: 0.42 },
  },
  dark: {
    select: 0xeee9df,
    hoop: 0xb5aea3,
    ghost: 0xc8ff2e,
    gridMinor: { color: 0xeee9df, alpha: 0.07 },
    gridMajor: { color: 0xeee9df, alpha: 0.18 },
  },
};
let C = PALETTES.light;
const ZOOM_STEP = 1.25;
const HANDLE_PX = 9;
const NODE_PX = 8;
const ROTATE_KNOB_PX = 26;
const OBJECT_BOX_PAD_PX = 10; // keeps scale handles off a shape's own corner points
const DRAG_THRESHOLD_PX = 3;
const DIM_ALPHA = 0.25;
const SNAP_PX = 7;

type Scene = {
  app: Application;
  grid: Graphics; // screen space, behind the world
  world: Container;
  pictures: Container;
  hoop: Graphics;
  stitches: Container;
  chunks: Chunk[];
  full: Container[]; // one per chunk, fully drawn
  /** Realistic thread: each chunk's stitches as sprites (null in the flat view). */
  real: (ThreadChunk | null)[];
  /** Needle points (P). */
  points: Graphics;
  partial: Graphics; // the chunk under the playhead, drawn up to it
  jumps: Graphics;
  needle: Graphics;
  overlay: Graphics; // selection box, nodes, pen preview
  heat: Container; // density map, over the stitches
  split: Container; // hoopings of a split design, while saving it
  design: Design | null;
  view: View;
  /** True until the user pans or zooms: resizes re-fit instead of keeping the old view. */
  autoFit: boolean;
};

/** A selected thing's frame: four corners (clockwise from top-left), centre and rotate knob. */
type Frame = {
  kind: "item" | "image";
  index: number;
  id: string;
  /** Everything the frame holds (several with Shift+click, Ctrl+A or a group). */
  indices: number[];
  ids: string[];
  corners: Pt[];
  center: Pt;
  knob: Pt;
  up: Pt;
  locked: boolean;
};

type Drag =
  | { kind: "pan"; x: number; y: number; moved: boolean; deselect: boolean }
  | { kind: "move" | "scale" | "rotate"; frame: Frame; startX: number; startY: number; ghost: Container | null; moved: boolean }
  | { kind: "node"; id: string; list: NodeList; index: number; startX: number; startY: number; moved: boolean; at: Pt };

// ---------------------------------------------------------------- textures for pictures

const textures = new Map<string, Texture>();
const loading = new Set<string>();

function textureFor(img: RefImage, onReady: () => void): Texture | null {
  const hit = textures.get(img.data_url);
  if (hit) return hit;
  if (!loading.has(img.data_url)) {
    loading.add(img.data_url);
    const el = new Image();
    el.onload = () => {
      textures.set(img.data_url, Texture.from(el));
      loading.delete(img.data_url);
      onReady();
    };
    el.src = img.data_url;
  }
  return null;
}

// ---------------------------------------------------------------- drawing helpers

/** Draw records [start, end) as thread; jumps and trims lift the needle. `only` limits to one item. */
function drawStitches(g: Graphics, d: Design, start: number, end: number, color: string, only?: number) {
  const { x, y, kind, item } = d.records;
  const keep = (i: number) => only === undefined || item?.[i] === only;
  // Each layer (edge, body, sheen) needs the path again: a stroke consumes it.
  for (const layer of threadLayers(color, useStore.getState().realistic)) {
    g.beginPath();
    let penDown = false;
    if (start > 0 && kind[start - 1] === Kind.Stitch && kind[start] === Kind.Stitch && keep(start - 1)) {
      g.moveTo(x[start - 1], y[start - 1]);
      penDown = true;
    }
    let segments = 0;
    for (let i = start; i < end; i++) {
      if (kind[i] !== Kind.Stitch || !keep(i)) {
        penDown = false;
        continue;
      }
      if (penDown) {
        g.lineTo(x[i], y[i]);
        segments++;
      } else {
        g.moveTo(x[i], y[i]);
        penDown = true;
      }
    }
    if (!segments) return;
    g.stroke({ width: layer.width, color: layer.color, alpha: layer.alpha, cap: "round", join: "round" });
  }
}

/**
 * Machine functions up to record `upTo`: travel lines (grey if trimmed, amber if a thread is
 * left behind), a red cross at each trim, and a pause sign at each stop. Sizes are in screen pixels.
 */
function drawFunctions(g: Graphics, d: Design, upTo: number, scale: number) {
  g.clear();
  const { x, y, kind } = d.records;
  const px = 1 / scale;
  let last = -1;
  let travelling = false;
  let trimmed = false;
  const cut: number[] = [];
  const left: number[] = [];
  const trims: number[] = [];
  const stops: number[] = [];
  for (let i = 0; i < upTo; i++) {
    const k = kind[i];
    if (k === Kind.Jump) travelling = true;
    else if (k === Kind.Trim) {
      travelling = trimmed = true;
      if (last >= 0) trims.push(last);
    } else if (k === Kind.Stitch) {
      if (travelling && last >= 0) (trimmed ? cut : left).push(last, i);
      travelling = trimmed = false;
      last = i;
    } else if (k === Kind.Stop) stops.push(i);
    else if (k === Kind.ColorChange) {
      last = -1;
      travelling = trimmed = false;
    }
  }
  const lines = (pairs: number[], color: number, width: number, alpha: number) => {
    if (!pairs.length) return;
    for (let j = 0; j < pairs.length; j += 2) g.moveTo(x[pairs[j]], y[pairs[j]]).lineTo(x[pairs[j + 1]], y[pairs[j + 1]]);
    g.stroke({ width: width * px, color, alpha });
  };
  lines(cut, TRAVEL_COLOR, 1, 0.7);
  lines(left, JUMP_COLOR, 2, 0.95);
  const r = 4 * px;
  for (const i of trims) g.moveTo(x[i] - r, y[i] - r).lineTo(x[i] + r, y[i] + r).moveTo(x[i] + r, y[i] - r).lineTo(x[i] - r, y[i] + r);
  if (trims.length) g.stroke({ width: 2 * px, color: TRIM_COLOR });
  for (const i of stops) {
    g.circle(x[i], y[i], 7 * px).fill(STOP_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
    g.rect(x[i] - 2.5 * px, y[i] - 3.5 * px, 1.6 * px, 7 * px).rect(x[i] + 0.9 * px, y[i] - 3.5 * px, 1.6 * px, 7 * px).fill(0xffffff);
  }
}

function applyView(scene: Scene) {
  const { world, view } = scene;
  world.scale.set(view.scale);
  world.position.set(view.x, view.y);
  drawGrid(scene);
  useStore.getState().setZoomScale(view.scale);
}

/** Squares across the whole visible area, centred on the hoop centre, spacing adapted to zoom. */
function drawGrid(scene: Scene) {
  const g = scene.grid;
  g.clear();
  const st = useStore.getState();
  g.visible = st.showGrid;
  if (!st.showGrid) return;
  const { scale, x: ox, y: oy } = scene.view;
  const w = scene.app.screen.width;
  const h = scene.app.screen.height;
  const sp = gridSpacing(scale, st.units);
  const snap = (v: number) => Math.round(v) + 0.5; // crisp 1px lines
  for (const major of [false, true]) {
    for (const l of gridLines((0 - ox) / scale, (w - ox) / scale, 0, sp)) {
      if (l.major !== major) continue;
      const sx = snap(l.mm * scale + ox);
      g.moveTo(sx, 0).lineTo(sx, h);
    }
    for (const l of gridLines((0 - oy) / scale, (h - oy) / scale, 0, sp)) {
      if (l.major !== major) continue;
      const sy = snap(l.mm * scale + oy);
      g.moveTo(0, sy).lineTo(w, sy);
    }
    g.stroke({ width: 1, ...(major ? C.gridMajor : C.gridMinor) });
  }
}

/** What "fit" frames: the hoop (fixed at the centre), the stitches and the pictures. */
function fitBounds(d: Design | null): [number, number, number, number] {
  const st = useStore.getState();
  const hoop = selectHoop(st);
  const boxes: [number, number, number, number][] = [];
  if (d) boxes.push(d.info.bounds_mm);
  if (hoop && st.showHoop) boxes.push([-hoop.width_mm / 2, -hoop.height_mm / 2, hoop.width_mm / 2, hoop.height_mm / 2]);
  for (const im of st.history.present?.images ?? []) {
    if (im.visible) boxes.push([im.x - im.width_mm / 2, im.y - im.height_mm / 2, im.x + im.width_mm / 2, im.y + im.height_mm / 2]);
  }
  if (!boxes.length) return [-50, -50, 50, 50];
  return [
    Math.min(...boxes.map((b) => b[0])),
    Math.min(...boxes.map((b) => b[1])),
    Math.max(...boxes.map((b) => b[2])),
    Math.max(...boxes.map((b) => b[3])),
  ];
}

/** The hoop stays put at the centre of the canvas; designs move inside it. */
function drawHoop(scene: Scene, hoop: Hoop | null, show: boolean) {
  const g = scene.hoop;
  g.clear();
  g.visible = show && hoop !== null;
  if (!hoop || !show) return;
  const s = scene.view.scale;
  const fits = !scene.design || hoopFit(scene.design.info, hoop) === "fits";
  const color = fits ? C.hoop : HOOP_BAD_COLOR;
  const w = hoop.width_mm;
  const h = hoop.height_mm;
  g.rect(-w / 2, -h / 2, w, h).stroke({ width: 2 / s, color, alpha: 0.9 });
  const m = Math.min(w, h) * 0.04;
  g.moveTo(-m, 0).lineTo(m, 0).moveTo(0, -m).lineTo(0, m).stroke({ width: 1 / s, color, alpha: 0.7 });
}

function drawPictures(scene: Scene) {
  const images = useStore.getState().history.present?.images ?? [];
  scene.pictures.removeChildren().forEach((c) => c.destroy());
  for (const im of images) {
    if (!im.visible) continue;
    const tex = textureFor(im, () => sceneRefForTextures?.() && drawPictures(sceneRefForTextures()!));
    if (!tex) continue;
    const sp = new Sprite(tex);
    sp.anchor.set(0.5);
    sp.position.set(im.x, im.y);
    sp.width = im.width_mm;
    sp.height = im.height_mm;
    sp.rotation = (im.rotate * Math.PI) / 180;
    sp.alpha = im.opacity;
    sp.label = im.id;
    scene.pictures.addChild(sp);
  }
}
let sceneRefForTextures: (() => Scene | null) | null = null;

// ---------------------------------------------------------------- density map

function drawHeat(scene: Scene, heat: Heatmap | undefined, show: boolean) {
  scene.heat.removeChildren().forEach((c) => c.destroy({ children: true, texture: true, textureSource: true }));
  if (!show || !heat) return;
  const bytes = Uint8Array.from(atob(heat.data), (ch) => ch.charCodeAt(0));
  const canvas = document.createElement("canvas");
  canvas.width = heat.width;
  canvas.height = heat.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const img = ctx.createImageData(heat.width, heat.height);
  bytes.forEach((v, i) => img.data.set(heatColor(v, heat.limit), i * 4));
  ctx.putImageData(img, 0, 0);
  const sp = new Sprite(Texture.from(canvas));
  sp.position.set(heat.x, heat.y);
  sp.width = heat.width * heat.cell_mm;
  sp.height = heat.height * heat.cell_mm;
  scene.heat.addChild(sp);
}

// ---------------------------------------------------------------- split hoopings

const SPLIT_COLORS = [0x2b7bd6, 0xe0218a, 0x2f8f4e, 0xe08a00];
const MARK_COLOR = 0xe0218a;

/** Each hooping's sewing window, numbered, and the alignment crosses. */
function drawSplit(scene: Scene, preview: { window_mm: number[]; marks: number[][] }[] | null) {
  scene.split.removeChildren().forEach((c) => c.destroy({ children: true }));
  if (!preview || preview.length < 2) return;
  const s = scene.view.scale;
  const g = new Graphics();
  preview.forEach((sec, i) => {
    const [x0, y0, x1, y1] = sec.window_mm;
    const color = SPLIT_COLORS[i % SPLIT_COLORS.length];
    g.rect(x0, y0, x1 - x0, y1 - y0).fill({ color, alpha: 0.06 }).stroke({ width: 2 / s, color, alpha: 0.9 });
    const label = new Text({ text: String(i + 1), style: { fill: color, fontSize: 28, fontWeight: "700", fontFamily: "system-ui" } });
    label.scale.set(1 / s);
    label.position.set(x0 + 6 / s, y0 + 4 / s);
    scene.split.addChild(label);
  });
  const arm = 3;
  for (const sec of preview)
    for (const [x, y] of sec.marks)
      g.moveTo(x - arm, y).lineTo(x + arm, y).moveTo(x, y - arm).lineTo(x, y + arm).stroke({ width: 2.5 / s, color: MARK_COLOR });
  scene.split.addChildAt(g, 0);
}

// ---------------------------------------------------------------- selection frames

function rotatePt(p: Pt, c: Pt, rad: number): Pt {
  const [ca, sa] = [Math.cos(rad), Math.sin(rad)];
  return [c[0] + (p[0] - c[0]) * ca - (p[1] - c[1]) * sa, c[1] + (p[0] - c[0]) * sa + (p[1] - c[1]) * ca];
}

function selectedFrame(scene: Scene): Frame | null {
  const st = useStore.getState();
  const doc = st.history.present;
  if (!doc || !st.selectedId) return null;
  const s = scene.view.scale;
  const imgIndex = doc.images.findIndex((im) => im.id === st.selectedId);
  if (imgIndex >= 0) {
    const im = doc.images[imgIndex];
    const c: Pt = [im.x, im.y];
    const rad = (im.rotate * Math.PI) / 180;
    const [hw, hh] = [im.width_mm / 2, im.height_mm / 2];
    const corners = ([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]] as Pt[]).map((p) => rotatePt([c[0] + p[0], c[1] + p[1]], c, rad));
    const topMid: Pt = rotatePt([c[0], c[1] - hh], c, rad);
    const up: Pt = [Math.sin(rad), -Math.cos(rad)];
    const knob: Pt = [topMid[0] + (up[0] * ROTATE_KNOB_PX) / s, topMid[1] + (up[1] * ROTATE_KNOB_PX) / s];
    return { kind: "image", index: imgIndex, id: im.id, indices: [imgIndex], ids: [im.id], corners, center: c, knob, up, locked: im.locked };
  }
  const index = doc.layout.items.findIndex((it) => it.id === st.selectedId);
  const ids = [st.selectedId, ...st.extraIds].filter((id) => doc.layout.items.some((it) => it.id === id));
  const indices = ids.map((id) => doc.layout.items.findIndex((it) => it.id === id));
  const boxes = indices.map((i) => scene.design?.items?.[i]?.bounds_mm).filter((x): x is [number, number, number, number] => !!x);
  if (index < 0 || !boxes.length) return null;
  const b = [Math.min(...boxes.map((x) => x[0])), Math.min(...boxes.map((x) => x[1])), Math.max(...boxes.map((x) => x[2])), Math.max(...boxes.map((x) => x[3]))];
  // Drawn objects get a little padding so the frame's handles don't sit on the shape's own points.
  const pad = ids.length > 1 || isObject(doc.layout.items[index]) ? OBJECT_BOX_PAD_PX / s : 0;
  const [x0, y0, x1, y1] = [b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad];
  const c: Pt = [(x0 + x1) / 2, (y0 + y1) / 2];
  return {
    kind: "item",
    index,
    id: st.selectedId,
    indices,
    ids,
    corners: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
    center: c,
    knob: [c[0], y0 - ROTATE_KNOB_PX / s],
    up: [0, -1],
    // Pinned designs and shapes can't be dragged (the frame shows faded, without handles).
    locked: indices.some((i) => !!doc.layout.items[i].locked),
  };
}

function selectedObject(): ObjectItem | null {
  const st = useStore.getState();
  const it = st.history.present?.layout.items.find((x) => x.id === st.selectedId);
  return it && isObject(it) ? it : null;
}

function drawOverlay(scene: Scene, live?: { id: string; list: NodeList; index: number; at: Pt }) {
  const g = scene.overlay;
  g.clear();
  const st = useStore.getState();
  const s = scene.view.scale;
  const px = 1 / s;
  if (st.pen) drawPen(g, st.pen, cursorMm, px);
  if (st.pen && st.ghost) drawGhost(g, st.pen, st.ghost, px);
  if (st.crosshair && cursorMm) {
    const [w, h] = [scene.app.screen.width / s, scene.app.screen.height / s];
    const [vx, vy] = [-scene.view.x / s, -scene.view.y / s];
    g.moveTo(vx, cursorMm[1]).lineTo(vx + w, cursorMm[1]).moveTo(cursorMm[0], vy).lineTo(cursorMm[0], vy + h).stroke({ width: px, color: C.select, alpha: 0.55 });
  }
  if (!st.showStitches) {
    // Stitches hidden (N): show every drawn shape's outline instead.
    for (const it of st.history.present?.layout.items ?? []) {
      if (!isObject(it)) continue;
      for (const l of nodeLists(it)) {
        const poly = flatten(l.nodes, l.closed);
        if (poly.length < 2) continue;
        g.moveTo(poly[0][0], poly[0][1]);
        for (const p of poly.slice(1)) g.lineTo(p[0], p[1]);
        if (l.closed) g.closePath();
        g.stroke({ width: 1.5 * px, color: parseInt(it.thread.color.slice(1), 16) });
      }
    }
  }
  for (const tool of [st.ruler, st.angleFor?.points] as ([number, number][] | null | undefined)[]) {
    if (!tool) continue;
    const end = tool.length === 1 ? cursorMm : tool[1];
    if (tool.length && end) {
      g.moveTo(tool[0][0], tool[0][1]).lineTo(end[0], end[1]).stroke({ width: 2 * px, color: tool === st.ruler ? C.select : C.ghost });
      for (const p of [tool[0], end]) g.circle(p[0], p[1], 3.5 * px).fill(HANDLE_FILL).stroke({ width: px, color: 0x121114 });
    }
  }
  if (st.measure) {
    const pts = st.measure.points;
    for (const p of pts) g.circle(p[0], p[1], 4 * px).fill(C.select).stroke({ width: px, color: 0xffffff });
    const end = pts.length === 1 ? cursorMm : pts[1];
    if (pts.length && end) g.moveTo(pts[0][0], pts[0][1]).lineTo(end[0], end[1]).stroke({ width: 2 * px, color: C.select });
  }
  if (st.tool !== "select") return;

  const f = selectedFrame(scene);
  if (f) {
    const [a, ...rest] = f.corners;
    g.moveTo(a[0], a[1]);
    for (const p of rest) g.lineTo(p[0], p[1]);
    g.closePath().stroke({ width: 1.5 * px, color: C.select, alpha: f.locked ? 0.5 : 1 });
    if (!f.locked) {
      const top: Pt = [(f.corners[0][0] + f.corners[1][0]) / 2, (f.corners[0][1] + f.corners[1][1]) / 2];
      g.moveTo(top[0], top[1]).lineTo(f.knob[0], f.knob[1]).stroke({ width: 1.5 * px, color: C.select });
      const hs = HANDLE_PX * px;
      for (const [hx, hy] of f.corners) g.rect(hx - hs / 2, hy - hs / 2, hs, hs).fill(HANDLE_FILL).stroke({ width: 1.5 * px, color: C.select });
      g.circle(f.knob[0], f.knob[1], hs / 2 + px).fill(HANDLE_FILL).stroke({ width: 1.5 * px, color: C.select });
    }
  }

  // Points of a selected drawn object, its entry (green) and exit (red).
  const o = selectedObject();
  if (!o) return;
  const lists = nodeLists(o).map((l) =>
    live && live.id === o.id && live.list === l.key
      ? { ...l, nodes: l.nodes.map((n, i) => (i === live.index ? ([live.at[0], live.at[1], n[2]] as PathNode) : n)) }
      : l,
  );
  for (const l of lists) {
    const poly = flatten(l.nodes, l.closed);
    if (poly.length > 1) {
      g.moveTo(poly[0][0], poly[0][1]);
      for (const p of poly.slice(1)) g.lineTo(p[0], p[1]);
      g.stroke({ width: 1.2 * px, color: C.select, alpha: 0.9 });
    }
  }
  if (o.kind === "satin") {
    const [ra, rb] = [lists[0].nodes, lists[1].nodes];
    ra.forEach((n, i) => rb[i] && g.moveTo(n[0], n[1]).lineTo(rb[i][0], rb[i][1]));
    g.stroke({ width: 1 * px, color: C.select, alpha: 0.5 });
  }
  const sel = st.selectedNode;
  for (const l of lists) {
    l.nodes.forEach((n, i) => {
      const on = sel && sel.id === o.id && sel.list === l.key && sel.index === i;
      const r = (NODE_PX / 2) * px;
      nodeMark(g, n, r);
      g.fill(on ? HANDLE_FILL : 0xffffff).stroke({ width: 1.5 * px, color: C.select });
    });
  }
  const d = scene.design;
  const idx = st.history.present!.layout.items.indexOf(o);
  if (d?.records.item) {
    const { x, y, kind, item } = d.records;
    let first = -1;
    let last = -1;
    for (let i = 0; i < kind.length; i++) {
      if (item[i] === idx && kind[i] === Kind.Stitch) {
        if (first < 0) first = i;
        last = i;
      }
    }
    if (first >= 0) {
      g.circle(x[first], y[first], 4 * px).fill(ENTRY_COLOR).stroke({ width: px, color: 0xffffff });
      g.circle(x[last], y[last], 4 * px).fill(EXIT_COLOR).stroke({ width: px, color: 0xffffff });
    }
  }
}

/** Point marker: curve = circle, line = square, cusp = diamond. */
function nodeMark(g: Graphics, n: PathNode, r: number) {
  if (n[2] === "s") g.circle(n[0], n[1], r);
  else if (n[2] === "l") g.rect(n[0] - r, n[1] - r, 2 * r, 2 * r);
  else g.poly([n[0], n[1] - r * 1.3, n[0] + r * 1.3, n[1], n[0], n[1] + r * 1.3, n[0] - r * 1.3, n[1]]);
}

/** What the pen has drawn so far, plus a rubber band to the cursor. */
function drawPen(g: Graphics, pen: Pen, cursor: Pt | null, px: number) {
  const color = parseInt(useStore.getState().drawThread.color.slice(1), 16);
  // The rubber band shows the kind of point the next click makes (curve, or line with Ctrl, cusp with Shift).
  const withCursor = (nodes: PathNode[]) => (cursor ? [...nodes, [cursor[0], cursor[1], cursorKind] as PathNode] : nodes);
  const line = (poly: Pt[], width: number, alpha: number) => {
    if (poly.length < 2) return;
    g.moveTo(poly[0][0], poly[0][1]);
    for (const p of poly.slice(1)) g.lineTo(p[0], p[1]);
    g.stroke({ width, color, alpha });
  };
  if (pen.kind === "fill") {
    const poly = flatten(withCursor(pen.a), true);
    if (poly.length > 2) {
      g.poly(poly.flat()).fill({ color, alpha: 0.25 });
    }
    line(poly, 1.5 * px, 1);
  } else if (pen.kind === "run") {
    line(flatten(withCursor(pen.a)), 1.5 * px, 1);
  } else {
    const nextOnA = pen.a.length === pen.b.length;
    line(flatten(nextOnA ? withCursor(pen.a) : pen.a), 1.5 * px, 1);
    line(flatten(nextOnA ? pen.b : withCursor(pen.b)), 1.5 * px, 1);
    const ra = nextOnA ? pen.a : pen.a;
    const rb = nextOnA ? pen.b : withCursor(pen.b);
    ra.forEach((n, i) => rb[i] && g.moveTo(n[0], n[1]).lineTo(rb[i][0], rb[i][1]));
    g.stroke({ width: 3 * px, color, alpha: 0.35 });
  }
  const r = 3 * px;
  for (const n of [...pen.a, ...pen.b]) nodeMark(g, n, r);
  g.fill(0xffffff).stroke({ width: px, color: C.select });
}
let cursorMm: Pt | null = null;
let cursorKind: NodeKind = "s";

/** The kind of point a click makes, from the keys held. */
const pointKind = (e: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }): NodeKind =>
  e.ctrlKey || e.metaKey ? "l" : e.shiftKey ? "c" : "s";

const ALT_COLOR = 0xe08a00;

/** Trace Assist's proposal: a ring at the next point and a line to it, fainter when less sure. */
function drawGhost(g: Graphics, pen: Pen, ghost: Ghost, px: number) {
  const alpha = 0.35 + 0.65 * Math.min(1, ghost.confidence);
  const last: Pt =
    pen.kind === "satin" && pen.b.length
      ? [(pen.a[pen.a.length - 1][0] + pen.b[pen.b.length - 1][0]) / 2, (pen.a[pen.a.length - 1][1] + pen.b[pen.b.length - 1][1]) / 2]
      : [pen.a[pen.a.length - 1][0], pen.a[pen.a.length - 1][1]];
  const ring = (p: Pt, color: number) => {
    g.moveTo(last[0], last[1]).lineTo(p[0], p[1]).stroke({ width: 2 * px, color, alpha: alpha * 0.8 });
    g.circle(p[0], p[1], 6 * px).stroke({ width: 2 * px, color, alpha });
    g.circle(p[0], p[1], 2 * px).fill({ color, alpha });
  };
  for (const a of ghost.alternatives) ring(a, ALT_COLOR);
  if (ghost.rails) {
    const [r1, r2] = ghost.rails;
    g.moveTo(r1[0], r1[1]).lineTo(r2[0], r2[1]).stroke({ width: 2 * px, color: C.ghost, alpha: alpha * 0.7 });
    for (const r of ghost.rails) g.circle(r[0], r[1], 4 * px).stroke({ width: 2 * px, color: C.ghost, alpha });
  }
  ring(ghost.point, C.ghost);
}

// ---------------------------------------------------------------- scene

function buildScene(app: Application, d: Design | null, prev: View | null): Scene {
  app.stage.removeChildren().forEach((c) => c.destroy({ children: true }));
  const grid = new Graphics();
  const world = new Container();
  app.stage.addChild(grid, world);
  const pictures = new Container();
  const hoop = new Graphics();
  const stitches = new Container();
  world.addChild(pictures, hoop, stitches);
  const chunks = d ? chunkBlocks(d) : [];
  const realistic = useStore.getState().realistic;
  const real: (ThreadChunk | null)[] = [];
  const full: Container[] = chunks.map((c) => {
    const color = d!.threads[c.thread]?.color ?? "#808080";
    if (realistic) {
      const tc = buildThreadChunk(d!, c.start, c.end, color);
      real.push(tc);
      stitches.addChild(tc.root);
      return tc.root;
    }
    const g = new Graphics();
    drawStitches(g, d!, c.start, c.end, color);
    stitches.addChild(g);
    real.push(null);
    return g;
  });
  const partial = new Graphics();
  const points = new Graphics();
  const jumps = new Graphics();
  const needle = new Graphics();
  const overlay = new Graphics();
  stitches.addChild(partial, points);
  const heat = new Container();
  const split = new Container();
  world.addChild(heat, jumps, needle, split, overlay);
  const view = prev ?? fitView(fitBounds(d), app.screen.width, app.screen.height);
  const scene: Scene = {
    app, grid, world, pictures, hoop, stitches, chunks, full, real, points, partial, jumps, needle, overlay, heat, split, design: d, view,
    autoFit: prev === null,
  };
  applyView(scene);
  drawPictures(scene);
  return scene;
}

/** Redraw everything whose line width depends on zoom, and the playhead state. */
function refresh(scene: Scene) {
  const s = useStore.getState();
  scene.stitches.visible = s.showStitches;
  scene.pictures.visible = s.showPictures;
  drawPoints(scene, s.showPoints);
  updatePlayhead(scene, s.stitchIdx, s.playhead, s.showJumps);
  drawHoop(scene, selectHoop(s), s.showHoop);
  drawOverlay(scene);
}

/** Show everything sewn up to `playhead` stitches. */
function updatePlayhead(scene: Scene, stitchIdx: Int32Array, playhead: number, showJumps: boolean) {
  const { design: d, chunks, full, partial, needle } = scene;
  partial.clear();
  needle.clear();
  scene.jumps.clear();
  if (!d) return;
  const upTo = visibleRecords(stitchIdx, playhead, d.records.kind.length);
  let current = -1;
  chunks.forEach((c, i) => {
    const tc = scene.real[i];
    if (tc) {
      // Realistic: show the chunk's own sprites up to the playhead (no redraw needed).
      full[i].visible = upTo > c.start;
      if (upTo > c.start) showUpTo(tc, upTo);
      return;
    }
    full[i].visible = upTo >= c.end;
    if (upTo > c.start && upTo < c.end) current = i;
  });
  if (current >= 0) {
    const c = chunks[current];
    drawStitches(partial, d, c.start, upTo, d.threads[c.thread]?.color ?? "#808080");
  }
  scene.jumps.visible = showJumps;
  if (showJumps) drawFunctions(scene.jumps, d, upTo, scene.view.scale);
  if (playhead > 0 && playhead < stitchIdx.length) {
    const r = stitchIdx[playhead - 1];
    const s = scene.view.scale;
    needle
      .circle(d.records.x[r], d.records.y[r], 5 / s)
      .stroke({ width: 1.5 / s, color: 0xffffff })
      .circle(d.records.x[r], d.records.y[r], 3.5 / s)
      .stroke({ width: 1.5 / s, color: 0xd9381e });
  }
}

/** Needle points (P): a dot where the needle goes down, in a colour that shows on any thread. */
function drawPoints(scene: Scene, show: boolean) {
  const g = scene.points;
  g.clear();
  const d = scene.design;
  if (!show || !d) return;
  const { x, y, kind } = d.records;
  const r = Math.max(0.08, 1.6 / scene.view.scale);
  for (let i = 0; i < kind.length; i++) if (kind[i] === Kind.Stitch) g.circle(x[i], y[i], r);
  g.fill({ color: 0xffffff, alpha: 0.9 }).stroke({ width: 0.6 / scene.view.scale, color: 0x121114, alpha: 0.9 });
}

/** A copy of one item's stitches that follows the pointer while dragging; everything else dims. */
function startGhost(scene: Scene, f: Frame): Container | null {
  if (f.kind === "image") return null; // the picture itself moves
  const ghost = new Container();
  ghost.pivot.set(f.center[0], f.center[1]);
  ghost.position.set(f.center[0], f.center[1]);
  const g = new Graphics();
  const d = scene.design;
  if (d) for (const i of f.indices) for (const b of d.blocks) drawStitches(g, d, b.start, b.end, d.threads[b.thread]?.color ?? "#808080", i);
  ghost.addChild(g);
  scene.stitches.alpha = DIM_ALPHA;
  scene.overlay.visible = false;
  scene.world.addChild(ghost);
  return ghost;
}

function endGhost(scene: Scene, ghost: Container | null) {
  if (ghost && !ghost.destroyed) ghost.destroy({ children: true });
  scene.stitches.alpha = 1;
  scene.overlay.visible = true;
  drawPictures(scene);
}

// ---------------------------------------------------------------- component

export function StitchCanvas() {
  const host = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<Scene | null>(null);
  const appRef = useRef<Application | null>(null);

  const design = useStore((s) => s.design);
  const hasDoc = useStore((s) => s.history.present !== null);
  const images = useStore((s) => s.history.present?.images);
  const playhead = useStore((s) => s.playhead);
  const showJumps = useStore((s) => s.showJumps);
  const showHoop = useStore((s) => s.showHoop);
  const hoop = useStore(selectHoop);
  const fitRequest = useStore((s) => s.fitRequest);
  const showGrid = useStore((s) => s.showGrid);
  const units = useStore((s) => s.units);
  const zoomRequest = useStore((s) => s.zoomRequest);
  const checks = useStore((s) => s.checks);
  const canvasDark = useStore(selectCanvasDark);
  const showDensity = useStore((s) => s.showDensity);
  const centerRequest = useStore((s) => s.centerRequest);
  const splitPreview = useStore((s) => s.splitPreview);
  const showPoints = useStore((s) => s.showPoints);
  const showStitches = useStore((s) => s.showStitches);
  const showPictures = useStore((s) => s.showPictures);
  const crosshair = useStore((s) => s.crosshair);
  const ruler = useStore((s) => s.ruler);
  const angleFor = useStore((s) => s.angleFor);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  const selectedNode = useStore((s) => s.selectedNode);
  const realistic = useStore((s) => s.realistic);
  const tool = useStore((s) => s.tool);
  const pen = useStore((s) => s.pen);
  const measure = useStore((s) => s.measure);
  const ghost = useStore((s) => s.ghost);

  // Create the Pixi app once.
  useEffect(() => {
    const el = host.current!;
    const app = new Application();
    let alive = true;
    let resizeObs: ResizeObserver | undefined;
    sceneRefForTextures = () => sceneRef.current;
    void app
      .init({ resizeTo: el, antialias: true, backgroundAlpha: 0, autoDensity: true, resolution: window.devicePixelRatio || 1 })
      .then(() => {
        if (!alive) return app.destroy(true, { children: true });
        el.appendChild(app.canvas);
        appRef.current = app;
        // Pixi's resizeTo only listens to window resizes; panels opening also change our size.
        resizeObs = new ResizeObserver(() => {
          app.resize();
          const scene = sceneRef.current;
          if (scene?.autoFit) {
            scene.view = fitView(fitBounds(scene.design), app.screen.width, app.screen.height);
            applyView(scene);
            refresh(scene);
          } else if (scene) drawGrid(scene);
        });
        resizeObs.observe(el);
        const st = useStore.getState();
        if (st.history.present) {
          sceneRef.current = buildScene(app, st.design, null);
          refresh(sceneRef.current);
        }
      });
    return () => {
      alive = false;
      resizeObs?.disconnect();
      sceneRefForTextures = null;
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
        sceneRef.current = null;
      }
    };
  }, []);

  // Light or dark design background: redraw the grid, hoop and handles in matching colors.
  useEffect(() => {
    C = canvasDark ? PALETTES.dark : PALETTES.light;
    const scene = sceneRef.current;
    if (!scene) return;
    drawGrid(scene);
    refresh(scene);
  }, [canvasDark]);

  // Rebuild for each new render or document; keep the view (a fit request re-frames separately).
  useEffect(() => {
    const app = appRef.current;
    if (!app) return;
    if (!hasDoc) {
      app.stage.removeChildren().forEach((c) => c.destroy({ children: true }));
      sceneRef.current = null;
      return;
    }
    const prev = sceneRef.current;
    sceneRef.current = buildScene(app, design, prev ? prev.view : null);
    if (prev) sceneRef.current.autoFit = prev.autoFit;
    refresh(sceneRef.current);
  }, [design, hasDoc, realistic]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawPictures(scene);
  }, [images]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawHoop(scene, hoop, showHoop);
  }, [hoop, showHoop]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawGrid(scene);
  }, [showGrid, units]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawOverlay(scene);
    if (host.current) host.current.classList.toggle("drawing", tool !== "select" || measure !== null || !!useStore.getState().ruler || !!useStore.getState().angleFor);
  }, [selectedId, extraIds, selectedNode, tool, pen, images, measure, ghost]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) updatePlayhead(scene, useStore.getState().stitchIdx, playhead, showJumps);
  }, [playhead, showJumps]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !fitRequest) return;
    scene.view = fitView(fitBounds(scene.design), scene.app.screen.width, scene.app.screen.height);
    scene.autoFit = true;
    applyView(scene);
    refresh(scene);
  }, [fitRequest]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawHeat(scene, checks?.heatmap, showDensity);
  }, [checks, showDensity, design]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawSplit(scene, splitPreview);
  }, [splitPreview, design]);

  // View toggles (P, N, B, E) and the measuring and angle tools.
  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) refresh(scene);
    const st = useStore.getState();
    if (host.current) host.current.classList.toggle("drawing", st.tool !== "select" || !!st.measure || !!ruler || !!angleFor);
  }, [showPoints, showStitches, showPictures, crosshair, ruler, angleFor]);

  // A quality check was clicked: bring its spot to the middle (zooming in if far out).
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !centerRequest) return;
    const { width, height } = scene.app.screen;
    const scale = Math.max(scene.view.scale, PX_PER_MM_ACTUAL * 2);
    const [x, y] = centerRequest.at;
    scene.view = { scale, x: width / 2 - x * scale, y: height / 2 - y * scale };
    scene.autoFit = false;
    applyView(scene);
    refresh(scene);
  }, [centerRequest]);

  // Zoom buttons and keys zoom around the centre of the canvas.
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !zoomRequest.n) return;
    const { width, height } = scene.app.screen;
    const v = scene.view;
    if (zoomRequest.kind === "box" && zoomRequest.box) {
      // S (selection) and 0 (hoop): fit that area.
      scene.view = fitView(zoomRequest.box, width, height, 48);
    } else {
      const target =
        zoomRequest.kind === "in"
          ? v.scale * ZOOM_STEP
          : zoomRequest.kind === "out"
            ? v.scale / ZOOM_STEP
            : PX_PER_MM_ACTUAL * (zoomRequest.kind === "scale" ? (zoomRequest.factor ?? 1) : 1);
      scene.view = zoomAt(v, clamp(target, MIN_SCALE, MAX_SCALE) / v.scale, width / 2, height / 2);
    }
    scene.autoFit = false;
    applyView(scene);
    refresh(scene);
  }, [zoomRequest]);

  // Pointer: draw, select, move/resize/rotate, edit points, pan; wheel zooms.
  useEffect(() => {
    const el = host.current!;
    let drag: Drag | null = null;
    let dragPointer = -1;
    let releaseEsc: (() => void) | null = null;

    /** Esc during a drag lets go: the shape, point or picture goes back where it was. */
    const cancelDrag = () => {
      const scene = sceneRef.current;
      const d = drag;
      drag = null;
      releaseEsc = null;
      if (el.hasPointerCapture(dragPointer)) el.releasePointerCapture(dragPointer);
      el.classList.remove("panning");
      if (!scene || !d || d.kind === "pan") return;
      if (d.kind === "node") return drawOverlay(scene);
      endGhost(scene, d.ghost);
    };

    const local = (e: PointerEvent | WheelEvent | MouseEvent) => {
      const r = el.getBoundingClientRect();
      return [e.clientX - r.left, e.clientY - r.top] as const;
    };
    const toWorld = (scene: Scene, sx: number, sy: number): Pt => [(sx - scene.view.x) / scene.view.scale, (sy - scene.view.y) / scene.view.scale];
    const toScreen = (scene: Scene, p: Pt): Pt => [p[0] * scene.view.scale + scene.view.x, p[1] * scene.view.scale + scene.view.y];
    const near = (scene: Scene, p: Pt, sx: number, sy: number, r: number) => {
      const [x, y] = toScreen(scene, p);
      return Math.abs(x - sx) <= r && Math.abs(y - sy) <= r;
    };
    /** Snap to an existing point of a drawn shape within a few pixels (so shapes meet exactly);
     *  holding Shift snaps to the grid's minor lines instead. */
    const snapped = (scene: Scene, p: Pt, e: { altKey: boolean }, skip?: { id: string; list: NodeList; index: number }): Pt => {
      const st = useStore.getState();
      // Alt while drawing: keep the new point on a 15-degree line from the last one (as in Embrilliance).
      const last = st.pen ? (st.pen.kind === "satin" && st.pen.b.length === st.pen.a.length && st.pen.b.length ? st.pen.b : st.pen.a).at(-1) : undefined;
      if (e.altKey && last && !skip) {
        const dx = p[0] - last[0];
        const dy = p[1] - last[1];
        const len = Math.hypot(dx, dy);
        const a = Math.round(Math.atan2(dy, dx) / (Math.PI / 12)) * (Math.PI / 12);
        return [last[0] + Math.cos(a) * len, last[1] + Math.sin(a) * len];
      }
      if (st.snapGrid) {
        const step = gridSpacing(scene.view.scale, st.units).minorMm;
        return [Math.round(p[0] / step) * step, Math.round(p[1] / step) * step];
      }
      const reach = SNAP_PX / scene.view.scale;
      let best: Pt | null = null;
      let bestD = reach;
      for (const it of st.history.present?.layout.items ?? []) {
        if (!isObject(it)) continue;
        for (const l of nodeLists(it)) {
          l.nodes.forEach((n, i) => {
            if (skip && skip.id === it.id && skip.list === l.key && skip.index === i) return;
            const d = Math.hypot(n[0] - p[0], n[1] - p[1]);
            if (d < bestD) {
              bestD = d;
              best = [n[0], n[1]];
            }
          });
        }
      }
      return best ?? p;
    };

    const nodeAt = (scene: Scene, sx: number, sy: number) => {
      const o = useStore.getState().tool === "select" ? selectedObject() : null;
      if (!o) return null;
      for (const l of nodeLists(o)) {
        for (let i = l.nodes.length - 1; i >= 0; i--) {
          if (near(scene, [l.nodes[i][0], l.nodes[i][1]], sx, sy, NODE_PX)) return { o, list: l.key, index: i };
        }
      }
      return null;
    };

    const handleAt = (scene: Scene, sx: number, sy: number): "scale" | "rotate" | null => {
      const f = selectedFrame(scene);
      if (!f || f.locked) return null;
      if (near(scene, f.knob, sx, sy, HANDLE_PX)) return "rotate";
      if (f.corners.some((c) => near(scene, c, sx, sy, HANDLE_PX))) return "scale";
      return null;
    };

    /** What's under the pointer: a layout item (topmost) or, below everything, an unlocked picture. */
    const pick = (scene: Scene, p: Pt): { id: string } | null => {
      const doc = currentDoc();
      if (!doc) return null;
      if (scene.design) {
        const hit = hitTest(scene.design, p[0], p[1], 4 / scene.view.scale);
        if (hit !== null && doc.layout.items[hit]) return { id: doc.layout.items[hit].id };
      }
      for (let i = doc.images.length - 1; i >= 0; i--) {
        const im = doc.images[i];
        if (im.locked || !im.visible) continue;
        const local = rotatePt(p, [im.x, im.y], (-im.rotate * Math.PI) / 180);
        if (Math.abs(local[0] - im.x) <= im.width_mm / 2 && Math.abs(local[1] - im.y) <= im.height_mm / 2) return { id: im.id };
      }
      return null;
    };

    const onWheel = (e: WheelEvent) => {
      const scene = sceneRef.current;
      if (!scene) return;
      e.preventDefault();
      const [sx, sy] = local(e);
      const factor = Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015));
      scene.view = zoomAt(scene.view, factor, sx, sy);
      scene.autoFit = false;
      applyView(scene);
      refresh(scene);
    };

    const onDown = (e: PointerEvent) => {
      startPointer(e);
      if (drag && !releaseEsc) {
        dragPointer = e.pointerId;
        releaseEsc = holdEscape(cancelDrag);
      }
    };

    const startPointer = (e: PointerEvent) => {
      const scene = sceneRef.current;
      if (!scene || e.button > 2) return;
      const [sx, sy] = local(e);
      const st = useStore.getState();
      if (e.button === 1) {
        el.setPointerCapture(e.pointerId);
        drag = { kind: "pan", x: e.clientX, y: e.clientY, moved: false, deselect: false };
        return;
      }
      // Measuring a picture: collect two clicks (the panel asks for the real distance).
      // Measuring tool (M): two clicks; a third starts a new measurement.
      if (st.ruler && e.button === 0) {
        const p = toWorld(scene, sx, sy);
        st.setRuler(st.ruler.length >= 2 ? [p] : [...st.ruler, p]);
        return;
      }
      // Inclination (I): a line across the fill sets its stitch angle.
      if (st.angleFor && e.button === 0) {
        const p = toWorld(scene, sx, sy);
        if (st.angleFor.points.length) finishAngle(st.angleFor.id, st.angleFor.points[0], p);
        else st.setAngleFor({ ...st.angleFor, points: [p] });
        return;
      }
      if (st.measure && e.button === 0) {
        if (st.measure.points.length < 2) st.setMeasure({ ...st.measure, points: [...st.measure.points, toWorld(scene, sx, sy)] });
        return;
      }
      // Text: click where it goes.
      if (st.tool === "text" && e.button === 0) {
        const p = toWorld(scene, sx, sy);
        void addText(p[0], p[1]);
        return;
      }
      // Drawing, as in Embrilliance: click = curve point, Ctrl+click = line point, Shift+click = cusp.
      // Right-click finishes the shape; Ctrl+right-click finishes and closes it.
      if (st.tool !== "select" && st.tool !== "text") {
        if (e.button === 2) {
          if (st.pen) void penFinish({ close: e.ctrlKey || e.metaKey });
          return;
        }
        const p = snapped(scene, toWorld(scene, sx, sy), e);
        penAdd([round2(p[0]), round2(p[1]), pointKind(e)]);
        return;
      }
      const node = nodeAt(scene, sx, sy);
      if (node) {
        if (e.button === 2) {
          toggleNodeKind(node.o.id, node.list, node.index);
          return;
        }
        st.selectNode({ id: node.o.id, list: node.list, index: node.index });
        el.setPointerCapture(e.pointerId);
        const n = nodeLists(node.o).find((l) => l.key === node.list)!.nodes[node.index];
        drag = { kind: "node", id: node.o.id, list: node.list, index: node.index, startX: sx, startY: sy, moved: false, at: [n[0], n[1]] };
        return;
      }
      if (e.button === 2) return;
      st.selectNode(null);
      const handle = handleAt(scene, sx, sy);
      const frame = selectedFrame(scene);
      if (handle && frame) {
        el.setPointerCapture(e.pointerId);
        drag = { kind: handle, frame, startX: sx, startY: sy, ghost: null, moved: false };
        return;
      }
      const hit = pick(scene, toWorld(scene, sx, sy));
      el.setPointerCapture(e.pointerId);
      if (hit) {
        const isItem = !!currentLayout()?.items.some((it) => it.id === hit.id);
        if (isItem) pickItem(hit.id, e.shiftKey || e.ctrlKey || e.metaKey);
        else st.select(hit.id);
        drawOverlay(scene);
        // Shift+click only adds to (or takes from) the selection; it doesn't start a drag.
        if (isItem && (e.shiftKey || e.ctrlKey || e.metaKey)) return;
        const f = selectedFrame(scene);
        if (f) drag = { kind: "move", frame: f, startX: sx, startY: sy, ghost: null, moved: false };
        return;
      }
      drag = { kind: "pan", x: e.clientX, y: e.clientY, moved: false, deselect: true };
    };

    const onDouble = (e: MouseEvent) => {
      const scene = sceneRef.current;
      if (!scene) return;
      const st = useStore.getState();
      if (st.tool !== "select") {
        void penFinish();
        return;
      }
      // Double-click a selected shape's outline to add a point there.
      const o = selectedObject();
      if (!o) return;
      const [sx, sy] = local(e);
      const p = toWorld(scene, sx, sy);
      for (const l of nodeLists(o)) {
        const span = spanAt(l.nodes, l.closed, p, 6 / scene.view.scale);
        if (span !== null) {
          insertNode(o.id, l.key, span, p[0], p[1]);
          return;
        }
      }
    };

    const onMove = (e: PointerEvent) => {
      const scene = sceneRef.current;
      if (!scene) return;
      const [sx, sy] = local(e);
      const st = useStore.getState();
      if ((st.tool !== "select" || st.measure || st.ruler || st.angleFor || st.crosshair) && !drag) {
        cursorMm = snapped(scene, toWorld(scene, sx, sy), e);
        cursorKind = pointKind(e);
        if (st.pen || st.measure || st.ruler || st.angleFor || st.crosshair) drawOverlay(scene);
        return;
      }
      if (!drag) {
        const h = nodeAt(scene, sx, sy) ? "node" : handleAt(scene, sx, sy);
        el.style.cursor =
          h === "node" ? "pointer" : h === "scale" ? "nwse-resize" : h === "rotate" ? "alias" : pick(scene, toWorld(scene, sx, sy)) ? "move" : "";
        return;
      }
      if (drag.kind === "pan") {
        const dx = e.clientX - drag.x;
        const dy = e.clientY - drag.y;
        if (dx || dy) drag.moved = true;
        scene.view = { ...scene.view, x: scene.view.x + dx, y: scene.view.y + dy };
        scene.autoFit = false;
        drag.x = e.clientX;
        drag.y = e.clientY;
        el.classList.add("panning");
        applyView(scene);
        return;
      }
      if (!drag.moved && Math.hypot(sx - drag.startX, sy - drag.startY) < DRAG_THRESHOLD_PX) return;
      drag.moved = true;
      if (drag.kind === "node") {
        drag.at = snapped(scene, toWorld(scene, sx, sy), e, { id: drag.id, list: drag.list, index: drag.index });
        drawOverlay(scene, { id: drag.id, list: drag.list, index: drag.index, at: drag.at });
        return;
      }
      const f = drag.frame;
      if (f.locked) return;
      drag.ghost ??= startGhost(scene, f);
      const s = scene.view.scale;
      const [ccx, ccy] = toScreen(scene, f.center);
      const target = f.kind === "image" ? scene.pictures.children.find((c) => c.label === f.id) : drag.ghost;
      if (!target) return;
      if (drag.kind === "move") {
        target.position.set(f.center[0] + (sx - drag.startX) / s, f.center[1] + (sy - drag.startY) / s);
      } else if (drag.kind === "scale") {
        const k = Math.hypot(sx - ccx, sy - ccy) / Math.max(1, Math.hypot(drag.startX - ccx, drag.startY - ccy));
        if (f.kind === "image") {
          const im = currentDoc()!.images[f.index];
          target.width = im.width_mm * Math.max(0.05, k);
          target.height = im.height_mm * Math.max(0.05, k);
        } else target.scale.set(Math.max(0.05, k));
      } else {
        let a = Math.atan2(sy - ccy, sx - ccx) - Math.atan2(drag.startY - ccy, drag.startX - ccx);
        if (e.shiftKey) a = (Math.round((a * 180) / Math.PI / 15) * 15 * Math.PI) / 180;
        target.rotation = (f.kind === "image" ? (currentDoc()!.images[f.index].rotate * Math.PI) / 180 : 0) + a;
      }
    };

    const onUp = (e: PointerEvent) => {
      const scene = sceneRef.current;
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      el.classList.remove("panning");
      releaseEsc?.();
      releaseEsc = null;
      const d = drag;
      drag = null;
      if (!scene || !d) return;
      if (d.kind === "pan") {
        if (!d.moved && d.deselect) {
          useStore.getState().select(null);
          drawOverlay(scene);
        }
        return;
      }
      if (d.kind === "node") {
        if (d.moved) moveNode(d.id, d.list, d.index, d.at[0], d.at[1]);
        else drawOverlay(scene);
        return;
      }
      const f = d.frame;
      const ghost = d.ghost;
      if (!d.moved || f.locked) return endGhost(scene, ghost);
      if (f.kind === "image") {
        const sprite = scene.pictures.children.find((c) => c.label === f.id);
        const im = currentDoc()!.images[f.index];
        if (sprite) {
          setPicture(f.id, {
            x: round2(sprite.position.x),
            y: round2(sprite.position.y),
            width_mm: round2(sprite.width),
            height_mm: round2(sprite.height),
            rotate: Math.round(((sprite.rotation * 180) / Math.PI) * 2) / 2,
          });
        } else endGhost(scene, null);
        void im;
        return;
      }
      const layout = currentLayout();
      if (!ghost || !layout) return endGhost(scene, ghost);
      let next = null;
      if (f.ids.length > 1) {
        // Several things move, grow or turn together, about the frame's centre.
        const g = selectionGeometry(f.ids);
        const k = Math.round(ghost.scale.x * 1000) / 1000;
        const deg = Math.round(((ghost.rotation * 180) / Math.PI) * 2) / 2;
        const op =
          d.kind === "move"
            ? { move: [ghost.position.x - f.center[0], ghost.position.y - f.center[1]] as [number, number] }
            : d.kind === "scale"
              ? k !== 1 ? { scale: k } : null
              : deg !== 0 ? { rotate: deg } : null;
        if (op) next = transformTogether(layout, f.ids, g.centers, f.center, op);
      } else if (d.kind === "move") next = moveBy(layout, f.id, ghost.position.x - f.center[0], ghost.position.y - f.center[1]);
      else if (d.kind === "scale") {
        const k = Math.round(ghost.scale.x * 1000) / 1000;
        if (k !== 1) next = scaleBy(layout, f.id, k);
      } else {
        const deg = Math.round(((ghost.rotation * 180) / Math.PI) * 2) / 2;
        if (deg !== 0) next = rotateBy(layout, f.id, deg);
      }
      if (!next) return endGhost(scene, ghost);
      // Keep the ghost until the new render replaces the scene; restore if the edit fails.
      void commit(next).then((ok) => {
        if (!ok && sceneRef.current === scene) endGhost(scene, ghost);
      });
    };

    const onLeave = () => {
      cursorMm = null;
      const scene = sceneRef.current;
      if (scene && useStore.getState().pen) drawOverlay(scene);
    };
    const noMenu = (e: Event) => e.preventDefault();

    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    el.addEventListener("pointerleave", onLeave);
    el.addEventListener("dblclick", onDouble);
    el.addEventListener("contextmenu", noMenu);
    return () => {
      releaseEsc?.();
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
      el.removeEventListener("pointerleave", onLeave);
      el.removeEventListener("dblclick", onDouble);
      el.removeEventListener("contextmenu", noMenu);
    };
  }, []);

  return <div ref={host} className="stitch-canvas" aria-label="Design canvas" />;
}

const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
