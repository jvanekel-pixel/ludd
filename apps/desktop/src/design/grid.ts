/** Zoom-adaptive grid: picks line spacings so squares stay readable at any zoom. */

export type Units = "in" | "mm";

export const MM_PER_IN = 25.4;
/** CSS pixels per mm at "100%": browsers assume 96 px per inch. */
export const PX_PER_MM_ACTUAL = 96 / MM_PER_IN;

/** Minor line spacing must be at least this many screen pixels apart. */
export const MIN_MINOR_PX = 8;

// [minor, major] spacings in the unit, finest first.
const STEPS: Record<Units, [number, number][]> = {
  in: [
    [1 / 32, 1],
    [1 / 16, 1],
    [1 / 8, 1],
    [1 / 4, 1],
    [1 / 2, 2],
    [1, 4],
    [2, 12],
    [6, 24],
    [12, 48],
  ],
  mm: [
    [0.5, 5],
    [1, 10],
    [2, 10],
    [5, 50],
    [10, 50],
    [25, 100],
    [50, 250],
    [100, 500],
    [250, 1000],
  ],
};

export type GridSpacing = { minorMm: number; majorMm: number; ratio: number };

/** Finest spacing whose minor lines are at least MIN_MINOR_PX apart at `scale` px/mm. */
export function gridSpacing(scale: number, units: Units): GridSpacing {
  const unit = units === "in" ? MM_PER_IN : 1;
  const steps = STEPS[units];
  const [minor, major] = steps.find(([m]) => m * unit * scale >= MIN_MINOR_PX) ?? steps[steps.length - 1];
  return { minorMm: minor * unit, majorMm: major * unit, ratio: Math.round(major / minor) };
}

/** Grid line positions (mm) covering [lo, hi], aligned to `origin`, with a major flag. */
export function gridLines(lo: number, hi: number, origin: number, sp: GridSpacing): { mm: number; major: boolean }[] {
  const k0 = Math.floor((lo - origin) / sp.minorMm);
  const k1 = Math.ceil((hi - origin) / sp.minorMm);
  const out = [];
  for (let k = k0; k <= k1; k++) {
    out.push({ mm: origin + k * sp.minorMm, major: ((k % sp.ratio) + sp.ratio) % sp.ratio === 0 });
  }
  return out;
}

/** Zoom percentage, where 100% shows the design at about real size on a typical screen. */
export function zoomPercent(scale: number): number {
  return Math.round((scale / PX_PER_MM_ACTUAL) * 100);
}
