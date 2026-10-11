"""Build the sample designs that ship with LUDD (samples/), all drawn here from scratch.

Run from the repo root:  uv run --project engine python scripts/make_samples.py
Each sample is a LUDD project (.ludd) plus, for some, a ready-to-stitch PES and JEF.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))

from threadline_engine import layout, project  # noqa: E402

OUT = ROOT / "samples"
IDENTITY = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}

# Thread colours named the way a hobbyist would describe them.
RED = {"color": "#c8102e", "name": "Red", "catalog": "", "brand": ""}
YELLOW = {"color": "#ffcd00", "name": "Sunflower", "catalog": "", "brand": ""}
GREEN = {"color": "#3a7d44", "name": "Leaf green", "catalog": "", "brand": ""}
DARK_GREEN = {"color": "#1e4d2b", "name": "Forest green", "catalog": "", "brand": ""}
NAVY = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}
GOLD = {"color": "#c9a227", "name": "Gold", "catalog": "", "brand": ""}
PINK = {"color": "#e86a92", "name": "Rose pink", "catalog": "", "brand": ""}
WHITE = {"color": "#f4f1ea", "name": "White", "catalog": "", "brand": ""}

_n = 0


def _id() -> str:
    global _n
    _n += 1
    return f"s{_n}"


def obj(kind: str, geometry: dict, thread: dict, name: str, **params) -> dict:
    return {"id": _id(), "kind": kind, "name": name, "geometry": geometry, "params": params, "thread": thread,
            "transform": dict(IDENTITY), "threads": [], "ops": []}


def ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 8, turn: float = 0.0) -> list:
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, y = rx * math.cos(a), ry * math.sin(a)
        t = math.radians(turn)
        pts.append([round(cx + x * math.cos(t) - y * math.sin(t), 2), round(cy + x * math.sin(t) + y * math.cos(t), 2), "s"])
    return pts


def ring(cx: float, cy: float, r: float, n: int = 12) -> list:
    pts = ellipse(cx, cy, r, r, n)
    return pts + [pts[0]]


def star(cx: float, cy: float, r_out: float, r_in: float, points: int = 5) -> list:
    pts = []
    for k in range(points * 2):
        a = -math.pi / 2 + math.pi * k / points
        r = r_out if k % 2 == 0 else r_in
        pts.append([round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2), "c"])
    return pts


def leaf(cx: float, cy: float, length: float, width: float, turn: float) -> list:
    """A pointed leaf: corners at both tips, curves along the sides."""
    t = math.radians(turn)

    def p(x, y, kind):
        return [round(cx + x * math.cos(t) - y * math.sin(t), 2), round(cy + x * math.sin(t) + y * math.cos(t), 2), kind]

    h = length / 2
    return [p(-h, 0, "c"), p(-h / 3, -width / 2, "s"), p(h / 3, -width / 2, "s"), p(h, 0, "c"), p(h / 3, width / 2, "s"), p(-h / 3, width / 2, "s")]


def heart(cx: float, cy: float, s: float) -> list:
    pts = []
    for k in range(16):
        a = 2 * math.pi * k / 16
        x = 16 * math.sin(a) ** 3
        y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append([round(cx + x * s, 2), round(cy + y * s, 2), "c" if k == 8 else "s"])
    return pts


def doc(title: str, items: list, fabric: str = "woven", **extra) -> dict:
    lay = {"title": title, "items": items, "merge_colors": False, "color_sort": False,
           "basting": {"enabled": False, "margin_mm": 5}, "fabric": fabric, **extra}
    return {"title": title, "layout": lay, "images": [], "machine": "brother-pe550d"}


def star_badge() -> dict:
    return doc("Star badge", [
        # The background leaves a star-shaped hole, so the star isn't sewn on top of it (less thread, no stiffness).
        obj("fill", {"outline": ellipse(0, 0, 29.4, 29.4, 12), "holes": [star(0, 0, 21.5, 8.6)]}, NAVY, "Background", angle_deg=135),
        obj("fill", {"outline": star(0, 0, 22, 9)}, GOLD, "Star", angle_deg=90),
        obj("satin", {"rail_a": ring(0, 0, 33), "rail_b": ring(0, 0, 29)}, GOLD, "Border"),
    ])


def flower() -> dict:
    items = [obj("satin", {"rail_a": [[-1.5, 12, "c"], [-3.5, 30, "s"], [-1.5, 48, "c"]],
                           "rail_b": [[1.5, 12, "c"], [-0.5, 30, "s"], [1.5, 48, "c"]]}, DARK_GREEN, "Stem"),
             obj("fill", {"outline": leaf(-12, 34, 20, 8, -30)}, GREEN, "Left leaf", angle_deg=60),
             obj("fill", {"outline": leaf(11, 40, 18, 7, 25)}, GREEN, "Right leaf", angle_deg=120)]
    for k in range(6):
        a = 60 * k
        cx, cy = 15.8 * math.cos(math.radians(a)), 15.8 * math.sin(math.radians(a))
        items.append(obj("fill", {"outline": ellipse(cx, cy - 8, 9.5, 6, 8, a)}, PINK, f"Petal {k + 1}", angle_deg=(a + 90) % 180))
    items.append(obj("fill", {"outline": ellipse(0, -8, 7, 7, 8)}, YELLOW, "Centre", angle_deg=45))
    return doc("Flower", items)


def applique_heart() -> dict:
    return doc("Applique heart", [
        obj("applique", {"outline": heart(0, 0, 2.1)}, RED, "Heart", cover_width_mm=3, tack="zigzag"),
        obj("run", {"nodes": heart(0, 1, 1.35), "closed": True}, WHITE, "Stitched line", style="triple"),
    ])


def wreath() -> dict:
    items = []
    for k in range(10):
        a = 36 * k
        cx, cy = 30 * math.cos(math.radians(a)), 30 * math.sin(math.radians(a))
        items.append(obj("fill", {"outline": leaf(cx, cy, 16, 7, a + 90)}, GREEN, f"Leaf {k + 1}", angle_deg=(a + 45) % 180))
    for k in range(5):
        a = 72 * k + 18
        items.append(obj("fill", {"outline": ellipse(36 * math.cos(math.radians(a)), 36 * math.sin(math.radians(a)), 3, 3, 8)}, RED, f"Berry {k + 1}"))
    return doc("Wreath", items)


def banner() -> dict:
    """Wider than a 4-inch hoop: try Save for machine to split it into two hoopings."""
    return doc("Banner (two hoopings)", [
        obj("fill", {"outline": [[-79.4, -21.4, "c"], [79.4, -21.4, "c"], [79.4, 21.4, "c"], [-79.4, 21.4, "c"]]}, NAVY, "Banner", angle_deg=30),
        obj("satin", {"rail_a": [[-82, -24, "c"], [82, -24, "c"], [82, 24, "c"], [-82, 24, "c"], [-82, -24, "c"]],
                      "rail_b": [[-79, -21, "c"], [79, -21, "c"], [79, 21, "c"], [-79, 21, "c"], [-79, -21, "c"]]}, GOLD, "Border"),
        obj("fill", {"outline": star(-55, 0, 14, 6)}, GOLD, "Left star", angle_deg=90),
        obj("fill", {"outline": star(0, 0, 14, 6)}, WHITE, "Middle star", angle_deg=90),
        obj("fill", {"outline": star(55, 0, 14, 6)}, GOLD, "Right star", angle_deg=90),
    ])


SAMPLES = {
    "Star badge": (star_badge, True),
    "Flower": (flower, True),
    "Applique heart": (applique_heart, False),
    "Wreath": (wreath, True),
    "Banner (two hoopings)": (banner, False),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, (build, machine_files) in SAMPLES.items():
        d = build()
        project.save(str(OUT / f"{name}.ludd"), d)
        info = layout.render_summary(d["layout"])["info"]
        print(f"{name}: {info['width_mm']:.0f} x {info['height_mm']:.0f} mm, {info['stitches']} stitches, {info['colors']} colors")
        if machine_files:
            for ext in ("pes", "jef"):
                layout.export(d["layout"], str(OUT / f"{name}.{ext}"))


if __name__ == "__main__":
    main()
