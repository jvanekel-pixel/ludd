import { setFabric, showCheck } from "../actions";
import { DEFAULT_FABRIC } from "../design/layout";
import type { Fabric, QualityCheck, Warning } from "../design/types";
import { selectLayout, useStore } from "../store";

export function fabricAdvice(f: Fabric): string {
  return `Stabilizer: ${f.stabilizer}.${f.topping ? ` Topping: ${f.topping}.` : ""}`;
}

/** What the design will be stitched on. It sets density, pull compensation and underlay
 *  for drawn shapes (anything set by hand on a shape wins) and says which stabilizer to use. */
export function FabricPicker() {
  const fabrics = useStore((s) => s.fabrics);
  const layout = useStore(selectLayout);
  const engine = useStore((s) => s.engine);
  if (!layout || !fabrics.length) return null;
  const current = fabrics.find((f) => f.id === (layout.fabric ?? DEFAULT_FABRIC)) ?? fabrics[0];
  return (
    <div className="fabric-picker">
      <label>
        <span>Stitching on</span>
        <select value={current.id} disabled={!engine} onChange={(e) => setFabric(e.target.value)} title={current.examples}>
          {fabrics.map((f) => (
            <option key={f.id} value={f.id} title={f.examples}>
              {f.name}
            </option>
          ))}
        </select>
      </label>
      <p className="hint">{fabricAdvice(current)}</p>
    </div>
  );
}

/** Problems worth fixing before stitching: each says why it matters and what to do. */
export function Checks() {
  const design = useStore((s) => s.design);
  const checks = useStore((s) => s.checks);
  const showDensity = useStore((s) => s.showDensity);
  const toggleDensity = useStore((s) => s.toggleDensity);
  if (!design) return null;
  const items: (Warning & Partial<QualityCheck>)[] = [
    ...(design.warnings ?? []).filter((w) => w.level !== "info"),
    ...(checks?.checks ?? []),
  ];
  return (
    <section className="checks" aria-label="Checks">
      <div className="checks-head">
        <h3>{items.length ? `Check before stitching (${items.length})` : "Checks"}</h3>
        <label className="check" title="Color the design by how much thread is in each spot (Shift+D)">
          <input type="checkbox" checked={showDensity} onChange={toggleDensity} /> Density map
        </label>
      </div>
      {items.length === 0 && checks && <p className="hint ok">✓ Nothing to fix: no thick spots, gaps or loose stitches found.</p>}
      <ul>
        {items.map((c) => (
          <li key={c.code} className={`check-${c.level}`}>
            <p className="what">
              {c.level === "info" ? "ℹ️" : "⚠️"} {c.message}
            </p>
            {c.why && <p className="why">{c.why}</p>}
            {c.fix && <p className="fix">{c.fix}</p>}
            {(c.at || c.item_id) && (
              <button className="link" onClick={() => showCheck(c)}>
                Show me
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
