"""SVG artwork, read with svgelements (paths, basic shapes, groups, transforms, <use>, CSS
classes and units) from the drawing svgclean.py rebuilt."""

from __future__ import annotations

import io
import math
import re

from . import MAX_COORDINATE, ArtError, Deadline, svgclean
from .model import INVALID, Drawing, Item, Point, Subpath, parse_color

MM_PER_PX = 25.4 / 96  # CSS pixels: 96 to the inch
NO_REAL_SIZE = ("This SVG doesn't say its real size, so LUDD read it at 96 pixels per inch. Set Width to the size you "
                "want.")
_PAINT_URL = re.compile(r"url\(\s*(['\"]?)([^'\"()]{0,2000})\1\s*\)(.*)\Z", re.IGNORECASE | re.DOTALL)


def read(data: bytes, deadline: Deadline) -> Drawing:
    if data[:2] == b"\x1f\x8b":
        raise ArtError("This is a compressed SVG (.svgz): save the drawing as a plain .svg and import that.")
    prepared = svgclean.prepare(data)
    deadline.check()
    from svgelements import SVG, Shape

    broken = 0
    try:
        document = SVG.parse(io.BytesIO(prepared.data), reify=False, ppi=96)
    except Exception:
        # One path it can't read mustn't lose the whole drawing: leave such paths out.
        data, broken = svgclean.without_broken_paths(prepared.data)
        if not broken:
            raise
        deadline.check()
        document = SVG.parse(io.BytesIO(data), reify=False, ppi=96)
    deadline.check()
    drawing = Drawing(scale_note=None if prepared.real_size else NO_REAL_SIZE)
    drawing.skipped.add("damaged", broken)
    drawing.skipped.add("link", prepared.links)
    drawing.skipped.add("clip", prepared.clips)
    for i, element in enumerate(document.elements()):
        if i % 100 == 0:
            deadline.check()
        values = getattr(element, "values", None) or {}
        if isinstance(element, Shape):
            if not _hidden(values):
                _shape(element, values, prepared, drawing)
        elif values.get("tag") in ("luddText", "luddImage") and not _hidden(values):
            drawing.skipped.add("text" if values["tag"] == "luddText" else "picture")
    return drawing


def _fraction(values: dict, name: str) -> float:
    text = str(values.get(name, "1")).strip()
    try:
        return float(text.rstrip("%")) / (100 if text.endswith("%") else 1)
    except ValueError:
        return 1.0


def _hidden(values: dict) -> bool:
    return (str(values.get("visibility", "")).strip().lower() in ("hidden", "collapse")
            or _fraction(values, "opacity") <= 0)


def _paint(raw: str, default: str | None, values: dict, prepared: svgclean.Prepared, drawing: Drawing) -> str | None:
    """A fill's or stroke's color, "#rrggbb", or None for none. `default`: what an unreadable
    color comes to (black for a fill, as SVG's fill is; no stroke)."""
    raw = raw.strip()
    if raw[:4].lower() == "url(":
        found = _PAINT_URL.match(raw)
        target = found[2].strip() if found else ""
        if target.startswith("#"):
            server = prepared.paint(target[1:])
            if server and server[0] == "gradient":
                drawing.skipped.add("gradient")
                return server[1]
            if server:
                drawing.skipped.add("pattern")
                return None
        elif target:
            drawing.skipped.add("link")  # paint in another file or on a website
        raw = (found[3].strip() if found else "") or "none"  # SVG's own fallback, after url()
    if raw.lower() == "currentcolor":
        raw = str(values.get("color") or "black")
    color = parse_color(raw)
    return default if color == INVALID else color


def _shape(element, values: dict, prepared: svgclean.Prepared, drawing: Drawing) -> None:
    fill = _paint(str(values.get("fill", "black")), "#000000", values, prepared, drawing)
    stroke = _paint(str(values.get("stroke", "none")), None, values, prepared, drawing)
    if _fraction(values, "fill-opacity") <= 0:
        fill = None
    if _fraction(values, "stroke-opacity") <= 0:
        stroke = None
    width = 0.0
    if stroke:
        width = element.implicit_stroke_width
        width = float(width) * MM_PER_PX if width is not None else 0.0
        if not math.isfinite(width) or width <= 0:
            stroke, width = None, 0.0
    if not fill and not stroke:
        return
    subpaths = _subpaths(element)
    if not subpaths:
        return
    own = values.get("attributes") or {}
    dashes = str(values.get("stroke-dasharray", "none")).strip().lower()
    drawing.items.append(Item(
        subpaths=subpaths,
        fill=fill,
        fill_rule="evenodd" if str(values.get("fill-rule", "")).strip().lower() == "evenodd" else "nonzero",
        stroke=stroke,
        stroke_width=width,
        cap=str(values.get("stroke-linecap", "butt")).strip().lower(),
        join=str(values.get("stroke-linejoin", "miter")).strip().lower(),
        miter_limit=_number(values.get("stroke-miterlimit"), 4.0),
        name=str(own.get(svgclean.INKSCAPE_LABEL) or own.get("data-name") or "").strip(),
        dashed=bool(stroke) and dashes not in ("", "none") and bool(re.search(r"[1-9]", dashes)),
    ))


