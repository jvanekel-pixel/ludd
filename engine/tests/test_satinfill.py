"""Satin fill: one satin column that fills a closed shape and turns with it."""

import math

import pytest
from shapely.geometry import LineString, Polygon

from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.satinfill import SatinFillError, satin_fill


def leaf():
    """A bent leaf 40 mm long and up to 12 mm wide."""
    top = [(t, 6 * math.sin(math.pi * t / 40) + 0.004 * (t - 20) ** 2) for t in range(0, 41, 4)]
    bot = [(t, -6 * math.sin(math.pi * t / 40) + 0.004 * (t - 20) ** 2) for t in range(40, -1, -4)][1:-1]
    return [[x, y, "s"] for x, y in top + bot]


RECT = [[0, 0, "c"], [40, 0, "c"], [40, 8, "c"], [0, 8, "c"]]


def stitches_of(r, spacing=0.4):
    return dz.satin_pairs(r["rail_a"], r["rail_b"], spacing)


def test_a_leaf_is_filled_tip_to_tip_with_stitches_across_it():
    r = satin_fill(leaf())
    a, b = r["rail_a"], r["rail_b"]
    assert len(a) == len(b) >= 5
    # It runs tip to tip (starting where the leaf is wide enough to sew, under a millimetre in).
    assert sorted([a[0][0], a[-1][0]])[0] < 1.5 and sorted([a[0][0], a[-1][0]])[1] > 38.5
    assert 0.9 <= math.dist(a[0][:2], b[0][:2]) < 2.5
    pairs = stitches_of(r)
    # Stitches go across the leaf: never longer than the leaf is wide, and widest in the middle.
    assert max(math.dist(p, q) for p, q in pairs) <= 12.2
    mid = pairs[len(pairs) // 2]
    assert math.dist(*mid) > 9


def test_stitches_stay_inside_the_shape_and_never_cross():
    pts, _ = flatten(leaf(), True)
    shape = Polygon(pts).buffer(0.35)
    pairs = stitches_of(satin_fill(leaf()))
    assert all(shape.contains(LineString([p, q]).interpolate(0.5, normalized=True)) for p, q in pairs)
    lines = [LineString([p, q]) for p, q in pairs if math.dist(p, q) > 0.5]
    assert not any(lines[k].crosses(lines[k + 2]) for k in range(len(lines) - 2))


def test_a_long_bar_is_sewn_across_its_short_side():
    r = satin_fill(RECT)
    pairs = stitches_of(r)
    assert r["widest_mm"] == pytest.approx(8, abs=0.3)
    assert max(math.dist(p, q) for p, q in pairs) == pytest.approx(8, abs=0.3)


def test_other_ways_turn_the_stitches_and_wrap_round():
    first = satin_fill(RECT, 0)
    assert first["ways"] >= 2
    second = satin_fill(RECT, 1)
    assert second["rail_a"][0][:2] != first["rail_a"][0][:2] or second["rail_a"][-1][:2] != first["rail_a"][-1][:2]
    assert satin_fill(RECT, first["ways"])["rail_a"] == first["rail_a"]  # wraps round


def test_a_tiny_or_broken_shape_is_refused_plainly():
    with pytest.raises(SatinFillError, match="too small"):
        satin_fill([[0, 0, "c"], [0.5, 0, "c"], [0.5, 0.5, "c"]])


def test_the_tips_can_be_chosen_by_hand():
    """The purple direction dots: the satin runs from one chosen tip to the other, whichever way
    the best automatic split would have gone."""
    import math

    from threadline_engine.digitize.satinfill import SatinFillError, satin_fill

    rect = [[0, 0, "l"], [40, 0, "l"], [40, 10, "l"], [0, 10, "l"]]
    across = satin_fill(rect, tips=[[20, 0], [20, 10]])  # tips mid top and bottom: stitches run left-right
    a, b = across["rail_a"], across["rail_b"]
    mid0 = ((a[0][0] + b[0][0]) / 2, (a[0][1] + b[0][1]) / 2)
    mid1 = ((a[-1][0] + b[-1][0]) / 2, (a[-1][1] + b[-1][1]) / 2)
    assert math.dist(mid0, (20, 0)) < 2.5 and math.dist(mid1, (20, 10)) < 2.5
    along = satin_fill(rect, tips=[[0, 5], [40, 5]])
    assert along["widest_mm"] < across["widest_mm"]
    with pytest.raises(SatinFillError):
        satin_fill(rect, tips=[[0, 5], [0, 5.2]])
