"""Phase 4, Track C: recognizing fills, satins and runs inside a stitch file (repair/recognize.py),
rebuilding them at a new size (repair/rebuild.py) and limiting density for a fabric
(repair/density.py).

Ground truth comes from LUDD's own digitizer: stitches are made from a known shape, then recognized.
"""

import math
import random
import re
from pathlib import Path

import pyembroidery as pe
import pytest
from shapely.geometry import Polygon, box

import invariants
from snapshot_util import check as snapshot, digest_pattern
from threadline_engine import design, fabrics, layout
from threadline_engine.digitize.stitches import STITCH, generate
from threadline_engine.repair import density, rebuild
from threadline_engine.repair.recognize import Span, recognize

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
FIXTURES = ROOT / "fixtures"
LOGS = ROOT / "_logs"

SQUARE = [[0, 0, "c"], [40, 0, "c"], [40, 40, "c"], [0, 40, "c"]]


def _fill(outline=SQUARE, angle=30.0, spacing=0.4, **params):
    obj = {"kind": "fill", "geometry": {"outline": outline},
           "params": {"angle_deg": angle, "spacing_mm": spacing, "underlay": [], "pull_comp_mm": 0, **params}}
    return generate(obj)[0]


def _satin_column(length=30.0, width=3.0, spacing=0.4):
    obj = {"kind": "satin", "geometry": {"rail_a": [[0, 0, "c"], [0, length, "c"]],
                                         "rail_b": [[width, 0, "c"], [width, length, "c"]]},
           "params": {"underlay": [], "pull_comp_mm": 0, "spacing_mm": spacing}}
    return generate(obj)[0]


def _ribbon(width=4.0):
    nodes = [[0, 0, "c"], [10, -8, "s"], [25, -6, "s"], [35, 6, "c"]]
    obj = {"kind": "satin", "geometry": {"nodes": nodes, "width_mm": width},
           "params": {"underlay": [], "pull_comp_mm": 0}}
    return generate(obj)[0]


def _points(recs):
    return [(float(r[0]), float(r[1])) for r in recs if r[2] == STITCH]


def _biggest(spans, kind):
    found = [s for s in spans if s.kind == kind]
    assert found, f"no {kind} in {[(s.kind, s.start, s.end) for s in spans]}"
    return max(found, key=lambda s: (s.end - s.start, -s.start))


def _covers_all(spans, n):
    assert spans[0].start == 0 and spans[-1].end == n
    for a, b in zip(spans, spans[1:]):
        assert a.end == b.start and a.start < a.end


def _iou(a, b):
    return a.intersection(b).area / a.union(b).area


def _angle_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


# ---------------------------------------------------------------- stitch files and layouts


def _pes(path: Path, *runs) -> str:
    """A PES with one color per run of (x, y, kind) records in mm."""
    p = pe.EmbPattern()
    for n, recs in enumerate(runs):
        p.add_thread(pe.EmbThread(["#cc2222", "#2222cc", "#22aa22"][n % 3], f"T{n}", str(n)))
        if n:
            p.color_change()
        for x, y, k in recs:
            if k == STITCH:
                p.stitch_abs(round(x * 10), round(y * 10))
            else:
                p.move_abs(round(x * 10), round(y * 10))
    p.end()
    pe.write(p, str(path), {"version": 6})
    return str(path)


def _layout(path, ops=(), fabric=None, **transform):
    t = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False, **transform}
    lay = {"items": [{"id": "f", "kind": "file", "path": str(path), "transform": t, "ops": list(ops)}]}
    if fabric:
        lay["fabric"] = fabric
    return lay


def _sewn(rendered):
    """The rendered design's records in mm, as (x, y, kind)."""
    return [(x / 10, y / 10, c & pe.COMMAND_MASK) for x, y, c in rendered.pattern.stitches
            if c & pe.COMMAND_MASK in (pe.STITCH, pe.JUMP, pe.TRIM, pe.STOP)]


