"""Applique: a piece of fabric sewn on and edged with satin.

The machine sews, in one thread:
1. a placement line (the outline), then stops: lay the fabric piece over it;
2. a tack-down (a narrow zigzag or a straight line) holding the piece, then stops: trim the fabric
   close to the stitching (or skip this if the piece was pre-cut from the SVG cut file);
3. the cover: a satin border over the raw edge.

Each stop is a STOP command; ties go before and after every stop, because single-needle machines
(the PE550D) cut the thread there. Written for LUDD from first principles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from shapely.geometry import Polygon

from .paths import Point, flatten, resample
from .stitches import (
    TRAVEL_STITCH_MM,
    DigitizeError,
    Rec,
    SatinParams,
    satin,
    stitch_run,
    tie_in,
    tie_off,
)
import pyembroidery as pe

STOP = pe.STOP


@dataclass
class AppliqueParams:
    cover_width_mm: float = 3.0  # satin border over the cut edge
    cover_spacing_mm: float = 0.4
    tack: str = "zigzag"  # zigzag | run
    tack_width_mm: float = 1.5
    placement: bool = True  # sew the placement line (off for pre-cut pieces placed by eye)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "AppliqueParams":
        d = d or {}
        p = cls(
            cover_width_mm=float(d.get("cover_width_mm", 3.0)),
            cover_spacing_mm=float(d.get("spacing_mm", d.get("cover_spacing_mm", 0.4))),
            tack=str(d.get("tack", "zigzag")),
            tack_width_mm=float(d.get("tack_width_mm", 1.5)),
            placement=bool(d.get("placement", True)),
        )
        if not 1 <= p.cover_width_mm <= 8:
            raise DigitizeError("The applique border must be between 1 and 8 mm wide")
        if p.tack not in ("zigzag", "run"):
            raise DigitizeError(f"Unknown tack-down: {p.tack}")
        if not 0.2 <= p.cover_spacing_mm <= 1.5:
            raise DigitizeError("Border spacing must be between 0.2 and 1.5 mm")
        return p


def outline_ring(outline: Sequence) -> list[Point]:
    """The applique's edge as a closed polyline, counter-clockwise, sampled about every mm."""
    ring, _ = flatten(outline, closed=True)
    if len(ring) < 3:
        raise DigitizeError("An applique needs at least three points")
    poly = Polygon(ring).buffer(0)
    if poly.is_empty or poly.area < 4:
        raise DigitizeError("This applique shape is too small to sew")
    if poly.geom_type != "Polygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    pts = list(poly.exterior.coords)
    if Polygon(pts).exterior.is_ccw is False:
        pts = pts[::-1]
    return resample(pts, 1.0)


def _offset_rails(ring: list[Point], half: float) -> tuple[list[list], list[list]]:
    """Two rails either side of the closed ring (outside, inside), one rung per ring point."""
    n = len(ring) - 1  # the last point repeats the first
    outer, inner = [], []
    for i in range(n + 1):
        p = ring[i % n]
        a, b = ring[(i - 1) % n], ring[(i + 1) % n]
        # Edge normals either side of the point; for a counter-clockwise ring, (dy, -dx) points out.
        def normal(u: Point, v: Point) -> Point:
            dx, dy = v[0] - u[0], v[1] - u[1]
            ln = math.hypot(dx, dy) or 1.0
            return dy / ln, -dx / ln

        n1, n2 = normal(a, p), normal(p, b)
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        ml = math.hypot(mx, my)
        if ml < 1e-6:
            mx, my, ml = n2[0], n2[1], 1.0
        mx, my = mx / ml, my / ml
        # Mitre: keep the border its full width through corners (capped for very sharp ones).
        cos_half = max(0.5, mx * n2[0] + my * n2[1])
        d = half / cos_half
        outer.append([p[0] + mx * d, p[1] + my * d, "c"])
        inner.append([p[0] - mx * d, p[1] - my * d, "c"])
    return outer, inner


def applique(outline: Sequence, params: AppliqueParams) -> tuple[list[Rec], list[str]]:
    ring = outline_ring(outline)
    warnings: list[str] = []
    out: list[Rec] = []

    def section(recs: list[Rec], stop_after: bool) -> None:
        recs = tie_off(tie_in(recs))
        if out:  # move (not sew) to where this part starts
            out.append((recs[0][0], recs[0][1], pe.JUMP))
        out.extend(recs)
        if stop_after:
            last = recs[-1]
            out.append((last[0], last[1], STOP))

    if params.placement:
        section(stitch_run(resample(ring, TRAVEL_STITCH_MM)), True)

    if params.tack == "zigzag":
        a, b = _offset_rails(ring, params.tack_width_mm / 2)
        tack, _ = satin(a, b, SatinParams(spacing_mm=1.2, pull_comp_mm=0, underlay=()))
    else:
        tack = stitch_run(resample(ring, 2.0))
    section(tack, True)

    a, b = _offset_rails(ring, params.cover_width_mm / 2)
    cover, cover_warnings = satin(a, b, SatinParams(spacing_mm=params.cover_spacing_mm, pull_comp_mm=0.2, underlay=()))
    warnings += cover_warnings
    section(cover, False)
    return out, warnings


def cut_path(outline: Sequence) -> list[Point]:
    """The line to cut the fabric piece on: the placement line."""
    return outline_ring(outline)
