"""The spiral fill: one line that winds from the middle of a shape out to its edge.

An Archimedean spiral, its rings `spiral_mm` apart, is drawn round the middle of the shape's
widest spot and cut to the shape. Each stretch of it inside the shape is one path, in order from
the middle out; the fill sews them one after another, travelling inside the shape in between. On
the tight turns near the middle the needle goes down more often, so a stitch doesn't cut far
across the curve.

Written from first principles for LUDD. Coordinates are mm. Imports from `..stitches` stay inside
the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import LineString

from ..paths import Point, dist
from . import FillPattern, Param, register

SAMPLE_MM = 0.5  # how finely the spiral is drawn before it's cut to the shape
CLIP_SAMPLES = 500  # samples cut at a time: ordering the cuts of a whole big spiral at once is slow
SHORTEST_PIECE_MM = 1.0  # stretches inside the shape no longer than this are left out
SHORTEST_STITCH_MM = 0.8  # the stitch length aimed for on the tightest turns
SAG_MM = 0.15  # on a circle of radius r, a stitch 2 * sqrt(2 * SAG_MM * r) long cuts this far inside it
TIGHT_MM = 0.6  # rings closer than this get a warning
TIGHT_WARNING = "Rings this close sew like a solid fill and can pucker in the middle; 1 mm or more is safer."


def _middle(shape) -> Point:
    """The middle of the shape's widest spot: the center of the biggest circle that fits inside."""
    if hasattr(shapely, "maximum_inscribed_circle"):  # shapely 2.1 and later
        x, y = shapely.maximum_inscribed_circle(shape).coords[0]
        return x, y
    p = shape.representative_point()
    return p.x, p.y


def _spiral(middle: Point, spacing: float, reach: float) -> list[Point]:
    """Points every SAMPLE_MM along a spiral round `middle` with rings `spacing` apart, from half a
    ring out until it's further than `reach` from the middle."""
    a = spacing / (2 * math.pi)  # the radius is a * theta
    r = spacing / 2
    theta = r / a
    points = [(middle[0] + r * math.cos(theta), middle[1] + r * math.sin(theta))]
    while r <= reach:
        theta += SAMPLE_MM / math.hypot(r, a)
        r = a * theta
        points.append((middle[0] + r * math.cos(theta), middle[1] + r * math.sin(theta)))
    return points


def _clip(spiral: list[Point], shape):
    """The parts of the spiral inside the shape as lists of points, in order from the middle out."""
    for first in range(0, len(spiral) - 1, CLIP_SAMPLES):
        line = LineString(spiral[first : first + CLIP_SAMPLES + 1])
        inside = [g for g in shapely.get_parts(line.intersection(shape)) if g.geom_type == "LineString" and g.length > 0]
        if not inside:
            continue
        # The overlay promises neither an order nor a direction: find where on the line each one lies.
        ends = shapely.line_locate_point(line, [shapely.get_point(g, i) for g in inside for i in (0, -1)])
        placed = sorted((min(s, e), list(g.coords)[:: 1 if s <= e else -1])
                        for g, s, e in zip(inside, ends[::2], ends[1::2]))
        yield from (points for _, points in placed)


def _pieces(spiral: list[Point], shape) -> list[list[Point]]:
    """The stretches of the spiral inside the shape that are worth sewing, from the middle out."""
    from ..stitches import MIN_STITCH_MM

    joined: list[list[Point]] = []
    for points in _clip(spiral, shape):
        # Parts less than a stitch apart are one stretch: cut in two where one clip ends and the
        # next begins, or by the spiral grazing an edge. (Travelling across so small a gap would
        # make a stitch too short to keep.)
        if joined and dist(joined[-1][-1], points[0]) < MIN_STITCH_MM:
            joined[-1] += points
        else:
            joined.append(points)
    return [p for p in joined if LineString(p).length > SHORTEST_PIECE_MM]


def _stitch_length(radius: float, stitch_mm: float) -> float:
    """The stitch to aim for where the spiral is `radius` from its middle: short on the tight turns,
    longer as they open out, never more than the fill's `stitch_mm`."""
    return min(max(2 * math.sqrt(2 * SAG_MM * radius), SHORTEST_STITCH_MM), stitch_mm)


def _needle_points(piece: list[Point], middle: Point, stitch_mm: float) -> list[Point]:
    """Needle drops along a piece of the spiral. Each goes exactly where the length since the one
    before reaches the stitch to aim for (not on the next sample, which could be 0.5 mm further).
    The last is the end of the piece, unless that's too close for a stitch."""
    from ..stitches import MIN_STITCH_MM

    out = [piece[0]]
    want = _stitch_length(dist(middle, piece[0]), stitch_mm)
    since = 0.0  # how far along the piece since the last needle drop
    for a, b in zip(piece, piece[1:]):
        step = dist(a, b)
        done = 0.0  # how much of this step has been walked
        while since + step - done >= want:
            done += want - since
            t = done / step
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            since = 0.0
            want = _stitch_length(dist(middle, out[-1]), stitch_mm)
        since += step - done
    if dist(out[-1], piece[-1]) >= MIN_STITCH_MM:
        out.append(piece[-1])
    return out


def _spiral_paths(poly, params, pos):
    """The spiral over one piece of a fill, as paths from the middle out. `pos`, where the fill was
    asked to start, isn't used: a spiral starts in the middle."""
    from ..stitches import MIN_STITCH_MM

    spacing = params.value("spiral_mm")
    warnings = [TIGHT_WARNING] if spacing < TIGHT_MM else []
    # Worked out with the shape's bounds starting at (0, 0), rounded to a millionth of a mm, so a
    # moved or copied shape gets exactly the same spiral. Where several spots are equally wide, the
    # last-digit noise that moving leaves behind could otherwise pick another middle.
    x0, y0 = poly.bounds[:2]
    local = shapely.transform(poly, lambda xy: np.round(xy - (x0, y0), 6))
    middle = _middle(local)
    reach = max(dist(middle, p) for p in local.exterior.coords) + spacing
    paths: list[list[Point]] = []
    for piece in _pieces(_spiral(middle, spacing, reach), local):
        points = _needle_points(piece, middle, params.stitch_mm)
        if paths and dist(paths[-1][-1], points[0]) < MIN_STITCH_MM:
            points = points[1:]  # already there
        if points:
            paths.append(points)
    return [[(x + x0, y + y0) for x, y in path] for path in paths], warnings


register(FillPattern("spiral", "open", params={"spiral_mm": Param(1.5, 0.4, 6.0, "Ring spacing")}, paths=_spiral_paths,
                     step_mm2=lambda p: p.value("spiral_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
