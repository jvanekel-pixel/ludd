"""Weave: how the needle points of neighboring rows line up. Each is tatami()'s "offsets" hook:
row number -> the shift of that row's needle grid, as a fraction of a stitch."""

from __future__ import annotations

from typing import Callable

# The fractions repeat row after row. Standard (0, 1/3, 2/3) is what tatami has always done.
SEQUENCES: dict[str, tuple[float, ...]] = {
    "brick": (0.0, 1 / 2),
    "twill": (0.0, 1 / 4, 1 / 2, 3 / 4),
    "smooth": (0.0, 2 / 5, 4 / 5, 1 / 5, 3 / 5),
}
WEAVES = ("standard", "brick", "twill", "smooth", "random")


def _scatter(row: int) -> float:
    """A repeatable pseudo-random fraction for a row, the same on every computer (whole-number
    arithmetic, no sines)."""
    v = (row * 2654435761 + 0x9E3779B9) & 0xFFFFFFFF
    v ^= v >> 16
    v = (v * 0x45D9F3B) & 0xFFFFFFFF
    v ^= v >> 16
    return v / 2**32


def offsets_for(weave: str) -> Callable[[int], float] | None:
    """The offsets hook for a weave; None for the standard one (tatami's own rule)."""
    if weave == "standard":
        return None
    if weave == "random":
        return _scatter
    seq = SEQUENCES[weave]
    return lambda row: seq[row % len(seq)]
