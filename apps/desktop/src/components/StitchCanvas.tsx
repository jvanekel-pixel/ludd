import { Application, Container, Graphics, Sprite, Text, Texture } from "pixi.js";
import { useEffect, useRef } from "react";
import {
  addText,
  commit,
  currentDoc,
  currentLayout,
  finishAngle,
  pickItem,
  moveStitchEnd,
  setFillDirection,
  setLetterEnd,
  setSatinTips,
  selectionGeometry,
  deleteNode,
  insertNode,
  moveNode,
  nodeLists,
  penAdd,
  penFinish,
  setPicture,
  toggleNodeKind,
  type NodeList,
  shapeStretchAnchor,
} from "../actions";
import { gridLines, gridSpacing, MM_PER_IN, PX_PER_MM_ACTUAL } from "../design/grid";
import { hitTest, itemLabel, moveBy, rotateBy, scaleBy, transformTogether } from "../design/layout";
import { heatColor } from "../design/heat";
import { hoopFit } from "../design/machine";
import { flatten, spanAt, type Pt } from "../design/paths";
import { chunkBlocks, visibleRecords, type Chunk } from "../design/player";
import { threadLayers } from "../design/threadLook";
import { buildThreadChunk, showUpTo, type ThreadChunk } from "./threadRender";
import { isObject, Kind, type Design, type Heatmap, type Hoop, type LayoutItemInfo, type NodeKind, type ObjectItem, type PathNode, type RefImage } from "../design/types";
import type { AutoTrace } from "../store";
import { clamp, fitView, MAX_SCALE, MIN_SCALE, zoomAt, type View } from "../design/view";
import { holdEscape } from "../escape";
import { acceptGuess, autoTraceAt, guessLists } from "../autoTrace";
import { endStitchEdit, finishKnife, moveSelectedStitches, setGuides } from "../features";
import { canvasMenu, itemMenu, openContextMenu, pictureMenu } from "../contextMenu";
import { garmentShape } from "../design/garments";
import { markSpacePanned } from "../spacePan";
import { cursorCss, type CursorName } from "../cursors";
import { OPPOSITE, resizeCursorFor, sideAxis, sideMids, stretchFactor } from "../design/handles";
import { columnRing, columnTips, fillDirection, fillRing, nearestOnLine, nearestOnRings } from "../design/direction";
import { drawOverlays, runCanvasMenu, runCanvasTool, snapToSources, type CanvasCtx } from "../canvas/hooks";
import { useLetterMode } from "../feat/letters";
import { useRepairHighlight } from "./RepairDialog";
import { nearestStitch, pickable, stitchesInBox } from "../design/stitchPick";
import { fixedFillEnd } from "../design/fillPatterns";
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
/** How faint the thread is while you hold a point. */
const NODE_DIM_ALPHA = 0.2;
/** See-through stitches (Shift+N): faint enough to see the picture under them, clear enough to follow. */
const SEE_THROUGH_ALPHA = 0.22;
/** How opaque the stitches are when nothing is being dragged. */
const restingAlpha = () => (useStore.getState().seeThrough ? SEE_THROUGH_ALPHA : 1);
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
  product: Graphics; // "Preview on": a garment behind the design
  rulers: Graphics; // screen space, along the top and left edges
  rulerLabels: Container;
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
  /** How far the frame sits outside the shape (mm), so a stretch keeps the shape's own side still. */
  pad: number;
};

type Drag =
  | { kind: "pan"; x: number; y: number; moved: boolean; deselect: boolean }
  | {
      kind: "move" | "scale" | "rotate";
      frame: Frame;
      startX: number;
      startY: number;
      /** Where it was grabbed, mm (zooming mid-drag can't shift it). */
      startW: Pt;
      ghost: Container | null;
      moved: boolean;
      /** A side handle: stretch that way only, the opposite side staying put. */
      side?: "n" | "e" | "s" | "w";
      /** The pointer it shows while dragging. */
      look?: CursorName;
    }
  | { kind: "node"; id: string; list: NodeList; index: number; startX: number; startY: number; moved: boolean; at: Pt }
  /** The green (start) or red (end) dot of the selected shape, dragged to a new place. */
  | { kind: "ends"; id: string; which: "start" | "end"; startX: number; startY: number; moved: boolean; at: Pt }
  /** A lettering letter's start or end dot. */
  | { kind: "letter"; id: string; index: number; which: "start" | "end"; startX: number; startY: number; moved: boolean; at: Pt }
  /** One of the purple direction dots (a fill's stitch direction, a satin column's tips). */
  | { kind: "dir"; id: string; which: 0 | 1; startX: number; startY: number; moved: boolean; at: Pt }
  | { kind: "guide"; startX: number; startY: number; moved: boolean }
  | { kind: "stitches"; startX: number; startY: number; moved: boolean; shift: boolean };

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

/** The needle path view's hairline: the thread's color, or grey for one too faint to see as a
 *  hairline on this fabric (nearly white, or nearly black on dark fabric). */
