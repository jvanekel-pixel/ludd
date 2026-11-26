"""Monogram frames, built as ordinary line objects (P5-D2), so "Break into shapes" hands them
over as lines you can edit.

Each is centred on the monogram's box and keeps `margin_mm` between the letters and the
frame's inner edge: a circle, two circles, a diamond, a square, a circle of scallops, or a
laurel (two leafy branches, open at the top)."""

from __future__ import annotations

import math
from typing import Any, Sequence

from ..digitize import stitches as dz
from ..digitize.paths import Point
from .fonts import LetteringError

FRAMES = ("circle", "double_circle", "diamond", "square", "scallop_circle", "laurel")
MARGIN_MM = 4.0
MARGINS_MM = (2.0, 15.0)
DOUBLE_GAP_MM = 2.0
SCALLOP_REPEAT_MM = 5.0
SCALLOP_WIDTH_MM = 3.0  # the scallop motif reaches a quarter of this either side of its circle
LAUREL_TOP_OPEN_DEG = 35  # the gap at the top, each side of straight up
LAUREL_BOTTOM_OPEN_DEG = 8
CIRCLE_POINTS = 16  # enough smooth points for a round circle that's still easy to edit
STITCH_MM = 2.5


def frame(points: Sequence[Point], ornament: dict[str, Any]) -> list[dict[str, Any]]:
    """The frame round `points` (the monogram's letters, mm), as line objects in sewing order."""
    ident = ornament.get("id")
    if ident not in FRAMES:
        raise LetteringError(f"This LUDD doesn't have the monogram frame “{ident}”")
    margin = min(max(dz._finite(ornament, "margin_mm", MARGIN_MM), MARGINS_MM[0]), MARGINS_MM[1])
    if not points:
        return []
    x0, y0, x1, y1 = dz.bounds(points)
    cx, cy = round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)
    off = [(x - cx, y - cy) for x, y in points]
    farthest = max(math.hypot(x, y) for x, y in off)
    thread = dict(ornament["thread"]) if isinstance(ornament.get("thread"), dict) else None

    def line(nodes: list, closed: bool = True, **params: Any) -> dict[str, Any]:
        return {"kind": "run", "geometry": {"nodes": nodes, "closed": closed},
                "params": params or {"style": "triple", "stitch_mm": STITCH_MM}, "extra": "frame", "thread": thread}

    def motif(name: str, repeat: float, width: float, nodes: list, closed: bool) -> dict[str, Any]:
        return line(nodes, closed, style="motif", motif=name, motif_mm=repeat, motif_width_mm=width,
                    stitch_mm=STITCH_MM)

    def at(radius: float, degrees: float, kind: str = "s") -> list:
        a = math.radians(degrees)  # y is down: 0 is right, 90 straight down, 270 straight up
        return [round(cx + radius * math.cos(a), 3), round(cy + radius * math.sin(a), 3), kind]

    def circle(radius: float, clockwise: bool = True) -> list:
        turn = 360 / CIRCLE_POINTS * (1 if clockwise else -1)
        return [at(radius, k * turn) for k in range(CIRCLE_POINTS)]  # both start at the right

    def corners(pts: list[Point]) -> list:
        return [[round(cx + x, 3), round(cy + y, 3), "c"] for x, y in pts]

    if ident == "circle":
        return [line(circle(farthest + margin))]
    if ident == "double_circle":
        return [line(circle(farthest + margin)), line(circle(farthest + margin + DOUBLE_GAP_MM))]
    if ident == "square":
        h = max(max(abs(x), abs(y)) for x, y in off) + margin
        return [line(corners([(h, -h), (h, h), (-h, h), (-h, -h)]))]
    if ident == "diamond":
        # A square on its point: a point (x, y) is (d - |x| - |y|) / sqrt(2) inside its edge.
        d = max(abs(x) + abs(y) for x, y in off) + margin * math.sqrt(2)
        return [line(corners([(d, 0), (0, d), (-d, 0), (0, -d)]))]
    if ident == "scallop_circle":
        # Sewn anticlockwise on screen, so the scallops' bumps point outwards.
        radius = farthest + margin + SCALLOP_WIDTH_MM / 4
        return [motif("scallop", SCALLOP_REPEAT_MM, SCALLOP_WIDTH_MM, circle(radius, clockwise=False), True)]
    # Laurel: a branch up each side, from near the bottom, its leaves pointing up.
    width = round(min(max((farthest + margin) * 0.2, 3.0), 6.0), 2)
    repeat = round(min(max(width * 1.35, 4.0), 8.0), 2)
    radius = farthest + margin + width / 2
    start, end = 90 + LAUREL_BOTTOM_OPEN_DEG, 270 - LAUREL_TOP_OPEN_DEG
    steps = math.ceil((end - start) / 15)
    left = [start + (end - start) * k / steps for k in range(steps + 1)]
    branches = [left, [180 - a for a in left]]  # the right branch mirrors the left one
    return [motif("leaf", repeat, width, [at(radius, a) for a in branch], False) for branch in branches]
