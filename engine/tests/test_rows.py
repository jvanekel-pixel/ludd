"""Phase 6 Track A: the rows engine. Weave, carved lines, feathered edges and the hand-sewn look.

Push compensation ("End trim", P6-A1) is held for an owner decision, so it has no tests here.

A fill's needle grid is fixed to the hoop along its rows (as tatami has always been), so the
moves-with-the-shape check moves a fill straight across its rows: the stitches must then move
exactly with it.
"""

import json
import math

import pytest
from shapely import affinity
from shapely.geometry import LineString, Point as SPoint, Polygon

import invariants
from snapshot_util import SNAPSHOT_DIR, check, digest_recs, digest_recs_steady
from steady_util import forget_stitches, nudge_trig
from threadline_engine.digitize import fills, paths, patterns, rows, stitches
from threadline_engine.digitize.paths import flatten
from threadline_engine.digitize.rows import carve, ends, weave
from threadline_engine.digitize.stitches import (STITCH, FillParams, fill_polygon, fill_underlay, generate,
                                                  geometry_points, transform_geometry)
from threadline_engine.layout import Transform

CARVE_WARNING = "A carved line that runs along the stitch rows won't show. Turn the fill's angle or the line."


def c(x, y):
    return [x, y, "c"]


def s(x, y):
    return [x, y, "s"]


SQUARE = [c(0, 0), c(20, 0), c(20, 20), c(0, 20)]
SQUARE_POLY = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])
DIAGONAL = [c(3, 1), c(17, 19)]


def _fill(outline=SQUARE, carve_lines=None, **params):
    g = {"outline": outline}
    if carve_lines is not None:
        g["carve"] = carve_lines
    return {"kind": "fill", "geometry": g, "params": params}


def _plain(**params):
    """A fill at 0 degrees with no underlay or Edge pad, so its stitches are its rows."""
    return _fill(**{"angle_deg": 0, "underlay": [], "pull_comp_mm": 0, **params})


def _untied(recs):
    """generate()'s records without the tie-in and tie-off (the two needle points each adds right
    after the first stitch and the last), so what is left is the stitching itself."""
    recs = list(recs)
    first = next(i for i, r in enumerate(recs) if r[2] == STITCH)
    del recs[first + 1:first + 3]
    last = max(i for i, r in enumerate(recs) if r[2] == STITCH)
    del recs[last - 1:last + 1]
    return recs


def _sewn(obj):
    return _untied(generate(obj)[0])


def _rows_of(recs, angle=0.0):
    """Needle points grouped into rows, in the rows' turned frame: {y: sorted xs}."""
    out: dict[float, list[float]] = {}
    a = math.radians(-angle)
    for x, y, k in recs:
        if k != STITCH:
            continue
        tx, ty = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        out.setdefault(round(ty, 4), []).append(tx)
    return {y: sorted(xs) for y, xs in out.items()}


def _row_lines(recs, angle=0.0):
    """Only the rows that are rows (more than three needle points; a long step between two rows
    is split by a point at a height of its own), keyed by their height."""
    return {y: xs for y, xs in _rows_of(recs, angle).items() if len(xs) > 3}


# ---------------------------------------------------------------- weave (P6-A2)


@pytest.mark.parametrize("name", ["brick", "twill", "smooth", "random"])
def test_each_weave_has_its_offsets(name):
    stitch = 4.0
    recs = _sewn(_plain(weave=name, stitch_mm=stitch))
    offsets = weave.offsets_for(name)
    got = _rows_of(recs)
    assert len(got) == 50
    for r in range(50):
        xs = got[round(0.2 + 0.4 * r, 4)]
        assert xs[0] == pytest.approx(0) and xs[-1] == pytest.approx(20), r
        inner = xs[1:-1]
        off = offsets(r) * stitch
        grid = [off + k * stitch for k in range(-1, 7) if 0.3 < off + k * stitch < 19.7]
        on_grid = [x for x in inner if any(abs(x - g) < 1e-6 for g in grid)]
        assert len(on_grid) == len(grid), (r, inner, grid)
        # Off the grid: only the one point that splits an end gap a dropped grid point made long.
        assert len(inner) - len(on_grid) <= 1, (r, inner, grid)
        if name != "random":
            assert inner == pytest.approx(grid), r