function wireColor(color: string): string {
  const n = parseInt(color.slice(1), 16);
  const light = (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
  return light > 0.8 || (C === PALETTES.dark && light < 0.2) ? "#8e877d" : color;
}

/** Draw records [start, end) as thread; jumps and trims lift the needle. `only` limits to one item. */
function drawStitches(g: Graphics, d: Design, start: number, end: number, color: string, only?: number) {
  const { x, y, kind, item } = d.records;
  const keep = (i: number) => only === undefined || item?.[i] === only;
  const { realistic, showWire } = useStore.getState();
  // Needle path view: one hairline, a screen pixel wide at any zoom (drawPoints adds its dots).
  const layers = showWire ? [{ width: 1, color: wireColor(color), alpha: 1 }] : threadLayers(color, realistic);
  // Each layer (edge, body, sheen) needs the path again: a stroke consumes it.
  for (const layer of layers) {
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
    g.stroke({ width: layer.width, color: layer.color, alpha: layer.alpha, cap: "round", join: "round", pixelLine: showWire });
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
  drawRulers(scene);
  useStore.getState().setZoomScale(view.scale);
}

/** Squares across the whole visible area, centred on the hoop centre, spacing adapted to zoom. */
/** "Preview on": the garment behind the design, in the chosen fabric color. */
function drawProduct(scene: Scene) {
  const g = scene.product;
  g.clear();
  const { garment, color } = useStore.getState().preview;
  const fill = parseInt(color.slice(1), 16);
  const shape = garmentShape(garment);
  if (!shape) {
    // Plain fabric in a chosen color (left alone when it's the standard one).
    if (color.toLowerCase() !== "#f4f1ea") g.rect(-3000, -3000, 6000, 6000).fill({ color: fill });
    return;
  }
  const px = 1 / scene.view.scale;
  g.poly(shape.outline.flat()).fill({ color: fill }).stroke({ width: 2 * px, color: 0x000000, alpha: 0.25 });
  for (const d of shape.details) {
    g.moveTo(d[0][0], d[0][1]);
    for (const q of d.slice(1)) g.lineTo(q[0], q[1]);
    g.stroke({ width: 2 * px, color: 0x000000, alpha: 0.2 });
  }
}

export const RULER_PX = 18;

/** Rulers along the top and left edges (in inches or mm), for dragging guides from. */
function drawRulers(scene: Scene) {
  const g = scene.rulers;
  g.clear();
  const st = useStore.getState();
  const show = st.showRulers && !!st.history.present;
  g.visible = show;
  scene.rulerLabels.visible = show;
  if (!show) return;
  const { scale, x: ox, y: oy } = scene.view;
  const w = scene.app.screen.width;
  const h = scene.app.screen.height;
  const bg = C === PALETTES.dark ? 0x232125 : 0xf8f5ef;
  const ink = C === PALETTES.dark ? 0xb5aea3 : 0x5f5950;
  g.rect(0, 0, w, RULER_PX).fill({ color: bg }).rect(0, 0, RULER_PX, h).fill({ color: bg });
  g.moveTo(0, RULER_PX + 0.5).lineTo(w, RULER_PX + 0.5).moveTo(RULER_PX + 0.5, 0).lineTo(RULER_PX + 0.5, h).stroke({ width: 1, color: ink, alpha: 0.5 });
  const sp = gridSpacing(scale, st.units);
  const labels: { text: string; x: number; y: number; vertical: boolean }[] = [];
  const unit = st.units === "in" ? MM_PER_IN : 1;
  for (const l of gridLines((RULER_PX - ox) / scale, (w - ox) / scale, 0, sp)) {
    const sx = Math.round(l.mm * scale + ox) + 0.5;
    g.moveTo(sx, l.major ? 2 : RULER_PX - 5).lineTo(sx, RULER_PX);
    if (l.major) labels.push({ text: fmtRuler(l.mm / unit), x: sx + 2, y: 1, vertical: false });
  }
  for (const l of gridLines((RULER_PX - oy) / scale, (h - oy) / scale, 0, sp)) {
    const sy = Math.round(l.mm * scale + oy) + 0.5;
    g.moveTo(l.major ? 2 : RULER_PX - 5, sy).lineTo(RULER_PX, sy);
    if (l.major) labels.push({ text: fmtRuler(l.mm / unit), x: 1, y: sy + 2, vertical: true });
  }
  g.stroke({ width: 1, color: ink, alpha: 0.8 });
  // Reuse label objects (making new ones on every pan is slow).
  const pool = scene.rulerLabels.children as Text[];
  labels.forEach((lb, i) => {
    let t = pool[i];
    if (!t) {
      t = new Text({ text: "", style: { fontFamily: "Space Mono, monospace", fontSize: 9, fill: ink } });
      scene.rulerLabels.addChild(t);
    }
    t.text = lb.text;
    t.style.fill = ink;
    t.position.set(lb.x, lb.y);
    t.rotation = lb.vertical ? Math.PI / 2 : 0;
    if (lb.vertical) t.position.set(RULER_PX - 2, lb.y);
    t.visible = true;
  });
  for (let i = labels.length; i < pool.length; i++) pool[i].visible = false;
}

const fmtRuler = (v: number) => (Math.abs(v) < 1e-9 ? "0" : Number(v.toFixed(2)).toString());

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

/** The selection's frame, if several things (a group) are selected and `p` is inside it. */
function insideGroupFrame(scene: Scene, p: Pt): Frame | null {
  const f = selectedFrame(scene);
  if (!f || f.kind !== "item" || f.ids.length < 2 || f.locked) return null;
  const xs = f.corners.map((c) => c[0]);
  const ys = f.corners.map((c) => c[1]);
  return p[0] >= Math.min(...xs) && p[0] <= Math.max(...xs) && p[1] >= Math.min(...ys) && p[1] <= Math.max(...ys) ? f : null;
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
    return { kind: "image", index: imgIndex, id: im.id, indices: [imgIndex], ids: [im.id], corners, center: c, knob, up, locked: im.locked, pad: 0 };
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
    pad,
  };
}

/** Side handles show (and work) only on a frame big enough on screen for them not to crowd the corners. */
/** The point a side stretch keeps still: the middle of the opposite side of the shape itself
 *  (inside the frame's padding). */
function stretchAnchor(f: Frame, side: "n" | "e" | "s" | "w"): Pt {
  const m = sideMids(f.corners)[OPPOSITE[side]];
  const a = sideAxis(f.corners, side);
  return [m[0] + a[0] * f.pad, m[1] + a[1] * f.pad];
}

function sidesFit(f: Frame, px: number): boolean {
  const w = Math.hypot(f.corners[1][0] - f.corners[0][0], f.corners[1][1] - f.corners[0][1]) / px;
  const h = Math.hypot(f.corners[3][0] - f.corners[0][0], f.corners[3][1] - f.corners[0][1]) / px;
  return Math.min(w, h) >= HANDLE_PX * 4;
}

function selectedObject(): ObjectItem | null {
  const st = useStore.getState();
  const it = st.history.present?.layout.items.find((x) => x.id === st.selectedId);
  return it && isObject(it) ? it : null;
}

/** What canvas hooks (canvas/hooks.ts) are given. */
function hookCtx(scene: Scene): CanvasCtx {
  return {
    toMm: (e) => {
      const r = scene.app.canvas.getBoundingClientRect(); // fills the host exactly
      return [(e.clientX - r.left - scene.view.x) / scene.view.scale, (e.clientY - r.top - scene.view.y) / scene.view.scale];
    },
    pxMm: () => 1 / scene.view.scale,
    redraw: () => {
      const now = sceneRefForTextures?.(); // the scene on screen: a new render replaces it
      if (now) drawOverlay(now);
    },
  };
}

function drawOverlay(scene: Scene, live?: { id: string; list: NodeList; index: number; at: Pt }) {
  drawOwnOverlay(scene, live);
  // Features' overlays go on top, on every path (drawOwnOverlay returns early on several).
  drawOverlays(scene.overlay, 1 / scene.view.scale, hookCtx(scene));
}

function drawOwnOverlay(scene: Scene, live?: { id: string; list: NodeList; index: number; at: Pt }) {
  const g = scene.overlay;
  g.clear();
  const st = useStore.getState();
  const s = scene.view.scale;
  const px = 1 / s;
  if (st.pen) drawPen(g, st.pen, cursorMm, px);
  if (st.pen && st.edgeFit && !st.edgeFit.original) {
    const fit = st.edgeFit.options[st.edgeFit.index];
    const poly = flatten(fit.nodes, fit.closed);
    if (fit.closed && poly.length) poly.push(poly[0]);
    if (poly.length > 1) {
      const path = () => {
        g.moveTo(poly[0][0], poly[0][1]);
        for (const q of poly.slice(1)) g.lineTo(q[0], q[1]);
      };
      path();
      g.stroke({ width: st.satinWidth, color: C.ghost, alpha: 0.22, join: "round", cap: "round" });
      path();
      g.stroke({ width: 1.5 * px, color: C.ghost, alpha: 0.9 });
    }
  }
  if (st.pen && st.ghost) drawGhost(g, st.pen, st.ghost, px);
  if (st.autoTrace) drawGuess(g, st.autoTrace, px);
  if (st.autoAll) drawWholePicture(g, st.autoAll, px);
  drawGuides(scene, g, px);
  if (st.knife) {
    const pts = st.knife.points;
    const end = pts.length === 1 ? cursorMm : null;
    if (pts.length && end) {
      g.moveTo(pts[0][0], pts[0][1]).lineTo(end[0], end[1]).stroke({ width: 2 * px, color: KNIFE_COLOR });
      g.circle(pts[0][0], pts[0][1], 3.5 * px).fill(KNIFE_COLOR);
    }
  }
  if (st.stitchEdit) drawStitchEdit(scene, g, px);
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
      if (sidesFit(f, px)) {
        const ss = hs * 0.8;
        for (const [hx, hy] of Object.values(sideMids(f.corners))) g.rect(hx - ss / 2, hy - ss / 2, ss, ss).fill(HANDLE_FILL).stroke({ width: 1.5 * px, color: C.select });
      }
      g.circle(f.knob[0], f.knob[1], hs / 2 + px).fill(HANDLE_FILL).stroke({ width: 1.5 * px, color: C.select });
    }
  }

  // Lettering: every letter's start (green) and end (red), smaller, on its own edge.
  const letters = selectedLetters(scene);
  if (letters) {
    for (const part of letters.parts) {
      for (const which of ["start", "end"] as const) {
        const q = liveLetter && liveLetter.id === letters.id && liveLetter.index === part.index && liveLetter.which === which ? liveLetter.at : part[which];
        g.circle(q[0], q[1], LETTER_DOT_PX * px).fill(which === "start" ? ENTRY_COLOR : EXIT_COLOR).stroke({ width: 1.2 * px, color: 0xffffff });
      }
    }
    return;
  }

  // Points of a selected drawn object, its entry (green) and exit (red). A pinned shape shows its
  // outline only (nothing on it can be dragged); with several selected, the dots aren't offered.
  const o = selectedObject();
  if (!o) return;
  const editable = !o.locked && !st.extraIds.length && st.tool === "select";
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
  if (o.kind === "satin" && lists.length > 1) {
    const [ra, rb] = [lists[0].nodes, lists[1].nodes];
    ra.forEach((n, i) => rb[i] && g.moveTo(n[0], n[1]).lineTo(rb[i][0], rb[i][1]));
    g.stroke({ width: 1 * px, color: C.select, alpha: 0.5 });
  }
  const sel = st.selectedNode;
  for (const l of o.locked ? [] : lists) {
    l.nodes.forEach((n, i) => {
      const on = sel && sel.id === o.id && sel.list === l.key && sel.index === i;
      const r = (NODE_PX / 2) * px;
      nodeMark(g, n, r);
      g.fill(on ? HANDLE_FILL : 0xffffff).stroke({ width: 1.5 * px, color: C.select });
    });
  }
  // The purple direction dots and the line between them: the way the rows (or satin) run.
  const dir = editable ? directionDots(o, tipsOut(scene)) : null;
  if (dir) {
    const [d0, d1] = dir.map((q, k) => (liveDir && liveDir.id === o.id && liveDir.which === k ? liveDir.at : q));
    g.moveTo(d0[0], d0[1]).lineTo(d1[0], d1[1]).stroke({ width: 2 * px, color: DIRECTION_COLOR, alpha: 0.95 });
    for (const q of [d0, d1]) g.circle(q[0], q[1], ENDS_PX * px).fill(DIRECTION_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
  }
  const ends = editable && o.kind !== "applique" ? stitchEnds(scene, o) : null;
  if (ends) {
    const at = (which: "start" | "end"): Pt => (liveEnd && liveEnd.id === o.id && liveEnd.which === which ? liveEnd.at : ends[which]);
    const [s0, e0] = [at("start"), at("end")];
    g.circle(s0[0], s0[1], ENDS_PX * px).fill(ENTRY_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
    g.circle(e0[0], e0[1], ENDS_PX * px).fill(EXIT_COLOR).stroke({ width: 1.5 * px, color: 0xffffff });
  }
}

/** Size of the start and end dots (radius, screen pixels). */
const ENDS_PX = 5;

/** The start (green) or red (end) dot being dragged (or let go and waiting for its new stitches),
 *  to draw it where it will go. Each belongs to one shape. */
let liveEnd: { id: string; which: "start" | "end"; at: Pt } | null = null;
/** A purple direction dot being dragged. */
let liveDir: { id: string; which: 0 | 1; at: Pt } | null = null;
const DIRECTION_COLOR = 0x8b5cf6;

/** A lettering letter's dot being dragged. */
let liveLetter: { id: string; index: number; which: "start" | "end"; at: Pt } | null = null;
const LETTER_DOT_PX = 3.5;

/** The selected lettering (alone) and its letters, as the engine last drew them. */
function selectedLetters(scene: Scene): { id: string; parts: NonNullable<LayoutItemInfo["letters"]> } | null {
  const st = useStore.getState();
  const doc = st.history.present;
  if (!doc || !st.selectedId || st.extraIds.length || st.tool !== "select") return null;
  const i = doc.layout.items.findIndex((it) => it.id === st.selectedId);
  const it = doc.layout.items[i];
  const parts = scene.design?.items?.[i]?.letters;
  // Letters made of stitches sew their file's own stitches: no start or end to move.
  const dots = parts?.filter((p) => p.kind !== "stitches");
  if (!it || it.kind !== "text" || it.locked || !dots?.length) return null;
  // While single letters are adjusted, their dots are the letters', not their starts and ends.
  return useLetterMode.getState().id === it.id ? null : { id: it.id, parts: dots };
}

/** The purple dots of a drawn shape: a fill's stitch direction, or a satin column's two tips
 *  (drawn just past each end, `out` mm, clear of the start and end dots). */
function directionDots(o: ObjectItem, out = 0): [Pt, Pt] | null {
  return fillDirection(o) ?? columnTips(o, out);
}

/** How far past a satin's ends its purple dots sit: a few pixels at any zoom. */
const tipsOut = (scene: Scene) => (ENDS_PX * 5) / scene.view.scale;

/** Where a dragged start or end dot goes: it follows the edge nearest the pointer, like a magnet.
 *  A fill starts on its outside edge and can end on any edge (a hole's too); a border or a satin
 *  anywhere along it. An open line's dots move its end points. */
function snapEnd(o: ObjectItem, which: "start" | "end", p: Pt): Pt {
  if (o.kind === "fill") {
    const g = o.geometry as { outline: PathNode[]; holes?: PathNode[][] };
    const rings = [flatten(g.outline, true), ...(which === "end" ? (g.holes ?? []).map((h) => flatten(h, true)) : [])];
    return nearestOnRings(rings, p);
  }
  const geo = o.geometry as { nodes?: PathNode[]; closed?: boolean };
  if (geo.nodes && geo.closed) return nearestOnLine(flatten(geo.nodes, true), p, true);
  // A satin starts and stops anywhere along it: a ribbon on its middle line, a column on its edge.
  if (o.kind === "satin" && geo.nodes) return nearestOnLine(flatten(geo.nodes), p, false);
  if (o.kind === "satin") return nearestOnLine(columnRing(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] }), p, true);
  return p;
}

