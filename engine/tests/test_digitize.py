"""Digitizing: paths, running stitch, satin, tatami fill. Property tests plus snapshots.

Snapshots live in tests/snapshots/digitize.json. A changed stitch output fails the test so it
can be reviewed; re-record with UPDATE_SNAPSHOTS=1 after checking the new output is right.
"""

import hashlib
import json
import math

import pytest
from shapely.geometry import Point as SPoint, Polygon

from snapshot_util import check
from threadline_engine.digitize.paths import flatten, length, resample
from threadline_engine.digitize.stitches import (
    JUMP,
    STITCH,
    TRIM,
    DigitizeError,
    FillParams,
    RunParams,
    SatinParams,
    fill,
    fill_polygon,
    generate,
    ribbon_pairs,
    running,
    satin,
    satin_pairs,
)


def c(x, y):
    return [x, y, "c"]


def s(x, y):
    return [x, y, "s"]


def pts(recs, kind=STITCH):
    return [(x, y) for x, y, k in recs if k == kind]


def steps(points):
    return [math.dist(a, b) for a, b in zip(points, points[1:])]


# ---------------------------------------------------------------- paths


def test_corners_make_straight_lines_through_the_nodes():
    poly, idx = flatten([c(0, 0), c(10, 0), c(10, 10)])
    assert poly == [(0, 0), (10, 0), (10, 10)]
    assert idx == [0, 1, 2]


def test_curves_pass_through_their_nodes_smoothly():
    nodes = [c(0, 0), s(10, 10), c(20, 0)]
    poly, idx = flatten(nodes)
    assert [poly[i] for i in idx] == [(0, 0), (10, 10), (20, 0)]
    assert len(poly) > 10  # actually curved
    # Smooth at the curve node: the direction barely changes across it.
    i = idx[1]
    before = math.atan2(poly[i][1] - poly[i - 1][1], poly[i][0] - poly[i - 1][0])
    after = math.atan2(poly[i + 1][1] - poly[i][1], poly[i + 1][0] - poly[i][0])
    assert abs(before - after) < 0.15


def test_closed_path_returns_to_start():
    poly, idx = flatten([c(0, 0), c(10, 0), c(10, 10)], closed=True)
    assert poly[-1] == (0, 0) and len(idx) == 3


def test_resample_keeps_corners_and_max_step():
    poly = [(0, 0), (10, 0), (10, 7)]
    out = resample(poly, 3.0, keep=[1])
    assert (10, 0) in out
    assert max(steps(out)) <= 3.0 + 1e-9
    assert out[0] == (0, 0) and out[-1] == (10, 7)


# ---------------------------------------------------------------- running stitch


def test_running_styles():
    nodes = [c(0, 0), c(10, 0)]
    single = pts(running(nodes, RunParams(stitch_mm=2.5)))
    assert len(single) == 5 and max(steps(single)) <= 2.5 + 1e-9
    triple = pts(running(nodes, RunParams(style="triple", stitch_mm=2.5)))
    assert len(triple) == 13 and triple[-1] == (10, 0)
    bean = pts(running(nodes, RunParams(style="bean", stitch_mm=2.5)))
    assert len(bean) == 13 and bean[:4] == [(0, 0), (2.5, 0), (0, 0), (2.5, 0)]


def test_running_hits_sharp_corners():
    out = pts(running([c(0, 0), c(7, 0), c(7, 7)], RunParams(stitch_mm=3)))
    assert (7, 0) in out


def test_run_params_validated():
    with pytest.raises(DigitizeError):
        RunParams.from_dict({"style": "zigzag"})
    with pytest.raises(DigitizeError):
        RunParams.from_dict({"stitch_mm": 0.1})


# ---------------------------------------------------------------- satin


A = [c(0, 0), c(20, 0)]
B = [c(0, 4), c(20, 4)]


def test_satin_pairs_follow_rungs_and_spacing():
    pairs = satin_pairs(A, B, 0.4)
    assert len(pairs) == 51  # 20 mm / 0.4 + 1
    assert pairs[0] == ((0, 0), (0, 4)) and pairs[-1] == ((20, 0), (20, 4))
    with pytest.raises(DigitizeError, match="same number"):
        satin_pairs(A, [c(0, 4)], 0.4)


def test_satin_zigzags_across_with_pull_compensation():
    recs, warnings = satin(A, B, SatinParams(spacing_mm=0.4, pull_comp_mm=0.4, underlay=()))
    p = pts(recs)
    assert not warnings
    ys = {round(y, 6) for _, y in p}
    assert ys == {-0.2, 4.2}  # each side pushed out by half the compensation
    # Alternates sides, never two in a row on the same side (apart from the turn at each pair).
    assert all(abs(p[i][1] - p[i + 1][1]) > 4 for i in range(0, len(p) - 1, 2))


def test_satin_underlays_end_where_they_start():
    for kind in ("center", "edge", "zigzag"):
        recs, _ = satin(A, B, SatinParams(underlay=(kind,)))
        p = pts(recs)
        first_top = p.index((0, -0.1))  # first top stitch
        assert first_top > 0
        assert math.dist(p[first_top - 1], (0, 2)) < 3  # underlay finished near the start


def test_satin_warns_when_too_wide_or_narrow():
    _, wide = satin([c(0, 0), c(20, 0)], [c(0, 12), c(20, 12)], SatinParams())
    assert "wide" in wide[0]
    _, narrow = satin([c(0, 0), c(20, 0)], [c(0, 0.5), c(20, 0.5)], SatinParams())
    assert "only" in narrow[0]


