/** Monograms here; frames, a shadow and an outline (the shadow and outline under More options). */
import { setText } from "../../actions";
import type { TextSlotProps } from "./slots";

export function ExtrasControls({ item }: TextSlotProps) {
  return (
    <label className="check">
      <input type="checkbox" checked={item.monogram} onChange={(e) => setText(item.id, { monogram: e.target.checked, text: e.target.checked ? (item.text.replace(/\s/g, "").slice(0, 3).padEnd(3, "A")) : item.text })} />
      Monogram (three letters, big middle initial)
    </label>
  );
}

export function ExtrasMore(_: TextSlotProps) {
  return null;
}
