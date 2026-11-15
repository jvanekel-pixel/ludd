import { useEffect, useRef, useState } from "react";
import { saveAISettings, setAIKey, testAI, type AISettings as Settings } from "../ai";
import { heldCount } from "../escape";
import { useStore } from "../store";
import { downloadTraceModel, removeTraceModel, resetPicks, setTraceAI } from "../autoTrace";

const MODES: { id: Settings["mode"]; label: string }[] = [
  { id: "off", label: "Off" },
  { id: "local", label: "On this computer" },
  { id: "cloud", label: "Cloud" },
];

/** A text box that saves when you leave it (or press Enter). */
function Field({ label, value, onSave, placeholder }: { label: string; value: string; onSave: (v: string) => void; placeholder?: string }) {
  const [v, setV] = useState(value);
  const reverting = useRef(false);
  useEffect(() => setV(value), [value]);
  return (
    <label className="field">
      {label}
      <input
        value={v}
        placeholder={placeholder}
        onChange={(e) => setV(e.target.value)}
        onBlur={() => {
          if (!reverting.current && v.trim() !== value) onSave(v.trim());
          reverting.current = false;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          // Esc lets go of the typing: the old value comes back, nothing is saved, and the
          // dialog stays open (one thing per press; something held, like a drag, goes first).
          if (e.key === "Escape" && !heldCount()) {
            e.preventDefault();
            reverting.current = true;
            setV(value);
            (e.target as HTMLInputElement).blur();
          }
        }}
      />
    </label>
  );
}

/** The optional AI add-on: off by default; a model on this computer (Ollama) or the user's own cloud key. */
export function AISettingsSection() {
  const ai = useStore((s) => s.ai);
  const [key, setKey] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  if (!ai) return null;

  const test = async () => {
    setTesting(true);
    setStatus(null);
    try {
      setStatus(await testAI());
    } catch (err) {
      setStatus(err instanceof Error ? err.message : String(err));
    } finally {
      setTesting(false);
    }
  };

  return (
    <>
      <h3>AI add-on (optional)</h3>
      <div className="seg" role="radiogroup" aria-label="AI">
        {MODES.map((m) => (
          <button key={m.id} role="radio" aria-checked={ai.mode === m.id} aria-pressed={ai.mode === m.id} onClick={() => void saveAISettings({ mode: m.id })}>
            {m.label}
          </button>
        ))}
      </div>
      {ai.mode === "off" && (
        <p className="hint">Off: nothing is sent anywhere, and everything in LUDD works without it. Turn it on for the Stitch Advisor and AI answers in Help.</p>
      )}
      {ai.mode === "local" && (
        <>
          <p className="hint">
            Uses Ollama, a free program that runs AI models on your own PC (a graphics card with 8 GB helps). Install it, then get a model that
            can see pictures, for example <code>ollama pull qwen2.5vl:7b</code> (or <code>gemma3:4b</code> on smaller cards).
          </p>
          <div className="ai-fields">
            <Field label="Model" value={ai.local.model} onSave={(model) => void saveAISettings({ local: { ...ai.local, model } })} />
            <Field label="Ollama address" value={ai.local.url} onSave={(url) => void saveAISettings({ local: { ...ai.local, url } })} />
          </div>
        </>
      )}
      {ai.mode === "cloud" && (
        <>
          <p className="hint">Uses your own account with an AI service; you pay them for what you use. Before anything is sent, LUDD shows you exactly what goes.</p>
          <div className="ai-fields">
            <label className="field">
              Service
              <select value={ai.cloud.provider} onChange={(e) => void saveAISettings({ cloud: { ...ai.cloud, provider: e.target.value as "anthropic" | "openai" } })}>
                <option value="anthropic">Anthropic (Claude)</option>
                <option value="openai">OpenAI-compatible</option>
              </select>
            </label>
            <Field label="Model" value={ai.cloud.model} onSave={(model) => void saveAISettings({ cloud: { ...ai.cloud, model } })} />
            {ai.cloud.provider === "openai" && (
              <Field label="Address" value={ai.cloud.base_url} onSave={(base_url) => void saveAISettings({ cloud: { ...ai.cloud, base_url } })} />
            )}
          </div>
          <div className="ai-key">
            <label className="field">
              API key {ai.has_key && <small className="ok">(saved)</small>}
              <input type="password" autoComplete="off" value={key} placeholder={ai.has_key ? "Saved; type a new one to replace it" : "Paste your key"} onChange={(e) => setKey(e.target.value)} />
            </label>
            <button
              onClick={() => {
                void setAIKey(key.trim());
                setKey("");
              }}
              disabled={!key.trim()}
            >
              Save key
            </button>
            {ai.has_key && <button onClick={() => void setAIKey(null)}>Remove</button>}
          </div>
          <details className="more">
            <summary>Cost estimate</summary>
            <p className="hint">Enter your service's prices (US$ per million tokens) to see a cost estimate before each request.</p>
            <div className="ai-fields">
              <Field label="Input price" value={ai.cloud.price_in?.toString() ?? ""} placeholder="e.g. 3" onSave={(v) => void saveAISettings({ cloud: { ...ai.cloud, price_in: v ? Number(v) : null } })} />
              <Field label="Output price" value={ai.cloud.price_out?.toString() ?? ""} placeholder="e.g. 15" onSave={(v) => void saveAISettings({ cloud: { ...ai.cloud, price_out: v ? Number(v) : null } })} />
            </div>
          </details>
        </>
      )}
      {ai.mode !== "off" && (
        <>
          <label className="check">
            <input type="checkbox" checked={ai.features.advisor} onChange={(e) => void saveAISettings({ features: { ...ai.features, advisor: e.target.checked } })} /> Stitch
            Advisor
            <small>Suggests stitch types, angles and sewing order for shapes you draw. You accept each suggestion.</small>
          </label>
          <label className="check">
            <input type="checkbox" checked={ai.features.help} onChange={(e) => void saveAISettings({ features: { ...ai.features, help: e.target.checked } })} /> AI
            answers in Help
          </label>
          <div className="btn-row">
            <button onClick={() => void test()} disabled={testing}>
              {testing ? "Testing…" : "Test connection"}
            </button>
          </div>
          {status && <p className="hint">{status}</p>}
        </>
      )}
    </>
  );
}

