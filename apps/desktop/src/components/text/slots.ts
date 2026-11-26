/** What each part of the lettering panel is given (components/TextPanel.tsx shows them in order:
 *  LayoutControls, StyleControls, ExtrasControls; their …More parts under More options). */
import type { LayoutItemInfo, TextItem } from "../../design/types";

export type TextSlotProps = { item: TextItem; info: LayoutItemInfo };

/** A LUDD stitch font: its letters are ready-made, so Satin look, True satin and Fill don't apply. */
export const isStitchFont = (path: string) => /\.(luddfont|tlfont)$/i.test(path);
