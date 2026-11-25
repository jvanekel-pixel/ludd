"""Placed stitch files: loading (cached), color blocks, per-item edits and the placement transform."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pyembroidery as pe

from .. import design, kept
from ..digitize import stitches as dz
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
    """Edits on one item: stitches and jumps added (stitch files only), colours and stitches
    deleted, stops and trims inserted, jumps trimmed.
    Damaged ops (missing or non-numeric fields) are skipped rather than stopping the whole design.
    `jt_mm`: the layout-wide "trim jumps longer than" setting. `generated`: the item's stitches are
    made from a shape or text, so an insert remembers how many records there were (`n`) and is
    dropped, with a note, once the shape has changed and that place no longer exists."""
    deleted = {i for o in ops if o.get("op") == "delete_block" for i in [_index(o.get("block"))] if i is not None}
    # Stitch editing: single stitches deleted (by their index in the file).
    gone = {i for o in ops if o.get("op") == "delete_stitches" and isinstance(o.get("indices"), list)
            for v in o["indices"] for i in [_index(v)] if i is not None}
    count = _record_count(blocks) if generated else None
    if not generated:
        # First, so that later deletes, moves, stops and trims can name an inserted stitch.
        blocks = _insert_stitches(blocks, ops, gone, notes)
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


def _past_lock(recs: list[Rec], i: int) -> int:
    """The position of the last record that goes with the stitch at i: after it, the lock stitches
    put on it (added records, numbered -1), so that later edits after it go after its lock."""
    while i + 1 < len(recs) and recs[i + 1][2] == pe.STITCH and recs[i + 1][4] < 0:
        i += 1
    return i


def _next_sewn(recs: list[Rec], i: int, gone: set[int]) -> tuple[int, bool]:
    """After the stitch at i (and its lock): the position of the next stitch that is sewn (len(recs)
    if there's none in this color), and whether the needle jumps on the way there."""
    jumped = False
    j = _past_lock(recs, i) + 1
    while j < len(recs) and not (recs[j][2] == pe.STITCH and recs[j][4] not in gone):
        jumped |= recs[j][2] == pe.JUMP
        j += 1
    return j, jumped


def _last_sewn(recs: list[Rec], i: int, gone: set[int]) -> int | None:
    """The stitch at position i, or the sewn one before it in its thread run (None if every one up
    to a jump, trim or stop is deleted)."""
    while i >= 0 and recs[i][2] == pe.STITCH:
        if recs[i][4] >= 0 and recs[i][4] not in gone:
            return i
        i -= 1
    return None


def _moved(r: Rec, offsets: dict[int, tuple[float, float]]) -> tuple[float, float]:
    """Where record r ends up once stitch editing's moves are made."""
    dx, dy = offsets.get(r[4], (0.0, 0.0)) if r[4] >= 0 else (0.0, 0.0)
    return r[0] + dx, r[1] + dy


def _insert_stitch(recs: list[Rec], i: int, o: dict, gone: set[int], offsets: dict) -> bool:
    x, y = o.get("x_mm"), o.get("y_mm")
    if x is not None and y is not None and _mm(x) is not None and _mm(y) is not None:
        at = (_mm(x) * 10, _mm(y) * 10)
    else:
        # Halfway to the next stitch. A later delete mustn't move it, so deletes don't count here.
        j, _ = _next_sewn(recs, i, set())
        if j == len(recs):
            return False
        at = ((recs[i][0] + recs[j][0]) / 2, (recs[i][1] + recs[j][1]) / 2)
    recs.insert(_past_lock(recs, i) + 1, [at[0], at[1], pe.STITCH, recs[i][3], _index(o.get("index"))])
    return True


def _insert_jump(recs: list[Rec], i: int, o: dict, gone: set[int], offsets: dict) -> bool:
    j, jumped = _next_sewn(recs, i, gone)
    if jumped:
        return True  # a jump already: nothing to add
    if j == len(recs):
        return False
    # At the next stitch that is sewn, where its moves put it, so no thread is sewn on the way.
    x, y = _moved(recs[j], offsets)
    recs.insert(j, [x, y, pe.JUMP, recs[j][3], -1])
    return True


def _lock(anchor: Rec, toward: tuple[float, float] | None, offsets: dict, start: bool) -> list[Rec]:
    """Three short stitches that lock the thread on the stitch `anchor`, along the thread to `toward`
    (the next stitch of its run, or the one before): the lock of dz.tie_in and dz.tie_off, with one
    stitch more halfway. It ends where it begins, so what comes before and after is sewn as it was."""
    ax, ay = _moved(anchor, offsets)
    bx, by = toward if toward is not None else (ax + 10, ay)
    a, b = (ax / 10, ay / 10, pe.STITCH), (bx / 10, by / 10, pe.STITCH)
    fx, fy, _ = dz.tie_in([a, b])[1] if start else dz.tie_off([b, a])[2]
    far = (fx * 10, fy * 10)
    half = ((ax + far[0]) / 2, (ay + far[1]) / 2)
    # At the start of a run the last step is a full one, so "Remove tiny stitches" keeps all three.
    path = [half, far, (ax, ay)] if start else [far, half, (ax, ay)]
    return [[x, y, pe.STITCH, anchor[3], -1] for x, y in path]


def _beside(recs: list[Rec], i: int, by: int, gone: set[int], offsets: dict) -> tuple[float, float] | None:
    """Where the lock on the stitch at i heads: the first sewn stitch before (by -1) or after (by 1)
    it in its thread run that is far enough for lock stitches of at least dz.MIN_STITCH_MM (bought
    designs often tie off with tiny ones), else the first in another place."""
    here = _moved(recs[i], offsets)
    near = None
    k = i + by
    while 0 <= k < len(recs) and recs[k][2] == pe.STITCH:
        if recs[k][4] not in gone:
            p = _moved(recs[k], offsets)
            d = math.dist(p, here)
            if d * 0.8 >= dz.MIN_STITCH_MM * 10 - 1e-6:  # dz's lock is min(TIE_MM, 0.8 d) long
                return p
            if near is None and d > 0.5:  # over 0.05 mm
                near = p
        k += by
    return near


def _lock_jump(recs: list[Rec], i: int, o: dict, gone: set[int], offsets: dict) -> bool:
    j, jumped = _next_sewn(recs, i, gone)
    if not jumped:
        return False
    before = _last_sewn(recs, i, gone)
    if j < len(recs):  # after the jump first, so the position before it doesn't shift
        recs[j + 1:j + 1] = _lock(recs[j], _beside(recs, j, 1, gone, offsets), offsets, start=True)
    if before is not None:
        end = _past_lock(recs, before) + 1
        recs[end:end] = _lock(recs[before], _beside(recs, before, -1, gone, offsets), offsets, start=False)
    return before is not None or j < len(recs)


_STITCH_INSERTS = {"insert_stitch": _insert_stitch, "insert_jump": _insert_jump, "lock_jump": _lock_jump}


def _insert_stitches(blocks: list[Block], ops: list[dict[str, Any]], gone: set[int],
                     notes: list[str] | None) -> list[Block]:
    """Stitch editing's added stitches, jumps and locks, in list order. Each names the stitch it
    goes after by its number; one whose stitch isn't there any more is left out, with a note, and so
    is an added stitch whose own number another stitch has (later edits would land on both)."""
    todo = [o for o in ops if isinstance(o.get("op"), str) and o["op"] in _STITCH_INSERTS]
    if not todo:
        return blocks
    blocks = [replace(b, recs=list(b.recs)) for b in blocks]
    offsets = _move_offsets(ops, local=True)
    numbers = {r[4] for b in blocks for r in b.recs}
    stale = 0
    for o in todo:
        after = _index(o.get("after"))
        number = _index(o.get("index")) if o["op"] == "insert_stitch" else None
        if after is None or (o["op"] == "insert_stitch" and number is None):
            continue  # a damaged op
        spot = next(((b.recs, i) for b in blocks for i, r in enumerate(b.recs)
                     if r[4] == after and r[2] == pe.STITCH), None)
        if spot is None or number in numbers or not _STITCH_INSERTS[o["op"]](*spot, o, gone, offsets):
            stale += 1
        elif number is not None:
            numbers.add(number)
    if stale and notes is not None:
        what = "stitches, jumps or locks you added were" if stale > 1 else "stitch, jump or lock you added was"
        them = "them" if stale > 1 else "it"
        notes.append(f"{stale} {what} left out because the stitches there changed. Add {them} again where you want {them}.")
    return blocks


def _move_offsets(ops: list[dict[str, Any]], local: bool) -> dict[int, tuple[float, float]]:
    """Stitch editing's drags, added up for each stitch number, in 0.1 mm: those in the file's own
    frame (`local`) or the older ones on the hoop."""
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
    return moves


def _move_stitches(blocks: list[Block], ops: list[dict[str, Any]], local: bool = True) -> None:
    """Stitch editing: stitches dragged to a new place, by (dx, dy) mm. Moves marked `local` are in
    the file's own frame and are applied before the design's transform (so they turn and resize
    with it); older ones, without the mark, are a shift on the hoop applied after it.
    `move_stitches` moves several stitches by one drag; older projects have one `move_stitch` each."""
    moves = _move_offsets(ops, local)
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
