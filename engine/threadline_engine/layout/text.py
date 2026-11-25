"""Lettering turned into color blocks, and into drawn shapes."""

from __future__ import annotations

import json
import math
from typing import Any

import pyembroidery as pe

from .. import fabrics, lettering
from ..digitize import stitches as dz
from ..digitize.paths import flatten
from .model import Block, LayoutError, Rec, Transform
from .objects import DEFAULT_THREAD, _generate_cached


_text_cache: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}


def _letter_ring(o: dict[str, Any]) -> list[list[float]]:
    """A letter part's outline (mm), for its start and end dots to slide along."""
    g = o.get("geometry") or {}
    if o.get("kind") == "fill":
        pts, _ = flatten(g.get("outline") or [], True)
    elif o.get("kind") == "satin" and g.get("rail_a"):
        a, _ = flatten(g.get("rail_a") or [])
        b, _ = flatten(g.get("rail_b") or [])
        pts = a + b[::-1]
    else:
        pts, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
    return [[round(x, 2), round(y, 2)] for x, y in pts]


def text_letters(it: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """A text item's letters as drawn shapes, turned, resized and mirrored with the text (but not
    yet moved to its place: add its x and y), each with where it starts and ends: where you put
    its dots (`letters` on the item, in the text's own unturned frame), or else starting at the
    edge nearest where the letter before ended and ending towards the next letter, so the jumps
    between letters are short."""
    spec = {k: it.get(k) for k in ("text", "font", "size_mm", "spacing_mm", "style", "shape", "monogram")}
    # The font file's date and size are part of the key: an edited stitch font shows at once.
    key = json.dumps({**spec, "font_file": lettering.font_stamp(spec.get("font") or {})}, sort_keys=True)
    hit = _text_cache.get(key)
    if hit is None:
        try:
            hit = lettering.layout_text(spec)
        except (lettering.LetteringError, dz.DigitizeError) as exc:
            raise LayoutError(f"{it.get('name') or 'Text'}: {exc}") from exc
        if len(_text_cache) > 64:
            _text_cache.pop(next(iter(_text_cache)))
        _text_cache[key] = hit
    objects, warnings = hit
    t = Transform.from_dict(it.get("transform"))
    shape_t = Transform(rotate=t.rotate, scale_x=t.scale_x, scale_y=t.scale_y, flip_x=t.flip_x, flip_y=t.flip_y)
    chosen = it.get("letters") or {}
    out = []
    for n, obj in enumerate(objects):
        mine = chosen.get(str(n)) or {}
        own = {k: mine[k] for k in ("start_mm", "end_mm") if dz._start_point(mine.get(k)) is not None}
        o = {**obj, "params": {**(obj.get("params") or {}), **own}} if own else obj
        o = o if shape_t.is_identity() else lettering.turn_with(dz.transform_geometry(o, shape_t, (0.0, 0.0)), shape_t)
        out.append((dict(o), set(own)))  # a copy: the cached letters are never changed
    # Short jumps: each letter ends towards the next (unless its end was chosen).
    for n, (o, own) in enumerate(out):
        if "end_mm" not in own and n + 1 < len(out) and o.get("kind") == "fill":
            ring = _letter_ring(out[n + 1][0])
            if ring:
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                o["params"] = {**(o.get("params") or {}), "end_mm": [round(cx, 3), round(cy, 3)]}
    return [o for o, _ in out], [w for w in warnings]


def _text_block(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[Block, list[str], tuple[float, float], list[dict[str, Any]]]:
    """All letters of a text item as one block in its thread. Letters are drawn shapes, so moving,
    turning or resizing the text regenerates stitches at the right density, and the fabric
    preset adjusts them like any other shape. Records are numbered in sewing order (their `src`),
    so a stop or trim can be inserted in lettering too. Also each letter part: its kind, outline,
    and where it starts and ends (mm), for the dots on the design."""
    letters, warnings = text_letters(it)
    t = Transform.from_dict(it.get("transform"))
    recs: list[Rec] = []
    parts: list[dict[str, Any]] = []
    skipped = 0
    # Letters are stitched at the text's own origin and then moved, so moving or nudging text
    # reuses the cached stitches; turning, mirroring or resizing turns the stitch angle too.
    prev_end: tuple[float, float] | None = None
    for n, letter in enumerate(letters):
        o = fabrics.apply(letter, fabric)
        # Each letter starts at its edge nearest where the one before ended (unless chosen).
        if (prev_end is not None and o.get("kind") == "fill" and dz._start_point((o.get("params") or {}).get("start_mm")) is None
                and "start_mm" not in ((it.get("letters") or {}).get(str(n)) or {})):
            o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
        try:
            mm, _ = _generate_cached(o)
        except dz.DigitizeError:
            skipped += 1  # a speck too small to stitch (e.g. a tiny dot)
            continue
        sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
        if sts:
            prev_end = sts[-1]
            look = "satin" if o.get("kind") == "fill" and it.get("style") == "satin" else o.get("kind")
            parts.append({"index": n, "kind": o.get("kind"), "look": look,
                          "start": [round(sts[0][0] + t.x, 2), round(sts[0][1] + t.y, 2)],
                          "end": [round(sts[-1][0] + t.x, 2), round(sts[-1][1] + t.y, 2)],
                          "ring": [[p[0] + t.x, p[1] + t.y] for p in _letter_ring(o)]})
        part = [[(x + t.x) * 10, (y + t.y) * 10, k, idx, -1] for x, y, k in mm]
        if recs and part:
            last = next((r for r in reversed(recs) if r[2] == pe.STITCH), None)
            first = next((r for r in part if r[2] == pe.STITCH), None)
            if last and first:
                d = math.hypot(first[0] - last[0], first[1] - last[1]) / 10
                if d > dz.TRIM_TRAVEL_MM:
                    recs.append([last[0], last[1], pe.TRIM, idx, -1])
                if d > dz.MIN_STITCH_MM:
                    recs.append([first[0], first[1], pe.JUMP, idx, -1])
        recs.extend(part)
    for n, r in enumerate(recs):
        r[4] = n
    if skipped:
        warnings = [*warnings, f"{skipped} tiny part{'s' if skipped > 1 else ''} of the letters were too small to stitch."]
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    block = Block(dict(thread), recs, [(idx, 0)], dict(thread), digitized=True)
    override = (it.get("threads") or [None])[0]
    if override:
        block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
    return block, warnings, (t.x, t.y), parts


def text_to_shapes(it: dict[str, Any]) -> dict[str, Any]:
    """Lettering broken into drawn shapes, one per letter part, each in place and in the text's
    thread, starting and ending where the letters did: {"objects": [...]}. They can then be
    edited like any shape (their points, stitch type, density, direction and dots)."""
    letters, _ = text_letters(it)
    t = Transform.from_dict(it.get("transform"))
    thread = (it.get("threads") or [None])[0] or it.get("thread") or DEFAULT_THREAD
    chosen = it.get("letters") or {}
    label = it.get("name") or str(it.get("text") or "Text").strip()[:24]
    out = []
    prev_end = None
    for n, o in enumerate(letters):
        # Each starts where the one before ended, as the lettering did (unless its start was chosen).
        if prev_end is not None and o.get("kind") == "fill" and "start_mm" not in (chosen.get(str(n)) or {}):
            o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
        try:
            mm, _ = _generate_cached(o)
            sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
            prev_end = sts[-1] if sts else prev_end
        except dz.DigitizeError:
            continue  # a speck too small to stitch, as in the lettering
        moved = dz.transform_geometry(o, Transform(x=t.x, y=t.y), (0.0, 0.0))
        out.append({"kind": moved["kind"], "geometry": moved["geometry"], "params": moved.get("params") or {},
                    "thread": dict(thread), "name": f"{label} {n + 1}"})
    return {"objects": out}
