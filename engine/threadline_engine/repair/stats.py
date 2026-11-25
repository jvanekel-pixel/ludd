"""The numbers repair.preview reports for a design before and after (P4-B1): stitches, trims,
jumps, tiny stitches, the longest stitch, the densest spot and the most needle hits in one spot."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pyembroidery as pe

from .. import quality
from .clumps import cell_of


def numbers(rendered, item: int) -> dict:
    """The preview's numbers for the rendered layout's item at position `item`. Stitch lengths and
    thread density are measured as the quality checks measure them, over this item's stitching."""
    segments: list[tuple[float, float, float, float]] = []
    points: list[tuple[float, float]] = []
    hits: Counter = Counter()
    trims = jumps = 0
    last = None
    for (x, y, command), owner in zip(rendered.pattern.stitches, rendered.item_of):
        kind = command & pe.COMMAND_MASK
        if owner != item or kind != pe.STITCH:
            last = None  # a jump, a trim, another design's stitching: the thread run ends
            if owner == item:
                trims += kind == pe.TRIM
                jumps += kind == pe.JUMP
            continue
        p = (x / 10.0, y / 10.0)
        if last is not None:
            segments.append((last[0], last[1], p[0], p[1]))
        points.append(p)
        hits[cell_of(x, y)] += 1
        last = p
    segs = np.array(segments, dtype=float).reshape(-1, 4)
    lengths = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
    densest = float(quality._grid(segs, np.array(points))[0].max()) if points else 0.0
    return {
        "stitches": len(points),
        "trims": int(trims),
        "jumps": int(jumps),
        "tiny": int(((lengths > 1e-6) & (lengths < quality.SHORT_MM)).sum()),
        "longest_mm": round(float(lengths.max()), 2) if len(lengths) else 0.0,
        "densest": round(densest, 2),
        "hits_max": max(hits.values(), default=0),
    }
