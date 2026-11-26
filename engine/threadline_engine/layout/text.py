"""Lettering turned into color blocks, and into drawn shapes.

A text is sewn in five steps: its letters are laid out (lettering.layout_text, cached), single
letters are changed (_apply_letter_edits), the extras are made from the letters (lettering.extras:
a shadow before them; an outline and a frame after), each part is stitched (_part_stitches) and
the parts are put into color blocks (_blocks), one for each run sewn in the same thread."""

from __future__ import annotations

import json
import math
from typing import Any

import pyembroidery as pe

from .. import fabrics, lettering
from ..digitize import stitches as dz
from ..digitize.paths import flatten
from .model import Block, LayoutError, Rec, Transform, _thread_key
from .objects import DEFAULT_THREAD, _generate_cached


_text_cache: dict[str, tuple[list[dict[str, Any]], list[str]]] = {}


def _letter_ring(o: dict[str, Any]) -> list[list[float]]:
    """A letter part's outline (mm), for its start and end dots to slide along."""
    g = o.get("geometry") or {}
    if o.get("kind") == "stitches":  # no outline: the box round its stitches
        nodes = g.get("nodes") or []
        if not nodes:
            return []
        x0, y0, x1, y1 = dz.bounds([(n[0], n[1]) for n in nodes])
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    elif o.get("kind") == "fill":
        pts, _ = flatten(g.get("outline") or [], True)
    elif o.get("kind") == "satin" and g.get("rail_a"):
        a, _ = flatten(g.get("rail_a") or [])
        b, _ = flatten(g.get("rail_b") or [])
        pts = a + b[::-1]
    else:
        pts, _ = flatten(g.get("nodes") or [], bool(g.get("closed")))
    return [[round(x, 2), round(y, 2)] for x, y in pts]


