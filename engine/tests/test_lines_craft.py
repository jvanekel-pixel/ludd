"""The craft line styles (digitize/lines/craft.py): backstitch, stem stitch, candlewicking, redwork
and French knots."""

import json
import math
import time
import zipfile

import pytest
from shapely.geometry import LineString, Point

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout, project
from threadline_engine.digitize import lines, ties
from threadline_engine.digitize import paths as dpaths
from threadline_engine.digitize import stitches as dz
from threadline_engine.digitize.lines import craft
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.stitches import JUMP, STITCH, TRIM, DigitizeError, RunParams, generate

NEW = ["backstitch", "stem", "candlewick", "redwork", "knots"]
THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}


def c(x, y):
    return [x, y, "c"]


def s(x, y):
    return [x, y, "s"]


LINE = [c(0, 0), c(30, 0)]
S_CURVE = [s(0, 0), s(20, 10), s(40, -10), s(60, 0)]
SQUARE = [c(0, 0), c(20, 0), c(20, 20), c(0, 20)]
CIRCLE = [s(10 * math.cos(2 * math.pi * i / 8), 10 * math.sin(2 * math.pi * i / 8)) for i in range(8)]
ELL = [c(0, 0), c(10, 0), c(10, 12)]


def _obj(nodes, closed=False, **params):
    return {"kind": "run", "geometry": {"nodes": nodes, "closed": closed}, "params": params}


def _recs(nodes, closed=False, **params):
    """A line's records without lock stitches, so every needle point is the style's own."""
    return generate(_obj(nodes, closed, tie_in=False, tie_off=False, **params))[0]


def _needles(recs):
    return [(x, y) for x, y, k in recs if k == STITCH]


