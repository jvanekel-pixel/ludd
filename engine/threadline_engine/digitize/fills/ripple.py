"""Ripple fill: rings spreading from a point, like a drop in water. Not built yet."""

from __future__ import annotations

from . import FillPattern, Param, register


def _paths(poly, params, pos):
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")


register(FillPattern("ripple", "open", params={"ripple_mm": Param(2.0, 0.6, 8.0, "Ring spacing")}, paths=_paths,
                     step_mm2=lambda p: p.value("ripple_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
