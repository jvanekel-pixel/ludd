/** How stitches are drawn: flat lines, or "realistic" shaded thread (edge, body, sheen). */

export type StrokeLayer = { width: number; color: string; alpha: number };

/** 40 wt embroidery thread lies about 0.4 mm wide. */
export const THREAD_WIDTH_MM = 0.4;

function parseHex(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h.padEnd(6, "0").slice(0, 6), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex([r, g, b]: [number, number, number]): string {
  return "#" + [r, g, b].map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, "0")).join("");
}

/** Mix toward black (amount < 0) or white (amount > 0), amount in [-1, 1]. */
export function shade(hex: string, amount: number): string {
  const [r, g, b] = parseHex(hex);
  const t = amount < 0 ? 0 : 255;
  const a = Math.abs(amount);
  return toHex([r + (t - r) * a, g + (t - g) * a, b + (t - b) * a]);
}

/** Stroke layers for one thread color, drawn in order. */
export function threadLayers(color: string, realistic: boolean): StrokeLayer[] {
  if (!realistic) return [{ width: THREAD_WIDTH_MM * 0.85, color, alpha: 1 }];
  return [
    { width: THREAD_WIDTH_MM, color: shade(color, -0.45), alpha: 0.9 }, // edge / shadow between stitches
    { width: THREAD_WIDTH_MM * 0.72, color, alpha: 1 }, // thread body
    { width: THREAD_WIDTH_MM * 0.22, color: shade(color, 0.45), alpha: 0.65 }, // sheen along the twist
  ];
}

// ---------------------------------------------------------------- realistic thread: light

/** Direction toward the light, on the design (y grows downward): the upper left. */
export const LIGHT: [number, number] = [-Math.SQRT1_2, -Math.SQRT1_2];
/**
 * Light on the thread's surface at a point: `v` across the thread (-1: the top edge, which faces
 * the light; 1: the bottom edge), `across` how much the light falls across the stitch (0..1).
 * Returns [diffuse 0..1, specular 0..1]. Pure, for tests.
 */
export function shadeAt(v: number, across: number): [number, number] {
  const r = Math.min(1, Math.abs(v));
  const nz = Math.sqrt(1 - r * r);
  const nx = -v; // the surface's tilt toward the top edge
  // Light from above and, when it falls across the stitch, from the top-edge side.
  const lx = across * 0.78;
  const lz = 0.62;
  const ll = Math.hypot(lx, lz);
  const diffuse = Math.max(0, (nx * lx + nz * lz) / ll);
  // Highlight (Blinn): halfway between the light and the eye (straight down at the design).
  const hx = lx / ll;
  const hz = lz / ll + 1;
  const hl = Math.hypot(hx, hz);
  const spec = Math.max(0, (nx * hx + nz * hz) / hl) ** 36;
  return [diffuse, spec];
}

/**
 * How the light falls on a stitch at this angle: how much across it (0..1), and whether the
 * texture's top edge faces away from the light (then the stitch is drawn flipped). Pure, for tests.
 */
export function lightOn(angle: number): { across: number; flip: boolean } {
  // The texture's top edge points this way on the design.
  const up = [Math.sin(angle), -Math.cos(angle)];
  const d = up[0] * LIGHT[0] + up[1] * LIGHT[1];
  return { across: Math.abs(d), flip: d < 0 };
}

/** How much a stitch at this angle catches the light (thread is brightest with the light across it). */
export function sheenFor(angle: number): number {
  return lightOn(angle).across;
}

/** The thread colour for a stitch at this angle: brighter across the light, a little darker along
 *  it. The shading in the texture darkens the edges, so the middle of the thread is lifted a bit
 *  above the thread colour to keep the colour true on average. */
export function tintFor([r, g, b]: [number, number, number], angle: number): number {
  const k = 1.06 + 0.14 * sheenFor(angle);
  const c = (v: number) => Math.min(255, Math.round(v * k));
  return (c(r) << 16) | (c(g) << 8) | c(b);
}

/** Which ply texture suits a stitch this long (mm): plies about 0.5 mm apart. */
export function pliesFor(lengthMm: number): number {
  return lengthMm < 1.6 ? 0 : lengthMm < 4 ? 1 : 2;
}
