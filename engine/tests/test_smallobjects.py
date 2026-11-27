"""Buttonholes and eyelets (digitize/smallobjects.py, RPC shape.buttonhole and shape.eyelet):
ordinary shapes, made through the engine the way the app asks for them."""

import json
import math

import pyembroidery as pe
import pytest
from shapely.geometry import LineString, Point, Polygon, box
from shapely import affinity

import invariants
from threadline_engine import fabrics, layout
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.stitches import FOLD_WARNING, generate, width_comp
from threadline_engine.methods import dispatcher

THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}
SIZES = [(16, 5, 1.0), (8, 3, 0.6), (40, 8, 2.0), (22, 6, 1.4), (12, 8, 0.6)]
FABRICS = ["woven", "denim", "knit", "fleece", "towel", "stretch", "felt"]


def _call(method, **params):
    return dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))


def _made(method="shape.buttonhole", **params):
    out = _call(method, **params)
    assert "result" in out, out
    return out["result"]


def _layout(objects, **extra):
    """The shapes as the app adds them: in sewing order, one thread, with Fewer jumps & trims on
    (as new designs have it)."""
    items = [{**o, "id": f"o{i}", "thread": THREAD} for i, o in enumerate(objects)]
    return {"items": items, "travel_under": True, **extra}


def _sewn(lay):
    """The design as sewn: (x mm, y mm, command, item) records."""
    r = layout.render(lay)
    return [(x / 10, y / 10, c & pe.COMMAND_MASK, item) for (x, y, c), item in zip(r.pattern.stitches, r.item_of)]


def _threads(records):
    return [LineString([a[:2], b[:2]]) for a, b in zip(records, records[1:]) if a[2] == b[2] == pe.STITCH]


def _round(nodes):
    return [(round(x, 4) + 0.0, round(y, 4) + 0.0) for x, y, *_ in nodes]


def test_bar_buttonhole_is_two_lips_and_two_bars():
    made = _made(length_mm=16, width_mm=5, style="bar", cut_gap_mm=1.0)
    assert made["warnings"] == []
    objects = made["objects"]
    assert [o["kind"] for o in objects] == ["satin"] * 4
    assert [o["name"] for o in objects] == ["Buttonhole lip 1", "Buttonhole lip 2", "Buttonhole bar 1",
                                            "Buttonhole bar 2"]
    assert [o["geometry"]["width_mm"] for o in objects] == [2, 2, 1.5, 1.5]
    assert not any(o["geometry"].get("closed") for o in objects)
    assert [o["params"]["underlay"] for o in objects] == [["center"], ["center"], [], []]
    lines = [_round(o["geometry"]["nodes"]) for o in objects]
    # Two lips 16 mm long, 1 mm apart: sewn down one and back up the other...
    assert lines[:2] == [[(-8, -1.5), (8, -1.5)], [(8, 1.5), (-8, 1.5)]]
    # ...then a tack across each end, the full 5 mm width, covering its last 1.5 mm.
    assert lines[2:] == [[(-7.25, 2.5), (-7.25, -2.5)], [(7.25, -2.5), (7.25, 2.5)]]


def test_the_defaults_are_a_16_by_5_bar_buttonhole_and_a_4_mm_eyelet():
    assert _made() == _made(length_mm=16, width_mm=5, style="bar", cut_gap_mm=1.0, angle_deg=0, at=[0, 0])
    assert _made("shape.eyelet") == _made("shape.eyelet", hole_mm=4, ring_mm=1.6, at=[0, 0])


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("fabric", ["woven", "knit", "stretch"])
def test_the_slit_is_left_clear(size, fabric):
    length, width, cut = size
    objects = _made(length_mm=length, width_mm=width, cut_gap_mm=cut)["objects"]
    records = _sewn(_layout(objects, fabric=fabric))
    pull = fabrics.get(fabric)["pull_comp_mm"]
    # Between the tacks, nothing sews in the slit (but the edge pad's share of each side).
    lip_spare = width_comp(pull, (width - cut) / 2) / 2 + 0.02
    tack_spare = width_comp(pull, 1.5) / 2 + 0.02
    slit = box(-length / 2 + 1.5 + tack_spare, -cut / 2 + lip_spare, length / 2 - 1.5 - tack_spare, cut / 2 - lip_spare)
    assert slit.area > 0
    assert not [t for t in _threads(records) if t.intersects(slit)]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("fabric", FABRICS)
