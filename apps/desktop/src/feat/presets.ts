/**
 * Stitch presets (P7-C4, Alt+P): a shape's stitch settings under a name, kept by the engine in
 * LUDD's data folder (presets.*), with a few built in. Applying one gives each selected shape of
 * its kind exactly its settings; what belongs to a shape (its direction and angle lines, where it
 * starts and ends and so on) stays its own.
 *
 * cmd/draw.ts imports this module: nothing here may call actions.ts while it loads.
 */
import { open as openDialog, save as saveDialog } from "@tauri-apps/plugin-dialog";
import { create } from "zustand";
import { commit, currentLayout, engine } from "../actions";
import { FILL_PATTERN_DEFS, withoutDeadCrossHatch } from "../design/fillPatterns";
import { LINE_STYLE_DEFS } from "../design/lineStyles";
import { isObject, isRibbon, type ObjectItem, type ObjectKind, type Transform } from "../design/types";
import { isTauri } from "../engine/sidecar";
import { nameFileStem } from "../features";
import { loadPrefs, savePrefs } from "../prefs";
import { selectedIds, useStore } from "../store";

export type Preset = {
  id: string;
  name: string;
  kind: ObjectKind;
  params: Record<string, unknown>;
  width_mm: number | null;
  note: string | null;
  builtin: boolean;
};

/** Settings that belong to one shape, never to a preset (the engine leaves them out too). */
export const ONE_SHAPE = ["angle_deg", "reverse", "start_mm", "end_mm", "angle_line", "angle_lines", "ripple_center", "blend_flip", "push_comp_mm"];

export const KIND_PLURAL: Record<ObjectKind, string> = { run: "lines", satin: "satins", fill: "fills", applique: "appliques" };
const KIND_WORD: Record<ObjectKind, string> = { run: "Line", satin: "Satin", fill: "Fill", applique: "Applique" };

/** The presets the engine lists, built-ins first (null until first asked). */
export const usePresets = create<{ list: Preset[] | null }>(() => ({ list: null }));

/** Alt+P: the Stitch presets window. */
export const openPresets = (): void => useStore.getState().setDialog("presets");

let asked = 0;

/** Ask the engine for the presets again (only the newest answer counts). Nothing without an engine. */
export async function loadPresets(): Promise<void> {
  const client = useStore.getState().engine;
  if (!client) return;
  const mine = ++asked;
  const list = await client.call<Preset[]>("presets.list");
  if (mine === asked && Array.isArray(list)) usePresets.setState({ list });
}

/** How much wider than drawn a ribbon sews (the handles' resizing, as the engine applies it). */
const widening = (t: Transform) => Math.sqrt(Math.abs(t.scale_x * t.scale_y)) || 1;
const round3 = (v: number) => Math.round(v * 1000) / 1000;

/** A shape's settings as a preset: without what belongs to the shape, and a ribbon's width as it
 *  sews (within the widths a ribbon can have). */
export function presetFrom(item: ObjectItem, name: string): { name: string; kind: ObjectKind; params: Record<string, unknown>; width_mm?: number } {
  const params = Object.fromEntries(Object.entries(item.params as Record<string, unknown>).filter(([k, v]) => !ONE_SHAPE.includes(k) && v !== undefined && v !== null));
  const width = isRibbon(item) ? Math.min(12, Math.max(0.5, round3(item.geometry.width_mm * widening(item.transform)))) : undefined;
  return { name, kind: item.kind, params, ...(width !== undefined ? { width_mm: width } : {}) };
}

/** The selected drawn shapes. */
const selectedShapes = (): ObjectItem[] => {
  const ids = selectedIds(useStore.getState());
  return (currentLayout()?.items ?? []).filter((it): it is ObjectItem => isObject(it) && ids.includes(it.id));
};

/** The selected shapes a preset can go on: those of its kind. */
export const targetsOf = (preset: Preset): ObjectItem[] => selectedShapes().filter((o) => o.kind === preset.kind);

/** A shape with exactly a preset's settings (a ribbon with its width too), keeping its own. */
export function withPreset(item: ObjectItem, preset: Preset): ObjectItem {
  const own = Object.fromEntries(Object.entries(item.params as Record<string, unknown>).filter(([k]) => ONE_SHAPE.includes(k)));
  const params = withoutDeadCrossHatch<Record<string, unknown>>({ ...structuredClone(preset.params), ...own });
  if (preset.width_mm && isRibbon(item)) {
    return { ...item, params, geometry: { ...item.geometry, width_mm: round3(preset.width_mm / widening(item.transform)) } } as ObjectItem;
  }
  return { ...item, params } as ObjectItem;
}

