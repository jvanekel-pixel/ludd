/**
 * A blend's colors: the shape's own thread, then the ones in `params.blend`; a color changed in
 * Order & colors (`threads[k]`, one per color) wins over either. Pure, for tests.
 */
import type { FillParams, ObjectItem, Thread } from "./types";

/** The panel offers up to three colors (the engine takes four). */
export const MAX_BLEND_COLORS = 3;

const WHITE: Thread = { color: "#ffffff", name: "White", catalog: "", brand: "" };
const NAVY: Thread = { color: "#1f3a93", name: "Navy", catalog: "", brand: "" };

/** Whether a "#rrggbb" color looks light (its perceived brightness). */
function isLight(color: string): boolean {
  const n = parseInt(color.replace("#", "").slice(0, 6), 16);
  if (!Number.isFinite(n)) return false;
  return 0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255) > 170;
}

/** The second color a new blend starts with: white, or navy on a light shape. */
export const secondColor = (first: Thread): Thread => ({ ...(isLight(first.color) ? NAVY : WHITE) });

/** What choosing the Blend pattern sets along with it: a second color, unless it has one. */
export function blendDefaults(o: ObjectItem): Record<string, unknown> {
  const p = o.params as FillParams;
  return p.blend?.length ? {} : { blend: [secondColor(o.threads?.[0] ?? o.thread)] };
}

/** The thread each part of a shape sews in, by slot: 0 the shape's own, then a blend's others. */
export function slotThreads(o: ObjectItem): Thread[] {
  const own = o.threads?.[0] ?? o.thread;
  if (o.kind !== "fill" || o.params.pattern !== "blend") return [own];
  return [own, ...(o.params.blend ?? []).map((t, k) => o.threads?.[k + 1] ?? t)];
}

const fillParams = (o: ObjectItem) => o.params as FillParams;

/** A blend's color `k` (1 or more: the shape's own is 0) set to `t`. Any Order & colors change of
 *  that color is cleared, so the new one shows. */
export function setBlendColor(o: ObjectItem, k: number, t: Thread): ObjectItem {
  const blend = [...(fillParams(o).blend ?? [])];
  if (k < 1 || k > blend.length) return o;
  blend[k - 1] = { ...t };
  const threads = [...(o.threads ?? [])];
  if (k < threads.length) threads[k] = null;
  return { ...o, params: { ...o.params, blend }, threads } as ObjectItem;
}

/** One more color at the far end of the blend (up to MAX_BLEND_COLORS in all). */
export function addBlendColor(o: ObjectItem): ObjectItem {
  const sewn = slotThreads(o);
  if (sewn.length >= MAX_BLEND_COLORS) return o;
  const blend = [...(fillParams(o).blend ?? []), secondColor(sewn[sewn.length - 1])];
  return { ...o, params: { ...o.params, blend } } as ObjectItem;
}

/** A blend without its color `k` (1 or more); it keeps at least one color besides the shape's
 *  own. Order & colors changes stay with the colors they were made to. */
export function removeBlendColor(o: ObjectItem, k: number): ObjectItem {
  const blend = [...(fillParams(o).blend ?? [])];
  if (k < 1 || k > blend.length || blend.length <= 1) return o;
  blend.splice(k - 1, 1);
  const threads = (o.threads ?? []).filter((_, i) => i !== k);
  return { ...o, params: { ...o.params, blend }, threads } as ObjectItem;
}

/** "Swap the colors": the shape sews its colors the other way round (its own thread included),
 *  so the fade runs the other way. Order & colors changes are folded in and cleared; the balance
 *  turns round too, so each color keeps the share of the shape it had. */
export function swapBlendColors(o: ObjectItem): ObjectItem {
  const sewn = slotThreads(o);
  if (sewn.length < 2) return o;
  const [first, ...rest] = [...sewn].reverse().map((t) => ({ ...t }));
  const balance = fillParams(o).blend_balance;
  const params = { ...o.params, blend: rest, ...(balance ? { blend_balance: -balance } : {}) };
  return { ...o, thread: first, params, threads: [] } as ObjectItem;
}
