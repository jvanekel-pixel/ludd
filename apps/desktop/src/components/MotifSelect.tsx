/** The motif a motif line or a motif fill repeats. */
import { setObjectParams } from "../actions";
import { MOTIF_DEFS } from "../design/lineStyles";
import type { ObjectItem } from "../design/types";
import { Row } from "./Accordion";

export function MotifSelect({ item }: { item: ObjectItem }) {
  const motif = (item.params as { motif?: string }).motif ?? "wave";
  return (
    <Row label="Motif">
      <select value={motif} onChange={(e) => setObjectParams(item.id, { motif: e.target.value })} aria-label="Motif">
        {MOTIF_DEFS.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
          </option>
        ))}
      </select>
    </Row>
  );
}