/** Where a dragged purple dot goes: along the fill's outline, or round the satin column's outline. */
function snapDirection(o: ObjectItem, p: Pt): Pt {
  if (o.kind === "fill") return nearestOnLine(fillRing(o), p, true);
  return nearestOnLine(columnRing(o.geometry as { rail_a: PathNode[]; rail_b: PathNode[] }), p, true);
}

/** Where a drawn shape's stitching starts and ends (its first and last needle drop), mm. A shape
 *  sewn in a branch has none of its own: the branch's dots show (canvas/branchOverlay.ts). */
function stitchEnds(scene: Scene, o: ObjectItem): { start: Pt; end: Pt } | null {
  const d = scene.design;
  const idx = useStore.getState().history.present?.layout.items.indexOf(o) ?? -1;
  if (!d?.records.item || idx < 0 || d.branches?.some((b) => b.items.includes(o.id))) return null;
  const { x, y, kind, item } = d.records;
  let first = -1;
  let last = -1;
  for (let i = 0; i < kind.length; i++) {
    if (item[i] === idx && kind[i] === Kind.Stitch) {
      if (first < 0) first = i;
      last = i;
    }
  }
  return first >= 0 ? { start: [x[first], y[first]], end: [x[last], y[last]] } : null;
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
    // A satin ribbon: its centre line, and a band as wide as the satin will be.
    const poly = pen.closed ? flatten(pen.a, true) : flatten(withCursor(pen.a));
    if (pen.closed && poly.length) poly.push(poly[0]);
    line(poly, useStore.getState().satinWidth, 0.3);
    line(poly, 1.5 * px, 1);
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

const KNIFE_COLOR = 0xd23a2a;
const GUIDE_COLOR = 0x2f8fd8;

/** A guide being dragged (from a ruler, or an existing one); null when none. */
let liveGuide: { index: number | null; axis: "x" | "y"; at: number } | null = null;
/** Stitch editing in progress: a box being drawn, or the selected stitches being moved. */
let liveStitches: { mode: "box" | "move"; from: Pt; to: Pt } | null = null;
/** Shift was held when the stitch-edit box started (add to the selection). */
let liveShift = false;

function drawGuides(scene: Scene, g: Graphics, px: number) {
  const guides = [...(useStore.getState().history.present?.layout.guides ?? [])];
  if (liveGuide) {
    if (liveGuide.index === null) guides.push({ axis: liveGuide.axis, at: liveGuide.at });
    else guides[liveGuide.index] = { axis: liveGuide.axis, at: liveGuide.at };
  }
  if (!guides.length) return;
  const s = scene.view.scale;
  const x0 = -scene.view.x / s;
  const y0 = -scene.view.y / s;
  const x1 = x0 + scene.app.screen.width / s;
  const y1 = y0 + scene.app.screen.height / s;
  for (const gd of guides) {
    if (gd.axis === "x") g.moveTo(gd.at, y0).lineTo(gd.at, y1);
    else g.moveTo(x0, gd.at).lineTo(x1, gd.at);
  }
  g.stroke({ width: 1.2 * px, color: GUIDE_COLOR, alpha: 0.85 });
}

/** Every shape "whole picture" found: fills shaded in their color, ribbons as bands, lines thin. */
function drawWholePicture(g: Graphics, a: NonNullable<ReturnType<typeof useStore.getState>["autoAll"]>, px: number) {
  const alpha = a.busy ? 0.35 : 1;
  for (const sh of a.shapes) {
    const color = parseInt(sh.color.slice(1), 16);
    if (sh.kind === "fill") {
      const outer = flatten(sh.outline, true);
      if (outer.length > 2) g.poly(outer.flat()).fill({ color, alpha: 0.55 * alpha }).stroke({ width: 1.5 * px, color: C.ghost, alpha });
      continue;
    }
    const poly = flatten(sh.nodes, sh.closed);
    if (poly.length < 2) continue;
    const path = () => {
      g.moveTo(poly[0][0], poly[0][1]);
      for (const q of poly.slice(1)) g.lineTo(q[0], q[1]);
      if (sh.closed) g.closePath();
    };
    path();
    g.stroke({ width: sh.kind === "satin" ? sh.width_mm : 1.5 * px, color, alpha: 0.8 * alpha });
  }
}

/** The stitch file's needle points while editing stitches: selected ones filled (and moved along). */
function drawStitchEdit(scene: Scene, g: Graphics, px: number) {
  const st = useStore.getState();
  const e = st.stitchEdit!;
  const d = scene.design;
  const idx = st.history.present?.layout.items.findIndex((it) => it.id === e.id) ?? -1;
  if (!d?.records.item || !d.records.src || idx < 0) return;
  const sel = new Set(e.selected);
  const { x, y, kind, src } = d.records;
  const off = liveStitches?.mode === "move" ? [liveStitches.to[0] - liveStitches.from[0], liveStitches.to[1] - liveStitches.from[1]] : [0, 0];
  const r = 2.2 * px;
  // Only the points on screen, and one per few pixels: a 30,000-stitch file stays smooth to drag.
  const s = scene.view.scale;
  const [vx0, vy0] = [-scene.view.x / s - r, -scene.view.y / s - r];
  const [vx1, vy1] = [vx0 + scene.app.screen.width / s + 2 * r, vy0 + scene.app.screen.height / s + 2 * r];
  const cell = 3 * px;
  const seen = [new Set<number>(), new Set<number>()];
  const shown = (px0: number, py0: number, selected: boolean) => {
    if (px0 < vx0 || px0 > vx1 || py0 < vy0 || py0 > vy1) return false;
    const key = Math.floor((px0 - vx0) / cell) * 100003 + Math.floor((py0 - vy0) / cell);
    const set = seen[selected ? 1 : 0];
    if (set.has(key)) return false;
    set.add(key);
    return true;
  };
  for (let i = 0; i < kind.length; i++) {
    if (!pickable(d.records, idx, i) || sel.has(src![i]) || !shown(x[i], y[i], false)) continue;
    g.rect(x[i] - r, y[i] - r, 2 * r, 2 * r);
  }
  g.fill({ color: 0xffffff, alpha: 0.9 }).stroke({ width: 0.8 * px, color: C.select, alpha: 0.7 });
  for (let i = 0; i < kind.length; i++) {
    if (!pickable(d.records, idx, i) || !sel.has(src![i]) || !shown(x[i] + off[0], y[i] + off[1], true)) continue;
    g.circle(x[i] + off[0], y[i] + off[1], r * 1.4);
  }
  g.fill({ color: KNIFE_COLOR }).stroke({ width: 0.8 * px, color: 0xffffff });
  if (liveStitches?.mode === "box") {
    const [a, b] = [liveStitches.from, liveStitches.to];
    g.rect(Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])).stroke({ width: px, color: C.select });
  }
}

