"""Where rows end: feathered edges and the hand-sewn look's wandering ends, as tatami()'s
"end_shift" hook. Not built yet."""

from __future__ import annotations

from typing import Callable


def end_shift_for(params) -> Callable[[int, float, float], tuple[float, float]] | None:
    """The end_shift hook a fill's settings ask for, or None."""
    if params.feather == "none" and not params.hand_pct:
        return None
    from ..stitches import DigitizeError

    raise DigitizeError("Feathered edges and the hand-sewn look aren't built yet")
