import { useEffect, useMemo, useRef, useState } from "react";
import {
  addMyThreads,
  deleteChart,
  getChart,
  importChart,
  matchThreads,
  recolorBlock,
  recolorBlocks,
  removeMyThreads,
} from "../actions";
import type { Chart, ChartThread, Thread, ThreadMatch } from "../design/types";
import { useStore } from "../store";

const MY_THREADS = "my-threads";

/** <dialog> that opens/closes with `open`. */
export function useModal(open: boolean) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);
  return ref;
}

/** Charts that can be matched against: My threads only once it has spools. */
function useMatchableCharts() {
  const charts = useStore((s) => s.charts);
  return useMemo(() => charts.filter((c) => !c.mine || c.count > 0), [charts]);
}

/** Remembers the last chart used across dialogs for this session. */
let lastChartId: string | null = null;

function useChartChoice() {
  const charts = useMatchableCharts();
  const [chartId, setChartId] = useState<string | null>(lastChartId);
  useEffect(() => {
    if (!charts.length) return;
    if (!chartId || !charts.some((c) => c.id === chartId)) {
      // Prefer the user's own spools, then an imported brand, then the machine palettes.
      setChartId((charts.find((c) => c.mine) ?? charts.find((c) => !c.builtin) ?? charts[0]).id);
    }
  }, [charts, chartId]);
  const choose = (id: string) => {
    lastChartId = id;
    setChartId(id);
  };
  return { chartId, choose };
}

function toThread(t: ChartThread, chartBrand: string): Thread {
  return { color: t.color, name: t.name, catalog: t.code, brand: t.brand || chartBrand };
}

function spoolLabel(t: ChartThread) {
  return [t.brand, t.code, t.name].filter(Boolean).join(" ") || t.color;
}

function ChartSelect({ value, onChange }: { value: string | null; onChange: (id: string) => void }) {
  const charts = useMatchableCharts();
  return (
    <select value={value ?? ""} onChange={(e) => onChange(e.target.value)} aria-label="Match against">
      {charts.map((c) => (
        <option key={c.id} value={c.id}>
          {c.mine ? `My threads (${c.count} spools)` : `${c.name} (${c.count})`}
        </option>
      ))}
    </select>
  );
}

