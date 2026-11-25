"""Find the fills, satins and runs inside a stitch file's thread runs (P4-C1). Rebuild and the
density limit use it; Phase 13 builds on it.

A thread run is the needle points between two jumps, trims or stops, in sewing order. Each step
claims stitches the earlier ones left, scanning from the start of the run:

1. Satin: at least 8 stitches across a column, each turning back more than 150 degrees from the one
   before, 1 to 12 mm long, neighbors within a factor of 1.6 in length, their middles moving on by
   0.05 to 0.6 mm a step. Between two of them there may be one short step (under 1 mm) along the
   edge: LUDD's own satins sew that way (across, along the edge, back across); bought designs
   mostly zigzag (each stitch crosses).
2. Fill: rows of stitches running one way (within 8 degrees), each row at least 1.5 mm long with
   stitches up to 7 mm, then a short move and a row back the other way. At least 4 rows the same
   distance apart (0.15 to 3 mm) make a fill. Sparse rows (over 1.2 mm apart) under a fill are its
   underlay: a fill too, with its own spacing.
3. Run: at least 4 stitches of 1 to 5 mm, each turning less than 60 degrees.
4. Other: everything else, including lock stitches.

Determinism: every decision compares sums and products of the input (no trigonometry, no library
ordering), against constants written out in full, and ties go to the earliest stitch. Angles are
only worked out at the end, for the result, and rounded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]  # mm, in the frame the run is given in


@dataclass
class Span:
    kind: str            # "fill" | "satin" | "run" | "other"
    start: int           # first stitch index in the run
    end: int             # one past the last
    angle_deg: float | None = None       # fill: row direction, 0..180
    spacing_mm: float | None = None      # fill: between rows; satin: between stitches on one side
    stitch_mm: float | None = None       # fill and run: typical stitch length
    outline: list[Point] | None = None   # fill: left row ends, then right row ends reversed
    rail_a: list[Point] | None = None    # satin: even stitches
    rail_b: list[Point] | None = None    # satin: odd stitches
    stepped: bool = False                # satin: a short step along the edge between stitches (LUDD's own)


# Thresholds as cosines, written out so every platform compares against the same number.
COS_8 = 0.9902680687415704      # cos(8 degrees): rows run one way within 8 degrees
COS_150 = -0.8660254037844387   # cos(150 degrees): a satin stitch turns back more than this
COS_60 = 0.5                    # cos(60 degrees): a run turns less than this

SATIN_MIN = 8                   # stitches across
SATIN_LEN = (1.0, 12.0)         # mm, each stitch across
SATIN_RATIO = 1.6               # neighbors' lengths
SATIN_ADVANCE = (0.05, 0.6)     # mm the middles move on, from one stitch across to the next
SATIN_STEP_MAX = 1.0            # mm, a step along the edge between two stitches across

ROW_MIN_MM = 1.5                # a row is at least this long
ROW_STITCH_MAX = 7.0            # and no stitch in it longer
ROW_START_MM = 1.0              # a row starts on a stitch at least this long (its direction is sure)
ROW_SURE_MM = 2.0               # stitches this long must point within 8 degrees of the row
ROW_TOL_MM = 0.15               # shorter ones may stray this far from it (the machine grid is 0.1 mm)
FILL_ROWS = 4
FILL_STEP = (0.15, 3.0)         # mm between rows
FILL_STEADY = (0.75, 1.0 / 0.75)  # each step, against the fill's first
FILL_MOVE_STITCHES = 3          # stitches at most between one row and the next
FILL_STITCH = (1.0, 7.0)        # mm, the stitch length a rebuild may use

RUN_MIN = 4
RUN_LEN = (1.0, 5.0)


def recognize(points: list[Point]) -> list[Span]:
    """What one thread run (needle points in sewing order) is made of: fills, satins, runs and,
    for the rest, "other". The spans cover every point, in order, without overlapping."""
    pts = [(float(x), float(y)) for x, y in points]
    n = len(pts)
    if n == 0:
        return []
    st = _Stitches(pts)
    owner: list[Span | None] = [None] * n
    for span in _satins(st):
        _claim(owner, span)
    for lo, hi in _free(owner):
        for span in _fills(st, lo, hi):
            _claim(owner, span)
    for lo, hi in _free(owner):
        for span in _runs(st, lo, hi):
            _claim(owner, span)
    out: list[Span] = []
    i = 0
    while i < n:
        s = owner[i]
        if s is None:
            j = i
            while j < n and owner[j] is None:
                j += 1
            out.append(Span("other", i, j))
            i = j
        else:
            out.append(s)
            i = s.end
    return out


# ---------------------------------------------------------------- shared


class _Stitches:
    """The points, and for each stitch (point i to point i + 1) its vector, length and direction."""

    def __init__(self, pts: list[Point]):
        self.p = pts
        self.n = len(pts) - 1  # stitches
        self.v = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
        self.len = [math.sqrt(dx * dx + dy * dy) for dx, dy in self.v]
        self.u = [(dx / ln, dy / ln) if ln > 1e-9 else (0.0, 0.0) for (dx, dy), ln in zip(self.v, self.len)]

    def mid(self, i: int) -> Point:
        a, b = self.p[i], self.p[i + 1]
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dist(a: Point, b: Point) -> float:
    dx, dy = a[0] - b[0], a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def _unit(a: Point, b: Point) -> Point:
    d = _dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d) if d > 1e-9 else (0.0, 0.0)


def _median(values: list[float]) -> float:
    s = sorted(values)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def _length(poly: list[Point]) -> float:
    return sum(_dist(a, b) for a, b in zip(poly, poly[1:]))


def _claim(owner: list, span: Span) -> None:
    for i in range(span.start, span.end):
        owner[i] = span


def _free(owner: list) -> list[tuple[int, int]]:
    """Point ranges [lo, hi) nobody has claimed yet."""
    out, i, n = [], 0, len(owner)
    while i < n:
        if owner[i] is None:
            j = i
            while j < n and owner[j] is None:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


# ---------------------------------------------------------------- satin


def _across(st: _Stitches, i: int) -> bool:
    return 0 <= i < st.n and SATIN_LEN[0] <= st.len[i] <= SATIN_LEN[1]


def _follows(st: _Stitches, k: int, j: int) -> bool:
    """Stitch j can be the next stitch across after k."""
    if not _across(st, j) or _dot(st.u[k], st.u[j]) >= COS_150:
        return False
    a, b = st.len[k], st.len[j]
    if max(a, b) > SATIN_RATIO * min(a, b):
        return False
    adv = _dist(st.mid(k), st.mid(j))
    return SATIN_ADVANCE[0] <= adv <= SATIN_ADVANCE[1]


def _satins(st: _Stitches) -> list[Span]:
    out: list[Span] = []
    i = 0
    while i < st.n:
        if not _across(st, i):
            i += 1
            continue
        chain, steps, k = [i], 0, i
        while True:
            if _follows(st, k, k + 1):
                k += 1
            elif k + 2 < st.n and st.len[k + 1] < SATIN_STEP_MAX and _follows(st, k, k + 2):
                k += 2
                steps += 1
            else:
                break
            chain.append(k)
        if len(chain) >= SATIN_MIN:
            out.append(_satin_span(st, chain, steps))
            i = chain[-1] + 1
        else:
            i += 1
    return out


def _satin_span(st: _Stitches, chain: list[int], steps: int) -> Span:
    start, end = chain[0], chain[-1] + 2
    # Each point's side: a stitch across starts on side A when it is an even one in the chain.
    side: dict[int, int] = {}
    for j, c in enumerate(chain):
        side.setdefault(c, j % 2)
        side.setdefault(c + 1, 1 - j % 2)
    rail_a = [st.p[q] for q in range(start, end) if side.get(q) == 0]
    rail_b = [st.p[q] for q in range(start, end) if side.get(q) == 1]
    gaps = max(1, (len(rail_a) - 1) + (len(rail_b) - 1))
    spacing = (_length(rail_a) + _length(rail_b)) / gaps
    return Span("satin", start, end, spacing_mm=round(spacing, 4), rail_a=rail_a, rail_b=rail_b,
                stepped=2 * steps >= len(chain) - 1)


# ---------------------------------------------------------------- fill


@dataclass
class _Row:
    first: int  # point index
    last: int   # point index (inclusive)
    d: Point    # unit direction, first point to last


def _rows(st: _Stitches, lo: int, hi: int) -> list[_Row]:
    """Rows of stitches running one way, in the points [lo, hi)."""
    p = st.p
    rows: list[_Row] = []
    i = lo
    while i < hi - 1:
        if not ROW_START_MM <= st.len[i] <= ROW_STITCH_MAX:
            i += 1
            continue
        first, d = i, st.u[i]
        j = i + 1  # the next stitch to try
        while j < hi - 1:
            if st.len[j] > ROW_STITCH_MAX or not _with_row(st, j, d):
                break
            j += 1
            if _dist(p[first], p[j]) >= ROW_SURE_MM:
                d = _unit(p[first], p[j])
        last = j  # stitches first .. j - 1, so points first .. j
        # Short end pieces just before the first long stitch belong to the row too (never reaching
        # back into the row before).
        floor = rows[-1].last if rows else lo - 1
        while first - 1 > floor and st.len[first - 1] < ROW_SURE_MM and _with_row(st, first - 1, d):
            first -= 1
        if _dist(p[first], p[last]) >= ROW_MIN_MM:
            rows.append(_Row(first, last, _unit(p[first], p[last])))
        i = max(j, i + 1)
    return rows


def _with_row(st: _Stitches, j: int, d: Point) -> bool:
    """Stitch j runs on along a row going direction d."""
    if st.len[j] <= 1e-9:
        return True
    if st.len[j] >= ROW_SURE_MM:
        return _dot(st.u[j], d) >= COS_8
    return _dot(st.v[j], d) > 0 and abs(_cross(d, st.v[j])) <= ROW_TOL_MM


def _offset(st: _Stitches, row: _Row, n: Point) -> float:
    """Where a row lies across the rows (along n): the mean of its points, which evens out the
    machine's 0.1 mm grid."""
    return sum(_dot(st.p[q], n) for q in range(row.first, row.last + 1)) / (row.last - row.first + 1)


