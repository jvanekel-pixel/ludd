"""Which side of its line a motif line sits on (motif_side): centered, as always, or all to the
left or right of the line, walking it the way it was drawn. On screen (y down) the left of a line
drawn left to right is up (y less than 0)."""

import math

import pytest
from shapely.geometry import Point

from threadline_engine.digitize import lines
from threadline_engine.digitize.patterns import motif_points
from threadline_engine.digitize.stitches import STITCH, DigitizeError, generate

LINE = [[0, 0, "c"], [30, 0, "c"]]  # drawn left to right
BUILTINS = ["wave", "zigzag", "scallop", "blanket", "leaf"]
# How far to its side each built-in motif reaches at Width 3: the whole width, but the scallop,
# which only goes half as far across as it is long.
REACH = {"wave": 3.0, "zigzag": 3.0, "scallop": 1.5, "blanket": 3.0, "leaf": 3.0}
# A motif of your own: a hill drawn above its line, and the same one drawn below it.
HILL_UP = [[0, 0], [0.25, -0.3], [0.75, -0.3], [1, 0]]
HILL_DOWN = [[0, 0], [0.25, 0.3], [0.75, 0.3], [1, 0]]


def _obj(nodes=LINE, motif="blanket", side=None, closed=False, **params):
    p = {"style": "motif", "motif": motif, "motif_mm": 5, "motif_width_mm": 3, "tie_in": False, "tie_off": False,
         **params}
    if side:
        p["motif_side"] = side
    return {"kind": "run", "geometry": {"nodes": nodes, "closed": closed}, "params": p}


def _recs(*args, **kwargs):
    return generate(_obj(*args, **kwargs))[0]


def _needles(recs):
    return [(x, y) for x, y, k in recs if k == STITCH]


@pytest.mark.parametrize("motif", BUILTINS)
def test_center_is_unchanged(motif):
    curve = [[0, 0, "s"], [15, 8, "s"], [30, 0, "s"]]
    for closed in (False, True):
        before = generate(_obj(curve, motif=motif, closed=closed))
        assert generate(_obj(curve, motif=motif, closed=closed, side="center")) == before
    assert motif_points(curve, motif, 5, 3, side="center") == motif_points(curve, motif, 5, 3)


@pytest.mark.parametrize("motif", BUILTINS)
def test_left_is_above_a_left_to_right_line(motif):
    ys = [y for _, y in _needles(_recs(motif=motif, side="left"))]
    assert max(ys) <= 1e-6
    assert min(ys) == pytest.approx(-REACH[motif], abs=0.01)


@pytest.mark.parametrize("motif", BUILTINS)
def test_right_mirrors_left(motif):
    left = _recs(motif=motif, side="left")
    right = _recs(motif=motif, side="right")
    assert [(round(x, 9), round(-y, 9) + 0.0, k) for x, y, k in left] == [(round(x, 9), round(y, 9) + 0.0, k)
                                                                           for x, y, k in right]


@pytest.mark.parametrize("side,sign", [("left", -1), ("right", 1)])
def test_blanket_teeth_point_away(side, sign):
    recs = _recs(side=side)
    runs = [(a[:2], b[:2]) for a, b in zip(recs, recs[1:])
            if a[2] == b[2] == STITCH and abs(a[1]) < 1e-6 and abs(b[1]) < 1e-6]
    assert sum(math.dist(a, b) for a, b in runs) == pytest.approx(30, abs=1e-6)  # the flat side lies on the line
    tips = sorted({round(x, 6) for x, y in _needles(recs) if y == pytest.approx(3 * sign)})
    assert tips == pytest.approx([2.5 + 5 * k for k in range(6)])  # one tooth a repeat, all to one side


def test_round_a_circle_drawn_clockwise_left_is_outside_and_right_inside():
    # The Shapes menu draws its circle clockwise on screen.
    circle = [[20 * math.cos(2 * math.pi * i / 16), 20 * math.sin(2 * math.pi * i / 16), "s"] for i in range(16)]
    out = [Point(0, 0).distance(Point(p)) for p in _needles(_recs(circle, side="left", closed=True))]
    assert min(out) > 19.8 and max(out) == pytest.approx(23, abs=0.1)
    inside = [Point(0, 0).distance(Point(p)) for p in _needles(_recs(circle, side="right", closed=True))]
    assert max(inside) < 20.05 and min(inside) == pytest.approx(17, abs=0.2)


@pytest.mark.parametrize("unit", [HILL_UP, HILL_DOWN], ids=["drawn_above", "drawn_below"])
@pytest.mark.parametrize("side,sign", [("left", -1), ("right", 1)])
def test_a_motif_of_your_own_goes_to_the_side_chosen(unit, side, sign):
    """Its line (where it starts and ends) lies on the line, and its hills point away, however it
    was drawn."""
    pts = _needles(_recs(motif="user:hill", motif_unit=unit, side=side))
    assert all(sign * y >= -1e-6 for _, y in pts)
    assert max(sign * y for _, y in pts) == pytest.approx(3)  # Width is how far it reaches
    assert sorted({round(x, 6) for x, y in pts if abs(y) < 1e-6}) == pytest.approx([5 * k for k in range(7)])


def test_motif_side_is_checked():
    with pytest.raises(DigitizeError, match="^Unknown motif side: up$"):
        generate(_obj(side="up"))
    # A line that isn't a motif line pays it no heed, and a motif fill isn't moved by it.
    plain = {"kind": "run", "geometry": {"nodes": LINE}, "params": {"motif_side": "up"}}
    assert generate(plain) == generate({**plain, "params": {}})
    square = {"kind": "fill", "geometry": {"outline": [[0, 0, "c"], [20, 0, "c"], [20, 20, "c"], [0, 20, "c"]]},
              "params": {"pattern": "motif"}}
    assert generate({**square, "params": {**square["params"], "motif_side": "left"}}) == generate(square)


def test_the_built_in_motifs_are_still_the_same():
    assert [lines.MOTIF_UNITS[m] for m in ["blanket", "zigzag"]] == [
        [(0.0, -0.5), (0.5, -0.5), (0.5, 0.5), (0.5, -0.5), (1.0, -0.5)], [(0.0, -0.5), (0.5, 0.5), (1.0, -0.5)]]
