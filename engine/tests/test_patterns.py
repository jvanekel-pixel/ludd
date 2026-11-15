"""Decorative fills and motif lines: they stay inside, keep stitches sewable, and look like
what they're called."""

import math

import pytest
from shapely.geometry import LineString, Point as SPoint, Polygon

from threadline_engine.digitize.patterns import contour_paths, cross_paths, gradient_ys, motif_points, stipple_path
from threadline_engine.digitize.stitches import STITCH, DigitizeError, FillParams, generate, fill

SQUARE = [[0, 0, "c"], [30, 0, "c"], [30, 30, "c"], [0, 30, "c"]]
POLY = Polygon([(0, 0), (30, 0), (30, 30), (0, 30)])


def stitches(recs):
    return [(x, y) for x, y, k in recs if k == STITCH]


def longest(points):
    return max(math.dist(a, b) for a, b in zip(points, points[1:]))


@pytest.mark.parametrize("pattern", ["gradient", "wave", "contour", "stipple", "cross"])
def test_every_pattern_stays_inside_and_sews(pattern):
    recs, _ = fill(SQUARE, [], FillParams(pattern=pattern, underlay=("edge",)))
    pts = stitches(recs)
    assert len(pts) > 50
    grown = POLY.buffer(0.6)
    assert all(grown.contains(SPoint(p)) for p in pts)
    assert longest(pts) <= 8.0


def test_gradient_rows_open_out():
    ys = gradient_ys(0, 30, 0.4, 2.0)
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    assert gaps[0] == pytest.approx(0.4, abs=0.05)
    assert gaps[-1] > 1.5
    assert all(b >= a - 1e-9 for a, b in zip(gaps, gaps[1:]))


def test_contour_rings_follow_the_outline_inwards():
    paths = contour_paths(POLY, 2.0, 2.5, (0, 0))
    assert len(paths) == pytest.approx(7, abs=1)  # 15 mm to the middle / 2 mm
    first = Polygon(paths[0])
    assert first.area == pytest.approx(28 * 28, rel=0.02)  # the first ring is half a spacing in


def test_stipple_is_one_line_that_never_crosses_itself():
    line = stipple_path(POLY, 3.0, 2.0, seed=1)
    assert len(line) > 100
    assert line[0] == line[-1] and LineString(line).is_simple  # a closed loop that never crosses itself
    # It wanders over most of the shape.
    assert LineString(line).buffer(2.0).intersection(POLY).area > 0.8 * POLY.area
    assert stipple_path(POLY, 3.0, 2.0, seed=1) == line  # the same design always sews the same


def test_cross_stitch_makes_an_x_in_each_square():
    paths = cross_paths(POLY, 3.0)
    assert len(paths) == 10  # ten rows of ten squares
    diagonals = sum(1 for p in paths for a, b in zip(p, p[1:]) if abs(abs(a[0] - b[0]) - 3) < 1e-6 and abs(abs(a[1] - b[1]) - 3) < 1e-6)
    assert diagonals == 200


@pytest.mark.parametrize("motif", ["wave", "zigzag", "scallop", "blanket"])
def test_motif_lines_stay_within_their_width(motif):
    nodes = [[0, 0, "c"], [40, 0, "c"]]
    pts = motif_points(nodes, motif, 4.0, 3.0)
    # As tall as it should be (a flattened motif would pass a "within the width" check).
    assert max(y for _, y in pts) - min(y for _, y in pts) == pytest.approx(1.5 if motif == "scallop" else 3.0, abs=0.01)
    assert min(x for x, _ in pts) == pytest.approx(0, abs=0.01)
    assert max(x for x, _ in pts) == pytest.approx(40, abs=0.01)
    assert max(abs(y) for _, y in pts) <= 1.5 + 1e-6
    recs = generate({"kind": "run", "geometry": {"nodes": nodes}, "params": {"style": "motif", "motif": motif}})[0]
    assert len(stitches(recs)) > 20


