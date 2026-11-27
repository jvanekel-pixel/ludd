/**
 * Right-click menus: what you can do with the thing under the mouse (a shape, a picture, a row in
 * a list, the empty canvas), each with its shortcut, so the commands can be found by right-clicking
 * and learned from there. The menus are lists of commands from the registry (they act on the
 * selection: right-clicking a thing selects it first), plus a few row-only items.
 */
import { create } from "zustand";
import type { MenuItem } from "./components/Menu";
import { command } from "./actions";
import type { LayoutItem } from "./design/types";
import { removeCarves } from "./feat/carve";
import { useStore } from "./store";

/** A row-only item (not a command): a label and what it does. */
export type LocalItem = { label: string; run: () => void; enabled?: boolean; hint?: string };
export type ContextItem = MenuItem | LocalItem;

type State = {
  menu: { x: number; y: number; items: ContextItem[]; title?: string } | null;
  /** A drawn shape or text whose thread is being picked from a menu (or Alt+T). */
  threadFor: string | null;
};

export const useContextMenu = create<State>(() => ({ menu: null, threadFor: null }));

/** Open a menu at the mouse. Items that can't be used right now are greyed out; a menu with
 *  none usable, or none at all, isn't shown. */
export function openContextMenu(e: { clientX: number; clientY: number; preventDefault?: () => void }, items: ContextItem[], title?: string) {
  e.preventDefault?.();
  const tidy = tidySeparators(items.filter((it) => it === "separator" || isLocal(it) || commandExists(it.id)));
  if (!tidy.some((it) => it !== "separator")) return;
  useContextMenu.setState({ menu: { x: e.clientX, y: e.clientY, items: tidy, title } });
}

export function closeContextMenu() {
  if (useContextMenu.getState().menu) useContextMenu.setState({ menu: null });
}

export const isLocal = (it: ContextItem): it is LocalItem => typeof it === "object" && "run" in it;

const commandExists = (id: string) => !!command(id);

/** No separator first, last or twice in a row. */
export function tidySeparators(items: ContextItem[]): ContextItem[] {
  const out: ContextItem[] = [];
  for (const it of items) {
    if (it === "separator" && (out.length === 0 || out[out.length - 1] === "separator")) continue;
    out.push(it);
  }
  while (out[out.length - 1] === "separator") out.pop();
  return out;
}

const SEP = "separator" as const;
const c = (id: string, label?: string): MenuItem => ({ id, label });

const EDIT: ContextItem[] = [c("edit.cut"), c("edit.copy"), c("edit.paste"), c("arrange.duplicate"), c("arrange.delete")];
const ORDER: ContextItem[] = [c("arrange.first"), c("arrange.earlier"), c("arrange.later"), c("arrange.last")];
const PLACE: ContextItem[] = [c("arrange.rotateCw"), c("arrange.rotateCcw"), c("arrange.mirrorX"), c("arrange.mirrorY"), c("arrange.centre"), c("arrange.repeat")];

/** The menu for a design item (a drawn shape, text or stitch file), given what's selected. */
export function itemMenu(item: LayoutItem | undefined, several: boolean): ContextItem[] {
  const kind = item?.kind;
  const shape = kind === "fill" || kind === "applique" || kind === "satin" || kind === "run";
  const fill = kind === "fill" || kind === "applique";
  const together = several
    ? [c("arrange.group"), c("arrange.ungroup"), c("object.merge"), c("text.onLine"), c("layout.branch", "Branch: sew as one path"), c("layout.unbranch", "Take out of the branch")]
    : [];
  return [
    ...(shape || kind === "text" ? [c("object.thread")] : []),
    ...(kind === "text"
      ? [c("text.edit"), c("text.letters"), c("text.resetLetters"), c("text.names"), c("text.saveTemplate"), c("text.resetEnds"), c("text.toShapes")]
      : []),
    ...(kind === "file" ? [c("edit.stitches")] : []),
    SEP,
    ...EDIT,
    SEP,
    ...(shape && !several ? [c("draw.continue", "Add points")] : []),
    ...(fill ? [c("object.hole"), c("object.angle")] : []),
    ...(kind === "fill" && !several ? [c("object.addAngle"), c("object.carve"), ...carveItems(item)] : []),
    ...(fill && several ? [c("object.cutOut")] : []),
    ...(shape ? [c("tool.knife")] : []),
    ...(kind === "satin" ? [c("satin.otherWay")] : []),
    ...(shape ? [c("object.border"), c("object.offset")] : []),
    ...together,
    SEP,
    ...ORDER,
    SEP,
    ...PLACE,
    c("arrange.pin"),
    ...(several ? [] : [c("arrange.rename")]),
    SEP,
    c("view.zoomSelected"),
    ...(shape && !several ? [c("presets.open", "Stitch presets…")] : []),
    ...(shape ? [c("ai.advisor")] : []),
  ];
}

/** "Remove carved lines", for a fill that has some. */
export function carveItems(item: LayoutItem | undefined): LocalItem[] {
  if (item?.kind !== "fill" || !item.geometry?.carve?.length) return [];
  const id = item.id;
  return [{ label: "Remove carved lines", run: () => removeCarves(id) }];
}

/** The menu for a picture to trace. */
export function pictureMenu(): ContextItem[] {
  return [
    c("tool.autotrace", "Auto-trace a shape in it"),
    c("autotrace.all", "Auto-digitize the whole picture…"),
    SEP,
    c("arrange.pin", "Pin in place / unpin (clicks go through)"),
    { id: "view.seeThrough", label: "See-through stitches (all)", checked: useStore.getState().seeThrough },
    { id: "view.pictures", label: "Show pictures (all)", checked: useStore.getState().showPictures },
    SEP,
    c("arrange.delete"),
    c("view.zoomSelected"),
  ];
}

/** The menu for the empty canvas: draw, paste, add, view. */
export function canvasMenu(): ContextItem[] {
  const v = useStore.getState();
  return [
    c("edit.paste"),
    c("edit.selectAll"),
    SEP,
    c("tool.run", "Draw a line"),
    c("tool.satin", "Draw a satin ribbon"),
    c("tool.fill", "Draw a fill"),
    c("tool.text", "Add text"),
    c("shape.rectangle"),
    c("shape.circle"),
    c("shape.star"),
    c("shape.roundedRect"),
    c("shape.ellipse"),
    c("shape.triangle"),
    c("shape.polygon"),
    c("shape.heart"),
    c("file.picture"),
    SEP,
    c("view.fit"),
    c("view.zoomHoop"),
    c("view.zoomActual"),
    SEP,
    { id: "view.grid", checked: v.showGrid },
    { id: "view.hoop", checked: v.showHoop },
    { id: "view.rulers", checked: v.showRulers },
    { id: "view.seeThrough", checked: v.seeThrough },
    { id: "view.realistic", checked: v.realistic },
    c("view.measure"),
  ];
}