def test_curved_satin_rails_never_cross():
    a = [c(0, 0), s(15, 10), c(30, 0)]
    b = [c(0, 4), s(15, 14), c(30, 4)]
    pairs = satin_pairs(a, b, 0.4)
    for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
        # Consecutive rungs don't intersect each other.
        assert not _segments_cross(a0, b0, a1, b1)


def _segments_cross(p1, p2, p3, p4):
    def ccw(a, b, cc):
        return (cc[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (cc[0] - a[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


# ---------------------------------------------------------------- fill


SQUARE = [c(0, 0), c(20, 0), c(20, 20), c(0, 20)]


def test_fill_stays_inside_and_keeps_stitch_lengths():
    params = FillParams(angle_deg=0, spacing_mm=0.4, stitch_mm=3.5, pull_comp_mm=0.0, underlay=())
    recs, _ = fill(SQUARE, [], params)
    p = pts(recs)
    poly = Polygon([(0, 0), (20, 0), (20, 20), (0, 20)]).buffer(0.01)
    assert all(poly.covers(SPoint(x, y)) for x, y in p)
    # Along a row no stitch is longer than the stitch length; between rows they step by the spacing.
    along = [d for (a, b), d in zip(zip(p, p[1:]), steps(p)) if abs(a[1] - b[1]) < 1e-9]
    assert max(along) <= 3.5 + 1e-6
    rows = {round(y, 4) for _, y in p}
    assert len(rows) == 50  # 20 mm / 0.4 mm


def test_fill_rows_are_staggered_bricks():
    params = FillParams(angle_deg=0, spacing_mm=1.0, stitch_mm=3.0, pull_comp_mm=0, underlay=())
    p = pts(fill(SQUARE, [], params)[0])
    by_row = {}
    for x, y in p:
        by_row.setdefault(round(y, 4), set()).add(round(x, 4))
    inner = [sorted(xs - {0.0, 20.0}) for _, xs in sorted(by_row.items())]
    assert inner[0] != inner[1] != inner[2]  # penetrations shift each row


def test_fill_avoids_holes():
    hole = [c(8, 8), c(12, 8), c(12, 12), c(8, 12)]
    params = FillParams(angle_deg=30, spacing_mm=0.4, pull_comp_mm=0, underlay=())
    recs, _ = fill(SQUARE, [hole], params)
    inner_hole = Polygon([(8, 8), (12, 8), (12, 12), (8, 12)]).buffer(-0.2)
    assert not any(inner_hole.contains(SPoint(x, y)) for x, y in pts(recs))


@pytest.mark.parametrize("angle", [0, 30, 45, 90])
def test_fill_with_hole_travels_around_it_without_jumps(angle):
    hole = [c(7, 7), c(13, 7), c(13, 13), c(7, 13)]
    recs, _ = fill(SQUARE, [hole], FillParams(angle_deg=angle, underlay=("edge", "tatami")))
    assert not [r for r in recs if r[2] in (JUMP, TRIM)]
    inner_hole = Polygon([(7, 7), (13, 7), (13, 13), (7, 13)]).buffer(-0.2)
    assert not any(inner_hole.contains(SPoint(x, y)) for x, y in pts(recs))


def test_fill_concave_shape_covers_every_row():
    u_shape = [c(0, 0), c(30, 0), c(30, 30), c(20, 30), c(20, 10), c(10, 10), c(10, 30), c(0, 30)]
    params = FillParams(angle_deg=0, spacing_mm=0.5, pull_comp_mm=0, underlay=())
    recs, _ = fill(u_shape, [], params)
    poly = Polygon([(n[0], n[1]) for n in u_shape]).buffer(0.01)
    assert all(poly.covers(SPoint(x, y)) for x, y in pts(recs))
    ys = {round(y, 4) for _, y in pts(recs)}
    assert {round(0.25 + k * 0.5, 4) for k in range(60)} <= ys  # every row covered, both arms of the U


def test_fill_pull_compensation_extends_rows():
    params = FillParams(angle_deg=0, spacing_mm=1, pull_comp_mm=0.4, underlay=())
    xs = [x for x, _ in pts(fill(SQUARE, [], params)[0])]
    assert min(xs) == pytest.approx(-0.2) and max(xs) == pytest.approx(20.2)


def test_fill_underlay_comes_first_and_is_sparse():
    with_ul, _ = fill(SQUARE, [], FillParams(angle_deg=0, underlay=("edge", "tatami")))
    without, _ = fill(SQUARE, [], FillParams(angle_deg=0, underlay=()))
    assert len(with_ul) > len(without)
    assert len(with_ul) - len(without) < len(without) / 2


def test_fill_rejects_tiny_or_degenerate_shapes():
    with pytest.raises(DigitizeError):
        fill_polygon([c(0, 0), c(1, 0)])
    with pytest.raises(DigitizeError, match="too small"):
        fill_polygon([c(0, 0), c(0.5, 0), c(0.5, 0.5)])


def test_self_intersecting_outline_is_repaired():
    """QA (tests, fill, patterns, visual): a bow-tie sewed only one of its two triangles."""
    bowtie = [c(0, 0), c(10, 10), c(10, 0), c(0, 10)]
    recs, _ = fill(bowtie, [], FillParams(underlay=()))
    p = pts(recs)
    assert any(x < 4 for x, _ in p) and any(x > 6 for x, _ in p)  # both lobes
    # The two lobes only touch at a point: lock off, cut, move, lock in.
    assert [k for *_, k in recs if k != STITCH] == [TRIM, JUMP]


# ---------------------------------------------------------------- objects


def test_generate_adds_ties_and_dispatches():
    run = {"kind": "run", "geometry": {"nodes": [c(0, 0), c(10, 0)]}, "params": {"stitch_mm": 2.5}}
    recs, _ = generate(run)
    p = pts(recs)
    assert p[:3] == [(0, 0), (0.7, 0), (0, 0)]  # tie-in
    assert p[-2:] == [(9.3, 0), (10, 0)]  # tie-off
    untied, _ = generate({**run, "params": {"tie_in": False, "tie_off": False}})
    assert len(pts(untied)) == len(p) - 4
    with pytest.raises(DigitizeError):
        generate({"kind": "spiral"})


# ---------------------------------------------------------------- snapshots


SNAPSHOT_CASES = {
    "run_single": {"kind": "run", "geometry": {"nodes": [c(0, 0), s(15, 8), c(30, 0)]}, "params": {}},
    "run_bean": {"kind": "run", "geometry": {"nodes": [c(0, 0), c(20, 5)]}, "params": {"style": "bean"}},
    "satin_curved": {
        "kind": "satin",
        "geometry": {"rail_a": [c(0, 0), s(15, 6), c(30, 0)], "rail_b": [c(0, 4), s(15, 10), c(30, 4)]},
        "params": {"underlay": ["center", "zigzag"]},
    },
    "satin_ribbon_s_curve": {
        "kind": "satin",
        "geometry": {"nodes": [c(0, 0), s(10, 6), s(20, 0), c(30, 6)], "width_mm": 3},
        "params": {"underlay": ["center"]},
    },
    "satin_ribbon_closed_square": {
        "kind": "satin",
        "geometry": {"nodes": [c(0, 0), c(20, 0), c(20, 20), c(0, 20)], "width_mm": 2.5, "closed": True},
        "params": {"underlay": []},
    },
    "fill_square_45": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"angle_deg": 45}},
    "fill_gradient": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "gradient", "underlay": []}},
    "fill_wave": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "wave", "underlay": []}},
    "fill_contour": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "contour", "spacing_mm": 1.5, "underlay": []}},
    "fill_stipple": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "stipple", "underlay": []}},
    "fill_cross": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "cross", "underlay": []}},
    "run_motif_scallop": {"kind": "run", "geometry": {"nodes": [c(0, 0), s(15, 8), c(30, 0)]}, "params": {"style": "motif", "motif": "scallop"}},
    "fill_donut": {
        "kind": "fill",
        "geometry": {"outline": SQUARE, "holes": [[c(7, 7), c(13, 7), c(13, 13), c(7, 13)]]},
        "params": {"angle_deg": 0, "underlay": ["edge"]},
    },
    # QA phase 4: every stitch type and its main variants.
    "run_triple": {"kind": "run", "geometry": {"nodes": [c(0, 0), s(15, 8), c(30, 0)]}, "params": {"style": "triple"}},
    "run_motif_wave": {"kind": "run", "geometry": {"nodes": [c(0, 0), c(30, 0)]}, "params": {"style": "motif", "motif": "wave"}},
    "run_motif_zigzag": {"kind": "run", "geometry": {"nodes": [c(0, 0), c(30, 0)]}, "params": {"style": "motif", "motif": "zigzag"}},
    "run_motif_blanket_closed": {"kind": "run", "geometry": {"nodes": SQUARE, "closed": True},
                                 "params": {"style": "motif", "motif": "blanket"}},
    "satin_edge_zigzag_underlay": {
        "kind": "satin",
        "geometry": {"rail_a": [c(0, 0), s(15, 6), c(30, 0)], "rail_b": [c(0, 6), s(15, 12), c(30, 6)]},
        "params": {"underlay": ["edge", "zigzag"]},
    },
    "satin_ribbon_auto_comp_widen": {
        "kind": "satin",
        "geometry": {"nodes": [c(0, 0), s(15, 8), c(30, 0)], "width_mm": 6},
        "params": {"underlay": "auto", "underlay_level": "heavy", "comp_by_width": True, "auto_widen": True},
    },
    "satin_ribbon_split": {
        "kind": "satin",
        "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": 10},
        "params": {"underlay": ["center", "edge", "zigzag"], "split_mm": 4},
    },
    "fill_random_reverse": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"random_pct": 30, "reverse": True}},
    "fill_heavy_auto_underlay": {"kind": "fill", "geometry": {"outline": SQUARE},
                                 "params": {"underlay": "auto", "underlay_level": "heavy"}},
    "fill_cross_with_underlay": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "cross"}},
    "fill_stipple_with_underlay": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"pattern": "stipple"}},
    "fill_bowtie": {"kind": "fill", "geometry": {"outline": [c(0, 0), c(20, 20), c(20, 0), c(0, 20)]}, "params": {}},
    "applique_square": {"kind": "applique", "geometry": {"outline": SQUARE}, "params": {}},
    "applique_with_hole_run_tack": {
        "kind": "applique",
        "geometry": {"outline": SQUARE, "holes": [[c(7, 7), c(13, 7), c(13, 13), c(7, 13)]]},
        "params": {"tack": "run", "cover_width_mm": 2.5},
    },
}


