/**
 * Realistic thread: every stitch is drawn as its own piece of thread between two needle holes.
 *
 * Each stitch is three sprites, all from small textures made once (the body and its sheen are
 * interleaved in sewing order, so a later stitch always covers an earlier one, underlay included):
 * - a soft shadow on the fabric, a little down and to the right of the thread;
 * - the thread body: round in cross-section (darker at the edges, lighter on top), with a fine
 *   twist pattern, and ends that darken as the thread dips into the needle hole;
 * - a sheen line, whose strength depends on the stitch's angle to the light (upper left), so
 *   fills sewn at different angles catch the light differently, as real thread does.
 * Thread is 0.4 mm (40 wt) and spreads a little as it's sewn, so it's drawn about 0.48 mm wide,
 * at true scale: sparse rows show fabric between them and
 * dense areas show threads piling up: you can see density without the density map.
 * Sprites with the same texture batch on the GPU, so tens of thousands of stitches stay smooth.
 */
import { Container, Sprite, Texture } from "pixi.js";
import { Kind, type Design } from "../design/types";
import { THREAD_WIDTH_MM } from "../design/threadLook";

const TEX_LEN = 128; // texture pixels along the thread
const TEX_W = 24; // texture pixels across the thread (the body fills the middle 2/3)
const BODY_FRACTION = 16 / TEX_W; // the part of the texture height that is thread
const LIGHT = (-135 * Math.PI) / 180; // light from the upper left (y grows downward)

type Textures = { body: Texture; shadow: Texture; sheen: Texture };
let textures: Textures | null = null;

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return [c, c.getContext("2d")!];
}

