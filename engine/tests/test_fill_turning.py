"""Turning fills: a tatami fill with two or more angle lines, whose rows turn smoothly to follow
each line where it lies (digitize/fills/turning.py, Phase 6 C2)."""

import json
import math

import pytest
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine import layout, project
from threadline_engine.digitize import stitches
from threadline_engine.digitize.fills import turning
from threadline_engine.digitize.stitches import STITCH, FillParams, fill_parts, generate, transform_geometry
from threadline_engine.layout import Transform

SPACING = 0.4
TOO_SHARP = ("The stitch direction turns too sharply for this shape here. Move the angle lines further apart or "
             "make the turn gentler.")


def _nodes(points):
    return [[x, y, "c"] for x, y in points]


def _line(cx, cy, deg, half=4.0):
    a = math.radians(deg)
    return [[cx - half * math.cos(a), cy - half * math.sin(a)], [cx + half * math.cos(a), cy + half * math.sin(a)]]


# A leaf 60 x 24 mm whose stitches fan: up at 30 degrees in its left half, down at 30 in its right.
LEAF = _nodes((30 + 30 * math.cos(2 * math.pi * i / 96), 12 + 12 * math.sin(2 * math.pi * i / 96)) for i in range(96))
LEAF_LINES = [_line(15, 12, 30), _line(45, 12, -30)]

# A ribbon 12 mm wide bent into an arch (radius 40 round its middle), with three lines along it.
_C = (0.0, -30.0)


def _arc(r, degrees):
    return [(_C[0] + r * math.cos(math.radians(d)), _C[1] + r * math.sin(math.radians(d))) for d in degrees]


RIBBON = _nodes(_arc(46, range(45, 136, 3)) + _arc(34, range(135, 44, -3)))
RIBBON_LINES = [_line(*_arc(40, [d])[0], d - 90) for d in (65, 90, 115)]

# A 50 x 30 mm panel whose rows turn through 60 degrees from left to right (-30 to 30).
PANEL = _nodes([(0, 0), (50, 0), (50, 30), (0, 30)])
FAN_LINES = [_line(12, 15, -30), _line(38, 15, 30)]

# A square whose rows turn through 90 degrees in 16 mm, near its top: too sharp for the room above.
SQUARE = _nodes([(0, 0), (40, 0), (40, 40), (0, 40)])
SHARP_LINES = [_line(12, 30, -45, 3), _line(28, 30, 45, 3)]


def _fill(outline, lines, **params):
    p = {"angle_deg": 45, "spacing_mm": SPACING, "underlay": [], "tie_in": False, "tie_off": False,
         "angle_lines": lines, **params}
    return {"kind": "fill", "geometry": {"outline": outline, "holes": []}, "params": p}


def _area(obj):
    g = obj["geometry"]
    return unary_union(fill_parts(g["outline"], g.get("holes") or []))


CASES = {
    "leaf_two_lines": _fill(LEAF, LEAF_LINES),
    "ribbon_three_lines": _fill(RIBBON, RIBBON_LINES),
    "fan_60": _fill(PANEL, FAN_LINES),
}


def _threads(recs, longer_than=0.0):
    return [(a[:2], b[:2]) for a, b in zip(recs, recs[1:])
            if a[2] == b[2] == STITCH and math.dist(a[:2], b[:2]) > longer_than]


def _axial(deg):
    return deg % 180


def _off(a, b):
    d = abs(_axial(a) - _axial(b))
    return min(d, 180 - d)


def _deg(p, q):
    return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))


def _follows(recs, lines):
    """For each line, how far (degrees) the row stitch nearest its middle turns from it."""
    rows = [LineString(t) for t in _threads(recs, 1.5)]
    out = []
    for a, b in lines:
        m = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        near = min(rows, key=lambda r: r.distance(m))
        (x0, y0), (x1, y1) = near.coords
        out.append(_off(_deg((x0, y0), (x1, y1)), _deg(a, b)))
    return out


def test_tatami_with_two_lines_is_a_turning_fill():
    p = FillParams.from_dict({"angle_lines": LEAF_LINES})
    assert turning.takes_over(p)
    assert not turning.takes_over(FillParams.from_dict({"angle_lines": LEAF_LINES[:1]}))
    assert not turning.takes_over(FillParams.from_dict({"pattern": "wave", "angle_lines": LEAF_LINES}))


def test_one_line_is_the_plain_fill():
    """One line sets the fill's angle as it always has (the app keeps Angle in step with it): the
    rows are the plain tatami at that angle."""
    line = _line(20, 20, 30)
    one = _fill(SQUARE, [line], angle_deg=30, underlay=["edge", "tatami"], tie_in=True, tie_off=True)
    plain = {**one, "params": {k: v for k, v in one["params"].items() if k != "angle_lines"}}
    assert generate(one) == generate(plain)