def test_weave_standard_equals_today():
    recorded = json.loads((SNAPSHOT_DIR / "digitize.json").read_text(encoding="utf-8"))["fill_square_45"]
    recs = generate(_fill(angle_deg=45, weave="standard"))[0]
    assert digest_recs(recs) == recorded


def test_wave_keeps_its_own_weave():
    plain = generate(_fill(pattern="wave", underlay=[]))[0]
    assert generate(_fill(pattern="wave", underlay=[], weave="brick"))[0] == plain


def test_weave_reaches_gradient_rows():
    plain = generate(_fill(pattern="gradient", underlay=[], angle_deg=0))[0]
    brick = generate(_fill(pattern="gradient", underlay=[], angle_deg=0, weave="brick"))[0]
    assert brick != plain
    invariants.assert_sane(brick, inside=SQUARE_POLY, tolerance_mm=0.15)


# ---------------------------------------------------------------- carved lines (P6-A3)


def _carve_cases():
    return [("tatami", 0), ("tatami", 30), ("gradient", 0), ("gradient", -60)]


@pytest.mark.parametrize("pattern,angle", _carve_cases())
def test_every_row_has_a_needle_on_the_carved_line(pattern, angle):
    obj = _fill(carve_lines=[DIAGONAL], pattern=pattern, angle_deg=angle, underlay=[])
    recs = _sewn(obj)
    line = LineString([(3, 1), (17, 19)])
    turned_line = affinity.rotate(line, -angle, origin=(0, 0))
    checked = 0
    for y, xs in _row_lines(recs, angle).items():
        hit = turned_line.intersection(LineString([(-100, y), (100, y)]))
        if hit.is_empty or min(abs(y - q[1]) for q in turned_line.coords) < 1e-6:
            continue  # off the line, or exactly at one of its ends
        crossing = hit.x
        if not (xs[0] + carve.KEEP_FROM_END_MM <= crossing <= xs[-1] - carve.KEEP_FROM_END_MM):
            continue
        assert min(abs(x - crossing) for x in xs) <= 0.05, (y, crossing)
        checked += 1
    assert checked > 20


@pytest.mark.parametrize("pattern,angle", _carve_cases())
def test_no_grid_point_crowds_a_carved_point(pattern, angle):
    # Two lines that never meet (where two lines cross, one needle point serves both).
    obj = _fill(carve_lines=[DIAGONAL, [c(9, 1), c(19, 14)]], pattern=pattern, angle_deg=angle, underlay=[])
    recs = _sewn(obj)
    lines = [affinity.rotate(LineString(ln), -angle, origin=(0, 0)) for ln in ([(3, 1), (17, 19)], [(9, 1), (19, 14)])]
    checked = 0
    for y, xs in _row_lines(recs, angle).items():
        hits = [h.x for h in (ln.intersection(LineString([(-100, y), (100, y)])) for ln in lines) if not h.is_empty]
        carved = [x for x in xs if any(abs(x - h) <= 0.05 for h in hits)]
        for h in hits:
            if not (xs[0] + 0.4 <= h <= xs[-1] - 0.4) or min(abs(y - q[1]) for ln in lines for q in ln.coords) < 1e-6:
                continue
            # The one needle point on the carved line, and no other (from the grid) near it.
            assert sum(1 for x in carved if abs(x - h) <= 0.05) == 1, (y, h, xs)
            assert not [x for x in xs if abs(x - h) < carve_clear() and x not in carved], (y, h, xs)
            checked += 1
    assert checked > 30


