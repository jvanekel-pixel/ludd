"""Limit density for the fabric: the "density_limit" repair (P4-C3). Fills and satins in a stitch
file that are denser than the layout's fabric takes are remade at that fabric's normal spacing; the
limits live here and in fabrics.py."""

from __future__ import annotations

import dataclasses

import numpy as np
import pyembroidery as pe

from .. import fabrics, quality
from ..layout.model import Block
from ..layout.passes import OpContext
from .rebuild import remake
from .recognize import Span

THICK_NOTE = "Still thick where layers overlap."


def limits(fabric_id: str | None) -> dict[str, tuple[float, float]]:
    """For each of "fill" and "satin": remade when its spacing is under the first number (mm),
    to the second, on this fabric."""
    d = fabrics.get(fabric_id)["density"]
    return {kind: (under / d, to / d) for kind, (under, to) in fabrics.DENSITY_LIMITS.items()}


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run on the hoop at final size, with the layout's fabric (ctx.fabric)."""
    lim = limits(ctx.fabric)

    def pick(span: Span) -> Span | None:
        if span.kind in lim and span.spacing_mm is not None and span.spacing_mm < lim[span.kind][0]:
            return dataclasses.replace(span, spacing_mm=lim[span.kind][1])
        return None

    out, _, _ = remake(blocks, ctx.index, (1.0, 1.0), (0.0, 0.0), pick)
    if _thick(out):
        ctx.notes.append(THICK_NOTE)
    return out


def _thick(blocks: list[Block]) -> bool:
    """A patch of the item's stitching over the quality checks' limit (thread per mm²), measured
    as they measure it."""
    segs, pts = [], []
    for blk in blocks:
        prev = None
        for r in blk.recs:
            if r[2] == pe.STITCH:
                p = (r[0] / 10, r[1] / 10)
                if prev is not None:
                    segs.append((prev[0], prev[1], p[0], p[1]))
                pts.append(p)
                prev = p
            else:
                prev = None
    if not pts:
        return False
    cover, _, _, _ = quality._grid(np.array(segs, dtype=float).reshape(-1, 4), np.array(pts, dtype=float).reshape(-1, 2))
    return int(quality._open3(cover > quality.DENSE_MM_PER_MM2).sum()) >= 3
