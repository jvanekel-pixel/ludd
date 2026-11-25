"""The spiral fill: one line that winds from the middle of a shape out to its edge
(digitize/fills/spiral.py)."""

import math
import statistics

import pytest
import shapely
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

import invariants
from snapshot_util import check, digest_recs
from threadline_engine import project
from threadline_engine.digitize import fills
from threadline_engine.digitize.fills import spiral
from threadline_engine.digitize.stitches import (MIN_STITCH_MM, STITCH, DigitizeError, FillParams, fill_parts,
                                                 fill_polygon, generate)

MIDDLE = (20.0, 20.0)  # of the 40 mm square
STITCH_MM = 3.5  # the standard fill stitch length
TIGHT = "Rings this close sew like a solid fill and can pucker in the middle; 1 mm or more is safer."


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


# Ready-made shapes from the Shapes menu, as design/shapes.ts draws them at 60 mm (the size in a 4" hoop).
_HEART_SIDE = [(6.58, -23.4), (16.14, -27), (26, -23.4), (29.89, -12.6), (22.12, 5.7)]
READY_HEART = [[0, -15.6, "c"], *([x, y, "s"] for x, y in _HEART_SIDE), [0, 27, "c"],
               *([-x, y, "s"] for x, y in reversed(_HEART_SIDE))]
READY_OVAL = [[x, y, "s"] for x, y in [(30, 0), (21.21, 14.85), (0, 21), (-21.21, 14.85), (-30, 0),
                                        (-21.21, -14.85), (0, -21), (21.21, -14.85)]]
READY_ROUNDED_RECTANGLE = [list(n) for n in [
    (21, -21, "l"), (24.44, -20.31, "s"), (27.36, -18.36, "s"), (29.31, -15.44, "s"), (30, -12, "c"),
    (30, 12, "l"), (29.31, 15.44, "s"), (27.36, 18.36, "s"), (24.44, 20.31, "s"), (21, 21, "c"),
    (-21, 21, "l"), (-24.44, 20.31, "s"), (-27.36, 18.36, "s"), (-29.31, 15.44, "s"), (-30, 12, "c"),
    (-30, -12, "l"), (-29.31, -15.44, "s"), (-27.36, -18.36, "s"), (-24.44, -20.31, "s"), (-21, -21, "c")]]
READY_RECTANGLE = [[-30, -21, "c"], [30, -21, "c"], [30, 21, "c"], [-30, 21, "c"]]
READY_TRIANGLE = [[0, -25.98, "c"], [30, 25.98, "c"], [-30, 25.98, "c"]]


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


@pytest.mark.parametrize("width,height", [(48, 24), (48, 40), (60, 42)])  # 60 x 42: the rounded rectangle shape's
def test_a_rectangle_starts_in_its_middle(width, height):
    """A rectangle is as wide as its widest spot all along a line: the spiral takes the middle of it."""
    obj = _spiral(_nodes([(0, 0), (width, 0), (width, height), (0, height)]), underlay="auto")  # as the app's fills are
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05,
                           max_jumps=0, max_trims=0, starts_near=(width / 2, height / 2), near_mm=1.5)


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


def _across_the_rings(recs, shape, spacing=1.5):
    """How much thread (mm) lies more than 1 mm inside the shape and off the spiral. Only a join
    between two stretches of the spiral can, and nothing covers it, so it shows."""
    middle = (recs[0][0] + spacing / 2, recs[0][1])  # the spiral begins half a ring to the left of it
    inside = shape.buffer(-1.0)
    shapely.prepare(inside)
    total = 0.0
    for a, b in _threads(recs):
        n = max(1, math.ceil(math.dist(a, b) / 0.1))
        for i in range(n):
            x, y = (a[k] + (b[k] - a[k]) * (i + 0.5) / n for k in (0, 1))
            dx, dy = x - middle[0], y - middle[1]
            # On the spiral, the distance from the middle matches the angle, give or take whole rings.
            off = (math.hypot(dx, dy) - spacing * math.atan2(dy, dx) / (2 * math.pi)) % spacing
            if min(off, spacing - off) > 0.3 and inside.contains(Point(x, y)):
                total += math.dist(a, b) / n
    return total


# Shapes that cut the spiral into many pieces: (outline, holes).
CUT_UP = {
    "heart": (READY_HEART, []),
    "oval": (READY_OVAL, []),
    "rounded_rectangle": (READY_ROUNDED_RECTANGLE, []),
    "rectangle": (READY_RECTANGLE, []),
    "triangle": (READY_TRIANGLE, []),
    "star": (STAR, []),
    "ring": (_round(20), [_round(10)]),  # the way round must keep to one edge, not cut across the band
    "donut": (SQUARE, [HOLE]),
    "three_holes": (_round(20), [_round(4, middle=(12, 14)), _round(3, middle=(27, 15)), _round(5, middle=(20, 29))]),
    # a hole 0.8 mm from the outline on one side: stretches too short to count join the two edges there
    "pinch": (_round(20), [_round(10, middle=(29.2, 20))]),
}


@pytest.mark.parametrize("outline,holes", CUT_UP.values(), ids=CUT_UP.keys())
def test_no_thread_crosses_the_rings(outline, holes):
    obj = _spiral(outline, holes, underlay="auto")
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05,
                           max_jumps=0, max_trims=0)
    assert _across_the_rings(recs, _area(obj)) < 0.5


