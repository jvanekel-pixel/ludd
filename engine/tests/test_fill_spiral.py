"""The spiral fill: one line that winds from the middle of a shape out to its edge
(digitize/fills/spiral.py)."""

import math
import statistics

import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import invariants
from snapshot_util import check, digest_recs
from threadline_engine import project
from threadline_engine.digitize import fills
from threadline_engine.digitize.stitches import (MIN_STITCH_MM, STITCH, DigitizeError, FillParams, fill_parts,
                                                 fill_polygon, generate)

MIDDLE = (20.0, 20.0)  # of the 40 mm square
STITCH_MM = 3.5  # the standard fill stitch length
TIGHT = "Rings this close sew like a solid fill and can pucker in the middle; 1 mm or more is safer."


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


def _round(r, n=96, middle=MIDDLE):
    return _nodes((middle[0] + r * math.cos(2 * math.pi * i / n), middle[1] + r * math.sin(2 * math.pi * i / n))
                  for i in range(n))


SQUARE = _nodes([(0, 0), (40, 0), (40, 40), (0, 40)])
HOLE = _nodes([(14, 14), (26, 14), (26, 26), (14, 26)])
STAR = _nodes((20 + r * math.cos(-math.pi / 2 + math.pi * k / 5), 20 + r * math.sin(-math.pi / 2 + math.pi * k / 5))
              for k, r in enumerate([20, 9] * 5))
# Shapes that are awkward for a spiral: (outline, holes).
_LOBES = unary_union([box(0, 0, 24, 24), box(24, 11, 32, 13), box(32, 4, 48, 20)])
ODD = {
    "thin_ring": (_round(15), [_round(13)]),  # a 2 mm band round an empty middle
    "star": (STAR, []),
    "two_lobes": (_nodes(list(_LOBES.exterior.coords)[:-1]), []),  # joined by a neck 2 mm wide
    "narrow_strip": (_nodes([(0, 0), (40, 0), (40, 1.3), (0, 1.3)]), []),  # narrower than the first turn
}


def _spiral(outline=SQUARE, holes=(), **params):
    """A spiral fill with no underlay (which is what Auto gives it) and any other settings."""
    return {"kind": "fill", "geometry": {"outline": outline, "holes": list(holes)},
            "params": {"pattern": "spiral", "underlay": [], **params}}


def _recs(outline=SQUARE, holes=(), **params):
    return generate(_spiral(outline, holes, **params))[0]


def _area(obj):
    g = obj["geometry"]
    return unary_union(fill_parts(g["outline"], g.get("holes") or []))


def _threads(recs):
    """The thread between two needle drops in a row, as (from, to)."""
    return [(a[:2], b[:2]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]


def test_spiral_is_registered_as_open():
    assert fills.get("spiral").kind == "open"


def test_square_is_one_line_from_the_middle():
    obj = _spiral()
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05,
                           max_jumps=0, max_trims=0, starts_near=MIDDLE, near_mm=1.5)


@pytest.mark.parametrize("start", [(0, 0), (40, 40), (20, -5), (-30, 21)])
def test_it_starts_in_the_middle_wherever_the_start_point_is(start):
    """The green start dot (and Optimize jumps) set start_mm; a spiral still sews from the middle out."""
    recs = _recs(start_mm=list(start))
    assert math.dist(recs[0][:2], MIDDLE) <= 1.5
    assert recs == _recs()


@pytest.mark.parametrize("spacing", [1.5, 3.0])
def test_rings_are_evenly_spaced(spacing):
    # The ray to the right of the middle. It stops just short of the edge, where travel runs along it.
    ray = LineString([MIDDLE, (39.8, 20.0)])
    hits = []
    for a, b in _threads(_recs(spiral_mm=spacing)):
        cross = ray.intersection(LineString([a, b]))
        if not cross.is_empty:
            assert cross.geom_type == "Point", cross
            hits.append(math.dist(MIDDLE, (cross.x, cross.y)))
    hits.sort()
    # A needle drop right on the ray belongs to both its stitches: count it once.
    rings = [h for i, h in enumerate(hits) if i == 0 or h - hits[i - 1] > 0.05]
    assert len(rings) == int(19.8 / spacing)
    gaps = [b - a for a, b in zip(rings, rings[1:])]
    assert all(abs(gap - spacing) <= 0.15 for gap in gaps), gaps


def test_it_reaches_the_corners():
    """Measured to the thread. The last turn into a corner is a short arc with its needle drops where
    it meets the two edges, further from the corner than the thread across it is."""
    threads = [LineString([a, b]) for a, b in _threads(_recs())]
    for corner in [(0, 0), (40, 0), (40, 40), (0, 40)]:
        assert min(Point(corner).distance(thread) for thread in threads) <= 1.5 + 0.5, corner


def test_short_stitches_near_the_middle_long_ones_outside():
    threads = _threads(_recs(tie_in=False, tie_off=False))
    sizes = [(math.dist(a, b), math.dist(MIDDLE, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))) for a, b in threads]
    near = [size for size, away in sizes if away <= 3]
    far = [size for size, away in sizes if away > 15]
    assert near and far
    assert statistics.mean(near) < statistics.mean(far)
    assert min(size for size, _ in sizes) >= MIN_STITCH_MM


def test_a_hole_stays_empty():
    recs = _recs(holes=[HOLE])
    inner = Polygon([(x, y) for x, y, _ in HOLE]).buffer(-0.3)
    assert not any(inner.contains(Point(p)) for p in invariants.stitch_points(recs))
    assert not any(inner.intersects(LineString([a, b])) for a, b in _threads(recs))


@pytest.mark.parametrize("spacing", [0.2, 0.39, 6.01, 20])
def test_ring_spacing_is_checked(spacing):
    with pytest.raises(DigitizeError, match="^Ring spacing must be between 0.4 and 6 mm$"):
        generate(_spiral(spiral_mm=spacing))