def test_bad_pattern_settings_are_refused():
    with pytest.raises(DigitizeError, match="pattern"):
        FillParams.from_dict({"pattern": "plaid"})
    with pytest.raises(DigitizeError, match="Stipple"):
        FillParams.from_dict({"pattern": "stipple", "stipple_mm": 50})
    with pytest.raises(DigitizeError, match="motif"):
        generate({"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [9, 0, "c"]]}, "params": {"style": "motif", "motif": "x"}})


def test_qa_c15_wave_rows_never_cross_each_other():
    from shapely.strtree import STRtree

    circle = [[15 + 12 * math.cos(2 * math.pi * i / 48), 15 + 12 * math.sin(2 * math.pi * i / 48), "c"] for i in range(48)]
    for angle in (0, 45):
        recs, _ = generate({"kind": "fill", "geometry": {"outline": circle}, "params": {"pattern": "wave", "underlay": [], "angle_deg": angle}})
        segs, prev = [], None
        for x, y, k in recs:
            if prev and k == STITCH and math.dist(prev, (x, y)) > 0.05:
                segs.append(LineString([prev, (x, y)]))
            prev = (x, y)
        tree = STRtree(segs)
        crossings = sum(1 for i, sg in enumerate(segs) for j in tree.query(sg) if j > i + 1 and sg.crosses(segs[j]))
        assert crossings <= len(segs) * 0.02, f"{crossings} crossings at {angle} degrees"


# ---------------------------------------------------------------- QA phase 4


def c(x, y):
    return [x, y, "c"]


def _circle(cx, cy, r, n=48):
    return [c(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def test_qa_stipple_fills_every_part_of_the_shape():
    from shapely.geometry import box
    from shapely.ops import unary_union

    g = unary_union([box(0, 0, 30, 30), box(30, 13.5, 40, 16), box(40, 8, 55, 23)])  # two blobs, a 2.5 mm neck
    recs, warnings = fill([c(x, y) for x, y in list(g.exterior.coords)[:-1]], [], FillParams(pattern="stipple", underlay=()))
    xs = [x for x, _ in stitches(recs)]
    assert max(xs) > 50 and not warnings  # was 29.2: the right-hand blob was left bare


def test_qa_stipple_says_when_a_part_is_too_narrow_for_its_loops():
    H = [c(0, 0), c(5, 0), c(5, 12.5), c(19, 12.5), c(19, 0), c(24, 0), c(24, 30), c(19, 30), c(19, 17.5), c(5, 17.5), c(5, 30), c(0, 30)]
    _, warnings = fill(H, [], FillParams(pattern="stipple", underlay=()))
    assert any("too narrow" in w for w in warnings)
    _, ok = fill(H, [], FillParams(pattern="stipple", stipple_mm=1.5, underlay=()))
    assert not ok


def test_qa_stipple_keeps_its_pattern_when_moved():
    def at(dx):
        sq = [c(dx, 0), c(30 + dx, 0), c(30 + dx, 30), c(dx, 30)]
        return [(round(x - dx, 6), round(y, 6)) for x, y in stitches(fill(sq, [], FillParams(pattern="stipple", underlay=()))[0])]

    assert at(0) == at(12.5)


def test_qa_contour_finishes_each_lobe_and_keeps_corners():
    from threadline_engine.digitize.stitches import fill_polygon

    H = [(0, 0), (15, 0), (15, 10), (25, 10), (25, 0), (40, 0), (40, 15), (25, 15), (25, 20), (40, 20), (40, 35), (25, 35), (25, 25),
         (15, 25), (15, 35), (0, 35)]
    paths = contour_paths(fill_polygon([c(*p) for p in H]), 0.4, 3.5, (0.5, 0.5))
    joins = [math.dist(a[-1], b[0]) for a, b in zip(paths, paths[1:])]
    assert sum(j > 5 for j in joins) <= 4 and sum(joins) < 120  # was 32 joins over 5 mm, 437 mm in all
    for size in (23, 30, 37):
        ring = LineString(contour_paths(Polygon([(0, 0), (size, 0), (size, size), (0, size)]), 0.4, 3.5, (0, 0))[0])
        corners = [(0.2, 0.2), (size - 0.2, 0.2), (size - 0.2, size - 0.2), (0.2, size - 0.2)]
        assert max(SPoint(p).distance(ring) for p in corners) < 0.05  # was 1.2 mm short of three corners


def test_qa_contour_round_a_hole_has_no_stacked_ridge():
    from threadline_engine import layout as L, quality

    lay = {"items": [{"id": "a", "kind": "fill", "geometry": {"outline": _circle(25, 25, 25), "holes": [_circle(25, 25, 10)]},
                      "params": {"pattern": "contour"}}]}
    segs, pts = quality._segments(L.render(lay).pattern)
    cover, *_ = quality._grid(segs, pts)
    assert float(cover.max()) < 10  # was 22 mm of thread per mm² along one radial line


def test_qa_contour_on_a_jagged_outline_is_quick():
    import random
    import time
    from threadline_engine.digitize.stitches import fill_polygon

    rnd = random.Random(3)
    n = 1000
    pts = [[(45 + 4.5 * math.sin(7 * a) + rnd.uniform(-.05, .05)) * math.cos(a) + 45,
            (45 + 4.5 * math.cos(5 * a) + rnd.uniform(-.05, .05)) * math.sin(a) + 45, "c"] for a in [2 * math.pi * i / n for i in range(n)]]
    poly = fill_polygon(pts)
    t = time.perf_counter()
    contour_paths(poly, 0.4, 3.5, None)
    assert time.perf_counter() - t < 3  # was about 5 s


def test_qa_cross_stitch_has_no_bars_between_crosses():
    paths = cross_paths(POLY, 3.0)
    vertical = sum(1 for p in paths for a, b in zip(p, p[1:]) if abs(a[0] - b[0]) < 1e-6 and abs(abs(a[1] - b[1]) - 3) < 1e-6)
    assert vertical == len(paths) == 10  # one turn per run of squares (was 190 bars)


def test_qa_cross_stitch_round_a_hole_needs_few_long_moves():
    from threadline_engine.digitize.stitches import fill_polygon

    paths = cross_paths(fill_polygon(_circle(25, 25, 25), [_circle(25, 25, 10)]), 2.5)
    joins = [math.dist(a[-1], b[0]) for a, b in zip(paths, paths[1:])]
    assert sum(j > 5 for j in joins) <= 2 and sum(joins) < 120  # was 8 moves over 5 mm, 286 mm in all


def test_qa_big_cross_stitch_squares_are_split():
    recs, _ = fill(SQUARE, [], FillParams(pattern="cross", cross_mm=8, underlay=()))
    assert longest(stitches(recs)) <= 7.0  # one 11.3 mm diagonal became two


def test_qa_open_pattern_underlay_ends_beside_the_pattern():
    from threadline_engine.digitize import stitches as dz

    moves = []
    real = dz.travel

    def spy(a, b, inside=None):
        moves.append(math.dist(a, b))
        return real(a, b, inside)

    dz.travel = spy
    try:
        for pattern in ("stipple", "cross", "contour"):
            moves.clear()
            fill(_circle(15, 15, 12), [], FillParams(pattern=pattern))
            assert max(moves) < 4, pattern  # was a 22.8 mm straight thread across the shape
    finally:
        dz.travel = real


def test_qa_closed_motif_line_meets_itself():
    recs, _ = generate({"kind": "run", "geometry": {"nodes": [c(0, 0), c(20, 0), c(20, 20), c(0, 20)], "closed": True},
                        "params": {"style": "motif", "motif": "zigzag", "tie_in": False, "tie_off": False}})
    assert math.dist(recs[0][:2], recs[-1][:2]) < 1e-6  # was 2.1 mm apart at the start corner
