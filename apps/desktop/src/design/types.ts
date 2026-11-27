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
  /** Layouts only: each branch as sewn (shapes sewn as one path). */
  branches?: BranchInfo[];
  warnings?: Warning[];
};

/** One branch as it was sewn: its members in order, its first and last stitch (mm), the travel
 *  hidden under later stitching and how many times the thread had to be cut. */
export type BranchInfo = { id: string; items: string[]; start: [number, number]; end: [number, number]; hidden_mm: number; cuts: number };

export type LayoutItemInfo = {
  id: string;
  name: string;
  kind: "file" | ObjectKind | "text";
  center_mm: [number, number];
  bounds_mm: [number, number, number, number] | null;
  source_size_mm: [number, number] | null;
  /** Lettering: each letter part, how it's stitched ("satin" look or "fill"), its outline and
   *  where it starts and ends (mm, as shown), and which letter, line and color run it is. */
  letters?: LetterPart[];
  /** Lettering: its color runs in sewing order (the item's color blocks, by number). */
  runs?: TextRun[];
};

export type LetterPart = {
  index: number;
  kind: string;
  look: string;
  start: [number, number];
  end: [number, number];
  ring: [number, number][];
  /** Which letter it is, from 0 for the first character that draws something. */
  letter: number;
  /** Which line of the text, from 0. */
  line: number;
  /** Which color run of the item sews it. */
  run: number;
};

/** A run of a text's parts sewn in one thread: its letters, or its shadow, outline or frame.
 *  `slots`: the text's color slots an Order & colors change of the whole run goes to (`threads`
 *  on the item); none when the change has to go to its letters one by one. */
export type TextRun = { run: number; what: "letters" | "shadow" | "outline" | "frame"; letters: number[]; slots: number[] };

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
  /** Stitch editing: single stitches deleted, by their index in the file. */
  | { op: "delete_stitches"; indices: number[] }
  /** Stitch editing: a stitch dragged (mm, on the design). */
  /** `local`: the move is in the design's own frame (turns and resizes with it). Older projects'
   *  moves have no `local` and are a fixed shift on the hoop. */
  | { op: "move_stitch"; index: number; dx_mm: number; dy_mm: number; local?: boolean }
  /** Stitch editing: several stitches dragged together (one op per drag). */
  | { op: "move_stitches"; indices: number[]; dx_mm: number; dy_mm: number; local?: boolean }
  /** `n`: for drawn shapes and lettering, how many records the item had when the stop or trim was
   *  added; if the shape changes, that place no longer exists and the engine leaves it out. */
  | { op: "insert"; after: number; command: "stop" | "trim"; n?: number }
  | { op: "jumps_to_trims"; min_mm: number }
  /** Repairs on a stitch file, applied when it's drawn or saved (the file never changes). An item
   *  holds at most one of each, written in the order rebuild, filter_small, declump,
   *  density_limit, remove_hidden (feat/repair/steps.ts). */
  | { op: "filter_small"; min_mm: number }
  | { op: "declump"; max_hits?: number }
  /** Uses the layout's fabric. */
  | { op: "density_limit" }
  /** At the item's current size. */
  | { op: "rebuild" }
  | { op: "remove_hidden"; keep_mm?: number }
  /** Stitch editing: a stitch added after stitch `after`, numbered `index` (one past the highest
   *  number in use on this item), at (x_mm, y_mm) in the file's frame, or else halfway to the next. */
  | { op: "insert_stitch"; after: number; index: number; x_mm?: number; y_mm?: number }
  /** The move after stitch `after` becomes a jump. */
  | { op: "insert_jump"; after: number }
  /** Lock stitches on both sides of the jump after stitch `after`. */
  | { op: "lock_jump"; after: number };