def _digest(recs):
    rounded = [[round(x, 3), round(y, 3), k] for x, y, k in recs]
    return {
        "records": len(rounded),
        "stitches": sum(1 for r in rounded if r[2] == STITCH),
        "jumps": sum(1 for r in rounded if r[2] == JUMP),
        "trims": sum(1 for r in rounded if r[2] == TRIM),
        "sha1": hashlib.sha1(json.dumps(rounded).encode()).hexdigest(),
    }


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot(name):
    check("digitize", name, _digest(generate(SNAPSHOT_CASES[name])[0]))


@pytest.mark.parametrize("angle", [0, 30, 45, -45, 90, 135])
def test_fill_never_makes_a_long_stitch(angle):
    """Underlay, travel and rows: nothing long and loose (underlay row turns reach about 4 mm)."""
    recs, _ = generate({"kind": "fill", "geometry": {"outline": [c(23, 0), c(43, 0), c(43, 20), c(23, 20)]},
                        "params": {"angle_deg": angle}})
    pts = [r for r in recs if r[2] == STITCH]
    longest = max(math.dist(a[:2], b[:2]) for a, b in zip(pts, pts[1:]))
    assert longest <= 4.1


@pytest.mark.parametrize("angle", [0, 45, 90, 135])
def test_star_fill_has_no_long_stitches(angle):
    """A star's arms run almost along the rows at some angles; the step between rows must stay short."""
    pts = []
    for k in range(10):
        a = -math.pi / 2 + math.pi * k / 5
        r = 22 if k % 2 == 0 else 9
        pts.append(c(r * math.cos(a), r * math.sin(a)))
    recs, _ = generate({"kind": "fill", "geometry": {"outline": pts}, "params": {"angle_deg": angle}})
    st = [r for r in recs if r[2] == STITCH]
    assert max(math.dist(a[:2], b[:2]) for a, b in zip(st, st[1:])) <= 4.1