/** Swatch grid of a chart's threads. Click picks, or toggles when `selected` is given. */
function ThreadGrid({
  threads,
  onPick,
  selected,
}: {
  threads: ChartThread[];
  onPick: (t: ChartThread) => void;
  selected?: (t: ChartThread) => boolean;
}) {
  return (
    <ul className="thread-grid">
      {threads.map((t) => {
        const on = selected?.(t);
        return (
          <li key={`${t.brand ?? ""}|${t.code}|${t.color}`}>
            <button
              onClick={() => onPick(t)}
              title={spoolLabel(t)}
              aria-pressed={selected ? on : undefined}
              className={on ? "on" : undefined}
            >
              <span className="swatch" style={{ background: t.color }} />
              <span className="code">{t.code}</span>
              <span className="tn">{t.name || t.color}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function useFiltered(threads: ChartThread[] | undefined, query: string) {
  return useMemo(() => {
    if (!threads) return [];
    const q = query.trim().toLowerCase();
    return q
      ? threads.filter((t) => [t.code, t.name, t.brand ?? ""].some((s) => s.toLowerCase().includes(q)))
      : threads;
  }, [threads, query]);
}

const sameThread = (a: Thread, b: Thread) =>
  a.color.toLowerCase() === b.color.toLowerCase() && a.name === b.name && a.catalog === b.catalog && a.brand === b.brand;

/**
 * Pick a thread. With a block index (as listed in the panel) it recolors that block; with
 * `onPick` and `current` it just hands back the choice (e.g. a drawn object's thread).
 */
export function ThreadPicker({
  index,
  onClose,
  onPick,
  current: given,
}: {
  index: number | null;
  onClose: () => void;
  onPick?: (t: Thread) => void;
  current?: Thread;
}) {
  const design = useStore((s) => s.design);
  const openThreads = useStore((s) => s.setChartsOpen);
  const ref = useModal(index !== null);
  const { chartId, choose } = useChartChoice();
  const [chart, setChart] = useState<Chart | null>(null);
  const [closest, setClosest] = useState<ThreadMatch[]>([]);
  const [query, setQuery] = useState("");
  const filtered = useFiltered(chart?.threads, query);

  const block = index !== null && index >= 0 && design ? design.blocks[index] : null;
  const current = given ?? (block && design ? design.threads[block.thread] : null);
  const original = block?.original ?? current;

  useEffect(() => {
    if (index === null || !chartId || !original) return;
    let stale = false;
    void getChart(chartId).then((c) => !stale && setChart(c));
    void matchThreads([original.color], chartId, 6).then((m) => !stale && setClosest(m[0]));
    return () => {
      stale = true;
    };
  }, [index, chartId, original]);

  const pick = (t: ChartThread) => {
    if (index === null || !chart) return;
    if (onPick) onPick(toThread(t, chart.brand));
    else recolorBlock(index, toThread(t, chart.brand));
    onClose();
  };

  return (
    <dialog ref={ref} className="modal picker" onClose={onClose}>
      {original && current && (
        <>
          <h2>
            Change thread <span className="swatch inline" style={{ background: current.color }} />{" "}
            {current.name || current.color}
          </h2>
          <div className="row">
            <ChartSelect value={chartId} onChange={choose} />
            <button className="link" onClick={() => openThreads(true)}>
              Add my threads…
            </button>
          </div>
          {closest.length > 0 && (
            <>
              <h3>Closest matches</h3>
              <ul className="chips">
                {closest.map((t) => (
                  <li key={`${t.brand}|${t.code}|${t.color}`}>
                    <button onClick={() => pick(t)} title={`Color difference ${t.delta_e} (under 2 looks the same)`}>
                      <span className="swatch" style={{ background: t.color }} />
                      {spoolLabel(t)}
                      <small>{closeness(t.delta_e)}</small>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <input
            className="search"
            placeholder="Search by number or name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <ThreadGrid threads={filtered} onPick={pick} />
          <div className="actions">
            {!onPick && !sameThread(original, current) && (
              <button
                onClick={() => {
                  recolorBlock(index!, null);
                  onClose();
                }}
              >
                Back to {original.name || original.color}
              </button>
            )}
            <button onClick={onClose}>Cancel</button>
          </div>
        </>
      )}
    </dialog>
  );
}

/** Plain-words color difference. */
function closeness(deltaE: number) {
  if (deltaE < 2) return "same";
  if (deltaE < 5) return "very close";
  if (deltaE < 10) return "close";
  return "different";
}

/** Propose the nearest thread for every color; the user unticks any to keep. */
export function MatchAllDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const design = useStore((s) => s.design);
  const ref = useModal(open);
  const { chartId, choose } = useChartChoice();
  const [matches, setMatches] = useState<ThreadMatch[] | null>(null);
  const [accepted, setAccepted] = useState<boolean[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Each color block in sewing order, matched from the file's own color.
  const used = useMemo(
    () => (design ? design.blocks.map((b, i) => ({ block: i, was: b.original ?? design.threads[b.thread] })) : []),
    [design],
  );

  useEffect(() => {
    if (!open || !chartId || !design) return;
    let stale = false;
    setMatches(null);
    setError(null);
    matchThreads(
      used.map((u) => u.was.color),
      chartId,
      1,
    )
      .then((m) => {
        if (stale) return;
        setMatches(m.map((x) => x[0]));
        setAccepted(m.map(() => true));
      })
      .catch((e: unknown) => !stale && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      stale = true;
    };
  }, [open, chartId, design, used]);

  const apply = () => {
    if (!matches || !design) return;
    recolorBlocks(
      used.flatMap((u, k) => (accepted[k] ? [{ block: u.block, thread: toThread(matches[k], matches[k].brand) }] : [])),
    );
    onClose();
  };
  const n = accepted.filter(Boolean).length;

  return (
    <dialog ref={ref} className="modal match" onClose={onClose}>
      <h2>Match threads</h2>
      <p className="hint">The closest thread for each color. Untick any you want to keep as they are.</p>
      <ChartSelect value={chartId} onChange={choose} />
      {error && <p className="error">{error}</p>}
      {!matches && !error && <p className="hint">Matching…</p>}
      {matches && design && (
        <table className="match-table">
          <thead>
            <tr>
              <th />
              <th>Design uses</th>
              <th />
              <th>Use instead</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {used.map(({ block, was }, k) => {
              const m = matches[k];
              return (
                <tr key={block} className={m.delta_e >= 10 ? "far" : undefined}>
                  <td>
                    <input
                      type="checkbox"
                      checked={accepted[k] ?? false}
                      onChange={(e) => setAccepted(accepted.map((a, j) => (j === k ? e.target.checked : a)))}
                      aria-label={`Use ${spoolLabel(m)} for color ${block + 1}`}
                    />
                  </td>
                  <td>
                    <span className="swatch inline" style={{ background: was.color }} /> {was.name || was.color}
                  </td>
                  <td aria-hidden>→</td>
                  <td>
                    <span className="swatch inline" style={{ background: m.color }} /> {spoolLabel(m)}
                  </td>
                  <td title={`Color difference ${m.delta_e}`}>{closeness(m.delta_e)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" onClick={apply} disabled={!matches || n === 0}>
          Use {n} thread{n === 1 ? "" : "s"}
        </button>
      </div>
    </dialog>
  );
}

/** My threads (the user's spools) and brand charts. */
export function ChartsDialog() {
  const open = useStore((s) => s.chartsOpen);
  const setOpen = useStore((s) => s.setChartsOpen);
  const charts = useStore((s) => s.charts);
  const ref = useModal(open);
  const [tab, setTab] = useState<"mine" | "charts">("mine");
  const [error, setError] = useState<string | null>(null);

  return (
    <dialog ref={ref} className="modal threads-dialog" onClose={() => setOpen(false)}>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "mine"} onClick={() => setTab("mine")}>
          My threads
        </button>
        <button role="tab" aria-selected={tab === "charts"} onClick={() => setTab("charts")}>
          Brand charts
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {open && tab === "mine" && <MyThreadsTab onError={setError} />}
      {open && tab === "charts" && <ChartsTab charts={charts} onError={setError} />}
      <div className="actions">
        <button className="primary" onClick={() => setOpen(false)}>
          Done
        </button>
      </div>
    </dialog>
  );
}

function MyThreadsTab({ onError }: { onError: (e: string | null) => void }) {
  const charts = useStore((s) => s.charts);
  const brandCharts = charts.filter((c) => !c.mine);
  const [mine, setMine] = useState<Chart | null>(null);
  const [mode, setMode] = useState<"list" | "chart" | "custom">("list");
  const [sourceId, setSourceId] = useState(brandCharts[0]?.id ?? "");
  const [source, setSource] = useState<Chart | null>(null);
  const [query, setQuery] = useState("");
  const [custom, setCustom] = useState({ name: "", color: "#3366cc", brand: "", code: "" });
  const myCount = charts.find((c) => c.mine)?.count ?? 0;
  const filtered = useFiltered(source?.threads, query);

  useEffect(() => {
    void getChart(MY_THREADS).then(setMine);
  }, [myCount]);
  useEffect(() => {
    if (mode === "chart" && sourceId) void getChart(sourceId).then(setSource);
  }, [mode, sourceId]);

  const owned = (t: ChartThread, brand: string) =>
    mine?.threads.some((m) => (m.brand ?? "").toLowerCase() === brand.toLowerCase() && m.code === t.code) ?? false;

  const run = (p: Promise<unknown>) =>
    p.then(() => onError(null)).catch((e: unknown) => onError(e instanceof Error ? e.message : String(e)));

  const toggle = (t: ChartThread) => {
    if (!source) return;
    const spool = { ...t, brand: source.brand };
    run(owned(t, source.brand) ? removeMyThreads([{ ...spool, code: t.code }]) : addMyThreads([spool]));
  };

  if (mode === "chart") {
    const all = source?.threads ?? [];
    return (
      <>
        <h2>Tick the threads you own</h2>
        <div className="row">
          <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} aria-label="Brand">
            {brandCharts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.count})
              </option>
            ))}
          </select>
          <button
            onClick={() => source && run(addMyThreads(all.map((t) => ({ ...t, brand: source.brand }))))}
            disabled={!source}
          >
            I own all {all.length}
          </button>
        </div>
        <p className="hint">
          Many Amazon kits are sold as "Brother colors": pick <em>Brother (machine palette)</em> and tick what's in your
          box.
        </p>
        <input className="search" placeholder="Search by number or name…" value={query} onChange={(e) => setQuery(e.target.value)} />
        <ThreadGrid threads={filtered} onPick={toggle} selected={(t) => (source ? owned(t, source.brand) : false)} />
        <button className="link" onClick={() => setMode("list")}>
          ← Back to my threads
        </button>
      </>
    );
  }

  if (mode === "custom") {
    return (
      <>
        <h2>Add a spool by color</h2>
        <p className="hint">For threads without a chart, like most Amazon kits. Only the name and color are needed.</p>
        <div className="custom-spool">
          <input
            type="color"
            value={custom.color}
            onChange={(e) => setCustom({ ...custom, color: e.target.value })}
            aria-label="Thread color"
          />
          <input placeholder="Name, e.g. Navy" value={custom.name} onChange={(e) => setCustom({ ...custom, name: e.target.value })} />
          <input placeholder="Brand (optional)" value={custom.brand} onChange={(e) => setCustom({ ...custom, brand: e.target.value })} />
          <input placeholder="Number (optional)" value={custom.code} onChange={(e) => setCustom({ ...custom, code: e.target.value })} />
        </div>
        <div className="row">
          <button className="link" onClick={() => setMode("list")}>
            ← Back
          </button>
          <span className="spacer" />
          <button
            className="primary"
            disabled={!custom.name.trim()}
            onClick={() =>
              run(addMyThreads([custom]).then(() => setCustom({ name: "", color: custom.color, brand: custom.brand, code: "" })))
            }
          >
            Add spool
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <h2>My threads</h2>
      <p className="hint">
        The spools you own. Matching uses these first, so LUDD suggests threads you can actually use.
      </p>
      <div className="row">
        <button onClick={() => setMode("chart")}>Add from a brand…</button>
        <button onClick={() => setMode("custom")}>Add a spool by color…</button>
      </div>
      {mine && mine.threads.length === 0 && <p className="empty-note">No spools yet.</p>}
      {mine && mine.threads.length > 0 && (
        <ul className="my-spools">
          {mine.threads.map((t) => (
            <li key={`${t.brand}|${t.code}|${t.color}`}>
              <span className="swatch" style={{ background: t.color }} />
              <span className="tn">{spoolLabel(t)}</span>
              <button
                aria-label={`Remove ${spoolLabel(t)}`}
                title="Remove"
                onClick={() => run(removeMyThreads([{ code: t.code, brand: t.brand ?? "", color: t.color }]))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ChartsTab({
  charts,
  onError,
}: {
  charts: { id: string; name: string; builtin: boolean; count: number; mine: boolean }[];
  onError: (e: string | null) => void;
}) {
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [busy, setBusy] = useState(false);

  const doImport = async () => {
    setBusy(true);
    onError(null);
    try {
      if (await importChart(name, brand)) {
        setName("");
        setBrand("");
      }
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2>Brand charts</h2>
      <ul className="chart-list">
        {charts
          .filter((c) => !c.mine)
          .map((c) => (
            <li key={c.id}>
              <span>
                {c.name} <small>{c.count} threads{c.builtin ? " · built in" : ""}</small>
              </span>
              {!c.builtin && (
                <button
                  onClick={() => void deleteChart(c.id).catch((e: unknown) => onError(String(e)))}
                  aria-label={`Delete ${c.name}`}
                >
                  Delete
                </button>
              )}
            </li>
          ))}
      </ul>
      <details className="more">
        <summary>Import a chart from CSV</summary>
        <p className="hint">
          A spreadsheet saved as CSV with a header row: a number column (e.g. <code>Code</code>), and a <code>HEX</code>{" "}
          column or <code>R</code>, <code>G</code>, <code>B</code> columns. A name column is optional.
        </p>
        <div className="row">
          <input placeholder="Chart name, e.g. Madeira Polyneon 40" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Brand (optional)" value={brand} onChange={(e) => setBrand(e.target.value)} />
          <button className="primary" onClick={doImport} disabled={busy}>
            {busy ? "Importing…" : "Choose CSV…"}
          </button>
        </div>
      </details>
    </>
  );
}