def _runs(recs):
    """Thread runs: stitch points between jumps, trims and stops."""
    runs, cur = [], []
    for x, y, k in recs:
        if k == STITCH:
            cur.append((x, y))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def _fill_spacing(recs):
    """The row spacing of the biggest fill found in `recs`, and that span."""
    best = None
    for run in _runs(recs):
        for s in recognize(run):
            if s.kind == "fill" and (best is None or s.end - s.start > best.end - best.start):
                best = s
    assert best is not None, "no fill recognized"
    return best.spacing_mm, best


def _coverage(rendered) -> float:
    for w in rendered.warnings:
        m = re.search(r"Rebuilt (\d+)% of the stitches", w["message"])
        if m:
            return int(m.group(1)) / 100
    raise AssertionError(f"no rebuild note in {[w['message'] for w in rendered.warnings]}")


def _stitch_count(recs):
    return sum(1 for r in recs if r[2] == STITCH)


# ---------------------------------------------------------------- C1 recognize


def test_recognizes_a_tatami_square():
    pts = _points(_fill(angle=30))
    spans = recognize(pts)
    _covers_all(spans, len(pts))
    f = _biggest(spans, "fill")
    assert _angle_diff(f.angle_deg, 30) <= 2
    assert abs(f.spacing_mm - 0.4) <= 0.4 * 0.05
    assert _iou(Polygon(f.outline), box(0, 0, 40, 40)) >= 0.9
    assert 3.0 <= f.stitch_mm <= 3.6
    assert (f.end - f.start) >= 0.9 * len(pts)


@pytest.mark.parametrize("angle", [0, 30, 45, 90, 135])
def test_recognizes_fills_at_every_angle(angle):
    pts = _points(_fill(angle=angle))
    f = _biggest(recognize(pts), "fill")
    assert _angle_diff(f.angle_deg, angle) <= 2
    assert abs(f.spacing_mm - 0.4) <= 0.4 * 0.05
    assert _iou(Polygon(f.outline), box(0, 0, 40, 40)) >= 0.9


def test_recognizes_fills_after_rounding_to_the_machine_grid():
    """A stitch file stores whole 0.1 mm: recognition still finds the angle and spacing."""
    for angle in (0, 30, 45, 135):
        pts = [(round(x, 1), round(y, 1)) for x, y in _points(_fill(angle=angle))]
        f = _biggest(recognize(pts), "fill")
        assert _angle_diff(f.angle_deg, angle) <= 2
        assert abs(f.spacing_mm - 0.4) <= 0.4 * 0.05


