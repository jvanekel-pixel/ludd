"""Turning fills: a tatami fill with two or more angle lines, whose rows turn to follow each
line where it lies. Tatami hands over here (stitches._fill_part). Not built yet."""

from __future__ import annotations


def takes_over(params) -> bool:
    """Whether a fill is sewn as a turning fill: tatami with two or more angle lines."""
    return params.pattern == "tatami" and len(params.angle_lines) >= 2


def mean_angle(params) -> float:
    """The rows' average direction, degrees: the cross-hatch underlay is sewn across it."""
    return params.angle_deg


def rows(poly, params, start, travel_within=None, end_near=None) -> tuple[list, list[str]]:
    """The top stitching of one piece of a turning fill: (records, warnings). `start`: where the
    needle is; travel stays inside `travel_within`; `end_near`: finish as near this point as the
    rows allow."""
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")
