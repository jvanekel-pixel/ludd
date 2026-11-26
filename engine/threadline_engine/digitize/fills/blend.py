"""Blend: the shape's color fades into a second (and a third or fourth) across the rows. Each
color is its own rows, sewn as its own part in its own thread. Not built yet."""

from __future__ import annotations

from . import FillPattern, Param, register


def _parts(pieces, params):
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")


register(FillPattern("blend", "rows", params={"blend_balance": Param(0.0, -1.0, 1.0, "Balance", unit="")},
                     parts=_parts, rows=lambda p: {}, step_mm2=lambda p: p.spacing_mm * p.stitch_mm,
                     tatami_underlay=False, auto_underlay=lambda level: []))