def test_recognizes_a_satin_column():
    pts = _points(_satin_column(width=3.0, spacing=0.4))
    spans = recognize(pts)
    _covers_all(spans, len(pts))
    s = _biggest(spans, "satin")
    widths = sorted(math.dist(a, b) for a, b in zip(s.rail_a, s.rail_b))
    assert abs(widths[len(widths) // 2] - 3.0) <= 0.3
    assert abs(s.spacing_mm - 0.4) <= 0.04
    assert (s.end - s.start) >= 0.9 * len(pts)


def test_recognizes_a_zigzag_satin():
    """Bought designs sew satins as a zigzag (each stitch crosses the column)."""
    pts = []
    for i in range(60):
        pts.append((0.0 if i % 2 == 0 else 4.0, i * 0.2))
    s = _biggest(recognize(pts), "satin")
    assert s.end - s.start == len(pts)
    assert abs(s.spacing_mm - 0.4) <= 0.04
    assert all(p[0] == 0.0 for p in s.rail_a) and all(p[0] == 4.0 for p in s.rail_b)


def test_recognizes_a_curved_satin_ribbon():
    pts = _points(_ribbon(width=4.0))
    spans = recognize(pts)
    _covers_all(spans, len(pts))
    s = _biggest(spans, "satin")
    assert (s.end - s.start) >= 0.8 * len(pts)
    widths = sorted(math.dist(a, b) for a, b in zip(s.rail_a, s.rail_b))
    assert abs(widths[len(widths) // 2] - 4.0) <= 0.3
    assert 0.3 <= s.spacing_mm <= 0.5


def test_recognizes_a_run_and_leaves_locks_as_other():
    obj = {"kind": "run", "geometry": {"nodes": [[0, 0, "c"], [20, 0, "s"], [30, 10, "s"], [30, 25, "c"]]},
           "params": {"stitch_mm": 2.5}}
    pts = _points(generate(obj)[0])
    spans = recognize(pts)
    _covers_all(spans, len(pts))
    assert spans[0].kind == "other" and spans[-1].kind == "other"  # the tie-in and the tie-off
    r = _biggest(spans, "run")
    assert r.end - r.start >= len(pts) - 8
    assert abs(r.stitch_mm - 2.5) <= 0.3
    for s in spans:
        if s.kind == "other":
            assert s.end - s.start <= 4


def test_recognize_is_steady_under_rounding_noise():
    """Noise far below the machine's 0.1 mm grid never changes what is recognized."""
    pts = _points(_fill(angle=45)) + [(45.0, 40.0)] + _points(_satin_column())
    rng = random.Random(7)
    noisy = [(x + rng.uniform(-1e-7, 1e-7), y + rng.uniform(-1e-7, 1e-7)) for x, y in pts]
    a, b = recognize(pts), recognize(noisy)
    assert [(s.kind, s.start, s.end) for s in a] == [(s.kind, s.start, s.end) for s in b]
    for s, t in zip(a, b):
        if s.spacing_mm is not None:
            assert abs(s.spacing_mm - t.spacing_mm) < 1e-4


def test_recognize_handles_tiny_runs():
    assert recognize([]) == []
    assert [(s.kind, s.start, s.end) for s in recognize([(0.0, 0.0)])] == [("other", 0, 1)]
    assert [(s.kind, s.start, s.end) for s in recognize([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0)])] == [("other", 0, 3)]
    assert isinstance(recognize([(0.0, 0.0), (2.0, 0.0)])[0], Span)


# ---------------------------------------------------------------- C2 rebuild


def _square_file(tmp_path, angle=30.0):
    recs = _fill(angle=angle)
    return _pes(tmp_path / "square.pes", recs), recs


def test_rebuild_at_150_keeps_row_spacing(tmp_path):
    path, recs = _square_file(tmp_path)
    original, _ = _fill_spacing(_sewn(layout.render(_layout(path))))
    plain = _sewn(layout.render(_layout(path, scale_x=1.5, scale_y=1.5)))
    r = layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5))
    got = _sewn(r)
    spacing, _ = _fill_spacing(got)
    assert abs(spacing - original) <= 0.1 * original
    assert abs(_fill_spacing(plain)[0] - 1.5 * original) <= 0.1 * original  # (as it was: rows 50% apart)
    n0 = _stitch_count(_sewn(layout.render(_layout(path))))
    assert abs(_stitch_count(got) / n0 - 2.25) <= 2.25 * 0.15
    xs, ys = [p[0] for p in _points(got)], [p[1] for p in _points(got)]
    assert abs((max(xs) - min(xs)) - 60) <= 0.5 and abs((max(ys) - min(ys)) - 60) <= 0.5
    invariants.assert_sane(got, max_stitch_mm=7.15)


def test_rebuild_at_60_keeps_row_spacing(tmp_path):
    path, _ = _square_file(tmp_path)
    original, _ = _fill_spacing(_sewn(layout.render(_layout(path))))
    got = _sewn(layout.render(_layout(path, [{"op": "rebuild"}], scale_x=0.6, scale_y=0.6)))
    spacing, _ = _fill_spacing(got)
    assert abs(spacing - original) <= 0.1 * original
    n0 = _stitch_count(_sewn(layout.render(_layout(path))))
    assert abs(_stitch_count(got) / n0 - 0.36) <= 0.36 * 0.20
    invariants.assert_sane(got, max_stitch_mm=7.15)


def test_rebuild_keeps_first_and_last_stitch(tmp_path):
    path, _ = _square_file(tmp_path)
    before = _points(_sewn(layout.render(_layout(path))))
    cx = (min(p[0] for p in before) + max(p[0] for p in before)) / 2
    cy = (min(p[1] for p in before) + max(p[1] for p in before)) / 2
    for s in (1.5, 0.6):
        got = _points(_sewn(layout.render(_layout(path, [{"op": "rebuild"}], scale_x=s, scale_y=s))))
        for want, have in ((before[0], got[0]), (before[-1], got[-1])):
            scaled = (cx + (want[0] - cx) * s, cy + (want[1] - cy) * s)
            assert math.dist(scaled, have) <= 0.5


def test_rebuild_stretched_one_way_turns_the_angle(tmp_path):
    path, _ = _square_file(tmp_path, angle=45)
    got = _sewn(layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.0)))
    spacing, f = _fill_spacing(got)
    want = math.degrees(math.atan2(math.sin(math.radians(45)) * 1.0, math.cos(math.radians(45)) * 1.5))
    assert _angle_diff(f.angle_deg, want) <= 2
    assert abs(spacing - 0.4) <= 0.04
    xs = [p[0] for p in _points(got)]
    assert abs((max(xs) - min(xs)) - 60) <= 0.5


