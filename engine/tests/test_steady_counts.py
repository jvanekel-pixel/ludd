"""Counts taken from a ratio of lengths come out the same on every computer.

Another computer's maths library can work a length out one last digit longer or shorter. A count
made with round, ceil or floor then lands either side of a whole number (or of a half) and can
differ by one, which moves stitches. So each ratio is rounded to a millionth first: a ratio that
close to a whole number (or half) counts as it. One test for each place in the Phase 7 code, found
by the second Phase 7 audit (a 38 mm line with a 4 mm motif, exactly nine and a half repeats) and
the sweep after it. Each test fails without the rounding.
"""

import math
from types import SimpleNamespace

import numpy as np
import pytest
from shapely.geometry import box

from threadline_engine import jumps
from threadline_engine.digitize import patterns
from threadline_engine.digitize.fills import blackwork, lattice
from threadline_engine.digitize.lines import builtin, craft
from threadline_engine.layout import branch


def last_digit(x: float) -> list[float]:
    """x, and x one last digit shorter and longer."""
    return [math.nextafter(x, -math.inf), x, math.nextafter(x, math.inf)]


@pytest.mark.parametrize("length", last_digit(38.0), ids=["shorter", "exact", "longer"])
def test_a_motif_line_half_a_repeat_over_takes_the_same_repeats(length, monkeypatch):
    nodes = [[0, 0, "c"], [length, 0, "l"]]
    points = patterns.motif_points(nodes, "blanket", 4.0, 3.0)
    exact = patterns.motif_points([[0, 0, "c"], [38.0, 0, "l"]], "blanket", 4.0, 3.0)
    assert len(points) == len(exact) and patterns.motif_repeats(length, 4.0) == 10
    # The count that refuses a line with too many stitches before laying it is the same one.
    counted = []
    real = builtin.motif_stitches
    monkeypatch.setattr(builtin, "motif_stitches", lambda shape, n, *a: counted.append(n) or real(shape, n, *a))
    params = SimpleNamespace(motif="blanket", motif_mm=4.0, motif_width_mm=3.0)
    builtin._refuse_too_many(nodes, params, False, None, 2.5)
    assert counted == [10]


def test_a_craft_lines_stitches_count_a_ratio_within_a_millionth_as_whole():
    # At most 5 mm apart: two parts for a stretch a hair over 10 mm.
    assert craft._parts(10 * (1 + 2e-9), 5.0, 0.31) == 2
    # None under 0.31 mm: three parts for a stretch a hair under three times it.
    assert craft._parts(0.93 * (1 - 2e-9), 0.1, 0.31) == 3


def test_a_blackwork_lattice_covers_the_same_cells_a_last_digit_either_way():
    assert [lattice._cells(span, 5.0) for span in last_digit(30.0)] == [range(-4, 5)] * 3


def test_a_blackwork_stretch_takes_the_same_stitches_for_a_ratio_within_a_millionth():
    nodes = [(0.0, 0.0), (5.0 * (1 + 2e-9), 0.0)]
    stretches = lattice._Stretches(nodes, [(0.0, 0.0), (0.0, nodes[1][0])], 2.5)
    assert len(stretches(0, 1)) == 2


def test_the_big_blackwork_estimate_counts_a_ratio_within_a_millionth_as_whole():
    def params(cell):
        return SimpleNamespace(value=lambda name: cell, stitch_mm=2.5, blackwork_lattice="grid")

    square = box(0, 0, 100, 100)
    assert blackwork.estimate(square, params(5.0 * (1 + 2e-9))) == pytest.approx(
        blackwork.estimate(square, params(5.0)), rel=1e-6)


def test_a_branch_tries_the_same_points_along_an_edge_a_last_digit_either_way():
    tried = [len(branch._sampled([(0.0, 0.0), (length, 0.0)], False)) for length in last_digit(10.0)]
    assert len(set(tried)) == 1, tried


def test_the_turn_check_compares_the_same_points_a_last_digit_either_way():
    parts = [jumps._sample_parts(np.array([[(0.0, 0.0), (length, 0.0)]])).tolist() for length in last_digit(0.5)]
    assert parts == [[2]] * 3, parts
