/** The motif a motif line or a motif fill repeats: the built-ins, then your own (My motifs). A
 *  shape sews the copy of your motif it carries, so one this computer doesn't have still shows. */
import { useEffect } from "react";
import { setObjectParams } from "../actions";
import { MOTIF_DEFS } from "../design/lineStyles";
import type { ObjectItem } from "../design/types";
import { loadMotifs, motifPatch, sameUnit, useMotifs, type MotifEntry } from "../feat/motifs";
import { useStore } from "../store";
import { Row } from "./Accordion";
import { Cmd } from "./controls";

/** The option standing for the shape's own motif, when it isn't one of those listed. */
const OWN = "own";

/** "user:my-hill" as words: "My hill". */
const asWords = (id: string) => id.replace(/^user:/, "").replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase());

function ownLabel(motif: string, listed: MotifEntry | undefined, carried: boolean, loaded: boolean): string {
  if (!carried) return `${asWords(motif)} (not found)`;
  if (listed) return `${listed.name} (this shape's own copy)`;
  return loaded ? `${asWords(motif)} (kept in this shape, not in My motifs)` : `${asWords(motif)} (kept in this shape)`;
}

export function MotifSelect({ item }: { item: ObjectItem }) {
  const engine = useStore((s) => s.engine);
  const list = useMotifs((s) => s.list);
  useEffect(() => {
    loadMotifs().catch(() => {}); // the built-ins are offered even so
  }, [engine]);

  const p = item.params as { motif?: string; motif_unit?: [number, number][] };
  const motif = p.motif ?? "wave";
  const mine = list?.filter((m) => !m.builtin) ?? [];
  const listed = mine.find((m) => m.id === motif);
  // The engine sews the copy a shape carries, whatever its name says.
  const own = p.motif_unit ? !listed || !sameUnit(listed.unit, p.motif_unit) : !listed && !MOTIF_DEFS.some((d) => d.id === motif);

  const choose = (id: string) => {
    const entry = mine.find((m) => m.id === id) ?? (MOTIF_DEFS.some((d) => d.id === id) ? { id, builtin: true, unit: [] } : undefined);
    if (entry) setObjectParams(item.id, motifPatch(entry, item));
  };

  return (
    <>
      <Row label="Motif">
        <select value={own ? OWN : motif} onChange={(e) => choose(e.target.value)} aria-label="Motif">
          {own && <option value={OWN}>{ownLabel(motif, listed, !!p.motif_unit, list !== null)}</option>}
          {MOTIF_DEFS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
          {mine.length > 0 && (
            <optgroup label="My motifs">
              {mine.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </Row>
      <Row label="">
        <Cmd id="motif.library" label="My motifs…" />
      </Row>
    </>
  );
}
