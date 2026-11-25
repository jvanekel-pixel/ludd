"""Layout extras: the basting box, knockdown stitching and the applique cut file."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import pyembroidery as pe
from shapely.geometry import LineString
from shapely.ops import unary_union

from ..digitize import stitches as dz
from .model import Block, LayoutError, Rec, Transform, _stitch_bounds


BASTING_STITCH_MM = 4.0
BASTING_MIN_MM = 2.0  # the box keeps at least this far from the design, even to fit the hoop
BASTING_THREAD = {"color": "#9e9e9e", "name": "Basting", "catalog": "", "brand": ""}


def _basting(blocks: list[Block], margin_mm: float) -> Block | None:
    bounds = [_stitch_bounds(b.recs) for b in blocks]
    bounds = [b for b in bounds if b]
    if not bounds:
        return None
    m = margin_mm * 10
    x0 = min(b[0] for b in bounds) - m
    y0 = min(b[1] for b in bounds) - m
    x1 = max(b[2] for b in bounds) + m
    y1 = max(b[3] for b in bounds) + m
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    step = BASTING_STITCH_MM * 10
    recs: list[Rec] = [[x0, y0, pe.JUMP, -1, -1], [x0, y0, pe.STITCH, -1, -1]]
    for (ax, ay), (bx, by) in zip(corners, corners[1:]):
        n = max(1, math.ceil(math.hypot(bx - ax, by - ay) / step))
        for i in range(1, n + 1):
            recs.append([ax + (bx - ax) * i / n, ay + (by - ay) * i / n, pe.STITCH, -1, -1])
    recs.append([x0, y0, pe.TRIM, -1, -1])
    return Block(dict(BASTING_THREAD), recs, [])


# ---------------------------------------------------------------- knockdown

KNOCKDOWN_THREAD = {"color": "#f2efe8", "name": "Knockdown (match the fabric)", "catalog": "", "brand": ""}
KNOCKDOWN_SPACING_MM = 2.0


def _stitched_area(blocks: list[Block]):
    """The area the design covers: its stitches, thickened and closed up (holes in letters stay)."""
    lines = []
    for b in blocks:
        run: list[tuple[float, float]] = []
        for r in b.recs:
            if r[2] == pe.STITCH:
                run.append((r[0] / 10, r[1] / 10))
                continue
            if len(run) > 1:
                lines.append(LineString(run))
            run = []
        if len(run) > 1:
            lines.append(LineString(run))
    if not lines:
        return None
    return unary_union([ln.simplify(0.1).buffer(0.8, quad_segs=2) for ln in lines]).buffer(-0.5, quad_segs=2)


def _knockdown(blocks: list[Block], margin_mm: float, thread: dict[str, str] | None) -> Block | None:
    """A light grid of stitches under the design that flattens towel loops and fleece pile, so the
    design sits on top instead of sinking. Sewn first, in a thread matching the fabric."""
    area = _stitched_area(blocks)
    if area is None or area.is_empty:
        return None
    area = area.buffer(margin_mm, quad_segs=4).simplify(0.2)
    parts = list(area.geoms) if area.geom_type == "MultiPolygon" else [area]
    mm: list = []
    pos = None
    for poly in parts:
        if poly.area < 4:
            continue
        for angle in (45.0, -45.0):
            sts = dz.tatami(poly, angle, KNOCKDOWN_SPACING_MM, 4.0, 0.0, pos)
            if not sts:
                continue
            if pos is not None:
                mm += dz.travel(pos, (sts[0][0], sts[0][1]), poly)
            mm += sts
            pos = (sts[-1][0], sts[-1][1])
    if not mm:
        return None
    recs = [[x * 10, y * 10, k, -1, -1] for x, y, k in dz.tie_off(dz.tie_in(mm))]
    return Block({**KNOCKDOWN_THREAD, **(thread or {})}, recs, [])


# ---------------------------------------------------------------- applique cut file


def applique_svg(layout: dict[str, Any]) -> tuple[str, int]:
    """An SVG of every applique piece's cutting line, real size in millimetres, for cutting
    machines (Cricut, ScanNCut, Silhouette) or to print and cut by hand."""
    from ..digitize.applique import cut_rings

    paths = []
    for idx, it in enumerate(layout.get("items") or []):
        if it.get("kind") != "applique":
            continue
        pts = dz.geometry_points(it)
        x0, y0, x1, y1 = dz.bounds(pts)
        t = Transform.from_dict(it.get("transform"))
        obj = it if t.is_identity() else dz.transform_geometry(it, t, ((x0 + x1) / 2, (y0 + y1) / 2))
        g = obj.get("geometry") or {}
        name = it.get("name") or f"Applique {idx + 1}"
        paths.append((name, cut_rings(g.get("outline") or [], g.get("holes") or [])))
    if not paths:
        raise LayoutError("There are no applique pieces in this design")
    xs = [p[0] for _, rs in paths for r in rs for p in r]
    ys = [p[1] for _, rs in paths for r in rs for p in r]
    m = 5.0
    ox, oy = min(xs) - m, min(ys) - m
    w, h = max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m
    body = []
    for name, rs in paths:
        # One path per piece: its outline and a sub-path for each hole (cut on every line).
        d = " ".join("M" + " L".join(f"{x - ox:.2f},{y - oy:.2f}" for x, y in ring) + " Z" for ring in rs)
        body.append(f'  <path d="{d}" fill="none" fill-rule="evenodd" stroke="#000" stroke-width="0.25"><title>{_xml(name)}</title></path>')
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" height="{h:.2f}mm" viewBox="0 0 {w:.2f} {h:.2f}">'
    note = "  <!-- Applique cutting lines from LUDD, real size. Cut on the lines. -->"
    svg = "\n".join([head, note, *body, "</svg>"]) + "\n"
    return svg, len(paths)


def _xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_applique_svg(layout: dict[str, Any], dest: str) -> dict[str, Any]:
    svg, n = applique_svg(layout)
    d = Path(dest)
    if d.suffix.lower() != ".svg":
        d = d.with_name(d.name + ".svg")
    # Written whole or not at all: a failure part-way leaves an earlier file as it was.
    tmp = d.with_name(f".{d.stem}.part{d.suffix}")
    try:
        tmp.write_text(svg, encoding="utf-8")
        os.replace(tmp, d)
    except OSError as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise LayoutError(f"Couldn't save {d.name}: {exc.strerror or exc}") from exc
    return {"path": str(d), "pieces": n}
