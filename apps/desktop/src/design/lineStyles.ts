/**
 * What the panel offers for running stitch lines: the line styles, the motifs, and the settings
 * each style has. A new style or motif is one entry here (and its name in types.ts).
 */
import type { Field } from "./fillPatterns";

export const MOTIF_FIELDS: Field[] = [
  { key: "motif_mm", label: "Repeat", def: 4, min: 1.5, max: 20, step: 0.5, digits: 1, suffix: "mm", title: "Length of one repeat" },
  { key: "motif_width_mm", label: "Width", def: 2.5, min: 0.5, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "How wide the motif is" },
];

const KNOT_SIZE: Field = { key: "knot_mm", label: "Knot size", def: 1.6, min: 1, max: 3, step: 0.2, digits: 1, suffix: "mm", title: "How big each knot is" };

export type LineStyleDef = {
  id: string;
  label: string;
  title: string;
  /** Listed under "More styles" instead of among the buttons. */
  more?: boolean;
  /** The settings only this style has (Length, in Advanced, is every line's). */
  fields: Field[];
  /** No stitch Length: the style's own sizes are all it has. */
  noLength?: boolean;
};

export const LINE_STYLE_DEFS: LineStyleDef[] = [
  { id: "single", label: "Single", title: "One pass", fields: [] },
  { id: "triple", label: "Triple", title: "Sewn three times end to end: bolder", fields: [] },
  { id: "bean", label: "Bean", title: "Each stitch sewn three times: boldest", fields: [] },
  { id: "motif", label: "Motif", title: "A little pattern repeated along the line: waves, zigzag, scallops, blanket stitch", fields: MOTIF_FIELDS },
  { id: "backstitch", label: "Backstitch", title: "Forward a stitch, back half of one: a firm outline three threads thick", more: true, fields: [] },
  {
    id: "stem",
    label: "Stem stitch",
    title: "Slanted stitches that overlap by half, like a twisted rope",
    more: true,
    fields: [{ key: "stem_width_mm", label: "Width", def: 0.8, min: 0.3, max: 2.5, step: 0.1, digits: 1, suffix: "mm", title: "How wide the rope is" }],
  },
  {
    id: "candlewick",
    label: "Candlewicking",
    title: "A line with little knots along it",
    more: true,
    fields: [
      KNOT_SIZE,
      { key: "knot_gap_mm", label: "Between knots", def: 4, min: 2, max: 15, step: 0.5, digits: 1, suffix: "mm", title: "From the middle of one knot to the next: at least the knot size plus 1 mm" },
    ],
  },
  { id: "redwork", label: "Redwork", title: "Out and back along the line, the way back filling in between the holes: smooth, like hand redwork", more: true, fields: [] },
  { id: "knots", label: "French knots", title: "A knot at every point of the line, with a jump from one to the next", more: true, noLength: true, fields: [KNOT_SIZE] },
];

/** A style's descriptor; an unknown or missing one is treated as Single. */
export const lineStyleDef = (id?: string): LineStyleDef => LINE_STYLE_DEFS.find((d) => d.id === id) ?? LINE_STYLE_DEFS[0];

export const MOTIF_DEFS: { id: string; label: string }[] = [
  { id: "wave", label: "Wave" },
  { id: "zigzag", label: "Zigzag" },
  { id: "scallop", label: "Scallop" },
  { id: "blanket", label: "Blanket stitch (applique edge)" },
  { id: "leaf", label: "Leaves" },
];