def carve_clear():
    return stitches.FORCED_CLEAR_MM


def test_carved_lines_find_the_ripple_of_a_wave_fill():
    obj = _plain(pattern="wave", carve_lines=[[c(10, 1), c(10, 19)]])
    recs, _ = generate(obj)
    on_line = [y for x, y, k in recs if k == STITCH and abs(x - 10) < 1e-6]
    assert len(on_line) >= 40  # every row (nearly 50) has a needle on x = 10, where its ripple is
    invariants.assert_sane(recs, inside=SQUARE_POLY, tolerance_mm=0.2)


def test_forced_for_rows_is_sorted_unique_and_keeps_off_the_ends():
    # A closed line (its first point repeated), crossed at a corner it shares: one crossing there.
    ring = [(5.0, 5.0), (15.0, 10.0), (5.0, 15.0), (5.0, 5.0)]
    forced = carve.forced_for_rows([ring], 0)
    assert forced(10.0, 0.0, 20.0) == pytest.approx([5.0, 15.0])
    assert forced(7.5, 0.0, 20.0) == pytest.approx([5.0, 10.0])
    assert forced(7.5, 5.2, 20.0) == pytest.approx([10.0])  # 5.0 is within 0.4 mm of the end
    assert forced(30.0, 0.0, 20.0) == []
    # Two lines through one point give it once.
    forced = carve.forced_for_rows([[(0, 0), (10, 10)], [(10, 0), (0, 10)]], 0)
    assert forced(5.0, -10.0, 20.0) == pytest.approx([5.0])


def test_forced_for_rows_turns_the_lines_with_the_rows():
    forced = carve.forced_for_rows([[(0.0, -10.0), (0.0, 10.0)]], 90)
    # The rows run up the page: a vertical line is now along them, a horizontal one across.
    assert forced(1.0, -20.0, 20.0) == []
    forced = carve.forced_for_rows([[(-10.0, 3.0), (10.0, 3.0)]], 90)
    assert forced(0.0, -20.0, 20.0) == pytest.approx([3.0])


def test_crossings_along_a_curved_row():
    path = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    lines = [[(5.0, -5.0), (5.0, 5.0)], [(5.0, 5.0), (15.0, 5.0)], [(0.1, -1), (0.1, 1)]]
    assert carve.crossings_along(lines, path) == pytest.approx([5.0, 15.0])  # 0.1 is too near the start
    assert carve.crossings_along([], path) == []


def test_carve_along_the_rows_warns():
    along = _plain(carve_lines=[[c(2, 10), c(18, 10.5)]])
    assert CARVE_WARNING in generate(along)[1]
    across = _plain(carve_lines=[[c(10, 2), c(10.5, 18)]])
    assert CARVE_WARNING not in generate(across)[1]
    # Turn the fill and the same line is across its rows.
    assert CARVE_WARNING not in generate({**along, "params": {**along["params"], "angle_deg": 90}})[1]
    # Mostly across, with a short part along: no warning.
    bent = _plain(carve_lines=[[c(10, 2), c(10, 16), c(14, 16)]])
    assert CARVE_WARNING not in generate(bent)[1]
    assert rows.notes(FillParams.from_dict({"angle_deg": 0}), 0) == []


def test_carve_moves_and_resizes_with_the_shape():
    obj = _plain(carve_lines=[DIAGONAL])
    invariants.assert_moves_with_shape(obj, 0, 7.31)
    # Resized with the handles: twice the size, and the rows still drop a needle on the line.
    big = transform_geometry(obj, Transform.from_dict({"scale_x": 2, "scale_y": 2}), (0.0, 0.0))
    assert big["geometry"]["carve"] == [[c(6, 2), c(34, 38)]]
    recs = _sewn(big)
    line = LineString([(6, 2), (34, 38)])
    checked = 0
    for y, xs in _row_lines(recs).items():
        if 2.5 < y < 37.5:
            hit = line.intersection(LineString([(-100, y), (100, y)]))
            assert min(abs(x - hit.x) for x in xs) <= 0.05, y
            checked += 1
    assert checked > 80


