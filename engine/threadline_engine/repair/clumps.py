"""Thin out spots where the needle hits over and over: the "declump" repair (P4-B3).

Needle hits are counted per 0.5 mm square, over the whole item. In a square with more than the
setting, a stitch may go if it isn't one of its thread run's lock stitches (the first and last
three) and either it lands within 0.15 mm of one of the six stitches before it, or taking it out
moves the thread path by less than 0.3 mm. Never one whose neighbors would then be joined by a
stitch longer than quality.LONG_MM. The latest hits go first, until the square is at the limit; the
busiest squares are done first, and never more than 15% of the item's stitches go.
"""

from __future__ import annotations

import math

from .. import quality
from ..layout.model import Block
from ..layout.passes import OpContext
from .small import EPS, LOCK, setting, thread_runs, without

CELL = 5.0       # 0.1 mm units: the 0.5 mm squares hits are counted in
SAME_HOLE = 1.5  # 0.15 mm: so close to a recent hit that it adds nothing
RECENT = 6       # how many stitches before it that looks at
DRIFT = 3.0      # 0.3 mm: the farthest the path may move when a stitch goes for no other reason
MOST = 0.15      # the largest share of the item's stitches taken out

MAX_HITS, LOWEST, HIGHEST = 5, 3, 10  # "Most needle hits in one spot"


def cell_of(x: float, y: float) -> tuple[int, int]:
    """The 0.5 mm square a needle drop at (x, y), in 0.1 mm, falls in. A drop on an edge counts for
    the square after it, whatever the rounding."""
    return math.floor((x + EPS) / CELL), math.floor((y + EPS) / CELL)


def _to_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    along = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / along)) if along else 0.0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


class _Run:
    """One thread run's needle points, and which of them are still sewn."""

    def __init__(self, block: int, start: int, points: list[tuple[float, float]]):
        self.block, self.start, self.points = block, start, points
        self.sewn = [True] * len(points)

    def _step(self, i: int, by: int) -> int:
        i += by
        while not self.sewn[i]:
            i += by
        return i

    def may_go(self, i: int) -> bool:
        if not (self.sewn[i] and LOCK <= i < len(self.points) - LOCK):
            return False
        a, b = self._step(i, -1), self._step(i, 1)  # the lock stitches are always there
        pa, pb, p = self.points[a], self.points[b], self.points[i]
        if math.dist(pa, pb) > quality.LONG_MM * 10 + EPS:
            return False
        j = i
        for _ in range(RECENT):
            if j == 0:
                break
            j = self._step(j, -1)
            if math.dist(self.points[j], p) <= SAME_HOLE + EPS:
                return True
        # Measured from where the thread went before anything was taken out, so it can't creep.
        return all(_to_segment(self.points[k], pa, pb) < DRIFT - EPS for k in range(a + 1, b))


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run on the hoop at final size."""
    limit = int(setting(op, "max_hits", MAX_HITS, LOWEST, HIGHEST))
    runs = [_Run(b, start, [(r[0], r[1]) for r in blk.recs[start:end]])
            for b, blk in enumerate(blocks) for start, end in thread_runs(blk.recs)]
    # The hits in each square, in sewing order, as (run, stitch).
    squares: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for n, run in enumerate(runs):
        for i, p in enumerate(run.points):
            squares.setdefault(cell_of(*p), []).append((n, i))
    left = {c: len(hits) for c, hits in squares.items()}
    most = int(sum(left.values()) * MOST + EPS)
    # The busiest square first; of two as busy, the one hit first.
    crowded = sorted((c for c in squares if left[c] > limit), key=lambda c: (-left[c], squares[c][0]))
    taken, capped, changed = 0, False, True
    while changed and not capped:  # taking one out can let another go
        changed = False
        for c in crowded:
            for n, i in reversed(squares[c]):
                if left[c] <= limit:
                    break
                if not runs[n].may_go(i):
                    continue
                if taken >= most:
                    capped = True
                    break
                runs[n].sewn[i] = False
                left[c] -= 1
                taken += 1
                changed = True
            if capped:
                break
    if capped:
        ctx.notes.append(f"Thinning stopped at {MOST:.0%} of the stitches, so some spots still get "
                         f"more than {limit} needle hits.")
    gone: dict[int, set[int]] = {}
    for run in runs:
        gone.setdefault(run.block, set()).update(run.start + i for i, sewn in enumerate(run.sewn) if not sewn)
    return [without(blk, gone.get(b, set())) for b, blk in enumerate(blocks)]
