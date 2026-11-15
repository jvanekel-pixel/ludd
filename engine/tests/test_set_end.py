"""Dragging a drawn piece's start (green dot) and end (red dot)."""

import math

import pytest

from threadline_engine import layout as L
from threadline_engine.digitize import stitches as dz
from threadline_engine.jumps import EndsError, set_end


def square(x0=0.0, y0=0.0, w=20.0, h=10.0, **params):
    pts = [[x0, y0, "l"], [x0 + w, y0, "l"], [x0 + w, y0 + h, "l"], [x0, y0 + h, "l"]]
    return {"id": "f", "kind": "fill", "geometry": {"outline": pts}, "params": {"angle_deg": 0, "underlay": ["edge"], **params},
            "thread": {"color": "#000000"}, "transform": {}}


def stitched(obj):
    recs, _ = dz.generate(obj)
    return [(r[0], r[1]) for r in recs if r[2] == dz.STITCH]


@pytest.mark.parametrize("corner", [(0, 0), (20, 0), (0, 10), (20, 10)])
def test_a_fill_ends_at_the_corner_its_end_point_is_dragged_to(corner):
    pts = stitched(set_end(square(), "end", list(corner)))
    assert math.dist(pts[-1], corner) < 1.5  # the last row's end, by that corner


def test_a_fill_starts_at_the_edge_nearest_its_start_point():
    pts = stitched(set_end(square(), "start", [10, -3]))
    assert math.dist(pts[0], (10, 0)) < 0.8


def test_the_start_and_end_move_with_a_moved_and_turned_fill():
    obj = set_end(set_end(square(), "end", [20, 10]), "end", [20, 10])
    # Moved 30 mm right and turned 180°: the end (bottom right corner) is now at the top left.
    moved = {**obj, "transform": {"x": 30, "rotate": 180}}
    shown = dz.transform_geometry(moved, L.Transform.from_dict(moved["transform"]), (10, 5))
    pts = stitched(shown)
    assert math.dist(pts[-1], (30, 0)) < 1.5
    # Dragging on the moved fill is in the coordinates you see.
    again = set_end(moved, "start", [50, 5])  # its right-hand edge as shown
    start_local = again["params"]["start_mm"]
    assert math.dist(start_local, (0, 5)) < 1e-6


def test_a_border_starts_exactly_where_its_start_is_dropped():
    nodes = [[0, 0, "l"], [10, 0, "l"], [10, 10, "l"], [0, 10, "l"]]
    run = {"id": "r", "kind": "run", "geometry": {"nodes": nodes, "closed": True}, "params": {}, "transform": {}}
    pts = stitched(set_end(run, "start", [6.3, 10.4]))
    assert math.dist(pts[0], (6.3, 10)) < 0.05 and math.dist(pts[-1], (6.3, 10)) < 0.05
    ribbon = {"id": "s", "kind": "satin", "geometry": {"nodes": nodes, "closed": True, "width_mm": 2}, "params": {}, "transform": {}}
    pts = stitched(set_end(ribbon, "start", [10.5, 4.0]))
    mid = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    assert math.dist(mid, (10, 4)) < 1.0


@pytest.mark.parametrize("at", [(10, 10), (0, 4), (20, 7), (13, 0)])
def test_a_fill_ends_exactly_where_its_end_is_dropped_anywhere_on_the_edge(at):
    for angle in (0, 45, 90):
        pts = stitched(set_end(square(angle_deg=angle), "end", list(at)))
        assert math.dist(pts[-1], at) < 1.0, (angle, pts[-1])


def test_an_open_line_turns_round_when_its_start_is_dragged_to_the_other_end():
    nodes = [[0, 0, "l"], [10, 0, "l"]]
    run = {"id": "r", "kind": "run", "geometry": {"nodes": nodes}, "params": {}, "transform": {}}
    assert set_end(run, "start", [9, 0])["geometry"]["nodes"][0][:2] == [10, 0]
    assert set_end(run, "start", [1, 0])["geometry"]["nodes"][0][:2] == [0, 0]
    assert set_end(run, "end", [1, 0])["geometry"]["nodes"][-1][:2] == [0, 0]


