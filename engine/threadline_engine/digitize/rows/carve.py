"""Carved lines: lines drawn over a fill that every row drops a needle on, so they show as
grooves. A fill's lines (geometry.carve) come flattened to polylines in mm, in the design's frame
(FillParams.carve). Not built yet."""

from __future__ import annotations

from typing import Callable, Sequence

from ..paths import Point

KEEP_FROM_END_MM = 0.4  # a crossing closer to a row's end than this is left to the end
NOT_BUILT = "Carved lines aren't built yet"


def forced_for_rows(lines: Sequence[Sequence[Point]], angle_deg: float) -> Callable[..., list[float]]:
    """tatami()'s "forced" hook for rows at `angle_deg`: (y, x0, x1, bend=None) -> where the row
    (turned frame) crosses a carved line, at least KEEP_FROM_END_MM inside its ends. `bend`:
    x -> the row's height there, for a rippled (wave) row."""
    from ..stitches import DigitizeError

    raise DigitizeError(NOT_BUILT)


def crossings_along(lines: Sequence[Sequence[Point]], path: Sequence[Point]) -> list[float]:
    """Where a curved row (a turning fill's, as points in mm) crosses a carved line: distances
    along it, at least KEEP_FROM_END_MM from its ends, in order."""
    if not lines:
        return []
    from ..stitches import DigitizeError

    raise DigitizeError(NOT_BUILT)