def test_fill_random_moves_penetrations_but_keeps_stitches_short():
    shape = [c(0, 0), c(30, 0), c(30, 20), c(0, 20)]
    plain, _ = fill(shape, [], FillParams(angle_deg=0, underlay=()))
    rnd, _ = fill(shape, [], FillParams(angle_deg=0, underlay=(), random_pct=30))
    again, _ = fill(shape, [], FillParams(angle_deg=0, underlay=(), random_pct=30))
    assert rnd == again  # the same design always gives the same stitches
    assert pts(rnd) != pts(plain)
    st = [r for r in rnd if r[2] == STITCH]
    assert max(math.dist(a[:2], b[:2]) for a, b in zip(st, st[1:])) <= 3.5 * 1.16
    with pytest.raises(DigitizeError, match="Random"):
        FillParams.from_dict({"random_pct": 80})


def test_fill_reverse_sews_from_the_other_end():
    shape = [c(0, 0), c(30, 0), c(30, 20), c(0, 20)]
    fwd, _ = fill(shape, [], FillParams(angle_deg=0, underlay=()))
    rev, _ = fill(shape, [], FillParams(angle_deg=0, underlay=(), reverse=True))
    assert pts(rev) == pts(fwd)[::-1]


def test_satin_split_breaks_long_stitches():
    a, b = [c(0, 0), c(30, 0)], [c(0, 9), c(30, 9)]
    recs, _ = satin(a, b, SatinParams(underlay=(), pull_comp_mm=0, split_mm=4))
    st = [r for r in recs if r[2] == STITCH]
    assert max(math.dist(p[:2], q[:2]) for p, q in zip(st, st[1:])) <= 4 + 1e-9


# ---------------------------------------------------------------- satin ribbon (centre line + width)


def test_ribbon_is_square_to_a_straight_line_and_as_wide_as_asked():
    pairs = ribbon_pairs([c(0, 0), c(20, 0)], 4, 0.4)
    assert len(pairs) == 51
    for a, b in pairs:
        assert a[0] == pytest.approx(b[0])  # straight across
        assert math.dist(a, b) == pytest.approx(4)
        assert (a[1] + b[1]) / 2 == pytest.approx(0)  # centred on the line


def test_ribbon_keeps_its_width_round_a_curve_and_its_edges_never_cross():
    nodes = [c(0, 0), s(10, 8), s(20, 0), c(30, 8)]
    pairs = ribbon_pairs(nodes, 3, 0.4)
    widths = [math.dist(a, b) for a, b in pairs]
    assert min(widths) == pytest.approx(3, abs=0.05)
    assert max(widths) < 3 * 2.0 + 1e-6  # the miter limit
    # Consecutive stitches never swap sides.
    for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
        assert math.dist(a0, a1) < math.dist(a0, b1)


def test_ribbon_corner_is_mitred_and_closed_ribbon_meets_itself():
    pairs = ribbon_pairs([c(0, 0), c(20, 0), c(20, 20), c(0, 20)], 2, 0.4, closed=True)
    assert [*pairs[0][0], *pairs[0][1]] == pytest.approx([*pairs[-1][0], *pairs[-1][1]])
    corner = min(pairs, key=lambda ab: math.dist(((ab[0][0] + ab[1][0]) / 2, (ab[0][1] + ab[1][1]) / 2), (20, 0)))
    assert math.dist(*corner) == pytest.approx(2 * math.sqrt(2), abs=0.01)  # 90°: √2 wider along the diagonal


