/**
 * LUDD's own mouse pointers: each one says what a click or drag will do where the pointer is.
 *
 * - Pointing at nothing: the arrow (a drag scrolls the view). Over a shape: the arrow with a move
 *   badge. Over a point: the arrow with a point badge. Over a corner handle: resize. Over the turn
 *   handle: turn. Over a ruler or a guide: a guide with arrows showing which way it moves.
 * - Space held, or dragging the view: an open hand, then a closed one.
 * - Drawing: a precise crosshair with the tool's badge (line, satin, fill); the mark in the middle
 *   shows the kind of point the next click makes (circle: curve, square: corner (Shift), diamond:
 *   straight line (Ctrl)).
 * - Text, the knife, measuring, the stitch angle and stitch editing: the crosshair with their badge.
 *   Auto-trace: a wand whose sparkle is the spot that's clicked.
 *
 * All are 32×32 SVG with an ink outline and a bone fill, so they show on the dark workspace and on
 * light fabric. Every one falls back to a standard system pointer.
 */
import type { NodeKind } from "./design/types";

const INK = "#121114";
const BONE = "#EEE9DF";
const LIME = "#C8FF2E";

export type DrawTool = "run" | "satin" | "fill";
export type CursorName =
  | "arrow"
  | "move"
  | "point"
  | "resize"
  | "resize-nesw"
  | "stretch-x"
  | "stretch-y"
  | "rotate"
  | "guide-x"
  | "guide-y"
  | "grab"
  | "grabbing"
  | "precise"
  | `draw-${DrawTool}-${NodeKind}`
  | "text"
  | "autotrace"
  | "knife"
  | "measure"
  | "angle"
  | "stitch"
  | "busy";

type Def = { body: string; x: number; y: number; fallback: string } | { system: string };

/** Filled shapes with one outline round the lot (the outline layer first, the fill on top). */
const solid = (shapes: string, fill = BONE) =>
  `<g fill="${INK}" stroke="${INK}" stroke-width="2.6" stroke-linejoin="round">${shapes}</g><g fill="${fill}">${shapes}</g>`;

/** Lines with a light halo, so they show on dark and light. */
const lines = (d: string, width = 1.5) =>
  `<path d="${d}" fill="none" stroke="${BONE}" stroke-width="${width + 2.2}" stroke-linecap="round" stroke-linejoin="round"/>` +
  `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;

const ARROW = "M3 2 L3 23.5 L8.6 18.4 L12.4 26.8 L16.2 25.2 L12.5 17 L19.6 17 Z";
const arrow = () => solid(`<path d="${ARROW}"/>`);

/** A lime badge in the bottom-right corner holding a small ink icon. */
const badge = (icon: string, round = false) =>
  (round
    ? `<circle cx="24.5" cy="24.5" r="6.8" fill="${LIME}" stroke="${INK}" stroke-width="1.4"/>`
    : `<rect x="17.5" y="17.5" width="13.5" height="13.5" rx="3.5" fill="${LIME}" stroke="${INK}" stroke-width="1.4"/>`) + icon;

const ink = (d: string, width = 1.5) => `<path d="${d}" fill="none" stroke="${INK}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;

const BADGES: Record<DrawTool | "text" | "knife" | "measure" | "angle" | "stitch", string> = {
  // A running stitch: a dashed line.
  run: `<path d="M20.5 28 L28 20.5" fill="none" stroke="${INK}" stroke-width="1.8" stroke-dasharray="2.4 1.7"/>`,
  // A satin: a zigzag.
  satin: ink("M19.8 26.5 L22 20.8 L24.2 27.6 L26.4 20.8 L28.6 26.5", 1.4),
  // A fill: rows.
  fill: ink("M20 23.8 L23.8 20 M20 28 L28 20 M24.2 28 L28 24.2", 1.3),
  text: ink("M20.6 20.8 H28 M24.3 20.8 V28.2", 2),
  // A blade with its handle.
  knife: `<path d="M22.6 25.4 L29 19 L28.4 23.2 L24.4 27.2 Z" fill="${INK}"/>` + ink("M19.6 28.4 L22.6 25.4", 2.6),
  measure: ink("M19.6 25.8 L25.8 19.6 L28.8 22.6 L22.6 28.8 Z M21.6 23.8 L23 25.2 M23.7 21.7 L25.1 23.1 M25.8 19.6 L27.2 21", 1.2),
  angle: ink("M20.2 28 H28.6 M20.2 28 L27 20.2 M24.8 28 A4.6 4.6 0 0 0 23.4 24.6", 1.4),
  stitch: ink("M20 29 L28.6 20.4", 2) + `<circle cx="27.3" cy="21.7" r="1" fill="${LIME}" stroke="${INK}" stroke-width="0.8"/>`,
};

