/** Where a design goes on common things, for the placement guides (text.placement,
 *  components/PlacementDialog.tsx) and the printed placement sheet (print.ts). Common practice,
 *  in our own words: each is a starting point, to check on the item itself. Measurements are in
 *  inches here and shown in inches and centimeters. */

/** One distance (inches), or a usual range. */
export type Measure = { label: string; inches: number | [number, number] };

export type Drawing = "towel" | "hand_towel" | "pillowcase" | "sheet" | "adult_chest" | "child_chest" | "tote" | "napkin" | "cap";

export type Placement = { id: string; name: string; where: string; measures: Measure[]; tip?: string; drawing: Drawing };

export const PLACEMENT_NOTE = "A starting point: check on your item.";

export const PLACEMENTS: Placement[] = [
  {
    id: "bath-towel",
    name: "Bath towel",
    where: "Centered side to side at one end, above the woven band (the flat stripe across the towel).",
    measures: [
      { label: "Bottom of the design above the band", inches: [2, 3] },
      { label: "With no band, bottom of the design above the hem", inches: [4, 5] },
      { label: "A usual letter height", inches: [3, 4] },
    ],
    tip: "Lay water-soluble topping over the loops so the stitches don't sink in.",
    drawing: "towel",
  },
  {
    id: "hand-towel",
    name: "Hand towel",
    where: "Centered side to side on the end that shows when the towel hangs.",
    measures: [
      { label: "Bottom of the design above the band", inches: [1.5, 2] },
      { label: "With no band, bottom of the design above the hem", inches: [3, 4] },
      { label: "A usual letter height", inches: [2, 2.5] },
    ],
    tip: "Use water-soluble topping on terry cloth.",
    drawing: "hand_towel",
  },
  {
    id: "pillowcase",
    name: "Pillowcase",
    where: "In the wide hem at the open end, halfway between the long edges, turned to read right when the pillow is on the bed.",
    measures: [
      { label: "Middle of the design in from the open edge, on a wide hem", inches: 2 },
      { label: "A usual letter height", inches: [2, 3] },
    ],
    tip: "Keep the other side of the pillowcase out of the hoop.",
    drawing: "pillowcase",
  },
  {
    id: "sheet-hem",
    name: "Sheet hem",
    where: "In the wide top hem of a flat sheet, halfway across. Fold the top down as it lies on the bed to check which way up the letters go.",
    measures: [
      { label: "Middle of the design from the hem's seam", inches: [1.5, 2] },
      { label: "A usual letter height", inches: [2, 3] },
    ],
    drawing: "sheet",
  },
  {
    id: "adult-left-chest",
    name: "Adult left chest",
    where: "On the wearer's left: it's on your right as you look at the shirt.",
    measures: [
      { label: "Middle of the design down from where the shoulder seam meets the collar", inches: [7, 9] },
      { label: "Middle of the design out from the center front", inches: [3.5, 4.5] },
      { label: "Design width, up to", inches: 4 },
    ],
    tip: "Smaller shirt sizes go toward the smaller numbers. Pin a printed copy on and try it before stitching.",
    drawing: "adult_chest",
  },
  {
    id: "child-left-chest",
    name: "Child left chest",
    where: "On the wearer's left: it's on your right as you look at the shirt.",
    measures: [
      { label: "Middle of the design down from where the shoulder seam meets the collar", inches: [5, 6] },
      { label: "Middle of the design out from the center front", inches: [2, 3] },
      { label: "Design width, up to", inches: 3 },
    ],
    tip: "Children's sizes vary a lot: check on the shirt itself.",
    drawing: "child_chest",
  },
  {
    id: "tote-bag",
    name: "Tote bag",
    where: "Centered side to side on the front.",
    measures: [
      { label: "Middle of the design down from the top edge", inches: [5, 7] },
      { label: "Stay at least this far from seams and handle stitching", inches: 1 },
    ],
    tip: "On a small bag, go a little above the middle instead. A thick bag can sit on sticky stabilizer rather than in the hoop.",
    drawing: "tote",
  },
  {
    id: "napkin-corner",
    name: "Napkin corner",
    where: "In one corner, turned on the diagonal so it reads from that corner toward the middle.",
    measures: [
      { label: "Middle of the design in from each edge of the corner, on a dinner napkin", inches: [2.5, 3] },
      { label: "A usual letter height", inches: [1.5, 2] },
    ],
    tip: "On a small cocktail napkin, move in less and stitch smaller.",
    drawing: "napkin",
  },
  {
    id: "cap-front",
    name: "Cap front",
    where: "Centered on the front panel, over the middle seam if the cap has one.",
    measures: [
      { label: "Bottom of the design above the bill's seam", inches: [0.5, 0.75] },
      { label: "Design height, up to", inches: 2.25 },
    ],
    tip: "A flat hoop can't hold a finished cap well: use a soft cap whose front lies flat, or sew a patch and attach it.",
    drawing: "cap",
  },
];

