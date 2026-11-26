/**
 * What the panel shows for each fill pattern. A new pattern is one entry here (and its name in the
 * FillPattern union in types.ts): the panel and the folded heading are built from it.
 */
import { blendDefaults } from "./blend";
import type { ObjectItem } from "./types";

/** A number setting a pattern or line style has: its key in the shape's params, and its stepper. */
export type Field = { key: string; label: string; def: number; min: number; max: number; step: number; digits?: number; suffix?: string; title?: string };

export type FillPatternDef = {
  id: string;
  label: string;
  title: string;
  /** Lines over the shape: no Angle, Random, Edge pad or cross-hatch underlay. */
  open?: boolean;
  /** Ignores row spacing too: Density, slider and Spacing are hidden. */
  noSpacing?: boolean;
  /** No stitch Length field. */
  noLength?: boolean;
  /** Longest Length offered (default 7). */
  maxStitch?: number;
  /** The settings only this pattern has. */
  fields: Field[];
  hint?: string;
  /** The folded heading of an open pattern. */
  summary?: "label" | "label+density";
  /** The purple direction dots on the canvas. Left out: only patterns that aren't open show them. */
  directionDots?: boolean;
  /** Show Angle although the pattern is open (it lays its lines at that angle). */
  angle?: boolean;
  /** How many more colors the pattern can take (a blend's): they get their own thread buttons. */
  threads?: number;
  /** Settings set along with the pattern when it's chosen. */
  onChoose?: (o: ObjectItem) => Record<string, unknown>;
};

export const FILL_PATTERN_DEFS: FillPatternDef[] = [
  { id: "tatami", label: "Tatami", title: "Rows of stitches: the standard fill", fields: [] },
  {
    id: "gradient",
    label: "Gradient",
    title: "Rows that open out from dense to sparse across the shape: shading",
    fields: [{ key: "gradient_to_mm", label: "Sparse end", def: 1.6, min: 0.3, max: 5, step: 0.1, digits: 1, suffix: "mm", title: "Row spacing at the light end (the dense end uses the density above)" }],
  },
  {
    id: "wave",
    label: "Wave",
    title: "Rows that ripple like water",
    fields: [
      { key: "wave_mm", label: "Wave height", def: 1.5, min: 0.3, max: 6, step: 0.25, suffix: "mm" },
      { key: "wave_length_mm", label: "Wave length", def: 8, min: 2, max: 40, step: 1, digits: 0, suffix: "mm" },
    ],
  },
  {
    id: "contour",
    label: "Contour",
    title: "Rows that follow the outline inwards, ring by ring",
    open: true,
    fields: [],
    hint: "Row spacing is the density; try Light for an open, ringed look.",
    summary: "label+density",
  },
  {
    id: "stipple",
    label: "Stipple",
    title: "One meandering line over the shape, quilting style",
    open: true,
    noSpacing: true,
    maxStitch: 2.5,
    fields: [{ key: "stipple_mm", label: "Loop size", def: 3, min: 1, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "How far apart the meandering line's turns are" }],
    summary: "label",
  },
  {
    id: "cross",
    label: "Cross-stitch",
    title: "Little Xs on a square grid",
    open: true,
    noSpacing: true,
    noLength: true,
    fields: [{ key: "cross_mm", label: "Square", def: 2.5, min: 1, max: 8, step: 0.5, digits: 1, suffix: "mm", title: "Size of one cross-stitch" }],
    summary: "label",
    directionDots: true, // open, but it has always shown them
  },
  {
    id: "spiral",
    label: "Spiral",
    title: "One line that winds from the middle of the shape out to its edge",
    open: true,
    noSpacing: true,
    maxStitch: 4,
    fields: [{ key: "spiral_mm", label: "Ring spacing", def: 1.5, min: 0.4, max: 6, step: 0.1, digits: 1, suffix: "mm", title: "How far apart the spiral's turns are" }],
    summary: "label",
  },
  {
    id: "blend",
    label: "Blend",
    title: "The shape's color fades into a second (or a third) across the rows",
    fields: [],
    threads: 2,
    onChoose: blendDefaults,
  },
  {
    id: "motif",
    label: "Motif",
    title: "Rows of a little pattern across the shape",
    open: true,
    noSpacing: true,
    angle: true,
    directionDots: true,
    fields: [
      { key: "motif_mm", label: "Repeat", def: 5, min: 1.5, max: 20, step: 0.5, digits: 1, suffix: "mm", title: "Length of one repeat" },
      { key: "motif_width_mm", label: "Height", def: 4, min: 0.5, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "How tall each row of the motif is" },
      { key: "motif_gap_mm", label: "Row gap", def: 0.5, min: 0, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "Space between the rows" },
      { key: "motif_stagger", label: "Shift alternate rows", def: 0.5, min: 0, max: 1, step: 0.25, digits: 2, title: "Every other row moves along by this much of a repeat" },
    ],
    summary: "label",
  },
  {
    id: "maze",
    label: "Maze",
    title: "One path that winds in to the middle and back out, never crossing itself",
    open: true,
    noSpacing: true,
    maxStitch: 4,
    fields: [{ key: "maze_mm", label: "Path spacing", def: 2, min: 0.8, max: 6, step: 0.2, digits: 1, suffix: "mm", title: "How far apart the path's turns are" }],
    summary: "label",
  },
  {
    id: "ripple",
    label: "Ripple",
    title: "Rings spreading from the middle, like a drop in water",
    open: true,
    noSpacing: true,
    maxStitch: 4,
    fields: [{ key: "ripple_mm", label: "Ring spacing", def: 2, min: 0.6, max: 8, step: 0.2, digits: 1, suffix: "mm", title: "How far apart the rings are" }],
    summary: "label",
  },
  {
    id: "mesh",
    label: "Mesh",
    title: "A net of two sets of lines",
    open: true,
    noSpacing: true,
    angle: true,
    directionDots: true,
    fields: [
      { key: "mesh_mm", label: "Cell size", def: 3, min: 1, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "How far apart the lines are" },
      { key: "mesh_cross_deg", label: "Crossing angle", def: 90, min: 45, max: 90, step: 5, digits: 0, suffix: "°", title: "The angle between the two sets of lines" },
    ],
    summary: "label",
  },
];

const TATAMI = FILL_PATTERN_DEFS.find((d) => d.id === "tatami")!;

/** A pattern's descriptor; an unknown or missing one is treated as tatami. */
export const fillPatternDef = (id?: string): FillPatternDef => FILL_PATTERN_DEFS.find((d) => d.id === id) ?? TATAMI;

/** An open pattern ends where its own lines end: the red dot shows it but can't be moved. */
export const fixedFillEnd = (id?: string): boolean => !!fillPatternDef(id).open;

/** Whether a fill's rows turn to follow its angle lines: only Tatami's do, and only with two or
 *  more (the engine's turning.takes_over). Lines left over from Tatami do nothing on another
 *  pattern, and come back when Tatami is chosen again. */
export const turnsRows = (p: { pattern?: string; angle_lines?: unknown }): boolean =>
  (p.pattern ?? "tatami") === "tatami" && Array.isArray(p.angle_lines) && p.angle_lines.length >= 2;

/** Whether a fill with this pattern shows the two purple dots that set its rows' direction. */
export const hasDirectionDots = (id?: string): boolean => {
  const def = fillPatternDef(id);
  return def.directionDots ?? !def.open;
};