def _number(value: Any) -> float | None:
    """A letter change's number, or None if it isn't one (a hand-edited project)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _edited_letter(parts: list[dict[str, Any]], edit: dict[str, Any]) -> list[dict[str, Any]]:
    """One letter's parts changed: resized and turned about the middle of their box, then moved
    (its stitch angles turn with it); then its own stitch angle and thread, if given."""
    dx, dy = _number(edit.get("dx_mm")) or 0.0, _number(edit.get("dy_mm")) or 0.0
    turn = _number(edit.get("rotate")) or 0.0
    grow = _number(edit.get("scale"))
    grow = min(max(grow, 0.1), 10.0) if grow and grow > 0 else 1.0
    points = [p for o in parts for p in lettering.envelope.part_points(o)]
    if points and (dx or dy or turn or grow != 1.0):
        x0, y0, x1, y1 = dz.bounds(points)
        change = Transform(x=dx, y=dy, rotate=turn, scale_x=grow, scale_y=grow)
        middle = ((x0 + x1) / 2, (y0 + y1) / 2)
        parts = [lettering._move(dz.transform_geometry(o, change, middle), lambda a, b: (round(a, 4), round(b, 4)))
                 for o in parts]
        if turn:
            parts = [lettering.turn_with(o, change) for o in parts]
    angle = _number(edit.get("angle_deg"))
    if angle is not None:
        parts = [{**o, "params": {**(o.get("params") or {}), "angle_deg": angle % 180}} if o.get("kind") == "fill" else o
                 for o in parts]
    thread = edit.get("thread")
    if isinstance(thread, dict) and thread.get("color"):
        own = {k: str(thread.get(k) or "") for k in ("color", "name", "catalog", "brand")}
        parts = [{**o, "own_thread": own} for o in parts]
    return parts


def _apply_letter_edits(objects: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    """The letters with single letters moved, turned, resized, recolored or sewn at another angle
    (P5-A4), in the text's own unturned frame, after their layout and envelope. Changes are kept
    by letter number; ones for letters the text doesn't have are left alone. A letter given its
    own thread carries it as "own_thread". The cached letters passed in are never changed."""
    edits = spec.get("letter_edits")
    if not isinstance(edits, dict) or not edits:
        return objects
    members: dict[Any, list[int]] = {}
    for n, o in enumerate(objects):
        members.setdefault(o.get("letter"), []).append(n)
    out = list(objects)
    for letter, at in members.items():
        edit = edits.get(str(letter))
        if isinstance(edit, dict):
            for n, part in zip(at, _edited_letter([objects[n] for n in at], edit)):
                out[n] = part
    return out


def _text_parts(it: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Everything a text item sews, in sewing order: (the extras before the letters, the letters,
    the extras after them, warnings), turned, resized and mirrored with the text (but not yet
    moved to its place: add its x and y).

    Each letter has where it starts and ends: where you put its dots (`letters` on the item, in
    the text's own unturned frame), or else starting at the edge nearest where the letter before
    ended and ending towards the next letter, so the jumps between letters are short."""
    spec = {k: it.get(k) for k in lettering.TEXT_SPEC_KEYS}
    # Single letters are changed after the layout, so changing one doesn't lay the text out again.
    laid_out_from = {**spec, "letter_edits": None}
    # The font file's date and size are part of the key: an edited stitch font shows at once.
    key = json.dumps({**laid_out_from, "font_file": lettering.font_stamp(spec.get("font") or {})}, sort_keys=True)
    try:
        hit = _text_cache.get(key)
        if hit is None:
            hit = lettering.layout_text(laid_out_from)
            if len(_text_cache) > 64:
                _text_cache.pop(next(iter(_text_cache)))
            _text_cache[key] = hit
        objects, warnings = hit
        objects = _apply_letter_edits(objects, spec)
        before, after = lettering.extras.build(spec, objects)
    except (lettering.LetteringError, dz.DigitizeError) as exc:
        raise LayoutError(f"{it.get('name') or 'Text'}: {exc}") from exc
    t = Transform.from_dict(it.get("transform"))
    shape_t = Transform(rotate=t.rotate, scale_x=t.scale_x, scale_y=t.scale_y, flip_x=t.flip_x, flip_y=t.flip_y)

    def turned(o: dict[str, Any]) -> dict[str, Any]:
        if not shape_t.is_identity():
            o = lettering.turn_with(dz.transform_geometry(o, shape_t, (0.0, 0.0)), shape_t)
        return dict(o)  # a copy: the cached letters are never changed

    chosen = it.get("letters") or {}
    out = []
    for n, obj in enumerate(objects):
        mine = chosen.get(str(n)) or {}
        own = {k: mine[k] for k in ("start_mm", "end_mm") if dz._start_point(mine.get(k)) is not None}
        o = {**obj, "params": {**(obj.get("params") or {}), **own}} if own else obj
        out.append((turned(o), set(own)))
    # Short jumps: each letter ends towards the next (unless its end was chosen).
    for n, (o, own) in enumerate(out):
        if "end_mm" not in own and n + 1 < len(out) and o.get("kind") == "fill":
            ring = _letter_ring(out[n + 1][0])
            if ring:
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                o["params"] = {**(o.get("params") or {}), "end_mm": [round(cx, 3), round(cy, 3)]}
    return [turned(o) for o in before], [o for o, _ in out], [turned(o) for o in after], list(warnings)


