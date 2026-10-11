import { Kind, type CutStops, type Design, type DesignInfo, type Hoop, type Machine } from "./types";

export type HoopFit = "fits" | "rotate" | "too_big";

/** Whether the design fits the hoop as is, only turned 90°, or not at all. */
export function hoopFit(info: Pick<DesignInfo, "width_mm" | "height_mm">, hoop: Hoop): HoopFit {
  const eps = 1e-6;
  const { width_mm: w, height_mm: h } = info;
  if (w <= hoop.width_mm + eps && h <= hoop.height_mm + eps) return "fits";
  if (h <= hoop.width_mm + eps && w <= hoop.height_mm + eps) return "rotate";
  return "too_big";
}

/** Whether the design has a trim between two stitches of the same color. */
export function hasTrims(design: Design): boolean {
  const kinds = design.records.kind;
  let sewn = false;
  for (const k of kinds) {
    if (k === Kind.Stitch) sewn = true;
    else if (k === Kind.Trim && sewn) return true;
    else if (k === Kind.ColorChange || k === Kind.Stop) sewn = false;
  }
  return false;
}

export const DEFAULT_CUT_STOPS: CutStops = { enabled: false, min_jump_mm: 3, include_untrimmed: false, tie: true };

/** Cut-stops are on by default for machines that only cut at color changes, if there's anything to cut. */
export function defaultCutStops(machine: Machine | null, design: Design | null): CutStops {
  return {
    ...DEFAULT_CUT_STOPS,
    enabled: machine?.cuts === "color_change" && design !== null && hasTrims(design),
  };
}

/** Default export extension: the machine's preferred format, else PES. */
export function defaultFormat(machine: Machine | null): string {
  return machine?.formats[0] ?? "pes";
}
