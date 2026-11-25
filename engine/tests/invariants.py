"""Checks every stitch type must pass, so a reviewer reads numbers, not code.

Records are what generate() returns: (x, y, command), in mm. A stitch line is the thread between
two needle drops in a row (a stitch right after a stitch).
"""

import math

import shapely
from shapely.geometry import LineString, Point

from threadline_engine.digitize.applique import STOP
from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM, generate, transform_geometry

_COMMANDS = (STITCH, JUMP, TRIM, STOP)


def stitch_points(recs) -> list[tuple[float, float]]:
    """Where the needle goes down."""
    return [(r[0], r[1]) for r in recs if r[2] == STITCH]


def count(recs, kind) -> int:
    return sum(1 for r in recs if r[2] == kind)


def _longest(recs) -> tuple[float, int]:
    """The longest needle move that ends in a stitch, and the index of that stitch."""
    return max(((math.dist(a[:2], b[:2]), i) for i, (a, b) in enumerate(zip(recs, recs[1:]), 1) if b[2] == STITCH),
               default=(0.0, 0))


def longest_stitch(recs) -> float:
    """The longest needle move that ends in a stitch, from the record before it: the stitch
    before, or where a jump landed."""
    return _longest(recs)[0]


def _stitch_lines(recs) -> list[LineString]:
    return [LineString([a[:2], b[:2]]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH and a[:2] != b[:2]]


def _outside(recs, area, tolerance_mm: float) -> list[str]:
    """What sews more than `tolerance_mm` outside `area`: needle drops, and the thread between
    them (which can cross a hole or a notch while both its ends are inside)."""
    zone = area.buffer(tolerance_mm)
    shapely.prepare(zone)
    shapes = [Point(p) for p in stitch_points(recs)] + _stitch_lines(recs)
    out = [g for g, inside in zip(shapes, shapely.covers(zone, shapes)) if not inside]
    if not out:
        return []
    samples = [p for g in out for p in ([g] if g.geom_type == "Point" else
                                        [g.interpolate(k / 100, normalized=True) for k in range(101)])]
    far, worst = max(((area.distance(p), p) for p in samples), key=lambda pair: pair[0])
    drops = sum(1 for g in out if g.geom_type == "Point")
    return [f"{drops} stitch(es) and {len(out) - drops} stitch line(s) outside the shape, up to {far:.2f} mm out "
            f"near ({worst.x:.2f}, {worst.y:.2f}) (tolerance {tolerance_mm} mm)"]


def assert_sane(recs, *, inside=None, tolerance_mm=0.6, max_stitch_mm=7.15, max_jumps=None, max_trims=None,
                starts_near=None, ends_near=None, near_mm=1.0) -> None:
    """Fail, naming every broken rule with its numbers, unless: there are stitches; every record
    is a known command at a finite point; no stitch is longer than max_stitch_mm; every stitch
    and stitch line stays within tolerance_mm of `inside` (a shapely area), when given; there are
    at most max_jumps jumps and max_trims trims, when given; and the first and last needle drops
    are within near_mm of starts_near and ends_near, when given."""
    recs = list(recs)
    lost = [i for i, r in enumerate(recs) if not (math.isfinite(r[0]) and math.isfinite(r[1]))]
    if lost:
        raise AssertionError(f"record {lost[0]} is not a number: {recs[lost[0]]} ({len(lost)} like it)")
    points = stitch_points(recs)
    if not points:
        raise AssertionError(f"no stitches in {len(recs)} records")
    problems = []
    unknown = [i for i, r in enumerate(recs) if r[2] not in _COMMANDS]
    if unknown:
        problems.append(f"unknown command {recs[unknown[0]][2]} at record {unknown[0]} ({len(unknown)} like it)")
    length, i = _longest(recs)
    if length > max_stitch_mm + 1e-9:
        x, y = recs[i][:2]
        problems.append(f"longest stitch {length:.2f} mm at record {i} (limit {max_stitch_mm} mm), "
                        f"ending at ({x:.2f}, {y:.2f})")
    if inside is not None:
        problems += _outside(recs, inside, tolerance_mm)
    for kind, name, limit in ((JUMP, "jumps", max_jumps), (TRIM, "trims", max_trims)):
        n = count(recs, kind)
        if limit is not None and n > limit:
            problems.append(f"{n} {name} (limit {limit})")
    for word, point, near in (("starts", points[0], starts_near), ("ends", points[-1], ends_near)):
        if near is not None and math.dist(point, near) > near_mm:
            problems.append(f"{word} {math.dist(point, near):.2f} mm from {tuple(near)}, at "
                            f"({point[0]:.2f}, {point[1]:.2f}) (limit {near_mm} mm)")
    if problems:
        raise AssertionError("; ".join(problems))


def assert_deterministic(make) -> None:
    """make() twice gives identical records (the same design always sews the same)."""
    first, second = list(make()), list(make())
    if len(first) != len(second):
        raise AssertionError(f"not deterministic: {len(first)} records, then {len(second)}")
    for i, (a, b) in enumerate(zip(first, second)):
        if a != b:
            raise AssertionError(f"not deterministic: record {i} was {a}, then {b}")


def assert_moves_with_shape(obj, dx, dy) -> None:
    """The stitches of `obj` moved by (dx, dy) are its stitches moved the same, to 0.01 mm."""
    from threadline_engine.layout import Transform

    before = generate(obj)[0]
    after = generate(transform_geometry(obj, Transform.from_dict({"x": dx, "y": dy}), (0.0, 0.0)))[0]
    if len(before) != len(after):
        raise AssertionError(f"didn't move with the shape: {len(before)} records before, {len(after)} after "
                             f"moving it by ({dx}, {dy})")
    for i, (a, b) in enumerate(zip(before, after)):
        want = (a[0] + dx, a[1] + dy)
        if a[2] != b[2] or math.dist(want, b[:2]) > 0.01 + 1e-9:
            raise AssertionError(f"didn't move with the shape: record {i} should be ({want[0]:.3f}, {want[1]:.3f}, "
                                 f"command {a[2]}) but is ({b[0]:.3f}, {b[1]:.3f}, command {b[2]})")


def coverage(recs, poly, reach_mm) -> float:
    """The share of `poly` (a shapely area) within reach_mm of a stitch line."""
    lines = _stitch_lines(recs)
    if not lines or not poly.area:
        return 0.0
    reached = shapely.union_all(shapely.buffer(lines, reach_mm))
    return min(1.0, reached.intersection(poly).area / poly.area)


def thread_per_mm2(recs, poly) -> float:
    """mm of thread laid inside `poly` for each mm² of it, every pass counted."""
    lines = _stitch_lines(recs)
    if not lines or not poly.area:
        return 0.0
    # Clipped one stitch line at a time: clipping them together would merge passes on top of each other.
    return float(shapely.length(shapely.intersection(lines, poly)).sum()) / poly.area