def test_carve_does_not_change_bounds():
    plain, carved = _plain(), _plain(carve_lines=[[c(-30, 10), c(50, 11)], DIAGONAL])
    assert geometry_points(carved) == geometry_points(plain)
    a, b = generate(plain)[0], generate(carved)[0]
    box = lambda recs: [f([p[i] for p in recs if p[2] == STITCH]) for i in (0, 1) for f in (min, max)]  # noqa: E731
    assert box(b) == pytest.approx(box(a), abs=1e-6)


# ---------------------------------------------------------------- feathered edges (P6-A4)


def _ends(recs):
    """Each row's two ends (a long step between rows is split by a point of its own: not a row)."""
    return {y: (xs[0], xs[-1]) for y, xs in _rows_of(_untied(recs)).items() if len(xs) >= 3}


@pytest.mark.parametrize("side", ["left", "right", "both"])
def test_feather_shortens_only_the_chosen_side(side):
    depth = 3.0
    got = _ends(generate(_plain(feather=side, feather_mm=depth))[0])
    assert len(got) == 50
    lefts = [a for a, _ in got.values()]
    rights = [20 - b for _, b in got.values()]
    for pulled, feathered in ((lefts, side in ("left", "both")), (rights, side in ("right", "both"))):
        if feathered:
            assert all(0.25 * depth - 1e-6 <= p <= depth + 1e-6 for p in pulled)
            assert max(pulled) - min(pulled) > depth / 2  # ragged, not a straight edge moved in
        else:
            assert pulled == pytest.approx([0.0] * 50, abs=1e-9)


def test_feather_depth_is_respected():
    for depth in (0.5, 2.0, 6.0):
        got = _ends(generate(_plain(feather="both", feather_mm=depth))[0])
        assert all(a <= depth + 1e-6 and 20 - b <= depth + 1e-6 for a, b in got.values()), depth
    # Resized with the handles: the depth is in mm, so it is the same on a shape twice the size.
    obj = _plain(feather="left", feather_mm=2.0)
    big = transform_geometry(obj, Transform.from_dict({"scale_x": 2, "scale_y": 2}), (0.0, 0.0))
    got = _ends(generate(big)[0])
    lefts = [a for a, _ in got.values()]
    assert len(lefts) == 100
    assert all(0.5 - 1e-6 <= a <= 2.0 + 1e-6 for a in lefts)
    assert all(b == pytest.approx(40) for _, b in got.values())


def test_end_shift_depends_only_on_the_row_and_keeps_narrow_rows():
    params = FillParams.from_dict({"feather": "both", "feather_mm": 6, "hand_pct": 100})
    shift = ends.end_shift_for(params)
    assert shift(7, 0.0, 30.0) == shift(7, 0.0, 30.0)
    assert shift(7, 100.0, 130.0) == pytest.approx(tuple(x + 100 for x in shift(7, 0.0, 30.0)))
    for row in range(200):
        a, b = shift(row, 0.0, 4.0)  # both ends can be pulled past each other here
        assert b - a >= min(4.0, ends.KEEP_MM) - 1e-9 and -0.6 - 1e-9 <= a and b <= 4.6 + 1e-9, row
        a, b = shift(row, 0.0, 0.5)
        assert b - a == pytest.approx(0.5) and a >= -1e-9 and b <= 0.5 + 1e-9, row
    assert ends.end_shift_for(FillParams.from_dict({})) is None
    assert ends.pull_in(params) == (6, 6) and ends.pull_in(FillParams.from_dict({"feather": "right"})) == (0, 2)


