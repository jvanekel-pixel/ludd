"""Repairs that clean up a placed stitch file (Phase 4, Track B): tiny stitches (filter_small),
spots the needle hits over and over (declump), and the numbers repair.preview shows before
anything is accepted. The designs are made here, in whole 0.1 mm units (a PES file holds them
exactly), so the results are the same on every machine."""

import json
import math
import random

import pyembroidery as pe
import pytest

from snapshot_util import check, digest_pattern
from threadline_engine import design, layout, quality
from threadline_engine.methods import dispatcher
from threadline_engine.repair import clumps, stats

M = pe.COMMAND_MASK
S, J, T = pe.STITCH, pe.JUMP, pe.TRIM
RED = pe.EmbThread("#ff0000", "Red", "1", brand="Test")


def write(path, *runs) -> str:
    """A one-color PES file: each run is a list of points (0.1 mm); runs are cut apart by a trim
    and a jump."""
    p = pe.EmbPattern()
    p.add_thread(RED)
    last = None
    for run in runs:
        if last is not None:
            p.add_stitch_absolute(pe.TRIM, *last)
            p.add_stitch_absolute(pe.JUMP, *run[0])
        for x, y in run:
            p.stitch_abs(x, y)
        last = run[-1]
    p.end()
    pe.write(p, str(path), {"version": 6})
    return str(path)


def lay(path, ops=(), **item):
    return {"items": [{"id": "a", "path": path, "ops": list(ops), **item}]}


def render(path, ops=(), **item):
    return layout.render(lay(path, ops, **item))


def records(r, item=0):
    """The item's records as (x, y, command, src)."""
    return [(x, y, c & M, src) for (x, y, c), it, src in zip(r.pattern.stitches, r.item_of, r.src_of) if it == item]


def runs_of(recs):
    """Needle points of each thread run (between jumps, trims, stops and color changes)."""
    out, run = [], []
    for x, y, k, _ in recs:
        if k == S:
            run.append((x, y))
        elif run:
            out.append(run)
            run = []
    if run:
        out.append(run)
    return out


def file_points(path):
    return [(x, y, c & M) for x, y, c in design.load(path).stitches if c & M in (S, J, T, pe.STOP)]


def src_of(path, point):
    """The record number, in the file, of the stitch at `point`."""
    return next(i for i, (x, y, c) in enumerate(design.load(path).stitches) if c & M == S and (x, y) == point)


def _to_segment(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy))) if (dx or dy) else 0.0
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _to_line(p, line):
    if len(line) == 1:
        return math.dist(p, line[0])
    return min(_to_segment(p, a, b) for a, b in zip(line, line[1:]))


def drift_mm(before, after) -> float:
    """How far the thread path moved, either way, between two lists of runs (0.1 mm)."""
    assert len(before) == len(after)
    worst = 0.0
    for old, new in zip(before, after):
        for line, other in ((old, new), (new, old)):
            samples = [(a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20)
                       for a, b in zip(line, line[1:]) for k in range(21)] or line
            worst = max(worst, max(_to_line(p, other) for p in samples))
    return worst / 10


# ---------------------------------------------------------------- designs

#: Along the 60 mm line: after these 2 mm marks comes one more stitch, 0.1 or 0.2 mm further on.
TINY_AFTER = (0, 2, 4, 5, 7, 9, 10, 12, 13, 15, 16, 18, 19, 21, 22, 24, 25, 27, 28, 29)


def tiny_line():
    """A 60 mm line in 2 mm stitches with twenty 0.1-0.2 mm stitches sprinkled in, two of them
    among the lock stitches at its ends."""
    pts = []
    for i in range(31):
        pts.append((i * 20, 0))
        if i in TINY_AFTER:
            pts.append((i * 20 + 1 + TINY_AFTER.index(i) % 2, 0))
    return pts


CENTER = (2, 2)  # inside the 0.5 mm square from 0 to 0.5 mm, so every hit there counts together


def star(passes=30, radius=30):
    """`passes` diameters, each stitched through the middle (a needle drop there each time), joined
    by short stitches round the rim."""
    pts = []
    for k in range(passes):
        a = math.radians(k * 180 / passes)
        dx, dy = round(radius * math.cos(a)), round(radius * math.sin(a))
        one, other = (CENTER[0] + dx, CENTER[1] + dy), (CENTER[0] - dx, CENTER[1] - dy)
        first, last = (one, other) if k % 2 == 0 else (other, one)
        pts += [first, CENTER, last]
    return pts


