/**
 * Garment outlines for "Preview on": simple silhouettes in mm, centred on the hoop (0, 0), the
 * way the design usually sits on them (a T-shirt's left chest, a towel's corner…). Only a
 * picture behind the design: nothing here is stitched.
 */
import type { Garment } from "../store";

export const GARMENTS: { id: Garment; label: string }[] = [
  { id: "none", label: "Nothing (plain fabric)" },
  { id: "tshirt", label: "T-shirt (left chest)" },
  { id: "tote", label: "Tote bag" },
  { id: "towel", label: "Towel (corner)" },
  { id: "bodysuit", label: "Baby bodysuit" },
  { id: "cap", label: "Cap (front)" },
];

type Pt = [number, number];

/** Outline (closed) and any detail lines, in mm, with the design at (0, 0). */
export function garmentShape(g: Garment): { outline: Pt[]; details: Pt[][] } | null {
  switch (g) {
    case "tshirt": {
      // About an adult medium: 520 mm wide at the chest; the design sits on the left chest.
      const ox = -80;
      const oy = 120;
      const o: Pt[] = [
        [-260, -300], [-90, -330], [-50, -300], [50, -300], [90, -330], [260, -300], [400, -170], [320, -80], [260, -150],
        [260, 420], [-260, 420], [-260, -150], [-320, -80], [-400, -170],
      ];
      const neck: Pt[] = [[-90, -330], [-60, -280], [0, -262], [60, -280], [90, -330]];
      return { outline: o.map(([x, y]) => [x + ox, y + oy]), details: [neck.map(([x, y]) => [x + ox, y + oy] as Pt)] };
    }
    case "tote": {
      const o: Pt[] = [[-190, -150], [190, -150], [190, 240], [-190, 240]];
      const strap: Pt[] = [[-90, -150], [-90, -330], [90, -330], [90, -150]];
      return { outline: o, details: [strap] };
    }
    case "towel": {
      // A hand towel, design in the bottom right corner.
      const o: Pt[] = [[-420, -650], [80, -650], [80, 110], [-420, 110]];
      const band: Pt[] = [[-420, 60], [80, 60]];
      return { outline: o, details: [band] };
    }
    case "bodysuit": {
      const o: Pt[] = [
        [-120, -170], [-50, -190], [50, -190], [120, -170], [190, -100], [150, -50], [120, -80], [120, 120], [60, 200], [30, 230],
        [-30, 230], [-60, 200], [-120, 120], [-120, -80], [-150, -50], [-190, -100],
      ];
      const neck: Pt[] = [[-50, -190], [-30, -160], [0, -152], [30, -160], [50, -190]];
      return { outline: o.map(([x, y]) => [x, y + 40] as Pt), details: [neck.map(([x, y]) => [x, y + 40] as Pt)] };
    }
    case "cap": {
      const crown: Pt[] = [];
      for (let i = 0; i <= 24; i++) {
        const a = Math.PI + (i / 24) * Math.PI;
        crown.push([Math.cos(a) * 130, Math.sin(a) * 110 + 40]);
      }
      const o: Pt[] = [...crown, [170, 40], [190, 80], [-190, 80], [-170, 40]];
      return { outline: o, details: [[[-130, 40], [130, 40]]] };
    }
    default:
      return null;
  }
}
