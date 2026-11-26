"""Slant and envelopes: maps that bend the letters (P5-A2 and P5-A3).

Both work on letter parts in the text's own frame (mm, y down).

  slant     each letter is sheared about its own baseline before it is placed: points keep their
            height and move sideways by -y tan(slant), so a positive slant leans the tops right.
  envelope  the laid-out text is reshaped inside its box [x0, x1] x [y0, y1]: x stays, and y moves
            by how far along the box x is (u = 0 at its left side, 1 at its right).

An envelope curves straight lines, so outlines and lines are first cut into pieces SEGMENT_MM long,
and satin columns get new rungs, placed so their stitches stay as close together as they were.
Letters made of stitches only have their needle points moved: no stitches are added.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from shapely.geometry import Polygon

from ..digitize import stitches as dz
from ..digitize.paths import cumulative, flatten, point_at
from .glyphs import _satin_angle

PointMap = Callable[[float, float], tuple[float, float]]

ENVELOPES = ("bulge", "pinch", "pennant_right", "pennant_left", "wave", "arch_top", "arch_bottom")
DEFAULT_AMOUNT = 0.5
SLANT_LIMIT_DEG = 30.0
SEGMENT_MM = 1.0  # outlines are cut this short before an envelope, so a straight stem can bend
SAMPLE_MM = 0.25  # how finely a satin column is traced to place its new rungs


def part_points(obj: dict[str, Any]) -> list[tuple[float, float]]:
    """The points round a letter part, curves traced (for stitched letters, where they sew)."""
    g = obj.get("geometry") or {}
    if obj.get("kind") == "stitches":
        nodes = g.get("nodes") or []
        sewn = [n for n in nodes if len(n) < 3 or n[2] == "s"]
        return [(float(n[0]), float(n[1])) for n in sewn or nodes]
    out: list[tuple[float, float]] = []
    for key, closed in (("outline", True), ("nodes", bool(g.get("closed"))), ("rail_a", False), ("rail_b", False)):
        if g.get(key):
            out += flatten(g[key], closed)[0]
    for hole in g.get("holes") or []:
        out += flatten(hole, True)[0]
    return out


# ---------------------------------------------------------------- moving points and angles


def _node(move: PointMap, n) -> list:
    """A node moved (to 0.001 mm), keeping its kind (a point's, or a stitched letter's)."""
    x, y = move(float(n[0]), float(n[1]))
    return [round(x, 3), round(y, 3), *n[2:]]


def _moved_params(params: dict[str, Any], move: PointMap) -> dict[str, Any]:
    """A stitch font letter's chosen start and end move with it."""
    out = dict(params)
    for key in ("start_mm", "end_mm"):
        point = dz._start_point(out.get(key))
        if point is not None:
            out[key] = [round(v, 3) for v in move(*point)]
    return out


def _mapped(obj: dict[str, Any], move: PointMap) -> dict[str, Any]:
    """Every point of a letter part moved, with no points added."""
    g = dict(obj.get("geometry") or {})
    for key in ("nodes", "rail_a", "rail_b", "outline"):
        if g.get(key):
            g[key] = [_node(move, n) for n in g[key]]
    if g.get("holes"):
        g["holes"] = [[_node(move, n) for n in hole] for hole in g["holes"]]
    out = {**obj, "geometry": g}
    if obj.get("params") is not None:
        out["params"] = _moved_params(obj["params"], move)
    return out


def _line_angle(dx: float, dy: float) -> float:
    """The stitch angle (0 to 180 degrees) of rows running along (dx, dy)."""
    deg = round(math.degrees(math.atan2(dy, dx)) % 180.0, 3)
    return 0.0 if deg >= 180.0 else deg


def _fill_angle(obj: dict[str, Any]) -> float:
    value = (obj.get("params") or {}).get("angle_deg")
    return float(dz.FillParams.angle_deg if value is None else value)


def carried_angle(angle_deg: float, move: PointMap, at: tuple[float, float], reach_mm: float = 0.5) -> float:
    """Where `move` takes rows at `angle_deg` around the point `at` (exact for a slant)."""
    a = math.radians(angle_deg)
    dx, dy = math.cos(a) * reach_mm, math.sin(a) * reach_mm
    start, end = move(at[0] - dx, at[1] - dy), move(at[0] + dx, at[1] + dy)
    return _line_angle(end[0] - start[0], end[1] - start[1])


