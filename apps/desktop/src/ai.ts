/**
 * The optional AI add-on in the UI: settings, the "before you send" check, Stitch Advisor
 * proposals and Help. Nothing here changes the design unless the user accepts a proposal.
 */
import { commit, currentDoc, currentLayout, fail, info } from "./actions";
import { updateObject } from "./design/layout";
import type { Layout, ObjectItem, PathNode } from "./design/types";
import { useStore } from "./store";

export type AISettings = {
  mode: "off" | "local" | "cloud";
  local: { url: string; model: string };
  cloud: { provider: "anthropic" | "openai"; model: string; base_url: string; price_in: number | null; price_out: number | null };
  features: { advisor: boolean; help: boolean };
  has_key: boolean;
};

/** What will be sent, shown before any cloud call. */
export type AIEstimate = {
  provider: string;
  model: string;
  cloud: boolean;
  text: string;
  images: { bytes: number; data_url: string }[];
  tokens_in: number;
  tokens_out_max: number;
  cost_usd_max: number | null;
};

export type AdviceChange = {
  stitch_type?: "run" | "satin" | "fill";
  angle_deg?: number;
  density?: "light" | "normal" | "dense";
  underlay?: "light" | "normal" | "heavy";
};
export type Proposal = { id: string; change: AdviceChange; reason: string };
export type Advice = { proposals: Proposal[]; order: { ids: string[]; reason: string } | null; dropped: number };
export type HelpResult = { sections: { title: string; text: string }[]; answer: string | null; ai: boolean };

const AI_TIMEOUT = 200_000; // local models on a modest graphics card can take a while

function engine() {
  const e = useStore.getState().engine;
  if (!e) throw new Error("The engine isn't connected");
  return e;
}

// ---------------------------------------------------------------- settings

export async function loadAISettings() {
  try {
    useStore.getState().setAI(await engine().call<AISettings>("ai.settings"));
  } catch {
    // AI settings are optional; without them AI simply stays off.
  }
}

export async function saveAISettings(patch: Partial<Omit<AISettings, "has_key">> & Record<string, unknown>) {
  try {
    useStore.getState().setAI(await engine().call<AISettings>("ai.save_settings", { patch }));
  } catch (err) {
    fail(err);
  }
}

export async function setAIKey(key: string | null) {
  try {
    useStore.getState().setAI(await engine().call<AISettings>("ai.set_key", { key }));
    info(key ? "Key saved, encrypted for your Windows account." : "Key removed.");
  } catch (err) {
    fail(err);
  }
}

export async function testAI(): Promise<string> {
  const r = await engine().call<{ ok: boolean; model: string; vision: boolean }>("ai.test", {}, AI_TIMEOUT);
  return r.ok
    ? `Connected to ${r.model}.${r.vision ? " It can look at pictures, so the Stitch Advisor will work." : " It can't look at pictures: choose a vision model for the Stitch Advisor."}`
    : "The model answered, but with nothing.";
}

export const aiOn = (feature: "advisor" | "help") => {
  const ai = useStore.getState().ai;
  return !!ai && ai.mode !== "off" && ai.features[feature];
};

/** Before a cloud call, show exactly what goes out (and the cost) and wait for Send or Cancel. */
function confirmSend(estimate: AIEstimate): Promise<boolean> {
  if (!estimate.cloud) return Promise.resolve(true);
  return new Promise((resolve) => useStore.getState().setAIPreview({ estimate, resolve }));
}

// ---------------------------------------------------------------- Stitch Advisor

const drawn = (l: Layout) => l.items.filter((it): it is ObjectItem => it.kind === "run" || it.kind === "satin" || it.kind === "fill");

/** The shapes to advise on: the selected one, or every drawn shape. */
function advisorTargets(): string[] | null {
  const l = currentLayout();
  if (!l) return null;
  const sel = useStore.getState().selectedId;
  const all = drawn(l);
  if (sel && all.some((o) => o.id === sel)) return [sel];
  return all.length ? all.map((o) => o.id) : null;
}

export const canAdvise = () => aiOn("advisor") && useStore.getState().engine !== null && advisorTargets() !== null;

export async function runAdvisor() {
  const s = useStore.getState();
  const layout = currentLayout();
  const ids = advisorTargets();
  if (!layout || !ids) return;
  const images = currentDoc()?.images ?? [];
  try {
    const estimate = await engine().call<AIEstimate>("ai.advisor_preview", { layout, images, ids }, AI_TIMEOUT);
    if (!(await confirmSend(estimate))) return;
    s.setAdvice({ proposals: [], order: null, dropped: 0, busy: true });
    const advice = await engine().call<Advice>("ai.advise", { layout, images, ids }, AI_TIMEOUT);
    useStore.getState().setAdvice({ ...advice, busy: false });
    if (!advice.proposals.length && !advice.order) {
      useStore.getState().setAdvice(null);
      info("The Stitch Advisor has no changes to suggest: these shapes look right to it.");
    }
  } catch (err) {
    useStore.getState().setAdvice(null);
    fail(err);
  }
}

