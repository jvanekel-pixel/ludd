"""Turning fills: a tatami fill with two or more angle lines, whose rows turn to follow each
line where it lies. Tatami hands over here (stitches._fill_part).

1. The lines are put in order along the principal axis of their middles. A line whose middle is
   under 1 mm from an earlier one's is left out (there is no room to turn), and the fill says so.
2. The guide: a smooth curve through each line's middle, running in that line's direction there
   (cubic Hermite), carried straight on past both ends beyond the shape.
3. Rows: curves parallel to the guide, (k + 1/2) x spacing to either side (each guide point moved
   along the guide's normal, with points added until they are at most SAMPLE_MM apart), as far as
   the furthest point of the outline (sampled every EDGE_STEP_MM).
4. Each row is clipped to the shape grown by half the Edge pad; pieces under MIN_STITCH_MM go.
5. Needle points every stitch length along each piece, shifted by the weave's offset for that
   row, measured from where the row crosses the guide's normal at the first line's middle (so a
   brick weave holds as the rows curve).
6. Rows are sewn in turn, alternating direction, grouped as tatami groups them; travel joins the
   groups inside the shape.
7. Where the guide turns tighter than a row is far from it, the row would loop back across its
   neighbors. Only the parts still that far from the whole guide are kept (the rows then meet in a
   crease), and where a cut part folded back more than FOLD_WARN_MM the fill says so.

Written for LUDD from the Phase 6 spec (no code ported from other projects).
"""

from __future__ import annotations

import bisect
import math
from typing import Sequence

import numpy as np
import shapely
from shapely.geometry import LineString

SAMPLE_MM = 0.25  # the guide is worked out at points about this far apart
SAG_MM = 0.04  # a stitch strays at most this far from its curved row
LOOP_TOL_MM = 0.05  # a row point this much nearer the guide than its row is part of a loop
EDGE_STEP_MM = 0.5  # how far apart the outline is sampled to find its furthest point from the guide
SAME_MIDDLE_MM = 1.0  # lines with middles nearer than this leave no room to turn between them
# Warn when a row cut away as a loop would have folded back more than this towards the guide
# (about four rows deep). A 30-degree fan over 20 mm folds 1.0 mm in a 50 x 30 mm shape; a
# 90-degree turn in 16 mm near the top of a 40 mm square, 2.5 mm. The length of row cut away
# can't tell those apart: the gentle fan's crease is the longer of the two (28 mm of row to 19).
FOLD_WARN_MM = 1.5
TOO_SHARP = ("The stitch direction turns too sharply for this shape here. Move the angle lines further apart or "
             "make the turn gentler.")
SAME_MIDDLE = ("Two angle lines have their middles in the same place, so the stitches follow the line drawn first "
               "and leave the other out. Move one of them at least 1 mm away to use both.")


def takes_over(params) -> bool:
    """Whether a fill is sewn as a turning fill: tatami with two or more angle lines."""
    return params.pattern == "tatami" and len(params.angle_lines) >= 2


def _r(v: float) -> float:
    """Rounded for a comparison or a choice, so the last digit of a sine never decides one."""
    return round(v, 6)


def _kept_lines(params) -> list:
    """The angle lines the rows follow: a line whose middle is under SAME_MIDDLE_MM from an
    earlier line's (in the order drawn) gives no room to turn between them, so it is left out."""
    kept: list = []
    for a, b in params.angle_lines:
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if all(_r(math.hypot(m[0] - k[0], m[1] - k[1])) >= SAME_MIDDLE_MM
               for k in (((c[0] + d[0]) / 2, (c[1] + d[1]) / 2) for c, d in kept)):
            kept.append((a, b))
    return kept


def mean_angle(params) -> float:
    """The rows' average direction, degrees 0 to 180: the cross-hatch underlay is sewn across it.
    Lines have no front or back, so 170 and 10 degrees average to 0."""
    if len(params.angle_lines) < 2:
        return params.angle_deg
    lines = _kept_lines(params)
    if len(lines) < 2:  # only the first line is followed
        (a, b), = lines
        return round(round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 9) % 180, 9)
    s = c = 0.0
    for a, b in lines:
        t = 2 * math.atan2(b[1] - a[1], b[0] - a[0])
        s, c = s + math.sin(t), c + math.cos(t)
    if round(s, 9) == 0 and round(c, 9) == 0:
        return params.angle_deg  # lines square to each other: no average direction
    return round(round(math.degrees(math.atan2(s, c)) / 2 % 180, 9) % 180, 9)


