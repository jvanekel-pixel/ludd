"""Where rows end: feathered edges (P6-A4) and the hand-sewn look's wandering ends (P6-A5), as
tatami()'s "end_shift" hook.

"Left" and "right" are as the rows run at 0 degrees: in the rows' turned frame, x0 is the left
end. A feathered end is pulled in by depth x (0.25 + 0.75 j), j a repeatable value in 0..1 for
that row, so the edge is ragged. The hand-sewn look then moves each end by up to ±0.6 mm.

The shift depends only on (row, x0, x1): a turning fill calls it with distances along a curved
row. The random values come from the row's number (rows.hand.unit), never from where it is.
"""

from __future__ import annotations

from typing import Callable

from . import hand

LEFT_SIDES = ("left", "both")
RIGHT_SIDES = ("right", "both")
KEEP_MM = 1.0  # a row whose moved ends would leave less keeps this much (or all it has)


def end_shift_for(params) -> Callable[[int, float, float], tuple[float, float]] | None:
    """The end_shift hook a fill's settings ask for, or None."""
    feather = params.feather
    h = params.hand_pct / 100
    if feather == "none" and not h:
        return None
    depth = params.feather_mm

    def shift(row: int, x0: float, x1: float) -> tuple[float, float]:
        a, b = x0, x1
        if feather in LEFT_SIDES:
            a += depth * (0.25 + 0.75 * hand.unit(row, 11))
        if feather in RIGHT_SIDES:
            b -= depth * (0.25 + 0.75 * hand.unit(row, 12))
        if h:
            a += hand.FILL_END_MM * h * hand.signed(row, 13)
            b += hand.FILL_END_MM * h * hand.signed(row, 14)
        keep = min(x1 - x0, KEEP_MM)
        if b - a < keep:
            # Ends pulled past each other (a narrow row): the row keeps `keep` of its length,
            # around where the ends met but within the row, so it is never squashed to a single
            # shortest stitch (whose length the last digit of a sine could round either way).
            middle = min(max((a + b) / 2, x0 + keep / 2), x1 - keep / 2)
            a, b = middle - keep / 2, middle + keep / 2
        return a, b

    return shift


def pull_in(params) -> tuple[float, float]:
    """How far in, at most, the left and right row ends are pulled (the feather's depth on each
    feathered side, else 0): where the cross-hatch underlay must stay out of, so it can't show."""
    return (params.feather_mm if params.feather in LEFT_SIDES else 0.0,
            params.feather_mm if params.feather in RIGHT_SIDES else 0.0)
