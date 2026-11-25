"""Rebuild a resized stitch file's fills, satins and runs at the new size, with the original
spacing and stitch length: the "rebuild" repair (P4-C2).

Each thread run is recognized (repair/recognize.py) and every fill, satin and run in it is made
again at its final size: a fill as a tatami of its scaled outline at its own spacing and stitch
length, a satin from its scaled edges at its own spacing, a run along its scaled path at its own
stitch length. Everything else is scaled as it is and keeps its stitch numbers (`src`); remade
stitches are new (`src` -1). The density limit (repair/density.py) uses the same remaking at scale 1.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Callable

import pyembroidery as pe
from shapely.geometry import Polygon

from ..digitize.paths import cumulative, point_at, resample, sharp_points
from ..digitize.patterns import polygons
from ..digitize.stitches import STITCH, tatami, travel
from ..layout.model import Block, Rec
from ..layout.passes import OpContext
from .recognize import Point, Span, _dist, recognize

JOIN_MM = 0.3  # a rebuilt fill joins its first and last stitch with a stitch when further than this

# Determinism: distances that decide anything use recognize._dist (a plain square root, the same on
# every platform); a remade fill's angle is rounded before tatami() gets it.

#: Which spans to remake, and how: the span (changed or not) to remake it, or None to keep it.
Pick = Callable[[Span], "Span | None"]


def apply(blocks: list[Block], op: dict, ctx: OpContext) -> list[Block]:
    """The item op, run in the file's own frame, before the item's transform. It takes over the
    scaling: it writes the stitches at final size and sets ctx.transform's scale to 1."""
    t = ctx.transform
    sx, sy = t.scale_x, t.scale_y
    if sx == 1 and sy == 1:
        return blocks  # nothing to rebuild at the size it was made for
    out, rebuilt, total = remake(blocks, ctx.index, (sx, sy), ctx.center, lambda s: s)
    ctx.transform = dataclasses.replace(t, scale_x=1.0, scale_y=1.0)
    if total:
        pct = int(100 * rebuilt / total + 0.5)
        note = f"Rebuilt {pct}% of the stitches (fills, satins and lines); the rest were resized as they are."
        if pct < 50:
            note += " Most of this design couldn't be rebuilt, so check the density map."
        ctx.notes.append(note)
    return out


def remake(blocks: list[Block], item: int, scale: tuple[float, float], center: tuple[float, float],
           pick: Pick) -> tuple[list[Block], int, int]:
    """The blocks with each thread run's spans that `pick` chooses remade at `scale` about `center`
    (0.1 mm), and the rest scaled as they are. Also how many of the original stitches were in
    remade spans, and how many there were."""
    sx, sy = scale
    cx, cy = center

    def sc(x: float, y: float) -> tuple[float, float]:
        return (cx + (x - cx) * sx, cy + (y - cy) * sy)

    rebuilt = total = 0
    out: list[Block] = []
    for blk in blocks:
        recs: list[Rec] = []
        run: list[Rec] = []

        def flush() -> None:
            nonlocal rebuilt, total
            if run:
                new, n = _remake_run(run, item, sc, scale, pick)
                recs.extend(new)
                rebuilt += n
                total += len(run)
                run.clear()

        for r in blk.recs:
            if r[2] == pe.STITCH:
                run.append(r)
                continue
            flush()
            x, y = sc(r[0], r[1])
            recs.append([x, y, r[2], r[3], r[4]])
        flush()
        out.append(Block(blk.thread, recs, blk.sources, blk.original, blk.digitized))
    return out, rebuilt, total


def _remake_run(run: list[Rec], item: int, sc, scale: tuple[float, float], pick: Pick) -> tuple[list[Rec], int]:
    pts = [(r[0] / 10, r[1] / 10) for r in run]
    out: list[Rec] = []
    done = 0
    for span in recognize(pts):
        chosen = pick(span) if span.kind != "other" else None
        made = _make(span, chosen, pts, sc, scale) if chosen is not None else None
        if made is None:
            for r in run[span.start:span.end]:
                x, y = sc(r[0], r[1])
                out.append([x, y, r[2], r[3], r[4]])
            continue
        done += span.end - span.start
        out.extend([x * 10, y * 10, k, item, -1] for x, y, k in made)
    return out, done