def chosen_angle(obj: dict[str, Any]) -> float:
    """The satin-look angle for a fill's shape as it is now (glyphs._satin_angle). The shape is
    measured from its own corner, to 0.001 mm, so the same letter gets the same angle wherever it
    sits, on every computer."""
    g = obj.get("geometry") or {}
    shell = flatten(g.get("outline") or [], True)[0]
    if len(shell) < 3:  # nothing to measure (the stitcher skips such a speck)
        return _fill_angle(obj)
    x0, y0 = min(p[0] for p in shell), min(p[1] for p in shell)

    def local(ring):
        return [(round(x - x0, 3), round(y - y0, 3)) for x, y in ring]

    outer = local(shell)
    holes = [local(flatten(h, True)[0]) for h in g.get("holes") or [] if len(h) >= 3]
    shape = Polygon(outer, holes)
    if not shape.is_valid:
        parts = dz.valid_parts(outer, holes)
        if not parts:
            return _fill_angle(obj)
        # The biggest piece; pieces as big as each other: the one highest and furthest left.
        shape = min(parts, key=lambda p: (-round(p.area, 2), [round(v, 2) for v in (p.bounds[1], p.bounds[0])]))
    return _satin_angle(shape)


def _with_angle(obj: dict[str, Any], angle: float) -> dict[str, Any]:
    return {**obj, "params": {**(obj.get("params") or {}), "angle_deg": angle}}


# ---------------------------------------------------------------- slant


def _shear(deg: float) -> PointMap:
    k = math.tan(math.radians(deg))
    return lambda x, y: (x - y * k, y)


def slant_shape(deg: float) -> Callable[[Polygon], Polygon]:
    """An outline letter's shape sheared about its baseline (for glyphs._outline_glyphs)."""
    move = _shear(deg)

    def ring(coords):
        return [tuple(round(v, 6) for v in move(x, y)) for x, y in coords]

    return lambda shape: Polygon(ring(shape.exterior.coords), [ring(h.coords) for h in shape.interiors])


def lean_satin_look(obj: dict[str, Any], deg: float) -> dict[str, Any]:
    """A slanted satin-look letter sewn at the angle chosen for it upright, leaned with it, so its
    stitches stay square across the leaning strokes. (Chosen on the sheared shape alone, a leaning
    bar would keep flat rows: they're as short across it as across an upright one.)"""
    if obj.get("kind") != "fill":
        return obj
    upright = _mapped(obj, _shear(-deg))
    return _with_angle(obj, round((chosen_angle(upright) + deg) % 180.0, 3))


def slant_object(obj: dict[str, Any], deg: float) -> dict[str, Any]:
    """A stitch font's letter part sheared about its baseline, a fill's stitch angle with it."""
    move = _shear(deg)
    out = _mapped(obj, move)
    return _with_angle(out, carried_angle(_fill_angle(obj), move, (0.0, 0.0))) if obj.get("kind") == "fill" else out


# ---------------------------------------------------------------- envelopes


def envelope_map(kind: str, amount: float, box: tuple[float, float, float, float]) -> PointMap:
    """The envelope `kind` at `amount` (0 to 1) over the text's `box` (x0, y0, x1, y1; y down)."""
    x0, y0, x1, y1 = box
    wide, tall, middle = x1 - x0, y1 - y0, (y0 + y1) / 2

    def move(x: float, y: float) -> tuple[float, float]:
        u = min(1.0, max(0.0, (x - x0) / wide))
        swell = math.sin(math.pi * u)  # nothing at the sides, most in the middle
        if kind == "bulge":
            return x, middle + (y - middle) * (1 + 0.8 * amount * swell)
        if kind == "pinch":
            return x, middle + (y - middle) * (1 - 0.6 * amount * swell)
        if kind == "pennant_right":
            return x, middle + (y - middle) * (1 - 0.7 * amount * u)
        if kind == "pennant_left":
            return x, middle + (y - middle) * (1 - 0.7 * amount * (1 - u))
        if kind == "wave":
            return x, y + 0.35 * amount * tall * math.sin(2 * math.pi * u)
        if kind == "arch_top":
            return x, y1 - (y1 - y) * (1 + 0.8 * amount * swell)
        return x, y0 + (y - y0) * (1 + 0.8 * amount * swell)  # arch_bottom

    return move


def _bent_ring(nodes: list, move: PointMap) -> list:
    """A fill's outline or hole, cut short and bent: straight pieces between its new points."""
    ring = flatten(nodes, True)[0]
    if len(ring) > 1:
        ring = ring[:-1]  # flatten() ends a closed ring where it began
    cut = dz._subdivide([*ring, ring[0]], SEGMENT_MM)[:-1]
    return [_node(move, (x, y, "c")) for x, y in cut]


def _bent_line(nodes: list, closed: bool, move: PointMap) -> list:
    """A running line or a satin ribbon's middle line, cut short and bent. Your own sharp points
    stay sharp; the new points are smooth ones, so stitches don't have to land on them."""
    poly, at = flatten(nodes, closed)
    if closed and len(poly) > 1:
        poly = poly[:-1]
    sharp = {i: (n[2] if len(n) > 2 else "c") for n, i in zip(nodes, at) if not (len(n) > 2 and n[2] == "s")}
    ends = [*poly, poly[0]] if closed else poly
    out = []
    for i, (a, b) in enumerate(zip(ends, ends[1:])):
        for j, (x, y) in enumerate(dz._subdivide([a, b], SEGMENT_MM)[:-1]):
            out.append(_node(move, (x, y, sharp.get(i, "s") if j == 0 else "s")))
    if not closed:
        out.append(_node(move, (*poly[-1], sharp.get(len(poly) - 1, "s"))))
    return out


