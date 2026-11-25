/**
 * Outlines for the ready-made shapes in the Shapes menu, as pen-tool points in mm (the curve rule
 * is in paths.ts: "s" curves smoothly through a point, "l" comes straight into it, "c" is a sharp
 * point). Each goes round clockwise on screen, like the rectangle.
 */
import type { NodeKind, PathNode } from "./types";

export type ShapeId = "rectangle" | "circle" | "star" | "roundedRect" | "ellipse" | "triangle" | "polygon" | "heart";

export const MIN_SIDES = 3;
export const MAX_SIDES = 12;
const DEFAULT_SIDES = 6;

/** A polygon's number of sides: a whole number from 3 to 12 (6 if it isn't a number at all). */
export function clampSides(v: unknown): number {
  return typeof v === "number" && Number.isFinite(v) ? Math.min(MAX_SIDES, Math.max(MIN_SIDES, Math.round(v))) : DEFAULT_SIDES;
}

/** The heart's right half between the dip and the tip, from its middle, as parts of its width
 *  (y down). It is 0.9 times as tall as it is wide. The two points beside each lobe's top are
 *  level, so the top is exactly that point. */
const HEART: readonly [number, number][] = [[0.1096, -0.39], [0.269, -0.45], [0.4334, -0.39], [0.4981, -0.21], [0.3686, 0.095]];
const HEART_DIP = -0.26;
const HEART_TIP = 0.45;

/** Outline points for a ready-made shape centered on (cx, cy), `size` mm wide. `sides` is for the
 *  polygon. (The star is centered on the circle its points sit on, a little narrower than `size`.) */
export function shapeNodes(shape: ShapeId, cx: number, cy: number, size: number, opts: { sides?: number } = {}): PathNode[] {
  const r = size / 2;
  /** A point, from the shape's middle. */
  const at = (x: number, y: number, kind: NodeKind): PathNode => [round2(cx + x), round2(cy + y), kind];
  // Eight curve points make a smooth oval (or circle) with the Catmull-Rom curve rule.
  const oval = (rx: number, ry: number) =>
    Array.from({ length: 8 }, (_, i) => {
      const a = (i / 8) * 2 * Math.PI;
      return at(rx * Math.cos(a), ry * Math.sin(a), "s");
    });
  /** A regular polygon with its first corner at the top, `size` wide, its box centered. */
  const regular = (n: number) => {
    const unit = Array.from({ length: n }, (_, i) => {
      const a = -Math.PI / 2 + (i / n) * 2 * Math.PI;
      return [Math.cos(a), Math.sin(a)] as const;
    });
    const xs = unit.map((p) => p[0]);
    const ys = unit.map((p) => p[1]);
    const k = size / (Math.max(...xs) - Math.min(...xs));
    const middle = (Math.min(...ys) + Math.max(...ys)) / 2; // (left and right are already even)
    return unit.map(([x, y]) => at(k * x, k * (y - middle), "c"));
  };

  switch (shape) {
    case "rectangle": {
      const h = r * 0.7;
      return [at(-r, -h, "c"), at(r, -h, "c"), at(r, h, "c"), at(-r, h, "c")];
    }
    case "circle":
      return oval(r, r);
    case "ellipse":
      return oval(r, r * 0.7);
    case "star":
      return Array.from({ length: 10 }, (_, i) => {
        const a = -Math.PI / 2 + (i / 10) * 2 * Math.PI;
        const rr = i % 2 === 0 ? r : r * 0.45;
        return at(rr * Math.cos(a), rr * Math.sin(a), "c");
      });
    case "roundedRect": {
      const h = r * 0.7;
      const corner = size * 0.15;
      // Each corner: the middle of its quarter circle and the angle it starts at, from top right.
      const corners = [
        [r - corner, corner - h, -90],
        [r - corner, h - corner, 0],
        [corner - r, h - corner, 90],
        [corner - r, corner - h, 180],
      ];
      return corners.flatMap(([x, y, from]) =>
        // A straight side runs into the first point ("l"), three curve points lie on the corner,
        // and the next side leaves straight from where it ends ("c").
        [0, 22.5, 45, 67.5, 90].map((turn) => {
          const a = ((from + turn) * Math.PI) / 180;
          return at(x + corner * Math.cos(a), y + corner * Math.sin(a), turn === 0 ? "l" : turn === 90 ? "c" : "s");
        }),
      );
    }
    case "triangle":
      return regular(3);
    case "polygon":
      return regular(clampSides(opts.sides));
    case "heart": {
      const right = HEART.map(([x, y]) => at(size * x, size * y, "s"));
      const left = [...HEART].reverse().map(([x, y]) => at(-size * x, size * y, "s"));
      return [at(0, size * HEART_DIP, "c"), ...right, at(0, size * HEART_TIP, "c"), ...left];
    }
  }
}

// "+ 0" turns -0 into 0, so points compare and serialize cleanly.
const round2 = (v: number) => Math.round(v * 100) / 100 + 0;