@pytest.mark.parametrize("name", sorted(CASES))
def test_rows_follow_each_line(name):
    """Done-when 3: at each line's middle the nearest row runs within 5 degrees of the line."""
    obj = CASES[name]
    worst = _follows(generate(obj)[0], obj["params"]["angle_lines"])
    assert max(worst) <= 5.0, worst


def _gaps_across(obj, monkeypatch, places=10):
    """Gaps between neighboring rows, measured along the guide's normal at `places` spots spread
    along the part of the guide well inside the shape. Only rows count: moves between groups of
    rows are made jumps here (sewn, they run inside the shape, often along the rows)."""
    with monkeypatch.context() as m:
        m.setattr(stitches, "travel", lambda a, b, inside=None: [(b[0], b[1], stitches.JUMP)])
        recs = generate(obj)[0]
    params = FillParams.from_dict(obj["params"])
    guide = turning.guide(params, _area(obj))
    inner = _area(obj).buffer(-2.0)
    inside = guide.intersection(inner)
    inside = max(getattr(inside, "geoms", [inside]), key=lambda g: g.length)
    lines = [LineString(t) for t in _threads(recs, 0.0)]
    tree = shapely.STRtree(lines)
    gaps = []
    for k in range(places):
        s = inside.length * (k + 0.5) / places
        p, q = inside.interpolate(s), inside.interpolate(min(inside.length, s + 0.05))
        dx, dy = q.x - p.x, q.y - p.y
        n = math.hypot(dx, dy)
        nx, ny = -dy / n, dx / n
        across = LineString([(p.x - 30 * nx, p.y - 30 * ny), (p.x + 30 * nx, p.y + 30 * ny)]).intersection(inner)
        across = min(getattr(across, "geoms", [across]), key=lambda g: g.distance(p))
        hits = []
        for i in tree.query(across):
            (ax, ay), (bx, by) = lines[i].coords
            if abs((bx - ax) * nx + (by - ay) * ny) > 0.5 * lines[i].length:
                continue  # a stitch across the rows (a step between rows, or travel), not a row
            x = across.intersection(lines[i])
            if x.geom_type == "Point":
                hits.append((x.x - p.x) * nx + (x.y - p.y) * ny)
        hits.sort()
        hits = [h for i, h in enumerate(hits) if i == 0 or h - hits[i - 1] > 0.05]  # a needle point on the normal
        gaps += [b - a for a, b in zip(hits, hits[1:])]
    return gaps


@pytest.mark.parametrize("name", sorted(CASES))
def test_spacing_holds_across_the_turn(name, monkeypatch):
    gaps = _gaps_across(CASES[name], monkeypatch)
    assert len(gaps) > 100
    bad = [round(g, 3) for g in gaps if abs(g - SPACING) > 0.2 * SPACING]
    assert not bad, bad


@pytest.mark.parametrize("name", sorted(CASES))
def test_coverage(name):
    obj = {**CASES[name], "params": {**CASES[name]["params"], "pull_comp_mm": 0.2}}
    recs = generate(obj)[0]
    assert invariants.coverage(recs, _area(obj), SPACING) >= 0.97
    assert TOO_SHARP not in generate(obj)[1]


def test_too_sharp_a_turn_warns_and_still_fills_most():
    obj = _fill(SQUARE, SHARP_LINES)
    recs, warnings = generate(obj)
    assert TOO_SHARP in warnings
    assert invariants.coverage(recs, _area(obj), SPACING) >= 0.8
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.4)


def test_lines_move_and_turn_with_the_shape(monkeypatch):
    """Turned, mirrored and resized with the handles, through the whole layout: the lines go with
    the shape, the rows still follow them and keep their spacing (a length in mm, not scaled)."""
    obj = CASES["fan_60"]
    pts = stitches.geometry_points(obj)
    x0, y0, x1, y1 = stitches.bounds(pts)
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    for t in ({"rotate": 30, "x": 12, "y": -5}, {"scale_x": 1.5, "scale_y": 1.5, "rotate": -50},
              {"flip_x": True, "scale_x": 1.25, "scale_y": 0.9}):
        moved = transform_geometry(obj, Transform.from_dict(t), center)
        blocks = layout.render({"items": [{"id": "a", **obj, "transform": t}]}).blocks
        recs = [(r[0] / 10, r[1] / 10, r[2]) for b in blocks for r in b.recs]
        assert max(_follows(recs, moved["params"]["angle_lines"])) <= 5.0, t
        direct = generate(moved)[0]
        assert len(recs) == len(direct) and all(math.dist(a[:2], b[:2]) <= 0.1 for a, b in zip(recs, direct))
        gaps = _gaps_across(moved, monkeypatch)
        assert not [g for g in gaps if abs(g - SPACING) > 0.2 * SPACING], t
    for dx, dy in [(10, -7.5), (0.1234, 33.333), (-250.7, 100.9)]:
        invariants.assert_moves_with_shape(obj, dx, dy)


