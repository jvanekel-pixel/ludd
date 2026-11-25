/**
 * What the panel offers for running stitch lines: the line styles, the motifs, and the settings a
 * motif line has. A new style or motif is one entry here (and its name in types.ts).
 */
import type { Field } from "./fillPatterns";

export const LINE_STYLE_DEFS: { id: string; label: string; title: string }[] = [
  { id: "single", label: "Single", title: "One pass" },
  { id: "triple", label: "Triple", title: "Sewn three times end to end: bolder" },
  { id: "bean", label: "Bean", title: "Each stitch sewn three times: boldest" },
  { id: "motif", label: "Motif", title: "A little pattern repeated along the line: waves, zigzag, scallops, blanket stitch" },
];

export const MOTIF_DEFS: { id: string; label: string }[] = [
  { id: "wave", label: "Wave" },
  { id: "zigzag", label: "Zigzag" },
  { id: "scallop", label: "Scallop" },
  { id: "blanket", label: "Blanket stitch (applique edge)" },
];

export const MOTIF_FIELDS: Field[] = [
  { key: "motif_mm", label: "Repeat", def: 4, min: 1.5, max: 20, step: 0.5, digits: 1, suffix: "mm", title: "Length of one repeat" },
  { key: "motif_width_mm", label: "Width", def: 2.5, min: 0.5, max: 10, step: 0.5, digits: 1, suffix: "mm", title: "How wide the motif is" },
];