/** AI tracing for Auto-trace: a small model that runs on this computer, downloaded only on request. */
export function AITracingSection() {
  const model = useStore((s) => s.traceModel);
  const ai = useStore((s) => s.traceAI);
  const engine = useStore((s) => s.engine);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  if (!model) return null;
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      setAsking(false);
    }
  };
  return (
    <>
      <h3>AI tracing (optional)</h3>
      <p className="hint">
        Makes Auto-trace much better at photos and shaded art: a small model (MobileSAM, Apache-2.0 license) that runs on this computer. Nothing is sent
        anywhere; the only network use is downloading it once.
      </p>
      {!model.runtime ? (
        <p className="hint">AI tracing isn't available on this computer (it needs ONNX Runtime, which has no version for Intel Macs). Auto-trace works without it.</p>
      ) : model.installed ? (
        <>
          <label className="check">
            <input type="checkbox" checked={ai} onChange={(e) => setTraceAI(e.target.checked)} /> Use AI guesses in Auto-trace
          </label>
          <div className="btn-row">
            <button onClick={() => void run(async () => void (await removeTraceModel()))} disabled={busy || !engine}>
              Remove the model ({model.size_mb} MB)
            </button>
          </div>
        </>
      ) : asking ? (
        <div className="confirm">
          <p>
            Download <b>mobile_sam_image_encoder.onnx</b> and <b>sam_mask_decoder_multi.onnx</b> (about {model.size_mb} MB together) from{" "}
            <b>{model.source}</b>?
          </p>
          <div className="btn-row">
            <button className="primary" onClick={() => void run(downloadTraceModel)} disabled={busy || !engine}>
              {busy ? "Downloading…" : "Download"}
            </button>
            <button onClick={() => setAsking(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="btn-row">
          <button onClick={() => setAsking(true)} disabled={!engine}>
            Get AI tracing…
          </button>
        </div>
      )}
      {err && <p className="hint warn">{err}</p>}
      <div className="btn-row">
        <button className="link" onClick={resetPicks} title="Auto-trace puts the kind of guess you use most first">
          Forget which Auto-trace guesses I usually pick
        </button>
      </div>
    </>
  );
}
