"""Putting the letters together: in a straight line, on an arch, a circle or a drawn line, or as
a monogram."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..digitize import stitches as dz
from .fonts import STITCH_FONT_EXTS, LetteringError, _signed_area, resolve_font, substitute_font
from .glyphs import SMALL_TEXT_MM, Glyph, _Missing, _outline_glyphs, _stitch_font_glyphs


def _move(obj: dict[str, Any], fn) -> dict[str, Any]:
    """Map every node of an object with fn(x, y) -> (x, y)."""
    g = dict(obj.get("geometry") or {})
    for key in ("nodes", "rail_a", "rail_b", "outline"):
        if g.get(key):
            g[key] = [[*fn(n[0], n[1]), *n[2:]] for n in g[key]]
    if g.get("holes"):
        g["holes"] = [[[*fn(n[0], n[1]), *n[2:]] for n in h] for h in g["holes"]]
    return {**obj, "geometry": g}


def turn_with(obj: dict[str, Any], t: Any) -> dict[str, Any]:
    """A letter's stitch angle turned, mirrored and stretched with it (`t` like a layout Transform:
    rotate in degrees, scale_x/scale_y, flip_x/flip_y), so satin stitches still cross the strokes."""
    p = obj.get("params") or {}
    if obj.get("kind") != "fill" or p.get("angle_deg") is None:
        return obj
    a = math.radians(float(p["angle_deg"]))
    vx = math.cos(a) * (-1.0 if getattr(t, "flip_x", False) else 1.0) * float(getattr(t, "scale_x", 1.0))
    vy = math.sin(a) * (-1.0 if getattr(t, "flip_y", False) else 1.0) * float(getattr(t, "scale_y", 1.0))
    deg = math.degrees(math.atan2(vy, vx)) + float(getattr(t, "rotate", 0.0))
    deg = round(deg % 180.0, 3)
    if deg >= 180.0:
        deg = 0.0
    return {**obj, "params": {**p, "angle_deg": deg}}


@dataclass
class _Turn:
    """A plain turn (degrees), for turn_with."""

    rotate: float


def _clean_text(text: str) -> str:
    """Composed accents (e + combining acute -> é), line breaks and tabs as spaces, invisible marks out."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\t\n\r\v\f  ]", " ", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def layout_text(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Objects for a text item, centred on (0, 0) in mm, plus warnings."""
    text = _clean_text(str(spec.get("text") or ""))
    font = spec.get("font") or {}
    size = float(spec.get("size_mm") or 12)
    spacing = float(spec.get("spacing_mm") or 0)
    style = spec.get("style") or "satin"
    shape = spec.get("shape") or {"type": "line"}
    monogram = bool(spec.get("monogram"))
    if not text.strip():
        raise LetteringError("Type some text first")
    if not font.get("path"):
        raise LetteringError("Choose a font")
    warnings: list[str] = []
    try:
        font = resolve_font(font)
    except LetteringError:
        # Not on this computer (a project from another PC, an uninstalled font): show the text in a
        # standard font and say so, rather than refusing to open the whole design.
        stand_in = substitute_font()
        if not stand_in:
            raise
        warnings.append(f"The font {font.get('family') or 'used here'} isn't installed on this computer, so it's shown in "
                        f"{stand_in['family']}. Install it, or pick another font in the Lettering panel.")
        font = {**font, "path": stand_in["path"], "index": stand_in["index"]}
    if not 2 <= size <= 200:
        raise LetteringError("Letter height must be between 2 and 200 mm")
    smallest = size * 0.7 if monogram else size  # a monogram's side letters are smaller
    if smallest < SMALL_TEXT_MM:
        warnings.append(f"Letters {smallest:.1f} mm tall are hard to stitch clearly (dots and thin parts drop out); "
                        f"{SMALL_TEXT_MM:.0f} mm or more is safer.")

    is_stitch_font = Path(str(font["path"])).suffix.lower() in STITCH_FONT_EXTS
    missing = _Missing()

    def glyphs_for(t: str, sz: float) -> list[Glyph]:
        if is_stitch_font:
            return _stitch_font_glyphs(t, font["path"], sz, spacing, missing)
        return _outline_glyphs(t, font["path"], int(font.get("index", 0)), sz, spacing, style, missing)

    def done(objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        if not objects:
            if missing.left_out:
                raise LetteringError("This font has none of these letters. Pick another font.")
            raise LetteringError("Nothing to stitch: these letters are empty or too small in this font.")
        return objects, warnings + missing.warnings(is_stitch_font)

    objects: list[dict[str, Any]] = []
    if monogram:
        from .monogram import layout as monogram_layout

        return done(monogram_layout([c for c in text if not c.isspace()], size, spacing, glyphs_for))

    glyphs = glyphs_for(text, size)
    total = sum(g.advance for g in glyphs) - spacing
    kind = shape.get("type", "line")
    radius = float(shape.get("radius_mm", 40))
    if kind == "path":
        closed = bool(shape.get("closed"))
        objects, length = _along_path(glyphs, total, size, shape.get("nodes") or [], closed)
        if total > length + 0.5:
            warnings.append(f"The text is longer than its line ({total:.0f} mm of letters on {length:.0f} mm), so letters "
                            f"{'overlap' if closed else 'past the ends pile up there'}. Make the line longer or the letters smaller.")
        return done(objects)
    if kind == "circle" and glyphs and total < 2 * math.pi * radius:
        # Round the whole circle: share the spare room out between the letters.
        extra = (2 * math.pi * radius - total - spacing) / len(glyphs)
        glyphs = [Glyph(g.objects, g.advance + extra) for g in glyphs]
        total = sum(g.advance for g in glyphs) - spacing
    pos = 0.0
    for g in glyphs:
        if kind == "line":
            dx = pos - total / 2
            objects += [_move(o, lambda a, b, dx=dx: (a + dx, b + size / 2)) for o in g.objects]
        else:
            centre = pos + g.advance / 2 - total / 2  # arc length to the letter's middle
            if kind == "arc_down":
                # Letters hang below the circle, reading left to right. Their tops are on the circle,
                # so they're spaced along it there; spaced along the lower baseline, the tops collide.
                r = radius + size
                phi = math.pi / 2 - centre / radius
                rot = phi - math.pi / 2
            else:  # arc_up and circle: letters stand on the circle, reading clockwise from the top
                r = radius
                phi = -math.pi / 2 + centre / r
                rot = phi + math.pi / 2
            cx, cy = r * math.cos(phi), r * math.sin(phi)
            ca, sa = math.cos(rot), math.sin(rot)
            half = g.advance / 2

            def place(a, b, half=half, ca=ca, sa=sa, cx=cx, cy=cy):
                lx = a - half
                return (lx * ca - b * sa + cx, lx * sa + b * ca + cy)

            turn = _Turn(math.degrees(rot))
            objects += [turn_with(_move(o, place), turn) for o in g.objects]
        pos += g.advance
    if kind != "line" and total > 2 * math.pi * radius + 0.5:
        warnings.append("The text is longer than the circle; make the circle bigger or the letters smaller.")
    # Straight text keeps its baseline where it is (names with and without a y or g line up).
    return done(_centre(objects, vertical=kind != "line"))


def _along_path(glyphs: list[Glyph], total: float, size: float, nodes: list, closed: bool) -> tuple[list[dict[str, Any]], float]:
    """Letters standing on a line you drew (its points are in the text's own frame), centred on
    the middle of the line. Not re-centred: the letters stay on the line. Also returns the line's
    length (letters that don't fit sit at its ends).

    A line drawn right to left still reads left to right, upright. On a closed line the letters
    stand outside it, centred at its top."""
    from ..digitize.paths import cumulative, flatten, point_at

    poly, _ = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
    if len(poly) < 2:
        raise LetteringError("Draw a line for the text to follow (at least two points)")
    if closed:
        if _signed_area(poly[:-1]) < 0:
            poly = poly[::-1]
    elif poly[-1][0] < poly[0][0] - 1e-6:
        poly = poly[::-1]
    cum = cumulative(poly)
    length = cum[-1]
    if length < 1.0:
        raise LetteringError("The line is too short for the text to follow; draw a longer line")
    if closed:
        top = min(range(len(poly) - 1), key=lambda i: (poly[i][1], poly[i][0]))
        middle = cum[top]
    else:
        middle = length / 2

    def at(s: float):
        if closed:
            s %= length
        return point_at(poly, cum, min(max(s, 0.0), length))

    objects: list[dict[str, Any]] = []
    pos = 0.0
    for g in glyphs:
        s_mid = middle + (pos + g.advance / 2 - total / 2)
        if not closed:
            s_mid = min(max(s_mid, 0.0), length)
        p = at(s_mid)
        if closed:
            a, b = at(s_mid - 0.5), at(s_mid + 0.5)
        else:
            a, b = at(max(0.0, s_mid - 0.5)), at(min(length, s_mid + 0.5))
        rot = math.atan2(b[1] - a[1], b[0] - a[0])
        ca, sa = math.cos(rot), math.sin(rot)
        half = g.advance / 2

        def place(x, y, half=half, ca=ca, sa=sa, px=p[0], py=p[1]):
            lx = x - half
            return (lx * ca - y * sa + px, lx * sa + y * ca + py)

        turn = _Turn(math.degrees(rot))
        objects += [turn_with(_move(o, place), turn) for o in g.objects]
        pos += g.advance
    return objects, length


def _centre(objects: list[dict[str, Any]], vertical: bool = True) -> list[dict[str, Any]]:
    """Centre the visible letters (not their spacing) on (0, 0), so the text sits where it's placed.
    `vertical=False`: only side to side (the baseline stays put)."""
    pts = [p for o in objects for p in dz.geometry_points(o)]
    if not pts:
        return objects
    x0, y0, x1, y1 = dz.bounds(pts)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 if vertical else 0.0
    return [_move(o, lambda a, b: (a - mx, b - my)) for o in objects]
