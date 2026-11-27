/**
 * For tests only: the real design canvas (components/StitchCanvas.tsx) mounted in jsdom, driven by
 * pointer events on it and keys through the app's own keyboard handler. The test must stand
 * fakePixi.ts in for pixi.js: vi.mock("pixi.js", () => import("../canvas/fakePixi")).
 */
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { StitchCanvas } from "../components/StitchCanvas";
import type { Pt } from "../design/paths";
import { onKeyDown } from "../keys";
import { useStore } from "../store";

/** The design area's size, px. */
const SIZE = { width: 800, height: 600 };

/** What jsdom lacks and the canvas uses. */
function prepareDom() {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  (globalThis as { ResizeObserver?: unknown }).ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  const proto = HTMLElement.prototype as unknown as Record<string, unknown>;
  proto.setPointerCapture = () => {};
  proto.releasePointerCapture = () => {};
  proto.hasPointerCapture = () => false;
  Element.prototype.getBoundingClientRect = () => ({ x: 0, y: 0, left: 0, top: 0, right: SIZE.width, bottom: SIZE.height, ...SIZE, toJSON: () => ({}) }) as DOMRect;
  if (typeof (globalThis as { PointerEvent?: unknown }).PointerEvent === "undefined") {
    (globalThis as { PointerEvent?: unknown }).PointerEvent = class extends MouseEvent {
      pointerId: number;
      pointerType: string;
      constructor(type: string, init: PointerEventInit = {}) {
        super(type, init);
        this.pointerId = init.pointerId ?? 0;
        this.pointerType = init.pointerType ?? "mouse";
      }
    };
  }
}

type Init = Partial<PointerEventInit>;

export async function mountCanvas() {
  prepareDom();
  const box = document.createElement("div");
  document.body.append(box);
  const root = createRoot(box);
  await act(async () => root.render(createElement(StitchCanvas)));
  const host = box.querySelector<HTMLElement>(".stitch-canvas")!;
  let [scale, ox, oy] = [1, 0, 0];

  /** Where a design point (mm) is on screen: the pointer moves a whole pixel at a time. */
  const at = ([x, y]: Pt) => ({ clientX: Math.round(x * scale + ox), clientY: Math.round(y * scale + oy) });
  const fire = (type: string, p: Pt | null, init: Init = {}) => {
    const e = new PointerEvent(type, {
      bubbles: true, cancelable: true, pointerId: 1, button: type === "pointermove" ? -1 : 0, buttons: type === "pointerup" ? 0 : 1,
      ...(p ? at(p) : {}), ...init,
    });
    act(() => void host.dispatchEvent(e));
    return e;
  };
  const down = (p: Pt, init?: Init) => fire("pointerdown", p, init);
  const move = (p: Pt, init?: Init) => fire("pointermove", p, init);
  const up = (p: Pt, init?: Init) => fire("pointerup", p, init);
  const click = (p: Pt, init?: Init) => {
    down(p, init);
    up(p, init);
  };
  /** Press at the first point, drag through the rest and let go at the last. */
  const stroke = (pts: readonly Pt[], init?: Init) => {
    down(pts[0], init);
    for (const p of pts.slice(1, -1)) move(p, init);
    move(pts[pts.length - 1], init);
    up(pts[pts.length - 1], init);
  };
  const key = (k: string, mods: { ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean } = {}) =>
    act(() => onKeyDown({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, altKey: false, repeat: false, target: null, preventDefault: () => {}, ...mods } as unknown as KeyboardEvent));

  // Zoom to real size (an ordinary zoom), then find where the design is on screen by clicking
  // two points with a drawing tool.
  await act(async () => useStore.getState().requestZoom("actual"));
  act(() => useStore.getState().setTool("run"));
  const find = (cx: number, cy: number) => {
    act(() => useStore.getState().setPen(null));
    click([cx, cy]);
    const [x, y] = useStore.getState().pen!.a[0];
    return [x, y] as Pt;
  };
  const a = find(200, 150);
  const b = find(600, 450);
  scale = 400 / (b[0] - a[0]);
  [ox, oy] = [200 - a[0] * scale, 150 - a[1] * scale];
  act(() => {
    useStore.getState().setPen(null);
    useStore.getState().setTool("select");
  });

  return {
    host,
    /** One screen pixel, mm. */
    get pxMm() {
      return 1 / scale;
    },
    /** A design point as the screen shows it, back in mm (what the pointer's whole pixel means). */
    onScreen: (p: Pt): Pt => {
      const c = at(p);
      return [(c.clientX - ox) / scale, (c.clientY - oy) / scale];
    },
    at,
    down,
    move,
    up,
    click,
    stroke,
    key,
    unmount() {
      act(() => root.unmount());
      box.remove();
    },
  };
}

export type TestCanvas = Awaited<ReturnType<typeof mountCanvas>>;
