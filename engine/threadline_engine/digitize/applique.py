"""Applique: a piece of fabric sewn on and edged with satin.

The machine sews, in one thread:
1. a placement line (the outline), then stops: lay the fabric piece over it;
2. a tack-down (a narrow zigzag or a straight line) holding the piece, then stops: trim the fabric
   close to the stitching (or skip this if the piece was pre-cut from the SVG cut file);
3. the cover: a satin border over the raw edge.
A piece with holes gets the same three parts round each hole's edge too (all before each stop), and
the cut file has a cutting line for every hole.

Each stop is a STOP command; ties go before and after every stop, because single-needle machines
(the PE550D) cut the thread there. Written for LUDD from first principles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from shapely.geometry import Polygon

from .paths import Point, flatten, resample, sharp_points
from .stitches import (
    FOLD_WARNING,
    LONG_STITCH_MM,
    TRAVEL_STITCH_MM,
    DigitizeError,
    Rec,
    SatinParams,
    _crossing_rungs,
    _finite,
    check_points,
    satin_from_pairs,
    stitch_run,
    tie_in,
    tie_off,
    valid_parts,
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
            cover_width_mm=_finite(d, "cover_width_mm", 3.0),
            cover_spacing_mm=_finite(d, "spacing_mm", _finite(d, "cover_spacing_mm", 0.4)),
            tack=str(d.get("tack", "zigzag")),
            tack_width_mm=_finite(d, "tack_width_mm", 1.5),
            placement=bool(d.get("placement", True)),
        )
        if not 1 <= p.cover_width_mm <= 8:
            raise DigitizeError("The applique border must be between 1 and 8 mm wide")
        if p.tack not in ("zigzag", "run"):
            raise DigitizeError(f"Unknown tack-down: {p.tack}")
        if not 0.5 <= p.tack_width_mm <= 4:
            raise DigitizeError("The tack-down zigzag must be between 0.5 and 4 mm wide")
        if not 0.2 <= p.cover_spacing_mm <= 1.5:
            raise DigitizeError("Border spacing must be between 0.2 and 1.5 mm")
        return p


MIN_PIECE_MM2 = 4.0  # smaller pieces are too small to sew as applique
MIN_HOLE_MM2 = 2.0


def _ccw(coords) -> list[Point]:
    pts = [(float(x), float(y)) for x, y in coords]
    if Polygon(pts).exterior.is_ccw is False:
        pts = pts[::-1]
    return pts


def _pieces(outline: Sequence, holes: Sequence[Sequence] = ()) -> list[Polygon]:
    """The fabric pieces: the outline less its holes, biggest first. An outline that crosses
    itself gives several pieces, and each is sewn (not just the biggest)."""
    try:
        shell, _ = flatten(outline, closed=True)
        hole_rings = [flatten(h, closed=True)[0] for h in holes or [] if len(h) >= 3]
    except (TypeError, ValueError, IndexError):
        raise DigitizeError("This applique has a point that isn't a number") from None
    if len(shell) < 3:
        raise DigitizeError("An applique needs at least three points")
    check_points(shell, "applique")
    parts = [p for p in valid_parts(shell, hole_rings) if p.area >= MIN_PIECE_MM2]
    if not parts:
        raise DigitizeError("This applique shape is too small to sew")
    return parts


def _edges(outline: Sequence, holes: Sequence[Sequence] = ()) -> list[list[Point]]:
    """Every edge of every piece as a dense closed line (counter-clockwise): each piece's outline,
    then its holes."""
    out = []
    for part in _pieces(outline, holes):
        out.append(_ccw(part.exterior.coords))
        out += [_ccw(r.coords) for r in part.interiors if Polygon(r).area >= MIN_HOLE_MM2]
    return out


def _sampled(edge: list[Point], step: float) -> list[Point]:
    """An edge sampled at most `step` apart, with its sharp corners kept."""
    return resample(edge, step, sharp_points(edge))


def outline_ring(outline: Sequence) -> list[Point]:
    """The applique's (biggest piece's) edge as a closed polyline, counter-clockwise, sampled about every mm."""
    return _sampled(_edges(outline)[0], 1.0)


def rings(outline: Sequence, holes: Sequence[Sequence] = ()) -> list[list[Point]]:
    """The pieces' edges as closed polylines (about every mm): each piece's outline, then each
    of its holes."""
    return [_sampled(e, 1.0) for e in _edges(outline, holes)]


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


def _border(edge: list[Point], width: float, spacing: float, pull_comp: float) -> tuple[list[Rec], list[str]]:
    """A satin border `width` wide centred on the edge, its stitches `spacing` apart along it (as
    asked: one stitch per sample of the edge), long stitches split."""
    ring = _sampled(edge, spacing)
    a, b = _offset_rails(ring, width / 2)
    pairs = [((p[0], p[1]), (q[0], q[1])) for p, q in zip(a, b)]
    recs, warnings = satin_from_pairs(pairs, SatinParams(spacing_mm=spacing, pull_comp_mm=pull_comp, underlay=(),
                                                         split_mm=LONG_STITCH_MM))
    corners = {i for i in sharp_points(ring)} | {0, len(ring) - 1}
    if _crossing_rungs(pairs, corners) >= 3:
        warnings.append(FOLD_WARNING)
    return recs, warnings


def applique(outline: Sequence, params: AppliqueParams, holes: Sequence[Sequence] = ()) -> tuple[list[Rec], list[str]]:
    edges = _edges(outline, holes)
    warnings: list[str] = []
    out: list[Rec] = []

    def section(parts: list[list[Rec]], stop_after: bool) -> None:
        for recs in parts:
            recs = tie_off(tie_in(recs))
            if out:  # move (not sew) to where this part starts
                out.append((recs[0][0], recs[0][1], pe.JUMP))
            out.extend(recs)
        if stop_after:
            last = out[-1]
            out.append((last[0], last[1], STOP))

    if params.placement:
        section([stitch_run(_sampled(edge, TRAVEL_STITCH_MM)) for edge in edges], True)

    tacks = []
    for edge in edges:
        if params.tack == "zigzag":
            tacks.append(_border(edge, params.tack_width_mm, 1.2, 0.0)[0])
        else:
            tacks.append(stitch_run(_sampled(edge, 2.0)))
    section(tacks, True)

    covers = []
    for edge in edges:
        cover, cover_warnings = _border(edge, params.cover_width_mm, params.cover_spacing_mm, 0.2)
        warnings += [w for w in cover_warnings if w not in warnings]
        covers.append(cover)
    section(covers, False)
    return out, warnings


def cut_path(outline: Sequence) -> list[Point]:
    """The line to cut the fabric piece on: the placement line."""
    return outline_ring(outline)


def cut_rings(outline: Sequence, holes: Sequence[Sequence] = ()) -> list[list[Point]]:
    """Every line to cut the piece on: its outline and each hole."""
    return rings(outline, holes)
