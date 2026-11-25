"""Placed stitch files: loading (cached), color blocks, per-item edits and the placement transform."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pyembroidery as pe

from .. import design, kept
from .model import M, Block, LayoutError, Rec, Transform, _index, _mm, _record_count, _thread_dict


_cache: dict[str, tuple[tuple, pe.EmbPattern]] = {}
_CACHE_MAX = 32  # stitch files kept in memory (the least recently used go first)


def _load(path: str, as_added: bool = False) -> pe.EmbPattern:
    """Load a stitch file, cached until it changes on disk (its time, size or the copy read).
    `as_added`: the item has edits, so read the private copy (what was on screen when they were
    made), never a newer file on disk (QA2 P3)."""
    p = Path(kept.readable(path, as_added))
    try:
        st = p.stat()
    except OSError as exc:
        raise LayoutError(f"File not found: {Path(path).name}. It may have been moved or deleted.") from exc
    stamp = (st.st_mtime_ns, st.st_size, str(p))
    hit = _cache.pop(path, None)
    if hit and hit[0] == stamp:
        _cache[path] = hit  # most recently used last
        return hit[1]
    pattern = design.load(p)
    if str(p) == str(path):
        # Keep a private copy, so the design survives the original being moved or deleted.
        try:
            kept.keep(path, p.read_bytes())
        except OSError:
            pass
    _cache[path] = (stamp, pattern)
    while len(_cache) > _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    return pattern


def _split_blocks(pattern: pe.EmbPattern, item: int) -> list[Block]:
    """Source records grouped into color blocks. Color changes become block boundaries."""
    blocks: list[Block] = []
    cur: list[Rec] = []
    for i, (x, y, c) in enumerate(pattern.stitches):
        k = c & M
        if k in (pe.COLOR_CHANGE, pe.NEEDLE_SET):
            blocks.append(Block({}, cur))
            cur = []
        elif k == pe.END:
            break
        elif k in (pe.STITCH, pe.JUMP, pe.TRIM, pe.STOP):
            cur.append([x, y, k, item, i])
        # other commands (sequins, speed) are dropped
    blocks.append(Block({}, cur))
    for b, blk in enumerate(blocks):
        t = pattern.threadlist[b] if b < len(pattern.threadlist) else None
        blk.thread = _thread_dict(t)
        blk.original = dict(blk.thread)
        blk.sources = [(item, b)]
    return blocks


def _apply_ops(blocks: list[Block], ops: list[dict[str, Any]], jt_mm: float | None = None,
               notes: list[str] | None = None, generated: bool = False) -> list[Block]:
    """Edits on one item: colours and stitches deleted, stops and trims inserted, jumps trimmed.
    Damaged ops (missing or non-numeric fields) are skipped rather than stopping the whole design.
    `jt_mm`: the layout-wide "trim jumps longer than" setting. `generated`: the item's stitches are
    made from a shape or text, so an insert remembers how many records there were (`n`) and is
    dropped, with a note, once the shape has changed and that place no longer exists."""
    deleted = {i for o in ops if o.get("op") == "delete_block" for i in [_index(o.get("block"))] if i is not None}
    # Stitch editing: single stitches deleted (by their index in the file).
    gone = {i for o in ops if o.get("op") == "delete_stitches" and isinstance(o.get("indices"), list)
            for v in o["indices"] for i in [_index(v)] if i is not None}
    count = _record_count(blocks) if generated else None
    inserts: dict[int, list[str]] = {}
    stale = 0
    for o in ops:
        if o.get("op") == "insert":
            if o.get("command") not in ("stop", "trim"):
                raise LayoutError("Can only insert a stop or a trim")
            after = _index(o.get("after"))
            if after is None:
                continue
            n = _index(o.get("n"))
            if count is not None and n is not None and n != count:
                stale += 1
                continue
            inserts.setdefault(after, []).append(o["command"])
    if stale and notes is not None:
        notes.append(f"{stale} stop{'s' if stale > 1 else ''} or trim{'s' if stale > 1 else ''} you added "
                     "were left out because the shape changed. Add them again where you want them.")
    jt = next((o for o in reversed(ops) if o.get("op") == "jumps_to_trims"), None)
    if jt is not None:
        jt_mm = _mm(jt.get("min_mm")) if jt.get("min_mm") is not None else 3.0
        if jt_mm is None:
            jt_mm = 3.0

    out = []
    for b, blk in enumerate(blocks):
        if b in deleted:
            continue
        recs: list[Rec] = []
        for r in blk.recs:
            if r[4] in gone and r[2] == pe.STITCH:
                # The stitch goes, but a stop or trim placed after it stays, at the last stitch kept.
                at = next((k for k in reversed(recs) if k[2] == pe.STITCH), r)
                for cmd in inserts.get(r[4], []):
                    recs.append([at[0], at[1], pe.STOP if cmd == "stop" else pe.TRIM, r[3], -1])
                continue
            recs.append(r)
            for cmd in inserts.get(r[4], []):
                recs.append([r[0], r[1], pe.STOP if cmd == "stop" else pe.TRIM, r[3], -1])
        if jt_mm is not None:
            recs = _jumps_to_trims(recs, jt_mm)
        out.append(Block(blk.thread, recs, blk.sources, blk.original, blk.digitized))
    return out


def _move_stitches(blocks: list[Block], ops: list[dict[str, Any]], local: bool = True) -> None:
    """Stitch editing: stitches dragged to a new place, by (dx, dy) mm. Moves marked `local` are in
    the file's own frame and are applied before the design's transform (so they turn and resize
    with it); older ones, without the mark, are a shift on the hoop applied after it.
    `move_stitches` moves several stitches by one drag; older projects have one `move_stitch` each."""
    moves: dict[int, tuple[float, float]] = {}
    for o in ops:
        kind = o.get("op")
        if kind not in ("move_stitch", "move_stitches") or bool(o.get("local")) != local:
            continue
        dx_mm, dy_mm = _mm(o.get("dx_mm")), _mm(o.get("dy_mm"))
        if dx_mm is None or dy_mm is None:
            continue
        raw = [o.get("index")] if kind == "move_stitch" else (o.get("indices") if isinstance(o.get("indices"), list) else [])
        for v in raw:
            i = _index(v)
            if i is None:
                continue
            dx, dy = moves.get(i, (0.0, 0.0))
            moves[i] = (dx + dx_mm * 10, dy + dy_mm * 10)
    if not moves:
        return
    for blk in blocks:
        for r in blk.recs:
            m = moves.get(r[4])
            if m and r[4] >= 0:
                r[0] += m[0]
                r[1] += m[1]


def _jumps_to_trims(recs: list[Rec], min_mm: float) -> list[Rec]:
    """Add a trim to every untrimmed jump run at least `min_mm` long between two stitches."""
    out: list[Rec] = []
    last = None
    i, n = 0, len(recs)
    while i < n:
        r = recs[i]
        if r[2] == pe.JUMP:
            j = i
            while j < n and recs[j][2] in (pe.JUMP, pe.TRIM):
                j += 1
            run = recs[i:j]
            nxt = recs[j] if j < n and recs[j][2] == pe.STITCH else None
            # Already trimmed: a trim in the run, or just before it (files and shapes store TRIM, JUMP).
            trimmed = any(x[2] == pe.TRIM for x in run) or bool(out and out[-1][2] == pe.TRIM)
            if last and nxt and not trimmed and math.hypot(nxt[0] - last[0], nxt[1] - last[1]) / 10 >= min_mm:
                out.append([last[0], last[1], pe.TRIM, r[3], -1])
            out.extend(run)
            i = j
            continue
        if r[2] == pe.STITCH:
            last = r
        elif r[2] == pe.STOP:
            last = None
        out.append(r)
        i += 1
    return out


def _transform(blocks: list[Block], t: Transform, center: tuple[float, float]) -> None:
    if t.is_identity():
        return
    cx, cy = center
    a = math.radians(t.rotate)
    ca, sa = math.cos(a), math.sin(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0
    dx, dy = t.x * 10, t.y * 10
    for blk in blocks:
        for r in blk.recs:
            px = (r[0] - cx) * fx * t.scale_x
            py = (r[1] - cy) * fy * t.scale_y
            r[0] = px * ca - py * sa + cx + dx
            r[1] = px * sa + py * ca + cy + dy
