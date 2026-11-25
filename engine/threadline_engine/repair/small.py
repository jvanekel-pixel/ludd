"""Remove tiny stitches: the "filter_small" repair (P4-B2).

A thread run is the stitching between jumps, trims, stops and color changes. In each run, a stitch
closer than the setting to the last one kept is taken out, unless it is one of the run's first or
last three (its lock stitches), or taking it out would leave a stitch longer than quality.LONG_MM.
The run's first and last points never move, and running it again changes nothing more.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pyembroidery as pe

from .. import quality
from ..layout.model import Block, Rec
from ..layout.passes import OpContext

#: Lock stitches: a thread run's first and last three stitches, which the clean-up repairs keep.
LOCK = 3
EPS = 1e-6  # 0.1 mm units: so a stitch exactly at a limit is judged the same on every machine

MIN_MM, LOWEST_MM, HIGHEST_MM = 0.4, 0.2, 1.0  # "Shorter than"


def setting(op: dict, key: str, default: float, lowest: float, highest: float) -> float:
    """A repair's number: the standard one if it's missing or not a number, else held to its range."""
    v = op.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return default
    return min(highest, max(lowest, v))


def thread_runs(recs: list[Rec]) -> list[tuple[int, int]]:
    """[start, end) of each thread run in a color block's records."""
    runs: list[tuple[int, int]] = []
    start = None
    for i, r in enumerate(recs):
        if r[2] == pe.STITCH:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(recs)))
    return runs


def without(block: Block, gone: set[int]) -> Block:
    """The block without the records at the positions in `gone`."""
    return replace(block, recs=[r for i, r in enumerate(block.recs) if i not in gone]) if gone else block


def _tiny(points: list[tuple[float, float]], shortest: float, longest: float) -> list[int]:
    """Which of a run's points go: each closer than `shortest` to the last one kept, if the stitch
    that would join its neighbors is no longer than `longest` (all in 0.1 mm)."""
    gone: list[int] = []
    last = 0
    for i in range(1, len(points)):
        if (LOCK <= i < len(points) - LOCK and math.dist(points[last], points[i]) < shortest - EPS
                and math.dist(points[last], points[i + 1]) <= longest + EPS):
            gone.append(i)
        else:
            last = i
    return gone


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run on the hoop at final size."""
    shortest = setting(op, "min_mm", MIN_MM, LOWEST_MM, HIGHEST_MM) * 10
    out = []
    for blk in blocks:
        gone: set[int] = set()
        for start, end in thread_runs(blk.recs):
            points = [(r[0], r[1]) for r in blk.recs[start:end]]
            gone.update(start + i for i in _tiny(points, shortest, quality.LONG_MM * 10))
        out.append(without(blk, gone))
    return out