def test_feather_left_is_left_as_the_rows_run():
    # At 90 degrees the rows run up the page: "left" is their start, the bottom of the shape.
    recs = _sewn(_plain(feather="left", feather_mm=3.0, angle_deg=90))
    ys = [y for x, y, k in recs if k == STITCH]
    assert min(ys) >= 0.75 - 1e-6 and max(ys) == pytest.approx(20)


def test_feathered_fill_has_no_edge_run_on_automatic():
    for level in ("light", "normal", "heavy"):
        assert "edge" in FillParams.from_dict({"underlay": "auto", "underlay_level": level}).underlay
        assert "edge" not in FillParams.from_dict({"underlay": "auto", "underlay_level": level, "feather": "left"}).underlay
    # A chosen underlay is left as chosen.
    assert FillParams.from_dict({"underlay": ["edge"], "feather": "both"}).underlay == ("edge",)
    # Through the whole engine: no stitches along the edge run's line (0.5 mm inside the edge).
    edge = SQUARE_POLY.buffer(-0.5).exterior

    def on_edge(obj):
        return sum(1 for x, y, k in generate(obj)[0] if k == STITCH and edge.distance(SPoint(x, y)) < 1e-6)

    assert on_edge(_fill(underlay="auto", angle_deg=0)) > 20
    assert on_edge(_fill(underlay="auto", angle_deg=0, feather="both")) <= 4


@pytest.mark.parametrize("side,angle", [("left", 0), ("right", 0), ("both", 30)])
def test_cross_hatch_stays_out_of_the_feathered_strip(side, angle):
    depth = 4.0
    params = FillParams.from_dict({"underlay": ["tatami"], "feather": side, "feather_mm": depth, "angle_deg": angle})
    under = fill_underlay(SQUARE_POLY, params, fills.get("tatami"), (0.0, 0.0))
    assert under
    turned = affinity.rotate(SQUARE_POLY, -angle, origin=(0, 0))
    a = math.radians(-angle)
    for x, y, k in under:
        if k != STITCH:
            continue
        tx = x * math.cos(a) - y * math.sin(a)
        ty = x * math.sin(a) + y * math.cos(a)
        row = turned.intersection(LineString([(-100, ty), (100, ty)]))
        if row.is_empty:
            continue
        lo, hi = row.bounds[0], row.bounds[2]
        if side in ("left", "both"):
            assert tx >= lo + depth - 0.05, (tx, ty, lo)
        if side in ("right", "both"):
            assert tx <= hi - depth + 0.05, (tx, ty, hi)


# ---------------------------------------------------------------- hand-sewn look (P6-A5)


RUN = {"kind": "run", "geometry": {"nodes": [c(0, 0), c(30, 0)]}, "params": {}}
CURVE = {"kind": "run", "geometry": {"nodes": [c(0, 0), s(15, 8), c(30, 0)]}, "params": {}}
SATIN = {"kind": "satin", "geometry": {"rail_a": [c(0, 0), c(30, 0)], "rail_b": [c(0, 4), c(30, 4)]},
         "params": {"underlay": [], "pull_comp_mm": 0}}
CURVED_SATIN = {"kind": "satin",
                "geometry": {"rail_a": [c(0, 0), s(15, 6), c(30, 0)], "rail_b": [c(0, 4), s(15, 10), c(30, 4)]},
                "params": {"underlay": ["center", "zigzag"]}}


def _with(obj, **params):
    return {**obj, "params": {**obj["params"], **params}}


