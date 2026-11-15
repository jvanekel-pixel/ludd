/**
 * Realistic thread: every stitch is drawn as its own piece of shiny, twisted thread between two
 * needle holes, lit from one direction (the upper left) the way a photo of a stitch-out is.
 *
 * Each stitch is three sprites, from small textures made once:
 * - a soft shadow cast down and to the right, onto the fabric and onto anything sewn earlier
 *   (each colour's shadows sit just under its own thread, so later shapes look raised);
 * - the thread body: a rounded cross-section shaded by the light (the side facing the light is
 *   brighter, the far side and the edges darker), with twisted plies and ends that dip into the
 *   needle hole;
 * - a glossy highlight: a sharp line, shifted toward the light and broken up by the twist, as on
 *   rayon or polyester thread.
 * The textures come in versions for how much the light falls across the stitch (it depends on the
 * stitch's angle) and for its length (so plies keep about the same size on short and long stitches).
 * A stitch whose top side faces away from the light is drawn flipped, so the lit side is always the
 * side toward the light. Stitches sewn at different angles therefore catch the light differently,
 * which is what makes satins look rounded and fills show their direction.
 *
 * The textures are mipmapped: when zoomed out, a thread only a pixel or two wide is drawn from a
 * smoothed copy (no sparkle or moiré), and up close the plies and highlight show.
 * Thread is 0.4 mm (40 wt) and spreads a little as it's sewn, so it's drawn about 0.48 mm wide, at
 * true scale: sparse rows show fabric between them and dense areas pile up.
 * Sprites batch on the GPU (all textures fit one batch), so tens of thousands of stitches stay smooth.
 */
import { CanvasSource, Container, Sprite, Texture } from "pixi.js";
import { Kind, type Design } from "../design/types";
import { lightOn, pliesFor, shadeAt, THREAD_WIDTH_MM, tintFor } from "../design/threadLook";

const TEX_LEN = 128; // texture pixels along the thread
const TEX_W = 32; // texture pixels across the thread (the body fills the middle part)
const BODY_FRACTION = 20 / TEX_W; // the part of the texture height that is thread
/** How many plies (twists) a texture shows, for short, medium and long stitches. */
const PLIES = [3, 6, 12];
/** How far across the stitch the light falls, for each texture version (0: along it, 1: square across). */
const ACROSS = [0, 0.5, 1];

type Textures = { body: Texture[][]; sheen: Texture[][]; shadow: Texture };
let textures: Textures | null = null;

function canvas(w: number, h: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  return [c, c.getContext("2d")!];
}

/** A texture that's smoothed when drawn small (mipmaps) and sharp up close. */
function smooth(c: HTMLCanvasElement): Texture {
  return new Texture({ source: new CanvasSource({ resource: c, autoGenerateMipmaps: true, scaleMode: "linear", maxAnisotropy: 8 }) });
}