def serpentine(rows=6, per_row=25, x0=100, y0=200):
    """Plain 2 mm stitching well away from the star, so the star is a small share of the design."""
    pts = []
    for r in range(rows):
        xs = [x0 + 20 * i for i in range(per_row)]
        pts += [(x, y0 + 20 * r) for x in (xs if r % 2 == 0 else xs[::-1])]
    return pts


def hits_at_center(recs):
    return sum(1 for x, y, k, _ in recs if k == S and clumps.cell_of(x, y) == clumps.cell_of(*CENTER))


# ---------------------------------------------------------------- tiny stitches


def test_tiny_stitches_go_ends_stay(tmp_path):
    pts = tiny_line()
    path = write(tmp_path / "tiny.pes", pts)
    got = runs_of(records(render(path, [{"op": "filter_small", "min_mm": 0.4}])))
    assert len(got) == 1
    out = got[0]
    assert out[0] == pts[0] and out[-1] == pts[-1]  # the ends don't move
    assert out[:3] == pts[:3] and out[-3:] == pts[-3:]  # the lock stitches stay, tiny or not
    for i in range(3, len(out) - 3):
        assert math.dist(out[i - 1], out[i]) / 10 >= 0.4 - 1e-9, (i, out[i - 1], out[i])
    # Only the eighteen tiny stitches away from the ends went.
    assert len(pts) - len(out) == 18
    assert [p for p in pts if p[0] % 20 == 0] == [p for p in out if p[0] % 20 == 0]


def test_repair_keeps_the_numbers_of_the_stitches_it_keeps(tmp_path):
    path = write(tmp_path / "tiny.pes", tiny_line())
    before = records(render(path))
    after = records(render(path, [{"op": "filter_small", "min_mm": 0.4}]))
    numbered = {src: (x, y, k) for x, y, k, src in before}
    assert all(numbered[src] == (x, y, k) for x, y, k, src in after)
    assert len({src for *_, src in after}) == len(after)


def test_no_long_stitch_is_created(tmp_path):
    # Dropping the stitch 0.2 mm after 10.9 mm would join 10.9 and 18.0: 7.1 mm of loose thread.
    pts = [(0, 0), (20, 0), (40, 0), (109, 0), (111, 0), (180, 0), (200, 0), (202, 0), (220, 0),
           (240, 0), (260, 0), (280, 0)]
    path = write(tmp_path / "long.pes", pts)
    out = runs_of(records(render(path, [{"op": "filter_small", "min_mm": 0.4}])))[0]
    assert (111, 0) in out and (202, 0) not in out
    assert max(math.dist(a, b) for a, b in zip(out, out[1:])) / 10 <= quality.LONG_MM


@pytest.mark.parametrize("min_mm", [0.4, 1.0])
def test_filter_small_twice_is_the_same(tmp_path, min_mm):
    # A rough zigzag path to and fro, many steps tiny and some nearly the longest allowed.
    rng = random.Random(7)
    x, y, way, pts = 0, 0, 1, [(0, 0)]
    for _ in range(300):
        x += way * rng.choice([1, 2, 3, 5, 9, 20, 40, 68, 69, 70])
        if not 0 <= x <= 900:
            way, y = -way, y + 10
        pts.append((x, y + rng.randrange(3)))
    path = write(tmp_path / "rough.pes", pts, [(0, 500), (1, 500), (2, 500), (30, 500), (31, 500), (60, 500), (90, 500)])
    once = records(render(path, [{"op": "filter_small", "min_mm": min_mm}]))
    twice = records(render(path, [{"op": "filter_small", "min_mm": min_mm}] * 2))
    assert once == twice and len(once) < len(records(render(path)))


def test_filter_small_keeps_each_run_and_cut_on_its_own(tmp_path):
    # Two short runs: every stitch is one of a run's first or last three, so nothing can go.
    a = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]
    b = [(100, 0), (101, 0), (102, 0)]
    path = write(tmp_path / "ends.pes", a, b)
    assert records(render(path, [{"op": "filter_small", "min_mm": 1.0}])) == records(render(path))


