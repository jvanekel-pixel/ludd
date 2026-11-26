/** "Placement guides…" (text.placement): where a design goes on common things, and a printed
 *  placement sheet for each. Nothing in the design changes. */
import { diagramSvg, formatMeasure, PLACEMENT_NOTE, PLACEMENTS } from "../design/placements";
import { printPlacement } from "../print";
import { useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const close = () => useStore.getState().setDialog(null);

export function PlacementDialog() {
  const ref = useModal(true);
  const hasDesign = useStore((s) => s.design !== null);
  return (
    <dialog ref={ref} className="modal" onClose={close} aria-labelledby="placement-title">
      <h2 id="placement-title">Placement guides</h2>
      <p className="hint">
        Where a design usually goes on common things. A placement sheet has the measurements and a crosshair
        {hasDesign ? ", with your design at real size" : ""}. Nothing in your design changes.
      </p>
      <ul style={{ listStyle: "none", margin: "0 0 0.75rem", padding: 0 }}>
        {PLACEMENTS.map((p) => (
          <li key={p.id} data-placement={p.id} style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", borderTop: "1px solid var(--line)", padding: "0.6rem 0" }}>
            <span aria-hidden="true" style={{ flex: "0 0 120px" }} dangerouslySetInnerHTML={{ __html: diagramSvg(p) }} />
            <div style={{ flex: "1 1 240px" }}>
              <h3 style={{ margin: "0 0 0.25rem" }}>{p.name}</h3>
              <p style={{ margin: "0 0 0.25rem" }}>{p.where}</p>
              <ul style={{ margin: "0 0 0.25rem", paddingLeft: "1.1rem" }}>
                {p.measures.map((m) => (
                  <li key={m.label}>
                    {m.label}: <strong>{formatMeasure(m)}</strong>
                  </li>
                ))}
              </ul>
              {p.tip && <p style={{ margin: "0 0 0.25rem", color: "var(--muted)" }}>{p.tip}</p>}
              <p style={{ margin: "0 0 0.35rem", color: "var(--muted)", fontSize: 12 }}>{PLACEMENT_NOTE}</p>
              <button onClick={() => printPlacement(p)} aria-label={`Print a placement sheet: ${p.name}`}>
                Print a placement sheet
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="actions">
        <button onClick={close}>Close</button>
      </div>
    </dialog>
  );
}