def test_ribbon_validates_width_and_points():
    with pytest.raises(DigitizeError, match="width"):
        ribbon_pairs([c(0, 0), c(10, 0)], 20, 0.4)
    with pytest.raises(DigitizeError, match="two points"):
        ribbon_pairs([c(0, 0)], 3, 0.4)


def test_generate_dispatches_ribbon_and_column_satins():
    ribbon = generate({"kind": "satin", "geometry": {"nodes": [c(0, 0), c(20, 0)], "width_mm": 3}, "params": {"underlay": []}})[0]
    column = generate({"kind": "satin", "geometry": {"rail_a": [c(0, -1.5), c(20, -1.5)], "rail_b": [c(0, 1.5), c(20, 1.5)]},
                       "params": {"underlay": []}})[0]
    ys = {round(y, 3) for _, y in pts(ribbon)[3:-3]}
    assert ys == {-1.6, 1.6}  # each side out by half the 0.2 mm default compensation
    assert len(pts(ribbon)) == len(pts(column))


def test_scaling_a_ribbon_scales_its_width():
    from threadline_engine.digitize.stitches import transform_geometry
    from threadline_engine.layout import Transform

    obj = {"kind": "satin", "geometry": {"nodes": [c(0, 0), c(20, 0)], "width_mm": 3}}
    t = Transform.from_dict({"scale_x": 2, "scale_y": 2})
    assert transform_geometry(obj, t, (10, 0))["geometry"]["width_mm"] == pytest.approx(6)


# ---------------------------------------------------------------- QA phase 4 (fills, satins, applique)


def _longest(recs):
    st = [r for r in recs if r[2] == STITCH]
    return max(math.dist(a[:2], b[:2]) for a, b in zip(st, st[1:]))


def test_qa_hole_cutting_a_shape_in_two_sews_both_pieces():
    bar = [c(0, 0), c(30, 0), c(30, 10), c(0, 10)]
    cut = [c(10, -1), c(20, -1), c(20, 11), c(10, 11)]
    recs, _ = generate({"kind": "fill", "geometry": {"outline": bar, "holes": [cut]}, "params": {}})
    xs = [x for x, _ in pts(recs)]
    assert min(xs) < 1 and max(xs) > 29 and not any(10.5 < x < 19.5 for x in xs)


def test_qa_underlay_reaches_every_lobe_and_hole_edge():
    neck = [c(0, 0), c(10, 0), c(10, 4.5), c(15, 4.5), c(15, 0), c(25, 0), c(25, 10), c(15, 10), c(15, 5.5),
            c(10, 5.5), c(10, 10), c(0, 10)]
    with_ul, _ = fill(neck, [], FillParams(angle_deg=0))
    bare, _ = fill(neck, [], FillParams(angle_deg=0, underlay=()))
    right = lambda recs: sum(1 for x, _ in pts(recs) if x > 15)  # noqa: E731
    assert right(with_ul) - right(bare) > 30  # the lobe behind the 1 mm neck gets its underlay
    hole = [c(7, 7), c(13, 7), c(13, 13), c(7, 13)]
    edged, _ = fill(SQUARE, [hole], FillParams(angle_deg=0, underlay=("edge",)))
    plain, _ = fill(SQUARE, [hole], FillParams(angle_deg=0, underlay=()))
    rim = Polygon([(7, 7), (13, 7), (13, 13), (7, 13)]).exterior
    near = lambda recs: sum(1 for p in pts(recs) if abs(rim.distance(SPoint(p)) - 0.5) < 0.05)  # noqa: E731
    assert near(edged) - near(plain) >= 8  # an edge run round the hole


def test_qa_travel_keeps_to_the_shape_round_notches():
    comb = [c(0, 0), c(13.5, 0)]
    for i in range(4, -1, -1):
        comb += [c(i * 3 + 1.5, 20), c(i * 3, 20)]
        if i:
            comb += [c(i * 3, 4), c(i * 3 - 1.5, 4)]
    # Rows reach 0.1 mm past the edge (pull compensation) and a row's step round a notch corner
    # cuts it by about 0.1 more; travel used to cut across notches up to 0.47 mm outside.
    allowed = fill_polygon(comb).buffer(0.25)
    for angle in range(0, 180, 15):
        recs, _ = fill(comb, [], FillParams(angle_deg=angle))
        for a, b in zip(recs, recs[1:]):
            if a[2] == b[2] == STITCH:
                seg = [a[:2], b[:2]]
                assert all(allowed.covers(SPoint(seg[0][0] + (seg[1][0] - seg[0][0]) * t, seg[0][1] + (seg[1][1] - seg[0][1]) * t))
                           for t in (0, 0.25, 0.5, 0.75, 1)), (angle, seg)


def test_qa_wobbly_outline_fills_quickly():
    import random
    import time

    rnd = random.Random(7)
    nodes = [[30 * (1 + 0.1 * rnd.uniform(-1, 1)) * math.cos(2 * math.pi * i / 250),
              30 * (1 + 0.1 * rnd.uniform(-1, 1)) * math.sin(2 * math.pi * i / 250), "s"] for i in range(250)]
    t = time.perf_counter()
    generate({"kind": "fill", "geometry": {"outline": nodes}, "params": {}})
    assert time.perf_counter() - t < 6  # was 8.7 s; now about 2 s