def _unit(v) -> np.ndarray:
    n = math.hypot(v[0], v[1])
    return np.array([v[0] / n, v[1] / n]) if n > 0 else np.array([1.0, 0.0])


def _ordered_lines(params) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """The lines' middles and directions, in order along the principal axis of the middles, each
    direction turned to run on from the one before."""
    lines = _kept_lines(params)
    mids = [np.array([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]) for a, b in lines]
    dirs = [_unit((b[0] - a[0], b[1] - a[1])) for a, b in lines]
    centre = sum(mids) / len(mids)
    sxx = sum(float((m - centre)[0] ** 2) for m in mids)
    syy = sum(float((m - centre)[1] ** 2) for m in mids)
    sxy = sum(float((m - centre)[0] * (m - centre)[1]) for m in mids)
    th = 0.5 * math.atan2(2 * sxy, sxx - syy)
    axis = np.array([math.cos(th), math.sin(th)])
    proj = [float((m - centre) @ axis) for m in mids]
    if _r(proj[0]) > _r(proj[-1]):  # the first line drawn comes first
        proj = [-p for p in proj]
    order = sorted(range(len(mids)), key=lambda i: (_r(proj[i]), i))
    mids, dirs = [mids[i] for i in order], [dirs[i] for i in order]
    for i, d in enumerate(dirs):
        chord = mids[i + 1] - mids[i] if i == 0 and len(mids) > 1 else mids[i] - mids[i - 1] if i else d
        lead = round(float(d @ dirs[i - 1]), 9) if i else 0.0
        if lead < 0 or (lead == 0 and round(float(d @ chord), 9) < 0):
            dirs[i] = -d
    return mids, dirs