/** The crosshair, centred on (11, 11), with an optional mark in the middle. */
const CROSS = "M11 1.5 V7.5 M11 14.5 V20.5 M1.5 11 H7.5 M14.5 11 H20.5";
const MARKS: Record<NodeKind, string> = {
  s: `<circle cx="11" cy="11" r="2.2"/>`,
  c: `<rect x="9" y="9" width="4" height="4"/>`,
  l: `<path d="M11 8.4 L13.6 11 L11 13.6 L8.4 11 Z"/>`,
};
const crosshair = (mark?: NodeKind) =>
  lines(CROSS) +
  (mark
    ? `<g fill="none" stroke="${BONE}" stroke-width="3.4">${MARKS[mark]}</g><g fill="none" stroke="${INK}" stroke-width="1.3">${MARKS[mark]}</g>`
    : "");

const DEFS: Record<string, Def> = {
  arrow: { body: arrow(), x: 3, y: 2, fallback: "default" },
  move: {
    body:
      arrow() +
      badge(
        `<path d="M24.5 18.6 L27 21.1 H25.4 V23.6 H27.9 V22 L30.4 24.5 L27.9 27 V25.4 H25.4 V27.9 H27 L24.5 30.4 L22 27.9 H23.6 V25.4 H21.1 V27 L18.6 24.5 L21.1 22 V23.6 H23.6 V21.1 H22 Z" fill="${INK}"/>`,
        true,
      ),
    x: 3,
    y: 2,
    fallback: "move",
  },
  point: {
    body: arrow() + badge(`<rect x="22" y="22" width="5" height="5" fill="${BONE}" stroke="${INK}" stroke-width="1.4"/>`, true),
    x: 3,
    y: 2,
    fallback: "pointer",
  },
  resize: {
    body: solid(`<path d="M5 5 H14 L10.6 8.4 L23.6 21.4 L27 18 V27 H18 L21.4 23.6 L8.4 10.6 L5 14 Z"/>`),
    x: 16,
    y: 16,
    fallback: "nwse-resize",
  },
  // The other diagonal (top-right and bottom-left corners).
  "resize-nesw": {
    body: solid(`<path d="M27 5 V14 L23.6 10.6 L10.6 23.6 L14 27 H5 V18 L8.4 21.4 L21.4 8.4 L18 5 Z"/>`),
    x: 16,
    y: 16,
    fallback: "nesw-resize",
  },
  // Side handles: stretch one way only.
  "stretch-x": {
    body: solid(`<path d="M3.5 16 L10 9.5 V13.6 H22 V9.5 L28.5 16 L22 22.5 V18.4 H10 V22.5 Z"/>`),
    x: 16,
    y: 16,
    fallback: "ew-resize",
  },
  "stretch-y": {
    body: solid(`<path d="M16 3.5 L22.5 10 H18.4 V22 H22.5 L16 28.5 L9.5 22 H13.6 V10 H9.5 Z"/>`),
    x: 16,
    y: 16,
    fallback: "ns-resize",
  },
  rotate: {
    // Three quarters of a circle, from the top round to the left, with the arrowhead going up.
    body: lines("M16 7 A9 9 0 1 1 7 16", 2.4) + solid(`<path d="M2.6 17.2 L11.4 17.2 L7 10.6 Z"/>`),
    x: 16,
    y: 16,
    fallback: "alias",
  },
  "guide-x": {
    body: lines("M16 2.5 V29.5", 1.8) + solid(`<path d="M3.5 16 L9.5 10 V13.6 H22.5 V10 L28.5 16 L22.5 22 V18.4 H9.5 V22 Z"/>`, LIME),
    x: 16,
    y: 16,
    fallback: "col-resize",
  },
  "guide-y": {
    body: lines("M2.5 16 H29.5", 1.8) + solid(`<path d="M16 3.5 L22 9.5 H18.4 V22.5 H22 L16 28.5 L10 22.5 H13.6 V9.5 H10 Z"/>`, LIME),
    x: 16,
    y: 16,
    fallback: "row-resize",
  },
  grab: {
    body:
      solid(
        `<rect x="9.2" y="6" width="3.6" height="13" rx="1.8"/><rect x="12.9" y="3.6" width="3.6" height="14" rx="1.8"/>` +
          `<rect x="16.6" y="4.6" width="3.6" height="13.4" rx="1.8"/><rect x="20.3" y="7.4" width="3.4" height="12" rx="1.7"/>` +
          `<rect x="8.8" y="13" width="15" height="14" rx="5.5"/><rect x="3.4" y="14.2" width="8.6" height="3.6" rx="1.8" transform="rotate(38 7.7 16)"/>`,
      ) + ink("M12.85 13 V17 M16.55 13 V17 M20.25 13 V17", 0.9),
    x: 16,
    y: 15,
    fallback: "grab",
  },
  grabbing: {
    body:
      solid(
        `<rect x="9.2" y="10.2" width="3.6" height="7" rx="1.8"/><rect x="12.9" y="9.2" width="3.6" height="8" rx="1.8"/>` +
          `<rect x="16.6" y="9.4" width="3.6" height="8" rx="1.8"/><rect x="20.3" y="10.6" width="3.4" height="7" rx="1.7"/>` +
          `<rect x="8.8" y="13" width="15" height="13" rx="5.5"/><rect x="5.6" y="15.2" width="7" height="3.6" rx="1.8" transform="rotate(20 9.1 17)"/>`,
      ) + ink("M12.85 13.2 V16 M16.55 13.2 V16 M20.25 13.2 V16", 0.9),
    x: 16,
    y: 16,
    fallback: "grabbing",
  },
  precise: { body: crosshair(), x: 11, y: 11, fallback: "crosshair" },
  text: { body: crosshair() + badge(BADGES.text), x: 11, y: 11, fallback: "crosshair" },
  knife: { body: crosshair() + badge(BADGES.knife), x: 11, y: 11, fallback: "crosshair" },
  measure: { body: crosshair() + badge(BADGES.measure), x: 11, y: 11, fallback: "crosshair" },
  angle: { body: crosshair() + badge(BADGES.angle), x: 11, y: 11, fallback: "crosshair" },
  stitch: { body: crosshair() + badge(BADGES.stitch), x: 11, y: 11, fallback: "crosshair" },
  autotrace: {
    // A wand; the sparkle at its tip is where the click lands.
    body:
      lines("M10.5 10.5 L27 27", 3) +
      `<path d="M10.5 10.5 L14.5 14.5" stroke="${LIME}" stroke-width="2.4" stroke-linecap="round"/>` +
      solid(`<path d="M5 0.8 L6.3 3.7 L9.2 5 L6.3 6.3 L5 9.2 L3.7 6.3 L0.8 5 L3.7 3.7 Z"/>`, LIME) +
      solid(`<path d="M13 2.5 L13.7 4 L15.2 4.7 L13.7 5.4 L13 6.9 L12.3 5.4 L10.8 4.7 L12.3 4 Z"/>`, LIME),
    x: 5,
    y: 5,
    fallback: "crosshair",
  },
  busy: { system: "progress" },
};
for (const tool of ["run", "satin", "fill"] as DrawTool[]) {
  for (const kind of ["s", "c", "l"] as NodeKind[]) {
    DEFS[`draw-${tool}-${kind}`] = { body: crosshair(kind) + badge(BADGES[tool]), x: 11, y: 11, fallback: "crosshair" };
  }
}

const svg = (body: string) => `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">${body}</svg>`;

const cache = new Map<string, string>();

/** The CSS `cursor` value for a pointer: the drawing, its hot spot, and a system pointer to fall back on. */
export function cursorCss(name: CursorName): string {
  const hit = cache.get(name);
  if (hit) return hit;
  const d = DEFS[name];
  const css = "system" in d ? d.system : `url("data:image/svg+xml,${encodeURIComponent(svg(d.body))}") ${d.x} ${d.y}, ${d.fallback}`;
  cache.set(name, css);
  return css;
}

/** Every pointer LUDD has (for tests and the gallery). */
export const CURSOR_NAMES = Object.keys(DEFS) as CursorName[];

/** The SVG of a pointer (for tests and the gallery); null for a system pointer. */
export function cursorSvg(name: CursorName): string | null {
  const d = DEFS[name];
  return "system" in d ? null : svg(d.body);
}