const inchText = (v: number) => String(v);
/** Half centimeters for longer distances, one decimal for short ones. */
const cmText = (v: number) => (v >= 2 ? String(Math.round(v * 2.54 * 2) / 2) : (v * 2.54).toFixed(1));

/** "7 to 9 in (18 to 23 cm)". */
export function formatMeasure(m: Measure): string {
  const values = Array.isArray(m.inches) ? m.inches : [m.inches];
  return `${values.map(inchText).join(" to ")} in (${values.map(cmText).join(" to ")} cm)`;
}

// ---------------------------------------------------------------- small drawings

// Each shape carries its own line width: the printed template styles every path on the page.
const LINE = 'style="stroke-width:1.5"';
const THIN = 'style="stroke-width:0.8" stroke-dasharray="3 2"';

/** Where the design's middle goes. */
const mark = (x: number, y: number, color: string) =>
  `<g stroke="${color}" fill="none"><circle cx="${x}" cy="${y}" r="5" ${LINE}/><path d="M${x - 9} ${y}h18M${x} ${y - 9}v18" ${LINE}/></g>`;

const SHIRT = "45,8 30,14 14,30 24,40 32,34 32,84 88,84 88,34 96,40 106,30 90,14 75,8 68,13 60,14 52,13";

const DRAWINGS: Record<Drawing, (color: string) => string> = {
  towel: (c) => `<rect x="35" y="4" width="50" height="82" rx="2" ${LINE}/><rect x="35" y="62" width="50" height="8" ${THIN}/>${mark(60, 48, c)}`,
  hand_towel: (c) => `<rect x="42" y="8" width="36" height="74" rx="2" ${LINE}/><rect x="42" y="60" width="36" height="7" ${THIN}/>${mark(60, 47, c)}`,
  pillowcase: (c) => `<rect x="8" y="20" width="104" height="50" rx="6" ${LINE}/><line x1="90" y1="20" x2="90" y2="70" ${THIN}/>${mark(101, 45, c)}`,
  sheet: (c) => `<rect x="14" y="6" width="92" height="78" ${LINE}/><line x1="14" y1="26" x2="106" y2="26" ${THIN}/>${mark(60, 16, c)}`,
  adult_chest: (c) => `<polygon points="${SHIRT}" ${LINE}/><line x1="60" y1="14" x2="60" y2="84" ${THIN}/>${mark(75, 36, c)}`,
  child_chest: (c) => `<g transform="translate(12 12) scale(0.8)"><polygon points="${SHIRT}" ${LINE}/><line x1="60" y1="14" x2="60" y2="84" ${THIN}/>${mark(74, 36, c)}</g>`,
  tote: (c) => `<path d="M42 30C42 4 78 4 78 30" ${LINE}/><rect x="28" y="30" width="64" height="54" rx="2" ${LINE}/>${mark(60, 50, c)}`,
  napkin: (c) => `<rect x="22" y="7" width="76" height="76" ${LINE}/><g transform="rotate(-45 83 68)">${mark(83, 68, c)}</g>`,
  cap: (c) => `<path d="M26 60C26 18 94 18 94 60Z" ${LINE}/><path d="M18 60C40 80 80 80 102 60C80 67 40 67 18 60Z" ${LINE}/><line x1="60" y1="29" x2="60" y2="60" ${THIN}/>${mark(60, 47, c)}`,
};

/** A small drawing of the thing, with a mark where the design's middle goes. Our own fixed
 *  text, safe to put straight into a page. */
export function diagramSvg(p: Placement, markColor = "#d33"): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 90" width="120" height="90" fill="none" stroke="currentColor">${DRAWINGS[p.drawing](markColor)}</svg>`;
}
