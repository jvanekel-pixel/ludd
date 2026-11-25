"""The six fill patterns LUDD 1.0 knew, registered in their original order.

The open patterns' paths are the three branches of the old `stitches._open_paths`, unchanged.
Imports from `..stitches` stay inside the function bodies: stitches imports this package.
"""

from __future__ import annotations

import math

from ..patterns import contour_paths, cross_paths, stipple_paths
from . import FillPattern, register


def _rows_step(p) -> float:
    return p.spacing_mm * min(p.stitch_mm, p.stitch_mm)


def _contour_paths(poly, params, pos):
    warnings: list[str] = []
    paths = contour_paths(poly, params.spacing_mm, params.stitch_mm, pos)
    return paths, warnings


def _stipple_paths(poly, params, pos):
    import shapely
    from shapely.geometry import LineString

    from ..stitches import _stipple_seed

    warnings: list[str] = []
    paths = stipple_paths(poly, params.stipple_mm, min(params.stitch_mm, 2.5), _stipple_seed(poly), pos)
    if paths:
        reach = shapely.union_all([LineString(p) for p in paths if len(p) > 1]).buffer(params.stipple_mm)
        bare = poly.difference(reach).area
        if bare > 4 and bare > 0.1 * poly.area:
            warnings.append(f"Parts of this shape are too narrow for {params.stipple_mm:g} mm stipple loops, so they "
                            "are left empty. Make the loops smaller.")
    return paths, warnings


def _cross_paths(poly, params, pos):
    from ..stitches import LONG_STITCH_MM, _subdivide

    warnings: list[str] = []
    paths = cross_paths(poly, params.cross_mm)
    if params.cross_mm * math.sqrt(2) > LONG_STITCH_MM:
        # Diagonals of big squares would be loose stitches: give each a needle point midway.
        paths = [_subdivide(p, LONG_STITCH_MM) for p in paths]
    return paths, warnings


register(FillPattern("tatami", "rows", rows=lambda p: {}, step_mm2=_rows_step))
register(FillPattern("gradient", "rows", rows=lambda p: {"sparse_to": p.gradient_to_mm}, step_mm2=_rows_step,
                     tatami_underlay=False))
register(FillPattern("wave", "rows", rows=lambda p: {"wave": (p.wave_mm, p.wave_length_mm)}, step_mm2=_rows_step))
register(FillPattern("contour", "open", paths=_contour_paths, step_mm2=_rows_step))
register(FillPattern("stipple", "open", paths=_stipple_paths, step_mm2=lambda p: p.spacing_mm * min(p.stitch_mm, 2.5)))
register(FillPattern("cross", "open", paths=_cross_paths, step_mm2=lambda p: p.cross_mm ** 2 / 4))