/** Grey-scale thread body (tinted to the thread colour per stitch). */
function bodyTexture(across: number, plies: number): HTMLCanvasElement {
  const [c, g] = canvas(TEX_LEN, TEX_W);
  const img = g.createImageData(TEX_LEN, TEX_W);
  const half = (TEX_W * BODY_FRACTION) / 2;
  const mid = TEX_W / 2;
  for (let y = 0; y < TEX_W; y++) {
    const v = (y + 0.5 - mid) / half; // -1 (top edge) .. 1 (bottom edge)
    for (let x = 0; x < TEX_LEN; x++) {
      const u = (x + 0.5) / TEX_LEN; // 0..1 along the thread
      // Rounded ends: the thread narrows where it goes into the needle hole.
      const endR = Math.min(1, Math.min(u, 1 - u) / 0.06);
      const r = Math.abs(v) / Math.max(0.3, Math.sqrt(endR));
      const i = (y * TEX_LEN + x) * 4;
      if (r >= 1) {
        img.data[i + 3] = 0;
        continue;
      }
      const [diffuse] = shadeAt(v / Math.max(0.3, Math.sqrt(endR)), across);
      let light = 0.6 + 0.46 * diffuse;
      // Twisted plies: diagonal grooves round the thread (darker in the grooves).
      const phase = (u * plies + (v + 1) * 0.42) * Math.PI * 2;
      light *= 0.9 + 0.1 * (0.5 + 0.5 * Math.cos(phase)) ** 0.6;
      // Ends dip into the fabric: darker.
      light *= 0.62 + 0.38 * Math.min(1, Math.min(u, 1 - u) / 0.13);
      const grey = Math.round(255 * Math.min(1, light));
      img.data[i] = img.data[i + 1] = img.data[i + 2] = grey;
      // Soft edge (anti-aliasing at any zoom).
      img.data[i + 3] = Math.round(255 * Math.min(1, (1 - r) / 0.16));
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

/** The glossy highlight, broken up by the plies (white; its strength is set per stitch). */
function sheenTexture(across: number, plies: number): HTMLCanvasElement {
  const [c, g] = canvas(TEX_LEN, TEX_W);
  const img = g.createImageData(TEX_LEN, TEX_W);
  const half = (TEX_W * BODY_FRACTION) / 2;
  const mid = TEX_W / 2;
  for (let y = 0; y < TEX_W; y++) {
    const v = (y + 0.5 - mid) / half;
    for (let x = 0; x < TEX_LEN; x++) {
      const u = (x + 0.5) / TEX_LEN;
      const i = (y * TEX_LEN + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = 255;
      if (Math.abs(v) >= 0.96) continue;
      const [, spec] = shadeAt(v, across);
      const phase = (u * plies + (v + 1) * 0.42) * Math.PI * 2;
      const twist = (0.5 + 0.5 * Math.cos(phase)) ** 1.5;
      const ends = Math.min(1, Math.min(u, 1 - u) / 0.16);
      img.data[i + 3] = Math.round(255 * Math.min(1, spec * (0.35 + 0.65 * twist) * ends));
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
      const e = Math.min(1, Math.min(u, 1 - u) / 0.14);
      const i = (y * TEX_LEN + x) * 4;
      img.data[i + 3] = Math.round(255 * Math.max(0, 1 - v) ** 1.4 * e);
    }
  }
  g.putImageData(img, 0, 0);
  return c;
}

function getTextures(): Textures {
  textures ??= {
    body: ACROSS.map((a) => PLIES.map((p) => smooth(bodyTexture(a, p)))),
    sheen: ACROSS.map((a) => PLIES.map((p) => smooth(sheenTexture(a, p)))),
    shadow: smooth(shadowTexture()),
  };
  return textures;
}

function rgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", "").padEnd(6, "0").slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
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
  // Bodies and highlights alternate in sewing order, so a later stitch covers an earlier one.
  const threads = new Container();
  const root = new Container();
  root.addChild(shadows, threads);
  const base = rgb(color);
  // Dark threads get a little more highlight (it's what shows their shape); white would wash out.
  const lum = (0.3 * base[0] + 0.59 * base[1] + 0.11 * base[2]) / 255;
  const sheenAlpha = 0.42 + 0.3 * (1 - lum);
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
    const { across, flip } = lightOn(angle);
    const ai = Math.round(across * (ACROSS.length - 1));
    const pi = pliesFor(len);
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
      if (flip) s.scale.y = -s.scale.y; // the lit side toward the light
      s.tint = tint;
      s.alpha = alpha;
      return s;
    };
    // The shadow falls away from the light (down and to the right), wider and softer than the thread.
    const shadow = make(t.shadow, w * 1.75, 0x000000, 0.26, 0.11, 0.15);
    const body = make(t.body[ai][pi], w, tintFor(base, angle), 1);
    const sheen = make(t.sheen[ai][pi], w, 0xffffff, sheenAlpha * (0.45 + 0.55 * across));
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