def test_a_damaged_or_out_of_range_setting_uses_the_standard_one(tmp_path):
    path = write(tmp_path / "tiny.pes", tiny_line())
    standard = records(render(path, [{"op": "filter_small", "min_mm": 0.4}]))
    for junk in ({}, {"min_mm": None}, {"min_mm": "lots"}, {"min_mm": float("nan")}):
        assert records(render(path, [{"op": "filter_small", **junk}])) == standard, junk
    # Past the ends of the range (0.2 to 1.0 mm) it's held to them.
    assert records(render(path, [{"op": "filter_small", "min_mm": 50}])) == records(render(path, [{"op": "filter_small", "min_mm": 1.0}]))
    star_path = write(tmp_path / "star.pes", star(), serpentine())
    five = records(render(star_path, [{"op": "declump", "max_hits": 5}]))
    for junk in ({}, {"max_hits": "x"}, {"max_hits": True}):
        assert records(render(star_path, [{"op": "declump", **junk}])) == five, junk
    assert records(render(star_path, [{"op": "declump", "max_hits": 0}])) == records(render(star_path, [{"op": "declump", "max_hits": 3}]))


# ---------------------------------------------------------------- needle clumps


def test_clump_at_a_star_center_is_thinned(tmp_path):
    path = write(tmp_path / "star.pes", star(), serpentine())
    before = records(render(path))
    r = render(path, [{"op": "declump", "max_hits": 5}])
    after = records(r)
    assert hits_at_center(before) == 30
    assert hits_at_center(after) <= 5
    assert drift_mm(runs_of(before), runs_of(after)) <= 0.3
    assert not [w for w in r.warnings if "15%" in w["message"]]
    # The latest hits went first: the middle's earliest drops are still there.
    centre_src = [src for x, y, k, src in before if (x, y) == CENTER]
    assert [src for x, y, k, src in after if (x, y) == CENTER] == centre_src[:4] + centre_src[-1:]


def test_declump_leaves_a_spot_at_the_limit_alone(tmp_path):
    path = write(tmp_path / "small.pes", star(passes=5), serpentine())
    assert records(render(path, [{"op": "declump", "max_hits": 5}])) == records(render(path))


def test_declump_never_makes_a_long_stitch(tmp_path):
    # Diameters of 8 mm: taking out a middle would leave 8 mm of loose thread.
    path = write(tmp_path / "wide.pes", star(radius=40), serpentine())
    r = render(path, [{"op": "declump", "max_hits": 5}])
    for run in runs_of(records(r)):
        assert max((math.dist(a, b) for a, b in zip(run, run[1:])), default=0) / 10 <= quality.LONG_MM


def test_lock_stitches_survive_declump(tmp_path):
    # Three runs, each tied in and off at the same spot, and passing through it once in between.
    p = (2, 2)
    runs = []
    for i, (dx, dy) in enumerate([(30, 0), (0, 30), (-30, 0)]):
        runs.append([p, (p[0] + 7, p[1]), p, (p[0] + dx, p[1] + dy), (p[0] + dx + 5 * (i + 1), p[1] + dy + 5),
                     p, (p[0] - dy, p[1] + dx), (p[0] - dy + 5, p[1] + dx + 5 * (i + 1)), p, (p[0] + 7, p[1]), p])
    path = write(tmp_path / "ties.pes", *runs)
    r = render(path, [{"op": "declump", "max_hits": 5}])
    got = runs_of(records(r))
    assert len(got) == 3
    for old, new in zip(runs, got):
        assert new[:3] == old[:3] and new[-3:] == old[-3:]
        assert new.count(p) == old.count(p) - 1  # the pass through the middle went
    assert not [w for w in r.warnings if "15%" in w["message"]]  # the locks held it, not the cap


def test_declump_caps_at_15_percent(tmp_path):
    path = write(tmp_path / "star.pes", star())
    before = records(render(path))
    r = render(path, [{"op": "declump", "max_hits": 5}])
    after = records(r)
    stitches = sum(1 for x, y, k, _ in before if k == S)
    assert stitches - sum(1 for x, y, k, _ in after if k == S) == int(stitches * 0.15) == 13
    assert hits_at_center(after) == 30 - 13
    notes = [w["message"] for w in r.warnings if w["code"].startswith("item_0_")]
    assert len(notes) == 1 and "15%" in notes[0] and "more than 5" in notes[0]