@pytest.mark.parametrize("spacing", [0.2, 0.25, 0.3])
def test_qa_dense_rows_reach_both_edges(spacing):
    recs, _ = fill([c(0, 0), c(20, 0), c(20, 20), c(0, 20)], [], FillParams(angle_deg=0, spacing_mm=spacing, pull_comp_mm=0, underlay=()))
    rows = {}
    for x, y in pts(recs):
        rows.setdefault(round(y, 3), []).append(x)
    assert all(min(r) < 0.01 and max(r) > 19.99 for r in rows.values())


def test_qa_dense_satin_gets_denser_not_sparser():
    counts = [len(pts(generate({"kind": "satin", "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": 3},
                                "params": {"spacing_mm": sp, "underlay": [], "tie_in": False, "tie_off": False}})[0]))
              for sp in (0.4, 0.32, 0.29, 0.25, 0.2)]
    assert counts == sorted(counts) and counts[-1] >= 290


@pytest.mark.parametrize("pattern", ["tatami", "contour", "cross", "stipple", "wave"])
def test_qa_no_second_needle_drop_in_the_same_hole(pattern):
    recs, _ = fill([c(0, 0), c(30, 0), c(30, 30), c(0, 30)], [], FillParams(pattern=pattern))
    p = pts(recs)
    assert not [1 for a, b in zip(p, p[1:]) if a == b]


def test_qa_gradient_skips_the_cross_hatch_so_it_fades_out():
    shape = [c(0, 0), c(40, 0), c(40, 40), c(0, 40)]
    full, _ = fill(shape, [], FillParams(pattern="gradient", angle_deg=0, gradient_to_mm=3.0, underlay=("edge", "tatami")))
    edge, _ = fill(shape, [], FillParams(pattern="gradient", angle_deg=0, gradient_to_mm=3.0, underlay=("edge",)))
    assert full == edge


def test_qa_cross_hatch_stays_inside_a_shape_with_zero_width_spikes():
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    def stroke(a):
        r = math.radians(a)
        return LineString([(-7 * math.cos(r), -7 * math.sin(r)), (7 * math.cos(r), 7 * math.sin(r))]).buffer(0.6, cap_style=2)

    g = unary_union([stroke(30), stroke(120)])
    outline = [c(x, y) for x, y in list(g.exterior.coords)[:-1]]
    poly = fill_polygon(outline)
    recs, _ = fill(outline, [], FillParams(angle_deg=0))
    assert max(poly.distance(SPoint(p)) for p in pts(recs)) < 0.15  # was 3.1 mm