def _number(text, otherwise: float) -> float:
    try:
        v = float(str(text))
    except (TypeError, ValueError):
        return otherwise
    return v if math.isfinite(v) else otherwise


def _subpaths(element) -> list[Subpath]:
    """The shape's segments in mm. Arcs become curves in the shape's own coordinates, then every
    point is moved by its transform (which keeps curves exact even when it skews them)."""
    from svgelements import Arc, Close, CubicBezier, Line, Move, QuadraticBezier

    m = element.transform
    a, b, c, d, e, f = (float(v) for v in (m.a, m.b, m.c, m.d, m.e, m.f))

    def place(x: float, y: float) -> Point:
        px, py = (a * x + c * y + e) * MM_PER_PX, (b * x + d * y + f) * MM_PER_PX
        if not (abs(px) <= MAX_COORDINATE and abs(py) <= MAX_COORDINATE):  # false for NaN too
            raise ArtError("This drawing has points that aren't numbers, or are far outside any real drawing. "
                           "Save it again from your drawing program.")
        return px, py

    def at(p) -> Point:
        return place(float(p.x), float(p.y))

    out: list[Subpath] = []
    current: Subpath | None = None

    def keep(sub: Subpath | None) -> None:
        if sub is not None and (sub.segments or sub.closed):
            out.append(sub)

    for seg in element.segments(transformed=False):
        if not _complete(seg):
            break  # path data that goes wrong is drawn up to there, as browsers draw it
        if isinstance(seg, Move):
            keep(current)
            current = Subpath(at(seg.end)) if seg.end is not None else None
            continue
        if isinstance(seg, Close):
            if current is not None:
                if math.dist(current.end, current.start) > 1e-9:
                    current.segments.append(("L", current.start))
                current.closed = True
                keep(current)
                current = None
            continue
        if seg.start is None or seg.end is None:
            continue
        if current is None:
            current = Subpath(at(seg.start))  # drawing straight after a Z starts where it closed
        if isinstance(seg, Line):
            current.segments.append(("L", at(seg.end)))
        elif isinstance(seg, CubicBezier):
            current.segments.append(("C", at(seg.control1), at(seg.control2), at(seg.end)))
        elif isinstance(seg, QuadraticBezier):
            (sx, sy), (qx, qy), (ex, ey) = ((float(p.x), float(p.y)) for p in (seg.start, seg.control, seg.end))
            current.segments.append(("C", place(sx + (qx - sx) * 2 / 3, sy + (qy - sy) * 2 / 3),
                                     place(ex + (qx - ex) * 2 / 3, ey + (qy - ey) * 2 / 3), place(ex, ey)))
        elif isinstance(seg, Arc):
            for c1, c2, end in _arc_curves(seg):
                if c1 is None:
                    current.segments.append(("L", place(*end)))
                else:
                    current.segments.append(("C", place(*c1), place(*c2), place(*end)))
    keep(current)
    return out


def _complete(seg) -> bool:
    """Does the segment have all its numbers? (Cut-short path data leaves some out.)"""
    points = (getattr(seg, name, None) for name in ("start", "end", "control", "control1", "control2", "center",
                                                    "prx", "pry"))
    return all(p is None or (p.x is not None and p.y is not None) for p in points)


def _arc_curves(arc) -> list[tuple]:
    """An elliptical arc as cubic curves of at most 45 degrees each: (c1, c2, end), or
    (None, None, end) for a straight line (a flat arc)."""
    end = (float(arc.end.x), float(arc.end.y))
    cx, cy = float(arc.center.x), float(arc.center.y)
    ux, uy = float(arc.prx.x) - cx, float(arc.prx.y) - cy
    vx, vy = float(arc.pry.x) - cx, float(arc.pry.y) - cy
    sweep = float(arc.sweep)
    det = ux * vy - uy * vx
    if not all(map(math.isfinite, (cx, cy, ux, uy, vx, vy, sweep, det))) or abs(det) < 1e-12 or sweep == 0:
        return [(None, None, end)]
    dx, dy = float(arc.start.x) - cx, float(arc.start.y) - cy
    t0 = math.atan2((ux * dy - uy * dx) / det, (dx * vy - dy * vx) / det)
    n = min(64, max(1, math.ceil(abs(sweep) / (math.pi / 4) - 1e-9)))
    step = sweep / n
    k = 4 / 3 * math.tan(step / 4)

    def point(t: float) -> tuple[float, float]:
        return cx + ux * math.cos(t) + vx * math.sin(t), cy + uy * math.cos(t) + vy * math.sin(t)

    def slope(t: float) -> tuple[float, float]:
        return -ux * math.sin(t) + vx * math.cos(t), -uy * math.sin(t) + vy * math.cos(t)

    out = []
    p = (float(arc.start.x), float(arc.start.y))
    for i in range(n):
        ta, tb = t0 + step * i, t0 + step * (i + 1)
        q = end if i == n - 1 else point(tb)
        (ax, ay), (bx, by) = slope(ta), slope(tb)
        out.append(((p[0] + k * ax, p[1] + k * ay), (q[0] - k * bx, q[1] - k * by), q))
        p = q
    return out
