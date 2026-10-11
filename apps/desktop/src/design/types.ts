/** Mirrors engine/threadline_engine/design.py. Units are millimetres. */

export const Kind = { Stitch: 0, Jump: 1, Trim: 2, Stop: 3, ColorChange: 4, End: 5 } as const;
export type Kind = (typeof Kind)[keyof typeof Kind];

export type Thread = { color: string; name: string; catalog: string; brand: string };

/** A run of records sewn in one thread. `end` is exclusive. */
export type Block = {
  thread: number;
  start: number;
  end: number;
  /** Layouts only: the source color blocks this block came from (several after combining colors). */
  sources?: { item: number; block: number }[];
  /** Layouts only: the file's thread before any recolor (null for added stitching such as basting). */
  original?: Thread | null;
};

export type DesignInfo = {
  stitches: number;
  jumps: number;
  trims: number;
  stops: number;
  color_changes: number;
  colors: number;
  width_mm: number;
  height_mm: number;
  bounds_mm: [number, number, number, number];
};

export type Design = {
  path: string;
  name: string;
  format: string;
  info: DesignInfo;
  threads: Thread[];
  blocks: Block[];
  records: {
    x: number[];
    y: number[];
    kind: Kind[];
    /** Layouts only: which item each record came from (-1 = added, e.g. basting). */
    item?: number[];
    /** Layouts only: the record's index in its item's source file (-1 = added). */
    src?: number[];
  };
  /** Layouts only: where each placed design ended up. */
  items?: LayoutItemInfo[];
  warnings?: Warning[];
};

export type LayoutItemInfo = {
  id: string;
  name: string;
  kind: "file" | ObjectKind | "text";
  center_mm: [number, number];
  bounds_mm: [number, number, number, number] | null;
  source_size_mm: [number, number] | null;
};

export type Transform = {
  x: number;
  y: number;
  rotate: number;
  scale_x: number;
  scale_y: number;
  flip_x: boolean;
  flip_y: boolean;
};

export type LayoutOp =
  | { op: "delete_block"; block: number }
  | { op: "insert"; after: number; command: "stop" | "trim" }
  | { op: "jumps_to_trims"; min_mm: number };

/** A stitch file placed in the layout. */
export type FileItem = {
  id: string;
  kind?: "file";
  path: string;
  transform: Transform;
  /** Replacement thread per source color block (null = as in the file). */
  threads: (Thread | null)[];
  ops: LayoutOp[];
  /** Pinned: can't be dragged on the canvas. */
  locked?: boolean;
  /** Items with the same group select and move together (Ctrl+G). */
  group?: string;
};

/** A pen-tool point in mm; its kind is the path coming into it: curve ("s"), line ("l") or cusp ("c"). */
export type NodeKind = "s" | "l" | "c";
export type PathNode = [number, number, NodeKind];

export type ObjectKind = "run" | "satin" | "fill" | "applique";

export type RunGeometry = { nodes: PathNode[]; closed?: boolean };
export type SatinGeometry = { rail_a: PathNode[]; rail_b: PathNode[] };
export type FillGeometry = { outline: PathNode[]; holes?: PathNode[][] };

export type RunParams = { style?: "single" | "triple" | "bean"; stitch_mm?: number; tie_in?: boolean; tie_off?: boolean };
export type SatinParams = {
  spacing_mm?: number;
  pull_comp_mm?: number;
  underlay?: ("center" | "edge" | "zigzag")[];
  tie_in?: boolean;
  tie_off?: boolean;
};
export type FillParams = {
  angle_deg?: number;
  spacing_mm?: number;
  stitch_mm?: number;
  pull_comp_mm?: number;
  underlay?: ("edge" | "tatami")[];
  tie_in?: boolean;
  tie_off?: boolean;
};

export type AppliqueParams = {
  /** Satin border over the cut edge. */
  cover_width_mm?: number;
  spacing_mm?: number;
  tack?: "zigzag" | "run";
  /** Sew a placement line first (off when pre-cut pieces are placed by eye). */
  placement?: boolean;
};

type ObjectBase = {
  id: string;
  name?: string;
  /** Pinned: can't be dragged on the canvas. */
  locked?: boolean;
  group?: string;
  thread: Thread;
  transform: Transform;
  threads: (Thread | null)[];
  ops: LayoutOp[];
};

/** A shape drawn in LUDD; its stitches are generated from it. */
export type ObjectItem =
  | (ObjectBase & { kind: "run"; geometry: RunGeometry; params: RunParams })
  | (ObjectBase & { kind: "satin"; geometry: SatinGeometry; params: SatinParams })
  | (ObjectBase & { kind: "fill"; geometry: FillGeometry; params: FillParams })
  | (ObjectBase & { kind: "applique"; geometry: FillGeometry; params: AppliqueParams });