def test_lips_join_without_a_jump(size, fabric):
    length, width, cut = size
    made = _made(length_mm=length, width_mm=width, cut_gap_mm=cut, angle_deg=30, at=[3, -2])["objects"]
    for travel_under in (True, False):
        records = _sewn(_layout(made, fabric=fabric, travel_under=travel_under))
        stitched = [(i, r) for i, r in enumerate(records) if r[2] == pe.STITCH]
        last = max(i for i, r in stitched if r[3] == 0)  # the first lip's last stitch...
        first = min(i for i, r in stitched if r[3] == 1)  # ...and the second's first
        between = {r[2] for r in records[last + 1 : first + 1]}
        if travel_under:  # sewn straight over, under the tack that then covers it
            assert between == {pe.STITCH}, between
        else:  # a short move: never a trim
            assert pe.TRIM not in between, between
        trims = [i for i, r in enumerate(records) if r[2] == pe.TRIM]
        assert len(trims) == 1 and records[trims[0]][3] in (2, 3)  # only from one tack to the other


def test_rounded_buttonhole_is_one_closed_ribbon():
    made = _made(style="round", length_mm=16, width_mm=5, cut_gap_mm=1)
    [obj] = made["objects"]
    assert made["warnings"] == [] and obj["kind"] == "satin" and obj["name"] == "Rounded buttonhole"
    assert obj["geometry"]["closed"] and obj["geometry"]["width_mm"] == 2 and obj["params"]["underlay"] == ["center"]
    middle = Polygon(flatten(obj["geometry"]["nodes"], True)[0])
    assert middle.buffer(1.0).bounds == pytest.approx((-8, -2.5, 8, 2.5), abs=0.06)  # 16 x 5 over all
    slit = middle.buffer(-1.0)
    assert slit.bounds == pytest.approx((-6, -0.5, 6, 0.5), abs=0.06)  # a 1 mm slit with round ends
    assert not [t for t in _threads(_sewn(_layout([obj]))) if t.intersects(slit.buffer(-0.12))]
    # As long as it's wide, it is a ring.
    [ring] = _made(style="round", length_mm=8, width_mm=8, cut_gap_mm=2)["objects"]
    assert Polygon(flatten(ring["geometry"]["nodes"], True)[0]).bounds == pytest.approx((-2.5, -2.5, 2.5, 2.5), abs=0.06)


def test_the_buttonhole_is_turned_and_moved():
    plain = _made(length_mm=20)["objects"]
    turned = _made(length_mm=20, angle_deg=90, at=[10, 5])["objects"]
    for a, b in zip(plain, turned):
        want = [(10 - y, 5 + x) for x, y in _round(a["geometry"]["nodes"])]
        assert _round(b["geometry"]["nodes"]) == [pytest.approx(p, abs=1e-3) for p in want]
        for key in ("start_mm", "end_mm"):
            if key in a["params"]:
                x, y = a["params"][key]
                assert b["params"][key] == pytest.approx([10 - y, 5 + x], abs=1e-3)


@pytest.mark.parametrize("method,params,says", [
    ("shape.buttonhole", {"length_mm": 7}, "Length must be between 8 and 40 mm"),
    ("shape.buttonhole", {"length_mm": 41}, "Length must be between 8 and 40 mm"),
    ("shape.buttonhole", {"length_mm": "16"}, "Length must be between 8 and 40 mm"),
    ("shape.buttonhole", {"width_mm": 2.9}, "Width must be between 3 and 8 mm"),
    ("shape.buttonhole", {"width_mm": 8.1}, "Width must be between 3 and 8 mm"),
    ("shape.buttonhole", {"cut_gap_mm": 0.5}, "Cut gap must be between 0.6 and 2 mm"),
    ("shape.buttonhole", {"cut_gap_mm": 2.1}, "Cut gap must be between 0.6 and 2 mm"),
    ("shape.buttonhole", {"width_mm": 3, "cut_gap_mm": 1.2}, "Make the buttonhole wider or the cut narrower"),
    ("shape.buttonhole", {"width_mm": 3, "cut_gap_mm": 1.2, "style": "round"},
     "Make the buttonhole wider or the cut narrower"),
    ("shape.buttonhole", {"style": "slot"}, "Unknown buttonhole style: slot"),
    ("shape.buttonhole", {"angle_deg": "up"}, "The angle must be a number"),
    ("shape.buttonhole", {"at": [1]}, "The place must be two numbers"),
    ("shape.eyelet", {"hole_mm": 1.9}, "Hole must be between 2 and 12 mm"),
    ("shape.eyelet", {"hole_mm": 12.1}, "Hole must be between 2 and 12 mm"),
    ("shape.eyelet", {"ring_mm": 0.9}, "Ring must be between 1 and 3 mm"),
    ("shape.eyelet", {"ring_mm": 3.1}, "Ring must be between 1 and 3 mm"),
    ("shape.eyelet", {"at": "here"}, "The place must be two numbers"),
])
def test_sizes_are_checked(method, params, says):
    out = _call(method, **params)
    assert out["error"]["code"] == -32000 and out["error"]["message"] == says, out