def test_declump_works_on_the_hoop_at_the_final_size(tmp_path):
    # 30 passes whose middles are 0.2 mm apart: no spot is crowded as the file is, but at a quarter
    # of the size they are 0.05 mm apart on the hoop.
    comb = [pt for k in range(30) for pt in [(100 + 2 * k, 80), (100 + 2 * k, 100), (100 + 2 * k, 120)]]
    path = write(tmp_path / "comb.pes", comb, serpentine())
    op = [{"op": "declump", "max_hits": 5}]
    assert records(render(path, op)) == records(render(path))
    small = {"transform": {"scale_x": 0.25, "scale_y": 0.25}}
    assert len(records(render(path, op, **small))) < len(records(render(path, **small)))


# ---------------------------------------------------------------- nothing asked, nothing changed


def test_untouched_file_sews_as_before(tmp_path):
    path = write(tmp_path / "all.pes", tiny_line(), star(), serpentine())
    r = render(path)
    assert [(x, y, c & M) for x, y, c in r.pattern.stitches[:-1]] == file_points(path)
    assert r.src_of == list(range(len(file_points(path))))
    # Edits that aren't repairs don't bring repairs with them.
    gone = src_of(path, (40, 0))
    edited = records(render(path, [{"op": "delete_stitches", "indices": [gone]}]))
    assert edited == [rec for rec in records(r) if rec[3] != gone]


def test_nothing_to_fix_changes_nothing(tmp_path):
    path = write(tmp_path / "clean.pes", serpentine())
    both = [{"op": "filter_small", "min_mm": 0.4}, {"op": "declump", "max_hits": 5}]
    r = render(path, both)
    assert records(r) == records(render(path))
    assert not r.warnings


# ---------------------------------------------------------------- the preview


def call(method, params):
    return dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}))


def preview(layout_, item_id="a", ops=()):
    out = call("repair.preview", {"layout": layout_, "item_id": item_id, "ops": list(ops)})
    assert "result" in out, out
    return out["result"]


STAT_KEYS = {"stitches", "trims", "jumps", "tiny", "longest_mm", "densest", "hits_max"}


def test_preview_reports_before_and_after(tmp_path):
    pts = [(i * 20, 0) for i in range(6)] + [(101, 0), (102, 0), (120, 0), (140, 0), (160, 0), (161, 0), (180, 0), (200, 0), (220, 0)]
    path = write(tmp_path / "p.pes", pts, [(0, 300), (20, 300), (40, 300)])
    got = preview(lay(path), ops=[{"op": "filter_small", "min_mm": 0.4}])
    assert set(got) == {"before", "after", "removed", "added", "limit", "notes"}
    assert set(got["before"]) == STAT_KEYS == set(got["after"])
    # By hand: the stitches 0.1 and 0.2 mm after 10 mm (two records in a row) and the one 0.1 mm
    # after 16 mm come out.
    a, b, c = src_of(path, (101, 0)), src_of(path, (102, 0)), src_of(path, (161, 0))
    assert b == a + 1
    assert got["removed"] == [[a, b + 1], [c, c + 1]]
    assert sum(end - start for start, end in got["removed"]) == 3 == got["before"]["stitches"] - got["after"]["stitches"]
    assert got["added"] == 0 and got["notes"] == []
    assert got["before"]["stitches"] == len(pts) + 3
    assert (got["before"]["trims"], got["before"]["jumps"]) == (1, 1) == (got["after"]["trims"], got["after"]["jumps"])
    assert got["before"]["tiny"] == 3 and got["after"]["tiny"] == 0
    assert got["before"]["longest_mm"] == 2.0 and got["after"]["longest_mm"] == 2.0
    assert got["limit"] == quality.DENSE_MM_PER_MM2
    assert got["before"]["densest"] > 0 and got["before"]["hits_max"] >= 3