def _make(orig: Span, span: Span, pts: list[Point], sc, scale) -> list[tuple[float, float, int]] | None:
    """The span's stitches remade (mm, at final size), or None if it can't be."""

    def scm(p: Point) -> Point:
        x, y = sc(p[0] * 10, p[1] * 10)
        return (x / 10, y / 10)

    first, last = scm(pts[orig.start]), scm(pts[orig.end - 1])
    if span.kind == "fill":
        return _fill(span, scm, scale, first, last)
    if span.kind == "satin":
        return _satin(span, scm, first, last)
    if span.kind == "run":
        path = [scm(p) for p in pts[orig.start:orig.end]]
        made = resample(path, span.stitch_mm, sharp_points(path))
        return [(x, y, STITCH) for x, y in made]
    return None


def _fill(span: Span, scm, scale, first: Point, last: Point) -> list[tuple[float, float, int]] | None:
    sx, sy = scale
    outline = [scm(p) for p in span.outline or []]
    if len(outline) < 3:
        return None
    poly = Polygon(outline)
    if not poly.is_valid:
        # Row ends that cross (a fill round a sharp bend): the biggest piece, the first of equals.
        pieces = polygons(poly.buffer(0))
        if not pieces:
            return None
        poly = max(enumerate(pieces), key=lambda kp: (round(kp[1].area, 6), -kp[0]))[1]
    if poly.area <= 0:
        return None
    a = math.radians(span.angle_deg or 0.0)
    angle = round(math.degrees(math.atan2(math.sin(a) * sy, math.cos(a) * sx)) % 180.0, 4) % 180.0
    try:
        rows = tatami(poly, angle, span.spacing_mm, span.stitch_mm, 0.0, start_near=first, end_near=last)
    except Exception:  # noqa: BLE001 (a shape the fill can't make sews as it was, resized)
        return None
    rows = [(float(x), float(y), int(k)) for x, y, k in rows]
    if not any(k == STITCH for _, _, k in rows):
        return None
    zone = poly.buffer(0.05)
    out: list[tuple[float, float, int]] = [(first[0], first[1], STITCH)]
    start = (rows[0][0], rows[0][1])
    if _dist(first, start) > JOIN_MM:
        out += [(x, y, k) for x, y, k in travel(first, start, zone)]
    _extend(out, rows)
    end = (out[-1][0], out[-1][1])
    if _dist(end, last) > JOIN_MM:
        out += [(x, y, k) for x, y, k in travel(end, last, zone)]
    if out[-1][2] != STITCH or _dist((out[-1][0], out[-1][1]), last) > 1e-9:
        out.append((last[0], last[1], STITCH))
    return out


def _extend(out: list, recs: list) -> None:
    """recs after out, without a second needle drop in the same hole where they meet."""
    if out and recs and out[-1][2] == STITCH and recs[0][2] == STITCH and \
            _dist(out[-1][:2], recs[0][:2]) < 1e-6:
        recs = recs[1:]
    out.extend(recs)


def _along(rail: list[Point], n: int) -> list[Point]:
    """n + 1 points evenly along a polyline, from its first point to its last."""
    cum = cumulative(rail)
    total = cum[-1]
    if total <= 0:
        return [rail[0]] * (n + 1)
    return [rail[0], *(point_at(rail, cum, total * k / n) for k in range(1, n)), rail[-1]]


def _satin(span: Span, scm, first: Point, last: Point) -> list[tuple[float, float, int]] | None:
    a = [scm(p) for p in span.rail_a or []]
    b = [scm(p) for p in span.rail_b or []]
    if len(a) < 2 or len(b) < 2 or not span.spacing_mm:
        return None
    mean = (sum(_dist(p, q) for p, q in zip(a, a[1:])) + sum(_dist(p, q) for p, q in zip(b, b[1:]))) / 2
    n = max(1, math.ceil(mean / span.spacing_mm - 1e-9))
    ra, rb = _along(a, n), _along(b, n)
    # Starting on the side the span started on (rail A). Stepped: across, along the edge, back
    # across, as LUDD sews satins; otherwise a zigzag, where every stitch crosses.
    pts = [p for k in range(n + 1) for p in ((rb[k], ra[k]) if span.stepped and k % 2 else (ra[k], rb[k]))]
    out = [(x, y, STITCH) for x, y in pts]
    if _dist(pts[-1], last) > JOIN_MM:
        out.append((last[0], last[1], STITCH))
    return out