def _scribble():
    """Stitches that are no fill, satin or run: lengths and turns all over the place."""
    rng = random.Random(3)
    x, y, out = 10.0, 10.0, []
    for _ in range(80):
        out.append((x, y, STITCH))
        a = rng.uniform(0, 2 * math.pi)
        d = rng.choice([0.4, 0.6, 5.5, 6.0, 0.5, 6.5])
        x, y = min(max(x + d * math.cos(a), 0), 30), min(max(y + d * math.sin(a), 0), 30)
    return out


def test_unrecognized_parts_resize_as_before(tmp_path):
    path = _pes(tmp_path / "scribble.pes", _scribble())
    plain = layout.render(_layout(path, scale_x=1.3, scale_y=1.3))
    rebuilt = layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.3, scale_y=1.3))
    assert [tuple(round(v, 6) for v in s[:2]) + (s[2],) for s in plain.pattern.stitches] == \
           [tuple(round(v, 6) for v in s[:2]) + (s[2],) for s in rebuilt.pattern.stitches]
    assert plain.src_of == rebuilt.src_of  # their stitch numbers stay, for stitch editing
    assert _coverage(rebuilt) == 0
    assert any("Most of this design couldn't be rebuilt" in w["message"] for w in rebuilt.warnings)


def test_rebuild_then_turn_and_mirror(tmp_path):
    path, _ = _square_file(tmp_path)
    flat = layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5))
    turned = layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5, rotate=30, flip_x=True))
    assert turned.items[0]["center_mm"] == pytest.approx(flat.items[0]["center_mm"])
    cx, cy = (v * 10 for v in flat.items[0]["center_mm"])
    a = math.radians(30)
    want = []
    for x, y, c in flat.pattern.stitches:
        px, py = -(x - cx), y - cy
        want.append((px * math.cos(a) - py * math.sin(a) + cx, px * math.sin(a) + py * math.cos(a) + cy, c))
    assert len(want) == len(turned.pattern.stitches)
    for (x, y, c), (u, v, k) in zip(want, turned.pattern.stitches):
        assert c == k and abs(x - u) < 1e-6 and abs(y - v) < 1e-6


