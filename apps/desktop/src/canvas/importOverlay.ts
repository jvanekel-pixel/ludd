/**
 * Artwork about to be imported (P7-D1), drawn as outlines on the hoop while its dialog is open.
 * Nothing here is in the design: feat/importArt.ts says what to show and when to stop.
 */
import type { Graphics } from "pixi.js";
import { flatten, type Pt } from "../design/paths";
import type { PathNode } from "../design/types";
import { registerOverlay, type CanvasCtx } from "./hooks";

/** One shape's outline: its lines (and a satin's width), in its color. */
export type ImportOutline = { color: string; width_mm?: number; paths: { nodes: PathNode[]; closed: boolean }[] };

let shown: readonly ImportOutline[] = [];
let canvas: CanvasCtx | null = null;

/** Show these outlines (none: show nothing), and redraw. */
export function showImportOutlines(outlines: readonly ImportOutline[]): void {
  if (!outlines.length && !shown.length) return;
  shown = outlines;
  canvas?.redraw();
}

/** What's shown now (for tests). */
export const importOutlines = (): readonly ImportOutline[] => shown;

const rgb = (color: string): number => Number.parseInt(color.slice(1, 7), 16) || 0;

/** Light colors get a dark edge, dark ones a white edge, so any thread shows on the fabric. */
const edge = (color: number): number => {
  const luminance = 0.2126 * ((color >> 16) & 255) + 0.7152 * ((color >> 8) & 255) + 0.0722 * (color & 255);
  return luminance > 170 ? 0x303030 : 0xffffff;
};

function trace(g: Graphics, points: Pt[]): void {
  g.moveTo(points[0][0], points[0][1]);
  for (const p of points.slice(1)) g.lineTo(p[0], p[1]);
}

registerOverlay({
  id: "import-art",
  draw(g, px, ctx) {
    canvas = ctx; // kept, so a new preview can be drawn when it arrives
    for (const outline of shown) {
      const color = rgb(outline.color);
      const lines = outline.paths.map(({ nodes, closed }) => {
        const points = flatten(nodes, closed);
        return closed && points.length ? [...points, points[0]] : points;
      });
      const all = lines.filter((p) => p.length > 1);
      if (!all.length) continue;
      if (outline.width_mm) {
        for (const points of all) trace(g, points);
        g.stroke({ width: outline.width_mm, color, alpha: 0.35, join: "round", cap: "butt" });
      }
      for (const points of all) trace(g, points);
      g.stroke({ width: 3 * px, color: edge(color), alpha: 0.85, join: "round", cap: "round" });
      for (const points of all) trace(g, points);
      g.stroke({ width: 1.5 * px, color, join: "round", cap: "round" });
    }
  },
});
