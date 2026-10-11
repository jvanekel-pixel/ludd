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
