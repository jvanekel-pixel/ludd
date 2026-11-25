/**
 * What the panel shows for each fill pattern. A new pattern is one entry here (and its name in the
 * FillPattern union in types.ts): the panel and the folded heading are built from it.
 */

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
  },
];

const TATAMI = FILL_PATTERN_DEFS.find((d) => d.id === "tatami")!;

/** A pattern's descriptor; an unknown or missing one is treated as tatami. */
export const fillPatternDef = (id?: string): FillPatternDef => FILL_PATTERN_DEFS.find((d) => d.id === id) ?? TATAMI;
