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
