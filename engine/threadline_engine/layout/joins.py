"""Same-thread joins, hidden travel under later stitching, footprints and the color sort."""

from __future__ import annotations

import hashlib
import math
from typing import Any

import pyembroidery as pe
from shapely.errors import GEOSException
from shapely.geometry import LineString, MultiLineString
from shapely.validation import make_valid

from ..digitize import stitches as dz
from .model import Block, _stitch_bounds, _thread_key


def _join(a: Block, b: Block) -> Block:
    """Two blocks of the same thread sewn back to back: the color change between them was a cut, keep it as a trim."""
    recs = list(a.recs)
    if recs and b.recs:
        last = recs[-1]
        recs.append([last[0], last[1], pe.TRIM, last[3], -1])
    recs.extend(b.recs)
    return Block(a.thread, recs, a.sources + b.sources, a.original)


def _merge_same(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        if out and _thread_key(out[-1].thread) == _thread_key(b.thread):
            out[-1] = _join(out[-1], b)
        else:
            out.append(b)
    return out


def _join_objects(a: Block, b: Block, is_hidden=None) -> Block:
    """Consecutive drawn objects in the same thread sew without a color change. If the way from
    one to the next lies under stitching that's sewn later (`is_hidden(path)`), the needle travels
    there in small running stitches, covered later: no jump, no trim. Otherwise a short move is a
    jump and a long one is trimmed so no thread is left across the fabric."""
    recs = list(a.recs)
    sa = next((r for r in reversed(a.recs) if r[2] == pe.STITCH), None)
    sb = next((r for r in b.recs if r[2] == pe.STITCH), None)
    if sa and sb:
        d = math.hypot(sb[0] - sa[0], sb[1] - sa[1]) / 10
        path = LineString([(sa[0] / 10, sa[1] / 10), (sb[0] / 10, sb[1] / 10)])
        if d > dz.MIN_STITCH_MM and is_hidden is not None and is_hidden(path):
            n = max(1, math.ceil(d / dz.TRAVEL_STITCH_MM))
            for k in range(1, n):
                t = k / n
                # Belongs to neither shape (item -1, like basting): a shape's own stitches stay its
                # own, for its start and end marks, its outline and the shortest order.
                recs.append([sa[0] + (sb[0] - sa[0]) * t, sa[1] + (sb[1] - sa[1]) * t, pe.STITCH, -1, -1])
        else:
            if d > dz.TRIM_TRAVEL_MM:
                recs.append([sa[0], sa[1], pe.TRIM, sa[3], -1])
            if d > dz.MIN_STITCH_MM:
                recs.append([sb[0], sb[1], pe.JUMP, sb[3], -1])
    recs.extend(b.recs)
    return Block(a.thread, recs, a.sources + b.sources, a.original, True)


_cover_cache: dict[bytes, Any] = {}
COVER_CLOSE_MM = 0.35  # half the widest gap between rows that still counts as covered


def _cover(block: Block):
    """Where a block's stitches will cover the fabric: its stitch lines thickened so neighbouring
    rows join, then shrunk back (a little further, to stay well inside). Cached by the stitches;
    None when there's nothing usable (a single line covers nothing; a broken outline is skipped)."""
    pts = [(r[0], r[1]) for r in block.recs if r[2] == pe.STITCH]
    if len(pts) < 3:
        return None
    key = hashlib.sha1(str(pts).encode()).digest()
    if key in _cover_cache:
        return _cover_cache[key]
    lines = []
    run: list[tuple[float, float]] = []
    for r in block.recs:
        if r[2] == pe.STITCH:
            run.append((r[0] / 10, r[1] / 10))
            continue
        if len(run) > 1:
            lines.append(run)
        run = []
    if len(run) > 1:
        lines.append(run)
    cover = None
    try:
        if lines:
            # Rows up to 0.7 mm apart join (a thread is about 0.4 mm wide, so nothing shows between
            # them); wider gaps and holes stay open, so travel there isn't counted as hidden.
            c = MultiLineString(lines).simplify(0.1).buffer(COVER_CLOSE_MM, quad_segs=1).buffer(-COVER_CLOSE_MM - 0.3, quad_segs=1)
            if not c.is_valid:
                c = make_valid(c)
            if not c.is_empty and c.area > 0.5:
                cover = c
    except GEOSException:
        cover = None
    if len(_cover_cache) > 2048:
        _cover_cache.pop(next(iter(_cover_cache)))
    _cover_cache[key] = cover
    return cover


def _join_same_thread_objects(blocks: list[Block], travel_under: bool = False) -> list[Block]:
    """Join consecutive drawn objects in one thread (in their final sewing order). With
    `travel_under`, a move lying under stitching sewn later becomes hidden travel."""
    joinable = any(
        a.digitized and b.digitized and _thread_key(a.thread) == _thread_key(b.thread) for a, b in zip(blocks, blocks[1:])
    )
    covers: dict[int, Any] = {}

    def cover(j: int):
        if j not in covers:
            covers[j] = _cover(blocks[j]) if blocks[j].digitized else None
        return covers[j]

    def hidden_from(i: int):
        def is_hidden(path: LineString) -> bool:
            # Covered if, taking away what each later block covers, nothing of the way is left.
            left = path
            try:
                for j in range(i, len(blocks)):
                    c = cover(j)
                    if c is None:
                        continue
                    left = left.difference(c)
                    if left.is_empty or left.length < 0.05:
                        return True
            except GEOSException:
                return False
            return False

        return is_hidden

    out: list[Block] = []
    for i, b in enumerate(blocks):
        prev = out[-1] if out else None
        if prev and prev.digitized and b.digitized and _thread_key(prev.thread) == _thread_key(b.thread):
            out[-1] = _join_objects(prev, b, hidden_from(i) if travel_under and joinable else None)
        else:
            out.append(b)
    return out


_footprint_cache: dict[bytes, Any] = {}


def _footprint(block: Block):
    """Where a block's thread lies (its stitch lines, a thread wide). Cached by the stitches."""
    pts = [(r[0], r[1]) for r in block.recs if r[2] == pe.STITCH]
    key = hashlib.sha1(str(pts).encode()).digest()
    if key in _footprint_cache:
        return _footprint_cache[key]
    lines, run = [], []
    for r in block.recs:
        if r[2] == pe.STITCH:
            run.append((r[0] / 10, r[1] / 10))
            continue
        if run:
            lines.append(run if len(run) > 1 else run * 2)
        run = []
    if run:
        lines.append(run if len(run) > 1 else run * 2)
    try:
        fp = MultiLineString(lines).simplify(0.05).buffer(0.2, quad_segs=1) if lines else None
    except GEOSException:
        fp = None
    if len(_footprint_cache) > 2048:
        _footprint_cache.pop(next(iter(_footprint_cache)))
    _footprint_cache[key] = fp
    return fp


def _blocks_overlap(a: Block, b: Block) -> bool:
    ba, bb = _stitch_bounds(a.recs), _stitch_bounds(b.recs)
    if not ba or not bb or ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
        return False
    fa, fb = _footprint(a), _footprint(b)
    if fa is None or fb is None:
        return True  # can't tell: assume they do, which keeps the order
    try:
        return fa.intersects(fb)
    except GEOSException:
        return True


def _sort_by_thread(blocks: list[Block]) -> tuple[list[Block], int]:
    """Blocks grouped by thread, in order of first appearance (stable within a thread). A block only
    moves forward to join its thread if nothing it would move ahead of overlaps it: otherwise that
    shape would end up on top of it. Returns the blocks and how many stayed apart for that reason.
    Only reorders: joining happens afterwards, on the final order."""
    out: list[Block] = []
    held = 0
    for b in blocks:
        k = _thread_key(b.thread)
        last = max((i for i, o in enumerate(out) if _thread_key(o.thread) == k), default=-1)
        if last < 0 or last == len(out) - 1:
            out.append(b)
        elif any(_blocks_overlap(b, o) for o in out[last + 1:]):
            out.append(b)
            held += 1
        else:
            out.insert(last + 1, b)
    return out, held
