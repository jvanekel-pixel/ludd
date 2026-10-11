"""Layouts: one or more stitch files placed together and edited without touching the files.

A layout is plain JSON (the UI keeps it and its undo history):

    {
      "items": [{
        "id": "a1", "path": "C:/designs/key.pes",
        "transform": {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": false, "flip_y": false},
        "threads": [null, {"color": "#123456", "name": "Navy", "catalog": "1043", "brand": "Madeira Rayon"}],
        "ops": [{"op": "delete_block", "block": 2}, {"op": "insert", "after": 120, "command": "stop"}]
      }],
      "merge_colors": false, "color_sort": false,
      "basting": {"enabled": false, "margin_mm": 5}
    }

Indices in ops and `threads` refer to the item's source file, so edits never shift each other.
Rendering returns the usual design summary plus, per record, which item and source record
it came from, so the UI can map a click or the player position back to an edit.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyembroidery as pe
from shapely.geometry import LineString
from shapely.ops import unary_union

from . import design, fabrics, kept, lettering, quality, split
from .digitize import stitches as dz
from .prepare import Options, prepare, write_settings

M = pe.COMMAND_MASK
SCALE_WARN = 0.20  # warn when an item is scaled more than ±20%
BASTING_STITCH_MM = 4.0
BASTING_THREAD = {"color": "#9e9e9e", "name": "Basting", "catalog": "", "brand": ""}

# A record while building: x, y (0.1 mm), command, item index (-1 = layout), source record index (-1 = added).
Rec = list


class LayoutError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- source cache

_cache: dict[str, tuple[float, pe.EmbPattern]] = {}


def _load(path: str) -> pe.EmbPattern:
    """Load a stitch file, cached until it changes on disk."""
    p = Path(kept.readable(path))
    try:
        mtime = p.stat().st_mtime
    except OSError as exc:
        raise LayoutError(f"File not found: {Path(path).name}. It may have been moved or deleted.") from exc
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    pattern = design.load(p)
    if str(p) == str(path):
        # Keep a private copy, so the design survives the original being moved or deleted.
        try:
            kept.keep(path, p.read_bytes())
        except OSError:
            pass
    _cache[path] = (mtime, pattern)
    return pattern


# ---------------------------------------------------------------- model


@dataclass
class Transform:
    x: float = 0.0  # mm
    y: float = 0.0
    rotate: float = 0.0  # degrees, clockwise on screen
    scale_x: float = 1.0
    scale_y: float = 1.0
    flip_x: bool = False  # mirror left-right
    flip_y: bool = False  # mirror top-bottom

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Transform":
        d = d or {}
        t = cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
        if t.scale_x <= 0 or t.scale_y <= 0:
            raise LayoutError("Size must be greater than zero")
        return t

    def is_identity(self) -> bool:
        return self == Transform()


@dataclass
class Block:
    thread: dict[str, str]
    recs: list[Rec]
    sources: list[tuple[int, int]] = field(default_factory=list)  # (item, source block)
    original: dict[str, str] | None = None  # the file's thread, before any recolor
    digitized: bool = False  # from a drawn object (not a stitch file)


def _thread_dict(t: pe.EmbThread | None) -> dict[str, str]:
    return design._thread(t)


def _split_blocks(pattern: pe.EmbPattern, item: int) -> list[Block]:
    """Source records grouped into color blocks. Color changes become block boundaries."""
    blocks: list[Block] = []
    cur: list[Rec] = []
    for i, (x, y, c) in enumerate(pattern.stitches):
        k = c & M
        if k in (pe.COLOR_CHANGE, pe.NEEDLE_SET):
            blocks.append(Block({}, cur))
            cur = []
        elif k == pe.END:
            break
        elif k in (pe.STITCH, pe.JUMP, pe.TRIM, pe.STOP):
            cur.append([x, y, k, item, i])
        # other commands (sequins, speed) are dropped
    blocks.append(Block({}, cur))
    for b, blk in enumerate(blocks):
        t = pattern.threadlist[b] if b < len(pattern.threadlist) else None
        blk.thread = _thread_dict(t)
        blk.original = dict(blk.thread)
        blk.sources = [(item, b)]
    return blocks


def _stitch_bounds(recs: list[Rec]) -> tuple[float, float, float, float] | None:
    pts = [(r[0], r[1]) for r in recs if r[2] == pe.STITCH]
    if not pts:
        return None
    xs, ys = zip(*pts)
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- per-item edits


def _apply_ops(blocks: list[Block], ops: list[dict[str, Any]]) -> list[Block]:
    deleted = {int(o["block"]) for o in ops if o.get("op") == "delete_block"}
    inserts: dict[int, list[str]] = {}
    for o in ops:
        if o.get("op") == "insert":
            if o.get("command") not in ("stop", "trim"):
                raise LayoutError("Can only insert a stop or a trim")
            inserts.setdefault(int(o["after"]), []).append(o["command"])
    jt = next((o for o in reversed(ops) if o.get("op") == "jumps_to_trims"), None)

    out = []
    for b, blk in enumerate(blocks):
        if b in deleted:
            continue
        recs: list[Rec] = []
        for r in blk.recs:
            recs.append(r)
            for cmd in inserts.get(r[4], []):
                recs.append([r[0], r[1], pe.STOP if cmd == "stop" else pe.TRIM, r[3], -1])
        if jt:
            recs = _jumps_to_trims(recs, float(jt.get("min_mm", 3.0)))
        out.append(Block(blk.thread, recs, blk.sources, blk.original, blk.digitized))
    return out


def _jumps_to_trims(recs: list[Rec], min_mm: float) -> list[Rec]:
    """Add a trim to every untrimmed jump run at least `min_mm` long between two stitches."""
    out: list[Rec] = []
    last = None
    i, n = 0, len(recs)
    while i < n:
        r = recs[i]
        if r[2] == pe.JUMP:
            j = i
            while j < n and recs[j][2] in (pe.JUMP, pe.TRIM):
                j += 1
            run = recs[i:j]
            nxt = recs[j] if j < n and recs[j][2] == pe.STITCH else None
            trimmed = any(x[2] == pe.TRIM for x in run)
            if last and nxt and not trimmed and math.hypot(nxt[0] - last[0], nxt[1] - last[1]) / 10 >= min_mm:
                out.append([last[0], last[1], pe.TRIM, r[3], -1])
            out.extend(run)
            i = j
            continue
        if r[2] == pe.STITCH:
            last = r
        elif r[2] == pe.STOP:
            last = None
        out.append(r)
        i += 1
    return out


def _transform(blocks: list[Block], t: Transform, center: tuple[float, float]) -> None:
    if t.is_identity():
        return
    cx, cy = center
    a = math.radians(t.rotate)
    ca, sa = math.cos(a), math.sin(a)
    fx = -1.0 if t.flip_x else 1.0
    fy = -1.0 if t.flip_y else 1.0
    dx, dy = t.x * 10, t.y * 10
    for blk in blocks:
        for r in blk.recs:
            px = (r[0] - cx) * fx * t.scale_x
            py = (r[1] - cy) * fy * t.scale_y
            r[0] = px * ca - py * sa + cx + dx
            r[1] = px * sa + py * ca + cy + dy


def _thread_key(t: dict[str, str]) -> tuple[str, str, str]:
    return (t.get("color", "").lower(), t.get("brand", "").lower(), t.get("catalog", "") or t.get("name", "").lower())


def _join(a: Block, b: Block) -> Block:
    """Two blocks of the same thread sewn back to back: the color change between them was a cut, keep it as a trim."""
    recs = list(a.recs)
    if recs and b.recs:
        last = recs[-1]
        recs.append([last[0], last[1], pe.TRIM, last[3], -1])
    recs.extend(b.recs)
    return Block(a.thread, recs, a.sources + b.sources, a.original)


def _merge_same(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        if out and _thread_key(out[-1].thread) == _thread_key(b.thread):
            out[-1] = _join(out[-1], b)
        else:
            out.append(b)
    return out


def _color_sort(blocks: list[Block]) -> list[Block]:
    """Group blocks by thread, in order of first appearance (stable within a thread)."""
    order: list[tuple[str, str, str]] = []
    groups: dict[tuple[str, str, str], list[Block]] = {}
    for b in blocks:
        k = _thread_key(b.thread)
        if k not in groups:
            order.append(k)
            groups[k] = []
        groups[k].append(b)
    out = []
    for k in order:
        g = groups[k][0]
        for b in groups[k][1:]:
            g = _join(g, b)
        out.append(g)
    return out


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
    from .digitize.applique import cut_path

    paths = []
    for idx, it in enumerate(layout.get("items") or []):
        if it.get("kind") != "applique":
            continue
        pts = dz.geometry_points(it)
        x0, y0, x1, y1 = dz.bounds(pts)
        t = Transform.from_dict(it.get("transform"))
        obj = it if t.is_identity() else dz.transform_geometry(it, t, ((x0 + x1) / 2, (y0 + y1) / 2))
        ring = cut_path((obj.get("geometry") or {}).get("outline") or [])
        name = it.get("name") or f"Applique {idx + 1}"
        paths.append((name, ring))
    if not paths:
        raise LayoutError("There are no applique pieces in this design")
    xs = [p[0] for _, r in paths for p in r]
    ys = [p[1] for _, r in paths for p in r]
    m = 5.0
    ox, oy = min(xs) - m, min(ys) - m
    w, h = max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m
    body = []
    for name, ring in paths:
        d = "M" + " L".join(f"{x - ox:.2f},{y - oy:.2f}" for x, y in ring) + " Z"
        body.append(f'  <path d="{d}" fill="none" stroke="#000" stroke-width="0.25"><title>{_xml(name)}</title></path>')
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
    try:
        d.write_text(svg, encoding="utf-8")
    except OSError as exc:
        raise LayoutError(f"Couldn't save {d.name}: {exc.strerror or exc}") from exc
    return {"path": str(d), "pieces": n}


# ---------------------------------------------------------------- digitized objects

OBJECT_KINDS = ("run", "satin", "fill", "applique")
OBJECT_LABEL = {"run": "Running stitch", "satin": "Satin", "fill": "Fill", "applique": "Applique"}
DEFAULT_THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}

_object_cache: dict[str, tuple[list, list[str]]] = {}
_OBJECT_CACHE_MAX = 512


def _generate_cached(obj: dict[str, Any]) -> tuple[list, list[str]]:
    """Stitches for an object, cached by its geometry and parameters (unchanged objects are free)."""
    key = json.dumps({k: obj.get(k) for k in ("kind", "geometry", "params")}, sort_keys=True)
    hit = _object_cache.get(key)
    if hit is None:
        hit = dz.generate(obj)
        if len(_object_cache) >= _OBJECT_CACHE_MAX:
            _object_cache.pop(next(iter(_object_cache)))
        _object_cache[key] = hit
    return hit


def _object_blocks(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[list[Block], dict[str, Any], list[str]]:
    """One block for a drawn object. Its transform moves the shape, then stitches are generated,
    so resizing keeps the stitch density right (unlike resizing a stitch file)."""
    label = it.get("name") or f"{OBJECT_LABEL.get(it.get('kind'), 'Object')} {idx + 1}"
    pts = dz.geometry_points(it)
    if not pts:
        raise LayoutError(f"{label} has no points")
    x0, y0, x1, y1 = dz.bounds(pts)
    center = ((x0 + x1) / 2, (y0 + y1) / 2)
    t = Transform.from_dict(it.get("transform"))
    obj = it if t.is_identity() else dz.transform_geometry(it, t, center)
    obj = fabrics.apply(obj, fabric)
    try:
        recs_mm, warnings = _generate_cached(obj)
    except dz.DigitizeError as exc:
        raise LayoutError(f"{label}: {exc}") from exc
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    recs = [[x * 10, y * 10, k, idx, i] for i, (x, y, k) in enumerate(recs_mm)]
    block = Block(dict(thread), recs, [(idx, 0)], dict(thread), digitized=True)
    override = (it.get("threads") or [None])[0]
    if override:
        block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
    return [block], {"center": center, "t": t}, warnings


_text_cache: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}


def _text_block(it: dict[str, Any], idx: int) -> tuple[Block, list[str], tuple[float, float]]:
    """All letters of a text item as one block in its thread. Letters are drawn shapes, so moving,
    turning or resizing the text regenerates stitches at the right density."""
    spec = {k: it.get(k) for k in ("text", "font", "size_mm", "spacing_mm", "style", "shape", "monogram")}
    key = json.dumps(spec, sort_keys=True)
    hit = _text_cache.get(key)
    if hit is None:
        try:
            hit = lettering.layout_text(spec)
        except (lettering.LetteringError, dz.DigitizeError) as exc:
            raise LayoutError(f"{it.get('name') or 'Text'}: {exc}") from exc
        if len(_text_cache) > 64:
            _text_cache.pop(next(iter(_text_cache)))
        _text_cache[key] = hit
    objects, warnings = hit
    t = Transform.from_dict(it.get("transform"))
    recs: list[Rec] = []
    skipped = 0
    for obj in objects:
        o = obj if t.is_identity() else dz.transform_geometry(obj, t, (0.0, 0.0))
        try:
            mm, _ = _generate_cached(o)
        except dz.DigitizeError:
            skipped += 1  # a speck too small to stitch (e.g. a tiny dot)
            continue
        part = [[x * 10, y * 10, k, idx, -1] for x, y, k in mm]
        if recs and part:
            last = next((r for r in reversed(recs) if r[2] == pe.STITCH), None)
            first = next((r for r in part if r[2] == pe.STITCH), None)
            if last and first:
                d = math.hypot(first[0] - last[0], first[1] - last[1]) / 10
                if d > dz.TRIM_TRAVEL_MM:
                    recs.append([last[0], last[1], pe.TRIM, idx, -1])
                if d > dz.MIN_STITCH_MM:
                    recs.append([first[0], first[1], pe.JUMP, idx, -1])
        recs.extend(part)
    if skipped:
        warnings = [*warnings, f"{skipped} tiny part{'s' if skipped > 1 else ''} of the letters were too small to stitch."]
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    block = Block(dict(thread), recs, [(idx, 0)], dict(thread), digitized=True)
    override = (it.get("threads") or [None])[0]
    if override:
        block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
    return block, warnings, (t.x, t.y)


def _join_objects(a: Block, b: Block) -> Block:
    """Consecutive drawn objects in the same thread sew without a color change: a short move is a
    jump, a long one is trimmed so no thread is left across the fabric."""
    recs = list(a.recs)
    sa = next((r for r in reversed(a.recs) if r[2] == pe.STITCH), None)
    sb = next((r for r in b.recs if r[2] == pe.STITCH), None)
    if sa and sb:
        d = math.hypot(sb[0] - sa[0], sb[1] - sa[1]) / 10
        if d > dz.TRIM_TRAVEL_MM:
            recs.append([sa[0], sa[1], pe.TRIM, sa[3], -1])
        if d > dz.MIN_STITCH_MM:
            recs.append([sb[0], sb[1], pe.JUMP, sb[3], -1])
    recs.extend(b.recs)
    return Block(a.thread, recs, a.sources + b.sources, a.original, True)


def _join_same_thread_objects(blocks: list[Block]) -> list[Block]:
    out: list[Block] = []
    for b in blocks:
        prev = out[-1] if out else None
        if prev and prev.digitized and b.digitized and _thread_key(prev.thread) == _thread_key(b.thread):
            out[-1] = _join_objects(prev, b)
        else:
            out.append(b)
    return out


# ---------------------------------------------------------------- render


@dataclass
class Rendered:
    pattern: pe.EmbPattern
    item_of: list[int]
    src_of: list[int]
    blocks: list[Block]
    items: list[dict[str, Any]]
    warnings: list[dict[str, str]]


def render(layout: dict[str, Any]) -> Rendered:
    items = layout.get("items") or []
    if not items:
        raise LayoutError("Nothing to show: the layout has no designs")
    all_blocks: list[Block] = []
    item_info: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []

    for idx, it in enumerate(items):
        if it.get("kind") == "text":
            block, text_warnings, centre = _text_block(it, idx)
            blocks = _apply_ops([block], it.get("ops") or [])
            b = _stitch_bounds([r for blk in blocks for r in blk.recs])
            name = it.get("name") or f"“{str(it.get('text', '')).strip()[:24]}”"
            item_info.append({
                "id": it.get("id", str(idx)),
                "name": name,
                "kind": "text",
                "center_mm": list(centre),
                "bounds_mm": [v / 10 for v in b] if b else None,
                "source_size_mm": None,
            })
            warnings += [{"level": "warning", "code": f"text_{idx}_{n}", "message": f"{name}: {w}"} for n, w in enumerate(text_warnings)]
            all_blocks.extend(blk for blk in blocks if blk.recs)
            continue
        if it.get("kind", "file") in OBJECT_KINDS:
            blocks, geo, obj_warnings = _object_blocks(it, idx, layout.get("fabric"))
            blocks = _apply_ops(blocks, it.get("ops") or [])
            b = _stitch_bounds([r for blk in blocks for r in blk.recs])
            name = it.get("name") or f"{OBJECT_LABEL[it['kind']]} {idx + 1}"
            item_info.append({
                "id": it.get("id", str(idx)),
                "name": name,
                "kind": it["kind"],
                "center_mm": [geo["center"][0] + geo["t"].x, geo["center"][1] + geo["t"].y],
                "bounds_mm": [v / 10 for v in b] if b else None,
                "source_size_mm": None,
            })
            warnings += [{"level": "warning", "code": f"object_{idx}_{n}", "message": f"{name}: {w}"}
                         for n, w in enumerate(obj_warnings)]
            all_blocks.extend(blk for blk in blocks if blk.recs)
            continue
        src = _load(it["path"])
        blocks = _split_blocks(src, idx)
        center_b = _stitch_bounds([r for b in blocks for r in b.recs])
        center = ((center_b[0] + center_b[2]) / 2, (center_b[1] + center_b[3]) / 2) if center_b else (0.0, 0.0)
        for b, t in enumerate(it.get("threads") or []):
            if t and b < len(blocks):
                blocks[b].thread = {k: str(t.get(k, "")) for k in ("color", "name", "catalog", "brand")}
        blocks = _apply_ops(blocks, it.get("ops") or [])
        t = Transform.from_dict(it.get("transform"))
        _transform(blocks, t, center)
        b = _stitch_bounds([r for blk in blocks for r in blk.recs])
        name = Path(it["path"]).name
        item_info.append({
            "id": it.get("id", str(idx)),
            "name": name,
            "kind": "file",
            "center_mm": [center[0] / 10 + t.x, center[1] / 10 + t.y],
            "bounds_mm": [v / 10 for v in b] if b else None,
            "source_size_mm": [(center_b[2] - center_b[0]) / 10, (center_b[3] - center_b[1]) / 10] if center_b else [0, 0],
        })
        for axis, s in (("width", t.scale_x), ("height", t.scale_y)):
            if abs(s - 1) > SCALE_WARN + 1e-9:
                warnings.append({"level": "warning", "code": f"scale_{idx}_{axis}", "message": (
                    f"{name} is resized to {s * 100:.0f}% {axis}. Beyond about ±20% stitches get too dense "
                    "or too sparse, because resizing a stitch file doesn't add or remove stitches.")})
                break
        all_blocks.extend(blk for blk in blocks if blk.recs)

    all_blocks = _join_same_thread_objects(all_blocks)
    if layout.get("color_sort"):
        all_blocks = _color_sort(all_blocks)
        warnings.append({"level": "info", "code": "color_sort", "message": (
            "Colors are sorted to sew each thread once. Where designs overlap, check that the stitching order still looks right.")})
    elif layout.get("merge_colors"):
        all_blocks = _merge_same(all_blocks)

    knockdown = layout.get("knockdown") or {}
    if knockdown.get("enabled"):
        block = _knockdown(all_blocks, float(knockdown.get("margin_mm", 2.0)), knockdown.get("thread"))
        if block:
            all_blocks.insert(0, block)

    basting = layout.get("basting") or {}
    if basting.get("enabled"):
        box = _basting(all_blocks, float(basting.get("margin_mm", 5)))
        if box:
            all_blocks.insert(0, box)

    pattern = pe.EmbPattern()
    item_of: list[int] = []
    src_of: list[int] = []
    for n, blk in enumerate(all_blocks):
        if n:
            last = pattern.stitches[-1] if pattern.stitches else [0, 0, 0]
            pattern.stitches.append([last[0], last[1], pe.COLOR_CHANGE])
            item_of.append(-1)
            src_of.append(-1)
        t = blk.thread
        pattern.add_thread(pe.EmbThread(t.get("color", "#000000"), t.get("name", ""), t.get("catalog", ""),
                                        brand=t.get("brand", ""), chart=t.get("brand", "")))
        for x, y, k, item, src in blk.recs:
            pattern.stitches.append([x, y, k])
            item_of.append(item)
            src_of.append(src)
    pattern.stitches.append([pattern.stitches[-1][0] if pattern.stitches else 0,
                             pattern.stitches[-1][1] if pattern.stitches else 0, pe.END])
    return Rendered(pattern, item_of, src_of, all_blocks, item_info, warnings)


def render_summary(layout: dict[str, Any]) -> dict[str, Any]:
    """The design summary the UI draws, plus item bounds and record provenance."""
    r = render(layout)
    summary = design.summarize(r.pattern)
    n = len(summary["records"]["kind"])
    summary["records"]["item"] = r.item_of[:n]
    summary["records"]["src"] = r.src_of[:n]
    # Every output block maps back to the source blocks it came from (several after merging).
    non_empty = [b for b in r.blocks if any(rec[2] == pe.STITCH for rec in b.recs)]
    for out_block, blk in zip(summary["blocks"], non_empty):
        out_block["sources"] = [{"item": i, "block": b} for i, b in blk.sources]
        out_block["original"] = blk.original
    title = layout.get("title") or ""
    first = next((it["path"] for it in layout["items"] if it.get("path")), "")
    if title:
        name = title
    elif not first:
        name = "New design"
    elif len(layout["items"]) == 1:
        name = Path(first).name
    else:
        name = f"{Path(first).stem} + {len(layout['items']) - 1} more"
    summary.update({
        "path": first,
        "name": name,
        "format": design._ext(first) if first else "ludd",
        "items": r.items,
        "warnings": r.warnings,
    })
    return summary


def _names(r: Rendered) -> dict[int, str]:
    """Drawn objects and lettering by item index (the ones whose shapes the checks compare)."""
    return {i: info["name"] for i, info in enumerate(r.items) if info["kind"] in ("satin", "fill", "applique", "text")}


def check(layout: dict[str, Any], heatmap: bool = False) -> dict[str, Any]:
    """Quality checks on the design as it will be sewn, plus (optionally) the density map, and
    the stabilizer to use on the chosen fabric."""
    r = render(layout)
    out = quality.check(r.pattern, r.item_of, _names(r), heatmap)
    for c in out["checks"]:
        if "item" in c and 0 <= c["item"] < len(r.items):
            c["item_id"] = r.items[c["item"]]["id"]
    fabric = fabrics.get(layout.get("fabric"))
    out["fabric"] = {"id": fabric["id"], "name": fabric["name"], "advice": fabrics.advice(fabric["id"])}
    return out


# ---------------------------------------------------------------- splitting across hoopings


def split_plan(layout: dict[str, Any], hoop: dict[str, Any], overlap_mm: float = 10.0) -> dict[str, Any]:
    """How a design too big for the hoop would be split: the hoopings and their alignment marks."""
    blocks, sections, grid, bounds = split.plan(render(layout).pattern, float(hoop["width_mm"]), float(hoop["height_mm"]), overlap_mm)
    return split.summary(blocks, sections, grid, bounds)


def export_split(layout: dict[str, Any], dest: str, hoop: dict[str, Any], overlap_mm: float = 10.0,
                 options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Save one file per hooping: "name 1 of 4.pes", "name 2 of 4.pes", …"""
    d = Path(dest).resolve()
    ext = design._ext(d)
    blocks, sections, grid, bounds = split.plan(render(layout).pattern, float(hoop["width_mm"]), float(hoop["height_mm"]), overlap_mm)
    opts = Options.from_dict(options)
    stem = d.stem
    files, stops = [], 0
    n = len(sections)
    sources = {Path(it["path"]).resolve() for it in layout.get("items") or [] if it.get("path")}
    for sec in sections:
        out = d.with_name(f"{stem} {sec.index + 1} of {n}{d.suffix}")
        if out in sources:
            raise LayoutError("Choose a different file name: saving over an original design isn't allowed")
        pattern, report = prepare(split.section_pattern(blocks, sec), opts, ext)
        design.write(pattern, out, write_settings(opts))
        stops += report.get("stops_added", 0)
        files.append(str(out))
    return {"paths": files, "stops_added": stops, **split.summary(blocks, sections, grid, bounds)}


def preview_export(layout: dict[str, Any], options: dict[str, Any] | None, ext: str | None) -> dict[str, Any]:
    r = render(layout)
    pattern, report = prepare(r.pattern, Options.from_dict(options), ext)
    # The quality checks belong in the last look before saving for the machine.
    report["warnings"] = report["warnings"] + quality.check(r.pattern, r.item_of, _names(r))["checks"]
    report["fabric_advice"] = fabrics.advice(layout.get("fabric"))
    return {**report, **design.summarize(pattern)}


def export(layout: dict[str, Any], dest: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    d = Path(dest).resolve()
    for it in layout.get("items") or []:
        if it.get("path") and Path(it["path"]).resolve() == d:
            raise LayoutError("Choose a different file name: saving over an original design isn't allowed")
    opts = Options.from_dict(options)
    pattern, report = prepare(render(layout).pattern, opts, design._ext(d))
    design.write(pattern, d, write_settings(opts))
    return {"path": str(d), **report}
