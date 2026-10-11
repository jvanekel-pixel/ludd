import { useEffect, useRef, useState } from "react";
import { acceptAll, acceptOrder, acceptProposal, aiOn, applicable, dropOrder, dropProposal, helpAsk, helpSearch, type AdviceChange, type HelpResult } from "../ai";
import { itemLabel } from "../design/layout";
import type { ObjectItem } from "../design/types";
import { selectLayout, useStore } from "../store";
import { useModal } from "./ThreadDialogs";

const TYPE_NAME = { run: "a running stitch line", satin: "a satin column", fill: "a fill" } as const;

/** Before anything goes to a cloud service: exactly what will be sent, and roughly what it costs. */
export function SendPreview() {
  const preview = useStore((s) => s.aiPreview);
  const setPreview = useStore((s) => s.setAIPreview);
  const ref = useModal(preview !== null);
  const done = (send: boolean) => {
    preview?.resolve(send);
    setPreview(null);
  };
  const e = preview?.estimate;
  return (
    <dialog ref={ref} className="modal send-preview" onClose={() => preview && done(false)} aria-labelledby="send-title">
      {e && (
        <>
          <h2 id="send-title">Send this to {e.provider === "anthropic" ? "Anthropic" : "your AI service"}?</h2>
          <p className="hint">
            Model {e.model}. About {e.tokens_in.toLocaleString()} tokens in and up to {e.tokens_out_max.toLocaleString()} out
            {e.cost_usd_max !== null ? `: at most about $${e.cost_usd_max.toFixed(3)} on your account.` : ". Add your service's prices in Settings → AI to see a cost estimate."}
          </p>
          {e.images.length > 0 && (
            <div className="send-images">
              {e.images.map((im, i) => (
                <img key={i} src={im.data_url} alt={`Picture ${i + 1} that will be sent`} />
              ))}
            </div>
          )}
          <details className="more">
            <summary>The text that will be sent</summary>
            <pre className="send-text">{e.text}</pre>
          </details>
          <div className="actions">
            <button onClick={() => done(false)}>Cancel</button>
            <button className="primary" onClick={() => done(true)}>
              Send
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}

function describe(o: ObjectItem | undefined, c: AdviceChange): string[] {
  const out: string[] = [];
  if (c.stitch_type && o && c.stitch_type !== o.kind) out.push(`Make it ${TYPE_NAME[c.stitch_type]}`);
  if (c.angle_deg !== undefined) out.push(`Stitch angle ${c.angle_deg}°`);
  if (c.density) out.push(`${c.density[0].toUpperCase()}${c.density.slice(1)} density`);
  if (c.underlay) out.push(`${c.underlay[0].toUpperCase()}${c.underlay.slice(1)} underlay`);
  return out;
}

/** Stitch Advisor suggestions: a checklist to accept or dismiss, one at a time or all together. */
export function AdvisorPanel() {
  const advice = useStore((s) => s.advice);
  const layout = useStore(selectLayout);
  const setAdvice = useStore((s) => s.setAdvice);
  if (!advice || !layout) return null;
  if (advice.busy)
    return (
      <section className="advisor" aria-live="polite">
        <h3>Stitch Advisor</h3>
        <p className="hint">Looking at your shapes… (a model on your own computer can take a minute)</p>
      </section>
    );
  const name = (id: string) => {
    const i = layout.items.findIndex((it) => it.id === id);
    return i >= 0 ? itemLabel(layout.items[i], i) : "A shape";
  };
  return (
    <section className="advisor" aria-label="Stitch Advisor suggestions">
      <div className="advisor-head">
        <h3>Stitch Advisor suggests</h3>
        <button className="primary" onClick={acceptAll}>
          Accept all
        </button>
        <button onClick={() => setAdvice(null)}>Dismiss all</button>
      </div>
      <ul>
        {advice.proposals.map((p) => {
          const o = layout.items.find((it) => it.id === p.id) as ObjectItem | undefined;
          const ok = !!o && applicable(o, p.change);
          return (
            <li key={p.id}>
              <p className="what">
                <strong>{name(p.id)}:</strong> {describe(o, p.change).join(", ")}
              </p>
              <p className="why">{p.reason}</p>
              {!ok && <p className="why">To follow this, draw the shape again with the {p.change.stitch_type} tool; it can't be switched over.</p>}
              <div className="btn-row">
                <button onClick={() => acceptProposal(p)} disabled={!ok}>
                  Accept
                </button>
                <button onClick={() => dropProposal(p)}>Dismiss</button>
              </div>
            </li>
          );
        })}
        {advice.order && (
          <li>
            <p className="what">
              <strong>Sewing order:</strong> {advice.order.ids.map(name).join(" → ")}
            </p>
            <p className="why">{advice.order.reason}</p>
            <div className="btn-row">
              <button onClick={acceptOrder}>Accept</button>
              <button onClick={dropOrder}>Dismiss</button>
            </div>
          </li>
        )}
      </ul>
      {advice.dropped > 0 && <p className="hint">{advice.dropped} suggestion(s) didn't make sense and were left out.</p>}
    </section>
  );
}

/** Help: search the guide (works offline); with AI on, also get an answer in plain words. */
export function HelpDialog() {
  const open = useStore((s) => s.helpOpen);
  const setOpen = useStore((s) => s.setHelpOpen);
  const ref = useModal(open);
  const [query, setQuery] = useState("");
  const [sections, setSections] = useState<HelpResult["sections"]>([]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const ai = aiOn("help");

  useEffect(() => {
    if (!open) return;
    let stale = false;
    const t = setTimeout(() => {
      (query.trim() ? helpSearch(query) : Promise.resolve([]))
        .then((r) => !stale && setSections(r))
        .catch(() => !stale && setSections([]));
    }, 150);
    return () => {
      stale = true;
      clearTimeout(t);
    };
  }, [query, open]);

  const ask = async () => {
    if (!query.trim()) return;
    setAsking(true);
    setError(null);
    setAnswer(null);
    try {
      const r = await helpAsk(query);
      if (r) {
        setAnswer(r.answer);
        setSections(r.sections);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAsking(false);
    }
  };

  return (
    <dialog ref={ref} className="modal help" onClose={() => setOpen(false)} aria-labelledby="help-title">
      <h2 id="help-title">Help</h2>
      <div className="help-ask">
        <input
          ref={input}
          autoFocus
          placeholder="Ask or search, e.g. how do I cut jump threads?"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setAnswer(null);
          }}
          onKeyDown={(e) => e.key === "Enter" && ai && void ask()}
        />
        {ai && (
          <button className="primary" onClick={() => void ask()} disabled={asking || !query.trim()}>
            {asking ? "Asking…" : "Ask AI"}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      {answer && (
        <div className="help-answer">
          <p>{answer}</p>
          <small>Answered by AI from the guide below. Check it against the guide if something looks off.</small>
        </div>
      )}
      <div className="help-sections">
        {sections.map((s) => (
          <article key={s.title}>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </article>
        ))}
        {!sections.length && query.trim() && <p className="hint">Nothing in the guide matches that. Try other words.</p>}
        {!query.trim() && <p className="hint">Type a question or a few words. The guide works without AI and without the internet.</p>}
      </div>
      <div className="actions">
        <button onClick={() => setOpen(false)}>Close</button>
      </div>
    </dialog>
  );
}