/** A stitch file placed in the layout. */
export type FileItem = {
  id: string;
  kind?: "file";
  path: string;
  /** Your own name for it (Sewing order); the file's name if unset. */
  name?: string;
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
/** A satin column clicked side by side (rung by rung): what older projects have. */
export type SatinColumn = { rail_a: PathNode[]; rail_b: PathNode[] };
/** A satin ribbon: a centre line and a width (what the Satin tool draws). */
export type SatinRibbon = { nodes: PathNode[]; width_mm: number; closed?: boolean };
export type SatinGeometry = SatinColumn | SatinRibbon;
/** `carve` (fills only): lines carved into the fill, which every row drops a needle on, so they show
 *  as grooves. Open paths; they never change the shape's size. */
export type FillGeometry = { outline: PathNode[]; holes?: PathNode[][]; carve?: PathNode[][] };

export type Motif = "wave" | "zigzag" | "scallop" | "blanket" | "leaf";
/** A built-in motif, or one of your own (its repeat travels with the shape in `motif_unit`). */
export type MotifId = Motif | `user:${string}`;
/** How a shape's lock stitches are shaped, at its start and end. */
export type TieStyle = "standard" | "triangle" | "backtack";
export type RunParams = {
  style?: "single" | "triple" | "bean" | "motif" | "backstitch" | "stem" | "candlewick" | "redwork" | "knots";
  stitch_mm?: number;
  /** style "motif": the pattern repeated along the line, how long each repeat is and how wide. */
  motif?: MotifId;
  motif_mm?: number;
  motif_width_mm?: number;
  /** One repeat of your own motif: [along 0..1, across] (same scale both ways). */
  motif_unit?: [number, number][];
  /** style "motif": which side of the line it sits on, seen walking the way it was drawn ("center"). */
  motif_side?: "center" | "left" | "right";
  /** style "stem": how wide the rope is, 0.3 to 2.5 mm (0.8). */
  stem_width_mm?: number;
  /** styles "candlewick" and "knots": how big each knot is, 1 to 3 mm (1.6). */
  knot_mm?: number;
  /** style "candlewick": how far apart the knots are, 2 to 15 mm (4). */
  knot_gap_mm?: number;
  /** "Hand-sewn look", 0 to 100%: stitches a little irregular, the same way every time. */
  hand_pct?: number;
  tie_in?: boolean;
  tie_off?: boolean;
  tie_style?: TieStyle;
};
export type SatinParams = {
  spacing_mm?: number;
  pull_comp_mm?: number;
  underlay?: ("center" | "edge" | "zigzag")[];
  /** "Hand-sewn look", 0 to 100%. */
  hand_pct?: number;
  /** Push compensation ("End trim"), not built yet. */
  push_comp_mm?: number;
  tie_in?: boolean;
  tie_off?: boolean;
  tie_style?: TieStyle;
};
export type FillPattern =
  | "tatami"
  | "gradient"
  | "wave"
  | "contour"
  | "stipple"
  | "cross"
  | "spiral"
  | "blend"
  | "motif"
  | "maze"
  | "ripple"
  | "mesh"
  | "blackwork";
/** How the needle points of neighboring rows line up. */
export type Weave = "standard" | "brick" | "twill" | "smooth" | "random";
/** Which row ends are feathered: left and right are as the rows run at angle 0. */
export type Feather = "none" | "left" | "right" | "both";
export type FillParams = {
  pattern?: FillPattern;
  /** gradient: row spacing at the sparse end. */
  gradient_to_mm?: number;
  wave_mm?: number;
  wave_length_mm?: number;
  stipple_mm?: number;
  cross_mm?: number;
  spiral_mm?: number;
  /** Push compensation ("End trim"), not built yet. */
  push_comp_mm?: number;
  weave?: Weave;
  feather?: Feather;
  /** How far in a feathered row end can be pulled, 0.5 to 6 mm (2). */
  feather_mm?: number;
  /** "Hand-sewn look", 0 to 100%. */
  hand_pct?: number;
  /** blend: the colors after the shape's own, one to three. */
  blend?: Thread[];
  /** blend: -1 to 1 (0): which color takes more of the shape. */
  blend_balance?: number;
  /** blend: the colors run the other way across the rows (set when turning or mirroring the shape
   *  turns its rows round, so the colors stay where they were on it). */
  blend_flip?: boolean;
  /** Turning fills: two or more direction lines the rows follow (mm, like the shape's points). */
  angle_lines?: [[number, number], [number, number]][];
  /** motif fill: which motif, its repeat, height, row gap and the shift of every other row. */
  motif?: MotifId;
  motif_mm?: number;
  motif_width_mm?: number;
  motif_gap_mm?: number;
  motif_stagger?: number;
  motif_unit?: [number, number][];
  maze_mm?: number;
  ripple_mm?: number;
  /** ripple: where the rings spread from (mm, like the shape's points); unset, the middle. */
  ripple_center?: [number, number];
  mesh_mm?: number;
  mesh_cross_deg?: number;
  /** blackwork: the size of one cell of the lattice, 3 to 12 mm (5), and which lattice ("diamonds"). */
  blackwork_mm?: number;
  blackwork_lattice?: "diamonds" | "grid" | "honeycomb" | "crossed";
  angle_deg?: number;
  /** Where its purple direction dots were left (they set angle_deg). */
  angle_line?: [[number, number], [number, number]];
  /** Where it starts (green dot) and ends (red dot), mm. */
  start_mm?: [number, number];
  end_mm?: [number, number];
  spacing_mm?: number;
  stitch_mm?: number;
  pull_comp_mm?: number;
  underlay?: ("edge" | "tatami")[];
  tie_in?: boolean;
  tie_off?: boolean;
  tie_style?: TieStyle;
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
  /** Shapes with the same branch id are sewn as one path, with one start and one end. */
  branch?: string;
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

/** `made_of: "stitches"`: a stitch font whose letters are stitches (made from letter files). */
export type FontRef = { path: string; index: number; family: string; style: string; made_of?: "stitches" };
export type FontInfo = { family: string; style: string; path: string; index: number; kind: "outline" | "stitch"; made_of?: "stitches" };

export type TextShape = {
  type: "line" | "arc_up" | "arc_down" | "circle" | "path";
  radius_mm?: number;
  /** type "path": the line the letters follow, in the text's own frame (mm from its position). */
  nodes?: PathNode[];
  closed?: boolean;
};

export type Envelope = "bulge" | "pinch" | "pennant_right" | "pennant_left" | "wave" | "arch_top" | "arch_bottom";
export type OrnamentId = "circle" | "double_circle" | "diamond" | "square" | "scallop_circle" | "laurel";
export type MonogramStyle = "classic" | "block" | "stacked";

/** A change to one letter: moved, turned, resized (1 = as it is), recolored or sewn at another angle. */
export type LetterEdit = { dx_mm?: number; dy_mm?: number; rotate?: number; scale?: number; thread?: Thread; angle_deg?: number };

/** Lettering: stitched from a font each time, so it stays editable and keeps its density at any size. */
export type TextItem = {
  id: string;
  kind: "text";
  name?: string;
  /** May hold line breaks ("\n"). */
  text: string;
  font: FontRef;
  /** Height of capital letters, mm. */
  size_mm: number;
  spacing_mm: number;
  /** "columns" is True satin: each stroke its own satin column. */
  style: "satin" | "columns" | "fill";
  shape: TextShape;
  monogram: boolean;
  /** Where letters start and end, chosen with their dots (by letter part, in the text's own frame). */
  letters?: Record<string, { start_mm?: [number, number]; end_mm?: [number, number] }>;
  /** Several lines: how they line up (default "center") and how far apart (x letter height, 1.3). */
  align?: "left" | "center" | "right";
  line_spacing?: number;
  /** -30 to 30 degrees; positive leans right. */
  slant_deg?: number;
  envelope?: { type: Envelope; amount: number };
  /** Letters stacked top to bottom. */
  vertical?: boolean;
  /** Changes to single letters, by letter number (0 = the first character that draws something). */
  letter_edits?: Record<string, LetterEdit>;
  monogram_style?: MonogramStyle;
  /** A frame round a monogram; no thread: the text's. */
  ornament?: { id: OrnamentId; margin_mm?: number; thread?: Thread };
  shadow?: { dx_mm: number; dy_mm: number; thread: Thread };
  outline?: { gap_mm: number; width_mm: number; style: "satin" | "run"; thread: Thread };
  /** Name templates: this text is filled from a list; `bind` is the column it takes ("name"). */
  placeholder?: boolean;
  bind?: string;
  /** A placeholder's long names shrink to this width. */
  fit_width_mm?: number;
  locked?: boolean;
  group?: string;
  thread: Thread;
  transform: Transform;
  threads: (Thread | null)[];
  ops: LayoutOp[];
};

export type LayoutItem = FileItem | ObjectItem | TextItem;

export const isText = (it: LayoutItem): it is TextItem => it.kind === "text";

export type SatinItem = Extract<ObjectItem, { kind: "satin" }>;

/** A satin drawn as a ribbon (centre line + width), not as two clicked sides. */
export const isRibbon = (o: ObjectItem): o is SatinItem & { geometry: SatinRibbon } => o.kind === "satin" && "nodes" in o.geometry;

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
  /** `fit_mm`: the hoop it was turned on for; the box comes in closer (down to 2 mm) to fit it. */
  basting: { enabled: boolean; margin_mm: number; fit_mm?: [number, number] };
  /** "Trim jumps longer than" this (mm), for every design in the layout, including ones added later. */
  jumps_to_trims?: number | null;
  /** What it will be stitched on (a fabric id); sets density, pull compensation and underlay. */
  fabric?: string;
  /** A light grid of stitches under the design, for towels and fleece. */
  knockdown?: { enabled: boolean; margin_mm: number; /** Its thread (one matching the fabric). */ thread?: Thread };
  /** Moves between same-thread shapes run under later stitching where they can (fewer jumps and trims). */
  travel_under?: boolean;
  /** "Allow for push at the ends", not built yet. */
  push_comp?: boolean;
  /** "Don't sew what's hidden under shapes on top" (drawn fills), and how far under their edge
   *  to keep sewing. */
  remove_overlap?: { enabled: boolean; keep_mm: number };
  /** Each branch's start and end dots moved by hand, mm on the hoop (by branch id). */
  branches?: Record<string, { start_mm?: [number, number]; end_mm?: [number, number] }>;
  /** Saved sets of thread colors (colorways), to switch between. */
  colorways?: Colorway[];
  /** Guide lines dragged from the rulers (mm). */
  guides?: Guide[];
};

/** A saved set of thread colors: each item's thread (and color changes), by item id. */
export type Colorway = { name: string; items: Record<string, { thread?: Thread; threads: (Thread | null)[] }> };

/** A guide line across the design area: vertical at x, or horizontal at y (mm). */
export type Guide = { axis: "x" | "y"; at: number };

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
  /** Top sewing speed (stitches per minute), for the time estimate; null = LUDD assumes 600. */
  speed_spm?: number | null;
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