export type FontRef = { path: string; index: number; family: string; style: string };
export type FontInfo = { family: string; style: string; path: string; index: number; kind: "outline" | "stitch" };

export type TextShape = { type: "line" | "arc_up" | "arc_down" | "circle"; radius_mm?: number };

/** Lettering: stitched from a font each time, so it stays editable and keeps its density at any size. */
export type TextItem = {
  id: string;
  kind: "text";
  name?: string;
  text: string;
  font: FontRef;
  /** Height of capital letters, mm. */
  size_mm: number;
  spacing_mm: number;
  style: "satin" | "fill";
  shape: TextShape;
  monogram: boolean;
  locked?: boolean;
  group?: string;
  thread: Thread;
  transform: Transform;
  threads: (Thread | null)[];
  ops: LayoutOp[];
};

export type LayoutItem = FileItem | ObjectItem | TextItem;

export const isText = (it: LayoutItem): it is TextItem => it.kind === "text";

export const isObject = (it: LayoutItem): it is ObjectItem =>
  it.kind === "run" || it.kind === "satin" || it.kind === "fill" || it.kind === "applique";

/** A picture to trace over. Placement in mm, centred on (x, y). */
export type RefImage = {
  id: string;
  name: string;
  path: string;
  data_url: string;
  x: number;
  y: number;
  width_mm: number;
  height_mm: number;
  rotate: number;
  opacity: number;
  locked: boolean;
  visible: boolean;
};

/** Everything undoable: the layout and the reference pictures. */
export type Doc = { layout: Layout; images: RefImage[] };

/** One or more stitch files placed and edited together; the files themselves are never changed. */
export type Layout = {
  /** Shown instead of the file name, e.g. a saved project's name. */
  title?: string;
  items: LayoutItem[];
  merge_colors: boolean;
  color_sort: boolean;
  basting: { enabled: boolean; margin_mm: number };
  /** What it will be stitched on (a fabric id); sets density, pull compensation and underlay. */
  fabric?: string;
  /** A light grid of stitches under the design, for towels and fleece. */
  knockdown?: { enabled: boolean; margin_mm: number };
};

export type Fabric = {
  id: string;
  name: string;
  examples: string;
  stabilizer: string;
  topping: string | null;
};

/** A quality check: what's wrong, why it matters and what to do, and where. */
export type QualityCheck = Warning & { why?: string; fix?: string; at?: [number, number]; item_id?: string };

/** Thread per square millimetre, 0..255 per cell (row by row); `limit` is where it gets too dense. */
export type Heatmap = { x: number; y: number; cell_mm: number; width: number; height: number; limit: number; data: string };

export type CheckResult = { checks: QualityCheck[]; heatmap?: Heatmap; fabric: { id: string; name: string; advice: string } };

export type Formats = {
  read: { ext: string; description: string }[];
  write: { ext: string; description: string }[];
};

export type ConvertResult = {
  converted: { src: string; dest: string }[];
  failed: { src: string; error: string }[];
  skipped: string[];
};

export type Hoop = { id: string; name: string; width_mm: number; height_mm: number };

export type Machine = {
  id: string;
  name: string;
  brand: string;
  formats: string[];
  needles: number;
  hoops: Hoop[];
  /** Where the machine cuts on its own. "color_change" machines need cut-stops to cut jumps. */
  cuts: "trim" | "color_change" | "none";
  max_stitch_mm: number | null;
  max_stitches: number | null;
  max_colors: number | null;
  notes: string;
  builtin: boolean;
};

export type ChartSummary = { id: string; name: string; brand: string; builtin: boolean; count: number; mine: boolean };
/** `brand` is set on My threads entries, which can mix brands. */
export type ChartThread = { code: string; name: string; color: string; brand?: string };
export type Chart = Omit<ChartSummary, "count"> & { threads: ChartThread[] };
export type ThreadMatch = ChartThread & { brand: string; delta_e: number };

export type CutStops = { enabled: boolean; min_jump_mm: number; include_untrimmed: boolean; tie: boolean };

export type ExportOptions = {
  machine: string | null;
  hoop: string | null;
  threads: (Thread | null)[];
  cut_stops: CutStops;
};

export type Warning = { level: "error" | "warning" | "info"; code: string; message: string };

export type ExportReport = { stops_added: number; warnings: QualityCheck[]; fabric_advice?: string };