def test_the_limits_themselves_are_allowed():
    for params in ({"length_mm": 8, "width_mm": 3, "cut_gap_mm": 1.0}, {"length_mm": 40, "width_mm": 8},
                   {"width_mm": 3.2, "cut_gap_mm": 1.2}):
        assert _made(**params)["objects"]
    for hole, ring in [(2, 1), (12, 3)]:
        assert _made("shape.eyelet", hole_mm=hole, ring_mm=ring)["objects"]


def test_eyelet_is_a_run_then_a_ring():
    made = _made("shape.eyelet", hole_mm=4, ring_mm=1.6, at=[10, -5])
    run, ring = made["objects"]
    assert made["warnings"] == []
    assert (run["kind"], run["name"], run["params"]["style"], run["geometry"]["closed"]) == (
        "run", "Eyelet run", "triple", True)
    assert (ring["kind"], ring["name"], ring["geometry"]["width_mm"], ring["geometry"]["closed"]) == (
        "satin", "Eyelet ring", 1.6, True)
    middle = Point(10, -5)
    for obj, radius in [(run, 2.3), (ring, 2.8)]:  # a run 0.3 mm outside the hole; the ring from its edge
        around = [middle.distance(Point(p)) for p in flatten(obj["geometry"]["nodes"], True)[0]]
        assert min(around) > radius - 0.06 and max(around) < radius + 0.01
    records = _sewn(_layout(made["objects"]))
    needles = [middle.distance(Point(r[:2])) for r in records if r[2] == pe.STITCH]
    assert min(needles) > 2 - 0.15 and max(needles) < 3.6 + 0.15
    assert not [t for t in _threads(records) if t.distance(middle) < 2 - 0.15]  # the hole stays open
    stitched = [r for r in records if r[2] == pe.STITCH]
    assert [r[3] for r in stitched] == sorted(r[3] for r in stitched)  # the run first, then the ring


def test_an_eyelet_ring_wider_than_the_hole_warns_that_it_bunches():
    assert _made("shape.eyelet", hole_mm=2, ring_mm=3)["warnings"] == [FOLD_WARNING]
    assert _made("shape.eyelet", hole_mm=2.5, ring_mm=2.6)["warnings"] == [FOLD_WARNING]
    assert _made("shape.eyelet", hole_mm=2, ring_mm=2)["warnings"] == []


def _area(obj):
    g = obj["geometry"]
    poly, _ = flatten(g["nodes"], g.get("closed", False))
    line = LineString(poly + [poly[0]] if g.get("closed") else poly)
    return line.buffer((g.get("width_mm") or 0) / 2 + 0.01, cap_style="square")


CASES = [("shape.buttonhole", {}), ("shape.buttonhole", {"length_mm": 8, "width_mm": 3, "cut_gap_mm": 0.6}),
         ("shape.buttonhole", {"length_mm": 40, "width_mm": 8, "cut_gap_mm": 2, "angle_deg": 37, "at": [4, 9]}),
         ("shape.buttonhole", {"style": "round"}), ("shape.buttonhole", {"style": "round", "angle_deg": 90}),
         ("shape.eyelet", {}), ("shape.eyelet", {"hole_mm": 2, "ring_mm": 1}),
         ("shape.eyelet", {"hole_mm": 12, "ring_mm": 3, "at": [-7, 3]})]


@pytest.mark.parametrize("method,params", CASES, ids=[f"{m[6:]}-{i}" for i, (m, _) in enumerate(CASES)])
def test_generated_objects_render_and_pass_invariants(method, params):
    made = _made(method, **params)
    rendered = layout.render_summary(_layout(made["objects"]))
    assert [w for w in rendered["warnings"] if w["level"] == "warning"] == []
    for obj in made["objects"]:
        recs, warnings = generate(obj)
        assert warnings == [], obj["name"]
        invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.55)
        invariants.assert_deterministic(lambda: generate(obj)[0])
        invariants.assert_moves_with_shape(obj, 12.3, -4.56)
