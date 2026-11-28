"""Painted paths (model.py) as LUDD's shapes, in mm round the artwork's middle, in the file's
drawing order (what is drawn first is sewn first).

- A filled area is a fill, its holes worked out by the path's fill rule.
- A stroke under 1 mm wide is a running-stitch line, 1 to 12 mm a satin ribbon of that width,
  and wider its outline as a fill. "Lines as" can make every line a running stitch, or a satin.
- A path with both gives its fill, then its stroke on top.
- A filled rectangle at the bottom that covers the artwork is flagged as background. The
  artwork's size and middle leave it out, unless the option keep_background asks to keep it.
"""

from __future__ import annotations

import math
from typing import Any

from . import (MANY_SHAPES, MAX_COORDINATE, MAX_LENGTH_MM, MAX_SHAPES, MAX_SIZE_MM, MAX_STITCHES, ArtError, Deadline,
               Options)
from . import geometry as g
from .model import Drawing, Item

SATIN_FROM_MM = 1.0  # thinner strokes sew as running stitch (automatic)
SATIN_MAX_MM = 12.0  # the widest satin ribbon LUDD sews
LINE_MIN_MM = 1.0  # shorter lines are too small to sew
AREA_MIN_MM2 = 1.0  # smaller pieces are too small to sew
NOTHING_MM2 = 0.001  # no area at all (an open line's fill): not worth counting
HOLE_MIN_MM2 = 0.5
BACKGROUND_COVER = 0.95
# Stitches per mm² of fill and per mm of satin and running stitch, at LUDD's standard settings.
_FILL, _SATIN, _RUN = 1.0, 6.0, 0.5


def _check_numbers(items: list[Item]) -> None:
    for item in items:
        values = [item.stroke_width, *(c for s in item.subpaths for p in [s.start, *(q for seg in s.segments for q in seg[1:])]
                                       for c in p)]
        if not all(math.isfinite(v) and abs(v) <= MAX_COORDINATE for v in values):
            raise ArtError("This drawing has points that aren't numbers, or are far outside any real drawing. Save it "
                           "again from your drawing program.")


def _fill_shows(item: Item) -> bool:
    """False for a fill with no area at all (a straight line's default fill)."""
    return bool(item.fill) and not all(g.is_flat([s.start, *(q for seg in s.segments for q in seg[1:])])
                                       for s in item.subpaths)


def _stroke_box(item: Item) -> g.Box:
    if item.stroke_width > 0:
        return g.stroke_box(item.subpaths, item.stroke_width, item.cap, item.join, item.miter_limit)
    return g.path_box([s for s in item.subpaths if g.control_length(s) > 1e-9])


def _boxes(item: Item) -> tuple[g.Box | None, g.Box | None]:
    fill = g.path_box(item.subpaths) if _fill_shows(item) else None
    stroke = _stroke_box(item) if item.stroke else None
    return fill, stroke if stroke is None or not stroke.empty else None


def _union(boxes) -> g.Box:
    out = g.Box()
    for box in boxes:
        if box is not None:
            out.join(box)
    return out


def _is_rectangle(item: Item, box: g.Box) -> bool:
    if len(item.subpaths) != 1 or box.width <= 0 or box.height <= 0:
        return False
    ring = g.ring_of(g.flatten(item.subpaths[0], close=True)[0])
    return len(ring) >= 3 and abs(g.signed_area(ring)) >= BACKGROUND_COVER * box.width * box.height


def _background(items: list[Item], boxes: list, everything: g.Box) -> int | None:
    """The first thing drawn, if it's a filled rectangle covering the artwork (and not all of it)."""
    if len(items) < 2:
        return None
    fill = boxes[0][0]
    if fill is None or everything.width * everything.height <= 0:
        return None
    if fill.width * fill.height < BACKGROUND_COVER * everything.width * everything.height:
        return None
    return 0 if _is_rectangle(items[0], fill) else None


def _size_words(mm: float) -> str:
    return f"{mm / 1000:.1f} m" if mm >= 1000 else f"{mm:.0f} mm"