def test_preview_replaces_the_items_repairs_and_keeps_its_other_edits(tmp_path):
    path = write(tmp_path / "p.pes", tiny_line())
    deleted = src_of(path, (120, 0))  # not next to a tiny stitch, so the same eighteen go
    current = lay(path, [{"op": "delete_stitches", "indices": [deleted]}, {"op": "filter_small", "min_mm": 0.4}])
    # The same repair: nothing would change.
    same = preview(current, ops=[{"op": "filter_small", "min_mm": 0.4}])
    assert same["before"] == same["after"] and same["removed"] == [] and same["added"] == 0
    # None: the tiny stitches come back; the deleted one stays deleted.
    off = preview(current, ops=[])
    assert off["after"]["stitches"] - off["before"]["stitches"] == 18 == off["added"]
    assert off["removed"] == []
    # And the layout given isn't changed.
    assert current["items"][0]["ops"][-1] == {"op": "filter_small", "min_mm": 0.4}


def test_preview_tells_what_declump_says(tmp_path):
    path = write(tmp_path / "star.pes", star())
    got = preview(lay(path), ops=[{"op": "declump", "max_hits": 5}])
    assert got["before"]["hits_max"] == 30 and got["after"]["hits_max"] == 30 - 13
    assert len(got["notes"]) == 1 and got["notes"][0].startswith("Thinning stopped at 15%")  # no design name in front


def test_preview_answers_plainly_when_it_cannot(tmp_path):
    path = write(tmp_path / "p.pes", tiny_line())
    fill = {"id": "f", "kind": "fill", "geometry": {"outline": [[0, 0, "c"], [30, 0, "c"], [30, 20, "c"]]},
            "params": {}, "thread": {"color": "#aa0000"}}
    for layout_, item_id in (({"items": [fill]}, "f"), (lay(path), "nope"), ({"items": []}, "a")):
        out = call("repair.preview", {"layout": layout_, "item_id": item_id, "ops": []})
        assert out["error"]["code"] == -32000, out


def test_preview_numbers_measure_density_as_the_checks_do(tmp_path):
    # 30 rows 0.1 mm apart over a 6 x 3 mm patch: about 10 mm of thread per mm².
    rows = [pt for r in range(30) for pt in ([(0, r), (30, r), (60, r)] if r % 2 == 0 else [(60, r), (30, r), (0, r)])]
    path = write(tmp_path / "thick.pes", rows, serpentine())
    r = render(path)
    n = stats.numbers(r, 0)
    segs, pts = quality._segments(r.pattern)
    cover, _, _, _ = quality._grid(segs, pts)
    assert n["densest"] == pytest.approx(float(cover.max()), abs=0.01) and n["densest"] > quality.DENSE_MM_PER_MM2
    assert n["stitches"] == len(rows) + len(serpentine())
    assert all(type(v) in (int, float) for v in n.values())  # nothing JSON can't send


def test_the_checks_that_can_be_repaired_name_the_command(tmp_path):
    rows = [pt for r in range(60) for pt in ([(0, r), (30, r), (60, r), (90, r)] if r % 2 == 0 else [(90, r), (60, r), (30, r), (0, r)])]
    shorts = [(200 + 2 * i, 0) for i in range(60)]
    path = write(tmp_path / "bad.pes", rows, star(), shorts)
    found = {c["code"]: c for c in layout.check(lay(path))["checks"]}
    assert found["dense"]["level"] == "info" and "Limit density for this fabric" in found["dense"]["fix"]
    assert found["needle_hits"]["level"] == "info" and "Thin out dense spots" in found["needle_hits"]["fix"]
    assert "Remove tiny stitches" in found["short"]["fix"]
    # The codes and messages are as they were.
    assert found["dense"]["message"].startswith("Thick spots in a placed stitch file")
    assert found["needle_hits"]["message"] == "A placed stitch file has spots where the needle hits often"
    assert found["short"]["message"].endswith("very short stitches (under 0.3 mm)")


# ---------------------------------------------------------------- snapshots

SNAPSHOTS = {
    "tiny_line": (tiny_line, [{"op": "filter_small", "min_mm": 0.4}]),
    "star_clump": (lambda: star(), [{"op": "declump", "max_hits": 5}]),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOTS))
def test_snapshots(tmp_path, name):
    make, ops = SNAPSHOTS[name]
    runs = [make()] if name == "tiny_line" else [make(), serpentine()]
    r = render(write(tmp_path / f"{name}.pes", *runs), ops)
    check("repair_cleanup", name, digest_pattern(r.pattern))