/** Grey-scale thread body (tinted to the thread colour per stitch). */
function bodyTexture(): HTMLCanvasElement {
  const [c, g] = canvas(TEX_LEN, TEX_W);
  const img = g.createImageData(TEX_LEN, TEX_W);
  const half = (TEX_W * BODY_FRACTION) / 2;
  const mid = TEX_W / 2;
  for (let y = 0; y < TEX_W; y++) {
    // Position across the thread, -1 (top edge) .. 1 (bottom edge).
    const v = (y + 0.5 - mid) / half;
    for (let x = 0; x < TEX_LEN; x++) {
      const u = (x + 0.5) / TEX_LEN; // 0..1 along the thread
      // Rounded ends: the thread is narrower near the needle holes.
      const endR = Math.min(1, Math.min(u, 1 - u) / 0.07);
      const r = Math.abs(v) / Math.max(0.35, Math.sqrt(endR));
      const i = (y * TEX_LEN + x) * 4;
      if (r >= 1) {
        img.data[i + 3] = 0;
        continue;
      }
      // Sewn thread is a flattened round: lit from above, gently darker toward the edges.
      const nz = Math.sqrt(1 - r * r);
      let light = 0.66 + 0.34 * Math.max(0, nz * 0.9 - v * 0.25);
      // Twist: fine diagonal plies, just visible up close.
      const ply = 0.955 + 0.045 * Math.cos((x * 2 + y * 3.2) * 0.55);
      light *= ply;
      // Ends dip into the fabric: slightly darker.
      light *= 0.86 + 0.14 * Math.min(1, Math.min(u, 1 - u) / 0.1);
      const vgrey = Math.round(255 * Math.min(1, light));
      img.data[i] = img.data[i + 1] = img.data[i + 2] = vgrey;
      // Soft edge (anti-aliasing at any zoom).
      img.data[i + 3] = Math.round(255 * Math.min(1, (1 - r) / 0.18));
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

/** A soft dark blur under the thread. */
function shadowTexture(): HTMLCanvasElement {
  const [c, g] = canvas(TEX_LEN, TEX_W);
  const img = g.createImageData(TEX_LEN, TEX_W);
  const mid = TEX_W / 2;
  for (let y = 0; y < TEX_W; y++) {
    const v = Math.abs((y + 0.5 - mid) / mid);
    for (let x = 0; x < TEX_LEN; x++) {
      const u = (x + 0.5) / TEX_LEN;
      const e = Math.min(1, Math.min(u, 1 - u) / 0.12);
      const i = (y * TEX_LEN + x) * 4;
      img.data[i + 3] = Math.round(255 * Math.max(0, 1 - v) ** 1.6 * e);
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

/** A thin bright line along the top of the thread. */
function sheenTexture(): HTMLCanvasElement {
  const [c, g] = canvas(TEX_LEN, TEX_W);
  const img = g.createImageData(TEX_LEN, TEX_W);
  const top = TEX_W / 2 - (TEX_W * BODY_FRACTION) / 6;
  for (let y = 0; y < TEX_W; y++) {
    const v = (y + 0.5 - top) / 1.6;
    for (let x = 0; x < TEX_LEN; x++) {
      const u = (x + 0.5) / TEX_LEN;
      const e = Math.min(1, Math.min(u, 1 - u) / 0.2);
      const i = (y * TEX_LEN + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = 255;
      img.data[i + 3] = Math.round(255 * Math.exp(-v * v) * e);
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

function getTextures(): Textures {
  textures ??= {
    body: Texture.from(bodyTexture()),
    shadow: Texture.from(shadowTexture()),
    sheen: Texture.from(sheenTexture()),
  };
  return textures;
}

function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", "").padEnd(6, "0").slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** How much a stitch at this angle catches the light (thread is brightest across the light). */
export function sheenFor(angle: number): number {
  return Math.abs(Math.sin(angle - LIGHT));
}

/** The thread colour for a stitch at this angle: brighter across the light, a little darker along it. */
export function tintFor([r, g, b]: [number, number, number], angle: number): number {
  const k = 0.84 + 0.22 * sheenFor(angle);
  const c = (v: number) => Math.min(255, Math.round(v * k));
  return (c(r) << 16) | (c(g) << 8) | c(b);
}

export type ThreadChunk = {
  root: Container;
  /** Record index of each stitch's end point, in order, and its three sprites. */
  records: number[];
  sprites: Sprite[][];
  /** The playhead last shown (to skip chunks that didn't change). */
  shown: number;
};

/** Sprites for the stitches of records [start, end) in one colour. */
export function buildThreadChunk(d: Design, start: number, end: number, color: string, only?: number): ThreadChunk {
  const t = getTextures();
  const { x, y, kind, item } = d.records;
  const shadows = new Container();
  // Bodies and sheens alternate in sewing order (same blend mode, so they still batch).
  const threads = new Container();
  const root = new Container();
  root.addChild(shadows, threads);
  const base = rgb(color);
  // Dark threads get a softer sheen; light ones a stronger one would wash out to white.
  const lum = (0.3 * base[0] + 0.59 * base[1] + 0.11 * base[2]) / 255;
  const sheenAlpha = 0.18 + 0.2 * (1 - lum);
  const records: number[] = [];
  const sprites: Sprite[][] = [];
  const w = (THREAD_WIDTH_MM * 1.2) / BODY_FRACTION;
  const keep = (i: number) => only === undefined || item?.[i] === only;
  for (let i = Math.max(1, start); i < end; i++) {
    if (kind[i] !== Kind.Stitch || kind[i - 1] !== Kind.Stitch || !keep(i) || !keep(i - 1)) continue;
    const x0 = x[i - 1];
    const y0 = y[i - 1];
    const dx = x[i] - x0;
    const dy = y[i] - y0;
    const len = Math.hypot(dx, dy);
    if (len < 0.05) continue;
    const angle = Math.atan2(dy, dx);
    // Thread reaches a little past each needle hole, as it wraps into it.
    const reach = Math.min(0.12, len * 0.2);
    const L = len + 2 * reach;
    const make = (tex: Texture, width: number, tint: number, alpha: number, ox = 0, oy = 0) => {
      const s = new Sprite(tex);
      s.anchor.set(0, 0.5);
      s.position.set(x0 - Math.cos(angle) * reach + ox, y0 - Math.sin(angle) * reach + oy);
      s.rotation = angle;
      s.width = L;
      s.height = width;
      s.tint = tint;
      s.alpha = alpha;
      return s;
    };
    const shadow = make(t.shadow, w * 1.1, 0x000000, 0.22, 0.05, 0.07);
    const body = make(t.body, w, tintFor(base, angle), 1);
    const sheen = make(t.sheen, w, 0xffffff, sheenAlpha * sheenFor(angle));
    shadows.addChild(shadow);
    threads.addChild(body, sheen);
    records.push(i);
    sprites.push([shadow, body, sheen]);
  }
  return { root, records, sprites, shown: Infinity };
}

/** Show the stitches whose end record is before `upTo` (for the stitch player). */
export function showUpTo(chunk: ThreadChunk, upTo: number) {
  const n = chunk.records.length;
  if (!n) return;
  const first = chunk.records[0];
  const last = chunk.records[n - 1];
  // Nothing changes if the playhead stayed past the end (or before the start) of this chunk.
  if ((chunk.shown > last && upTo > last) || (chunk.shown <= first && upTo <= first)) {
    chunk.shown = upTo;
    return;
  }
  chunk.shown = upTo;
  for (let k = 0; k < n; k++) {
    const v = chunk.records[k] < upTo;
    const ss = chunk.sprites[k];
    if (ss[1].visible !== v) for (const s of ss) s.visible = v;
  }
}
