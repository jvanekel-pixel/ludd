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
    last ended (overlapping ones keep their order: it decides which is on top).
    Returns {"order": [item ids], "saved_mm": travel saved}."""
    r = render(layout)
    items = layout.get("items") or []
    ids = [it.get("id", str(i)) for i, it in enumerate(items)]

    # Each shape's own stitches (src >= 0): not travel or ties added between shapes.
    own: dict[int, list[tuple[float, float]]] = {}
    for (x, y, k), it, src in zip(r.pattern.stitches, r.item_of, r.src_of):
        if it >= 0 and src >= 0 and k & M == pe.STITCH:
            own.setdefault(it, []).append((x, y))

    def ends(idx: int) -> tuple[tuple[float, float], tuple[float, float]] | None:
        pts = own.get(idx)
        return ((pts[0][0] / 10, pts[0][1] / 10), (pts[-1][0] / 10, pts[-1][1] / 10)) if pts else None

    def key(it: dict[str, Any]) -> tuple:
        t = it.get("thread") or {}
        o = (it.get("threads") or [None])[0] or {}
        t = {**t, **o}
        return _thread_key({k: str(v) for k, v in t.items() if v is not None})  # as the file groups them (QA2 P5)

    shapes: dict[int, Block] = {}
    box = {k: (min(p[0] for p in v), min(p[1] for p in v), max(p[0] for p in v), max(p[1] for p in v)) for k, v in own.items()}

    def overlap(a: int, b: int) -> bool:
        """Whether two shapes' stitching really overlaps (then their order decides which is on top)."""
        ba, bb = box.get(a), box.get(b)
        if not ba or not bb:
            return True
        if ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
            return False
        for k in (a, b):
            if k not in shapes:
                shapes[k] = Block({}, [[x, y, pe.STITCH, k, 0] for x, y in own.get(k, [])])
        if not shapes[a].recs or not shapes[b].recs:
            return True
        return joins._blocks_overlap(shapes[a], shapes[b])  # read from joins, so a test can replace it there

    order: list[int] = []
    saved = 0.0
    i = 0
    while i < len(items):
        drawn = items[i].get("kind") in OBJECT_KINDS
        j = i + 1
        if drawn:
            while j < len(items) and items[j].get("kind") in OBJECT_KINDS and key(items[j]) == key(items[i]):
                j += 1
        run = list(range(i, j))
        e = {k: ends(k) for k in run}
        if len(run) > 2 and all(e.values()):
            # A shape may be sewn next once every shape before it in the run that it overlaps is
            # sewn: overlapping shapes keep their order, the others go nearest-first.
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
        order += run
        i = j
    return {"order": [ids[k] for k in order], "saved_mm": round(saved, 1)}
