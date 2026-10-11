/** Canvas view: screen px = world mm * scale + offset. */
export type View = { scale: number; x: number; y: number };

export const MIN_SCALE = 0.1; // px per mm (about 3%)
export const MAX_SCALE = 400;

/** Centre `bounds` (mm) in a viewport (px) with a margin, at most `maxScale`. */
export function fitView(
  bounds: readonly [number, number, number, number],
  width: number,
  height: number,
  margin = 32,
  maxScale = 40,
): View {
  const [x0, y0, x1, y1] = bounds;
  const w = Math.max(x1 - x0, 1);
  const h = Math.max(y1 - y0, 1);
  const availW = Math.max(width - 2 * margin, 1);
  const availH = Math.max(height - 2 * margin, 1);
  const scale = clamp(Math.min(availW / w, availH / h), MIN_SCALE, maxScale);
  return {
    scale,
    x: width / 2 - ((x0 + x1) / 2) * scale,
    y: height / 2 - ((y0 + y1) / 2) * scale,
  };
}

/** Zoom by `factor`, keeping the world point under screen point (px, py) fixed. */
export function zoomAt(view: View, factor: number, px: number, py: number): View {
  const scale = clamp(view.scale * factor, MIN_SCALE, MAX_SCALE);
  const k = scale / view.scale;
  return { scale, x: px - (px - view.x) * k, y: py - (py - view.y) * k };
}

export function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}
