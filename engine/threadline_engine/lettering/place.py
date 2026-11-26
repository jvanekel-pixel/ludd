"""Putting the letters together: lines of straight text (or stacked letters), arches, a circle, a
drawn line or a monogram, with a slant and an envelope."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..digitize import stitches as dz
from . import envelope, stitchglyphs
from .fonts import STITCH_FONT_EXTS, LetteringError, _signed_area, resolve_font, substitute_font
from .glyphs import SMALL_TEXT_MM, Glyph, _Missing, _outline_glyphs, _stitch_font_glyphs, small_text_warning

LINE_SPACING = 1.3  # x the letter height, from one line to the next
LINE_SPACING_LIMITS = (0.8, 3.0)
STACK_STEP = 1.15  # x the letter height (plus the letter spacing), from one stacked letter to the next


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
    """Composed accents (e + combining acute -> é); line breaks kept as "\\n" (Windows and old Mac
    ones too); tabs and other breaks as spaces; invisible marks out."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\v\f  ]", " ", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def _number(value: Any, default: float, lo: float, hi: float) -> float:
    """A setting from a project: a number kept within [lo, hi], else the default."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(v, lo), hi) if math.isfinite(v) else default


def _envelope_choice(spec: dict[str, Any], warnings: list[str]) -> tuple[str, float] | None:
    """The text's envelope and how strong it is, or None for none."""
    chosen = spec.get("envelope")
    if not isinstance(chosen, dict) or not chosen.get("type"):
        return None
    if chosen["type"] not in envelope.ENVELOPES:
        warnings.append("This envelope isn't one LUDD knows, so the letters are left straight.")
        return None
    amount = _number(chosen.get("amount"), envelope.DEFAULT_AMOUNT, 0.0, 1.0)
    return (chosen["type"], amount) if amount > 0 else None


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
    from . import monogram as monograms  # here: it uses _move and _centre from this module

    monogram_style = str(spec.get("monogram_style") or "classic")
    # A monogram's side letters are smaller.
    smallest = monograms.smallest_letter(size, monogram_style) if monogram else size
    if smallest < SMALL_TEXT_MM:
        warnings.append(small_text_warning(smallest))

    is_stitch_font = Path(str(font["path"])).suffix.lower() in STITCH_FONT_EXTS
    if is_stitch_font:
        warnings += stitchglyphs.size_notes(str(font["path"]), size)
    slant = _number(spec.get("slant_deg"), 0.0, -envelope.SLANT_LIMIT_DEG, envelope.SLANT_LIMIT_DEG)
    missing = _Missing()
    drawn = 0  # letters that draw something, numbered from 0 in the order they're laid out

    def glyphs_for(t: str, sz: float, line: int = 0) -> list[Glyph]:
        nonlocal drawn
        if is_stitch_font:
            got = _stitch_font_glyphs(t, font["path"], sz, spacing, missing)
            if slant:
                for g in got:
                    g.objects = [envelope.slant_object(o, slant) for o in g.objects]
        else:
            shear = envelope.slant_shape(slant) if slant else None
            got = _outline_glyphs(t, font["path"], int(font.get("index", 0)), sz, spacing, style, missing, shear)
            if slant and style != "fill" and not bend:  # (an envelope chooses the angle again anyway)
                for g in got:
                    g.objects = [envelope.lean_satin_look(o, slant) for o in g.objects]
        for g in got:
            if g.objects:  # each object says which letter it's part of, and on which line (from 0)
                g.objects = [{**o, "letter": drawn, "line": line} for o in g.objects]
                drawn += 1
        return got

    def done(objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        if not objects:
            if missing.left_out:
                raise LetteringError("This font has none of these letters. Pick another font.")
            raise LetteringError("Nothing to stitch: these letters are empty or too small in this font.")
        return objects, warnings + missing.warnings(is_stitch_font)

    bend = _envelope_choice(spec, warnings)

    def bent(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not bend:
            return objects
        # Satin-look letters get their angle chosen again on the new shape; a stitch font's own
        # rows bend with it; woven letters keep their angle.
        angles = "carry" if is_stitch_font else "keep" if style == "fill" else "choose"
        return envelope.bend(objects, bend[0], bend[1], angles)

    if monogram:
        letters = [c for c in text if not c.isspace()]  # line breaks count as spaces
        return done(bent(monograms.layout(letters, size, spacing, glyphs_for, monogram_style)))

    kind = shape.get("type", "line")
    vertical = bool(spec.get("vertical"))
    if kind != "line":
        if vertical:
            warnings.append("Stacked letters only work on straight text, so stacking is left off here.")
        if bend:
            warnings.append("An envelope only works on straight text, so it's left off here.")
        vertical, bend = False, None
    elif vertical and bend:
        warnings.append("Stacked letters can't be bent into an envelope, so the envelope is left off.")
        bend = None
    radius = float(shape.get("radius_mm", 40))
    line_spacing = _number(spec.get("line_spacing"), LINE_SPACING, *LINE_SPACING_LIMITS)
    align = spec.get("align")
    rows = text.split("\n")

    if kind in ("path", "circle"):
        # One line only: the first with anything on it.
        first = next(j for j, row in enumerate(rows) if row.strip())
        if any(row.strip() for row in rows[first + 1:]):
            warnings.append("Text on a circle or a drawn line uses the first line only.")
        glyphs = glyphs_for(rows[first], size, first)
        total = sum(g.advance for g in glyphs) - spacing
        if kind == "path":
            closed = bool(shape.get("closed"))
            objects, length = _along_path(glyphs, total, size, shape.get("nodes") or [], closed)
            if total > length + 0.5:
                warnings.append(f"The text is longer than its line ({total:.0f} mm of letters on {length:.0f} mm), so letters "
                                f"{'overlap' if closed else 'past the ends pile up there'}. Make the line longer or the letters smaller.")
            return done(objects)
        if glyphs and total < 2 * math.pi * radius:
            # Round the whole circle: share the spare room out between the letters.
            extra = (2 * math.pi * radius - total - spacing) / len(glyphs)
            glyphs = [Glyph(g.objects, g.advance + extra) for g in glyphs]
        lines = {first: glyphs}
    else:
        lines = {j: glyphs_for(row, size, j) for j, row in enumerate(rows)}

    if kind == "line":
        if vertical:
            return done(_stacked(lines, size, spacing, line_spacing))
        return done(bent(_straight(lines, size, spacing, line_spacing, align)))
    objects = _arched(lines, kind, radius, size, spacing, line_spacing, align, warnings)
    return done(_centre(objects))


def _inked(lines: dict[int, list[Glyph]]) -> list[int]:
    """The numbers of the lines that draw something: blank lines before the first and after the
    last take no room."""
    return [j for j, glyphs in lines.items() if any(g.objects for g in glyphs)]


def _points(objects: list[dict[str, Any]]) -> list[tuple[float, float]]:
    return [p for o in objects for p in dz.geometry_points(o)]


def _set_line(glyphs: list[Glyph], size: float, spacing: float) -> list[dict[str, Any]]:
    """One line standing on a baseline at y = size / 2, centred by its letters' spacing."""
    total = sum(g.advance for g in glyphs) - spacing
    objects: list[dict[str, Any]] = []
    pos = 0.0
    for g in glyphs:
        dx = pos - total / 2
        objects += [_move(o, lambda a, b, dx=dx: (a + dx, b + size / 2)) for o in g.objects]
        pos += g.advance
    return objects


def _straight(lines: dict[int, list[Glyph]], size: float, spacing: float, line_spacing: float,
              align: Any) -> list[dict[str, Any]]:
    """Straight text. Lines are `line_spacing` letter heights apart (the middle of the block stays
    where one line would be) and line up left, center or right against the widest, by the letters
    you see, which are centred side to side."""
    inked = _inked(lines)
    if not inked:
        return []
    placed = {j: _set_line(lines[j], size, spacing) for j in inked}
    if len(inked) == 1:
        # Straight text keeps its baseline where it is (names with and without a y or g line up).
        return _centre(placed[inked[0]], vertical=False)
    boxes = {j: dz.bounds(_points(placed[j])) for j in inked}
    widest = max(x1 - x0 for x0, _, x1, _ in boxes.values())
    step = line_spacing * size
    lift = (inked[-1] - inked[0]) * step / 2
    objects: list[dict[str, Any]] = []
    for j in inked:
        x0, _, x1, _ = boxes[j]
        across = -widest / 2 - x0 if align == "left" else widest / 2 - x1 if align == "right" else -(x0 + x1) / 2
        down = (j - inked[0]) * step - lift
        objects += [_move(o, lambda a, b, across=across, down=down: (a + across, b + down)) for o in placed[j]]
    return objects


def _stacked(lines: dict[int, list[Glyph]], size: float, spacing: float, line_spacing: float) -> list[dict[str, Any]]:
    """Letters one under another, each centred on its column. Lines are columns, left to right,
    `line_spacing` letter heights apart; they all start level. A space leaves a gap."""
    inked = _inked(lines)
    if not inked:
        return []
    drawn_at = [i for j in inked for i, g in enumerate(lines[j]) if g.objects]
    step = size * STACK_STEP + spacing
    first_baseline = size / 2 - (min(drawn_at) + max(drawn_at)) * step / 2  # the stack's middle stays put
    middle = (inked[0] + inked[-1]) / 2
    objects: list[dict[str, Any]] = []
    for j in inked:
        column = (j - middle) * line_spacing * size
        for i, g in enumerate(lines[j]):
            if not g.objects:
                continue
            x0, _, x1, _ = dz.bounds(_points(g.objects))
            dx, dy = column - (x0 + x1) / 2, first_baseline + i * step
            objects += [_move(o, lambda a, b, dx=dx, dy=dy: (a + dx, b + dy)) for o in g.objects]
    return objects


def _arched(lines: dict[int, list[Glyph]], kind: str, radius: float, size: float, spacing: float, line_spacing: float,
            align: Any, warnings: list[str]) -> list[dict[str, Any]]:
    """Text over the top of a circle ("arc_up", and round a whole "circle") or under the bottom
    ("arc_down"). Further lines go on circles round the same middle, a line spacing further down:
    inside over the top, outside under the bottom. Lines are centred, or start or end together."""
    inked = _inked(lines)
    if not inked:
        return []
    step = line_spacing * size
    inward = kind != "arc_down"
    last = inked[-1] - inked[0]
    if inward and last and radius < last * step + size:
        # The innermost line needs a circle at least a letter across.
        radius = last * step + size
        warnings.append("This curve is too small for this many lines, so it's drawn bigger. Make the curve size "
                        "bigger, or the lines closer.")
    radii = {j: radius + (inked[0] - j if inward else j - inked[0]) * step for j in inked}
    totals = {j: sum(g.advance for g in lines[j]) - spacing for j in inked}
    widest = max(totals[j] / radii[j] for j in inked)  # the angle the longest line covers
    objects: list[dict[str, Any]] = []
    wraps = False
    for j in inked:
        line_radius, total = radii[j], totals[j]
        spare = (widest - total / line_radius) / 2 * line_radius  # from centred to lined up
        shift = -spare if align == "left" else spare if align == "right" else 0.0
        pos = 0.0
        for g in lines[j]:
            centre = pos + g.advance / 2 - total / 2 + shift  # arc length to the letter's middle
            if kind == "arc_down":
                # Letters hang below the circle, reading left to right. Their tops are on the circle,
                # so they're spaced along it there; spaced along the lower baseline, the tops collide.
                r = line_radius + size
                phi = math.pi / 2 - centre / line_radius
                rot = phi - math.pi / 2
            else:  # arc_up and circle: letters stand on the circle, reading clockwise from the top
                r = line_radius
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
        wraps = wraps or total > 2 * math.pi * line_radius + 0.5
    if wraps:
        warnings.append("The text is longer than the circle; make the circle bigger or the letters smaller.")
    return objects


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