const DENSITY_SPACING = { light: 0.5, normal: 0.4, dense: 0.33 } as const;
const UNDERLAY = {
  fill: { light: ["edge"], normal: ["edge", "tatami"], heavy: ["edge", "tatami"] },
  satin: { light: ["center"], normal: ["edge"], heavy: ["edge", "zigzag"] },
} as const;

/** Can this proposal be applied as it is? (A satin is two rails; a fill or line can't become one.) */
export function applicable(o: ObjectItem, c: AdviceChange): boolean {
  if (!c.stitch_type || c.stitch_type === o.kind) return true;
  return c.stitch_type !== "satin" && o.kind !== "satin";
}

/** The shape with a proposal's changes. Pure, for tests. */
export function withChange(o: ObjectItem, c: AdviceChange): ObjectItem {
  let out: ObjectItem = o;
  if (c.stitch_type && c.stitch_type !== o.kind && applicable(o, c)) {
    const outline: PathNode[] = o.kind === "run" ? o.geometry.nodes : o.kind === "satin" ? [] : o.geometry.outline;
    out =
      c.stitch_type === "run"
        ? ({ ...o, kind: "run", geometry: { nodes: outline, closed: true }, params: { style: "single", stitch_mm: 2.5 } } as ObjectItem)
        : ({ ...o, kind: "fill", geometry: { outline }, params: { angle_deg: 45, spacing_mm: 0.4, stitch_mm: 3.5 } } as ObjectItem);
  }
  const p: Record<string, unknown> = { ...out.params };
  if (out.kind === "fill" && c.angle_deg !== undefined) p.angle_deg = c.angle_deg;
  if ((out.kind === "fill" || out.kind === "satin") && c.density) p.spacing_mm = DENSITY_SPACING[c.density];
  if ((out.kind === "fill" || out.kind === "satin") && c.underlay) p.underlay = [...UNDERLAY[out.kind][c.underlay]];
  return { ...out, params: p } as ObjectItem;
}

/** Put the advised shapes in the suggested order, in the places they took before. Pure, for tests. */
export function withOrder(l: Layout, ids: string[]): Layout {
  const slots = l.items.map((it, i) => (ids.includes(it.id) ? i : -1)).filter((i) => i >= 0);
  const items = [...l.items];
  slots.forEach((slot, k) => {
    const it = l.items.find((x) => x.id === ids[k]);
    if (it) items[slot] = it;
  });
  return { ...l, items };
}

export function acceptProposal(p: Proposal) {
  const l = currentLayout();
  const o = l?.items.find((it) => it.id === p.id) as ObjectItem | undefined;
  if (!l || !o) return dropProposal(p);
  void commit(updateObject(l, p.id, (x) => withChange(x, p.change)));
  dropProposal(p);
}

export function dropProposal(p: Proposal) {
  const a = useStore.getState().advice;
  if (!a) return;
  const proposals = a.proposals.filter((x) => x !== p);
  useStore.getState().setAdvice(proposals.length || a.order ? { ...a, proposals } : null);
}

export function acceptOrder() {
  const a = useStore.getState().advice;
  const l = currentLayout();
  if (!a?.order || !l) return;
  void commit(withOrder(l, a.order.ids));
  useStore.getState().setAdvice(a.proposals.length ? { ...a, order: null } : null);
}

export function dropOrder() {
  const a = useStore.getState().advice;
  if (a) useStore.getState().setAdvice(a.proposals.length ? { ...a, order: null } : null);
}

/** Accept everything that can be applied, in one step (one Ctrl+Z undoes it). */
export function acceptAll() {
  const a = useStore.getState().advice;
  let l = currentLayout();
  if (!a || !l) return;
  for (const p of a.proposals) {
    const o = l.items.find((it) => it.id === p.id) as ObjectItem | undefined;
    if (o && applicable(o, p.change)) l = updateObject(l, p.id, (x) => withChange(x, p.change));
  }
  if (a.order) l = withOrder(l, a.order.ids);
  void commit(l);
  useStore.getState().setAdvice(null);
}

// ---------------------------------------------------------------- Help

export async function helpSearch(query: string): Promise<HelpResult["sections"]> {
  return engine().call<HelpResult["sections"]>("help.search", { query });
}

export async function helpAsk(question: string): Promise<HelpResult | null> {
  if (aiOn("help")) {
    const estimate = await engine().call<AIEstimate>("help.preview", { question });
    if (!(await confirmSend(estimate))) return null;
  }
  return engine().call<HelpResult>("help.ask", { question, use_ai: aiOn("help") }, AI_TIMEOUT);
}