@pytest.mark.parametrize("style", ["single", "triple", "bean"])
def test_hand_look_on_a_line_is_repeatable_and_bounded(style):
    stitch = 2.5
    base = [r for r in _sewn(_with(RUN, style=style)) if r[2] == STITCH]
    obj = _with(RUN, style=style, hand_pct=100)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    got = [r for r in _sewn(obj) if r[2] == STITCH]
    assert len(got) == len(base)
    assert got != base
    assert got[0][:2] == base[0][:2] and got[-1][:2] == base[-1][:2]  # the ends stay put
    assert max(abs(y) for _, y, _ in got) <= 0.25 + 1e-9  # sideways, at most 0.25 mm
    assert max(abs(y) for _, y, _ in got) > 0.1
    single = [r for r in _sewn(_with(RUN, hand_pct=100)) if r[2] == STITCH]
    lengths = [math.dist(a[:2], b[:2]) for a, b in zip(single, single[1:])]
    # ±30% of a stitch along the line, and up to 0.25 mm sideways at each end of it.
    assert all(0.7 * stitch - 0.5 - 1e-9 <= d <= 1.3 * stitch + 0.5 + 1e-9 for d in lengths)
    assert max(lengths) > 1.15 * stitch and min(lengths) < 0.85 * stitch
    invariants.assert_sane(got, inside=LineString([(0, 0), (30, 0)]), tolerance_mm=0.26, max_stitch_mm=1.3 * stitch + 0.5)


def test_hand_look_on_a_satin_is_repeatable_and_bounded():
    base = [r for r in _sewn(SATIN) if r[2] == STITCH]
    obj = _with(SATIN, hand_pct=100)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    got = [r for r in _sewn(obj) if r[2] == STITCH]
    assert len(got) == len(base)
    # Rung ends move along the rung (here, up and down) by at most 0.3 mm.
    assert all(min(abs(y), abs(y - 4)) <= 0.3 + 1e-9 for _, y, _ in got)
    assert max(min(abs(y), abs(y - 4)) for _, y, _ in got) > 0.15
    # The spacing varies by at most ±20%.
    xs = sorted({round(x, 9) for x, _, _ in got})
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    base_gap = 30 / (len(xs) - 1)
    assert all(0.8 * base_gap - 1e-6 <= g <= 1.2 * base_gap + 1e-6 for g in gaps)
    assert max(gaps) > 1.08 * base_gap and min(gaps) < 0.92 * base_gap
    invariants.assert_sane(got, inside=Polygon([(0, 0), (30, 0), (30, 4), (0, 4)]), tolerance_mm=0.31)


def test_hand_look_on_a_fill_is_repeatable_and_bounded():
    obj = _plain(hand_pct=100)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    got = _ends(generate(obj)[0])
    assert len(got) == 50
    assert all(abs(a) <= 0.6 + 1e-9 and abs(b - 20) <= 0.6 + 1e-9 for a, b in got.values())
    assert max(abs(a) for a, _ in got.values()) > 0.3
    # The needle points move as Random 50% does.
    hooks = rows.hooks(FillParams.from_dict({"hand_pct": 100}), 0)
    assert hooks["random"] == pytest.approx(0.5)
    assert rows.hooks(FillParams.from_dict({"hand_pct": 60}), 0)["random"] == pytest.approx(0.3)
    assert rows.hooks(FillParams.from_dict({"hand_pct": 20, "random_pct": 40}), 0)["random"] == pytest.approx(0.4)
    invariants.assert_sane(generate(obj)[0], inside=SQUARE_POLY, tolerance_mm=0.61)


def test_hand_look_leaves_motif_lines_alone():
    motif = _with(RUN, style="motif", motif="zigzag")
    assert generate(_with(motif, hand_pct=80))[0] == generate(motif)[0]


@pytest.mark.parametrize("obj", [RUN, CURVE, _with(RUN, style="triple"), SATIN, CURVED_SATIN, _plain(), _fill()],
                         ids=["run", "curve", "triple", "satin", "curved_satin", "fill_plain", "fill"])
def test_hand_look_zero_is_unchanged(obj):
    assert generate(_with(obj, hand_pct=0))[0] == generate(obj)[0]


