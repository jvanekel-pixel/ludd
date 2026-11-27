/**
 * For tests only: just enough of pixi.js for the real design canvas (components/StitchCanvas.tsx)
 * to run in jsdom. Drawing calls are taken and ignored; nothing is rendered. A test uses it with
 *   vi.mock("pixi.js", () => import("../canvas/fakePixi"));
 */

class Point {
  constructor(
    public x = 0,
    public y = x,
  ) {}
  set(x = 0, y = x) {
    this.x = x;
    this.y = y;
    return this;
  }
}

export class Container {
  children: Container[] = [];
  parent: Container | null = null;
  position = new Point();
  scale = new Point(1);
  pivot = new Point();
  anchor = new Point();
  alpha = 1;
  visible = true;
  label = "";
  rotation = 0;
  width = 0;
  height = 0;
  destroyed = false;
  get x() {
    return this.position.x;
  }
  set x(v: number) {
    this.position.x = v;
  }
  get y() {
    return this.position.y;
  }
  set y(v: number) {
    this.position.y = v;
  }
  addChildAt<T extends Container>(c: T, i: number): T {
    c.parent?.removeChild(c);
    c.parent = this;
    this.children.splice(i, 0, c);
    return c;
  }
  addChild(...cs: Container[]) {
    for (const c of cs) this.addChildAt(c, this.children.length);
    return cs[0];
  }
  getChildIndex(c: Container) {
    return this.children.indexOf(c);
  }
  removeChild(c: Container) {
    const i = this.children.indexOf(c);
    if (i >= 0) this.children.splice(i, 1);
    c.parent = null;
    return c;
  }
  removeChildren() {
    const out = this.children;
    this.children = [];
    for (const c of out) c.parent = null;
    return out;
  }
  destroy(_options?: unknown) {
    this.destroyed = true;
    this.parent?.removeChild(this);
  }
}

export class Graphics extends Container {
  clear() {
    return this;
  }
  beginPath() {
    return this;
  }
  closePath() {
    return this;
  }
  moveTo() {
    return this;
  }
  lineTo() {
    return this;
  }
  stroke() {
    return this;
  }
  fill() {
    return this;
  }
  circle() {
    return this;
  }
  ellipse() {
    return this;
  }
  rect() {
    return this;
  }
  roundRect() {
    return this;
  }
  poly() {
    return this;
  }
  arc() {
    return this;
  }
  bezierCurveTo() {
    return this;
  }
}

export class Texture {
  width = 1;
  height = 1;
  static from(_source?: unknown) {
    return new Texture();
  }
  destroy() {}
}

export class Sprite extends Container {
  tint = 0xffffff;
  constructor(public texture?: unknown) {
    super();
  }
}

export class Text extends Container {
  text: string;
  style: unknown;
  constructor(options?: { text?: string; style?: unknown }) {
    super();
    this.text = options?.text ?? "";
    this.style = options?.style;
  }
}

export class Application {
  stage = new Container();
  canvas = document.createElement("canvas");
  screen = { width: 800, height: 600 };
  init() {
    return Promise.resolve();
  }
  resize() {}
  destroy() {}
}
