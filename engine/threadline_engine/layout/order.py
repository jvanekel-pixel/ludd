"""The shortest sewing order for same-thread shapes."""

from __future__ import annotations

import math
from typing import Any

import pyembroidery as pe

from . import joins
from .model import M, Block, _thread_key
from .objects import OBJECT_KINDS
from .render import render


def optimize_order(layout: dict[str, Any]) -> dict[str, Any]:
    """Sew same-thread shapes in the shortest order: within each run of consecutive drawn shapes
    in one thread, shapes that don't overlap each other are reordered so each starts near where the
    last ended (overlapping ones keep their order: it decides which is on top). A branch sewn as one
    path moves as one piece: its shapes stay together, in their order.
    Returns {"order": [item ids], "saved_mm": travel saved}."""
    r = render(layout)
    items = layout.get("items") or []
    ids = [it.get("id", str(i)) for i, it in enumerate(items)]

    # Each shape's own stitches (src >= 0): not travel or ties added between shapes.
    own: dict[int, list[tuple[float, float]]] = {}
    for (x, y, k), it, src in zip(r.pattern.stitches, r.item_of, r.src_of):
        if it >= 0 and src >= 0 and k & M == pe.STITCH:
            own.setdefault(it, []).append((x, y))

    # The pieces that are reordered: a branch sewn as one path (its shapes, side by side in the
    # list), or a single item.
    place = {str(x): k for k, x in enumerate(ids)}
    branches = {}  # first item of a branch -> (its last item, where it starts, where it ends)
    for info in r.branches:
        at = sorted(place[m] for m in info["items"] if m in place)
        if at:
            branches[at[0]] = (at[-1], tuple(info["start"]), tuple(info["end"]))
    pieces: list[list[int]] = []
    ends: list[tuple | None] = []  # each piece's first and last needle point, in mm
    stitching: list[list[tuple]] = []  # each piece's records (x, y, command); a branch's with its joins
    k = 0
    while k < len(items):
        if k in branches:
            last, start, end = branches[k]
            members = range(k, last + 1)
            spots = [n for n, it in enumerate(r.item_of) if it in members]
            span = slice(spots[0], spots[-1] + 1)
            # With the stitches that join its shapes (and its jumps, so a gap it jumps isn't covered):
            # a shape sewn later over a join stays after it, so the join stays hidden.
            recs = [(x, y, c & M) for (x, y, c), it in zip(r.pattern.stitches[span], r.item_of[span])
                    if it < 0 or it in members]
            pieces.append(list(members))
            ends.append((start, end))
            stitching.append(recs)
            k = last + 1
        else:
            pts = own.get(k) or []
            pieces.append([k])
            ends.append(((pts[0][0] / 10, pts[0][1] / 10), (pts[-1][0] / 10, pts[-1][1] / 10)) if pts else None)
            stitching.append([(x, y, pe.STITCH) for x, y in pts])
            k += 1

    def key(it: dict[str, Any]) -> tuple:
        t = it.get("thread") or {}
        o = (it.get("threads") or [None])[0] or {}
        t = {**t, **o}
        return _thread_key({k: str(v) for k, v in t.items() if v is not None})  # as the file groups them (QA2 P5)

    def drawn(p: int) -> bool:
        return items[pieces[p][0]].get("kind") in OBJECT_KINDS

    shapes: dict[int, Block] = {}
    box = {}
    for p, recs in enumerate(stitching):
        sewn = [(x, y) for x, y, c in recs if c == pe.STITCH]
        if sewn:
            box[p] = (min(x for x, _ in sewn), min(y for _, y in sewn), max(x for x, _ in sewn), max(y for _, y in sewn))

    def overlap(a: int, b: int) -> bool:
        """Whether two pieces' stitching really overlaps (then their order decides which is on top)."""
        ba, bb = box.get(a), box.get(b)
        if not ba or not bb:
            return True
        if ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
            return False
        for p in (a, b):
            if p not in shapes:
                shapes[p] = Block({}, [[x, y, c, pieces[p][0], 0] for x, y, c in stitching[p]])
        if not shapes[a].recs or not shapes[b].recs:
            return True
        return joins._blocks_overlap(shapes[a], shapes[b])  # read from joins, so a test can replace it there

    order: list[int] = []
    saved = 0.0
    i = 0
    while i < len(pieces):
        j = i + 1
        if drawn(i):
            first = key(items[pieces[i][0]])
            while j < len(pieces) and drawn(j) and key(items[pieces[j][0]]) == first:
                j += 1
        run = list(range(i, j))
        e = {p: ends[p] for p in run}
        if len(run) > 2 and all(e.values()):
            # A piece may be sewn next once every piece before it in the run that it overlaps is
            # sewn: overlapping pieces keep their order, the others go nearest-first.
            before_of = {b: {a for a in run if a < b and overlap(a, b)} for b in run}

            def length(seq):
                return sum(math.dist(e[a][1], e[b][0]) for a, b in zip(seq, seq[1:]))

            todo = run[1:]
            seq = [run[0]]
            while todo:
                done = set(seq)
                ready = [k for k in todo if before_of[k] <= done]
                nxt = min(ready, key=lambda k: math.dist(e[seq[-1]][1], e[k][0]))
                todo.remove(nxt)
                seq.append(nxt)
            if length(seq) < length(run) - 1e-6:
                saved += length(run) - length(seq)
                run = seq
        order += [k for p in run for k in pieces[p]]
        i = j
    return {"order": [ids[k] for k in order], "saved_mm": round(saved, 1)}