@pytest.mark.parametrize("start,end", [((0, 1.5), (30, 1.5)), ((12, 0), (30, 3)), ((5, 3), (21, 0)), ((25, 1.5), (8, 3)), (None, (15, 0))])
def test_a_satin_starts_and_stops_anywhere_along_it(start, end):
    """Columns and ribbons: the first and last stitches are where the dots were put (within the
    satin's width), and the moves between its parts run along its middle, under satin sewn later."""
    a = [[0, 0, "l"], [30, 0, "l"]]
    b = [[0, 3, "l"], [30, 3, "l"]]
    col = {"id": "s", "kind": "satin", "geometry": {"rail_a": a, "rail_b": b}, "params": {"underlay": []}, "transform": {}}
    rib = {"id": "r", "kind": "satin", "geometry": {"nodes": [[0, 1.5, "l"], [30, 1.5, "l"]], "width_mm": 3}, "params": {"underlay": []}, "transform": {}}
    for obj in (col, rib):
        if start:
            obj = set_end(obj, "start", list(start))
        obj = set_end(obj, "end", list(end))
        pts = stitched(obj)
        if start:
            assert math.dist(pts[0], start) < 0.45  # on the satin's nearest stitch (0.4 mm apart)
        assert abs(pts[-1][0] - end[0]) < 1.0 and abs(pts[-1][1] - end[1]) <= 3.3
        # Every stitch along the column (not across it) runs down its middle: hidden travel.
        along = [(p, q) for p, q in zip(pts, pts[1:]) if abs(q[0] - p[0]) > 1.0 and abs(q[1] - p[1]) < 0.3]
        assert all(abs(p[1] - 1.5) < 0.05 and abs(q[1] - 1.5) < 0.05 for p, q in along)


def test_text_has_no_start_and_end_to_move():
    with pytest.raises(EndsError):
        set_end({"id": "t", "kind": "text"}, "start", [0, 0])


@pytest.mark.parametrize("angle", [0, 21, 45, 90, 135])
@pytest.mark.parametrize("at", [(0.36, 10), (20, 3), (-0.5, 0), (13, 0)])
def test_moving_to_the_end_never_crosses_rows_already_sewn(angle, at):
    """The rows before the end row finish beside it; the move on to the far rows crosses only
    rows still to be sewn. No long stitch runs across the finished top stitching."""
    from shapely.geometry import LineString

    obj = set_end(square(angle_deg=angle, underlay=[]), "end", list(at))
    pts = stitched(obj)
    a = math.radians(angle)
    sewn_rows = []
    for i, (p, q) in enumerate(zip(pts, pts[1:])):
        d = math.dist(p, q)
        along = abs(math.cos(math.atan2(q[1] - p[1], q[0] - p[0]) - a))
        if d > 0.9 and along > 0.97:
            sewn_rows.append(LineString([p, q]))
        elif d > 0.9 and sewn_rows:
            # A move across: it mustn't lie over rows sewn earlier (it would show on top).
            move = LineString([p, q])
            crossed = sum(1 for r in sewn_rows[:-2] if r.crosses(move))
            assert crossed == 0, (i, p, q, crossed)


def test_a_wide_satin_stops_on_the_side_chosen():
    """Top and bottom of a wide satin share their stitch across: it ends on the side the dot is on."""
    a = [[0, 0, "l"], [30, 0, "l"]]
    b = [[0, 20, "l"], [30, 20, "l"]]
    col = {"id": "s", "kind": "satin", "geometry": {"rail_a": a, "rail_b": b}, "params": {"split_mm": 7}, "transform": {}}
    for side in (0, 20):
        pts = stitched(set_end(col, "end", [15, side]))
        assert math.dist(pts[-1], (15, side)) < 1.5, (side, pts[-1])


def test_a_satin_never_starts_off_the_satin():
    """A start point left off the satin (its points moved later) doesn't sew a line over bare fabric."""
    rib = {"id": "r", "kind": "satin", "geometry": {"nodes": [[0, 0, "l"], [20, 0, "l"]], "width_mm": 3},
           "params": {"start_mm": [-15, 0]}, "transform": {}}
    pts = stitched(rib)
    assert min(p[0] for p in pts) > -2.0


def test_a_fill_in_pieces_ends_on_the_piece_its_end_is_on():
    o = {"id": "f", "kind": "fill", "transform": {},
         "geometry": {"outline": [[0, 0, "l"], [30, 0, "l"], [30, 10, "l"], [0, 10, "l"]],
                      "holes": [[[19, -1, "l"], [20, -1, "l"], [20, 11, "l"], [19, 11, "l"]]]},
         "params": {"angle_deg": 0, "end_mm": [5, 0]}}
    assert math.dist(stitched(o)[-1], (5, 0)) < 1.0


def test_optimize_jumps_can_still_improve_a_satin_whose_dots_were_moved():
    from threadline_engine.jumps import optimize_jumps

    thread = {"color": "#000000"}
    rib = {"id": "a", "kind": "satin", "geometry": {"nodes": [[0, 0, "l"], [40, 0, "l"]], "width_mm": 3},
           "params": {"start_mm": [0, 0]}, "thread": thread, "transform": {}, "threads": [], "ops": []}
    after = {"id": "b", "kind": "run", "geometry": {"nodes": [[-10, 5, "l"], [-20, 5, "l"]]},
             "params": {}, "thread": thread, "transform": {}, "threads": [], "ops": []}
    r = optimize_jumps({"items": [rib, after]})
    assert r["after_mm"] < r["before_mm"]
