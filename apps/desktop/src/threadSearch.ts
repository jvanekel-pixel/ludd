/**
 * Searching a thread chart: by number, name or brand, or by a color code (#FF7A1A, FF7A1A, F70),
 * which lists the chart's threads closest to that color first. Pure, for tests.
 */
import type { ChartThread } from "./design/types";

/** A color code typed in the search box, as #rrggbb, or null if it isn't one. */
export function hexQuery(q: string): string | null {
  const m = q.trim().match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!m) return null;
  let h = m[1].toLowerCase();
  // Without a #, six letters only (a word like "facade" or "decade") are a name, not a color.
  if (!q.trim().startsWith("#") && /^[a-f]+$/i.test(h)) return null;
  // Three digits only with a # (so "123", a thread number, still searches numbers).
  if (h.length === 3) {
    if (!q.trim().startsWith("#")) return null;
    h = h.replace(/./g, (c) => c + c);
  }
  return `#${h}`;
}

/** A 6-digit code that is also all digits (e.g. "100200") could be a thread number: only a color if # or a letter is in it. */
const looksLikeNumber = (q: string) => /^\d+$/.test(q.trim());

function lab(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  const lin = (v: number) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = [lin((n >> 16) & 255), lin((n >> 8) & 255), lin(n & 255)];
  const f = (t: number) => (t > 216 / 24389 ? Math.cbrt(t) : (841 / 108) * t + 4 / 29);
  const x = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047);
  const y = f(0.2126 * r + 0.7152 * g + 0.0722 * b);
  const z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883);
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}

/** How different two colors look: CIEDE2000, as the engine's thread matching uses (under about 2
 *  they look the same). Ported from the engine's threads.ciede2000 (Sharma, Wu, Dalal 2005). */
export function colorDifference(x: string, y: string): number {
  const [L1, a1, b1] = lab(x);
  const [L2, a2, b2] = lab(y);
  const rad = (d: number) => (d * Math.PI) / 180;
  const deg = (r: number) => (r * 180) / Math.PI;
  const C1 = Math.hypot(a1, b1);
  const C2 = Math.hypot(a2, b2);
  const Cbar = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25 ** 7)));
  const a1p = (1 + G) * a1;
  const a2p = (1 + G) * a2;
  const C1p = Math.hypot(a1p, b1);
  const C2p = Math.hypot(a2p, b2);
  const h1p = C1p ? (deg(Math.atan2(b1, a1p)) + 360) % 360 : 0;
  const h2p = C2p ? (deg(Math.atan2(b2, a2p)) + 360) % 360 : 0;
  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp = 0;
  if (C1p * C2p !== 0) dhp = Math.abs(h2p - h1p) <= 180 ? h2p - h1p : h2p - h1p > 180 ? h2p - h1p - 360 : h2p - h1p + 360;
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(rad(dhp / 2));
  const Lbp = (L1 + L2) / 2;
  const Cbp = (C1p + C2p) / 2;
  let hbp = h1p + h2p;
  if (C1p * C2p !== 0) hbp = Math.abs(h1p - h2p) <= 180 ? (h1p + h2p) / 2 : h1p + h2p < 360 ? (h1p + h2p + 360) / 2 : (h1p + h2p - 360) / 2;
  const T = 1 - 0.17 * Math.cos(rad(hbp - 30)) + 0.24 * Math.cos(rad(2 * hbp)) + 0.32 * Math.cos(rad(3 * hbp + 6)) - 0.2 * Math.cos(rad(4 * hbp - 63));
  const dtheta = 30 * Math.exp(-(((hbp - 275) / 25) ** 2));
  const Rc = 2 * Math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7));
  const Sl = 1 + (0.015 * (Lbp - 50) ** 2) / Math.sqrt(20 + (Lbp - 50) ** 2);
  const Sc = 1 + 0.045 * Cbp;
  const Sh = 1 + 0.015 * Cbp * T;
  const Rt = -Math.sin(rad(2 * dtheta)) * Rc;
  return Math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh));
}

/** The threads that match a search, best first. A color code lists every thread, closest first. */
export function searchThreads(threads: ChartThread[], query: string): { threads: ChartThread[]; hex: string | null } {
  const q = query.trim().toLowerCase();
  if (!q) return { threads, hex: null };
  const hex = looksLikeNumber(q) && !q.startsWith("#") ? null : hexQuery(q);
  if (hex) {
    const byDiff = threads.map((t) => ({ t, d: colorDifference(hex, t.color) })).sort((x, y) => x.d - y.d);
    return { threads: byDiff.map((x) => x.t), hex };
  }
  // Numbers: an exact number first, then numbers starting with it, then anything containing it.
  const rank = (t: ChartThread) => {
    const code = t.code.toLowerCase();
    if (code === q) return 0;
    if (code.startsWith(q)) return 1;
    if (t.name.toLowerCase().startsWith(q)) return 2;
    return 3;
  };
  const hits = threads.filter((t) => [t.code, t.name, t.brand ?? "", t.color].some((s) => s.toLowerCase().includes(q)));
  return { threads: hits.map((t, i) => ({ t, r: rank(t), i })).sort((x, y) => x.r - y.r || x.i - y.i).map((x) => x.t), hex: null };
}
