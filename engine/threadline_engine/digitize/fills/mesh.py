"""Mesh fill: a net of two sets of lines. Not built yet."""

from __future__ import annotations

from . import FillPattern, Param, register


def _paths(poly, params, pos):
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")


register(FillPattern("mesh", "open",
                     params={"mesh_mm": Param(3.0, 1.0, 10.0, "Cell size"),
                             "mesh_cross_deg": Param(90.0, 45.0, 90.0, "Crossing angle", unit="°")},
                     paths=_paths, step_mm2=lambda p: p.value("mesh_mm") * min(p.stitch_mm, 3.0) / 2,
                     auto_underlay=lambda level: []))
