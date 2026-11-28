"""RPC methods. Shape tools: offset, split, cut out, satin fill, merge, start and end dots."""

from __future__ import annotations

from .registry import dispatcher


@dispatcher.method("shape.offset")
def shape_offset(layout: dict, ids: list, distance_mm: float, spacing: float = 3.0, holes: bool = False) -> dict:
    from .. import shapeops

    return shapeops.offset(layout, ids, distance_mm, spacing, holes)


@dispatcher.method("shape.split")
def shape_split(obj: dict, a: list, b: list, spacing: float = 3.0) -> dict:
    from .. import shapeops

    return shapeops.split(obj, tuple(a), tuple(b), spacing)


@dispatcher.method("shape.cut_out")
def shape_cut_out(target: dict, cutters: list, spacing: float = 3.0) -> dict:
    from .. import shapeops

    return shapeops.cut_out(target, cutters, spacing)


@dispatcher.method("shape.satin_fill")
def shape_satin_fill(outline: list, way: int = 0, tips: list | None = None) -> dict:
    """Fill a closed shape with one satin that turns with it (its two sides, split at its tips;
    `tips`: the two tips chosen by hand)."""
    from ..digitize.satinfill import satin_fill

    return satin_fill(outline, way, tips)


@dispatcher.method("shape.merge")
def shape_merge(objs: list, spacing: float = 3.0) -> dict:
    from .. import shapeops

    return shapeops.merge(objs, spacing)


@dispatcher.method("shape.set_end")
def shape_set_end(obj: dict, which: str, at: list) -> dict:
    """Drag a drawn piece's start (green dot) or end (red dot) to `at`: the piece, changed to suit."""
    from ..jumps import set_end

    return set_end(obj, which, at)


@dispatcher.method("shape.buttonhole")
def shape_buttonhole(length_mm: float = 16, width_mm: float = 5, style: str = "bar", cut_gap_mm: float = 1.0,
                     angle_deg: float = 0, at: list | None = None) -> dict:
    """A buttonhole as ordinary shapes, centered on `at` (mm): {objects, warnings}."""
    from ..digitize.smallobjects import buttonhole

    return buttonhole(length_mm, width_mm, style, cut_gap_mm, angle_deg, at)


@dispatcher.method("shape.eyelet")
def shape_eyelet(hole_mm: float = 4, ring_mm: float = 1.6, at: list | None = None) -> dict:
    """An eyelet as ordinary shapes, centered on `at` (mm): {objects, warnings}."""
    from ..digitize.smallobjects import eyelet

    return eyelet(hole_mm, ring_mm, at)