class _Shapes:
    def __init__(self, drawing: Drawing, opts: Options, scale: float, cx: float, cy: float, deadline: Deadline) -> None:
        self.drawing, self.opts, self.scale, self.cx, self.cy = drawing, opts, scale, cx, cy
        self.deadline = deadline
        self.out: list[dict[str, Any]] = []
        self.wide = 0  # strokes brought in as their outline
        self.thin = 0  # lines made into 1 mm satins
        self.stitches = 0.0
        self.painted: dict[int, Any] = {}  # id(item): what its big wide stroke covers (outline_big_strokes)

    def as_outline(self, width: float) -> bool:
        """Does a stroke `width` mm wide come in as its outline (too wide for a satin)?"""
        return self.opts.strokes != "lines" and width > SATIN_MAX_MM + 1e-6

    def outline_big_strokes(self, items: list[Item]) -> None:
        """The big wide strokes' outlines, worked out together first in a child process that can be
        stopped: GEOS can take minutes and gigabytes over one (geometry.OUTLINE_IN_CHILD)."""
        big, jobs = [], []
        for item in items:
            if not self.as_outline(item.stroke_width * self.scale):
                continue
            lines = [(points, closed) for points, _, closed in self.flat(item)]
            if g.is_big_stroke(lines):
                g.check_tangle(lines, self.deadline.check)
                big.append(item)
                jobs.append({"lines": lines, "width": item.stroke_width * self.scale, "cap": item.cap,
                             "join": item.join, "miter_limit": item.miter_limit})
        if jobs:
            from .child import outline_strokes

            for item, painted in zip(big, outline_strokes(jobs, self.deadline)):
                self.painted[id(item)] = painted

    def add(self, shape: dict[str, Any]) -> None:
        self.out.append(shape)
        if len(self.out) > MAX_SHAPES:
            raise ArtError(f"This artwork comes to more than {MAX_SHAPES:,} shapes, too many to import. Simplify it "
                           "first: merge shapes, remove tiny details and unused layers, then save it again.")

    def flat(self, item: Item, close: bool = False) -> list[tuple[list, set, bool]]:
        out = []
        for sub in item.subpaths:
            self.deadline.check()
            points, corners = g.flatten(g.scaled(sub, self.scale, self.cx, self.cy), close=close)
            out.append((points, corners, sub.closed))
        return out

    def areas(self, regions: list[g.Region], corners: set, color: str, name: str, background: bool = False) -> None:
        for region in regions:
            self.deadline.check()
            area = g.region_area(region)
            if area < AREA_MIN_MM2:
                if area > NOTHING_MM2:
                    self.drawing.skipped.add("tiny")
                continue
            outline, holes = region
            nodes = g.fit_ring(outline, corners | g.vertex_corners(outline, True), self.opts.spacing_mm)
            if len(nodes) < 3:
                self.drawing.skipped.add("tiny")
                continue
            geometry: dict[str, Any] = {"outline": nodes}
            kept = []
            for h in holes:
                self.deadline.check()
                if abs(g.signed_area(h)) >= HOLE_MIN_MM2:
                    fitted = g.fit_ring(h, corners | g.vertex_corners(h, True), self.opts.spacing_mm)
                    if len(fitted) >= 3:
                        kept.append(fitted)
            if kept:
                geometry["holes"] = kept
            shape = {"kind": "fill", "geometry": geometry, "color": color, "name": name}
            if background:
                shape["background"] = True
                background = False
            self.stitches += area * _FILL
            self.add(shape)

    def fill(self, item: Item, name: str, background: bool) -> None:
        rings, corners = [], set()
        for points, found, _ in self.flat(item, close=True):
            rings.append(g.ring_of(points))
            corners |= found
        regions = g.fill_regions(rings, item.fill_rule, self.deadline.check)
        self.areas(regions, corners, item.fill, name, background)

    def stroke(self, item: Item, name: str) -> None:
        width = item.stroke_width * self.scale
        mode = self.opts.strokes
        if item.dashed:
            self.drawing.skipped.add("dash")
        flattened = self.flat(item)
        if self.as_outline(width):
            regions = g.stroke_regions([(p, closed) for p, _, closed in flattened], width, item.cap, item.join,
                                       item.miter_limit, self.deadline.check, self.painted.get(id(item)))
            corners = set().union(*(c for _, c, _ in flattened)) if flattened else set()
            before = len(self.out)
            self.areas(regions, corners, item.stroke, name)
            self.wide += len(self.out) > before
            return
        satin = mode == "satins" or (mode == "auto" and width >= SATIN_FROM_MM - 1e-6)
        for points, corners, closed in flattened:
            self.deadline.check()
            length = g.line_length(points)
            if length < LINE_MIN_MM:
                if length > 1e-3 or (item.cap != "butt" and not item.stroke_width == 0):
                    self.drawing.skipped.add("tiny")
                continue
            closed = closed or (math.dist(points[0], points[-1]) <= g.JOIN_MM and length > 3 * g.JOIN_MM)
            closed = closed and len(g.ring_of(points)) >= 3
            nodes = g.fit_line(points, corners | g.vertex_corners(points, closed), closed, self.opts.spacing_mm)
            if len(nodes) < 2:
                self.drawing.skipped.add("tiny")
                continue
            geometry: dict[str, Any] = {"nodes": nodes}
            if satin:
                if width < SATIN_FROM_MM - 1e-6:
                    self.thin += 1
                geometry["width_mm"] = round(min(SATIN_MAX_MM, max(SATIN_FROM_MM, width)), 2)
            if closed and len(nodes) >= 3:
                geometry["closed"] = True
            self.stitches += length * (_SATIN if satin else _RUN)
            self.add({"kind": "satin" if satin else "run", "geometry": geometry, "color": item.stroke, "name": name})


def _warning(code: str, message: str, level: str = "warning") -> dict[str, str]:
    return {"level": level, "code": code, "message": message}


