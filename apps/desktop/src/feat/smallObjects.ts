/**
 * Buttonholes and eyelets (P7-A5): the engine makes ordinary shapes from a few sizes, and they're
 * added in the middle of the hoop as one group, selected, in one undo step. The sizes used are
 * kept for next time.
 *
 * cmd/lines.ts imports this module: nothing here may call actions.ts while it loads.
 */
import { commit, currentLayout, engine, info, newProject } from "../actions";
import { addObject, newId } from "../design/layout";
import type { ObjectItem } from "../design/types";
import { loadPrefs, savePrefs } from "../prefs";
import { useStore } from "../store";

export type SmallDialog = "buttonhole" | "eyelet";
export type ButtonholeSizes = { style: "bar" | "round"; length_mm: number; width_mm: number; cut_gap_mm: number; angle_deg: number };
export type EyeletSizes = { hole_mm: number; ring_mm: number };

/** The standard sizes (the engine's own defaults). */
export const BUTTONHOLE: ButtonholeSizes = { style: "bar", length_mm: 16, width_mm: 5, cut_gap_mm: 1, angle_deg: 0 };
export const EYELET: EyeletSizes = { hole_mm: 4, ring_mm: 1.6 };

export const openButtonhole = (): void => useStore.getState().setDialog("buttonhole");
export const openEyelet = (): void => useStore.getState().setDialog("eyelet");

/** The sizes used last in a dialog, over the standard ones (a value of the wrong kind is ignored). */
export function lastSizes<T extends Record<string, number | string>>(dialog: SmallDialog, standard: T): T {
  const saved = loadPrefs().smallObjects?.[dialog] ?? {};
  return Object.fromEntries(Object.entries(standard).map(([k, v]) => [k, typeof saved[k] === typeof v ? saved[k] : v])) as T;
}

type Made = { objects: Pick<ObjectItem, "kind" | "geometry" | "params" | "name">[]; warnings: string[] };

/** Ask the engine for the shapes and add them. The engine's refusal is thrown; false means nothing
 *  was added. `wanted` is asked once they arrive: the dialog may have been closed meanwhile. */
export async function addSmallObject(dialog: SmallDialog, sizes: ButtonholeSizes | EyeletSizes, wanted: () => boolean = () => true): Promise<boolean> {
  const params = { ...sizes, at: [0, 0] }; // the middle of the hoop
  const made = dialog === "buttonhole" ? await engine().call<Made>("shape.buttonhole", params) : await engine().call<Made>("shape.eyelet", params);
  if (!wanted()) return false;
  if (!useStore.getState().history.present) {
    await newProject(); // nothing to lose, so it asks nothing
    useStore.getState().notify(null);
  }
  const { drawThread } = useStore.getState();
  const group = newId();
  const ids: string[] = [];
  let layout = currentLayout()!;
  for (const o of made.objects) {
    const added = addObject(layout, { ...o, thread: drawThread, group } as Omit<ObjectItem, "id" | "transform" | "threads" | "ops">);
    layout = added.layout;
    ids.push(added.id);
  }
  if (!(await commit(layout))) return false;
  useStore.getState().setTool("select");
  useStore.getState().setSelection(ids[0], ids.slice(1));
  savePrefs({ smallObjects: { ...loadPrefs().smallObjects, [dialog]: { ...sizes } } });
  if (made.warnings.length) info(made.warnings.join(" "));
  return true;
}
