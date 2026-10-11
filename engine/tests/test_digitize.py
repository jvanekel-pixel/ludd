"""Digitizing: paths, running stitch, satin, tatami fill. Property tests plus snapshots.

Snapshots live in tests/snapshots/digitize.json. A changed stitch output fails the test so it
can be reviewed; re-record with UPDATE_SNAPSHOTS=1 after checking the new output is right.
"""

import hashlib
import json
import math
import os
from pathlib import Path

import pytest
from shapely.geometry import Point as SPoint, Polygon

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
    running,
    satin,
    satin_pairs,
)

SNAPSHOTS = Path(__file__).parent / "snapshots" / "digitize.json"


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
    bowtie = [c(0, 0), c(10, 10), c(10, 0), c(0, 10)]
    recs, _ = fill(bowtie, [], FillParams(underlay=()))
    assert pts(recs)


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
    "fill_square_45": {"kind": "fill", "geometry": {"outline": SQUARE}, "params": {"angle_deg": 45}},
    "fill_donut": {
        "kind": "fill",
        "geometry": {"outline": SQUARE, "holes": [[c(7, 7), c(13, 7), c(13, 13), c(7, 13)]]},
        "params": {"angle_deg": 0, "underlay": ["edge"]},
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
    got = _digest(generate(SNAPSHOT_CASES[name])[0])
    stored = json.loads(SNAPSHOTS.read_text()) if SNAPSHOTS.exists() else {}
    if os.environ.get("UPDATE_SNAPSHOTS") or name not in stored:
        stored[name] = got
        SNAPSHOTS.parent.mkdir(exist_ok=True)
        SNAPSHOTS.write_text(json.dumps(stored, indent=1, sort_keys=True) + "\n")
        return
    assert got == stored[name], f"{name} stitches changed; review, then re-record with UPDATE_SNAPSHOTS=1"


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