def test_removing_down_to_one_line_goes_back():
    """Lines too short to give a direction are left out: one line left is the plain fill again."""
    tiny = [[20, 20], [20.2, 20.1]]
    obj = _fill(SQUARE, [_line(20, 20, 30), tiny], angle_deg=30)
    plain = _fill(SQUARE, [], angle_deg=30)
    assert generate(obj) == generate(plain)


def test_the_cross_hatch_underlay_runs_across_the_mean_direction():
    assert turning.mean_angle(FillParams.from_dict({"angle_lines": LEAF_LINES})) == pytest.approx(0.0, abs=1e-6)
    assert turning.mean_angle(FillParams.from_dict({"angle_lines": [_line(12, 15, 0), _line(38, 15, 60)]})) == pytest.approx(30.0)
    assert turning.mean_angle(FillParams.from_dict({"angle_lines": [_line(0, 0, 170), _line(9, 0, 10)]})) == pytest.approx(0.0, abs=1e-6)
    obj = _fill(PANEL, FAN_LINES, underlay=["edge", "tatami"], tie_in=True, tie_off=True)
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.4)


def test_weave_holds_as_rows_curve(monkeypatch):
    """A brick weave on curved rows: other needle points than the standard weave, on the same rows."""
    brick_fill = {**CASES["fan_60"], "params": {**CASES["fan_60"]["params"], "weave": "brick"}}
    assert generate(CASES["fan_60"])[0] != generate(brick_fill)[0]
    gaps = _gaps_across(brick_fill, monkeypatch)
    assert not [g for g in gaps if abs(g - SPACING) > 0.2 * SPACING]


def test_start_and_end_points():
    obj = _fill(PANEL, FAN_LINES, start_mm=[0, 0], end_mm=[50, 30])
    recs = generate(obj)[0]
    pts = invariants.stitch_points(recs)
    assert math.dist(pts[0], (0, 0)) <= 3.0
    assert math.dist(pts[-1], (50, 30)) <= 1.0


def test_reverse_sews_from_the_other_end():
    recs = generate(CASES["fan_60"])[0]
    back = generate({**CASES["fan_60"], "params": {**CASES["fan_60"]["params"], "reverse": True}})[0]
    assert back == recs[::-1]


def test_a_shape_with_a_hole_and_in_pieces():
    hole = _nodes([(20, 10), (30, 10), (30, 20), (20, 20)])
    obj = {**_fill(PANEL, FAN_LINES), "geometry": {"outline": PANEL, "holes": [hole]}}
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=0.4)
    assert invariants.coverage(recs, _area(obj), SPACING) >= 0.95
    bowtie = _fill(_nodes([(0, 0), (30, 30), (30, 0), (0, 30)]), [_line(8, 15, 80), _line(22, 15, 100)])
    invariants.assert_sane(generate(bowtie)[0], inside=_area(bowtie), tolerance_mm=0.4)


@pytest.mark.parametrize("name", sorted(CASES))
def test_invariants(name):
    obj = CASES[name]
    invariants.assert_sane(generate(obj)[0], inside=_area(obj), tolerance_mm=0.4)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    invariants.assert_moves_with_shape(obj, 13.37, -7.11)


def test_project_names_the_feature():
    assert "fill_turning" in project._features({"items": [CASES["fan_60"]]})


SNAPSHOT_CASES = {
    # An edge run only: the cross-hatch's own rows (stitches.tatami, no row hooks) can start at
    # either of two mirror-image ends of this symmetric leaf, decided by a sine's last digit.
    "leaf_two_lines": _fill(LEAF, LEAF_LINES, underlay=["edge"], tie_in=True, tie_off=True),
    "ribbon_three_lines": _fill(RIBBON, RIBBON_LINES, underlay="auto"),
    "fan_60": _fill(PANEL, FAN_LINES, weave="brick"),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("fill_turning", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    path = SNAPSHOT_DIR / "fill_turning.json"
    if not path.exists():
        pytest.skip("snapshots not recorded yet")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    forget_stitches()
    try:
        nudge_trig(monkeypatch, seed, stitches, turning, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()
