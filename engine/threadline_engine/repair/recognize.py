"""Find the fills, satins and runs inside a stitch file's thread runs (P4-C1). Rebuild and the
density limit use it; Phase 13 builds on it."""

from __future__ import annotations

from dataclasses import dataclass

from ..layout.model import LayoutError

Point = tuple[float, float]  # mm, in the frame the run is given in


@dataclass
class Span:
    kind: str            # "fill" | "satin" | "run" | "other"
    start: int           # first stitch index in the run
    end: int             # one past the last
    angle_deg: float | None = None       # fill: row direction, 0..180
    spacing_mm: float | None = None      # fill: between rows; satin: between stitches on one side
    stitch_mm: float | None = None       # fill and run: typical stitch length
    outline: list[Point] | None = None   # fill: left row ends, then right row ends reversed
    rail_a: list[Point] | None = None    # satin: even stitches
    rail_b: list[Point] | None = None    # satin: odd stitches


def recognize(points: list[Point]) -> list[Span]:
    """What one thread run (needle points in sewing order) is made of: fills, satins, runs and,
    for the rest, "other"."""
    raise LayoutError("not built yet")
