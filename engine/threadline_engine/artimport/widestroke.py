"""What lines painted some width wide cover, worked out by GEOS: for strokes too wide for a satin,
which come in as their outline (geometry.stroke_regions). Only shapely is needed, so the child
process that outlines big wide strokes (child.py) starts without the rest of the engine."""

from __future__ import annotations

from typing import Sequence

from shapely.geometry import LinearRing, LineString
from shapely.geometry import Point as SPoint
from shapely.ops import unary_union

from .model import Point


def ring_of(points: Sequence[Point]) -> list[Point]:
    """Points round a ring, without the closing repeat of the first."""
    ring = list(points)
    while len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def union(lines: Sequence[tuple[list[Point], bool]], width: float, cap: str = "butt", join: str = "miter",
          miter_limit: float = 4.0):
    """The area the (points, closed) lines cover painted `width` wide, as one GEOS geometry."""
    caps = {"butt": "flat", "round": "round", "square": "square"}
    joins = {"round": "round", "bevel": "bevel"}
    painted = []
    for points, closed in lines:
        if len(points) < 2:
            if points and cap != "butt":
                painted.append(SPoint(points[0]).buffer(width / 2, quad_segs=16))
            continue
        shape = LinearRing(ring_of(points)) if closed and len(ring_of(points)) >= 3 else LineString(points)
        painted.append(shape.buffer(width / 2, quad_segs=16, cap_style=caps.get(cap, "flat"),
                                    join_style=joins.get(join, "mitre"), mitre_limit=max(1.0, miter_limit)))
    return unary_union(painted)