def test_qa_bad_or_absurd_fill_settings_are_refused_clearly():
    for key, val in (("angle_deg", float("nan")), ("angle_deg", float("inf")), ("pull_comp_mm", float("nan")),
                     ("pull_comp_mm", -1), ("pull_comp_mm", 5), ("spacing_mm", "x")):
        with pytest.raises(DigitizeError):
            generate({"kind": "fill", "geometry": {"outline": SQUARE}, "params": {key: val}})
    assert generate({"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"angle_deg": None}})[0]  # null: the default
    with pytest.raises(DigitizeError, match="bigger than any hoop"):
        generate({"kind": "fill", "geometry": {"outline": [c(0, 0), c(5000, 0), c(5000, 5000), c(0, 5000)]}, "params": {}})
    with pytest.raises(DigitizeError, match="tack-down"):
        generate({"kind": "applique", "geometry": {"outline": SQUARE}, "params": {"tack_width_mm": 100}})


def test_qa_heavy_fabric_gets_a_firmer_fill_base():
    assert FillParams.from_dict({"underlay": "auto", "underlay_level": "heavy"}).underlay_spacing_mm == 1.5
    assert FillParams.from_dict({"underlay": "auto", "underlay_level": "normal"}).underlay_spacing_mm == 2.0
    heavy, _ = generate({"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"underlay": "auto", "underlay_level": "heavy"}})
    normal, _ = generate({"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"underlay": "auto", "underlay_level": "normal"}})
    assert len(heavy) > len(normal)


@pytest.mark.parametrize("width,split", [(12, 7), (8, 4), (12, 4), (9, 3)])
def test_qa_split_satin_pieces_never_exceed_the_longest_setting(width, split):
    for underlay in ([], ["center", "edge", "zigzag"]):
        recs, _ = generate({"kind": "satin", "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": width},
                            "params": {"underlay": underlay, "pull_comp_mm": 0, "split_mm": split, "tie_in": False, "tie_off": False}})
        assert _longest(recs) <= split + 1e-9


def test_qa_satin_warns_from_7_mm_unless_split():
    def warnings(w, **p):
        return generate({"kind": "satin", "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": w}, "params": {"underlay": [], **p}})[1]

    assert not warnings(6.5)
    assert any("Split long stitches" in x for x in warnings(8))
    assert not warnings(8, split_mm=7)


def test_qa_satin_tighter_than_its_width_warns():
    loop = [s(3, 0), s(0, 3), s(-3, 0), s(0, -3)]
    _, w = generate({"kind": "satin", "geometry": {"nodes": loop, "width_mm": 6, "closed": True}, "params": {}})
    assert any("curves more tightly" in x for x in w)
    for nodes, closed in (([c(0, 0), c(20, 0), c(20, 20), c(0, 20)], True), ([c(0, 0), s(10, 6), s(20, 0), c(30, 6)], False)):
        _, w = generate({"kind": "satin", "geometry": {"nodes": nodes, "width_mm": 2.5, "closed": closed}, "params": {}})
        assert not any("curves more tightly" in x for x in w)


def test_qa_reversed_satin_rails_are_named_as_such():
    _, w = generate({"kind": "satin", "geometry": {"rail_a": [c(0, 0), c(30, 0)], "rail_b": [c(30, 4), c(0, 4)]}, "params": {}})
    assert any("cross each other" in x for x in w)
    _, ok = generate({"kind": "satin", "geometry": {"rail_a": A, "rail_b": B}, "params": {}})
    assert not ok


def test_qa_ribbon_miter_is_limited_at_a_hairpin():
    pairs = ribbon_pairs([c(0, 0), c(10, 0), c(0, 0.5)], 2, 0.4)
    assert max(math.dist(a, b) for a, b in pairs) <= 2 * 2.0 + 1e-6


def test_qa_a_line_shorter_than_a_stitch_says_so():
    _, w = generate({"kind": "run", "geometry": {"nodes": [c(0, 0), c(0.2, 0)]}, "params": {}})
    assert any("single needle drop" in x for x in w)
    assert not generate({"kind": "run", "geometry": {"nodes": [c(0, 0), c(10, 0)]}, "params": {}})[1]


def test_qa_applique_border_spacing_is_what_was_asked():
    for sp in (0.4, 0.6, 1.0):
        recs, _ = generate({"kind": "applique", "geometry": {"outline": [c(0, 0), c(30, 0), c(30, 30), c(0, 30)]},
                            "params": {"spacing_mm": sp, "placement": False, "tack": "run", "tie_in": False}})
        stop = [i for i, r in enumerate(recs) if r[2] == 3][0]
        n = sum(1 for r in recs[stop + 1:] if r[2] == STITCH)
        assert 120 / (n / 2) == pytest.approx(sp, rel=0.05)  # was 0.33 for 0.4 and 0.98 for 1.0


def test_qa_wide_applique_border_is_split():
    recs, _ = generate({"kind": "applique", "geometry": {"outline": [c(0, 0), c(40, 0), c(40, 40), c(0, 40)]},
                        "params": {"cover_width_mm": 8}})
    assert _longest(recs) <= 7.0 + 1e-6  # was 11.5 mm


def test_qa_self_crossing_applique_sews_and_cuts_every_lobe():
    from threadline_engine import layout as L

    bow = [c(0, 0), c(20, 20), c(20, 0), c(0, 20)]
    recs, _ = generate({"kind": "applique", "geometry": {"outline": bow}, "params": {}})
    xs = [x for x, _ in pts(recs)]
    assert min(xs) < 1 and max(xs) > 19
    svg, _ = L.applique_svg({"items": [{"id": "a", "kind": "applique", "geometry": {"outline": bow}, "params": {}}]})
    assert svg.count(" Z") == 2


def test_qa_no_object_can_ask_for_millions_of_stitches():
    with pytest.raises(DigitizeError, match="far more than any design"):
        generate({"kind": "fill", "geometry": {"outline": [c(0, 0), c(900, 0), c(900, 900), c(0, 900)]},
                  "params": {"spacing_mm": 0.2, "stitch_mm": 1}})
    for g in ({"kind": "run", "geometry": {"nodes": [c(0, 0), c(1e7, 0)]}},
              {"kind": "satin", "geometry": {"nodes": [c(0, 0), c(5000, 0)], "width_mm": 3}}):
        with pytest.raises(DigitizeError, match="bigger than any hoop"):
            generate({**g, "params": {}})
    with pytest.raises(DigitizeError, match="isn't a number"):
        generate({"kind": "run", "geometry": {"nodes": [c(0, 0), [None, 1, "c"]]}, "params": {}})


def _sq(x0, y0, x1, y1):
    return [c(x0, y0), c(x1, y0), c(x1, y1), c(x0, y1)]


def test_qa2_s5_no_tick_split_advice_when_split_is_on():
    """QA2 S5: with Longest over 7 mm the warning told you to tick the box already ticked."""
    rib = {"kind": "satin", "geometry": {"nodes": [c(0, 0), c(30, 0)], "width_mm": 12}}
    for split, warned in ((0, "tick Split"), (7, None), (8, None), (12, "set Longest")):
        _, w = generate({**rib, "params": {"split_mm": split}})
        hit = [m for m in w if "wide" in m or "Longest" in m]
        assert (warned in hit[0]) if warned else not hit, (split, w)


@pytest.mark.parametrize("params,geom", [
    ({"width_mm": None}, None), ({"spacing_mm": None}, None), ({"underlay": None}, None), ({"underlay": 5}, "x"),
    ({"spacing_mm": "x"}, "x"), ({"split_mm": "x"}, "x"),
])
def test_qa2_s6_null_or_text_satin_settings_are_plain_errors_or_defaults(params, geom):
    """QA2 S6: null or text satin/run settings crashed as "engine bug"."""
    g = {"nodes": [c(0, 0), c(30, 0)], "width_mm": params.pop("width_mm", 3)}
    obj = {"kind": "satin", "geometry": g, "params": params}
    if geom:
        with pytest.raises(DigitizeError):
            generate(obj)
    else:
        assert generate(obj)[0]
    run = {"kind": "run", "geometry": {"nodes": [c(0, 0), c(30, 0)]}}
    assert generate({**run, "params": {"stitch_mm": None}})[0]
    with pytest.raises(DigitizeError):
        generate({**run, "params": {"stitch_mm": "x"}})


def test_qa2_s7_bad_hole_points_are_refused_not_sewn_over():
    """QA2 S7: a hole with a NaN point vanished (the fill sewed over it); a 1e9 point was kept."""
    from threadline_engine.digitize.applique import AppliqueParams, applique

    for bad in (float("nan"), 1e9):
        hole = [c(5, 5), c(10, 5), c(10, bad), c(5, 10)]
        with pytest.raises(DigitizeError, match="hole"):
            fill(_sq(0, 0, 20, 20), [hole], FillParams())
        with pytest.raises(DigitizeError, match="hole"):
            applique(_sq(0, 0, 20, 20), AppliqueParams(), [hole])


# ---------------------------------------------------------------- QA pass 2 decisions 1-4


def _neck_shape(neck=0.3):
    from shapely.geometry import box
    from shapely.ops import unary_union

    C = box(0, 0, 30, 30).difference(box(8, 8, 30, 22))
    g = unary_union([C, box(30, 23, 40, 23 + neck), box(40, 18, 55, 30)])
    return [[x, y, "c"] for x, y in list(g.exterior.coords)[:-1]]


def _longest(recs):
    return max((math.dist(a[:2], b[:2]) for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH), default=0)


def test_qa2_s1_a_thin_neck_elsewhere_does_not_turn_travel_into_jumps():
    """Decision 1: a neck under ~0.6 mm made the shrunk zone split, and every edge route gave up."""
    recs, _ = generate({"kind": "fill", "geometry": {"outline": _neck_shape()},
                        "params": {"underlay": [], "pull_comp_mm": 0, "angle_deg": 0}})
    assert not [r for r in recs if r[2] in (JUMP, TRIM)]


def test_qa2_s1_default_underlay_with_a_neck_needs_no_trims():
    recs, _ = generate({"kind": "fill", "geometry": {"outline": _neck_shape(0.5)}, "params": {}})
    assert not [r for r in recs if r[2] == TRIM]


@pytest.mark.parametrize("end", [(20, 15), (5, 25), (50, 20), (45, 29), (1, 1), (35, 23)])
def test_qa2_s1_a_fill_never_ends_on_a_jump_or_a_long_lock_stitch(end):
    recs, _ = generate({"kind": "fill", "geometry": {"outline": _neck_shape()},
                        "params": {"underlay": [], "pull_comp_mm": 0, "end_mm": list(end)}})
    assert recs[-1][2] == STITCH
    assert _longest(recs) < 7


def test_qa2_s1_lock_stitches_go_before_a_trailing_jump():
    from threadline_engine.digitize.stitches import tie_in, tie_off

    recs = [(0, 0, STITCH), (2, 0, STITCH), (4, 0, STITCH), (4, 0, TRIM), (20, 0, JUMP)]
    out = tie_off(recs)
    assert out[-2:] == recs[-2:] and len(out) == len(recs) + 2
    assert _longest(out) <= 2
    lead = [(0, 0, JUMP), (1, 0, STITCH), (3, 0, STITCH)]
    out = tie_in(lead)
    assert out[0] == lead[0] and _longest(out) <= 2


@pytest.mark.parametrize("rungs", [50, 55, 56])
def test_qa2_s2_zigzag_underlay_crosses_back_instead_of_retracing(rungs):
    """Decision 2: with an even zigzag count the way back sewed the same legs again."""
    from threadline_engine.digitize.stitches import satin_from_pairs

    pairs = [((i * 0.4, 0.0), (i * 0.4, 4.0)) for i in range(rungs)]
    recs, _ = satin_from_pairs(pairs, SatinParams(underlay=("zigzag",), spacing_mm=0.4))
    legs = [tuple(sorted([(round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))]))
            for a, b in zip(recs, recs[1:]) if a[2] == b[2] == STITCH]
    under = legs[: len(legs) - (rungs - 1)]
    assert len(set(under)) == len(under)


def test_qa2_s3_applique_moves_between_edges_are_trimmed():
    """Decision 3: moves over 3 mm between applique edges were bare jumps, never cut."""
    from threadline_engine.digitize.applique import STOP, AppliqueParams, applique

    holes = [_sq(10, 5, 20, 15), _sq(40, 5, 50, 15)]
    recs, _ = applique(_sq(0, 0, 60, 20), AppliqueParams(), holes)
    for prev, r in zip(recs, recs[1:]):
        if r[2] == JUMP and prev[2] not in (STOP, TRIM):
            assert math.dist(prev[:2], r[:2]) <= 3, (prev, r)
    assert [r for r in recs if r[2] == TRIM]


def test_qa2_s4_split_long_stitches_holds_at_sharp_corners():
    """Decision 4: wide ribbons and applique borders made 8-8.6 mm stitches at sharp corners."""
    from threadline_engine.digitize.applique import AppliqueParams, applique

    for turn in (30, 45):
        a = math.radians(turn)
        nodes = [c(0, 0), c(20, 0), c(20 - 20 * math.cos(a), 20 * math.sin(a))]
        recs, _ = generate({"kind": "satin", "geometry": {"nodes": nodes, "width_mm": 8},
                            "params": {"split_mm": 7}})
        assert _longest(recs) <= 7 + 1e-6, turn
    star = []
    for k in range(10):
        r = 25 if k % 2 == 0 else 7.5
        star.append(c(r * math.cos(math.pi * k / 5 + math.pi / 2), r * math.sin(math.pi * k / 5 + math.pi / 2)))
    recs, _ = applique(star, AppliqueParams(cover_width_mm=8))
    assert _longest(recs) <= 7 + 1e-6
