"""Branching (P7-B1), the Phase 7 audit's cases: three shapes in one thread that touch, overlap or
meet, through render and PES export, and the fixes behind them.

`CASES` marks each case WHOLE (sewn as one path: no jump or trim from its first stitch to its last,
in the render and in the PES file read back) or with the cuts and jumps it still has, each with its
note. A later improvement that sews one more case whole fails here on purpose: mark it WHOLE."""

import math
import random

import pyembroidery as pe
import pytest
import shapely
from shapely.geometry import Point, Polygon

from test_branch import BLUE, RED, between_first_and_last, fill, lay, obj, recs_of, sq
from threadline_engine import layout as L
from threadline_engine.digitize import stitches as dz
from threadline_engine.layout import branch

M = pe.COMMAND_MASK


@pytest.fixture(autouse=True)
def _fresh():
    branch.forget()
    yield
    branch.forget()


def run(i, pts, **kw):
    return obj(i, "run", {"nodes": [[x, y, "c"] for x, y in pts]}, **kw)


def satin(i, pts, w=3.0, **kw):
    return obj(i, "satin", {"nodes": [[x, y, "c"] for x, y in pts], "width_mm": w}, **kw)


def circ(cx, cy, r, n=32):
    return [[cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), "c"] for k in range(n)]


WHOLE = (0, 0)  # (trims, jumps) between the branch's first stitch and its last

# name: (shapes, (trims, jumps) in the render)
CASES = {
    "fill/edges": ([fill("a", 0, 0, 10), fill("b", 10, 0, 10), fill("c", 20, 0, 10)], WHOLE),
    "fill/overlap": ([fill("a", 0, 0, 12), fill("b", 9, 2, 12), fill("c", 18, 0, 12)], WHOLE),
    "fill/corners": ([fill("a", 0, 0, 10), fill("b", 10, 10, 10), fill("c", 20, 20, 10)], WHOLE),
    "fill/circles_tangent": ([obj("a", "fill", {"outline": circ(5, 5, 5)}), obj("b", "fill", {"outline": circ(15, 5, 5)}),
                              obj("c", "fill", {"outline": circ(25, 5, 5)})], WHOLE),
    "run/end_to_end": ([run("a", [(0, 0), (10, 0)]), run("b", [(10, 0), (20, 5)]), run("c", [(20, 5), (30, 0)])], WHOLE),
    # Lines that cross or meet in a T are not joined (a later phase): two cuts each.
    "run/cross": ([run("a", [(0, 0), (20, 0)]), run("b", [(10, -5), (10, 10)]), run("c", [(5, 8), (25, 8)])], (2, 2)),
    "run/T": ([run("a", [(0, 0), (20, 0)]), run("b", [(10, 0), (10, 10)]), run("c", [(0, 10), (20, 10)])], (2, 2)),
    "satin/end_to_end": ([satin("a", [(0, 0), (10, 0)]), satin("b", [(10, 0), (20, 0)]), satin("c", [(20, 0), (30, 0)])],
                         WHOLE),
    "satin/overlap": ([satin("a", [(0, 0), (12, 0)]), satin("b", [(10, -5), (10, 10)]), satin("c", [(8, 8), (20, 8)])],
                      WHOLE),
    # The second satin ends on its inner edge, 1.93 mm across the bare outer corner from where the
    # third starts: a jump (no trim: 3 mm or less).
    "satin/L_corners": ([satin("a", [(0, 0), (10, 0)]), satin("b", [(10, 0), (10, 10)]),
                         satin("c", [(10, 10), (20, 10)])], (0, 1)),
    "mix/end_to_end": ([fill("a", 0, 0, 10), run("b", [(10, 5), (20, 5)]), satin("c", [(20, 5), (30, 5)])], WHOLE),
    # The satin ends 2 mm past the line, whose ends are 6 and 9 mm away, with nothing over the way.
    "mix/overlap": ([fill("a", 0, 0, 12), satin("b", [(8, 6), (22, 6)]), run("c", [(20, 0), (20, 15)])], (1, 1)),
    "mix/corners": ([fill("a", 0, 0, 10), run("b", [(10, 10), (20, 20)]), fill("c", 20, 20, 10)], WHOLE),
    # The line along the square's edge starts 5 mm off it.
    "mix/line_along_edge": ([fill("a", 0, 0, 10), run("b", [(-5, 10), (15, 10)]), fill("c", 15, 10, 10)], (1, 1)),
    # The satin ends 2 mm short of the second square, 4.4 mm from where it starts.
    "mix/satin_between_fills": ([fill("a", 0, 0, 10), satin("b", [(-2, 11.5), (12, 11.5)]), fill("c", 0, 13, 10)],
                                (1, 1)),
}


