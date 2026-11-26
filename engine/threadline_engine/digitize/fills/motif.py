"""Motif fill: rows of a little pattern across the shape. Not built yet."""

from __future__ import annotations

from . import FillPattern, Param, register


def _paths(poly, params, pos):
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")


register(FillPattern("motif", "open",
                     params={"motif_mm": Param(5.0, 1.5, 20.0, "Repeat"),
                             "motif_width_mm": Param(4.0, 0.5, 10.0, "Height"),
                             "motif_gap_mm": Param(0.5, 0.0, 10.0, "Row gap"),
                             "motif_stagger": Param(0.5, 0.0, 1.0, "Shift alternate rows", unit="")},
                     paths=_paths, step_mm2=lambda p: (p.value("motif_width_mm") + p.value("motif_gap_mm")) * 2,
                     auto_underlay=lambda level: []))
