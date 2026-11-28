"""Buttonholes and eyelets: ordinary shapes made from a few sizes, so they can be reshaped like
any others (there is no new object kind). Each comes back centered on the place asked for, turned
by `angle_deg` (at 0 the slit lies level), as {objects, warnings}; the objects have no thread or id
(the app gives them its own).

A bar buttonhole is two satin lips the length of the buttonhole with the cut gap between them, sewn
down one and back up the other, then a bar tack across each end, covering the lips' last 1.5 mm.
So the slit between the tacks is the length less 3 mm. The lips hand over under one tack: the
first stops, and the second starts, a little in from that end (their green and red dots), so the
thread crosses the gap where the tack then covers it, with no jump. A rounded buttonhole is one
satin ribbon round a slot with round ends. An eyelet is a triple run just outside the hole, then a
satin ring from the hole's edge outward.

Written from first principles for LUDD. Coordinates are mm. Imports from `.stitches` stay inside
the function bodies.
"""

from __future__ import annotations

import math
from typing import Any

BUTTONHOLE_STYLES = ("bar", "round")
TACK_MM = 1.5  # how long, along the buttonhole, a bar tack is
HAND_OVER_MM = 1.0  # the lips hand over this far in from the end, under the middle of its tack
LIP_MIN_MM = 1.0
RUN_OUTSIDE_MM = 0.3  # an eyelet's run goes round this far outside the hole
RUN_STITCH_MM = 1.5  # short enough that a 2 mm hole's run stays outside it
FARTHEST_MM = 10_000.0  # far past any hoop: a place beyond it is a typing slip


def _size(value: Any, what: str, lo: float, hi: float) -> float:
    from .stitches import DigitizeError

    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise DigitizeError(f"{what} must be between {lo:g} and {hi:g} mm")
    return float(value)


def _numbers(values: Any, n: int, refusal: str) -> list[float]:
    from .stitches import DigitizeError

    if not (isinstance(values, (list, tuple)) and len(values) == n and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and -FARTHEST_MM <= v <= FARTHEST_MM
            for v in values)):
        raise DigitizeError(refusal)
    return [float(v) for v in values]


class _Placed:
    """Points drawn about (0, 0), turned and moved to the shape's place."""

    def __init__(self, angle_deg: Any, at: Any):
        (angle,) = _numbers([angle_deg], 1, "The angle must be a number")
        self.x, self.y = _numbers([0, 0] if at is None else at, 2, "The place must be two numbers")
        self.cos, self.sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def point(self, x: float, y: float) -> list[float]:
        return [round(x * self.cos - y * self.sin + self.x, 4) + 0.0,
                round(x * self.sin + y * self.cos + self.y, 4) + 0.0]

    def node(self, x: float, y: float, kind: str = "c") -> list:
        return [*self.point(x, y), kind]


def _satin(name: str, nodes: list, width: float, params: dict, closed: bool = False) -> dict:
    geometry = {"nodes": nodes, "width_mm": round(width, 4), **({"closed": True} if closed else {})}
    return {"kind": "satin", "name": name, "geometry": geometry, "params": {"spacing_mm": 0.4, **params}}


def _circle(placed: _Placed, radius: float) -> list:
    """A circle as eight curve points, clockwise on screen from its right (as the Shapes menu's)."""
    return [placed.node(radius * math.cos(math.pi * k / 4), radius * math.sin(math.pi * k / 4), "s")
            for k in range(8)]


def _bar(placed: _Placed, length: float, width: float, cut: float, lip: float) -> list[dict]:
    half, middle = length / 2, cut / 2 + lip / 2  # the lips' middle lines are this far from the slit's
    over = half - HAND_OVER_MM
    lips = [
        # Both lips have both dots, so Optimize jumps leaves their handover as it is.
        _satin("Buttonhole lip 1", [placed.node(-half, -middle), placed.node(half, -middle, "l")], lip,
               {"underlay": ["center"], "start_mm": placed.point(-half, -middle),
                "end_mm": placed.point(over, -cut / 2)}),
        _satin("Buttonhole lip 2", [placed.node(half, middle), placed.node(-half, middle, "l")], lip,
               {"underlay": ["center"], "start_mm": placed.point(over, cut / 2),
                "end_mm": placed.point(-half, width / 2)}),
    ]
    tack_at = half - TACK_MM / 2
    tacks = [
        _satin("Buttonhole bar 1", [placed.node(-tack_at, width / 2), placed.node(-tack_at, -width / 2, "l")],
               TACK_MM, {"underlay": []}),
        _satin("Buttonhole bar 2", [placed.node(tack_at, -width / 2), placed.node(tack_at, width / 2, "l")],
               TACK_MM, {"underlay": []}),
    ]
    return [*lips, *tacks]


def _rounded(placed: _Placed, length: float, width: float, cut: float, lip: float) -> list[dict]:
    radius = cut / 2 + lip / 2  # the middle line's round ends; its straight sides are this far out
    reach = length / 2 - width / 2  # where the round ends are centered
    if reach <= 1e-6:
        nodes = _circle(placed, radius)
    else:
        # As the rounded rectangle: a straight side runs into each end's first point ("l"), curve
        # points go round it, and the next side leaves straight from where it ends ("c").
        nodes = [placed.node(side * reach + radius * math.cos(math.radians(start + 22.5 * k)),
                             radius * math.sin(math.radians(start + 22.5 * k)),
                             "l" if k == 0 else "c" if k == 8 else "s")
                 for side, start in ((1, -90), (-1, 90)) for k in range(9)]
    return [_satin("Rounded buttonhole", nodes, lip, {"underlay": ["center"]}, closed=True)]


def buttonhole(length_mm: Any = 16, width_mm: Any = 5, style: Any = "bar", cut_gap_mm: Any = 1.0,
               angle_deg: Any = 0, at: Any = None) -> dict[str, Any]:
    """A buttonhole `length_mm` long and `width_mm` wide, its slit `cut_gap_mm` wide."""
    from .stitches import DigitizeError

    if style not in BUTTONHOLE_STYLES:
        raise DigitizeError(f"Unknown buttonhole style: {style}")
    length = _size(length_mm, "Length", 8, 40)
    width = _size(width_mm, "Width", 3, 8)
    cut = _size(cut_gap_mm, "Cut gap", 0.6, 2)
    lip = (width - cut) / 2
    if lip < LIP_MIN_MM - 1e-9:
        raise DigitizeError("Make the buttonhole wider or the cut narrower")
    make = _bar if style == "bar" else _rounded
    return {"objects": make(_Placed(angle_deg, at), length, width, cut, lip), "warnings": []}


def eyelet(hole_mm: Any = 4, ring_mm: Any = 1.6, at: Any = None) -> dict[str, Any]:
    """An eyelet round a hole `hole_mm` across, its satin ring `ring_mm` wide."""
    from .stitches import FOLD_WARNING

    hole = _size(hole_mm, "Hole", 2, 12)
    ring = _size(ring_mm, "Ring", 1, 3)
    placed = _Placed(0, at)
    run = {"kind": "run", "name": "Eyelet run",
           "geometry": {"nodes": _circle(placed, hole / 2 + RUN_OUTSIDE_MM), "closed": True},
           "params": {"style": "triple", "stitch_mm": RUN_STITCH_MM}}
    satin = _satin("Eyelet ring", _circle(placed, hole / 2 + ring / 2), ring, {"underlay": []}, closed=True)
    # A ring wider than its hole curves more tightly than it is wide: it bunches up inside.
    return {"objects": [run, satin], "warnings": [FOLD_WARNING] if ring > hole + 1e-9 else []}
