"""The rows engine's Phase 6 settings, each as one of tatami()'s hooks: how neighboring rows'
needle points line up (weave), lines carved into the fill, feathered edges and the hand-sewn look.
Push compensation ("End trim") is not built (see push.py).

Every rows pattern takes its hooks from `hooks()`, and the warnings its settings call for from
`notes()`. Tatami, gradient and wave do through stitches._fill_part; a blend and a turning fill
call them too. A turning fill's curved rows find carved lines with carve.crossings_along().
"""

from __future__ import annotations

from typing import Any

from . import carve, ends, hand, push, weave

__all__ = ["carve", "ends", "hand", "hooks", "in_use", "notes", "push", "weave"]

# Patterns that keep their own needle positions: wave rows copy each other, so they never cross.
OWN_WEAVE = ("wave",)


def hooks(params, angle_deg: float) -> dict[str, Any]:
    """The extra keyword arguments for tatami() that a fill's settings ask for, for rows at
    `angle_deg`: "offsets" (weave), "forced" (carved lines), "end_shift" (feather, hand-sewn look)
    and "random" (the hand-sewn look's). Empty for a plain fill."""
    out: dict[str, Any] = {}
    offsets = None if params.pattern in OWN_WEAVE else weave.offsets_for(params.weave)
    if offsets is not None:
        out["offsets"] = offsets
    if params.carve:
        out["forced"] = carve.forced_for_rows(params.carve, angle_deg)
    end_shift = ends.end_shift_for(params)
    if end_shift is not None:
        out["end_shift"] = end_shift
    if params.hand_pct:
        # The needle points move as Random 50% does at 100%; a higher Random of the fill's own stays.
        out["random"] = max(params.random_pct / 100, hand.FILL_RANDOM * params.hand_pct / 100)
    return out


def in_use(params) -> bool:
    """Whether a fill uses any of the rows settings. Such a fill's cross-hatch underlay is sewn
    steadily too (its equally good choices settled to a millionth of a mm): a fill without them
    keeps exactly the stitches it always had."""
    return bool(params.weave != "standard" or params.carve or params.feather != "none" or params.hand_pct)


def notes(params, angle_deg: float) -> list[str]:
    """Warnings about a fill's row settings, for rows at `angle_deg`."""
    if params.carve and carve.along_the_rows(params.carve, angle_deg):
        return [carve.ALONG_WARNING]
    return []
