"""Optimize jumps: each piece's start and end chosen so same-thread jumps are short."""

import math

from threadline_engine import layout as L
from threadline_engine.jumps import optimize_jumps

I = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}
RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}


def obj(i, kind, geometry, thread=RED, params=None):
    return {"id": i, "kind": kind, "geometry": geometry, "params": params or {}, "thread": thread, "transform": I, "threads": [], "ops": []}


def sq(x, y, w):
    return [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]]


def circle(cx, cy, r, n=16):
    return [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), "s"] for k in range(n)]


def layout_of(*items):
    return {"version": 1, "items": list(items)}


def applied(lay, changes):
    out = []
    for it in lay["items"]:
        c = changes.get(it["id"], {})
        out.append({**it, **({"geometry": c["geometry"]} if "geometry" in c else {}), **({"params": c["params"]} if "params" in c else {})})
    return layout_of(*out)


def same_thread_jumps(lay):
    r = L.render(lay)
    own = {}
    for (x, y, k), it, src in zip(r.pattern.stitches, r.item_of, r.src_of):
        if it >= 0 and src >= 0 and k & L.M == 0:
            own.setdefault(it, []).append((x / 10, y / 10))
    return sum(math.dist(own[i - 1][-1], own[i][0]) for i in range(1, len(lay["items"])))


def test_lines_fills_and_borders_are_turned_so_the_jumps_are_short():
    lay = layout_of(
        # A line drawn away from the next piece, a fill that starts on its far side, a ring.
        obj("a", "run", {"nodes": [[30, 0, "c"], [0, 0, "c"]]}),
        obj("b", "fill", {"outline": sq(40, -5, 10)[2:] + sq(40, -5, 10)[:2]}),
        obj("c", "satin", {"nodes": circle(80, 0, 8), "width_mm": 2, "closed": True}),
    )
    before = same_thread_jumps(lay)
    r = optimize_jumps(lay)
    after = same_thread_jumps(applied(lay, r["changes"]))
    assert r["before_mm"] > r["after_mm"]
    assert after < before * 0.5
    assert set(r["changes"]) <= {"a", "b", "c"}
    # The sewing order never changes.
    assert [it["id"] for it in applied(lay, r["changes"])["items"]] == ["a", "b", "c"]


def test_a_colour_change_is_left_alone_and_nothing_to_do_changes_nothing():
    lay = layout_of(
        obj("a", "run", {"nodes": [[30, 0, "c"], [0, 0, "c"]]}),
        obj("b", "run", {"nodes": [[60, 0, "c"], [90, 0, "c"]]}, thread=BLUE),
    )
    assert optimize_jumps(lay)["changes"] == {}
    near = layout_of(obj("a", "run", {"nodes": [[0, 0, "c"], [30, 0, "c"]]}), obj("b", "run", {"nodes": [[31, 0, "c"], [60, 0, "c"]]}))
    assert optimize_jumps(near)["changes"] == {}


def test_a_fill_starts_at_the_edge_nearest_the_piece_before():
    lay = layout_of(
        obj("a", "run", {"nodes": [[-20, 25, "c"], [0, 25, "c"]]}),
        obj("b", "fill", {"outline": sq(0, 0, 20)}),
    )
    r = optimize_jumps(lay)
    assert r["changes"]["b"]["params"]["start_mm"] is not None
    assert r["after_mm"] < r["before_mm"]
