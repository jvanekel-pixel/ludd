"""Fill patterns: one registry, so a new pattern is one file and one import line here.

A pattern is either "rows" (tatami rows, shaped by extra keyword arguments for `tatami()`) or
"open" (lines laid over the shape, sewn in order). Settings the pattern needs beyond FillParams'
own fields go in `params`: FillParams.from_dict reads and range-checks them into `extra`, and
`FillParams.value(key)` reads either kind.

A new pattern: `digitize/fills/<name>.py` that calls `register(...)`, plus one import line at the
bottom of this file. Imports from `..stitches` go inside function bodies (stitches imports this).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Param:
    default: float
    lo: float
    hi: float
    label: str  # for the error text: "<label> must be between <lo> and <hi> mm"


@dataclass(frozen=True)
class FillPattern:
    name: str
    kind: str  # "rows" (tatami rows) | "open" (lines over the shape)
    params: dict[str, Param] = field(default_factory=dict)  # settings beyond FillParams' own fields
    paths: Callable | None = None  # open: (poly, params, pos) -> (list[list[Point]], list[str])
    rows: Callable | None = None  # rows: (params) -> extra keyword arguments for tatami()
    step_mm2: Callable | None = None  # (params) -> fabric area per stitch, for the MAX_STITCHES guard
    tatami_underlay: bool = True  # may it have the cross-hatch underlay?
    auto_underlay: Callable | None = None  # (level) -> list[str]; None = today's rule


REGISTRY: dict[str, FillPattern] = {}


def register(p: FillPattern) -> None:
    """Add a pattern. A name registered twice raises."""
    if p.name in REGISTRY:
        raise ValueError(f"Fill pattern already registered: {p.name}")
    REGISTRY[p.name] = p


def get(name: str) -> FillPattern:
    """The pattern called `name`; an unknown one is a DigitizeError, worded as it always was."""
    p = REGISTRY.get(name)
    if p is None:
        from ..stitches import DigitizeError

        raise DigitizeError(f"Unknown fill pattern: {name}")
    return p


from . import builtin  # noqa: E402,F401  (registers the six, in today's order)
from . import spiral  # noqa: E402,F401