def test_hand_look_on_a_satin_with_a_stop_keeps_each_rung_jitter():
    obj = {"kind": "satin", "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": 4},
           "params": {"underlay": [], "end_mm": [15, 0], "hand_pct": 100}}
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=Polygon([(0, -2), (30, -2), (30, 2), (0, 2)]), tolerance_mm=0.5)
    invariants.assert_deterministic(lambda: generate(obj)[0])


# ---------------------------------------------------------------- snapshots


SNAPSHOT_CASES = {
    "weave_brick": _fill(angle_deg=30, weave="brick"),
    "weave_twill": _fill(angle_deg=0, weave="twill", underlay="auto"),
    "weave_smooth": _fill(angle_deg=-45, weave="smooth", pattern="gradient", underlay=[]),
    "carve_cross": _fill(carve_lines=[[c(2, 2), c(18, 18)], [c(2, 18), s(10, 12), c(18, 2)]], angle_deg=15),
    "feather_both": _fill(feather="both", feather_mm=2.5, angle_deg=0, underlay="auto"),
    "hand_fill_60": _fill(hand_pct=60, angle_deg=45),
    "hand_satin_60": _with(CURVED_SATIN, hand_pct=60),
    "hand_run_60": _with(CURVE, hand_pct=60, style="triple"),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name):
    check("rows", name, digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, monkeypatch):
    """Every rows case gives its recorded stitches with the last digit of each sine and cosine
    nudged, the turns of shapely's rotate() too (see steady_util)."""
    recorded = json.loads((SNAPSHOT_DIR / "rows.json").read_text(encoding="utf-8"))
    forget_stitches()
    try:
        # The modules that work out these stitches with sines and cosines (weave, ends and hand
        # use whole-number hashing only).
        nudge_trig(monkeypatch, seed, stitches, patterns, paths, carve, rotations=True)
        for name in sorted(SNAPSHOT_CASES):
            assert digest_recs_steady(generate(SNAPSHOT_CASES[name])[0]) == recorded[name], name
    finally:
        monkeypatch.undo()
        forget_stitches()


def _area(obj):
    g = obj["geometry"]
    if obj["kind"] == "fill":
        return fill_polygon(g["outline"])
    if obj["kind"] == "satin":
        return Polygon(flatten(g["rail_a"])[0] + flatten(g["rail_b"])[0][::-1]).buffer(0)
    return LineString(flatten(g["nodes"])[0])


def _tolerance(obj):
    """How far a case may sew outside its shape: Edge pad (half the pull compensation) at a row's
    end, plus the hand-sewn look's 0.6 mm at its end for fills (0.3 mm along a satin's rung, 0.25
    mm sideways off a line), and 0.05 mm for curves drawn as short straight pieces."""
    p = obj["params"]
    h = p.get("hand_pct", 0) / 100
    if obj["kind"] == "fill":
        return p.get("pull_comp_mm", 0.2) / 2 + 0.6 * h + 0.05
    if obj["kind"] == "satin":
        return p.get("pull_comp_mm", 0.2) / 2 + 0.3 * h + 0.05
    return 0.25 * h + 0.05


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_pass_the_invariants(name):
    obj = SNAPSHOT_CASES[name]
    recs = generate(obj)[0]
    invariants.assert_sane(recs, inside=_area(obj), tolerance_mm=_tolerance(obj), max_jumps=0)
    invariants.assert_deterministic(lambda: generate(obj)[0])
    if obj["kind"] == "fill":
        # Straight across the rows: the needle grid is fixed in place along them. The rows'
        # settings are checked on the top stitching: the cross-hatch underlay, whose rows cross
        # the top's, doesn't move exactly with the shape on any fill today (a plain one included).
        a = math.radians(obj["params"].get("angle_deg", 45))
        top = {**obj, "params": {**obj["params"], "underlay": []}}
        invariants.assert_moves_with_shape(top, -7.3 * math.sin(a), 7.3 * math.cos(a))
    else:
        invariants.assert_moves_with_shape(obj, 13.37, -7.11)
