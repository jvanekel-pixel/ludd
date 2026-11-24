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
import os
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyembroidery as pe
from shapely.errors import GEOSException
from shapely.geometry import LineString, MultiLineString
from shapely.validation import make_valid
from shapely.ops import unary_union

from . import design, fabrics, kept, lettering, quality, split
from .digitize import stitches as dz
from .digitize.paths import flatten
from .prepare import Options, prepare, write_settings

M = pe.COMMAND_MASK
SCALE_WARN = 0.20  # warn when an item is scaled more than ±20%
BASTING_STITCH_MM = 4.0
BASTING_MIN_MM = 2.0  # the box keeps at least this far from the design, even to fit the hoop
BASTING_THREAD = {"color": "#9e9e9e", "name": "Basting", "catalog": "", "brand": ""}

# A record while building: x, y (0.1 mm), command, item index (-1 = layout), source record index (-1 = added).
Rec = list


class LayoutError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- source cache

_cache: dict[str, tuple[tuple, pe.EmbPattern]] = {}
_CACHE_MAX = 32  # stitch files kept in memory (the least recently used go first)


def _load(path: str) -> pe.EmbPattern:
    """Load a stitch file, cached until it changes on disk (its time, size or the copy read)."""
    p = Path(kept.readable(path))
    try:
        st = p.stat()
    except OSError as exc:
        raise LayoutError(f"File not found: {Path(path).name}. It may have been moved or deleted.") from exc
    stamp = (st.st_mtime_ns, st.st_size, str(p))
    hit = _cache.pop(path, None)
    if hit and hit[0] == stamp:
        _cache[path] = hit  # most recently used last
        return hit[1]
    pattern = design.load(p)
    if str(p) == str(path):
        # Keep a private copy, so the design survives the original being moved or deleted.
        try:
            kept.keep(path, p.read_bytes())
        except OSError:
            pass
    _cache[path] = (stamp, pattern)
    while len(_cache) > _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
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


def _index(v: Any) -> int | None:
    """A record index from an op, or None if it isn't one (a damaged or hand-edited project)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v != int(v):
        return None
    return int(v)


def _mm(v: Any) -> float | None:
    """A finite distance from an op (missing counts as 0), or None if it isn't a number."""
    if v is None:
        return 0.0
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _record_count(blocks: list[Block]) -> int:
    return 1 + max((r[4] for b in blocks for r in b.recs), default=-1)


def _apply_ops(blocks: list[Block], ops: list[dict[str, Any]], jt_mm: float | None = None,
               notes: list[str] | None = None, generated: bool = False) -> list[Block]:
    """Edits on one item: colours and stitches deleted, stops and trims inserted, jumps trimmed.
    Damaged ops (missing or non-numeric fields) are skipped rather than stopping the whole design.
    `jt_mm`: the layout-wide "trim jumps longer than" setting. `generated`: the item's stitches are
    made from a shape or text, so an insert remembers how many records there were (`n`) and is
    dropped, with a note, once the shape has changed and that place no longer exists."""
    deleted = {i for o in ops if o.get("op") == "delete_block" for i in [_index(o.get("block"))] if i is not None}
    # Stitch editing: single stitches deleted (by their index in the file).
    gone = {i for o in ops if o.get("op") == "delete_stitches" and isinstance(o.get("indices"), list)
            for v in o["indices"] for i in [_index(v)] if i is not None}
    count = _record_count(blocks) if generated else None
    inserts: dict[int, list[str]] = {}
    stale = 0
    for o in ops:
        if o.get("op") == "insert":
            if o.get("command") not in ("stop", "trim"):
                raise LayoutError("Can only insert a stop or a trim")
            after = _index(o.get("after"))
            if after is None:
                continue
            n = _index(o.get("n"))
            if count is not None and n is not None and n != count:
                stale += 1
                continue
            inserts.setdefault(after, []).append(o["command"])
    if stale and notes is not None:
        notes.append(f"{stale} stop{'s' if stale > 1 else ''} or trim{'s' if stale > 1 else ''} you added "
                     "were left out because the shape changed. Add them again where you want them.")
    jt = next((o for o in reversed(ops) if o.get("op") == "jumps_to_trims"), None)
    if jt is not None:
        jt_mm = _mm(jt.get("min_mm")) if jt.get("min_mm") is not None else 3.0
        if jt_mm is None:
            jt_mm = 3.0

    out = []
    for b, blk in enumerate(blocks):
        if b in deleted:
            continue
        recs: list[Rec] = []
        for r in blk.recs:
            if r[4] in gone and r[2] == pe.STITCH:
                # The stitch goes, but a stop or trim placed after it stays, at the last stitch kept.
                at = next((k for k in reversed(recs) if k[2] == pe.STITCH), r)
                for cmd in inserts.get(r[4], []):
                    recs.append([at[0], at[1], pe.STOP if cmd == "stop" else pe.TRIM, r[3], -1])
                continue
            recs.append(r)
            for cmd in inserts.get(r[4], []):
                recs.append([r[0], r[1], pe.STOP if cmd == "stop" else pe.TRIM, r[3], -1])
        if jt_mm is not None:
            recs = _jumps_to_trims(recs, jt_mm)
        out.append(Block(blk.thread, recs, blk.sources, blk.original, blk.digitized))
    return out


