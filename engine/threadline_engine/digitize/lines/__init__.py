"""Running-stitch line styles and motifs: one registry each, so a new one is one file and one
import line here.

A style turns a line's nodes into the needle points, in order; `stitches.running()` looks the
style up and sews the points. Settings a style needs beyond RunParams' own fields go in `params`
(read and range-checked into RunParams.extra). A motif is one repeat: x 0..1 along the line,
y -0.5..0.5 across it. A motif of your own is carried by the shape that uses it
(params["motif_unit"]); carried_unit() checks it and sewn_unit() sizes it.

Imports from `..stitches` go inside function bodies (stitches imports this package).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ..fills import Param

MIN_UNIT_POINTS, MAX_UNIT_POINTS = 2, 200
MAX_UNIT_VALUE = 1000.0  # far bigger than any motif: a typing slip or a damaged file
FLAT_SPAN = 1e-4  # a motif that goes no further than this across its line (as a share of one repeat) is flat
MOST_ACROSS = 10.0  # a hand-edited motif nowhere near its line stays within this many widths of it
SEWN_WITHIN_MM = 0.1  # a motif of your own is sewn this near its shape, with no more points than that takes
MAX_LINE_STITCHES = 60_000  # a motif line asking for more is refused (a whole design is usually 5,000 to 30,000)


@dataclass(frozen=True)
class LineStyle:
    name: str
    params: dict[str, Param] = field(default_factory=dict)  # Param from digitize.fills
    points: Callable = None  # (nodes, params, closed, start) -> list[Point]: the needle points, in order


REGISTRY: dict[str, LineStyle] = {}
MOTIF_UNITS: dict[str, list[tuple[float, float]]] = {}  # one repeat: x 0..1 along the line, y -0.5..0.5 across


def register(s: LineStyle) -> None:
    """Add a line style. A name registered twice raises."""
    if s.name in REGISTRY:
        raise ValueError(f"Line style already registered: {s.name}")
    REGISTRY[s.name] = s


def motif_stitches(unit: Sequence[tuple[float, float]], repeats: float, repeat_mm: float, width_mm: float,
                   stitch_mm: float) -> float:
    """About how many stitches `repeats` of a motif take, laid straight: every corner is a needle
    point, long sides are split to the stitch length, and tiny moves are merged."""
    from ..stitches import MIN_STITCH_MM

    length = sum(math.hypot((u1 - u0) * repeat_mm, (v1 - v0) * width_mm) for (u0, v0), (u1, v1) in zip(unit, unit[1:]))
    return repeats * min(max(len(unit) - 1, length / stitch_mm), length / MIN_STITCH_MM + 1)


def carried_unit(value: Any) -> list[tuple[float, float]] | None:
    """A motif of your own that a shape carries (params["motif_unit"]), checked; None when it
    carries none (a built-in motif). It is 2 to 200 points, each two ordinary numbers."""
    if value is None:
        return None
    from ..stitches import DigitizeError

    def refused(why: str) -> DigitizeError:
        return DigitizeError(f"This motif can't be used: {why}.")

    if not isinstance(value, (list, tuple)):
        raise refused("it isn't a list of points")
    if not MIN_UNIT_POINTS <= len(value) <= MAX_UNIT_POINTS:
        raise refused(f"it has {len(value)} points, and a motif has {MIN_UNIT_POINTS} to {MAX_UNIT_POINTS}")
    unit: list[tuple[float, float]] = []
    for point in value:
        if not (isinstance(point, (list, tuple)) and len(point) == 2
                and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in point)):
            raise refused("it has a point that isn't two numbers")
        if any(abs(c) > MAX_UNIT_VALUE for c in point):
            raise refused("it has a point far bigger than any motif")
        if not all(math.isfinite(c) for c in point):
            raise refused("it has a point that isn't two numbers")
        unit.append((float(point[0]), float(point[1])))
    return unit


def sewn_unit(unit: Sequence[tuple[float, float]] | None, repeat_mm: float,
              width_mm: float) -> list[tuple[float, float]] | None:
    """A motif of your own as motif_points() sews it at this Repeat and Width; None (a built-in
    motif) stays None. This is the one place these rules live: motif lines and motif fills both
    sew through it.

    - motif_points sews across as v x width, and built-in motifs are about 1 across. One of your
      own keeps the proportions you drew (the same scale along and across), so its v is divided
      by how far across it goes (its biggest v less its smallest): then the Width setting (a motif
      fill's Height) is how wide it really sews, as for the built-ins. A flat one sews flat.
    - A curve you drew is saved as many points close together, which would sew as tiny stitches
      that pile up: points that make no difference at this size are left out (_thinned)."""
    if unit is None:
        return None
    vs = [v for _, v in unit]
    span = max(vs) - min(vs)
    scale = 1 / span if span > FLAT_SPAN else 0.0
    return _thinned([(u, min(max(v * scale, -MOST_ACROSS), MOST_ACROSS)) for u, v in unit], repeat_mm, width_mm)


def _thinned(unit: list[tuple[float, float]], repeat_mm: float, width_mm: float) -> list[tuple[float, float]]:
    """The unit without the points it can do without, staying within SEWN_WITHIN_MM of its shape
    as sewn (measured in mm); its first and last points stay."""
    from ..fills.motif import kept_points

    at = [(u * repeat_mm, v * width_mm) for u, v in unit]
    return [unit[i] for i in kept_points(at, SEWN_WITHIN_MM)]


def register_motif(name: str, unit: list[tuple[float, float]]) -> None:
    """Add a motif. A name registered twice raises."""
    if name in MOTIF_UNITS:
        raise ValueError(f"Motif already registered: {name}")
    MOTIF_UNITS[name] = unit


__all__ = ["LineStyle", "MOTIF_UNITS", "Param", "REGISTRY", "carried_unit", "register", "register_motif", "sewn_unit"]

from . import builtin  # noqa: E402,F401  (registers single, triple, bean, motif and the four motifs)
from . import leaf  # noqa: E402,F401  (the leaf motif)