def text_letters(it: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """A text item's letters as drawn shapes, as _text_parts gives them, plus warnings."""
    _, letters, _, warnings = _text_parts(it)
    return letters, warnings


def _part_stitches(o: dict[str, Any]) -> list:
    """A letter's or extra's stitches (x mm, y mm, command), in the text's own frame."""
    if o.get("kind") == "stitches":
        return lettering.stitchglyphs.records(o)
    return _generate_cached(o)[0]


def _stitched_parts(before: list[dict[str, Any]], letters: list[dict[str, Any]], after: list[dict[str, Any]],
                    chosen: dict[str, Any], fabric: str | None) -> tuple[list[dict[str, Any]], int]:
    """Every part stitched, in sewing order, and how many were too small to stitch. Each fill
    starts at its edge nearest where the part before it ended (unless chosen); the shadow, the
    letters and the outline each start afresh, so adding one doesn't change the others."""
    out: list[dict[str, Any]] = []
    skipped = 0
    for group, parts in (("before", before), ("letters", letters), ("after", after)):
        prev_end: tuple[float, float] | None = None
        for n, part in enumerate(parts):
            o = fabrics.apply(part, fabric)
            if (prev_end is not None and o.get("kind") == "fill" and dz._start_point((o.get("params") or {}).get("start_mm")) is None
                    and (group != "letters" or "start_mm" not in (chosen.get(str(n)) or {}))):
                o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
            try:
                mm = _part_stitches(o)
            except dz.DigitizeError:
                skipped += 1  # a speck too small to stitch (e.g. a tiny dot)
                continue
            sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
            if sts:
                prev_end = sts[-1]
            what = "letters" if group == "letters" else str(o.get("extra") or ("shadow" if group == "before" else "outline"))
            out.append({"what": what, "index": n, "part": o, "recs": mm, "stitches": sts})
    # A stitched font with several colors sews color by color across the whole text (a stable
    # sort, so each color keeps the letters' order).
    letters_at = [i for i, p in enumerate(out) if p["what"] == "letters"]
    if any(out[i]["part"].get("color_index") for i in letters_at):
        ordered = sorted((out[i] for i in letters_at), key=lambda p: int(p["part"].get("color_index") or 0))
        for i, p in zip(letters_at, ordered):
            out[i] = p
    return out, skipped


def _override(it: dict[str, Any], slot: int) -> dict[str, str] | None:
    """The Order & colors change for a text's color `slot` (0 is the text's own color; a stitched
    font's other colors follow), if there is one."""
    threads = it.get("threads") or []
    chosen = threads[slot] if 0 <= slot < len(threads) else None
    return {k: str(chosen.get(k, "")) for k in ("color", "name", "catalog", "brand")} if chosen else None


def _part_threads(p: dict[str, Any], it: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """(the thread a part is sewn in, the one it would have without an Order & colors change, the
    color slot such a change goes to, None if it takes none)."""
    o = p["part"]
    base = {**DEFAULT_THREAD, **(it.get("thread") or {})}
    if p["what"] != "letters":  # an extra: its own thread, else the text's
        if o.get("thread"):
            own = {**DEFAULT_THREAD, **o["thread"]}
            return own, own, None
        return _override(it, 0) or base, base, None
    if o.get("own_thread"):  # a single letter's own color wins
        own = {**DEFAULT_THREAD, **o["own_thread"]}
        return own, own, None
    slot = int(o.get("color_index") or 0)
    plain = {**DEFAULT_THREAD, **o["thread"]} if o.get("thread") else base  # a stitched font's own color
    return _override(it, slot) or plain, plain, slot


def _blocks(sewn: list[dict[str, Any]], it: dict[str, Any], idx: int,
            t: Transform) -> tuple[list[Block], list[dict[str, Any]], list[dict[str, Any]]]:
    """The stitched parts as color blocks (a new one wherever the thread changes, or from the
    shadow to the letters, or on to the outline or frame), moved into place. Records are numbered
    in sewing order across them (their `src`), so a stop or trim can be inserted in lettering too.

    Also each letter part (kind, outline, start and end (mm), which letter and line it is, and the
    run it's sewn in), for the dots on the design; and each run: its number (the block's number in
    this item), what it is, its letters, and the color slots an Order & colors change of the whole
    run goes to (none if the run doesn't hold all of their letters, or a letter has its own
    color: then the change goes to its letters)."""
    blocks: list[Block] = []
    runs: list[dict[str, Any]] = []
    parts: list[dict[str, Any]] = []
    run_slots: list[tuple[int, int | None]] = []  # (run, slot) for each letter part
    for p in sewn:
        o, mm = p["part"], p["recs"]
        thread, original, slot = _part_threads(p, it)
        part: list[Rec] = [[(x + t.x) * 10, (y + t.y) * 10, k, idx, -1] for x, y, k in mm]
        if not part:
            continue
        run = runs[-1] if runs else None
        if run is None or run["what"] != p["what"] or _thread_key(blocks[-1].thread) != _thread_key(thread):
            blocks.append(Block(dict(thread), [], [(idx, len(blocks))], dict(original), digitized=True))
            run = {"run": len(runs), "what": p["what"], "letters": [], "slots": []}
            runs.append(run)
        recs = blocks[-1].recs
        if recs:
            last = next((r for r in reversed(recs) if r[2] == pe.STITCH), None)
            first = next((r for r in part if r[2] == pe.STITCH), None)
            if last and first:
                d = math.hypot(first[0] - last[0], first[1] - last[1]) / 10
                if d > dz.TRIM_TRAVEL_MM:
                    recs.append([last[0], last[1], pe.TRIM, idx, -1])
                if d > dz.MIN_STITCH_MM:
                    recs.append([first[0], first[1], pe.JUMP, idx, -1])
        recs.extend(part)
        if p["what"] != "letters":
            continue
        letter = int(o.get("letter", p["index"]))
        if letter not in run["letters"]:
            run["letters"].append(letter)
        run_slots.append((run["run"], slot))
        sts = p["stitches"]
        if sts:
            look = "satin" if o.get("kind") == "fill" and it.get("style") in ("satin", "columns") else o.get("kind")
            parts.append({"index": p["index"], "kind": o.get("kind"), "look": look,
                          "start": [round(sts[0][0] + t.x, 2), round(sts[0][1] + t.y, 2)],
                          "end": [round(sts[-1][0] + t.x, 2), round(sts[-1][1] + t.y, 2)],
                          "ring": [[q[0] + t.x, q[1] + t.y] for q in _letter_ring(o)],
                          "letter": letter, "line": int(o.get("line", 0)), "run": run["run"]})
    for run in runs:
        here = {s for r, s in run_slots if r == run["run"]}
        if None not in here:
            run["slots"] = sorted(s for s in here if all(r == run["run"] for r, other in run_slots if other == s))
    n = 0
    for blk in blocks:
        for r in blk.recs:
            r[4] = n
            n += 1
    return blocks, parts, runs


def _text_block(it: dict[str, Any], idx: int, fabric: str | None = None) -> tuple[
        list[Block], list[str], tuple[float, float], list[dict[str, Any]], list[dict[str, Any]]]:
    """A text item as color blocks, its warnings, where it is, its letter parts and its runs (see
    _blocks). Letters are drawn shapes, so moving, turning or resizing the text regenerates
    stitches at the right density, and the fabric preset adjusts them like any other shape."""
    before, letters, after, warnings = _text_parts(it)
    t = Transform.from_dict(it.get("transform"))
    # Letters are stitched at the text's own origin and then moved, so moving or nudging text
    # reuses the cached stitches; turning, mirroring or resizing turns the stitch angle too.
    sewn, skipped = _stitched_parts(before, letters, after, it.get("letters") or {}, fabric)
    blocks, parts, runs = _blocks(sewn, it, idx, t)
    if skipped:
        warnings = [*warnings, f"{skipped} tiny part{'s' if skipped > 1 else ''} of the letters were too small to stitch."]
    return blocks, warnings, (t.x, t.y), parts, runs


def text_to_shapes(it: dict[str, Any]) -> dict[str, Any]:
    """Lettering broken into drawn shapes, one per letter part (and per part of a shadow, outline
    or frame), in sewing order, each in place and in its thread, starting and ending where the
    letters did: {"objects": [...]}. They can then be edited like any shape (their points, stitch
    type, density, direction and dots)."""
    before, letters, after, _ = _text_parts(it)
    if any(o.get("kind") == "stitches" for o in letters):
        raise LayoutError("Letters from a stitched font have no outlines to edit.")
    t = Transform.from_dict(it.get("transform"))
    whole = (it.get("threads") or [None])[0] or it.get("thread") or DEFAULT_THREAD
    chosen = it.get("letters") or {}
    label = it.get("name") or " ".join(str(it.get("text") or "Text").strip().splitlines())[:24]
    out = []
    for group, parts in (("before", before), ("letters", letters), ("after", after)):
        prev_end = None
        for n, o in enumerate(parts):
            # Each starts where the one before ended, as the lettering did (unless its start was chosen).
            if prev_end is not None and o.get("kind") == "fill" and (group != "letters" or "start_mm" not in (chosen.get(str(n)) or {})):
                o = {**o, "params": {**(o.get("params") or {}), "start_mm": [round(prev_end[0], 3), round(prev_end[1], 3)]}}
            try:
                mm, _ = _generate_cached(o)
                sts = [(x, y) for x, y, k in mm if k == pe.STITCH]
                prev_end = sts[-1] if sts else prev_end
            except dz.DigitizeError:
                continue  # a speck too small to stitch, as in the lettering
            moved = dz.transform_geometry(o, Transform(x=t.x, y=t.y), (0.0, 0.0))
            if group == "letters":
                thread, name = o.get("own_thread") or whole, f"{label} {n + 1}"
            else:
                thread, name = o.get("thread") or whole, f"{label} {o.get('extra') or 'extra'} {n + 1}"
            out.append({"kind": moved["kind"], "geometry": moved["geometry"], "params": moved.get("params") or {},
                        "thread": dict(thread), "name": name})
    return {"objects": out}