def _most_threads_along_an_edge(recs, shape):
    """The most threads lying side by side along the shape's outline or a hole's rim, looked at
    every 0.5 mm: within 0.4 mm of that spot, and running the same way as the edge there."""
    threads = [LineString(t) for t in _threads(recs) if t[0] != t[1]]
    tree = STRtree(threads)
    most = 0
    for ring in [shape.exterior, *shape.interiors]:
        edge = LineString(ring.coords)
        for k in range(int(edge.length / 0.5)):
            s = 0.25 + 0.5 * k
            spot, back, ahead = (edge.interpolate(s + d) for d in (0, -0.2, 0.2))
            along = 0
            for i in tree.query(spot.buffer(0.4)):
                (ax, ay), (bx, by) = threads[i].coords
                sizes = math.hypot(bx - ax, by - ay) * math.hypot(ahead.x - back.x, ahead.y - back.y)
                same_way = abs((bx - ax) * (ahead.x - back.x) + (by - ay) * (ahead.y - back.y)) > 0.85 * sizes
                along += same_way and threads[i].distance(spot) <= 0.4
            most = max(most, along)
    return most


@pytest.mark.parametrize("outline,holes", CUT_UP.values(), ids=CUT_UP.keys())
def test_joining_thread_does_not_pile_up_along_the_edges(outline, holes):
    obj = _spiral(outline, holes, underlay="auto", tie_in=False, tie_off=False)
    assert _most_threads_along_an_edge(generate(obj)[0], _area(obj)) <= 6


def _farthest_unsewn(recs, shape, spacing=1.5):
    """How far from the thread the spiral gets anywhere 1 mm or more inside the shape (mm): large if
    any stretch of it was left out."""
    mx, my = recs[0][0] + spacing / 2, recs[0][1]
    reach = max(math.dist((mx, my), p) for p in shape.exterior.coords)
    spots = []
    for degrees in range(360):
        turn = math.radians(degrees)
        radii = (spacing * (degrees / 360 + k) for k in range(int(reach / spacing) + 2))
        spots += [Point(mx + r * math.cos(turn), my + r * math.sin(turn)) for r in radii if r >= spacing / 2]
    inside = shape.buffer(-1.0)
    shapely.prepare(inside)
    spots = [p for p in spots if inside.contains(p)]
    assert len(spots) > 100
    return max(shapely.distance(MultiLineString(_threads(recs)), spots))


@pytest.mark.parametrize("outline,holes", CUT_UP.values(), ids=CUT_UP.keys())
def test_every_part_of_every_ring_is_sewn(outline, holes):
    obj = _spiral(outline, holes, underlay="auto")
    assert _farthest_unsewn(generate(obj)[0], _area(obj)) <= 0.3


def _stretch(start, end):
    """A stretch's two ends for _sewing_order, each (edge, how far round it, where it is)."""
    return (start, end)


FIRST = (None, 0.0, (0.0, 0.0))  # the first stretch starts in the middle, on no edge


def test_the_nearest_end_along_the_edge_is_next_from_either_end():
    ends = [_stretch(FIRST, (0, 19.0, (19, 0))),  # the needle is 19 mm round a 20 mm edge
            _stretch((0, 9.0, (9, 0)), (0, 12.0, (12, 0))),
            _stretch((0, 4.0, (4, 0)), (0, 1.0, (1, 0)))]  # its far end is 2 mm on, past where the edge starts
    assert spiral._sewing_order(ends, [20.0]) == [(0, False), (2, True), (1, False)]


def test_a_stretch_waits_if_sewing_it_now_would_strand_another():
    """Edge 0 is the outline, edge 1 a hole. The nearest end on the outline starts a stretch to the
    hole. One that begins and ends on the outline couldn't be reached from there, so it goes first."""
    ends = [_stretch(FIRST, (0, 0.0, (0, 0))),
            _stretch((0, 1.0, (1, 0)), (1, 0.0, (1, 5))),
            _stretch((0, 5.0, (5, 0)), (0, 8.0, (8, 0)))]
    assert spiral._sewing_order(ends, [20.0, 10.0]) == [(0, False), (2, False), (1, False)]


def test_with_nothing_left_on_this_edge_the_stretch_nearest_in_a_straight_line_is_next():
    """Only if the edges don't connect up (they always do in a spiral cut by a shape)."""
    ends = [_stretch(FIRST, (0, 0.0, (0, 0))),
            _stretch((1, 2.0, (8, 0)), (1, 3.0, (9, 0))),
            _stretch((2, 2.0, (3, 0)), (2, 3.0, (30, 0)))]
    assert spiral._sewing_order(ends, [20.0, 20.0, 40.0]) == [(0, False), (2, False), (1, True)]


def test_stretches_no_edge_can_join_are_still_sewn(monkeypatch):
    """Should no way along an edge stay inside the shape, the stretches stay apart and the fill
    travels between them as it does for any open pattern."""
    monkeypatch.setattr(spiral, "_way_round", lambda *args: None)
    obj = _spiral(holes=[HOLE])
    shape = fill_polygon(*obj["geometry"].values())
    assert len(fills.get("spiral").paths(shape, FillParams.from_dict(obj["params"]), (0.0, 0.0))[0]) > 1
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.3, max_stitch_mm=STITCH_MM + 0.05)


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
    """Every stitch of the spiral's path, the joins along the edge included."""
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