def test_rebuild_keeps_the_center_and_clears_the_resize_warning(tmp_path):
    path, _ = _square_file(tmp_path)
    plain = layout.render(_layout(path, scale_x=1.5, scale_y=1.5, x=3, y=-2))
    rebuilt = layout.render(_layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5, x=3, y=-2))
    assert rebuilt.items[0]["center_mm"] == pytest.approx(plain.items[0]["center_mm"])
    assert rebuilt.items[0]["source_size_mm"] == plain.items[0]["source_size_mm"]
    pb, rb = plain.items[0]["bounds_mm"], rebuilt.items[0]["bounds_mm"]
    assert all(abs(a - b) <= 0.5 for a, b in zip(pb, rb))
    scale = [w["message"] for w in plain.warnings if w["code"].startswith("scale_")]
    assert scale and "Rebuild stitches at this size (Alt+Shift+R) fixes this." in scale[0]
    assert not any(w["code"].startswith("scale_") for w in rebuilt.warnings)


def test_rebuild_at_full_size_changes_nothing(tmp_path):
    path, _ = _square_file(tmp_path)
    plain = layout.render(_layout(path))
    same = layout.render(_layout(path, [{"op": "rebuild"}]))
    assert plain.pattern.stitches == same.pattern.stitches and plain.src_of == same.src_of


def test_rebuild_marks_new_stitches_and_is_deterministic(tmp_path):
    path, _ = _square_file(tmp_path)
    lay = _layout(path, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5)
    r = layout.render(lay)
    assert -1 in r.src_of
    invariants.assert_deterministic(lambda: [tuple(s) for s in layout.render(lay).pattern.stitches])


def test_rebuild_is_steady_under_rounding_noise():
    """The same blocks give the same stitches; noise far below the 0.1 mm grid moves none of them
    by more than that noise scaled."""
    from threadline_engine.layout.model import Block, Transform
    from threadline_engine.layout.passes import OpContext

    recs = _fill(angle=30) + [(45.0, 40.0, STITCH)] + _satin_column()
    rng = random.Random(11)

    def blocks(noise):
        return [Block({}, [[x * 10 + rng.uniform(-noise, noise), y * 10 + rng.uniform(-noise, noise), k, 0, i]
                           for i, (x, y, k) in enumerate(recs)])]

    def run(bl):
        ctx = OpContext({}, 0, Transform(scale_x=1.5, scale_y=1.5), (200.0, 200.0), None, [])
        return [r for b in rebuild.apply(bl, {"op": "rebuild"}, ctx) for r in b.recs]

    a, b = run(blocks(0.0)), run(blocks(1e-6))
    assert len(a) == len(b)
    assert max(max(abs(p[0] - q[0]), abs(p[1] - q[1])) for p, q in zip(a, b)) < 1e-3


def _sample_layout(name, s=1.5, **kw):
    return _layout(SAMPLES / name, [{"op": "rebuild"}], scale_x=s, scale_y=s, **kw)


def test_rebuild_sample_coverage():
    r = layout.render(_sample_layout("Flower.pes"))
    assert _coverage(r) >= 0.70
    invariants.assert_sane(_sewn(r), max_stitch_mm=7.15)


@pytest.mark.parametrize("name", ["Star badge.pes", "Wreath.pes"])
def test_rebuild_other_samples_stay_sane(name):
    r = layout.render(_sample_layout(name))
    assert 0 <= _coverage(r) <= 1
    invariants.assert_sane(_sewn(r), max_stitch_mm=7.15)


def test_rebuilt_sample_round_trips_pes_and_jef(tmp_path):
    from threadline_engine.prepare import Options, prepare

    lay = _sample_layout("Flower.pes")
    for ext in ("pes", "jef"):
        want, _ = prepare(layout.render(lay).pattern, Options.from_dict(None), ext)
        dest = tmp_path / f"flower.{ext}"
        layout.export(lay, str(dest))
        back = design.load(dest)
        count = lambda p: sum(1 for *_, c in p.stitches if c & pe.COMMAND_MASK == pe.STITCH)  # noqa: E731
        assert count(back) == count(want)


