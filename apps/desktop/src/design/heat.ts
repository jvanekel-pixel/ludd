/** Color for one cell of the density map: clear where the thread is fine, then yellow-green,
 *  orange at the warning level, red beyond it. */
export function heatColor(v: number, limit: number): [number, number, number, number] {
  if (v < limit * 0.6) return [0, 0, 0, 0];
  const t = Math.min(1, v / limit);
  if (v <= limit) {
    // 0.6..1 of the limit (a second layer): yellow-green to orange
    const k = (t - 0.6) / 0.4;
    return [Math.round(200 + 55 * k), Math.round(255 - 115 * k), Math.round(46 - 46 * k), Math.round(90 + 70 * k)];
  }
  const k = Math.min(1, (v - limit) / limit);
  return [255, Math.round(140 - 120 * k), 0, Math.round(170 + 60 * k)];
}
