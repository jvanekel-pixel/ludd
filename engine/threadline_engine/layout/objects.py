"""Drawn shapes (run, satin, fill, applique) turned into color blocks."""

from __future__ import annotations

import json
from typing import Any

from .. import fabrics
from ..digitize import stitches as dz
from .model import Block, LayoutError, Transform


OBJECT_KINDS = ("run", "satin", "fill", "applique")
OBJECT_LABEL = {"run": "Running stitch", "satin": "Satin", "fill": "Fill", "applique": "Applique"}
DEFAULT_THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}

_object_cache: dict[str, tuple[list, list[str]]] = {}
_OBJECT_CACHE_MAX = 4096  # a whole-picture trace can make a thousand shapes or more


def _generate_cached(obj: dict[str, Any]) -> tuple[list, list[str]]:
    """Stitches for an object, cached by its geometry and parameters (unchanged objects are free)."""
    key = json.dumps({k: obj.get(k) for k in ("kind", "geometry", "params")}, sort_keys=True)
    hit = _object_cache.get(key)
    if hit is None:
        hit = dz.generate(obj)
        if len(_object_cache) >= _OBJECT_CACHE_MAX:
            _object_cache.pop(next(iter(_object_cache)))
        _object_cache[key] = hit
    return hit


def _object_blocks(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[list[Block], dict[str, Any], list[str]]:
    """One block for a drawn object. Its transform moves the shape, then stitches are generated,
    so resizing keeps the stitch density right (unlike resizing a stitch file)."""
    label = it.get("name") or f"{OBJECT_LABEL.get(it.get('kind'), 'Object')} {idx + 1}"
    pts = dz.geometry_points(it)
    if not pts:
        raise LayoutError(f"{label} has no points")
    x0, y0, x1, y1 = dz.bounds(pts)
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    t = Transform.from_dict(it.get("transform"))
    obj = it if t.is_identity() else dz.transform_geometry(it, t, center)
    obj = fabrics.apply(obj, fabric)
    try:
        recs_mm, warnings = _generate_cached(obj)
    except dz.DigitizeError as exc:
        raise LayoutError(f"{label}: {exc}") from exc
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    recs = [[x * 10, y * 10, k, idx, i] for i, (x, y, k) in enumerate(recs_mm)]
    block = Block(dict(thread), recs, [(idx, 0)], dict(thread), digitized=True)
    override = (it.get("threads") or [None])[0]
    if override:
        block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
    return [block], {"center": center, "t": t}, warnings