/** Auto-trace's guess: the outline (or ribbon) it found, with the points it would place. */
function drawGuess(g: Graphics, a: AutoTrace, px: number) {
  const guess = a.guesses[a.index];
  if (!guess) return;
  const alpha = a.busy ? 0.35 : 1;
  const lists = guessLists(guess);
  if (guess.kind === "fill") {
    for (const part of [guess.outline, ...(guess.parts ?? []).map((p) => p.outline)]) {
      const outer = flatten(part, true);
      if (outer.length > 2) g.poly(outer.flat()).fill({ color: C.ghost, alpha: 0.18 * alpha });
    }
  }
  for (const l of lists) {
    const poly = flatten(l.nodes, l.closed);
    if (poly.length < 2) continue;
    const path = () => {
      g.moveTo(poly[0][0], poly[0][1]);
      for (const p of poly.slice(1)) g.lineTo(p[0], p[1]);
      if (l.closed) g.closePath();
    };
    if (guess.kind === "satin") {
      path();
      g.stroke({ width: guess.width_mm, color: C.ghost, alpha: 0.3 * alpha });
    }
    path();
    g.stroke({ width: 2 * px, color: C.ghost, alpha });
  }
  const r = 3.5 * px;
  for (const l of lists) for (const n of l.nodes) nodeMark(g, n, r);
  g.fill({ color: 0xffffff, alpha }).stroke({ width: 1.5 * px, color: C.ghost, alpha });
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
  const product = new Graphics();
  world.addChild(product, pictures, hoop, stitches);
  const chunks = d ? chunkBlocks(d) : [];
  const { realistic, showWire } = useStore.getState();
  const real: (ThreadChunk | null)[] = [];
  const full: Container[] = chunks.map((c) => {
    const color = d!.threads[c.thread]?.color ?? "#808080";
    if (realistic && !showWire) {
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
  // Needle path view: the density map goes under the hairlines, so a dense spot reads stitch by stitch.
  if (showWire) world.addChildAt(heat, world.getChildIndex(stitches));
  const rulers = new Graphics();
  const rulerLabels = new Container();
  app.stage.addChild(rulers, rulerLabels);
  const view = prev ?? fitView(fitBounds(d), app.screen.width, app.screen.height);
  const scene: Scene = {
    app, grid, world, pictures, hoop, stitches, chunks, full, real, points, partial, jumps, needle, overlay, heat, split, design: d, view,
    autoFit: prev === null, product, rulers, rulerLabels,
  };
  applyView(scene);
  drawPictures(scene);
  drawProduct(scene);
  return scene;
}

/** Redraw everything whose line width depends on zoom, and the playhead state. */
function refresh(scene: Scene) {
  const s = useStore.getState();
  scene.stitches.visible = s.showStitches;
  scene.stitches.alpha = restingAlpha();
  scene.pictures.visible = s.showPictures;
  drawPoints(scene, s.showPoints || s.showWire);
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

/** After a pan: needle points and stitch-edit points are drawn only near the screen, so bring
 *  in the ones that have come into view. */
function afterPan(scene: Scene) {
  const st = useStore.getState();
  if (st.showPoints || st.showWire) drawPoints(scene, true);
  if (st.stitchEdit) drawOverlay(scene);
}

/** Needle points (P): a dot where the needle goes down, in a colour that shows on any thread.
 *  The needle path view has them too: small ink dots, the same size at any zoom. */
function drawPoints(scene: Scene, show: boolean) {
  const g = scene.points;
  g.clear();
  const d = scene.design;
  if (!show || !d) return;
  const { x, y, kind } = d.records;
  const s = scene.view.scale;
  const wire = !useStore.getState().showPoints; // only the needle path view asks for them
  const r = wire ? 1.6 / s : Math.max(0.08, 1.6 / s);
  // A 40,000-stitch design: only points near the screen (one screen's width around it, so a pan
  // still shows them; redrawn when the pan ends), and one per couple of pixels.
  const [w, h] = [scene.app.screen.width / s, scene.app.screen.height / s];
  const [vx0, vy0] = [-scene.view.x / s - w, -scene.view.y / s - h];
  const [vx1, vy1] = [vx0 + 3 * w, vy0 + 3 * h];
  const cell = Math.max(r, 2 / s);
  const seen = new Set<number>();
  for (let i = 0; i < kind.length; i++) {
    if (kind[i] !== Kind.Stitch) continue;
    const px = x[i];
    const py = y[i];
    if (px < vx0 || px > vx1 || py < vy0 || py > vy1) continue;
    const key = Math.floor((px - vx0) / cell) * 1000003 + Math.floor((py - vy0) / cell);
    if (seen.has(key)) continue;
    seen.add(key);
    g.circle(px, py, r);
  }
  if (wire) g.fill({ color: C.select });
  else g.fill({ color: 0xffffff, alpha: 0.9 }).stroke({ width: 0.6 / s, color: 0x121114, alpha: 0.9 });
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
  scene.stitches.alpha = Math.min(DIM_ALPHA, restingAlpha());
  scene.overlay.visible = false;
  scene.world.addChild(ghost);
  return ghost;
}

function endGhost(scene: Scene, ghost: Container | null) {
  if (ghost && !ghost.destroyed) ghost.destroy({ children: true });
  scene.stitches.alpha = restingAlpha();
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
  const seeThrough = useStore((s) => s.seeThrough);
  const edgeFit = useStore((s) => s.edgeFit);
  const showPictures = useStore((s) => s.showPictures);
  const crosshair = useStore((s) => s.crosshair);
  const ruler = useStore((s) => s.ruler);
  const angleFor = useStore((s) => s.angleFor);
  const spaceHeld = useStore((s) => s.spaceDown);
  useEffect(() => {
    host.current?.classList.toggle("space-pan", spaceHeld);
  }, [spaceHeld]);
  const selectedId = useStore((s) => s.selectedId);
  const extraIds = useStore((s) => s.extraIds);
  const selectedNode = useStore((s) => s.selectedNode);
  const realistic = useStore((s) => s.realistic);
  const tool = useStore((s) => s.tool);
  const pen = useStore((s) => s.pen);
  const measure = useStore((s) => s.measure);
  const ghost = useStore((s) => s.ghost);
  const autoTrace = useStore((s) => s.autoTrace);
  const autoAll = useStore((s) => s.autoAll);
  const knife = useStore((s) => s.knife);
  const stitchEdit = useStore((s) => s.stitchEdit);
  const guides = useStore((s) => s.history.present?.layout.guides);
  const preview = useStore((s) => s.preview);
  const showRulers = useStore((s) => s.showRulers);
  const showWire = useStore((s) => s.showWire);
  const repairMarks = useRepairHighlight((s) => s.shown); // "Show on the design" (an overlay)
  const letterMode = useLetterMode(); // adjusting single letters (an overlay)

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
      })
      .catch((err: unknown) => {
        // Never fail silently: a blank design area with no explanation is the worst outcome.
        console.error("The design area couldn't start", err);
        useStore.getState().notify({
          kind: "error",
          text: `The design area couldn't start (${err instanceof Error ? err.message : String(err)}). Please report this at github.com/jvanekel-pixel/ludd/issues.`,
        });
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
  }, [design, hasDoc, realistic, showWire, canvasDark]);

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
  }, [selectedId, extraIds, selectedNode, tool, pen, images, measure, ghost, autoTrace, autoAll, knife, stitchEdit, guides, edgeFit, repairMarks, letterMode]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawProduct(scene);
  }, [preview]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (scene) drawRulers(scene);
  }, [showRulers, units, canvasDark, hasDoc]);

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
  }, [showPoints, showStitches, showPictures, crosshair, ruler, angleFor, seeThrough]);

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
    if (zoomRequest.kind === "pan" && zoomRequest.pan) {
      // Arrow keys while drawing: the view moves, the design stays put.
      scene.view = { ...v, x: v.x - zoomRequest.pan[0] * v.scale, y: v.y - zoomRequest.pan[1] * v.scale };
    } else if (zoomRequest.kind === "box" && zoomRequest.box) {
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

    // Auto-pan: while drawing, a pointer within EDGE_PX of the edge scrolls the view that way,
    // faster the closer it is.
    const EDGE_PX = 28;
    const EDGE_SPEED = 14; // px per frame at the very edge
    let edge: [number, number] = [0, 0];
    let edgeFrame = 0;
    let wheelFrame = 0;
    const stepAutoPan = () => {
      const scene = sceneRef.current;
      if (!scene || (!edge[0] && !edge[1]) || !useStore.getState().pen) {
        edgeFrame = 0;
        return;
      }
      scene.view = { ...scene.view, x: scene.view.x - edge[0], y: scene.view.y - edge[1] };
      scene.autoFit = false;
      applyView(scene);
      refresh(scene);
      edgeFrame = requestAnimationFrame(stepAutoPan);
    };
    const autoPan = (sx: number, sy: number) => {
      const r = el.getBoundingClientRect();
      const pull = (d: number) => (d < EDGE_PX ? EDGE_SPEED * (1 - Math.max(0, d) / EDGE_PX) : 0);
      edge = [pull(r.width - sx) - pull(sx), pull(r.height - sy) - pull(sy)];
      if ((edge[0] || edge[1]) && !edgeFrame) edgeFrame = requestAnimationFrame(stepAutoPan);
    };
    const stopAutoPan = () => {
      edge = [0, 0];
      if (edgeFrame) cancelAnimationFrame(edgeFrame);
      edgeFrame = 0;
    };
    let releaseEsc: (() => void) | null = null;

    /** Esc during a drag lets go: the shape, point or picture goes back where it was. */
    const cancelDrag = () => {
      const scene = sceneRef.current;
      const d = drag;
      drag = null;
      // Every way out of a drag (Esc, the window losing focus, a cancelled touch) gives back its
      // Esc booking, so the next Esc press does something visible. (Releasing twice is harmless.)
      const release = releaseEsc;
      releaseEsc = null;
      release?.();
      if (el.hasPointerCapture(dragPointer)) el.releasePointerCapture(dragPointer);
      el.classList.remove("panning");
      liveGuide = null;
      liveStitches = null;
      refreshCursor();
      if (!scene || !d) return;
      if (d.kind === "pan") return afterPan(scene);
      if (d.kind === "guide" || d.kind === "stitches") return drawOverlay(scene);
      if (d.kind === "ends" || d.kind === "dir" || d.kind === "letter") {
        liveEnd = null;
        liveDir = null;
        liveLetter = null;
        return drawOverlay(scene);
      }
      if (d.kind === "node") {
        scene.stitches.alpha = restingAlpha();
        return drawOverlay(scene);
      }
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
      const reach = SNAP_PX / scene.view.scale;
      // Points near a guide land on it (also with Snap to grid on: the guide wins on its axis).
      let gx: number | null = null;
      let gy: number | null = null;
      for (const gd of st.history.present?.layout.guides ?? []) {
        if (gd.axis === "x" && Math.abs(p[0] - gd.at) < reach && (gx === null || Math.abs(p[0] - gd.at) < Math.abs(p[0] - gx))) gx = gd.at;
        if (gd.axis === "y" && Math.abs(p[1] - gd.at) < reach && (gy === null || Math.abs(p[1] - gd.at) < Math.abs(p[1] - gy))) gy = gd.at;
      }
      if (st.snapGrid) {
        const step = gridSpacing(scene.view.scale, st.units).minorMm;
        return [gx ?? Math.round(p[0] / step) * step, gy ?? Math.round(p[1] / step) * step];
      }
      if (gx !== null || gy !== null) return [gx ?? p[0], gy ?? p[1]];
      const hooked = snapToSources(p, reach); if (hooked) return hooked;
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

    /** The guide under the pointer (within a few pixels), if any. */
    const guideAt = (scene: Scene, sx: number, sy: number): number | null => {
      const guides = useStore.getState().history.present?.layout.guides ?? [];
      const p = toWorld(scene, sx, sy);
      const reach = 4 / scene.view.scale;
      const i = guides.findIndex((gd) => Math.abs((gd.axis === "x" ? p[0] : p[1]) - gd.at) <= reach);
      return i >= 0 ? i : null;
    };
    /** Stitch editing: the file index of the stitch under the pointer (within a few pixels). */
    const stitchAt = (scene: Scene, sx: number, sy: number): number | null => {
      const st = useStore.getState();
      const d = scene.design;
      const idx = st.history.present?.layout.items.findIndex((it) => it.id === st.stitchEdit?.id) ?? -1;
      if (!d?.records.item || !d.records.src || idx < 0) return null;
      const p = toWorld(scene, sx, sy);
      return nearestStitch(d.records, idx, p[0], p[1], 6 / scene.view.scale);
    };
    /** The selected shape's start or end dot under the pointer (applique and lettering have none
     *  to move). The end dot wins where both sit together. */
    const endAt = (scene: Scene, sx: number, sy: number): { id: string; which: "start" | "end"; at: Pt } | null => {
      const st = useStore.getState();
      if (st.tool !== "select" || st.extraIds.length) return null;
      const o = selectedObject();
      if (!o || o.locked || o.kind === "applique") return null;
      const ends = stitchEnds(scene, o);
      if (!ends) return null;
      // Open fill patterns (contour, stipple, cross-stitch…) end where their pattern does: their red
      // dot shows it but can't be moved.
      const fixedEnd = o.kind === "fill" && fixedFillEnd((o.params as { pattern?: string }).pattern);
      for (const which of ["end", "start"] as const) {
        if (which === "end" && fixedEnd) continue;
        if (near(scene, ends[which], sx, sy, ENDS_PX + 3)) return { id: o.id, which, at: ends[which] };
      }
      return null;
    };

    /** A letter's start or end dot under the pointer (the selected lettering's). */
    const letterAt = (scene: Scene, sx: number, sy: number): { id: string; index: number; which: "start" | "end"; at: Pt } | null => {
      const sel = selectedLetters(scene);
      if (!sel || handleAt(scene, sx, sy)) return null;
      // The end wins where a letter's end and the next one's start meet.
      for (const which of ["end", "start"] as const)
        for (const part of sel.parts) if (near(scene, part[which], sx, sy, LETTER_DOT_PX + 3)) return { id: sel.id, index: part.index, which, at: part[which] };
      return null;
    };

    /** The selected shape's purple direction dot under the pointer. */
    const dirAt = (scene: Scene, sx: number, sy: number): { id: string; which: 0 | 1; at: Pt } | null => {
      const st = useStore.getState();
      if (st.tool !== "select" || st.extraIds.length) return null;
      const o = selectedObject();
      if (!o || o.locked || handleAt(scene, sx, sy)) return null;
      const dots = directionDots(o, tipsOut(scene));
      if (!dots) return null;
      for (const which of [0, 1] as const) if (near(scene, dots[which], sx, sy, ENDS_PX + 3)) return { id: o.id, which, at: dots[which] };
      return null;
    };

    const nodeAt = (scene: Scene, sx: number, sy: number) => {
      const o = useStore.getState().tool === "select" ? selectedObject() : null;
      if (!o || o.locked) return null;
      for (const l of nodeLists(o)) {
        for (let i = l.nodes.length - 1; i >= 0; i--) {
          if (near(scene, [l.nodes[i][0], l.nodes[i][1]], sx, sy, NODE_PX)) return { o, list: l.key, index: i };
        }
      }
      return null;
    };

    /** The frame handle under the pointer: the turn knob, a corner (resize) or a side (stretch). */
    const handleAt = (scene: Scene, sx: number, sy: number): { drag: "scale" | "rotate"; at: Pt; side?: "n" | "e" | "s" | "w" } | null => {
      const f = selectedFrame(scene);
      if (!f || f.locked) return null;
      if (near(scene, f.knob, sx, sy, HANDLE_PX)) return { drag: "rotate", at: f.knob };
      const corner = f.corners.find((c) => near(scene, c, sx, sy, HANDLE_PX));
      if (corner) return { drag: "scale", at: corner };
      if (sidesFit(f, 1 / scene.view.scale)) {
        const mids = sideMids(f.corners);
        for (const side of ["n", "e", "s", "w"] as const) if (near(scene, mids[side], sx, sy, HANDLE_PX)) return { drag: "scale", at: mids[side], side };
      }
      return null;
    };

    /** What's under the pointer: a layout item (topmost) or, below everything, an unlocked picture. */
    // ---------------------------------------------------------------- the mouse pointer
    // One place decides it, from what a click or drag would do right here (see cursors.ts). It's
    // worked out again whenever the pointer moves, a key is pressed or let go, or the app changes.
    let pointerAt: { sx: number; sy: number; ctrlKey: boolean; metaKey: boolean; shiftKey: boolean } | null = null;
    let shownCursor: CursorName | null = null;

    const cursorHere = (scene: Scene, sx: number, sy: number, keys: { ctrlKey: boolean; metaKey: boolean; shiftKey: boolean }): CursorName => {
      const st = useStore.getState();
      if (drag) {
        switch (drag.kind) {
          case "pan":
            return "grabbing";
          case "move":
            return "move";
          case "scale":
            return drag.look ?? "resize";
          case "rotate":
            return "rotate";
          case "node":
          case "ends":
          case "dir":
          case "letter":
            return "point";
          case "guide":
            return liveGuide?.axis === "x" ? "guide-x" : "guide-y";
          case "stitches":
            return liveStitches?.mode === "move" ? "move" : "stitch";
        }
      }
      if (st.spaceDown) return "grab";
      if (st.autoTrace?.busy || st.autoAll?.busy) return "busy";
      // The same order as a click (startPointer): rulers, then the tool or mode in use, then Select.
      if (st.showRulers && (sx < RULER_PX || sy < RULER_PX)) return sx < RULER_PX && sy < RULER_PX ? "arrow" : sy < RULER_PX ? "guide-y" : "guide-x";
      if (st.knife) return "knife";
      if (st.stitchEdit) {
        const i = stitchAt(scene, sx, sy);
        return i === null ? "stitch" : st.stitchEdit.selected.includes(i) ? "move" : "point";
      }
      if (st.ruler || st.measure) return "measure";
      if (st.angleFor) return "angle";
      if (st.tool === "text") return "text";
      if (st.tool === "autotrace") return "autotrace";
      if (st.tool === "run" || st.tool === "satin" || st.tool === "fill") return `draw-${st.tool}-${pointKind(keys)}`;
      if (letterAt(scene, sx, sy) || endAt(scene, sx, sy) || dirAt(scene, sx, sy)) return "point";
      const node = nodeAt(scene, sx, sy);
      if (node) return "point";
      const gi = guideAt(scene, sx, sy);
      if (gi !== null) return st.history.present?.layout.guides?.[gi]?.axis === "x" ? "guide-x" : "guide-y";
      const h = handleAt(scene, sx, sy);
      if (h) return h.drag === "rotate" ? "rotate" : resizeCursorFor(h.at, selectedFrame(scene)!.center);
      if (pick(scene, toWorld(scene, sx, sy)) || insideGroupFrame(scene, toWorld(scene, sx, sy))) return "move";
      return st.crosshair ? "precise" : "arrow";
    };

    const refreshCursor = () => {
      const scene = sceneRef.current;
      if (!scene || !pointerAt) return;
      const name = cursorHere(scene, pointerAt.sx, pointerAt.sy, pointerAt);
      if (name === shownCursor) return;
      shownCursor = name;
      el.style.cursor = cursorCss(name);
    };
    const onKeyForCursor = (e: KeyboardEvent) => {
      if (!pointerAt) return;
      pointerAt = { ...pointerAt, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey };
      refreshCursor();
    };
    // Only changes that can change the pointer (not, say, every frame of the stitch-out player).
    const CURSOR_STATE = ["tool", "knife", "stitchEdit", "ruler", "measure", "angleFor", "spaceDown", "autoTrace", "autoAll", "crosshair", "showRulers", "selectedId", "extraIds", "selectedNode", "design"] as const;
    const unsubscribeCursor = useStore.subscribe((now, before) => {
      if (CURSOR_STATE.some((k) => now[k] !== before[k])) refreshCursor();
    });

    const pick = (scene: Scene, p: Pt): { id: string } | null => {
      const doc = currentDoc();
      if (!doc) return null;
      if (scene.design) {
        const hit = hitTest(scene.design, p[0], p[1], 4 / scene.view.scale);
        if (hit !== null && doc.layout.items[hit]) return { id: doc.layout.items[hit].id };
      }
      // Pictures hidden (B) can't be clicked or dragged.
      for (let i = useStore.getState().showPictures ? doc.images.length - 1 : -1; i >= 0; i--) {
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
      // A burst of wheel events redraws the zoom-dependent parts (needle points, trims, handles)
      // once per frame, not once per event: smooth on big designs.
      if (!wheelFrame)
        wheelFrame = requestAnimationFrame(() => {
          wheelFrame = 0;
          if (sceneRef.current) refresh(sceneRef.current);
        });
    };

    const onDown = (e: PointerEvent) => {
      // A drag whose button came up somewhere we didn't hear about is over: drop it, so its Esc
      // booking can't swallow the next Esc press.
      // A second finger or pen while dragging: the drag goes back, and the new pointer does nothing.
      if (drag || releaseEsc) {
        const other = drag !== null && e.pointerId !== dragPointer;
        cancelDrag();
        if (other) return;
      }
      // Space held: the hand tool. Dragging only moves the view; nothing is selected, drawn or moved.
      if (useStore.getState().spaceDown && (e.button === 0 || e.button === 1)) {
        el.setPointerCapture(e.pointerId);
        drag = { kind: "pan", x: e.clientX, y: e.clientY, moved: false, deselect: false };
        dragPointer = e.pointerId;
        releaseEsc ??= holdEscape(cancelDrag);
        refreshCursor();
        return;
      }
      startPointer(e);
      if (drag && !releaseEsc) {
        dragPointer = e.pointerId;
        releaseEsc = holdEscape(cancelDrag);
      }
      refreshCursor();
    };

    const startPointer = (e: PointerEvent) => {
      const scene = sceneRef.current;
      if (!scene || e.button > 2) return;
      if (runCanvasTool("down", e, hookCtx(scene))) return;
      const [sx, sy] = local(e);
      const st = useStore.getState();
      if (e.button === 1) {
        el.setPointerCapture(e.pointerId);
        drag = { kind: "pan", x: e.clientX, y: e.clientY, moved: false, deselect: false };
        return;
      }
      // Drag a guide out of a ruler.
      if (st.showRulers && e.button === 0 && (sx < RULER_PX || sy < RULER_PX) && !(sx < RULER_PX && sy < RULER_PX)) {
        const p = toWorld(scene, sx, sy);
        const axis = sy < RULER_PX ? "y" : "x";
        liveGuide = { index: null, axis, at: axis === "x" ? p[0] : p[1] };
        drag = { kind: "guide", startX: sx, startY: sy, moved: false };
        el.setPointerCapture(e.pointerId);
        return;
      }
      // The knife: two clicks make the cut.
      if (st.knife && e.button === 0) {
        // Snapped like any drawn point (shape points, guides, the grid), so a cut can start exactly on a corner.
        const p = snapped(scene, toWorld(scene, sx, sy), e);
        if (st.knife.points.length) void finishKnife(st.knife.points[0], p);
        else st.setKnife({ ...st.knife, points: [p] });
        return;
      }
      // Stitch editing: pick stitches (Shift adds), drag them, or drag a box round some.
      if (st.stitchEdit && e.button === 0) {
        const hitIndex = stitchAt(scene, sx, sy);
        const e2 = st.stitchEdit;
        const p = toWorld(scene, sx, sy);
        if (hitIndex !== null && e2.selected.includes(hitIndex) && !e.shiftKey) {
          // Dragging a selected stitch moves all the selected ones.
          liveStitches = { mode: "move", from: p, to: p };
          drag = { kind: "stitches", startX: sx, startY: sy, moved: false, shift: false };
        } else {
          // A click picks the stitch under it (Shift: adds or takes it away); a drag draws a box.
          if (hitIndex !== null) {
            const already = e2.selected.includes(hitIndex);
            st.setStitchEdit({ ...e2, selected: e.shiftKey ? (already ? e2.selected.filter((i) => i !== hitIndex) : [...e2.selected, hitIndex]) : [hitIndex] });
          }
          liveStitches = { mode: "box", from: p, to: p };
          drag = { kind: "stitches", startX: sx, startY: sy, moved: false, shift: e.shiftKey || hitIndex !== null };
          liveShift = e.shiftKey;
        }
        el.setPointerCapture(e.pointerId);
        drawOverlay(scene);
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
        // On a text already there: pick it, to change its words in the panel.
        const on = pick(scene, p);
        const onText = on && currentLayout()?.items.find((it) => it.id === on.id && it.kind === "text");
        if (onText) st.select(onText.id);
        else void addText(p[0], p[1]);
        return;
      }
      // Auto-trace: a click asks for guesses; a right-click uses the one shown.
      if (st.tool === "autotrace") {
        if (e.button === 2) void acceptGuess();
        else if (e.button === 0) {
          const p = toWorld(scene, sx, sy);
          void autoTraceAt(round2(p[0]), round2(p[1]), e.shiftKey ? "add" : e.altKey ? "subtract" : "new");
        }
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
      const letterHit = e.button === 0 ? letterAt(scene, sx, sy) : null;
      if (letterHit) {
        drag = { kind: "letter", id: letterHit.id, index: letterHit.index, which: letterHit.which, startX: sx, startY: sy, moved: false, at: letterHit.at };
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          // A pointer that's already gone: the window still hears it.
        }
        return;
      }
      const dirHit = e.button === 0 && !endAt(scene, sx, sy) ? dirAt(scene, sx, sy) : null;
      if (dirHit) {
        st.selectNode(null);
        drag = { kind: "dir", id: dirHit.id, which: dirHit.which, startX: sx, startY: sy, moved: false, at: dirHit.at };
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          // A pointer that's already gone: the window still hears it.
        }
        return;
      }
      const end = e.button === 0 ? endAt(scene, sx, sy) : null;
      if (end) {
        st.selectNode(null);
        drag = { kind: "ends", id: end.id, which: end.which, startX: sx, startY: sy, moved: false, at: end.at };
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          // A pointer that's already gone: the window still hears it.
        }
        return;
      }
      const node = nodeAt(scene, sx, sy);
      if (node) {
        if (e.button === 2) {
          toggleNodeKind(node.o.id, node.list, node.index);
          return;
        }
        st.selectNode({ id: node.o.id, list: node.list, index: node.index });
        // While a point is held, the thread fades so the outline and points are easy to see.
        scene.stitches.alpha = Math.min(NODE_DIM_ALPHA, restingAlpha());
        const n = nodeLists(node.o).find((l) => l.key === node.list)!.nodes[node.index];
        drag = { kind: "node", id: node.o.id, list: node.list, index: node.index, startX: sx, startY: sy, moved: false, at: [n[0], n[1]] };
        try {
          el.setPointerCapture(e.pointerId);
        } catch {
          // A pointer that's already gone (the button came up first): the window still hears it.
        }
        return;
      }
      if (e.button === 2) return;
      st.selectNode(null);
      // Grab a guide to move it (drop it on a ruler to remove it).
      const gi = guideAt(scene, sx, sy);
      if (gi !== null && e.button === 0) {
        const gd = st.history.present!.layout.guides![gi];
        liveGuide = { index: gi, axis: gd.axis, at: gd.at };
        drag = { kind: "guide", startX: sx, startY: sy, moved: false };
        el.setPointerCapture(e.pointerId);
        return;
      }
      const handle = handleAt(scene, sx, sy);
      const frame = selectedFrame(scene);
      if (handle && frame) {
        el.setPointerCapture(e.pointerId);
        drag = {
          kind: handle.drag,
          frame,
          startX: sx,
          startY: sy,
          startW: toWorld(scene, sx, sy),
          ghost: null,
          moved: false,
          side: handle.side,
          look: handle.drag === "rotate" ? "rotate" : resizeCursorFor(handle.at, frame.center),
        };
        return;
      }
      let hit = pick(scene, toWorld(scene, sx, sy));
      el.setPointerCapture(e.pointerId);
      // Inside a group's frame, a picture underneath doesn't take the click from the group.
      if (hit && !currentLayout()?.items.some((it) => it.id === hit!.id) && insideGroupFrame(scene, toWorld(scene, sx, sy))) hit = null;
      if (hit) {
        const isItem = !!currentLayout()?.items.some((it) => it.id === hit.id);
        if (isItem) pickItem(hit.id, e.shiftKey || e.ctrlKey || e.metaKey);
        else st.select(hit.id);
        drawOverlay(scene);
        // Shift+click only adds to (or takes from) the selection; it doesn't start a drag.
        if (isItem && (e.shiftKey || e.ctrlKey || e.metaKey)) return;
        const f = selectedFrame(scene);
        if (f) drag = { kind: "move", frame: f, startX: sx, startY: sy, startW: toWorld(scene, sx, sy), ghost: null, moved: false };
        return;
      }
      // Inside the frame of a group (or several selected things), between its pieces: grab them
      // all, as the frame shows them as one. (Shift+click there still adds or takes away.)
      const together = insideGroupFrame(scene, toWorld(scene, sx, sy));
      if (together && !(e.shiftKey || e.ctrlKey || e.metaKey)) {
        drag = { kind: "move", frame: together, startX: sx, startY: sy, startW: toWorld(scene, sx, sy), ghost: null, moved: false };
        return;
      }
      drag = { kind: "pan", x: e.clientX, y: e.clientY, moved: false, deselect: !(e.shiftKey || e.ctrlKey || e.metaKey) };
    };

    const onDouble = (e: MouseEvent) => {
      const scene = sceneRef.current;
      if (!scene) return;
      const st = useStore.getState();
      if (st.tool === "autotrace") return;
      if (st.tool !== "select") {
        void penFinish();
        return;
      }
      // Double-click a point to delete it (as in Embrilliance); on the outline, to add one there.
      const o = selectedObject();
      if (!o || o.locked) return;
      const [sx, sy] = local(e);
      if (letterAt(scene, sx, sy) || endAt(scene, sx, sy) || dirAt(scene, sx, sy)) return;
      const node = nodeAt(scene, sx, sy);
      if (node && node.o.id === o.id) {
        deleteNode(o.id, node.list, node.index);
        return;
      }
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
      // Only the pointer that started a drag moves it.
      if (drag && e.pointerId !== dragPointer) return;
      if (runCanvasTool("move", e, hookCtx(scene))) return;
      const [sx, sy] = local(e);
      pointerAt = { sx, sy, ctrlKey: e.ctrlKey, metaKey: e.metaKey, shiftKey: e.shiftKey };
      refreshCursor();
      const st = useStore.getState();
      // Drawing near the edge of the design area: the view scrolls that way (Embrilliance's auto-pan).
      if (st.pen && !drag) autoPan(sx, sy);
      else stopAutoPan();
      if (st.knife && !drag) {
        cursorMm = snapped(scene, toWorld(scene, sx, sy), e);
        drawOverlay(scene);
        return;
      }
      if (drag?.kind === "guide" && liveGuide) {
        drag.moved = true;
        const p = toWorld(scene, sx, sy);
        const v = liveGuide.axis === "x" ? p[0] : p[1];
        // Guides land on the grid's small squares when the grid is on.
        const step = st.showGrid ? gridSpacing(scene.view.scale, st.units).minorMm : 0;
        liveGuide = { ...liveGuide, at: step ? Math.round(v / step) * step : Math.round(v * 10) / 10 };
        drawOverlay(scene);
        return;
      }
      if (drag?.kind === "stitches" && liveStitches) {
        if (!drag.moved && Math.hypot(sx - drag.startX, sy - drag.startY) < DRAG_THRESHOLD_PX) return;
        drag.moved = true;
        liveStitches = { ...liveStitches, to: toWorld(scene, sx, sy) };
        drawOverlay(scene);
        return;
      }
      if ((st.tool !== "select" || st.measure || st.ruler || st.angleFor || st.crosshair) && !drag) {
        cursorMm = snapped(scene, toWorld(scene, sx, sy), e);
        cursorKind = pointKind(e);
        if (st.pen || st.measure || st.ruler || st.angleFor || st.crosshair) drawOverlay(scene);
        return;
      }
      if (!drag) return; // (the pointer was decided above)
      if (drag.kind === "pan") {
        const dx = e.clientX - drag.x;
        const dy = e.clientY - drag.y;
        if (dx || dy) {
          drag.moved = true;
          if (useStore.getState().spaceDown) markSpacePanned();
        }
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
      if (drag.kind === "letter") {
        const d = drag;
        const part = selectedLetters(scene)?.parts.find((x) => x.index === d.index);
        if (!part) return;
        d.at = nearestOnLine(part.ring, toWorld(scene, sx, sy), true);
        liveLetter = { id: d.id, index: d.index, which: d.which, at: d.at };
        drawOverlay(scene);
        return;
      }
      if (drag.kind === "ends" || drag.kind === "dir") {
        const o = selectedObject();
        if (!o || o.id !== drag.id) return;
        const p = toWorld(scene, sx, sy);
        if (drag.kind === "ends") {
          drag.at = snapEnd(o, drag.which, p);
          liveEnd = { id: drag.id, which: drag.which, at: drag.at };
        } else {
          drag.at = snapDirection(o, p);
          liveDir = { id: drag.id, which: drag.which, at: drag.at };
        }
        drawOverlay(scene);
        return;
      }
      if (drag.kind === "guide" || drag.kind === "stitches") return;
      if (drag.frame.locked) return;
      placeGhost(scene, drag, sx, sy, e.shiftKey);
    };

    /** Show a move, resize or turn in progress: the ghost (or the picture itself) follows the pointer.
     *  If a render replaced the scene mid-drag, the ghost is made again on the new one. */
    const placeGhost = (scene: Scene, d: Extract<Drag, { frame: Frame }>, sx: number, sy: number, shift: boolean) => {
      const f = d.frame;
      if (d.ghost && (d.ghost.destroyed || d.ghost.parent !== scene.world)) d.ghost = null;
      d.ghost ??= startGhost(scene, f);
      // Worked out in mm, from where it was grabbed: zooming or panning mid-drag keeps it under the pointer.
      const [wx, wy] = toWorld(scene, sx, sy);
      const [gx, gy] = d.startW;
      const [ccx, ccy] = f.center;
      const target = f.kind === "image" ? scene.pictures.children.find((c) => c.label === f.id) : d.ghost;
      if (!target) return;
      if (d.kind === "move") {
        target.position.set(f.center[0] + wx - gx, f.center[1] + wy - gy);
      } else if (d.kind === "scale" && d.side) {
        // A side handle: stretch across that side only; the opposite side stays where it is.
        const anchor = stretchAnchor(f, d.side);
        const k = stretchFactor(anchor, [gx, gy], [wx, wy], sideAxis(f.corners, d.side));
        const across = d.side === "e" || d.side === "w";
        target.position.set(anchor[0] + (ccx - anchor[0]) * k, anchor[1] + (ccy - anchor[1]) * k);
        if (f.kind === "image") {
          const im = currentDoc()!.images[f.index];
          target.width = im.width_mm * (across ? k : 1);
          target.height = im.height_mm * (across ? 1 : k);
        } else target.scale.set(across ? k : 1, across ? 1 : k);
      } else if (d.kind === "scale") {
        const k = Math.hypot(wx - ccx, wy - ccy) / Math.max(1 / scene.view.scale, Math.hypot(gx - ccx, gy - ccy));
        if (f.kind === "image") {
          const im = currentDoc()!.images[f.index];
          target.width = im.width_mm * Math.max(0.05, k);
          target.height = im.height_mm * Math.max(0.05, k);
        } else target.scale.set(Math.max(0.05, k));
      } else {
        let a = Math.atan2(wy - ccy, wx - ccx) - Math.atan2(gy - ccy, gx - ccx);
        if (shift) a = (Math.round((a * 180) / Math.PI / 15) * 15 * Math.PI) / 180;
        target.rotation = (f.kind === "image" ? (currentDoc()!.images[f.index].rotate * Math.PI) / 180 : 0) + a;
      }
    };

    const onUp = (e: PointerEvent) => {
      const scene = sceneRef.current;
      // Another pointer coming up doesn't end (or drop) this drag.
      if (drag && e.pointerId !== dragPointer) return;
      if (scene && runCanvasTool("up", e, hookCtx(scene))) return;
      if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      el.classList.remove("panning");
      releaseEsc?.();
      releaseEsc = null;
      const d = drag;
      drag = null;
      refreshCursor();
      if (!scene || !d) return;
      if (d.kind === "pan") {
        if (!d.moved && d.deselect) {
          useStore.getState().select(null);
          drawOverlay(scene);
        } else if (d.moved) afterPan(scene);
        return;
      }
      if (d.kind === "guide") {
        const g = liveGuide;
        liveGuide = null;
        if (!g) return;
        const [ux, uy] = local(e);
        const guides = [...(currentLayout()?.guides ?? [])];
        const onRuler = ux < RULER_PX || uy < RULER_PX || ux > scene.app.screen.width || uy > scene.app.screen.height;
        if (g.index === null) {
          if (!onRuler) void setGuides([...guides, { axis: g.axis, at: Math.round(g.at * 100) / 100 }]);
        } else if (onRuler) void setGuides(guides.filter((_, i) => i !== g.index));
        else if (d.moved) void setGuides(guides.map((gd, i) => (i === g.index ? { axis: g.axis, at: Math.round(g.at * 100) / 100 } : gd)));
        drawOverlay(scene);
        return;
      }
      if (d.kind === "stitches") {
        const ls = liveStitches;
        liveStitches = null;
        const st = useStore.getState();
        if (ls && st.stitchEdit && d.moved) {
          if (ls.mode === "move") moveSelectedStitches(ls.to[0] - ls.from[0], ls.to[1] - ls.from[1]);
          else {
            // Box select: every stitch of the file inside the box.
            const des = scene.design;
            const idx = st.history.present?.layout.items.findIndex((it) => it.id === st.stitchEdit!.id) ?? -1;
            const [x0, x1] = [Math.min(ls.from[0], ls.to[0]), Math.max(ls.from[0], ls.to[0])];
            const [y0, y1] = [Math.min(ls.from[1], ls.to[1]), Math.max(ls.from[1], ls.to[1])];
            const inBox = des ? stitchesInBox(des.records, idx, x0, y0, x1, y1) : [];
            const keep = d.shift && (useStore.getState().stitchEdit?.selected ?? []).length > 0 && liveShift;
            const selected = keep ? [...new Set([...st.stitchEdit.selected, ...inBox])] : inBox;
            st.setStitchEdit({ ...st.stitchEdit, selected });
          }
        } else if (ls?.mode === "box" && st.stitchEdit && !d.shift) st.setStitchEdit({ ...st.stitchEdit, selected: [] });
        liveShift = false;
        drawOverlay(scene);
        return;
      }
      if (d.kind === "node") {
        scene.stitches.alpha = restingAlpha();
        if (d.moved) moveNode(d.id, d.list, d.index, d.at[0], d.at[1]);
        else drawOverlay(scene);
        return;
      }
      if (d.kind === "ends") {
        // The dot stays where it was let go until the new stitches arrive (then it's on them).
        if (d.moved) void moveStitchEnd(d.id, d.which, d.at).finally(() => {
          liveEnd = null;
          if (sceneRef.current) drawOverlay(sceneRef.current);
        });
        else liveEnd = null;
        drawOverlay(scene);
        return;
      }
      if (d.kind === "letter") {
        if (d.moved)
          void setLetterEnd(d.id, d.index, d.which, d.at).finally(() => {
            liveLetter = null;
            if (sceneRef.current) drawOverlay(sceneRef.current);
          });
        else liveLetter = null;
        drawOverlay(scene);
        return;
      }
      if (d.kind === "dir") {
        const o = selectedObject();
        const dots = o && o.id === d.id ? directionDots(o) : null;
        if (d.moved && o && dots) {
          const line: [Pt, Pt] = d.which === 0 ? [d.at, dots[1]] : [dots[0], d.at];
          void (o.kind === "fill" ? setFillDirection(d.id, line) : setSatinTips(d.id, line)).finally(() => {
            liveDir = null;
            if (sceneRef.current) drawOverlay(sceneRef.current);
          });
        } else liveDir = null;
        drawOverlay(scene);
        return;
      }
      const f = d.frame;
      // A render may have replaced the scene since the last pointer move: place the ghost again.
      if (d.moved && !f.locked && (!d.ghost || d.ghost.destroyed || d.ghost.parent !== scene.world)) {
        const [ux, uy] = local(e);
        placeGhost(scene, d, ux, uy, e.shiftKey);
      }
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
      if (d.kind === "scale" && d.side) {
        // Stretched from a side: about the opposite side, which stays put (several things together).
        const kx = Math.round(ghost.scale.x * 1000) / 1000;
        const ky = Math.round(ghost.scale.y * 1000) / 1000;
        const anchor = shapeStretchAnchor(f.ids, d.side) ?? stretchAnchor(f, d.side);
        if (kx !== 1 || ky !== 1) next = transformTogether(layout, f.ids, selectionGeometry(f.ids).centers, anchor, { stretch: [kx, ky] });
      } else if (f.ids.length > 1) {
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
      stopAutoPan();
      cursorMm = null;
      pointerAt = null;
      const scene = sceneRef.current;
      if (scene && useStore.getState().pen) drawOverlay(scene);
    };
    /** Right-click: a menu of what can be done with the thing under the mouse (selecting it
     *  first), or with the canvas. While drawing or tracing, a right-click keeps its own meaning
     *  (finish the shape, use the guess), and on a point it switches the point's kind. */
    const onMenu = (e: MouseEvent) => {
      e.preventDefault();
      const scene = sceneRef.current;
      const st = useStore.getState();
      if (!scene || !st.history.present) return;
      if (st.pen || st.knife || st.ruler || st.measure || st.angleFor || st.autoTrace || st.autoAll || drag) return;
      if (st.tool !== "select" && st.tool !== "text") return;
      const [sx, sy] = local(e);
      if (st.stitchEdit) {
        // Right-clicking selects the stitch under the pointer first, as it does everywhere else.
        const hit = stitchAt(scene, sx, sy);
        if (hit !== null && !st.stitchEdit.selected.includes(hit)) st.setStitchEdit({ ...st.stitchEdit, selected: [hit] });
        const edits = [{ id: "stitch.insert" }, { id: "stitch.insertJump" }, { id: "stitch.lockJump" }, "separator" as const, { id: "stitch.deleteSelected" }];
        return openContextMenu(e, [...edits, "separator", { label: "Done editing stitches", run: endStitchEdit }], "Stitches");
      }
      if (runCanvasMenu(e, hookCtx(scene))) return;
      if (nodeAt(scene, sx, sy)) return;
      const p = toWorld(scene, sx, sy);
      const hit = pick(scene, p) ?? pinnedPictureAt(p);
      const doc = currentDoc()!;
      const item = hit ? doc.layout.items.find((it) => it.id === hit.id) : undefined;
      if (item) {
        if (st.selectedId !== item.id && !st.extraIds.includes(item.id)) pickItem(item.id, false);
        const now = useStore.getState();
        const several = !!now.selectedId && now.extraIds.length > 0;
        drawOverlay(scene);
        return openContextMenu(e, itemMenu(item, several), several ? `${now.extraIds.length + 1} things` : itemLabel(item, doc.layout.items.indexOf(item)));
      }
      const img = hit ? doc.images.find((im) => im.id === hit.id) : undefined;
      if (img) {
        st.select(img.id);
        drawOverlay(scene);
        return openContextMenu(e, [...pictureMenu(), "separator", { label: "Hide this picture", run: () => setPicture(img.id, { visible: false }) }], img.name || "Picture");
      }
      openContextMenu(e, canvasMenu());
    };
    /** A pinned picture lets clicks through, but a right-click still finds it (to unpin it). */
    const pinnedPictureAt = (p: Pt): { id: string } | null => {
      const doc = currentDoc();
      if (!doc || !useStore.getState().showPictures) return null;
      for (let i = doc.images.length - 1; i >= 0; i--) {
        const im = doc.images[i];
        if (!im.visible) continue;
        const l = rotatePt(p, [im.x, im.y], (-im.rotate * Math.PI) / 180);
        if (Math.abs(l[0] - im.x) <= im.width_mm / 2 && Math.abs(l[1] - im.y) <= im.height_mm / 2) return { id: im.id };
      }
      return null;
    };
    // A cancelled gesture (the system took the touch) puts things back rather than dropping them there.
    const onCancel = (e: PointerEvent) => {
      if (drag && e.pointerId === dragPointer) cancelDrag();
    };
    // Switching to another window: the drag goes back and the view stops scrolling by itself.
    const onBlur = () => {
      cancelDrag();
      stopAutoPan();
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
    window.addEventListener("blur", onBlur);
    el.addEventListener("pointerleave", onLeave);
    el.addEventListener("dblclick", onDouble);
    el.addEventListener("contextmenu", onMenu);
    window.addEventListener("keydown", onKeyForCursor);
    window.addEventListener("keyup", onKeyForCursor);
    return () => {
      unsubscribeCursor();
      window.removeEventListener("keydown", onKeyForCursor);
      window.removeEventListener("keyup", onKeyForCursor);
      releaseEsc?.();
      stopAutoPan();
      if (wheelFrame) cancelAnimationFrame(wheelFrame);
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
      window.removeEventListener("blur", onBlur);
      el.removeEventListener("pointerleave", onLeave);
      el.removeEventListener("dblclick", onDouble);
      el.removeEventListener("contextmenu", onMenu);
    };
  }, []);

  return <div ref={host} className="stitch-canvas" aria-label="Design canvas" />;
}

const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
