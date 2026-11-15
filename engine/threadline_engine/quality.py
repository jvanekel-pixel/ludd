"""Quality checks on the finished stitches, each with why it matters and what to do.

Run on the whole design as it will be sewn (after color merging and sorting), so overlaps
between objects count. Also builds the density map the canvas can show.

Thresholds are starting points from common digitizing practice, to be confirmed by stitch-outs:
- thread coverage: one layer of fill or satin at 0.4 mm spacing lays about 2.5 mm of thread per mm²;
  with underlay about 3.5. Over 7 (three layers) the fabric puckers and needles break.
- needle hits: over 20 in one square millimetre punches the fabric full of holes.
"""

from __future__ import annotations

import base64
import hashlib
import math
from typing import Any

import numpy as np
import pyembroidery as pe
from shapely import STRtree
from shapely.geometry import LineString, MultiLineString

CELL_MM = 1.0
DENSE_MM_PER_MM2 = 7.0
HITS_PER_MM2 = 20
SHORT_MM = 0.3
SHORT_COUNT = 25  # a few short stitches (ties, corners) are normal
LONG_MM = 7.0
# Stitches made exactly LONG_MM long (satin-look letters, split stitches) come out a hair longer
# after rounding to the machine's 0.1 mm grid; they are not loose stitches.
LONG_TOLERANCE_MM = 0.15
GAP_MM = 0.6  # shapes closer than this but not overlapping may show fabric between them


def _segments(pattern: pe.EmbPattern) -> tuple[np.ndarray, np.ndarray]:
    """Stitch segments (x0, y0, x1, y1 in mm) and needle points, skipping jumps and trims."""
    segs, pts = [], []
    prev = None
    for x, y, cmd in pattern.stitches:
        c = cmd & pe.COMMAND_MASK
        if c == pe.STITCH:
            p = (x / 10.0, y / 10.0)
            if prev is not None:
                segs.append((prev[0], prev[1], p[0], p[1]))
            pts.append(p)
            prev = p
        elif c == pe.END:
            break
        else:  # jump, trim, color change, stop: the next stitch starts fresh
            prev = None
    return np.array(segs, dtype=float).reshape(-1, 4), np.array(pts, dtype=float).reshape(-1, 2)


