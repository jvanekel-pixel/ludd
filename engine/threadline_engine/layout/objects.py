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

_object_cache: dict[str, list[tuple[list, list[str], int]]] = {}  # dz.generate_parts, by shape
_OBJECT_CACHE_MAX = 4096  # a whole-picture trace can make a thousand shapes or more


def _generate_cached(obj: dict[str, Any]) -> tuple[list, list[str]]:
    """An object's stitches as one list, and its warnings (lettering's letters are one thread)."""
    return dz.one_run(_generate_parts_cached(obj))


def _generate_parts_cached(obj: dict[str, Any]) -> list[tuple[list, list[str], int]]:
    """Stitches for an object, one part per thread, cached by its geometry and parameters
    (unchanged objects are free)."""
    key = json.dumps({k: obj.get(k) for k in ("kind", "geometry", "params")}, sort_keys=True)
    hit = _object_cache.get(key)
    if hit is None:
        hit = dz.generate_parts(obj)
        if len(_object_cache) >= _OBJECT_CACHE_MAX:
            _object_cache.pop(next(iter(_object_cache)))
        _object_cache[key] = hit
    return hit


def _object_blocks(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[list[Block], dict[str, Any], list[str]]:
    """A block for each thread a drawn object sews in (one, or a blend's colors). Its transform
    moves the shape, then stitches are generated, so resizing keeps the stitch density right
    (unlike resizing a stitch file). A part's block is sewn in its slot's thread (slot 0 the
    object's own, slot k params["blend"][k - 1]), or in threads[k] on the item if that's set;
    its source is (item, slot), so Order & colors recolors each part."""
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
        parts = _generate_parts_cached(obj)
    except dz.DigitizeError as exc:
        raise LayoutError(f"{label}: {exc}") from exc
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    others = (obj.get("params") or {}).get("blend")
    overrides = it.get("threads") or []
    blocks: list[Block] = []
    warnings: list[str] = []
    n = 0  # records are numbered through all of the object's parts
    for recs_mm, said, slot in parts:
        own = thread if slot == 0 else {**DEFAULT_THREAD, **_other_color(others, slot)}
        recs = [[x * 10, y * 10, k, idx, n + i] for i, (x, y, k) in enumerate(recs_mm)]
        n += len(recs_mm)
        block = Block(dict(own), recs, [(idx, slot)], dict(own), digitized=True)
        override = overrides[slot] if slot < len(overrides) else None
        if override:
            block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
        blocks.append(block)
        warnings += [w for w in said if w not in warnings]
    return blocks, {"center": center, "t": t}, warnings


def _other_color(others: Any, slot: int) -> dict[str, Any]:
    """The thread of a part in slot 1 or more: the (slot)th of a blend's other colors."""
    t = others[slot - 1] if isinstance(others, list) and 0 < slot <= len(others) else None
    return t if isinstance(t, dict) else {}