def _threads(recs):
    """The thread between two needle drops in a row, as (from, to)."""
    return [(a[:2], b[:2]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]


def _covering(recs, p):
    """How many stitches lie over the point `p` of a straight stretch of the line."""
    return sum(1 for a, b in _threads(recs)
               if LineString([a, b]).distance(Point(p)) < 1e-6 and math.dist(a, p) > 1e-6 and math.dist(b, p) > 1e-6)


def _knots(recs, size):
    """The centers of the knots: a needle point, then eleven a knot's radius away, then back."""
    pts, r, found, i = _needles(recs), size / 2, [], 0
    while i + 12 < len(pts):
        mid = pts[i]
        if all(abs(math.dist(mid, p) - r) < 1e-6 for p in pts[i + 1 : i + 12]) and math.dist(pts[i + 12], mid) < 1e-6:
            found.append(mid)
            i += 12
        else:
            i += 1
    return found


def _along(nodes, p, closed=False):
    """How far along the line the point nearest `p` is, and how far off the line `p` is."""
    poly, _ = flatten(nodes, closed)
    line = LineString(poly + [poly[0]] if closed else poly)
    return line.project(Point(p)), line.distance(Point(p))


# ---------------------------------------------------------------- the five styles


def test_five_styles_registered():
    assert list(lines.REGISTRY) == ["single", "triple", "bean", "motif", *NEW]
    for name in NEW[:4]:
        assert callable(lines.REGISTRY[name].points) and lines.REGISTRY[name].recs is None, name
    assert callable(lines.REGISTRY["knots"].recs)
    for name in NEW:
        assert generate(_obj(LINE, style=name))[0], name


def test_backstitch_holes_are_half_a_stitch_apart():
    xs = [x for x, _ in _needles(_recs(LINE, style="backstitch", stitch_mm=2.5))]
    assert xs[:6] == pytest.approx([0, 2.5, 1.25, 3.75, 2.5, 5.0])  # forward a stitch, back half
    assert xs[-1] == pytest.approx(30)
    assert sorted({round(x, 6) for x in xs}) == pytest.approx([1.25 * k for k in range(25)])
    # A line half stitches don't divide: still evenly spaced, no further apart than half a stitch.
    holes = sorted({round(x, 6) for x, _ in _needles(_recs([c(0, 0), c(31, 0)], style="backstitch", stitch_mm=3))})
    gaps = [b - a for a, b in zip(holes, holes[1:])]
    assert max(gaps) - min(gaps) < 1e-5 and max(gaps) <= 1.5


def test_backstitch_covers_the_line_three_times():
    recs = _recs(LINE, style="backstitch", stitch_mm=2.5)
    # Everywhere but the first and last half stitch, three stitches lie over the line.
    for k in range(13, 287):
        assert _covering(recs, (k / 10 + 0.0137, 0.0)) == 3, k / 10


def test_backstitch_and_stem_never_cut_a_corner():
    sides = LineString([(0, 0), (10, 0), (10, 12)])
    for a, b in _threads(_recs(ELL, style="backstitch", stitch_mm=3)):
        assert sides.buffer(1e-6).covers(LineString([a, b]))
    stem = _recs(ELL, style="stem", stitch_mm=3, stem_width_mm=0.8)
    invariants.assert_sane(stem, inside=sides.buffer(0.4), tolerance_mm=0.1)


def test_stem_stitches_slant_and_overlap():
    pts = _needles(_recs(LINE, style="stem", stitch_mm=3, stem_width_mm=0.8))
    first = [(0, -0.4), (3, 0.4), (1.5, -0.4), (4.5, 0.4), (3, -0.4)]
    assert pts[:5] == [pytest.approx(p) for p in first]
    tops = [(pts[i], pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
    assert len(tops) == 19
    for a, b in tops:  # each slants off the line, and the next starts half way along it
        assert 10 <= math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) <= 25, (a, b)
    assert [b[0] - a[0] for (a, _), (b, _) in zip(tops, tops[1:])] == pytest.approx([1.5] * 18)
    # On a curve the needle goes down half the width off the line, either side.
    off = [_along(S_CURVE, p)[1] for p in _needles(_recs(S_CURVE, style="stem", stem_width_mm=1.6))]
    assert min(off) > 0.75 and max(off) < 0.81


def test_candlewick_knots_evenly_spaced_on_the_line():
    recs = _recs(LINE, style="candlewick", knot_mm=1.6, knot_gap_mm=4)
    knots = _knots(recs, 1.6)
    assert [x for x, _ in knots] == pytest.approx([30 * k / 8 for k in range(9)])  # 30 mm: 8 gaps of 3.75
    assert all(abs(y) < 1e-9 for _, y in knots)
    # On a curve: on the line, the same distance apart along it.
    places = [_along(S_CURVE, p) for p in _knots(_recs(S_CURVE, style="candlewick", knot_gap_mm=6), 1.6)]
    assert all(off < 1e-6 for _, off in places)
    gaps = [b - a for (a, _), (b, _) in zip(places, places[1:])]
    assert len(gaps) >= 8 and max(gaps) - min(gaps) < 0.01 and 5 < gaps[0] < 7
    # Between the knots, a single run along the line.
    run = [(a, b) for a, b in _threads(recs) if abs(a[1]) < 1e-9 and abs(b[1]) < 1e-9 and math.dist(a, b) > 1]
    assert sum(math.dist(a, b) for a, b in run) == pytest.approx(30, abs=1e-6)
    assert max(math.dist(a, b) for a, b in run) <= 2.5 + 1e-9


@pytest.mark.parametrize("length,gap,knot,count", [(30, 4, 1.6, 9), (6, 4, 1.6, 3), (5, 4, 1.6, 2), (3, 4, 1.6, 2),
                                                   (2, 4, 1.6, 1), (10, 4, 3, 3)])
def test_candlewick_knots_are_never_closer_than_touching(length, gap, knot, count):
    knots = _knots(_recs([c(0, 0), c(length, 0)], style="candlewick", knot_gap_mm=gap, knot_mm=knot), knot)
    assert len(knots) == count, knots
    assert all(b[0] - a[0] >= knot + 1 - 1e-9 for a, b in zip(knots, knots[1:]))


def test_candlewick_refuses_knots_that_would_touch():
    with pytest.raises(DigitizeError, match="^Knots this close would touch: make the gap at least 4 mm$"):
        generate(_obj(LINE, style="candlewick", knot_mm=3, knot_gap_mm=3.5))
    with pytest.raises(DigitizeError, match="make the gap at least 2.6 mm"):
        generate(_obj(LINE, style="candlewick", knot_gap_mm=2.5))
    assert generate(_obj(LINE, style="candlewick", knot_gap_mm=2.6))[0]


def test_a_knot_is_ten_short_stitches_round_its_center():
    recs = _recs([c(0, 0), c(20, 0)], style="knots", knot_mm=2)
    knot = _needles(recs)[:13]  # the middle, the star twice round, the middle again
    assert knot[0] == pytest.approx((0, 0)) and knot[-1] == pytest.approx((0, 0))
    ring = knot[1:-1]
    assert [math.dist((0, 0), p) for p in ring] == pytest.approx([1.0] * 11)
    stitches = [math.dist(a, b) for a, b in zip(ring, ring[1:])]
    assert len(stitches) == 10 and stitches == pytest.approx([0.951 * 2] * 10, abs=0.002)
    angle = lambda p: math.degrees(math.atan2(p[1], p[0]))  # noqa: E731
    order = [round((angle(p) - angle(ring[0])) / 72) % 5 for p in ring]
    assert order == [0, 2, 4, 1, 3, 0, 2, 4, 1, 3, 0]
    assert len({(round(x, 6), round(y, 6)) for x, y in ring}) == 5


def test_french_knots_sit_on_the_points_with_jumps_between():
    points = [(0, 0), (2.6, 0), (12, 0), (12, 2.5), (15.05, 2.5)]
    recs = _recs([c(*p) for p in points], style="knots", knot_mm=1.6)
    assert _knots(recs, 1.6) == [pytest.approx(p) for p in points]
    jumps = [i for i, r in enumerate(recs) if r[2] == JUMP]
    assert [recs[i][:2] for i in jumps] == [pytest.approx(p) for p in points[1:]]  # each jump to the next point
    # Trimmed only where the jump is over 3 mm.
    assert [recs[i - 1][2] == TRIM for i in jumps] == [False, True, False, True]
    assert invariants.count(recs, TRIM) == 2


def test_french_knots_closer_than_a_knot_are_left_out_with_a_note():
    nodes = [c(0, 0), c(1.0, 0), c(1.7, 0), c(10, 0)]
    recs, warnings = generate(_obj(nodes, style="knots", knot_mm=1.6, tie_in=False, tie_off=False))
    assert _knots(recs, 1.6) == [pytest.approx(p) for p in [(0, 0), (1.7, 0), (10, 0)]]
    assert warnings == ["1 French knot was left out: points closer together than the knot size (1.6 mm) "
                        "would pile one knot on another. Move them further apart to sew them all."]
    twice = generate(_obj(nodes + [c(10.2, 0)], style="knots", knot_mm=1.6))[1]
    assert twice[0].startswith("2 French knots were left out")
    # Points exactly a knot apart are all sewn, with no note.
    assert generate(_obj([c(0, 0), c(1.6, 0)], style="knots"))[1] == []


def test_redwork_sews_every_stretch_twice_and_ends_where_it_started():
    recs = _recs(LINE, style="redwork", stitch_mm=2.5)
    for k in range(1, 299):
        assert _covering(recs, (k / 10 + 0.0137, 0.0)) == 2, k / 10
    assert _needles(recs)[0] == _needles(recs)[-1] == (0, 0)
    square = _recs(SQUARE, closed=True, style="redwork", stitch_mm=3)  # twice round
    for at in range(1, 80):
        t = at + 0.0137
        p = [(t, 0), (20, t - 20), (60 - t, 20), (0, 80 - t)][int(t // 20)]
        assert _covering(square, p) == 2, p
    assert _needles(square)[0] == pytest.approx((0, 0)) and _needles(square)[-1] == pytest.approx((0, 0))


def test_redwork_return_holes_fall_between():
    xs = [x for x, _ in _needles(_recs(LINE, style="redwork", stitch_mm=3))]
    out = [3 * k for k in range(11)]
    assert xs == pytest.approx(out + [28.5 - 3 * k for k in range(10)] + [0])
    # Round a corner the way back goes through it too, so no stitch cuts across it.
    ell = _needles(_recs(ELL, style="redwork", stitch_mm=3))
    assert sum(1 for p in ell if math.dist(p, (10, 0)) < 1e-9) == 2
    # Twice round a closed line, the second round's holes between the first's.
    pts = _needles(_recs(SQUARE, closed=True, style="redwork", stitch_mm=3))
    side = [20 * k / 7 for k in range(8)]
    first = [x for x, y in pts[:29] if abs(y) < 1e-9 and 0 < x < 20]
    second = [x for x, y in pts[29:] if abs(y) < 1e-9 and 0 < x < 20]
    assert first == pytest.approx(side[1:-1])
    assert second == pytest.approx([(a + b) / 2 for a, b in zip(side, side[1:])])


def _hits_cases():
    cases = {
        "candlewick_tight": _obj([c(0, 0), c(60, 0)], style="candlewick", knot_mm=1, knot_gap_mm=2),
        "candlewick_big": _obj([c(0, 0), c(60, 0)], style="candlewick", knot_mm=3, knot_gap_mm=4),
        "candlewick_square": _obj(SQUARE, closed=True, style="candlewick"),
        "candlewick_curve": _obj(S_CURVE, style="candlewick", knot_mm=1, knot_gap_mm=2),
        "knots_touching_small": _obj([c(k, 0) for k in range(20)], style="knots", knot_mm=1),
        "knots_touching": _obj([c(1.6 * k, 0) for k in range(20)], style="knots"),
        # A little cluster, as a flower's middle: knots in a hexagonal bunch, just touching.
        "knots_cluster": _obj([c(1.6 * (i + 0.5 * (j % 2)), 1.6 * j * math.sqrt(3) / 2) for j in range(4)
                               for i in range(4)], style="knots"),
    }
    return cases


@pytest.mark.parametrize("name", sorted(_hits_cases()))
def test_knots_do_not_trip_the_needle_hits_check(name):
    # (The check counts needle drops in 1 mm squares, so try the shape in several places on its grid.)
    for dx, dy in [(0, 0), (0.25, 0.5), (0.5, 0.25), (0.75, 0.75), (0.5, 0.5)]:
        item = {**_hits_cases()[name], "id": "a", "thread": THREAD, "transform": {"x": dx, "y": dy}}
        codes = [found["code"] for found in layout.check({"items": [item]})["checks"]]
        assert "needle_hits" not in codes, (dx, dy)


@pytest.mark.parametrize("params,says", [
    ({"style": "knots", "knot_mm": 0.5}, "^Knot size must be between 1 and 3 mm$"),
    ({"style": "candlewick", "knot_mm": 3.5}, "^Knot size must be between 1 and 3 mm$"),
    ({"style": "candlewick", "knot_gap_mm": 1}, "^Between knots must be between 2 and 15 mm$"),
    ({"style": "candlewick", "knot_gap_mm": 16}, "^Between knots must be between 2 and 15 mm$"),
    ({"style": "stem", "stem_width_mm": 3}, "^Width must be between 0.3 and 2.5 mm$"),
    ({"style": "stem", "stem_width_mm": 0.2}, "^Width must be between 0.3 and 2.5 mm$"),
    ({"style": "backstitch", "stitch_mm": 13}, "^Stitch length must be between 0.5 and 12 mm$"),
])
def test_style_settings_are_range_checked(params, says):
    with pytest.raises(DigitizeError, match=says):
        RunParams.from_dict(params)


def test_the_settings_have_their_defaults():
    assert RunParams.from_dict({"style": "stem"}).value("stem_width_mm") == 0.8
    assert RunParams.from_dict({"style": "candlewick"}).extra == {"knot_mm": 1.6, "knot_gap_mm": 4}
    assert RunParams.from_dict({"style": "knots"}).extra == {"knot_mm": 1.6}


@pytest.mark.parametrize("style", NEW)
def test_the_hand_sewn_look_leaves_them_as_they_are(style):
    assert _recs(SQUARE, style=style, hand_pct=80) == _recs(SQUARE, style=style)


@pytest.mark.parametrize("style", NEW)
def test_closed_lines_meet_without_a_gap(style):
    for nodes in (SQUARE, CIRCLE):
        pts = _needles(_recs(nodes, closed=True, style=style, knot_mm=1.6))
        if style == "knots":
            centers = _knots(_recs(nodes, closed=True, style=style), 1.6)
            assert centers == [pytest.approx((n[0], n[1])) for n in nodes]  # one knot a point, none twice
            continue
        assert math.dist(pts[0], pts[-1]) < 1e-6, nodes
    # Begun where the green dot says, part way along a side.
    pts = _needles(_recs(SQUARE, closed=True, style=style, start_mm=[10, -1]))
    if style == "knots":
        assert pts[0] == pytest.approx((0, 0))  # the knot nearest the dot is sewn first
    else:
        near = 0.4 if style == "stem" else 1e-6  # stem stitch starts half its width off the line
        assert math.dist(pts[0], (10, 0)) <= near + 1e-6 and math.dist(pts[0], pts[-1]) < 1e-6


def test_backstitch_goes_all_round_a_smooth_circle_three_times():
    recs = _recs(CIRCLE, closed=True, style="backstitch")
    where = [math.atan2(y, x) for x, y in _needles(recs)]
    spans = [(a, math.remainder(b - a, 2 * math.pi)) for a, b in zip(where, where[1:])]
    for k in range(360):
        at = -math.pi + 2 * math.pi * (k + 0.37) / 360
        assert sum(1 for a, d in spans if 0 < math.remainder(at - a, 2 * math.pi) / d < 1) == 3, k


# ---------------------------------------------------------------- sizes and limits


def _sewn_at(obj, scale):
    """The object made `scale` times bigger with the handles, as the app does it: records in mm."""
    item = {**obj, "id": "a", "thread": THREAD, "transform": {"scale_x": scale, "scale_y": scale}}
    forget_stitches()
    return [(x / 10, y / 10, k) for x, y, k, *_ in layout.render({"items": [item]}).blocks[0].recs]


def test_knot_and_rope_sizes_stay_in_mm_when_resized():
    ties_off = {"tie_in": False, "tie_off": False}
    knots = _knots(_sewn_at(_obj(LINE, style="candlewick", knot_gap_mm=4, **ties_off), 2), 1.6)
    assert [b[0] - a[0] for a, b in zip(knots, knots[1:])] == pytest.approx([4] * 15, abs=1e-6)  # 60 mm now
    rope = _needles(_sewn_at(_obj(LINE, style="stem", **ties_off), 2))
    assert max(abs(y) for _, y in rope) == pytest.approx(0.4) and min(abs(y) for _, y in rope) == pytest.approx(0.4)
    french = _sewn_at(_obj([c(0, 0), c(10, 0)], style="knots", **ties_off), 2)
    centers = _knots(french, 1.6)
    assert len(centers) == 2 and math.dist(*centers) == pytest.approx(20)


# Rows 900 mm long, 2 mm apart: 180 m of line.
LONG = [c(900 * (k % 2), 2 * k) for k in range(200)]
MANY_POINTS = [c(3 * (k % 300), 3 * (k // 300)) for k in range(6000)]


@pytest.mark.parametrize("style,nodes", [("backstitch", LONG), ("stem", LONG), ("candlewick", LONG),
                                         ("redwork", LONG), ("knots", MANY_POINTS)])
def test_too_many_stitches_are_refused_before_they_are_laid_out(style, nodes, monkeypatch):
    laid = []
    real = dpaths.point_at
    monkeypatch.setattr(craft, "point_at", lambda *a: laid.append(1) or real(*a))
    start = time.monotonic()
    with pytest.raises(DigitizeError, match=r"^This line would need about [\d,]+ stitches, far more than any design\. "):
        generate(_obj(nodes, style=style))
    assert time.monotonic() - start < 5 and len(laid) < 2000  # a few points measured, none laid


def test_projects_name_each_feature(tmp_path):
    cases = {
        "line_backstitch": _obj(LINE, style="backstitch"),
        "line_stem": _obj(LINE, style="stem"),
        "line_candlewick": _obj(LINE, style="candlewick"),
        "line_redwork": _obj(LINE, style="redwork"),
        "line_knots": _obj(LINE, style="knots"),
        "fill_blackwork": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "blackwork"}},
        "motif_side": _obj(LINE, style="motif", motif="blanket", motif_side="left"),
        "tie_styles": _obj(LINE, tie_style="triangle"),
    }
    for i, (feature, obj) in enumerate(cases.items()):
        lay = {"items": [{"id": "a", "thread": THREAD, **obj}]}
        layout.render(lay)  # it sews
        saved = project.save(str(tmp_path / f"p{i}"), {"title": "t", "layout": lay, "images": []})
        with zipfile.ZipFile(saved["path"]) as z:
            features = json.loads(z.read("project.json"))["features"]
        assert feature in features, features
        assert project.open_project(saved["path"])["layout"]["items"][0]["params"] == obj["params"]
    # A centered motif, the usual locks and a shape with no lock stitches need none of these.
    plain = [_obj(LINE, style="motif", motif="blanket", motif_side="center"),
             _obj(LINE, tie_style="standard"), _obj(LINE, tie_style="backtack", tie_in=False, tie_off=False)]
    used = project._features({"items": plain})
    assert used == {"motif_lines"}


# ---------------------------------------------------------------- snapshots and invariants


S_AT = [s(7, 11), s(27, 21), s(47, 1), s(67, 11)]
SNAPSHOT_CASES = {
    "backstitch_s_curve": _obj(S_AT, style="backstitch"),
    "stem_s_curve": _obj(S_AT, style="stem"),
    "candlewick_line": _obj([c(7, 11), c(67, 11)], style="candlewick"),
    "redwork_closed_square": _obj([c(7, 11), c(27, 11), c(27, 31), c(7, 31)], closed=True, style="redwork"),
    "knots_five": _obj([c(7, 11), c(11.5, 15), c(17, 12), c(25, 14.5), c(31, 11)], style="knots"),
}
REACH_MM = {"backstitch": 0.1, "stem": 0.45, "candlewick": 0.85, "redwork": 0.1, "knots": 0.85}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("lines_craft", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    recorded = json.loads((SNAPSHOT_DIR / "lines_craft.json").read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, dz, dpaths, craft, ties, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_pass_the_invariants(name):
    obj = SNAPSHOT_CASES[name]
    g, style = obj["geometry"], obj["params"]["style"]
    poly, _ = flatten(g["nodes"], g["closed"])
    line = LineString(poly + [poly[0]] if g["closed"] else poly)
    jumps = len(g["nodes"]) - 1 if style == "knots" else 0
    invariants.assert_sane(generate(obj)[0], inside=line.buffer(REACH_MM[style]), tolerance_mm=0.05,
                           max_jumps=jumps, max_trims=jumps)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    invariants.assert_moves_with_shape(obj, 3.3, -8.1)
    invariants.assert_moves_with_shape(obj, -250.7, 1000.9)