def _grid(segs: np.ndarray, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Thread length (mm) and needle hits per CELL_MM square."""
    allx = np.concatenate([segs[:, [0, 2]].ravel(), pts[:, 0]]) if len(segs) else pts[:, 0]
    ally = np.concatenate([segs[:, [1, 3]].ravel(), pts[:, 1]]) if len(segs) else pts[:, 1]
    x0, y0 = math.floor(allx.min()) - 1, math.floor(ally.min()) - 1
    w = int(math.ceil((allx.max() - x0) / CELL_MM)) + 2
    h = int(math.ceil((ally.max() - y0) / CELL_MM)) + 2
    cover = np.zeros((h, w))
    hits = np.zeros((h, w))
    if len(segs):
        lengths = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
        # Sample each stitch every quarter cell and spread its length over the samples.
        n = np.maximum(1, np.ceil(lengths / (CELL_MM / 4))).astype(int)
        idx = np.repeat(np.arange(len(segs)), n)
        t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 0.5) / np.repeat(n, n)
        sx = segs[idx, 0] + (segs[idx, 2] - segs[idx, 0]) * t
        sy = segs[idx, 1] + (segs[idx, 3] - segs[idx, 1]) * t
        cx = ((sx - x0) / CELL_MM).astype(int)
        cy = ((sy - y0) / CELL_MM).astype(int)
        np.add.at(cover, (cy, cx), (lengths / n)[idx])
    if len(pts):
        np.add.at(hits, (((pts[:, 1] - y0) / CELL_MM).astype(int), ((pts[:, 0] - x0) / CELL_MM).astype(int)), 1)
    return cover / (CELL_MM * CELL_MM), hits / (CELL_MM * CELL_MM), x0, y0


def _drawn_cells(pattern: pe.EmbPattern, item_of: list[int], names: dict[int, str], shape: tuple[int, int],
                 x0: float, y0: float) -> np.ndarray:
    """Cells (and their neighbours) where shapes or lettering drawn in LUDD put a needle."""
    pts = [(x / 10.0, y / 10.0) for (x, y, c), it in zip(pattern.stitches, item_of)
           if it in names and c & pe.COMMAND_MASK == pe.STITCH]
    mask = np.zeros(shape, dtype=bool)
    if pts:
        a = np.array(pts)
        cx = ((a[:, 0] - x0) / CELL_MM).astype(int).clip(0, shape[1] - 1)
        cy = ((a[:, 1] - y0) / CELL_MM).astype(int).clip(0, shape[0] - 1)
        mask[cy, cx] = True
        p = np.pad(mask, 1)
        mask = np.logical_or.reduce([p[1 + dy:1 + dy + shape[0], 1 + dx:1 + dx + shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return mask


def _open3(mask: np.ndarray) -> np.ndarray:
    """Morphological opening with a 3 x 3 square: removes anything narrower than 3 cells."""
    def shifts(m: np.ndarray, fill: bool):
        p = np.pad(m, 1, constant_values=fill)
        return [p[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

    eroded = np.logical_and.reduce(shifts(mask, False))
    return np.logical_or.reduce(shifts(eroded, False))


def _worst_spot(mask: np.ndarray, value: np.ndarray, x0: float, y0: float) -> list[float]:
    ys, xs = np.nonzero(mask)
    k = int(np.argmax(value[ys, xs]))
    return [round(float(x0 + (xs[k] + 0.5) * CELL_MM), 2), round(float(y0 + (ys[k] + 0.5) * CELL_MM), 2)]


def _check(code: str, level: str, title: str, why: str, fix: str, at: list[float] | None = None,
           item: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "level": level, "message": title, "why": why, "fix": fix}
    if at is not None:
        out["at"] = at
    if item is not None:
        out["item"] = item
    return out


_gap_cache: dict[bytes, Any] = {}


def _gap_shape(runs: list[list[tuple[float, float]]]):
    """An item's stitched area: rows closed up, then shrunk back to about the stitched edge.
    Cached by the stitches, so after an edit only the changed shapes are worked out again."""
    key = hashlib.sha1(repr(runs).encode()).digest()
    hit = _gap_cache.get(key)
    if hit is None:
        hit = MultiLineString(runs).simplify(0.1).buffer(0.25, quad_segs=2).buffer(-0.22, quad_segs=2)
        if len(_gap_cache) > 2048:
            _gap_cache.pop(next(iter(_gap_cache)))
        _gap_cache[key] = hit
    return hit


def _gaps(pattern: pe.EmbPattern, item_of: list[int], names: dict[int, str]) -> list[dict[str, Any]]:
    """Objects that nearly touch: pull-in opens a line of bare fabric between them."""
    lines: dict[int, list[list[tuple[float, float]]]] = {}
    run: list[tuple[float, float]] = []
    run_item = -1
    for (x, y, cmd), item in zip(pattern.stitches, item_of + [-1] * (len(pattern.stitches) - len(item_of))):
        if (cmd & pe.COMMAND_MASK) == pe.STITCH and item in names and item == run_item:
            run.append((x / 10.0, y / 10.0))
            continue
        if len(run) > 1:
            lines.setdefault(run_item, []).append(run)
        run = [(x / 10.0, y / 10.0)] if (cmd & pe.COMMAND_MASK) == pe.STITCH and item in names else []
        run_item = item
    if len(run) > 1:
        lines.setdefault(run_item, []).append(run)
    if len(lines) < 2:
        return []
    shapes = {item: _gap_shape(runs) for item, runs in lines.items()}
    out = []
    keys = sorted(shapes)
    # Only neighbours are compared (a spatial index), so designs with hundreds of shapes are checked too.
    tree = STRtree([shapes[k] for k in keys])
    for i, a in enumerate(keys):
        near = tree.query(shapes[a].envelope.buffer(GAP_MM))
        for j in sorted(int(n) for n in near if n > i):
            b = keys[j]
            sa, sb = shapes[a], shapes[b]
            if sa.is_empty or sb.is_empty or sa.intersects(sb):
                continue  # they overlap: no gap
            d = sa.distance(sb)
            if 0 < d < GAP_MM:
                pa = sa.boundary.interpolate(sa.boundary.project(sb.centroid))
                # Stacked copies of a shape share one gap: say it once.
                if any(math.dist(c["at"], (pa.x, pa.y)) < 3 for c in out):
                    continue
                out.append(_check(
                    f"gap_{a}_{b}", "warning", f"{names[a]} and {names[b]} almost touch",
                    "Stitches pull the fabric in, so shapes that only just meet can open a thin line of bare fabric between them.",
                    "Make them overlap by about half a millimetre, or move them apart on purpose.",
                    [round(pa.x, 2), round(pa.y, 2)], a))
    return out


def check(pattern: pe.EmbPattern, item_of: list[int] | None = None, names: dict[int, str] | None = None,
          heatmap: bool = False) -> dict[str, Any]:
    segs, pts = _segments(pattern)
    checks: list[dict[str, Any]] = []
    result: dict[str, Any] = {"checks": checks}
    if not len(pts):
        return result
    cover, hits, x0, y0 = _grid(segs, pts)

    # Only areas count: a border overlapping the edge of a fill makes a thin dense band, which is
    # normal practice. Opening the mask (shrink, then grow back) keeps patches at least 3 mm across.
    # In a layout, thick spots only in placed stitch files are a note, not a warning: bought designs
    # often have them and sew fine, and there's nothing to change in them here. Anything drawn in
    # LUDD (shapes, lettering) that takes part still gets the warning.
    mine = _drawn_cells(pattern, item_of, names, cover.shape, x0, y0) if item_of is not None and names is not None else None
    dense = _open3(cover > DENSE_MM_PER_MM2)
    if dense.sum() >= 3:
        area = int(dense.sum() * CELL_MM * CELL_MM)
        if mine is None or (dense & mine).any():
            checks.append(_check(
                "dense", "warning", f"Too much thread in one place (about {area} mm²)",
                "Where layers pile up, the fabric puckers, the stitching turns stiff like a patch and needles can break.",
                "Remove overlapping layers, lower the density (Light) there, or turn off underlay on the top object.",
                _worst_spot(dense if mine is None else dense & mine, cover, x0, y0)))
        else:
            checks.append(_check(
                "dense", "info", f"Thick spots in a placed stitch file (about {area} mm²)",
                "Bought designs often have places with several layers; they usually sew fine.",
                "If the stitch-out puckers, use a firmer stabilizer.",
                _worst_spot(dense, cover, x0, y0)))
    pile = hits > HITS_PER_MM2
    if pile.any():
        if mine is None or (pile & mine).any():
            checks.append(_check(
                "needle_hits", "warning", "The needle hits one spot over and over",
                "Many stitches ending in the same tiny area cut the fabric like perforations and can break the thread.",
                "Look for very narrow satins, tiny letters or points where many shapes start and end.",
                _worst_spot(pile if mine is None else pile & mine, hits, x0, y0)))
        else:
            checks.append(_check(
                "needle_hits", "info", "A placed stitch file has spots where the needle hits often",
                "Common in bought designs (small details, lettering); usually fine.",
                "Use a sharp needle; if it cuts the fabric, use a firmer stabilizer.",
                _worst_spot(pile, hits, x0, y0)))
    if len(segs):
        lengths = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
        short = (lengths > 1e-6) & (lengths < SHORT_MM)
        if short.sum() > SHORT_COUNT:
            k = int(np.argmax(short))
            checks.append(_check(
                "short", "info", f"{int(short.sum())} very short stitches (under {SHORT_MM} mm)",
                "Very short stitches can make the machine nest thread or skip; a few at corners and ties are normal.",
                "Use a longer stitch length, or check tiny details you could leave out.",
                [round(float(segs[k, 2]), 2), round(float(segs[k, 3]), 2)]))
        long_ = lengths > LONG_MM + LONG_TOLERANCE_MM
        if long_.any():
            k = int(np.argmax(lengths))
            checks.append(_check(
                "long", "warning", f"{int(long_.sum())} long loose stitch{'es' if long_.sum() != 1 else ''} (up to {lengths[k]:.1f} mm)",
                "Stitches longer than about 7 mm lie loose on top, catch on fingers and washing, and pull out.",
                "For a wide satin, tick Split long stitches, make it narrower or use a fill; "
                "for a fill use a shorter stitch length, and for cross-stitch smaller squares.",
                [round(float(segs[k, 0] + segs[k, 2]) / 2, 2), round(float(segs[k, 1] + segs[k, 3]) / 2, 2)]))
    if item_of is not None and names:
        checks += _gaps(pattern, item_of, names)

    if heatmap:
        # 0..255 where 255 is twice the "too dense" limit; the UI colors it.
        scaled = np.clip(cover / (2 * DENSE_MM_PER_MM2) * 255, 0, 255).astype(np.uint8)
        result["heatmap"] = {
            "x": float(x0), "y": float(y0), "cell_mm": CELL_MM, "width": int(scaled.shape[1]), "height": int(scaled.shape[0]),
            "limit": round(DENSE_MM_PER_MM2 / (2 * DENSE_MM_PER_MM2) * 255),
            "data": base64.b64encode(scaled.tobytes()).decode("ascii"),
        }
    return result