# ---------------------------------------------------------------- C3 density limit


def test_density_limits_come_from_the_fabric():
    woven = density.limits("woven")
    assert woven["fill"] == pytest.approx((0.33, 0.40)) and woven["satin"] == pytest.approx((0.30, 0.36))
    knit = fabrics.get("knit")["density"]
    assert density.limits("knit")["fill"] == pytest.approx((0.33 / knit, 0.40 / knit))


def test_density_limit_respaces_a_dense_fill(tmp_path):
    path = _pes(tmp_path / "dense.pes", _fill(angle=30, spacing=0.25))
    before, _ = _fill_spacing(_sewn(layout.render(_layout(path, fabric="knit"))))
    assert abs(before - 0.25) <= 0.025
    r = layout.render(_layout(path, [{"op": "density_limit"}], fabric="knit"))
    got = _sewn(r)
    spacing, _ = _fill_spacing(got)
    assert abs(spacing - 0.44) <= 0.044
    invariants.assert_sane(got, max_stitch_mm=7.15)


def test_density_limit_respaces_a_dense_satin(tmp_path):
    path = _pes(tmp_path / "satin.pes", _satin_column(spacing=0.2))
    got = _sewn(layout.render(_layout(path, [{"op": "density_limit"}])))
    s = max((s for run in _runs(got) for s in recognize(run) if s.kind == "satin"), key=lambda s: s.end - s.start)
    assert abs(s.spacing_mm - 0.36) <= 0.036


def test_density_limit_leaves_normal_fills_alone(tmp_path):
    path = _pes(tmp_path / "normal.pes", _fill(angle=30, spacing=0.4), _satin_column(spacing=0.4))
    plain = layout.render(_layout(path, scale_x=1.2, scale_y=1.2, rotate=20))
    limited = layout.render(_layout(path, [{"op": "density_limit"}], scale_x=1.2, scale_y=1.2, rotate=20))
    assert plain.pattern.stitches == limited.pattern.stitches and plain.src_of == limited.src_of


# ---------------------------------------------------------------- snapshots and the owner's designs


def test_snapshots(tmp_path):
    square, _ = _square_file(tmp_path)
    satin = _pes(tmp_path / "satin.pes", _satin_column())
    cases = {
        "square_150": _layout(square, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5),
        "square_60": _layout(square, [{"op": "rebuild"}], scale_x=0.6, scale_y=0.6),
        "satin_150": _layout(satin, [{"op": "rebuild"}], scale_x=1.5, scale_y=1.5),
        "flower_150": _sample_layout("Flower.pes"),
    }
    for name, lay in cases.items():
        r = layout.render(lay)
        invariants.assert_sane(_sewn(r), max_stitch_mm=7.15)
        snapshot("repair_rebuild", name, digest_pattern(r.pattern))


def _fixture_files():
    exts = {f["ext"] for f in design.formats()["read"]}
    return sorted(p for p in FIXTURES.glob("*") if p.suffix.lower().lstrip(".") in exts) if FIXTURES.is_dir() else []


@pytest.mark.skipif(not _fixture_files(), reason="no fixtures/ (the owner's own designs, never committed)")
def test_rebuild_coverage_on_fixtures():
    """Not a pass or fail: writes how much of each of the owner's designs Rebuild remakes at 150%."""
    lines = []
    for p in _fixture_files():
        try:
            lines.append(f"{_coverage(layout.render(_layout(p, [{'op': 'rebuild'}], scale_x=1.5, scale_y=1.5))):6.0%}  {p.name}")
        except Exception as exc:  # noqa: BLE001 (a damaged file is a line in the report, not a failure)
            lines.append(f"  error  {p.name}: {exc}")
    LOGS.mkdir(exist_ok=True)
    (LOGS / "rebuild-coverage.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