def _result(drawing: Drawing, size, shapes, warnings) -> dict[str, Any]:
    skipped = drawing.skipped.report()
    if not shapes:
        why = "See what was left out below." if skipped else "It has no filled areas or lines that show."
        warnings = [*warnings, _warning("art_empty", f"LUDD found nothing to sew in this file. {why}")]
    return {"size_mm": size, "scale_note": drawing.scale_note, "shapes": shapes, "skipped": skipped,
            "warnings": warnings, "pages": drawing.pages}


def convert(drawing: Drawing, opts: Options, deadline: Deadline) -> dict[str, Any]:
    """{size_mm, scale_note, shapes, skipped, warnings, pages}: shapes are {kind, geometry, color,
    name} (the background also has "background": true), in mm round the artwork's middle."""
    _check_numbers(drawing.items)
    items, boxes = [], []
    for item in drawing.items:
        deadline.check()
        fill, stroke = _boxes(item)
        if fill is not None or stroke is not None:
            items.append(item)
            boxes.append((fill, stroke))
    if not items:
        return _result(drawing, [0.0, 0.0], [], [])
    everything = _union(b for pair in boxes for b in pair)
    background = _background(items, boxes, everything)
    # Unless it's being kept, the background doesn't count toward the artwork's size and middle (a
    # white page behind a small logo would make Width size the page, not the logo).
    art = _union(b for i, pair in enumerate(boxes) for j, b in enumerate(pair)
                 if opts.keep_background or not (i == background and j == 0))
    if art.empty or max(art.width, art.height) <= 0:
        art = everything
    warnings: list[dict[str, str]] = []
    scale = 1.0
    if opts.width_mm is not None:
        if art.width >= 0.05:
            scale = opts.width_mm / art.width
        else:
            warnings.append(_warning("art_no_width", "This drawing has no width, so Width wasn't applied."))
    left_out_background = False
    if background is not None:
        fill = boxes[background][0]
        if max(fill.width, fill.height) * scale > MAX_SIZE_MM:
            left_out_background = True
            warnings.append(_warning("art_big_background", "The background rectangle is bigger than any hoop, so it "
                                                           "was left out.", "info"))
    others = _union(b for i, pair in enumerate(boxes) for j, b in enumerate(pair)
                    if not (left_out_background and i == background and j == 0))
    if max(others.width, others.height) * scale > MAX_SIZE_MM:
        wide, tall = art.width * scale, art.height * scale
        if opts.width_mm is None:
            raise ArtError(f"At its real size this drawing is {_size_words(wide)} wide and {_size_words(tall)} tall, "
                           "far bigger than any hoop. Set Width to the size you want it.")
        raise ArtError(f"At a width of {opts.width_mm:.0f} mm this drawing is {_size_words(tall)} tall, bigger than "
                       f"LUDD's largest design ({MAX_SIZE_MM:.0f} mm). Set a smaller Width.")
    if sum(g.control_length(s) for item in items for s in item.subpaths) * scale > MAX_LENGTH_MM:
        raise ArtError("This artwork has too much detail to import at this size. Simplify it in your drawing program, "
                       "or set a smaller Width.")
    cx, cy = (art.x0 + art.x1) / 2, (art.y0 + art.y1) / 2
    shapes = _Shapes(drawing, opts, scale, round(cx, 6), round(cy, 6), deadline)
    shapes.outline_big_strokes([item for i, item in enumerate(items) if boxes[i][1] is not None])
    for i, item in enumerate(items):
        deadline.check()
        name = item.name[:80]
        if boxes[i][0] is not None and not (left_out_background and i == background):
            shapes.fill(item, name, i == background)
        if boxes[i][1] is not None:
            shapes.stroke(item, name)
    if shapes.stitches > MAX_STITCHES:
        raise ArtError(f"At this size the artwork would take about {shapes.stitches / 1000:,.0f},000 stitches, more "
                       "than LUDD sews in one design. Set a smaller Width.")
    if shapes.wide:
        n = shapes.wide
        warnings.append(_warning("art_wide_stroke", ("1 stroke" if n == 1 else f"{n} strokes") +
                                 f" wider than {SATIN_MAX_MM:.0f} mm came in as filled shapes (a satin can be at most "
                                 f"{SATIN_MAX_MM:.0f} mm wide).", "info"))
    if shapes.thin:
        n = shapes.thin
        warnings.append(_warning("art_thin_satin", ("1 line" if n == 1 else f"{n} lines") +
                                 f" thinner than {SATIN_FROM_MM:.0f} mm became {SATIN_FROM_MM:.0f} mm satins.", "info"))
    if len(shapes.out) > MANY_SHAPES:
        warnings.append(_warning("art_many_shapes", f"This artwork comes to {len(shapes.out):,} shapes. That's a lot "
                                                    "to sew and to edit: leave out colors you don't need, or simplify "
                                                    "the drawing first."))
    size = [round(art.width * scale, 2), round(art.height * scale, 2)]
    return _result(drawing, size, shapes.out, warnings)
