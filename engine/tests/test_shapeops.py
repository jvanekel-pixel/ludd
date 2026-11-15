"""Outlines & offsets, the knife, and merging."""

import math

import pytest
from shapely.geometry import Polygon

from threadline_engine import shapeops
from threadline_engine.shapeops import ShapeError

IDENT = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}
RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}


def fill(i, nodes, holes=None):
    g = {"outline": nodes, **({"holes": holes} if holes else {})}
    return {"id": i, "kind": "fill", "geometry": g, "params": {"underlay": []}, "thread": RED, "transform": IDENT, "threads": [], "ops": []}


def sq(x, y, w):
    return [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]]


def area(nodes):
    return Polygon([(n[0], n[1]) for n in nodes]).area


def test_offset_rings_a_shape_at_the_distance():
    lay = {"version": 1, "items": [fill("a", sq(0, 0, 20))]}
    ring = shapeops.offset(lay, ["a"], 3.0)["rings"]
    assert len(ring) == 1
    # About 20 + 2 * 3 wide (the corners are rounded).
    xs = [n[0] for n in ring[0]]
    assert max(xs) - min(xs) == pytest.approx(26, abs=0.8)
    assert sum(1 for *_, k in ring[0]) >= 8 and all(k in ("s", "c") for *_, k in ring[0])


def test_offset_goes_around_several_things_as_one_when_they_are_close():
    lay = {"version": 1, "items": [fill("a", sq(0, 0, 10)), fill("b", sq(12, 0, 10))]}
    assert len(shapeops.offset(lay, ["a", "b"], 2.0)["rings"]) == 1
    assert len(shapeops.offset(lay, ["a"], 0.5)["rings"]) == 1
    with pytest.raises(ShapeError):
        shapeops.offset(lay, ["nope"], 2.0)


def test_knife_cuts_a_fill_in_two():
    obj = fill("a", sq(0, 0, 20))
    parts = shapeops.split(obj, (10, -5), (10, 25))["geometries"]
    assert len(parts) == 2
    assert [area(p["outline"]) for p in parts] == [pytest.approx(200, rel=0.03)] * 2
    with pytest.raises(ShapeError, match="doesn't cross"):
        shapeops.split(obj, (30, 0), (30, 10))


def test_knife_keeps_holes_on_the_side_they_are_on():
    obj = fill("a", sq(0, 0, 20), holes=[sq(2, 2, 5)])
    parts = shapeops.split(obj, (10, -5), (10, 25))["geometries"]
    assert sum(len(p.get("holes", [])) for p in parts) == 1



def test_qa_c14_outline_round_a_dense_design_is_quick():
    """A satin spiral packed 12 turns deep (8,700 stitches) took 9 s; a whole design 18 s."""
    import time
    nodes = [[(5 + 2.5 * i / 24) * math.cos(2 * math.pi * i / 24), (5 + 2.5 * i / 24) * math.sin(2 * math.pi * i / 24), "s"]
             for i in range(24 * 12 + 1)]
    lay = {"version": 1, "items": [{"id": "s", "kind": "satin", "geometry": {"nodes": nodes, "width_mm": 2.5}, "params": {},
                                    "thread": RED, "transform": IDENT, "threads": [], "ops": []}]}
    shapeops.offset(lay, ["s"], 2.0)  # (stitches cached)
    t = time.perf_counter()
    rings = shapeops.offset(lay, ["s"], 2.0)["rings"]
    assert time.perf_counter() - t < 3
    # One ring 2 mm outside the outermost turn (radius 35 + half the 2.5 mm width + 2).
    r = max(math.hypot(n[0], n[1]) for n in rings[0])
    assert len(rings) == 1 and r == pytest.approx(38.25, abs=0.6)


