"""Splitting a design that's bigger than the hoop into several hoopings.

How it works (kept simple and documented on purpose; see the patent note in docs/PLAN.md):

1. The design's area is divided into a grid of equal cells, as few as fit the hoop. Each hooping's
   sewing window is the hoop's size, centred on its cell, so neighbouring windows overlap.
2. Each run of stitches (one object's stitching between jumps) is cut where it crosses from one
   cell into the next (the cut lands exactly on the seam, so the halves meet), and each piece is
   sewn in its own cell's hooping. A run that crosses a seam is sewn whole instead (cleaner) when it
   fits one hooping's window and doing so can't change what's on top: nothing it overlaps that is
   sewn before it may end up in a later hooping, nor anything sewn after it in an earlier one.
   STOPs (applique placement and tack-down, stops you inserted) are kept in every hooping.
   A hooping that would sew nothing is left out.
3. Alignment marks, small crosses inside both windows (on bare fabric where there is room, so they
   can be pulled out), are sewn at the end of the earlier hooping and at the start of the later
   one. After re-hooping, the start of the next file sews over the first marks: if the needle
   lands on them, everything lines up.
4. Each hooping becomes its own file, centred on its window. Within it, colours keep the design's
   order; across hoopings, overlapping stitching keeps its layering (see 2).

Units: stitches are in 0.1 mm (pyembroidery); everything else here is millimetres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pyembroidery as pe

from .digitize.stitches import tie_in, tie_off

SAFETY_MM = 1.0  # stay this far inside the hoop's sewing field
MARK_ARM_MM = 3.0
MARK_CLEAR_MM = 1.0  # keep crosses this far from the design's thread where there's room
OCC_CELL_MM = 0.5
CUT_START, CUT_END = 1, 2  # a piece of a run starts / ends on a seam
MARK_THREAD = {"color": "#e0218a", "name": "Alignment marks (pull out afterwards)", "catalog": "", "brand": ""}
JOIN_TRIM_MM = 3.0


class SplitError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


@dataclass
class Section:
    index: int
    col: int
    row: int
    cell: tuple[float, float, float, float]
    window: tuple[float, float, float, float]
    # (colour block index, [(x, y), ...] in mm, cut at a seam) in sewing order
    runs: list[tuple[int, list[tuple[float, float]], bool]] = field(default_factory=list)
    # For each run: how many STOPs came before it in the design (a rise means "stop here first").
    stops: list[int] = field(default_factory=list)
    marks_start: list[tuple[float, float]] = field(default_factory=list)
    marks_end: list[tuple[float, float]] = field(default_factory=list)

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.window
        return (x0 + x1) / 2, (y0 + y1) / 2


def _blocks(pattern: pe.EmbPattern, stop_counts: dict[int, int] | None = None) -> list[tuple[dict[str, str], list[list[tuple[float, float]]]]]:
    """Colour blocks, each a thread and its runs of stitches (mm), split at jumps, trims and stops.
    `stop_counts` (if given) is filled with id(run) -> how many STOPs came before that run."""
    threads = pattern.threadlist
    out: list[tuple[dict[str, str], list[list[tuple[float, float]]]]] = []
    cur: list[list[tuple[float, float]]] = []
    run: list[tuple[float, float]] = []
    color = 0
    stops = 0

    def thread(i: int) -> dict[str, str]:
        t = threads[i] if i < len(threads) else None
        if t is None:
            return {"color": "#000000", "name": "", "catalog": "", "brand": ""}
        return {"color": t.hex_color(), "name": t.description or "", "catalog": t.catalog_number or "", "brand": t.brand or ""}

    def end_run() -> None:
        nonlocal run
        if run:  # a single stitch on its own (a dot) is kept too
            cur.append(run)
            if stop_counts is not None:
                stop_counts[id(run)] = stops
        run = []

    for x, y, cmd in pattern.stitches:
        c = cmd & pe.COMMAND_MASK
        if c == pe.STITCH:
            run.append((x / 10.0, y / 10.0))
        elif c == pe.COLOR_CHANGE:
            end_run()
            out.append((thread(color), cur))
            cur = []
            color += 1
        elif c == pe.END:
            break
        else:
            end_run()
            if c == pe.STOP:
                stops += 1
            if c == pe.JUMP:
                run = []
    end_run()
    out.append((thread(color), cur))
    return [(t, runs) for t, runs in out if runs]


def _bounds(pts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(b: tuple[float, float, float, float], w: tuple[float, float, float, float]) -> bool:
    return b[0] >= w[0] and b[1] >= w[1] and b[2] <= w[2] and b[3] <= w[3]


def _grid(bounds: tuple[float, float, float, float], hoop_w: float, hoop_h: float, overlap: float) -> list[Section]:
    x0, y0, x1, y1 = bounds
    w, h = hoop_w - 2 * SAFETY_MM, hoop_h - 2 * SAFETY_MM
    if overlap * 2 >= min(w, h):
        raise SplitError("The overlap is too big for this hoop")
    W, H = x1 - x0, y1 - y0
    # Enough hoopings that neighbouring sewing windows overlap by at least `overlap` (each window
    # is the hoop's size, centred on a cell of W / cols): room for the crosses and for shapes
    # across the seam to be sewn whole.
    cols = 1 if W <= w else math.ceil(W / (w - overlap) - 1e-9)
    rows = 1 if H <= h else math.ceil(H / (h - overlap) - 1e-9)
    cw, ch = W / cols, H / rows
    sections = []
    for r in range(rows):
        for c in range(cols):
            cell = (x0 + c * cw, y0 + r * ch, x0 + (c + 1) * cw, y0 + (r + 1) * ch)
            cx, cy = (cell[0] + cell[2]) / 2, (cell[1] + cell[3]) / 2
            window = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            sections.append(Section(len(sections), c, r, cell, window))
    return sections


def _cell_of(sections: list[Section], p: tuple[float, float], cols: int, rows: int, bounds) -> Section:
    x0, y0, x1, y1 = bounds
    c = min(cols - 1, max(0, int((p[0] - x0) / ((x1 - x0) / cols or 1))))
    r = min(rows - 1, max(0, int((p[1] - y0) / ((y1 - y0) / rows or 1))))
    return sections[r * cols + c]


def _cut(run: list[tuple[float, float]], sections, cols, rows, bounds) -> list[tuple[Section, list[tuple[float, float]]]]:
    """Cut a run where it crosses from one cell into another, adding the crossing point to both sides."""
    pieces: list[tuple[Section, list[tuple[float, float]]]] = []
    cur_sec = _cell_of(sections, run[0], cols, rows, bounds)
    if len(run) == 1:
        return [(cur_sec, run)]
    cur = [run[0]]
    for p in run[1:]:
        sec = _cell_of(sections, p, cols, rows, bounds)
        if sec is cur_sec:
            cur.append(p)
            continue
        q = cur[-1]
        # Where the stitch leaves the old cell (the seam).
        cx0, cy0, cx1, cy1 = cur_sec.cell
        t = 1.0
        for edge, a, b in ((cx0, q[0], p[0]), (cx1, q[0], p[0])):
            if (a - edge) * (b - edge) < 0:
                t = min(t, (edge - a) / (b - a))
        for edge, a, b in ((cy0, q[1], p[1]), (cy1, q[1], p[1])):
            if (a - edge) * (b - edge) < 0:
                t = min(t, (edge - a) / (b - a))
        m = (q[0] + (p[0] - q[0]) * t, q[1] + (p[1] - q[1]) * t)
        cur.append(m)
        pieces.append((cur_sec, cur))
        cur_sec, cur = sec, [m, p]
    pieces.append((cur_sec, cur))
    return [(s, pts) for s, pts in pieces if len(pts) > 1]


class _Occupancy:
    """Where the design has thread, on a OCC_CELL_MM grid, to keep the crosses off it."""

    def __init__(self, blocks, bounds) -> None:
        m = 2 * (MARK_ARM_MM + MARK_CLEAR_MM)
        self.x0, self.y0 = bounds[0] - m, bounds[1] - m
        self.w = int(math.ceil((bounds[2] - bounds[0] + 2 * m) / OCC_CELL_MM)) + 1
        self.h = int(math.ceil((bounds[3] - bounds[1] + 2 * m) / OCC_CELL_MM)) + 1
        grid = np.zeros((self.h, self.w), dtype=np.int32)
        for _, runs in blocks:
            for run in runs:
                a = np.asarray(run, dtype=float)
                if len(a) > 1:
                    # Points along every stitch, closer than a cell, so rows of fill mark every cell.
                    seg = np.diff(a, axis=0)
                    n = np.maximum(1, np.ceil(np.hypot(seg[:, 0], seg[:, 1]) / (OCC_CELL_MM / 2))).astype(int)
                    t = np.concatenate([np.arange(k) / k for k in n])
                    start = np.repeat(a[:-1], n, axis=0)
                    a = np.vstack([start + np.repeat(seg, n, axis=0) * t[:, None], a[-1:]])
                ix = ((a[:, 0] - self.x0) / OCC_CELL_MM).astype(int).clip(0, self.w - 1)
                iy = ((a[:, 1] - self.y0) / OCC_CELL_MM).astype(int).clip(0, self.h - 1)
                grid[iy, ix] = 1
        # Summed-area table: thread cells in any box in constant time.
        self.sat = np.zeros((self.h + 1, self.w + 1), dtype=np.int64)
        self.sat[1:, 1:] = grid.cumsum(0).cumsum(1)

    def count(self, x0: float, y0: float, x1: float, y1: float) -> int:
        """Cells with thread in the box (mm)."""
        c0 = max(0, int((x0 - self.x0) / OCC_CELL_MM))
        r0 = max(0, int((y0 - self.y0) / OCC_CELL_MM))
        c1 = min(self.w, int(math.ceil((x1 - self.x0) / OCC_CELL_MM)))
        r1 = min(self.h, int(math.ceil((y1 - self.y0) / OCC_CELL_MM)))
        if c1 <= c0 or r1 <= r0:
            return 0
        s = self.sat
        return int(s[r1, c1] - s[r0, c1] - s[r1, c0] + s[r0, c0])


def _occupancy(blocks, bounds) -> _Occupancy:
    return _Occupancy(blocks, bounds)


def _mark_spots(a: Section, b: Section, occ: _Occupancy) -> list[tuple[float, float]]:
    """Two places for crosses inside both hoopings' windows, as far apart as possible, on bare
    fabric where there is any (a cross under later stitching can't be pulled out)."""
    arm, clear = MARK_ARM_MM, MARK_CLEAR_MM
    x0, y0 = max(a.window[0], b.window[0]) + arm, max(a.window[1], b.window[1]) + arm
    x1, y1 = min(a.window[2], b.window[2]) - arm, min(a.window[3], b.window[3]) - arm
    if x1 < x0 or y1 < y0:
        return []
    step = 1.0
    nx, ny = int((x1 - x0) / step) + 1, int((y1 - y0) / step) + 1
    cands = [(x0 + i * (x1 - x0) / max(1, nx - 1), y0 + j * (y1 - y0) / max(1, ny - 1)) for i in range(nx) for j in range(ny)]
    r = arm + clear
    scored = [(occ.count(x - r, y - r, x + r, y + r), (x, y)) for x, y in cands]
    best = min(s for s, _ in scored)
    pool = [p for s, p in scored if s == best]
    if len(pool) < 2:
        pool = [p for s, p in sorted(scored)[:max(2, len(scored) // 20)]]
    # The two spots furthest apart (from the region's middle, the furthest; then the furthest from it).
    mid = ((x0 + x1) / 2, (y0 + y1) / 2)
    p1 = max(pool, key=lambda p: math.dist(p, mid))
    p2 = max(pool, key=lambda p: math.dist(p, p1))
    return [p1, p2] if math.dist(p1, p2) >= 2 * arm else [p1]


def _marks(sections: list[Section], occ: _Occupancy) -> None:
    """Crosses where each hooping meets an earlier one: sewn at the end of the earlier hooping and at
    the start of the later one. Neighbours in the grid are paired; a hooping with no earlier
    neighbour (its neighbours had nothing to sew) pairs with the earlier one its window overlaps most."""
    for s in sections:
        earlier = [p for p in sections if p.index < s.index]
        if not earlier:
            continue
        partners = [p for p in earlier if abs(p.col - s.col) + abs(p.row - s.row) == 1]
        if not partners:
            def shared(p: Section) -> float:
                return max(0.0, min(p.window[2], s.window[2]) - max(p.window[0], s.window[0])) * \
                    max(0.0, min(p.window[3], s.window[3]) - max(p.window[1], s.window[1]))
            best = max(earlier, key=shared)
            partners = [best] if shared(best) > 0 else []
        for p in partners:
            pts = _mark_spots(p, s, occ)
            p.marks_end += pts
            s.marks_start += pts


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def plan(pattern: pe.EmbPattern, hoop_w: float, hoop_h: float, overlap: float = 10.0):
    counts: dict[int, int] = {}
    blocks = _blocks(pattern, counts)
    pts = [p for _, runs in blocks for r in runs for p in r]
    if not pts:
        raise SplitError("There's nothing to split")
    bounds = _bounds(pts)
    sections = _grid(bounds, hoop_w, hoop_h, overlap)
    cols = max(s.col for s in sections) + 1
    rows = max(s.row for s in sections) + 1

    # Every run in sewing order, first cut at the seams so each piece lies in one cell.
    runs = []  # [order, block, run, bbox, [(section, points, cut)]]
    for bi, (_, rs) in enumerate(blocks):
        for run in rs:
            pieces = _cut(run, sections, cols, rows, bounds)
            if len({id(sec) for sec, _ in pieces}) == 1:
                pieces = [(pieces[0][0], run)]
                runs.append([len(runs), bi, run, _bounds(run), [(pieces[0][0], run, False)]])
            else:
                # Which ends of each piece lie on a seam: CUT_START, CUT_END or both.
                last = len(pieces) - 1
                runs.append([len(runs), bi, run, _bounds(run), [
                    (sec, pc, (CUT_START if k else 0) | (CUT_END if k < last else 0)) for k, (sec, pc) in enumerate(pieces)]])

    # Sew a seam-crossing run whole when it fits a window and keeps the layering.
    def safe(entry, h: int) -> bool:
        order, _, _, rb, _ = entry
        for other in runs:
            if other is entry or not _overlap(rb, other[3]):
                continue
            for sec, pc, _ in other[4]:
                if not _overlap(rb, _bounds(pc)):
                    continue
                if other[0] < order and sec.index > h:  # sewn before, but in a later hooping: it would cover this
                    return False
                if other[0] > order and sec.index < h:  # sewn after, but in an earlier hooping: this would cover it
                    return False
        return True

    for entry in runs:
        if len(entry[4]) == 1:
            continue
        rb = entry[3]
        mid = ((rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2)
        home = _cell_of(sections, mid, cols, rows, bounds)
        fits = sorted((s for s in sections if _inside(rb, s.window)), key=lambda s: s is not home)
        for sec in fits:
            if safe(entry, sec.index):
                entry[4] = [(sec, entry[2], 0)]
                break

    for order, bi, run, _, pieces in runs:
        for sec, pc, cut in pieces:
            sec.runs.append((bi, pc, cut))
            sec.stops.append(counts.get(id(run), 0))
    # A hooping with nothing to sew is left out (two badges in opposite corners: 2 hoopings, not 4).
    sections = [s for s in sections if s.runs]
    for i, s in enumerate(sections):
        s.index = i
    if len(sections) > 1:
        _marks(sections, _occupancy(blocks, bounds))
    return blocks, sections, (cols, rows), bounds


def _mark_stitches(p: tuple[float, float]) -> list[tuple[float, float]]:
    """A plus sign: up, back through the middle, down; left, through, right; back to the middle."""
    x, y, a = p[0], p[1], MARK_ARM_MM
    return [(x, y), (x, y - a), (x, y + a), (x, y), (x - a, y), (x + a, y), (x, y)]


def _tied(run: list[tuple[float, float]], start: bool, end: bool) -> list[tuple[float, float]]:
    recs = [(x, y, pe.STITCH) for x, y in run]
    if start:
        recs = tie_in(recs)
    if end:
        recs = tie_off(recs)
    return [(r[0], r[1]) for r in recs]


def _joined(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> bool:
    """Whether the thread runs on from a to b (at most a short jump, no trim between them)."""
    return math.dist(a[-1], b[0]) <= JOIN_TRIM_MM


def section_pattern(blocks, sec: Section) -> pe.EmbPattern:
    """One hooping as its own design, centred on its window."""
    cx, cy = sec.center
    out = pe.EmbPattern()
    groups: list[tuple[dict[str, str], list[list[tuple[float, float]]]]] = []
    if sec.marks_start:
        groups.append((MARK_THREAD, [_mark_stitches(p) for p in sec.marks_start]))
    by_block: dict[int, list[tuple[list[tuple[float, float]], int, int]]] = {}
    stops = sec.stops if len(sec.stops) == len(sec.runs) else [0] * len(sec.runs)
    for (bi, run, cut), n_stops in zip(sec.runs, stops):
        by_block.setdefault(bi, []).append((run, n_stops, int(cut)))
    for bi in sorted(by_block):
        rs = by_block[bi]
        tied = []
        for k, (run, n_stops, cut) in enumerate(rs):
            # A run cut at a seam ends there without lock stitches. Add them where the thread will
            # be cut (a trim, stop or colour change next to it); not where the thread runs on to
            # the next piece, as the rows of a fill do at the seam (ties there only pile up holes).
            prev = rs[k - 1] if k else None
            nxt = rs[k + 1] if k + 1 < len(rs) else None
            start = bool(cut & CUT_START) and not (prev and prev[1] == n_stops and _joined(prev[0], run))
            end = bool(cut & CUT_END) and not (nxt and nxt[1] == n_stops and _joined(run, nxt[0]))
            tied.append((_tied(run, start, end) if start or end else run, n_stops))
        groups.append((blocks[bi][0], tied))
    if sec.marks_end:
        groups.append((MARK_THREAD, [(_mark_stitches(p), -1) for p in sec.marks_end]))
    groups = [(t, [r if isinstance(r, tuple) else (r, -1) for r in rs]) for t, rs in groups]

    last = None
    for gi, (thread, runs) in enumerate(groups):
        if gi:
            out.add_stitch_absolute(pe.COLOR_CHANGE, *(last or (0, 0)))
        out.add_thread(pe.EmbThread(thread["color"], thread.get("name", ""), thread.get("catalog", ""),
                                    brand=thread.get("brand", ""), chart=thread.get("brand", "")))
        prev_stops = None
        for run, n_stops in runs:
            # The design stopped here (applique placement, tack-down, a stop you added): so does this file.
            if prev_stops is not None and n_stops > prev_stops and last is not None:
                out.add_stitch_absolute(pe.STOP, *last)
            if n_stops >= 0:
                prev_stops = n_stops
            first = ((run[0][0] - cx) * 10, (run[0][1] - cy) * 10)
            if last is not None and math.dist(first, last) > 0.5:
                if math.dist(first, last) > JOIN_TRIM_MM * 10:
                    out.add_stitch_absolute(pe.TRIM, *last)
                out.add_stitch_absolute(pe.JUMP, *first)
            for x, y in run:
                last = ((x - cx) * 10, (y - cy) * 10)
                out.add_stitch_absolute(pe.STITCH, *last)
    out.add_stitch_absolute(pe.END, *(last or (0, 0)))
    return out


def summary(blocks, sections, grid, bounds) -> dict[str, Any]:
    cols, rows = grid
    return {
        "cols": cols,
        "rows": rows,
        "bounds_mm": [round(v, 2) for v in bounds],
        "sections": [{
            "index": s.index,
            "window_mm": [round(v, 2) for v in s.window],
            "cell_mm": [round(v, 2) for v in s.cell],
            "stitches": sum(len(r) for _, r, _ in s.runs),
            "colors": len({bi for bi, _, _ in s.runs}),
            "marks": [[round(x, 2), round(y, 2)] for x, y in s.marks_start + s.marks_end],
        } for s in sections],
    }