def _bent_column(rail_a: list, rail_b: list, spacing: float, move: PointMap) -> tuple[list, list]:
    """A satin column bent. Each pair of points (a[k], b[k]) is a rung, and between rungs both
    sides are walked at the same pace (digitize.satin_pairs). Each stretch between two rungs is
    traced finely, bent, and given new rungs a whole number of stitches apart, at most about
    SEGMENT_MM: the stitches cross as before and stay as close together."""
    a_line, a_at = flatten(rail_a)
    b_line, b_at = flatten(rail_b)
    out_a: list = []
    out_b: list = []
    for k in range(len(rail_a) - 1):
        a, b = a_line[a_at[k] : a_at[k + 1] + 1], b_line[b_at[k] : b_at[k + 1] + 1]
        a_len, b_len = cumulative(a), cumulative(b)
        fine = max(2, math.ceil(max(a_len[-1], b_len[-1]) / SAMPLE_MM - 1e-6))
        bent_a = [move(*point_at(a, a_len, a_len[-1] * i / fine)) for i in range(fine + 1)]
        bent_b = [move(*point_at(b, b_len, b_len[-1] * i / fine)) for i in range(fine + 1)]
        along = [0.0]  # measured as the stitcher measures it: the mean of the two sides
        for i in range(fine):
            along.append(along[-1] + (math.dist(bent_a[i], bent_a[i + 1]) + math.dist(bent_b[i], bent_b[i + 1])) / 2)
        total = along[-1]
        # A little under the spacing each, so rounding can't add a stitch between two rungs.
        count = max(1, math.ceil(total / max(spacing - 0.003, 0.1) - 1e-6))
        each = max(1, int(SEGMENT_MM * count / total + 1e-6)) if total > 0 else count
        for j in [*range(0, count, each), count]:
            if k and j == 0:
                continue  # the rung the stretch before ended on
            s = total * j / count
            for side, bent in ((out_a, bent_a), (out_b, bent_b)):
                side.append([*(round(v, 3) for v in point_at(bent, along, s)), "c"])
    return out_a, out_b


def bend_object(obj: dict[str, Any], move: PointMap) -> dict[str, Any]:
    """A letter part bent by `move`: outlines, lines and columns cut short first."""
    g = obj.get("geometry") or {}
    if obj.get("kind") == "stitches":
        return _mapped(obj, move)  # only the needle points move: no stitches are added
    new = dict(g)
    if g.get("outline"):
        new["outline"] = _bent_ring(g["outline"], move)
    if g.get("holes"):
        new["holes"] = [_bent_ring(h, move) if len(h) >= 3 else [_node(move, n) for n in h] for h in g["holes"]]
    if g.get("nodes"):
        new["nodes"] = _bent_line(g["nodes"], bool(g.get("closed")), move)
    rail_a, rail_b = g.get("rail_a") or [], g.get("rail_b") or []
    if len(rail_a) == len(rail_b) >= 2:
        spacing = float((obj.get("params") or {}).get("spacing_mm") or dz.SatinParams.spacing_mm)
        new["rail_a"], new["rail_b"] = _bent_column(rail_a, rail_b, spacing, move)
    elif rail_a or rail_b:  # uneven sides: moved as they are, and the stitcher says what's wrong
        new["rail_a"], new["rail_b"] = [_node(move, n) for n in rail_a], [_node(move, n) for n in rail_b]
    out = {**obj, "geometry": new}
    if obj.get("params") is not None:
        out["params"] = _moved_params(obj["params"], move)
    return out


def bend(objects: list[dict[str, Any]], kind: str, amount: float, angles: str = "keep") -> list[dict[str, Any]]:
    """The laid-out letter parts bent into the envelope. `angles` says what happens to a fill's
    stitch angle: "choose" it again for the new shape (satin-look letters), "carry" it through the
    bend (a stitch font's own rows), or "keep" it (woven letters)."""
    points = [p for o in objects for p in part_points(o)]
    if not points or amount <= 0:
        return objects
    box = dz.bounds(points)
    if box[2] - box[0] < 1e-6 or box[3] - box[1] < 1e-6:
        return objects  # nothing wide or tall enough to bend
    move = envelope_map(kind, amount, box)
    out = []
    for o in objects:
        bent = bend_object(o, move)
        if bent.get("kind") == "fill" and angles == "choose":
            bent = _with_angle(bent, chosen_angle(bent))
        elif bent.get("kind") == "fill" and angles == "carry" and part_points(o):
            x0, y0, x1, y1 = dz.bounds(part_points(o))
            bent = _with_angle(bent, carried_angle(_fill_angle(o), move, ((x0 + x1) / 2, (y0 + y1) / 2)))
        out.append(bent)
    return out