def _moves(span):
    return (sum(1 for r in span if r[2] == pe.TRIM), sum(1 for r in span if r[2] == pe.JUMP))


@pytest.mark.parametrize("name", sorted(CASES))
def test_three_shapes_sew_whole_or_say_why(name, tmp_path):
    shapes, expected = CASES[name]
    layout = lay(*shapes)
    r = L.render(layout)
    assert len(r.blocks) == 1 and [b["items"] for b in r.branches] == [["a", "b", "c"]]
    span = between_first_and_last(recs_of(r), {0, 1, 2})
    assert _moves(span) == expected, [x for x in span if x[2] != pe.STITCH]
    notes = [w["message"] for w in r.warnings if w["code"].startswith("branch_cut_")]
    assert len(notes) == max(expected), notes
    for note in notes:
        assert "don't touch" not in note and "hidden under stitching" in note, note
    assert r.branches[0]["cuts"] == expected[0]
    # The PES file says the same (its writer writes a jump as a trim and a jump).
    dest = tmp_path / "three.pes"
    L.export(layout, str(dest))
    first = []
    for x, y, k in pe.read(str(dest)).stitches:
        if k & M in (pe.COLOR_CHANGE, pe.STOP, pe.END) and any(c == pe.STITCH for *_, c in first):
            break
        first.append((x / 10, y / 10, k & M))
    sewn = [n for n, rec in enumerate(first) if rec[2] == pe.STITCH]
    moves = [rec for rec in first[sewn[0]:sewn[-1] + 1] if rec[2] != pe.STITCH]
    if expected == WHOLE:
        assert moves == []
    else:
        assert moves, "the render cuts or jumps but the PES file doesn't"


# ---------------------------------------------------------------- the fixes behind them


def test_a_reached_point_lies_inside_the_cover_once_rounded():
    """`_reach` gives a point the join's Zone holds (it allows only 1e-6 mm outside its shape)."""
    zone = shapely.affinity.rotate(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), 37, origin=(5, 5))
    held = dz.Zone(zone).cover
    rng = random.Random(5)
    for _ in range(400):
        a = rng.uniform(0, 2 * math.pi)
        edge = zone.exterior.interpolate(rng.uniform(0, zone.exterior.length))
        p = (edge.x + rng.uniform(0.05, 0.95) * math.cos(a), edge.y + rng.uniform(0.05, 0.95) * math.sin(a))
        q = branch._reach(p, zone)
        if q is not None:
            assert held.covers(Point(q)), (p, q)


def test_a_join_runs_under_two_later_shapes_that_meet():
    """Two later fills sharing an edge hide a join that crosses from one to the other (their covers,
    each 0.3 mm inside its stitching, left a slit there)."""
    left = obj("x", "fill", {"outline": sq(-2, -2, 17, 14)}, thread=BLUE, br=None)
    right = obj("y", "fill", {"outline": sq(15, -2, 17, 14)}, thread=BLUE, br=None)
    r = L.render(lay(fill("a", 0, 0, 10), fill("b", 20, 0, 10), left, right))
    span = between_first_and_last(recs_of(r), {0, 1})
    assert _moves(span) == WHOLE and r.branches[0]["cuts"] == 0
    assert not [w for w in r.warnings if w["code"].startswith("branch_")]


def test_the_branch_takes_the_thread_most_members_sew_in():
    """Recoloring the first member leaves that one out, not the others, and the note names it."""
    shapes = [fill("a", 0, 0, 10, thread=BLUE), fill("b", 10, 0, 10), fill("c", 20, 0, 10)]
    r = L.render(lay(*shapes))
    assert [b["items"] for b in r.branches] == [["b", "c"]]
    (note,) = [w for w in r.warnings if w["code"].startswith("branch_")]
    assert note["code"] == "branch_thread_0" and note["message"].startswith("Fill 1 ")
    # A tie: the thread of the member listed first.
    two = [fill("a", 0, 0, 10, thread=BLUE), fill("b", 10, 0, 10), fill("c", 20, 0, 10, thread=BLUE),
           fill("d", 30, 0, 10, thread=RED)]
    r = L.render(lay(*two))
    codes = sorted(w["code"] for w in r.warnings if w["code"].startswith("branch_"))
    assert codes == ["branch_apart_2", "branch_thread_1", "branch_thread_3"]
