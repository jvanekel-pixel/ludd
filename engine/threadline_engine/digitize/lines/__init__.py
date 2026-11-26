"""Running-stitch line styles and motifs: one registry each, so a new one is one file and one
import line here.

A style turns a line's nodes into the needle points, in order; `stitches.running()` looks the
style up and sews the points. Settings a style needs beyond RunParams' own fields go in `params`
(read and range-checked into RunParams.extra). A motif is one repeat: x 0..1 along the line,
y -0.5..0.5 across it.

Imports from `..stitches` go inside function bodies (stitches imports this package).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..fills import Param


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


def carried_unit(value: Any) -> list[tuple[float, float]] | None:
    """A motif of your own that a shape carries (params["motif_unit"]), checked; None when it
    carries none (a built-in motif). Not built yet."""
    if value is None:
        return None
    from ..stitches import DigitizeError

    raise DigitizeError("Your own motifs aren't built yet")


def register_motif(name: str, unit: list[tuple[float, float]]) -> None:
    """Add a motif. A name registered twice raises."""
    if name in MOTIF_UNITS:
        raise ValueError(f"Motif already registered: {name}")
    MOTIF_UNITS[name] = unit


__all__ = ["LineStyle", "MOTIF_UNITS", "Param", "REGISTRY", "carried_unit", "register", "register_motif"]

from . import builtin  # noqa: E402,F401  (registers single, triple, bean, motif and the four motifs)
from . import leaf  # noqa: E402,F401  (the leaf motif)