def _fills(st: _Stitches, lo: int, hi: int) -> list[Span]:
    rows = _rows(st, lo, hi)
    out: list[Span] = []
    k = 0
    while k < len(rows):
        chain = [rows[k]]
        n0 = (-rows[k].d[1], rows[k].d[0])  # across the rows, for the whole chain
        offs = [_offset(st, rows[k], n0)]
        nxt = k + 1
        while nxt < len(rows):
            a = chain[-1]
            # A single long stitch that doesn't run back (the move along a slanting edge to the
            # next row, in sparse rows) is part of the move, not a row.
            b = nxt
            while b < len(rows) and rows[b].last - rows[b].first == 1 and _dot(a.d, rows[b].d) > -COS_8 and                     rows[b].last - a.last < FILL_MOVE_STITCHES:
                b += 1
            if b >= len(rows):
                break
            r = rows[b]
            if _dot(a.d, r.d) > -COS_8 or _dot(r.d, chain[0].d) * (1 if len(chain) % 2 == 0 else -1) < COS_8:
                break
            moves = range(a.last, r.first)
            if r.first - a.last > FILL_MOVE_STITCHES or any(st.len[m] > ROW_STITCH_MAX for m in moves):
                break
            off = _offset(st, r, n0)
            step = off - offs[-1]
            if not FILL_STEP[0] <= abs(step) <= FILL_STEP[1]:
                break
            if len(offs) > 1:
                # Steady: the same way as before, and about as far as the steps so far on average.
                mean = (offs[-1] - offs[0]) / (len(offs) - 1)
                if step * mean <= 0 or not FILL_STEADY[0] <= step / mean <= FILL_STEADY[1]:
                    break
            chain.append(r)
            offs.append(off)
            nxt = b + 1
        if len(chain) >= FILL_ROWS:
            out.append(_fill_span(st, chain))
            k = nxt
        else:
            k += 1
    return out


