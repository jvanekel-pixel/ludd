"""The rows engine's Phase 6 settings, each as one of tatami()'s hooks: how neighboring rows'
needle points line up (weave), lines carved into the fill, feathered edges and the hand-sewn look.
Push compensation ("End trim") is not built (see push.py).

Every rows pattern takes its hooks from `hooks()`, and the warnings its settings call for from
`notes()`. Tatami, gradient and wave do through stitches._fill_part; a blend and a turning fill
call them too. A turning fill's curved rows find carved lines with carve.crossings_along().
"""

from __future__ import annotations

from typing import Any

from . import carve, ends, push, weave

__all__ = ["carve", "ends", "hooks", "notes", "push", "weave"]

# Patterns that keep their own needle positions: wave rows copy each other, so they never cross.
OWN_WEAVE = ("wave",)


def hooks(params, angle_deg: float) -> dict[str, Any]:
    """The extra keyword arguments for tatami() that a fill's settings ask for, for rows at
    `angle_deg`: "offsets" (weave), "forced" (carved lines), "end_shift" (feather, hand-sewn look)
    and "random" (the hand-sewn look's). Empty for a plain fill."""
    if params.carve or params.feather != "none" or params.hand_pct:
        from ..stitches import DigitizeError

        raise DigitizeError("Carved lines, feathered edges and the hand-sewn look aren't built yet")
    out: dict[str, Any] = {}
    offsets = None if params.pattern in OWN_WEAVE else weave.offsets_for(params.weave)
    if offsets is not None:
        out["offsets"] = offsets
    return out


def notes(params, angle_deg: float) -> list[str]:
    """Warnings about a fill's row settings, for rows at `angle_deg`."""
    return []