def _move_stitches(blocks: list[Block], ops: list[dict[str, Any]], local: bool = True) -> None:
    """Stitch editing: stitches dragged to a new place, by (dx, dy) mm. Moves marked `local` are in
    the file's own frame and are applied before the design's transform (so they turn and resize
    with it); older ones, without the mark, are a shift on the hoop applied after it.
    `move_stitches` moves several stitches by one drag; older projects have one `move_stitch` each."""
    moves: dict[int, tuple[float, float]] = {}
    for o in ops:
        kind = o.get("op")
        if kind not in ("move_stitch", "move_stitches") or bool(o.get("local")) != local:
            continue
        dx_mm, dy_mm = _mm(o.get("dx_mm")), _mm(o.get("dy_mm"))
        if dx_mm is None or dy_mm is None:
            continue
        raw = [o.get("index")] if kind == "move_stitch" else (o.get("indices") if isinstance(o.get("indices"), list) else [])
        for v in raw:
            i = _index(v)
            if i is None:
                continue
            dx, dy = moves.get(i, (0.0, 0.0))
            moves[i] = (dx + dx_mm * 10, dy + dy_mm * 10)
    if not moves:
        return
    for blk in blocks:
        for r in blk.recs:
            m = moves.get(r[4])
            if m and r[4] >= 0:
                r[0] += m[0]
                r[1] += m[1]


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
            # Already trimmed: a trim in the run, or just before it (files and shapes store TRIM, JUMP).
            trimmed = any(x[2] == pe.TRIM for x in run) or bool(out and out[-1][2] == pe.TRIM)
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
    from .digitize.applique import cut_rings

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


# ---------------------------------------------------------------- digitized objects

OBJECT_KINDS = ("run", "satin", "fill", "applique")
OBJECT_LABEL = {"run": "Running stitch", "satin": "Satin", "fill": "Fill", "applique": "Applique"}
DEFAULT_THREAD = {"color": "#1f3a93", "name": "Navy", "catalog": "", "brand": ""}

_object_cache: dict[str, tuple[list, list[str]]] = {}
_OBJECT_CACHE_MAX = 4096  # a whole-picture trace can make a thousand shapes or more


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


def _letter_ring(o: dict[str, Any]) -> list[list[float]]:
    """A letter part's outline (mm), for its start and end dots to slide along."""
    g = o.get("geometry") or {}
    if o.get("kind") == "fill":
        pts, _ = flatten(g.get("outline") or [], True)
    elif o.get("kind") == "satin" and g.get("rail_a"):
        a, _ = flatten(g.get("rail_a") or [])
        b, _ = flatten(g.get("rail_b") or [])
        pts = a + b[::-1]
    else:
        pts, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
    return [[round(x, 2), round(y, 2)] for x, y in pts]