def _guide_points(params, area) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """The guide: points (n x 2), unit normals at them (n x 2), distance along it (0 at the first
    line's middle) and the index of that point."""
    mids, dirs = _ordered_lines(params)
    x0, y0, x1, y1 = area.bounds
    corners = [np.array(p) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    reach = max(float(np.hypot(*(c - m))) for c in corners for m in (mids[0], mids[-1])) + 2.0
    pts: list[np.ndarray] = []
    tans: list[np.ndarray] = []
    steps = max(1, math.ceil(reach / SAMPLE_MM))
    for j in range(steps, 0, -1):  # carried straight on before the first line
        pts.append(mids[0] - dirs[0] * (reach * j / steps))
        tans.append(dirs[0])
    first = len(pts)
    for i in range(len(mids) - 1):
        m0, m1 = mids[i], mids[i + 1]
        chord = float(np.hypot(*(m1 - m0)))
        if chord < 1e-6:
            continue
        # Tangents a little longer than the chord as the direction turns, so that between two lines
        # turned evenly the guide is (very nearly) a circular arc: the same bend all along, rather
        # than tighter at the lines (cubic Bezier arcs: handles (4/3) tan(turn / 4) of the radius).
        turn = min(math.acos(max(-1.0, min(1.0, float(dirs[i] @ dirs[i + 1])))), math.radians(170))
        scale = 2 * math.tan(turn / 4) / math.sin(turn / 2) if turn > 1e-6 else 1.0
        t0, t1 = dirs[i] * chord * scale, dirs[i + 1] * chord * scale
        n = max(8, math.ceil(2 * chord / SAMPLE_MM))
        for j in range(n):
            u = j / n
            h00, h10, h01, h11 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
            d00, d10, d01, d11 = 6 * u**2 - 6 * u, 3 * u**2 - 4 * u + 1, -6 * u**2 + 6 * u, 3 * u**2 - 2 * u
            pts.append(h00 * m0 + h10 * t0 + h01 * m1 + h11 * t1)
            tan = d00 * m0 + d10 * t0 + d01 * m1 + d11 * t1
            tans.append(_unit(tan) if math.hypot(*tan) > 1e-9 else dirs[i])
    for j in range(0, steps + 1):  # and after the last
        pts.append(mids[-1] + dirs[-1] * (reach * j / steps))
        tans.append(dirs[-1])
    p = np.array(pts)
    t = np.array(tans)
    normals = np.column_stack([-t[:, 1], t[:, 0]])
    along = np.concatenate([[0.0], np.cumsum(np.hypot(*(p[1:] - p[:-1]).T))])
    return p, normals, along - along[first], first


def guide(params, area) -> LineString:
    """The guide curve the rows run beside, for a fill with these angle lines over `area`."""
    return LineString(_guide_points(params, area)[0])


def _off_chord(p, a, b) -> float:
    """How far point p lies from the straight stitch a-b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    return abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / n


def _crossing(inside_pt: np.ndarray, outside_pt: np.ndarray, edge) -> np.ndarray:
    """Where the step from a point inside the zone to one outside it crosses the zone's edge: the
    crossing nearest the inside point."""
    hit = LineString([inside_pt, outside_pt]).intersection(edge)
    found = [np.array(g.coords[0]) for g in getattr(hit, "geoms", [hit]) if not g.is_empty and g.geom_type == "Point"]
    if not found:
        return inside_pt
    return min(found, key=lambda q: (_r(float(np.hypot(*(q - inside_pt)))), _r(float(q[0])), _r(float(q[1]))))


def _row(p: np.ndarray, normals: np.ndarray, s: np.ndarray, offset: float):
    """The row `offset` from the guide, with points added until they are at most SAMPLE_MM apart
    (on the outside of a bend the guide's own points spread out): (points, guide distance at each,
    index of each guide point among them). Between two guide points the row point moves straight
    and its normal turns evenly, so a row round a corner stays `offset` from it."""
    q = p + normals * offset
    d = np.hypot(*(q[1:] - q[:-1]).T)
    m = np.maximum(1, np.ceil(np.round(d / SAMPLE_MM, 6))).astype(int)
    first = np.concatenate([[0], np.cumsum(m)])  # where each guide point lands among the row's
    if int(first[-1]) == len(m):  # no points to add
        return q, s, first
    seg = np.repeat(np.arange(len(m)), m)
    t = ((np.arange(int(first[-1])) - first[:-1][seg]) / m[seg])[:, None]
    nn = normals[seg] * (1 - t) + normals[seg + 1] * t
    nn /= np.hypot(nn[:, 0], nn[:, 1])[:, None]
    dense = np.vstack([p[seg] + (p[seg + 1] - p[seg]) * t + nn * offset, q[-1:]])
    sd = np.concatenate([s[seg] + (s[seg + 1] - s[seg]) * t[:, 0], s[-1:]])
    return dense, sd, first


def _row_pieces(q: np.ndarray, inside: np.ndarray, edge, along: np.ndarray, from_stitches):
    """The pieces of a row inside the zone: (distance along the row where it starts, where it
    ends, guide distance at its start and end, the row's own points between) in order along it."""
    out = []
    n = len(q)
    i = 0
    while i < n:
        if not inside[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and inside[j + 1]:
            j += 1
        start = _crossing(q[i], q[i - 1], edge) if i > 0 else q[i]
        end = _crossing(q[j], q[j + 1], edge) if j + 1 < n else q[j]
        a0 = float(along[i] - np.hypot(*(q[i] - start)))
        a1 = float(along[j] + np.hypot(*(end - q[j])))
        if _r(a1 - a0) > from_stitches.MIN_STITCH_MM:
            out.append((a0, a1, i, j, [tuple(start), *map(tuple, q[i:j + 1]), tuple(end)]))
        i = j + 1
    return out


def rows(poly, params, start, travel_within=None, end_near=None) -> tuple[list, list[str]]:
    """The top stitching of one piece of a turning fill: (records, warnings). `start`: where the
    needle is; travel stays inside `travel_within`; `end_near`: finish as near this point as the
    rows allow (the row end nearest it)."""
    from .. import rows as row_hooks
    from .. import stitches as st
    from ..paths import dist

    angle = mean_angle(params)
    hooks = row_hooks.hooks(params, angle)
    said: list[str] = []
    offsets = hooks.get("offsets")
    random = hooks.get("random", params.random_pct / 100)
    end_shift = hooks.get("end_shift")
    spacing, stitch, pad = params.spacing_mm, params.stitch_mm, params.pull_comp_mm / 2
    zone = poly.buffer(pad) if pad > 0 else poly
    shapely.prepare(zone)
    edge = zone.boundary
    if len(_kept_lines(params)) < len(params.angle_lines):
        said.append(SAME_MIDDLE)
    p, normals, s, ref = _guide_points(params, zone)
    guide_line = LineString(p)
    # As far as the furthest point of the outline (the middle of an edge can be further than
    # any corner), and of any hole's edge.
    rings = [zone.exterior, *zone.interiors]
    edge_pts = np.vstack([shapely.get_coordinates(shapely.segmentize(r, EDGE_STEP_MM)) for r in rings])
    far = float(shapely.distance(guide_line, shapely.points(edge_pts)).max()) + spacing
    shapely.prepare(guide_line)  # the loop check below asks "within this distance?" of many points

    found: dict[int, list] = {}
    row_s: dict[int, np.ndarray] = {}
    too_sharp = False  # a loop cut away folds back more than FOLD_WARN_MM towards the guide
    for side in (1, -1):
        k = 0 if side > 0 else -1
        while True:
            offset = (k + 0.5) * spacing
            if abs(offset) > far:
                break
            q, sq, at_guide = _row(p, normals, s, offset)
            inside = shapely.contains_xy(zone, q[:, 0], q[:, 1])
            if inside.any():
                # Cut away the loops: points nearer another part of the guide than this row is.
                at = np.flatnonzero(inside)
                short = shapely.dwithin(guide_line, shapely.points(q[at]), abs(offset) - LOOP_TOL_MM)
                if short.any():
                    cut = at[short]
                    if not too_sharp and abs(offset) > FOLD_WARN_MM:
                        too_sharp = bool(shapely.dwithin(guide_line, shapely.points(q[cut]),
                                                         _r(abs(offset) - FOLD_WARN_MM)).any())
                    inside = inside.copy()
                    inside[cut] = False
                if inside.any():
                    along = np.concatenate([[0.0], np.cumsum(np.hypot(*(q[1:] - q[:-1]).T))])
                    found[k] = _row_pieces(q, inside, edge, along - along[at_guide[ref]], st)
                    row_s[k] = sq
            k += side
    if too_sharp:
        said.append(TOO_SHARP)
    keys = sorted(k for k, pieces in found.items() if pieces)
    if not keys:
        top = st.tatami(poly, angle, spacing, stitch, pad, start, travel_within=travel_within, end_near=end_near)
        return top, [*row_hooks.notes(params, angle), *said]
    # The rows' own warnings, judged against the curved rows themselves.
    said = [*row_hooks.notes(params, angle, [path for k in keys for *_, path in found[k]]), *said]
    reach = 0.0  # how far a row end has been moved outwards (the hand-sewn look)

    def needle_points(k: int, a0: float, a1: float, path) -> list[tuple[float, float]]:
        nonlocal reach
        path_start, path_end = a0, a1
        if end_shift is not None:
            a0, a1 = st._shifted_ends(end_shift, k, a0, a1)
            reach = max(reach, path_start - a0, a1 - path_end)
        forced = ()
        if params.carve:
            forced = [path_start + d for d in row_hooks.carve.crossings_along(params.carve, path)]
        shift = (k % 3) * stitch / 3 if offsets is None else offsets(k) * stitch
        xs = [x for x, _ in st._row_stitches(a0, a1, 0.0, stitch, shift, True, random, k, forced, steady=True)]
        line_along = [path_start]
        for u, v in zip(path, path[1:]):
            line_along.append(line_along[-1] + dist(u, v))
        at_along = np.array(line_along)
        px, py = np.array([u[0] for u in path], dtype=float), np.array([u[1] for u in path], dtype=float)

        def at(x: float) -> tuple[float, float]:
            """The point `x` along the row; past an end (a feathered edge) the row runs straight on."""
            if line_along[0] <= x <= line_along[-1] or len(path) < 2:
                return float(np.interp(x, at_along, px)), float(np.interp(x, at_along, py))
            u, v, base = (path[0], path[1], line_along[0]) if x < line_along[0] else (path[-2], path[-1], line_along[-1])
            d = _unit((v[0] - u[0], v[1] - u[1]))
            end_pt = path[0] if x < line_along[0] else path[-1]
            return end_pt[0] + d[0] * (x - base), end_pt[1] + d[1] * (x - base)

        # A stitch is straight and the row curves: where a stitch would stray more than SAG_MM
        # from the row, it is split evenly (rows stay their spacing apart all along the turn).
        fine = [xs[0]]
        for xa, xb in zip(xs, xs[1:]):
            pa, pb = at(xa), at(xb)
            lo, hi = bisect.bisect_right(line_along, xa), bisect.bisect_left(line_along, xb)
            sag = max((_off_chord(path[m], pa, pb) for m in range(lo, hi)), default=0.0)
            if _r(sag) > SAG_MM:
                n = math.ceil(round(math.sqrt(sag / SAG_MM), 6))
                fine += [xa + (xb - xa) * i / n for i in range(1, n)]
            fine.append(xb)
        return [at(x) for x in fine]

    # The pieces: per row, in order along it, with their guide distances for grouping.
    pieces = {}
    for k in keys:
        for idx, (a0, a1, i, j, path) in enumerate(found[k]):
            pieces[(k, idx)] = (float(row_s[k][i]), float(row_s[k][j]), needle_points(k, a0, a1, path))
    unvisited = set(pieces)
    regions: list[list[tuple[int, int]]] = []
    while unvisited:
        cur = min(unvisited)
        region = [cur]
        unvisited.discard(cur)
        while True:
            s0, s1, pts = pieces[cur]
            nxt = sorted(c for c in unvisited if c[0] == cur[0] + 1)
            nxt = [c for c in nxt if pieces[c][0] < s1 and pieces[c][1] > s0
                   and _r(abs(pieces[c][0] - s0)) <= stitch and _r(abs(pieces[c][1] - s1)) <= stitch]
            if not nxt:
                break
            cur = nxt[0]
            region.append(cur)
            unvisited.discard(cur)
        regions.append(region)

    def region_points(region, forward: bool) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for c in region:
            row = pieces[c][2] if forward else pieces[c][2][::-1]
            if out and dist(out[-1], row[0]) > stitch:
                out += st._subdivide([out[-1], row[0]], stitch)[1:-1]
            out += row
            forward = not forward
        return out

    options = []
    for reg in regions:
        f, b = region_points(reg, True), region_points(reg, False)
        options.append([f, f[::-1], b, b[::-1]])
    inside_zone = st.Zone((travel_within or poly).buffer(pad + 0.05 + reach))  # as far as ends went
    min_step = st._min_step(spacing)
    remaining = list(range(len(options)))
    last = None
    if end_near is not None:
        last, v = min(((k, v) for k in remaining for v in range(4)),
                      key=lambda kv: (_r(dist(options[kv[0]][kv[1]][-1], end_near)), kv))
        options[last] = [options[last][v]]
        remaining.remove(last)
    out: list = []
    pos = start
    while remaining or last is not None:
        if remaining:
            k, v = min(((k, v) for k in remaining for v in range(len(options[k]))),
                       key=lambda kv: (_r(dist(pos, options[kv[0]][kv[1]][0])) if pos is not None else 0.0, kv))
            remaining.remove(k)
        else:
            k, v, last = last, 0, None
        seq = options[k][v]
        if out:
            out += st.travel(pos, seq[0], inside_zone)
        st._append(out, st.stitch_run(seq, min_step))
        pos = seq[-1]
    return out, said


__all__: Sequence[str] = ("SAME_MIDDLE", "TOO_SHARP","guide", "mean_angle", "rows", "takes_over")