/** "Apply to selection": every selected shape of the preset's kind, in one undo step. How many
 *  got it (0: none selected, or the change couldn't be made, and it says why). */
export async function applyPreset(preset: Preset): Promise<number> {
  const layout = currentLayout();
  const ids = new Set(targetsOf(preset).map((o) => o.id));
  if (!layout || !ids.size) return 0;
  const next = { ...layout, items: layout.items.map((it) => (ids.has(it.id) ? withPreset(it as ObjectItem, preset) : it)) };
  return (await commit(next)) ? ids.size : 0;
}

/** "Use for new shapes": new shapes of its kind start with its settings (and ribbon width). */
export function useForNewShapes(preset: Preset): void {
  const all = { ...(loadPrefs().objectDefaults ?? {}) };
  all[preset.kind] = structuredClone(preset.params);
  savePrefs({ objectDefaults: all });
  if (preset.kind === "satin" && preset.width_mm) {
    savePrefs({ satinWidth: preset.width_mm });
    useStore.getState().setSatinWidth(preset.width_mm);
  }
}

/** The one shape "Save current as…" saves: the selected one (the panel's, with several). */
export function currentShape(s = useStore.getState()): ObjectItem | null {
  const it = s.history.present?.layout.items.find((x) => x.id === s.selectedId);
  return it && isObject(it) ? it : null;
}

export async function savePreset(item: ObjectItem, name: string, replace = false): Promise<string> {
  const { id } = await engine().call<{ id: string }>("presets.save", { preset: presetFrom(item, name), replace });
  await loadPresets();
  return id;
}

export async function deletePreset(id: string): Promise<void> {
  await engine().call("presets.delete", { id });
  await loadPresets();
}

const FILTER = { name: "LUDD stitch preset", extensions: ["luddpreset"] };

/** Save a preset as a file you pick (typed in the browser preview). Its path, or null if you didn't. */
export async function exportPreset(preset: Preset): Promise<string | null> {
  const suggested = `${nameFileStem(preset.name)}.luddpreset`;
  const dest = isTauri()
    ? await saveDialog({ title: "Export a stitch preset", defaultPath: suggested, filters: [FILTER] })
    : window.prompt("Save the preset file as (a full path)", suggested) || null;
  if (!dest) return null;
  return (await engine().call<{ path: string }>("presets.export", { id: preset.id, dest })).path;
}

/** Add a preset from a file you pick. Null if you didn't pick one. */
export async function importPreset(): Promise<{ id: string; name: string; kind: ObjectKind } | null> {
  const path = isTauri()
    ? await openDialog({
        title: "Import a stitch preset",
        multiple: false,
        directory: false,
        filters: [FILTER, { name: "All files", extensions: ["*"] }],
      })
    : window.prompt("Preset file to import (a full path)") || null;
  if (typeof path !== "string") return null;
  const added = await engine().call<{ id: string; name: string; kind: ObjectKind }>("presets.import", { path });
  await loadPresets();
  return added;
}

const named = (defs: readonly { id: string; label: string }[], id: string) => defs.find((d) => d.id === id)?.label ?? id.charAt(0).toUpperCase() + id.slice(1);

/** A preset in a few words: its kind and its main settings. */
export function summary(preset: Preset): string {
  const p = preset.params as { style?: string; pattern?: string; stitch_mm?: number; spacing_mm?: number; cover_width_mm?: number; tack?: string };
  const mm = (label: string, v: number | undefined) => (v === undefined ? "" : `${label} ${v} mm`);
  const parts =
    preset.kind === "run"
      ? [named(LINE_STYLE_DEFS, p.style ?? "single"), mm("stitches", p.stitch_mm)]
      : preset.kind === "satin"
        ? [preset.width_mm ? `${preset.width_mm} mm wide` : "", mm("spacing", p.spacing_mm)]
        : preset.kind === "fill"
          ? [named(FILL_PATTERN_DEFS, p.pattern ?? "tatami"), mm("spacing", p.spacing_mm)]
          : [mm("border", p.cover_width_mm), p.tack ? `${p.tack === "run" ? "straight" : "zigzag"} tack-down` : ""];
  return [KIND_WORD[preset.kind], ...parts.filter(Boolean)].join(" · ");
}