def text_letters(it: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """A text item's letters as drawn shapes, turned, resized and mirrored with the text (but not
    yet moved to its place: add its x and y), each with where it starts and ends: where you put
    its dots (`letters` on the item, in the text's own unturned frame), or else starting at the
    edge nearest where the letter before ended and ending towards the next letter, so the jumps
    between letters are short."""
    spec = {k: it.get(k) for k in ("text", "font", "size_mm", "spacing_mm", "style", "shape", "monogram")}
    # The font file's date and size are part of the key: an edited stitch font shows at once.
    key = json.dumps({**spec, "font_file": lettering.font_stamp(spec.get("font") or {})}, sort_keys=True)
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
    shape_t = Transform(rotate=t.rotate, scale_x=t.scale_x, scale_y=t.scale_y, flip_x=t.flip_x, flip_y=t.flip_y)
    chosen = it.get("letters") or {}
    out = []
    for n, obj in enumerate(objects):
        mine = chosen.get(str(n)) or {}
        own = {k: mine[k] for k in ("start_mm", "end_mm") if dz._start_point(mine.get(k)) is not None}
        o = {**obj, "params": {**(obj.get("params") or {}), **own}} if own else obj
        o = o if shape_t.is_identity() else lettering.turn_with(dz.transform_geometry(o, shape_t, (0.0, 0.0)), shape_t)
        out.append((dict(o), set(own)))  # a copy: the cached letters are never changed
    # Short jumps: each letter ends towards the next (unless its end was chosen).
    for n, (o, own) in enumerate(out):
        if "end_mm" not in own and n + 1 < len(out) and o.get("kind") == "fill":
            ring = _letter_ring(out[n + 1][0])
            if ring:
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                o["params"] = {**(o.get("params") or {}), "end_mm": [round(cx, 3), round(cy, 3)]}
    return [o for o, _ in out], [w for w in warnings]


def _text_block(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[Block, list[str], tuple[float, float], list[dict[str, Any]]]:
    """All letters of a text item as one block in its thread. Letters are drawn shapes, so moving,
    turning or resizing the text regenerates stitches at the right density, and the fabric
    preset adjusts them like any other shape. Records are numbered in sewing order (their `src`),
    so a stop or trim can be inserted in lettering too. Also each letter part: its kind, outline,
    and where it starts and ends (mm), for the dots on the design."""
    letters, warnings = text_letters(it)
    t = Transform.from_dict(it.get("transform"))
    recs: list[Rec] = []
    parts: list[dict[str, Any]] = []
    skipped = 0
    # Letters are stitched at the text's own origin and then moved, so moving or nudging text
    # reuses the cached stitches; turning, mirroring or resizing turns the stitch angle too.
    prev_end: tuple[float, float] | None = None
    for n, letter in enumerate(letters):
        o = fabrics.apply(letter, fabric)
        # Each letter starts at its edge nearest where the one before ended (unless chosen).
        if (prev_end is not None and o.get("kind") == "fill" and dz._start_point((o.get("params") or {}).get("start_mm")) is None
                and "start_mm" not in ((it.get("letters") or {}).get(str(n)) or {})):
            o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
        try:
            mm, _ = _generate_cached(o)
        except dz.DigitizeError:
            skipped += 1  # a speck too small to stitch (e.g. a tiny dot)
            continue
        sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
        if sts:
            prev_end = sts[-1]
            look = "satin" if o.get("kind") == "fill" and it.get("style") == "satin" else o.get("kind")
            parts.append({"index": n, "kind": o.get("kind"), "look": look,
                          "start": [round(sts[0][0] + t.x, 2), round(sts[0][1] + t.y, 2)],
                          "end": [round(sts[-1][0] + t.x, 2), round(sts[-1][1] + t.y, 2)],
                          "ring": [[p[0] + t.x, p[1] + t.y] for p in _letter_ring(o)]})
        part = [[(x + t.x) * 10, (y + t.y) * 10, k, idx, -1] for x, y, k in mm]
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
    for n, r in enumerate(recs):
        r[4] = n
    if skipped:
        warnings = [*warnings, f"{skipped} tiny part{'s' if skipped > 1 else ''} of the letters were too small to stitch."]
    thread = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    block = Block(dict(thread), recs, [(idx, 0)], dict(thread), digitized=True)
    override = (it.get("threads") or [None])[0]
    if override:
        block.thread = {k: str(override.get(k, "")) for k in ("color", "name", "catalog", "brand")}
    return block, warnings, (t.x, t.y), parts


def text_to_shapes(it: dict[str, Any]) -> dict[str, Any]:
    """Lettering broken into drawn shapes, one per letter part, each in place and in the text's
    thread, starting and ending where the letters did: {"objects": [...]}. They can then be
    edited like any shape (their points, stitch type, density, direction and dots)."""
    letters, _ = text_letters(it)
    t = Transform.from_dict(it.get("transform"))
    thread = (it.get("threads") or [None])[0] or it.get("thread") or DEFAULT_THREAD
    chosen = it.get("letters") or {}
    label = it.get("name") or str(it.get("text") or "Text").strip()[:24]
    out = []
    prev_end = None
    for n, o in enumerate(letters):
        # Each starts where the one before ended, as the lettering did (unless its start was chosen).
        if prev_end is not None and o.get("kind") == "fill" and "start_mm" not in (chosen.get(str(n)) or {}):
            o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
        try:
            mm, _ = _generate_cached(o)
            sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
            prev_end = sts[-1] if sts else prev_end
        except dz.DigitizeError:
            continue  # a speck too small to stitch, as in the lettering
        moved = dz.transform_geometry(o, Transform(x=t.x, y=t.y), (0.0, 0.0))
        out.append({"kind": moved["kind"], "geometry": moved["geometry"], "params": moved.get("params") or {},
                    "thread": dict(thread), "name": f"{label} {n + 1}"})
    return {"objects": out}


def _join_objects(a: Block, b: Block, is_hidden=None) -> Block:
    """Consecutive drawn objects in the same thread sew without a color change. If the way from
    one to the next lies under stitching that's sewn later (`is_hidden(path)`), the needle travels
    there in small running stitches, covered later: no jump, no trim. Otherwise a short move is a
    jump and a long one is trimmed so no thread is left across the fabric."""
    recs = list(a.recs)
    sa = next((r for r in reversed(a.recs) if r[2] == pe.STITCH), None)
    sb = next((r for r in b.recs if r[2] == pe.STITCH), None)
    if sa and sb:
        d = math.hypot(sb[0] - sa[0], sb[1] - sa[1]) / 10
        path = LineString([(sa[0] / 10, sa[1] / 10), (sb[0] / 10, sb[1] / 10)])
        if d > dz.MIN_STITCH_MM and is_hidden is not None and is_hidden(path):
            n = max(1, math.ceil(d / dz.TRAVEL_STITCH_MM))
            for k in range(1, n):
                t = k / n
                # Belongs to neither shape (item -1, like basting): a shape's own stitches stay its
                # own, for its start and end marks, its outline and the shortest order.
                recs.append([sa[0] + (sb[0] - sa[0]) * t, sa[1] + (sb[1] - sa[1]) * t, pe.STITCH, -1, -1])
        else:
            if d > dz.TRIM_TRAVEL_MM:
                recs.append([sa[0], sa[1], pe.TRIM, sa[3], -1])
            if d > dz.MIN_STITCH_MM:
                recs.append([sb[0], sb[1], pe.JUMP, sb[3], -1])
    recs.extend(b.recs)
    return Block(a.thread, recs, a.sources + b.sources, a.original, True)


_cover_cache: dict[bytes, Any] = {}
COVER_CLOSE_MM = 0.35  # half the widest gap between rows that still counts as covered


def _cover(block: Block):
    """Where a block's stitches will cover the fabric: its stitch lines thickened so neighbouring
    rows join, then shrunk back (a little further, to stay well inside). Cached by the stitches;
    None when there's nothing usable (a single line covers nothing; a broken outline is skipped)."""
    pts = [(r[0], r[1]) for r in block.recs if r[2] == pe.STITCH]
    if len(pts) < 3:
        return None
    key = hashlib.sha1(str(pts).encode()).digest()
    if key in _cover_cache:
        return _cover_cache[key]
    lines = []
    run: list[tuple[float, float]] = []
    for r in block.recs:
        if r[2] == pe.STITCH:
            run.append((r[0] / 10, r[1] / 10))
            continue
        if len(run) > 1:
            lines.append(run)
        run = []
    if len(run) > 1:
        lines.append(run)
    cover = None
    try:
        if lines:
            # Rows up to 0.7 mm apart join (a thread is about 0.4 mm wide, so nothing shows between
            # them); wider gaps and holes stay open, so travel there isn't counted as hidden.
            c = MultiLineString(lines).simplify(0.1).buffer(COVER_CLOSE_MM, quad_segs=1).buffer(-COVER_CLOSE_MM - 0.3, quad_segs=1)
            if not c.is_valid:
                c = make_valid(c)
            if not c.is_empty and c.area > 0.5:
                cover = c
    except GEOSException:
        cover = None
    if len(_cover_cache) > 2048:
        _cover_cache.pop(next(iter(_cover_cache)))
    _cover_cache[key] = cover
    return cover


def _join_same_thread_objects(blocks: list[Block], travel_under: bool = False) -> list[Block]:
    """Join consecutive drawn objects in one thread (in their final sewing order). With
    `travel_under`, a move lying under stitching sewn later becomes hidden travel."""
    joinable = any(
        a.digitized and b.digitized and _thread_key(a.thread) == _thread_key(b.thread) for a, b in zip(blocks, blocks[1:])
    )
    covers: dict[int, Any] = {}

    def cover(j: int):
        if j not in covers:
            covers[j] = _cover(blocks[j]) if blocks[j].digitized else None
        return covers[j]

    def hidden_from(i: int):
        def is_hidden(path: LineString) -> bool:
            # Covered if, taking away what each later block covers, nothing of the way is left.
            left = path
            try:
                for j in range(i, len(blocks)):
                    c = cover(j)
                    if c is None:
                        continue
                    left = left.difference(c)
                    if left.is_empty or left.length < 0.05:
                        return True
            except GEOSException:
                return False
            return False

        return is_hidden

    out: list[Block] = []
    for i, b in enumerate(blocks):
        prev = out[-1] if out else None
        if prev and prev.digitized and b.digitized and _thread_key(prev.thread) == _thread_key(b.thread):
            out[-1] = _join_objects(prev, b, hidden_from(i) if travel_under and joinable else None)
        else:
            out.append(b)
    return out


_footprint_cache: dict[bytes, Any] = {}


def _footprint(block: Block):
    """Where a block's thread lies (its stitch lines, a thread wide). Cached by the stitches."""
    pts = [(r[0], r[1]) for r in block.recs if r[2] == pe.STITCH]
    key = hashlib.sha1(str(pts).encode()).digest()
    if key in _footprint_cache:
        return _footprint_cache[key]
    lines, run = [], []
    for r in block.recs:
        if r[2] == pe.STITCH:
            run.append((r[0] / 10, r[1] / 10))
            continue
        if run:
            lines.append(run if len(run) > 1 else run * 2)
        run = []
    if run:
        lines.append(run if len(run) > 1 else run * 2)
    try:
        fp = MultiLineString(lines).simplify(0.05).buffer(0.2, quad_segs=1) if lines else None
    except GEOSException:
        fp = None
    if len(_footprint_cache) > 2048:
        _footprint_cache.pop(next(iter(_footprint_cache)))
    _footprint_cache[key] = fp
    return fp


def _blocks_overlap(a: Block, b: Block) -> bool:
    ba, bb = _stitch_bounds(a.recs), _stitch_bounds(b.recs)
    if not ba or not bb or ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
        return False
    fa, fb = _footprint(a), _footprint(b)
    if fa is None or fb is None:
        return True  # can't tell: assume they do, which keeps the order
    try:
        return fa.intersects(fb)
    except GEOSException:
        return True


def _sort_by_thread(blocks: list[Block]) -> tuple[list[Block], int]:
    """Blocks grouped by thread, in order of first appearance (stable within a thread). A block only
    moves forward to join its thread if nothing it would move ahead of overlaps it: otherwise that
    shape would end up on top of it. Returns the blocks and how many stayed apart for that reason.
    Only reorders: joining happens afterwards, on the final order."""
    out: list[Block] = []
    held = 0
    for b in blocks:
        k = _thread_key(b.thread)
        last = max((i for i, o in enumerate(out) if _thread_key(o.thread) == k), default=-1)
        if last < 0 or last == len(out) - 1:
            out.append(b)
        elif any(_blocks_overlap(b, o) for o in out[last + 1:]):
            out.append(b)
            held += 1
        else:
            out.insert(last + 1, b)
    return out, held


def optimize_order(layout: dict[str, Any]) -> dict[str, Any]:
    """Sew same-thread shapes in the shortest order: within each run of consecutive drawn shapes
    in one thread, shapes that don't overlap each other are reordered so each starts near where the
    last ended (overlapping ones keep their order: it decides which is on top).
    Returns {"order": [item ids], "saved_mm": travel saved}."""
    r = render(layout)
    items = layout.get("items") or []
    ids = [it.get("id", str(i)) for i, it in enumerate(items)]

    # Each shape's own stitches (src >= 0): not travel or ties added between shapes.
    own: dict[int, list[tuple[float, float]]] = {}
    for (x, y, k), it, src in zip(r.pattern.stitches, r.item_of, r.src_of):
        if it >= 0 and src >= 0 and k & M == pe.STITCH:
            own.setdefault(it, []).append((x, y))

    def ends(idx: int) -> tuple[tuple[float, float], tuple[float, float]] | None:
        pts = own.get(idx)
        return ((pts[0][0] / 10, pts[0][1] / 10), (pts[-1][0] / 10, pts[-1][1] / 10)) if pts else None

    def key(it: dict[str, Any]) -> tuple:
        t = it.get("thread") or {}
        o = (it.get("threads") or [None])[0] or {}
        t = {**t, **o}
        return _thread_key({k: str(v) for k, v in t.items() if v is not None})  # as the file groups them (QA2 P5)

    shapes: dict[int, Block] = {}
    box = {k: (min(p[0] for p in v), min(p[1] for p in v), max(p[0] for p in v), max(p[1] for p in v)) for k, v in own.items()}

    def overlap(a: int, b: int) -> bool:
        """Whether two shapes' stitching really overlaps (then their order decides which is on top)."""
        ba, bb = box.get(a), box.get(b)
        if not ba or not bb:
            return True
        if ba[2] < bb[0] or bb[2] < ba[0] or ba[3] < bb[1] or bb[3] < ba[1]:
            return False
        for k in (a, b):
            if k not in shapes:
                shapes[k] = Block({}, [[x, y, pe.STITCH, k, 0] for x, y in own.get(k, [])])
        if not shapes[a].recs or not shapes[b].recs:
            return True
        return _blocks_overlap(shapes[a], shapes[b])

    order: list[int] = []
    saved = 0.0
    i = 0
    while i < len(items):
        drawn = items[i].get("kind") in OBJECT_KINDS
        j = i + 1
        if drawn:
            while j < len(items) and items[j].get("kind") in OBJECT_KINDS and key(items[j]) == key(items[i]):
                j += 1
        run = list(range(i, j))
        e = {k: ends(k) for k in run}
        if len(run) > 2 and all(e.values()):
            # A shape may be sewn next once every shape before it in the run that it overlaps is
            # sewn: overlapping shapes keep their order, the others go nearest-first.
            before_of = {b: {a for a in run if a < b and overlap(a, b)} for b in run}

            def length(seq):
                return sum(math.dist(e[a][1], e[b][0]) for a, b in zip(seq, seq[1:]))

            todo = run[1:]
            seq = [run[0]]
            while todo:
                done = set(seq)
                ready = [k for k in todo if before_of[k] <= done]
                nxt = min(ready, key=lambda k: math.dist(e[seq[-1]][1], e[k][0]))
                todo.remove(nxt)
                seq.append(nxt)
            if length(seq) < length(run) - 1e-6:
                saved += length(run) - length(seq)
                run = seq
        order += run
        i = j
    return {"order": [ids[k] for k in order], "saved_mm": round(saved, 1)}


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

    # "Trim jumps longer than …" for the whole design (older projects keep it as an op per item).
    jt_mm = _mm(layout.get("jumps_to_trims")) if layout.get("jumps_to_trims") is not None else None

    for idx, it in enumerate(items):
        if it.get("kind") == "text":
            block, text_warnings, centre, parts = _text_block(it, idx, layout.get("fabric"))
            text_warnings = list(text_warnings)
            blocks = _apply_ops([block], it.get("ops") or [], jt_mm, text_warnings, generated=True)
            b = _stitch_bounds([r for blk in blocks for r in blk.recs])
            name = it.get("name") or f"“{str(it.get('text', '')).strip()[:24]}”"
            item_info.append({
                "id": it.get("id", str(idx)),
                "name": name,
                "kind": "text",
                "letters": parts,
                "center_mm": list(centre),
                "bounds_mm": [v / 10 for v in b] if b else None,
                "source_size_mm": None,
            })
            warnings += [{"level": "warning", "code": f"text_{idx}_{n}", "message": f"{name}: {w}"} for n, w in enumerate(text_warnings)]
            all_blocks.extend(blk for blk in blocks if blk.recs)
            continue
        if it.get("kind", "file") in OBJECT_KINDS:
            blocks, geo, obj_warnings = _object_blocks(it, idx, layout.get("fabric"))
            obj_warnings = list(obj_warnings)
            blocks = _apply_ops(blocks, it.get("ops") or [], jt_mm, obj_warnings, generated=True)
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
        blocks = _apply_ops(blocks, it.get("ops") or [], jt_mm)
        _move_stitches(blocks, it.get("ops") or [], local=True)
        t = Transform.from_dict(it.get("transform"))
        _transform(blocks, t, center)
        _move_stitches(blocks, it.get("ops") or [], local=False)
        b = _stitch_bounds([r for blk in blocks for r in blk.recs])
        name = it.get("name") or Path(it["path"]).name
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

    # A colour whose stitches were all deleted (stitch editing) sews nothing: leave it out, so the
    # file has no empty colour change and its thread list stays in step with the stitches.
    all_blocks = [b for b in all_blocks if any(r[2] == pe.STITCH for r in b.recs)]
    if not all_blocks:
        raise LayoutError("There are no stitches left: everything was deleted")
    # Colours are sorted first, so moves are judged on the order the design is really sewn in.
    held = 0
    if layout.get("color_sort"):
        all_blocks, held = _sort_by_thread(all_blocks)
    all_blocks = _join_same_thread_objects(all_blocks, bool(layout.get("travel_under", False)))
    if layout.get("color_sort"):
        all_blocks = _merge_same(all_blocks)
        if held:
            warnings.append({"level": "info", "code": "color_sort", "message": (
                f"Some colors are still sewn more than once ({held} part{'s' if held > 1 else ''}): sewing them earlier "
                "would hide them under shapes that are meant to be underneath.")})
    elif layout.get("merge_colors"):
        all_blocks = _merge_same(all_blocks)

    knockdown = layout.get("knockdown") or {}
    if knockdown.get("enabled"):
        block = _knockdown(all_blocks, float(knockdown.get("margin_mm", 2.0)), knockdown.get("thread"))
        if block:
            all_blocks.insert(0, block)

    basting = layout.get("basting") or {}
    if basting.get("enabled"):
        margin = _mm(basting.get("margin_mm", 5))
        margin = 5.0 if margin is None else margin
        fit = basting.get("fit_mm")
        b = _stitch_bounds([r for blk in all_blocks for r in blk.recs])
        if b and isinstance(fit, list) and len(fit) == 2 and all(_mm(v) for v in fit):
            # The box shouldn't be what makes the design too big for the hoop: bring it in to fit,
            # but no closer than BASTING_MIN_MM.
            room = min(float(fit[0]) - (b[2] - b[0]) / 10, float(fit[1]) - (b[3] - b[1]) / 10) / 2 - 0.1
            if room < margin:
                margin = max(BASTING_MIN_MM, room)
                if -0.1 <= room < BASTING_MIN_MM:  # the design fits; with the box it doesn't
                    warnings.append({"level": "warning", "code": "basting_fit", "message": (
                        "The basting box makes the design bigger than the hoop. Turn the basting box off, "
                        "or make the design a little smaller.")})
        box = _basting(all_blocks, margin)
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


def check(layout: dict[str, Any], heatmap: bool = False, rendered: "Rendered | None" = None) -> dict[str, Any]:
    """Quality checks on the design as it will be sewn, plus (optionally) the density map, and
    the stabilizer to use on the chosen fabric. `rendered`: render(layout), if already made."""
    r = rendered if rendered is not None else render(layout)
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
    files, stops = [], 0
    n = len(sections)
    sources = {Path(it["path"]).resolve() for it in layout.get("items") or [] if it.get("path")}

    def names(stem: str) -> list[Path]:
        return [d.with_name(f"{stem} {sec.index + 1} of {n}{d.suffix}") for sec in sections]

    # Never replace files from an earlier split: "name (1) 1 of 3.pes" etc. instead.
    stem, k = d.stem, 0
    while any(p.exists() for p in names(stem)):
        k += 1
        stem = f"{d.stem} ({k})"
    for sec, out in zip(sections, names(stem)):
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


def export(layout: dict[str, Any], dest: str, options: dict[str, Any] | None = None, keep_existing: bool = False) -> dict[str, Any]:
    """Save the design for a machine. `keep_existing`: never replace a file already there (save as
    "name (1).pes" instead), for batches such as one file per name."""
    d = Path(dest).resolve()
    if keep_existing:
        d = design._free_name(d)
    for it in layout.get("items") or []:
        if it.get("path") and Path(it["path"]).resolve() == d:
            raise LayoutError("Choose a different file name: saving over an original design isn't allowed")
    opts = Options.from_dict(options)
    pattern, report = prepare(render(layout).pattern, opts, design._ext(d))
    design.write(pattern, d, write_settings(opts))
    return {"path": str(d), **report}
