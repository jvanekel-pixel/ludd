import { useEffect, useState } from "react";
import { saveAISettings, setAIKey, testAI, type AISettings as Settings } from "../ai";
import { useStore } from "../store";

const MODES: { id: Settings["mode"]; label: string }[] = [
  { id: "off", label: "Off" },
  { id: "local", label: "On this computer" },
  { id: "cloud", label: "Cloud" },
];

/** A text box that saves when you leave it (or press Enter). */
function Field({ label, value, onSave, placeholder }: { label: string; value: string; onSave: (v: string) => void; placeholder?: string }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <label className="field">
      {label}
      <input
        value={v}
        placeholder={placeholder}
        onChange={(e) => setV(e.target.value)}
        onBlur={() => v.trim() !== value && onSave(v.trim())}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
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