def test_ring_spacing_defaults_to_one_and_a_half():
    assert FillParams.from_dict({"pattern": "spiral"}).value("spiral_mm") == 1.5
    assert FillParams.from_dict({"pattern": "spiral", "spiral_mm": 6}).value("spiral_mm") == 6


def test_tight_rings_warn():
    assert TIGHT in generate(_spiral(spiral_mm=0.5))[1]
    assert generate(_spiral(spiral_mm=0.6))[1] == []
    # Said once, even when the shape is in two pieces.
    bowtie = _nodes([(0, 0), (20, 20), (20, 0), (0, 20)])
    assert generate(_spiral(bowtie, spiral_mm=0.5))[1].count(TIGHT) == 1


@pytest.mark.parametrize("level", [None, "light", "normal", "heavy"])
def test_no_underlay_on_automatic(level):
    auto = {"underlay": "auto", **({"underlay_level": level} if level else {})}
    assert FillParams.from_dict({"pattern": "spiral", **auto}).underlay == ()
    recs = _recs(**auto)
    assert math.dist(recs[0][:2], MIDDLE) <= 1.5
    assert recs == _recs(underlay=[])


def test_an_edge_run_can_still_be_picked():
    recs = _recs(underlay=["edge"])
    assert Point(recs[0][:2]).distance(box(0, 0, 40, 40).exterior) <= 0.6  # the edge run comes first
    assert len(invariants.stitch_points(recs)) > len(invariants.stitch_points(_recs()))


@pytest.mark.parametrize("name,outline,holes", [
    ("square", SQUARE, []),
    ("donut", SQUARE, [HOLE]),  # four equally wide corners to put the middle in
    ("flat", _nodes([(0, 0), (40, 0), (40, 12), (0, 12)]), []),  # a whole line of equally wide spots
    ("star", STAR, []),
])
def test_moves_with_the_shape(name, outline, holes):
    for dx, dy in [(10, -7.5), (0.1234, 33.333), (-250.7, 1000.9)]:
        invariants.assert_moves_with_shape(_spiral(outline, holes), dx, dy)


@pytest.mark.parametrize("obj", [_spiral(), _spiral(holes=[HOLE]), _spiral(STAR)], ids=["square", "donut", "star"])
def test_deterministic(obj):
    invariants.assert_deterministic(lambda: generate(obj)[0])


@pytest.mark.parametrize("spacing", [0.4, 0.9, 1.5, 6.0])
@pytest.mark.parametrize("stitch_mm", [1.0, 1.3, 2.2, 3.4, 3.5, 4.0, 8.0])
@pytest.mark.parametrize("name", ["square", *ODD])
def test_needle_points_stay_inside_and_within_the_stitch_length(name, stitch_mm, spacing):
    """The spiral's own stitches (travel between its pieces has its own length, up to 2.5 mm)."""
    outline, holes = ODD.get(name, (SQUARE, []))
    shape = fill_polygon(outline, holes)
    params = FillParams.from_dict({"pattern": "spiral", "spiral_mm": spacing, "stitch_mm": stitch_mm})
    paths, _ = fills.get("spiral").paths(shape, params, (0.0, 0.0))
    assert paths
    steps = [math.dist(a, b) for path in paths for a, b in zip(path, path[1:])]
    assert max(steps) <= stitch_mm + 1e-6
    assert min(steps) >= MIN_STITCH_MM
    # Where one piece ends and the next begins, they're never so close that sewing the next one's
    # first point would make a stitch too short to keep.
    assert all(math.dist(a[-1], b[0]) >= MIN_STITCH_MM for a, b in zip(paths, paths[1:]))
    zone = shape.buffer(0.3)
    assert all(zone.covers(LineString(path)) for path in paths if len(path) > 1)


@pytest.mark.parametrize("name", sorted(ODD))
def test_odd_shapes_sew_inside_with_no_long_stitch(name):
    obj = _spiral(*ODD[name])
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05)


def test_a_shape_too_thin_for_any_ring_says_so():
    with pytest.raises(DigitizeError, match="too small for a spiral fill"):
        generate(_spiral(_nodes([(0, 0), (40, 0), (40, 0.6), (0, 0.6)])))


def test_without_maximum_inscribed_circle_the_middle_is_a_point_inside(monkeypatch):
    """A shapely before 2.1 has no maximum_inscribed_circle: the spiral starts at a point inside."""
    monkeypatch.delattr(shapely, "maximum_inscribed_circle")
    obj = _spiral(holes=[HOLE])
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05)
    inside = _area(obj).representative_point()
    assert math.dist(recs[0][:2], (inside.x, inside.y)) <= 1.5


SNAPSHOT_CASES = {
    "square_40": _spiral(underlay="auto"),
    "donut": _spiral(holes=[HOLE], underlay="auto"),
    "star": _spiral(STAR, underlay="auto"),
    "tight_0_6": _spiral(spiral_mm=0.6, underlay="auto"),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("fills_spiral", name, digest_recs(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_are_sane(name):
    obj = SNAPSHOT_CASES[name]
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05,
                           max_jumps=0, max_trims=0)


def test_project_names_the_feature():
    assert "fill_spiral" in project._features({"items": [_spiral()]})
    assert "fill_spiral" in project._features({"items": [{"kind": "applique", "params": {"pattern": "spiral"}}]})
    assert "fill_spiral" not in project._features({"items": [{"kind": "fill", "params": {"pattern": "contour"}}]})
    assert "fill_spiral" not in project._features({"items": [{"kind": "run", "params": {"pattern": "spiral"}}]})
    assert "fill_spiral" in project.KNOWN_FEATURES
