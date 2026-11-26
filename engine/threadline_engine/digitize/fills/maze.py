"""Maze fill: one path that winds into the shape and back out between its own turns. Not built
yet."""

from __future__ import annotations

from . import FillPattern, Param, register


def _paths(poly, params, pos):
    from ..stitches import DigitizeError

    raise DigitizeError("not built yet")


register(FillPattern("maze", "open", params={"maze_mm": Param(2.0, 0.8, 6.0, "Path spacing")}, paths=_paths,
                     step_mm2=lambda p: p.value("maze_mm") * min(p.stitch_mm, 3.0), auto_underlay=lambda level: []))
