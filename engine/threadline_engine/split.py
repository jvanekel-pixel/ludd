"""Splitting a design that's bigger than the hoop into several hoopings.

How it works (kept simple and documented on purpose; see the patent note in docs/PLAN.md):

1. The design's area is divided into a grid of equal cells, as few as fit the hoop. Each hooping's
   sewing window is the hoop's size, centred on its cell, so neighbouring windows overlap.
2. Each run of stitches (one object's stitching between jumps) goes whole to one hooping when it
   fits inside that hooping's window, preferring the hooping whose cell holds the run's middle.
   Runs too big for any window are cut where they cross from one cell into the next; the cut
   lands exactly on the seam, so the two halves meet.
3. Alignment marks, small crosses on each seam inside both windows, are sewn at the end of the
   earlier hooping and at the start of the later one. After re-hooping, the start of the next
   file sews over the first marks: if the needle lands on them, everything lines up.
4. Each hooping becomes its own file, centred on its window, in the design's colour order.

Units: stitches are in 0.1 mm (pyembroidery); everything else here is millimetres.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pyembroidery as pe

from .digitize.stitches import tie_in, tie_off

SAFETY_MM = 1.0  # stay this far inside the hoop's sewing field
MARK_ARM_MM = 3.0
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
    marks_start: list[tuple[float, float]] = field(default_factory=list)
    marks_end: list[tuple[float, float]] = field(default_factory=list)

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.window
        return (x0 + x1) / 2, (y0 + y1) / 2


def _blocks(pattern: pe.EmbPattern) -> list[tuple[dict[str, str], list[list[tuple[float, float]]]]]:
    """Colour blocks, each a thread and its runs of stitches (mm), split at jumps, trims and stops."""
    threads = pattern.threadlist
    out: list[tuple[dict[str, str], list[list[tuple[float, float]]]]] = []
    cur: list[list[tuple[float, float]]] = []
    run: list[tuple[float, float]] = []
    color = 0

    def thread(i: int) -> dict[str, str]:
        t = threads[i] if i < len(threads) else None
        if t is None:
            return {"color": "#000000", "name": "", "catalog": "", "brand": ""}
        return {"color": t.hex_color(), "name": t.description or "", "catalog": t.catalog_number or "", "brand": t.brand or ""}

    def end_run() -> None:
        nonlocal run
        if len(run) > 1:
            cur.append(run)
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
    cols = 1 if W <= w else math.ceil((W - overlap) / (w - overlap))
    rows = 1 if H <= h else math.ceil((H - overlap) / (h - overlap))
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


def _marks(sections: list[Section], cols: int, rows: int, bounds) -> None:
    """Two crosses on every seam between neighbours, inside both windows."""
    arm = MARK_ARM_MM

    def fits(p, s):
        return _inside((p[0] - arm, p[1] - arm, p[0] + arm, p[1] + arm), s.window)

    for s in sections:
        for dc, dr in ((1, 0), (0, 1)):
            c, r = s.col + dc, s.row + dr
            if c >= cols or r >= rows:
                continue
            n = sections[r * cols + c]
            if dc:  # vertical seam
                x = s.cell[2]
                lo, hi = max(s.window[1], n.window[1], bounds[1]), min(s.window[3], n.window[3], bounds[3])
                pts = [(x, lo + (hi - lo) * f) for f in (0.2, 0.8)]
            else:  # horizontal seam
                y = s.cell[3]
                lo, hi = max(s.window[0], n.window[0], bounds[0]), min(s.window[2], n.window[2], bounds[2])
                pts = [(lo + (hi - lo) * f, y) for f in (0.2, 0.8)]
            pts = [p for p in pts if fits(p, s) and fits(p, n)]
            s.marks_end += pts
            n.marks_start += pts


def plan(pattern: pe.EmbPattern, hoop_w: float, hoop_h: float, overlap: float = 10.0):
    blocks = _blocks(pattern)
    pts = [p for _, runs in blocks for r in runs for p in r]
    if not pts:
        raise SplitError("There's nothing to split")
    bounds = _bounds(pts)
    sections = _grid(bounds, hoop_w, hoop_h, overlap)
    cols = max(s.col for s in sections) + 1
    rows = max(s.row for s in sections) + 1
    for bi, (_, runs) in enumerate(blocks):
        for run in runs:
            rb = _bounds(run)
            mid = ((rb[0] + rb[2]) / 2, (rb[1] + rb[3]) / 2)
            home = _cell_of(sections, mid, cols, rows, bounds)
            fits = [s for s in sections if _inside(rb, s.window)]
            if fits:
                target = home if home in fits else fits[0]
                target.runs.append((bi, run, False))
            else:
                for sec, piece in _cut(run, sections, cols, rows, bounds):
                    sec.runs.append((bi, piece, True))
    if len(sections) > 1:
        _marks(sections, cols, rows, bounds)
    return blocks, sections, (cols, rows), bounds


def _mark_stitches(p: tuple[float, float]) -> list[tuple[float, float]]:
    """A plus sign: up, back through the middle, down; left, through, right; back to the middle."""
    x, y, a = p[0], p[1], MARK_ARM_MM
    return [(x, y), (x, y - a), (x, y + a), (x, y), (x - a, y), (x + a, y), (x, y)]


def _tied(run: list[tuple[float, float]]) -> list[tuple[float, float]]:
    recs = tie_off(tie_in([(x, y, pe.STITCH) for x, y in run]))
    return [(r[0], r[1]) for r in recs]


def section_pattern(blocks, sec: Section) -> pe.EmbPattern:
    """One hooping as its own design, centred on its window."""
    cx, cy = sec.center
    out = pe.EmbPattern()
    groups: list[tuple[dict[str, str], list[list[tuple[float, float]]]]] = []
    if sec.marks_start:
        groups.append((MARK_THREAD, [_mark_stitches(p) for p in sec.marks_start]))
    by_block: dict[int, list[list[tuple[float, float]]]] = {}
    for bi, run, cut in sec.runs:
        # A run cut at a seam ends without its own lock stitches: add them so it can't unravel.
        by_block.setdefault(bi, []).append(_tied(run) if cut else run)
    for bi in sorted(by_block):
        groups.append((blocks[bi][0], by_block[bi]))
    if sec.marks_end:
        groups.append((MARK_THREAD, [_mark_stitches(p) for p in sec.marks_end]))

    last = None
    for gi, (thread, runs) in enumerate(groups):
        if gi:
            out.add_stitch_absolute(pe.COLOR_CHANGE, *(last or (0, 0)))
        out.add_thread(pe.EmbThread(thread["color"], thread.get("name", ""), thread.get("catalog", ""),
                                    brand=thread.get("brand", ""), chart=thread.get("brand", "")))
        for run in runs:
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