def _fill_span(st: _Stitches, chain: list[_Row]) -> Span:
    p = st.p
    # The row direction: each row's angle, folded to within 90 degrees of the first, then the median.
    angles = []
    for r in chain:
        a = math.degrees(math.atan2(r.d[1], r.d[0]))
        while angles and a - angles[0] > 90:
            a -= 180
        while angles and a - angles[0] <= -90:
            a += 180
        angles.append(a)
    angle = round(_median(angles) % 180.0, 4) % 180.0
    rad = math.radians(angle)
    d = (math.cos(rad), math.sin(rad))
    n = (-d[1], d[0])
    offsets = [_offset(st, r, n) for r in chain]
    # From the first row to the last, not the median step: a machine's 0.1 mm grid makes single
    # steps come out uneven (at 45 degrees, 0.35 and 0.42 mm for 0.4), but they add up.
    spacing = abs(offsets[-1] - offsets[0]) / (len(offsets) - 1)
    advance = 1.0 if offsets[-1] >= offsets[0] else -1.0
    # Typical stitch length: the stitches inside rows, leaving out each row's end pieces.
    inner, every = [], []
    for r in chain:
        lens = [st.len[i] for i in range(r.first, r.last)]
        every += lens
        inner += lens[1:-1]
    stitch = _median(inner if len(inner) >= 3 else every)
    stitch = min(max(stitch, FILL_STITCH[0]), FILL_STITCH[1])
    lefts, rights = [], []
    for r in chain:
        a, b = p[r.first], p[r.last]
        lo_end, hi_end = (a, b) if _dot(a, d) <= _dot(b, d) else (b, a)
        lefts.append(lo_end)
        rights.append(hi_end)
    # The rows cover half a row past the first and last row's middles.
    half = advance * spacing / 2
    push = lambda q, k: (q[0] + n[0] * half * k, q[1] + n[1] * half * k)  # noqa: E731
    lefts[0], rights[0] = push(lefts[0], -1), push(rights[0], -1)
    lefts[-1], rights[-1] = push(lefts[-1], 1), push(rights[-1], 1)
    return Span("fill", chain[0].first, chain[-1].last + 1, angle_deg=angle, spacing_mm=round(spacing, 4),
                stitch_mm=round(stitch, 3), outline=lefts + rights[::-1])


# ---------------------------------------------------------------- run


def _runs(st: _Stitches, lo: int, hi: int) -> list[Span]:
    out: list[Span] = []
    i = lo
    while i < hi - 1:
        if not RUN_LEN[0] <= st.len[i] <= RUN_LEN[1]:
            i += 1
            continue
        j = i
        while j + 1 < hi - 1 and RUN_LEN[0] <= st.len[j + 1] <= RUN_LEN[1] and _dot(st.u[j], st.u[j + 1]) > COS_60:
            j += 1
        if j - i + 1 >= RUN_MIN:
            out.append(Span("run", i, j + 2, stitch_mm=round(_median(st.len[i:j + 1]), 3)))
            i = j + 2
        else:
            i += 1
    return out