def test_knife_cuts_a_line_and_a_ribbon():
    line = {"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [30, 0, "c"]]}}
    parts = shapeops.split(line, (15, -5), (15, 5))["geometries"]
    assert len(parts) == 2 and abs(parts[0]["nodes"][-1][0] - 15) < 0.1
    ribbon = {"kind": "satin", "geometry": {"nodes": [[0, 0, "c"], [30, 0, "c"]], "width_mm": 3}}
    assert all(p["width_mm"] == 3 for p in shapeops.split(ribbon, (10, -5), (10, 5))["geometries"])


def test_merge_joins_touching_fills_and_refuses_separate_ones():
    joined = shapeops.merge([fill("a", sq(0, 0, 10)), fill("b", sq(8, 0, 10))])["geometry"]
    assert area(joined["outline"]) == pytest.approx(180, rel=0.03)
    with pytest.raises(ShapeError, match="don't touch"):
        shapeops.merge([fill("a", sq(0, 0, 10)), fill("b", sq(30, 0, 10))])



def test_qa_c13_knife_and_merge_use_the_shape_as_shown():
    """A moved or resized shape is cut where it's shown, and merges join what's on screen."""
    moved = fill("a", sq(0, 0, 10))
    moved["transform"] = {**IDENT, "x": 50, "scale_x": 2, "scale_y": 2}  # shown at 45..65 x -5..15
    parts = shapeops.split(moved, (55, -20), (55, 20))["geometries"]
    assert len(parts) == 2
    xs = sorted(n[0] for p in parts for n in p["outline"])
    assert xs[0] == pytest.approx(45, abs=0.1) and xs[-1] == pytest.approx(65, abs=0.1)
    with pytest.raises(ShapeError, match="doesn't cross"):
        shapeops.split(moved, (5, -20), (5, 20))  # where it was before the move
    # Two squares that only touch once one is moved next to the other.
    b = fill("b", sq(30, 0, 10))
    b["transform"] = {**IDENT, "x": -22}  # shown at 8..18: overlaps a
    joined = shapeops.merge([fill("a", sq(0, 0, 10)), b])["geometry"]
    assert area(joined["outline"]) == pytest.approx(180, rel=0.03)
    # A turned ribbon is cut where it's shown, and keeps its resized width.
    ribbon = {"kind": "satin", "geometry": {"nodes": [[0, 0, "c"], [30, 0, "c"]], "width_mm": 3},
              "transform": {**IDENT, "rotate": 90, "scale_x": 2, "scale_y": 2}}  # shown upright, x=15, y -15..45
    cut = shapeops.split(ribbon, (0, 10), (30, 10))["geometries"]
    assert len(cut) == 2 and all(p["width_mm"] == pytest.approx(6) for p in cut)


def test_to_nodes_keeps_square_corners_and_smooths_circles():
    corners = shapeops.to_nodes([(0, 0), (20, 0), (20, 20), (0, 20)], 4)
    assert sum(1 for n in corners if n[2] == "c") == 4
    circle = [(10 * math.cos(t / 50 * 2 * math.pi), 10 * math.sin(t / 50 * 2 * math.pi)) for t in range(50)]
    assert all(n[2] == "s" for n in shapeops.to_nodes(circle, 3))


# ---------------------------------------------------------------- QA phase 4


def test_qa_outline_ignores_hidden_travel_to_the_previous_shape():
    a, b = fill("A", sq(0, 0, 20)), fill("B", sq(40, 0, 20))
    cover = {**fill("C", [[-5, -5, "c"], [65, -5, "c"], [65, 25, "c"], [-5, 25, "c"]]), "thread": {**RED, "color": "#2222cc"}}
    for travel_under in (False, True):
        ring = shapeops.offset({"version": 1, "items": [a, b, cover], "travel_under": travel_under}, ["B"], 2.0)["rings"][0]
        assert min(n[0] for n in ring) > 37  # was 0.7 with Fewer jumps & trims: a spur back to A


def test_qa_outline_rings_small_holes_too():
    item = fill("a", sq(0, 0, 30), holes=[sq(13, 13, 4)])
    assert len(shapeops.offset({"version": 1, "items": [item]}, ["a"], 0.5, 3.0, True)["rings"]) == 2  # was 1


def test_qa_one_cut_across_a_closed_line_or_ribbon_gives_two_pieces():
    ring = [[10 * math.cos(2 * math.pi * i / 8), 10 * math.sin(2 * math.pi * i / 8), "s"] for i in range(8)]
    assert len(shapeops.split({"kind": "run", "geometry": {"nodes": ring, "closed": True}}, (0, -20), (0, 20))["geometries"]) == 2
    square = {"kind": "satin", "geometry": {"nodes": sq(0, 0, 20), "width_mm": 2.5, "closed": True}}
    pieces = shapeops.split(square, (10, -5), (10, 5))["geometries"]
    assert len(pieces) == 2 and all(p["width_mm"] == 2.5 for p in pieces)
    assert len(shapeops.split(square, (0, -5), (20, 25))["geometries"]) == 2  # a cut through the start point


def test_qa_knife_mistakes_get_plain_messages():
    line = {"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [30, 0, "c"]]}}
    with pytest.raises(ShapeError, match="runs along"):
        shapeops.split(line, (0, 0), (30, 0))
    with pytest.raises(ShapeError, match="too short"):
        shapeops.split({"kind": "run", "geometry": {"nodes": [[0, 0, "c"]]}}, (0, -1), (0, 1))


def test_qa_knife_keeps_small_holes_and_cuts_both_lobes_of_a_bowtie():
    holed = fill("a", sq(0, 0, 30), holes=[sq(10, 10, 1.2)])
    assert sum(len(p.get("holes", [])) for p in shapeops.split(holed, (25, -5), (25, 35))["geometries"]) == 1
    bow = fill("b", [[0, 0, "c"], [20, 20, "c"], [20, 0, "c"], [0, 20, "c"]])
    assert len(shapeops.split(bow, (5, -5), (5, 25))["geometries"]) == 3  # left lobe cut in two, right lobe whole


def test_qa_merge_refuses_shapes_that_only_meet_at_a_corner():
    with pytest.raises(ShapeError, match="corner"):
        shapeops.merge([fill("a", sq(0, 0, 10)), fill("b", sq(10, 10, 10))])
    assert area(shapeops.merge([fill("a", sq(0, 0, 10)), fill("b", sq(10, 0, 10))])["geometry"]["outline"]) == pytest.approx(200, rel=0.02)


def test_cut_out_makes_a_hole_or_a_bite_and_refuses_shapes_that_miss():
    target = fill("a", sq(0, 0, 40))
    hole = shapeops.cut_out(target, [fill("b", sq(10, 10, 10))])["geometries"]
    assert len(hole) == 1 and len(hole[0]["holes"]) == 1
    assert area(hole[0]["outline"]) - area(hole[0]["holes"][0]) == pytest.approx(1500, rel=0.02)
    bite = shapeops.cut_out(target, [fill("b", sq(30, 10, 20))])["geometries"]
    assert len(bite) == 1 and "holes" not in bite[0]
    assert area(bite[0]["outline"]) == pytest.approx(1400, rel=0.02)
    # A circle drawn as a closed line, and a satin bar right across: two pieces.
    across = {"kind": "satin", "geometry": {"nodes": [[-5, 20, "c"], [45, 20, "c"]], "width_mm": 4}, "transform": IDENT}
    assert len(shapeops.cut_out(target, [across])["geometries"]) == 2
    with pytest.raises(ShapeError, match="don't overlap"):
        shapeops.cut_out(target, [fill("b", sq(60, 60, 5))])
    with pytest.raises(ShapeError, match="whole fill"):
        shapeops.cut_out(target, [fill("b", sq(-5, -5, 50))])
