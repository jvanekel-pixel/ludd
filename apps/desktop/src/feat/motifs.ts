/**
 * Motifs: the built-in ones and your own, kept by the engine in LUDD's data folder (methods
 * motifs.*). A shape that uses one of yours carries a copy of it, so it sews anywhere.
 *
 * cmd/fills.ts imports this module: nothing here may call actions.ts while it loads.
 */
import { open as openDialog, save as saveDialog } from "@tauri-apps/plugin-dialog";
import { create } from "zustand";
import { engine } from "../actions";
import { fillPatternDef } from "../design/fillPatterns";
import { MOTIF_FIELDS } from "../design/lineStyles";
import type { ObjectItem, PathNode } from "../design/types";
import { isTauri } from "../engine/sidecar";
import { nameFileStem } from "../features";
import { useStore } from "../store";

export type MotifEntry = { id: string; name: string; builtin: boolean; unit: [number, number][] };
type Saved = { id: string; name: string; unit: [number, number][] };
type Line = Extract<ObjectItem, { kind: "run" }>;

/** The motifs the engine lists, built-ins first (null until first asked). */
export const useMotifs = create<{ list: MotifEntry[] | null }>(() => ({ list: null }));

/** Alt+Shift+M: the Motifs window. */
export const openMotifs = () => useStore.getState().setDialog("motifs");

let asked = 0;

/** Ask the engine for the motifs again (only the newest answer counts). Nothing without an engine. */
export async function loadMotifs(): Promise<void> {
  const client = useStore.getState().engine;
  if (!client) return;
  const mine = ++asked;
  const list = await client.call<MotifEntry[]>("motifs.list");
  if (mine === asked && Array.isArray(list)) useMotifs.setState({ list });
}

/** The line a motif can be made from: one drawn line selected, and nothing half drawn. */
export function selectedLine(s = useStore.getState()): Line | null {
  if (!s.selectedId || s.extraIds.length || s.pen) return null;
  const it = s.history.present?.layout.items.find((x) => x.id === s.selectedId);
  return it?.kind === "run" ? it : null;
}

/** The line's points as it's sewn: resized and mirrored as the handles left it. (Turning and
 *  moving it make no difference to a motif.) */
export function lineNodes(line: Line): PathNode[] {
  const t = line.transform;
  const sx = (t.flip_x ? -1 : 1) * t.scale_x;
  const sy = (t.flip_y ? -1 : 1) * t.scale_y;
  return line.geometry.nodes.map(([x, y, kind]) => [x * sx + 0, y * sy + 0, kind]); // (+ 0: no -0)
}

export async function saveLineMotif(line: Line, name: string): Promise<Saved> {
  const saved = await engine().call<Saved>("motifs.save", { name, nodes: lineNodes(line), closed: !!line.geometry.closed });
  await loadMotifs();
  return saved;
}

export async function deleteMotif(id: string): Promise<void> {
  await engine().call("motifs.delete", { id });
  await loadMotifs();
}

/** Save a motif as a file you pick (typed in the browser preview). Its path, or null if you didn't. */
export async function exportMotif(motif: MotifEntry): Promise<string | null> {
  const suggested = `${nameFileStem(motif.name)}.json`;
  const dest = isTauri()
    ? await saveDialog({ title: "Export a motif", defaultPath: suggested, filters: [{ name: "LUDD motif", extensions: ["json"] }] })
    : window.prompt("Save the motif file as (a full path)", suggested) || null;
  if (!dest) return null;
  return (await engine().call<{ path: string }>("motifs.export", { id: motif.id, dest })).path;
}

/** Add a motif from a file you pick. Null if you didn't pick one. */
export async function importMotif(): Promise<Saved | null> {
  const path = isTauri()
    ? await openDialog({
        title: "Import a motif",
        multiple: false,
        directory: false,
        filters: [
          { name: "LUDD motif", extensions: ["json", "JSON"] },
          { name: "All files", extensions: ["*"] },
        ],
      })
    : window.prompt("Motif file to import (a full path)") || null;
  if (typeof path !== "string") return null;
  const added = await engine().call<Saved>("motifs.import", { path });
  await loadMotifs();
  return added;
}

// ---------------------------------------------------------------- choosing one

/** The ranges of Repeat and Width (a motif fill's Height), as the engine takes them. */
const REPEAT_RANGE = [1.5, 20] as const;
const WIDTH_RANGE = [0.5, 10] as const;
/** A motif that goes no further than this across is flat (the engine's FLAT_SPAN). */
const FLAT_SPAN = 1e-4;

const clamp = (v: number, [lo, hi]: readonly [number, number]) => Math.min(hi, Math.max(lo, v));
const hundredths = (v: number) => Math.round(v * 100) / 100;

/** How far across a motif goes, as a share of one repeat. */
export function motifSpan(unit: readonly (readonly [number, number])[]): number {
  const vs = unit.map(([, v]) => v);
  return vs.length ? Math.max(...vs) - Math.min(...vs) : 0;
}

/** The Width (and, only if the Width's range holds it back, a new Repeat) that sews a motif of
 *  your own with the proportions you drew it: Width = Repeat × span. The engine sews yours as wide
 *  as Width says (digitize/lines sewn_unit). A flat one keeps the sizes it has. */
export function drawnSize(span: number, repeat: number): { motif_width_mm?: number; motif_mm?: number } {
  if (!(span > FLAT_SPAN)) return {};
  let r = clamp(repeat, REPEAT_RANGE);
  let width = r * span;
  if (width < WIDTH_RANGE[0] || width > WIDTH_RANGE[1]) {
    r = clamp(clamp(width, WIDTH_RANGE) / span, REPEAT_RANGE);
    width = clamp(r * span, WIDTH_RANGE);
  }
  const size = { motif_width_mm: hundredths(width) };
  return hundredths(r) === repeat ? size : { ...size, motif_mm: hundredths(r) };
}

/** The settings choosing a motif gives a motif line or a motif fill. A built-in needs no copy;
 *  yours travels with the shape, sized to its drawn proportions at the shape's Repeat. */
export function motifPatch(motif: Pick<MotifEntry, "id" | "builtin" | "unit">, item: ObjectItem): Record<string, unknown> {
  if (motif.builtin) return { motif: motif.id, motif_unit: undefined };
  const fields = item.kind === "fill" ? fillPatternDef("motif").fields : MOTIF_FIELDS;
  const repeat = (item.params as { motif_mm?: number }).motif_mm ?? fields.find((f) => f.key === "motif_mm")!.def;
  return { motif: motif.id, motif_unit: motif.unit.map(([u, v]) => [u, v]), ...drawnSize(motifSpan(motif.unit), repeat) };
}

/** Whether a shape's copy of a motif is the same shape as one in the list. */
export const sameUnit = (a: readonly (readonly [number, number])[], b: readonly (readonly [number, number])[]) =>
  a.length === b.length && a.every(([u, v], i) => Math.abs(u - b[i][0]) < 1e-9 && Math.abs(v - b[i][1]) < 1e-9);
