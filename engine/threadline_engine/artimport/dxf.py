"""DXF artwork, read with ezdxf: lines, polylines, circles, arcs, ellipses, splines, hatches and
blocks, in millimeters by $INSUNITS, with y turned to point down. Outlines are lines (closed ones
become fills if asked), hatches are fills, and layer colors come across.

Linked drawings (xrefs) and pictures are never opened. Blocks are followed on paper first, so a
block that inserts itself, or copies that multiply out without end, are refused before anything is
built.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import threading
from dataclasses import dataclass

from . import MAX_COORDINATE, ArtError, Deadline, Options
from .geometry import flatten, ring_of
from .model import Drawing, Item, Point, Subpath, rgb_hex

MAX_ENTITIES = 50_000  # in the drawing, once every block is expanded
MAX_BLOCK_DEPTH = 16  # blocks inside blocks
MAX_POINTS = 300_000  # vertices and control points, once every block is expanded
MAX_SPLINE_DEGREE = 11
MAX_SPLINE_POINTS = 10_000

# $INSUNITS: millimeters in one drawing unit.
UNIT_MM = {1: 25.4, 2: 304.8, 3: 1_609_344.0, 4: 1.0, 5: 10.0, 6: 1000.0, 7: 1e6, 8: 2.54e-5, 9: 0.0254, 10: 914.4,
           11: 1e-7, 12: 1e-6, 13: 0.001, 14: 100.0, 15: 10_000.0, 16: 100_000.0, 17: 1e12, 18: 1.495978707e14,
           19: 9.4607304725808e18, 20: 3.0856775814914e19, 21: 304.800609601219, 22: 25.4000508001016,
           23: 914.401828803658, 24: 1_609_347.21869444}
NO_UNITS = ("This DXF doesn't say its units, so LUDD read it as millimeters. Set Width to the size you want if that's "
            "wrong.")
_CURVES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE", "CIRCLE", "ARC", "ELLIPSE", "SPLINE"})
_TEXT = frozenset({"TEXT", "MTEXT", "ATTRIB", "ARCALIGNEDTEXT", "RTEXT"})
_PICTURES = frozenset({"IMAGE", "OLE2FRAME", "OLEFRAME", "PDFUNDERLAY", "DWFUNDERLAY", "DGNUNDERLAY", "UNDERLAY"})
_NOTES = frozenset({"DIMENSION", "ARC_DIMENSION", "LARGE_RADIAL_DIMENSION", "LEADER", "MULTILEADER", "MLEADER",
                    "TOLERANCE", "ACAD_TABLE"})
_XREF_FLAGS = 4 | 8 | 16 | 32  # BLOCK flags: an xref, an overlay, externally dependent, resolved
_BINARY = b"AutoCAD Binary DXF"
# ezdxf's repairs drop objects it can't make sense of, and say so like this.
_REMOVED = re.compile(r"Removed (SPLINE|LWPOLYLINE|POLYLINE|LINE|CIRCLE|ARC|ELLIPSE|HATCH|MPOLYGON|INSERT)\b")

_import_lock = threading.Lock()


def load_ezdxf():
    """ezdxf, imported without it reading the computer's fonts. On import it opens every installed
    font and writes a cache of them into the home folder, unless it finds a cache already: so it is
    given one of its own that lists no fonts, in a folder deleted straight after. (Artwork import
    never draws text, so it needs no fonts.) It also reads no ezdxf settings from the home folder."""
    with _import_lock:
        if "ezdxf" not in sys.modules:
            names = ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "EZDXF_CONFIG_FILE")
            before = {name: os.environ.get(name) for name in names}
            work = tempfile.mkdtemp(prefix="ludd-ezdxf-")
            try:
                os.makedirs(os.path.join(work, "ezdxf"))
                with open(os.path.join(work, "ezdxf", "font_manager_cache.json"), "w", encoding="utf-8") as fh:
                    json.dump({"version": 2, "font-faces": []}, fh)
                os.environ["XDG_CACHE_HOME"] = os.environ["XDG_CONFIG_HOME"] = work
                os.environ.pop("EZDXF_CONFIG_FILE", None)
                try:
                    import ezdxf  # noqa: F401
                    import ezdxf.colors  # noqa: F401
                    import ezdxf.path  # noqa: F401
                    import ezdxf.recover  # noqa: F401
                except SystemExit:  # ezdxf stops the program on a settings file it can't read
                    raise ArtError("LUDD couldn't start its DXF reader because of an ezdxf.ini settings file on this "
                                   "computer. Rename that file and try again.") from None
            finally:
                for name, value in before.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
                shutil.rmtree(work, ignore_errors=True)
    return sys.modules["ezdxf"]


def _open(data: bytes):
    if data[:4] == b"AC10":
        raise ArtError("This is an AutoCAD DWG drawing, not a DXF. In your CAD program, use Save As and choose DXF.")
    if not data.rstrip(b"\x00\x1a \t\r\n").endswith(b"EOF"):  # ezdxf's recovery reads a cut file as empty
        raise ArtError("This DXF is cut off or damaged (it doesn't end the way a DXF does). Save or export it again "
                       "from your CAD program.")
    load_ezdxf()
    if data.startswith(_BINARY):
        from ezdxf.document import Drawing as Document
        from ezdxf.lldxf.tagger import binary_tags_loader

        return Document.load(binary_tags_loader(data)), 0
    from ezdxf import recover

    document, auditor = recover.read(io.BytesIO(data))
    return document, sum(1 for fix in auditor.fixes if _REMOVED.match(str(fix.message)))


@dataclass
class _Closed:
    """A closed outline that is to be a fill, kept until every outline is known (holes)."""

    item: Item


class _Reader:
    def __init__(self, document, opts: Options, deadline: Deadline, factor: float) -> None:
        self.doc, self.opts, self.deadline, self.factor = document, opts, deadline, factor
        self.drawing = Drawing()
        self.found: list[Item | _Closed] = []
        self.points = 0
        self.seen = 0
        self._sizes: dict[str, tuple[int, int]] = {}  # block name: (entities, depth) once expanded

    # ---------------------------------------------------------------- blocks

    def _block(self, name: str):
        return self.doc.blocks.get(name)

    @staticmethod
    def _is_xref(block) -> bool:
        head = block.block
        return head is not None and bool(head.dxf.get("flags", 0) & _XREF_FLAGS or head.dxf.get("xref_path", ""))

    @staticmethod
    def _grid(insert) -> tuple[int, int]:
        """(rows, columns) of a MINSERT: 1 for a direction with no spacing (its copies would land
        on top of each other)."""
        rows = insert.dxf.get("row_count", 1) if insert.dxf.get("row_spacing", 0) else 1
        columns = insert.dxf.get("column_count", 1) if insert.dxf.get("column_spacing", 0) else 1
        return max(1, int(rows)), max(1, int(columns))

    def expanded(self, entities, inside: tuple[str, ...] = ()) -> tuple[int, int]:
        """(how many entities these come to with every block copied in, how deep blocks go)."""
        total = depth = 0
        for entity in entities:
            if entity.dxftype() != "INSERT":
                total += 1
            else:
                rows, columns = self._grid(entity)
                count, below = self._block_size(entity.dxf.get("name", ""), inside)
                total += rows * columns * (count + 1)
                depth = max(depth, below + 1)
            if total > MAX_ENTITIES:
                raise ArtError(f"This DXF's blocks and repeats come to more than {MAX_ENTITIES:,} objects, too many "
                               "to import. Simplify the drawing in your CAD program.")
        return total, depth

    def _block_size(self, name: str, inside: tuple[str, ...]) -> tuple[int, int]:
        key = name.lower()
        if key in inside:
            raise ArtError(f"This DXF has a block that inserts itself (“{name}”), so it never ends. Fix or "
                           "explode that block in your CAD program and save the file again.")
        too_deep = ArtError(f"This DXF has blocks inside blocks more than {MAX_BLOCK_DEPTH} deep. Explode them in your "
                            "CAD program and save the file again.")
        if len(inside) >= MAX_BLOCK_DEPTH:
            raise too_deep
        if key not in self._sizes:
            block = self._block(name)
            if block is None or self._is_xref(block):
                self._sizes[key] = (0, 0)
            else:
                self._sizes[key] = self.expanded(block, (*inside, key))
        count, depth = self._sizes[key]
        if len(inside) + depth >= MAX_BLOCK_DEPTH:
            raise too_deep
        return count, depth

    # ---------------------------------------------------------------- layers and colors

    def _layer(self, name: str):
        return self.doc.layers.get(name) if self.doc.layers.has_entry(name) else None

    def _hidden(self, name: str) -> bool:
        layer = self._layer(name)
        return layer is not None and (layer.is_off() or layer.is_frozen())

    @staticmethod
    def _index_color(index: int) -> str:
        """An AutoCAD color number. 7 is white on a dark screen and black on paper: black here."""
        from ezdxf.colors import aci2rgb

        if index == 7 or not 1 <= index <= 255:
            return "#000000"
        return rgb_hex(*aci2rgb(index))

    @staticmethod
    def _rgb(value: int) -> str:
        return f"#{value & 0xFFFFFF:06x}"

    def _color(self, entity, layer_name: str, from_block: str) -> str:
        if entity.dxf.hasattr("true_color"):
            return self._rgb(entity.dxf.true_color)
        index = entity.dxf.get("color", 256)
        if index == 0:  # by block: the color of the INSERT that placed it
            return from_block
        if index != 256:  # not by layer
            return self._index_color(index)
        layer = self._layer(layer_name)
        if layer is None:
            return "#000000"
        if layer.dxf.hasattr("true_color"):
            return self._rgb(layer.dxf.true_color)
        return self._index_color(abs(layer.dxf.get("color", 7)))

    def _dashed(self, entity, layer_name: str) -> bool:
        linetype = str(entity.dxf.get("linetype", "BYLAYER")).upper()
        if linetype == "BYLAYER":
            layer = self._layer(layer_name)
            linetype = str(layer.dxf.get("linetype", "CONTINUOUS")).upper() if layer is not None else "CONTINUOUS"
        return linetype not in ("CONTINUOUS", "BYLAYER", "BYBLOCK", "")

    # ---------------------------------------------------------------- geometry

    def _place(self, matrix, v) -> Point:
        w = matrix.transform(v) if matrix is not None else v
        x, y = float(w[0]) * self.factor, -float(w[1]) * self.factor  # DXF's y points up
        if not (abs(x) <= MAX_COORDINATE and abs(y) <= MAX_COORDINATE):  # false for NaN too
            raise ArtError("This DXF has points that aren't numbers, or are far outside any real drawing. Save or "
                           "export it again from your CAD program.")
        return x, y

    def _count(self, n: int) -> None:
        self.points += n
        if self.points > MAX_POINTS:
            raise ArtError("This DXF has more points than LUDD imports. Simplify the drawing in your CAD program.")

    def _subpaths(self, path, matrix) -> list[Subpath]:
        out: list[Subpath] = []
        current = Subpath(self._place(matrix, path.start))
        for command in path.commands():
            kind = command.type.name
            if kind == "MOVE_TO":
                if current.segments:
                    out.append(current)
                current = Subpath(self._place(matrix, command.end))
            elif kind == "LINE_TO":
                current.segments.append(("L", self._place(matrix, command.end)))
            elif kind == "CURVE4_TO":
                current.segments.append(("C", self._place(matrix, command.ctrl1), self._place(matrix, command.ctrl2),
                                         self._place(matrix, command.end)))
            else:  # CURVE3_TO: a quadratic curve, as the cubic that draws the same
                (sx, sy), (qx, qy), (ex, ey) = current.end, self._place(matrix, command.ctrl), self._place(matrix, command.end)
                current.segments.append(("C", (sx + (qx - sx) * 2 / 3, sy + (qy - sy) * 2 / 3),
                                         (ex + (qx - ex) * 2 / 3, ey + (qy - ey) * 2 / 3), (ex, ey)))
        if current.segments:
            out.append(current)
        return out

    @staticmethod
    def _close_up(sub: Subpath) -> None:
        if math.dist(sub.end, sub.start) > 1e-9:
            sub.segments.append(("L", sub.start))
        sub.closed = True

    def _width(self, entity, matrix) -> float:
        """A wide polyline's width in mm (0: an ordinary line). Plotting line weights aren't widths."""
        kind = entity.dxftype()
        width = 0.0
        if kind == "LWPOLYLINE":
            width = entity.dxf.get("const_width", 0.0)
            if not width:
                widths = {(s, e) for s, e in entity.get_points("se")}
                if len(widths) == 1:
                    start, end = widths.pop()
                    width = start if start == end else 0.0
        elif kind == "POLYLINE":
            start, end = entity.dxf.get("default_start_width", 0.0), entity.dxf.get("default_end_width", 0.0)
            width = start if start == end else 0.0
        if not width:
            return 0.0
        if matrix is not None:
            ux, uy = matrix.transform_direction((1, 0, 0)), matrix.transform_direction((0, 1, 0))
            width *= math.sqrt(abs(ux[0] * uy[1] - ux[1] * uy[0]))
        width = float(width) * self.factor
        return width if 0 < width <= MAX_COORDINATE else 0.0

    @staticmethod
    def _closed(entity) -> bool:
        kind = entity.dxftype()
        if kind == "CIRCLE":
            return True
        if kind == "LWPOLYLINE":
            return bool(entity.closed)
        if kind == "POLYLINE":
            return bool(entity.is_closed)
        if kind == "SPLINE":
            return bool(entity.closed)
        if kind == "ELLIPSE":
            span = entity.dxf.get("end_param", math.tau) - entity.dxf.get("start_param", 0.0)
            return span % math.tau < 1e-6 or abs(span - math.tau) < 1e-6
        return False

    def _name(self, layer: str) -> str:
        return "" if layer == "0" else layer

    # ---------------------------------------------------------------- walking the drawing

    def walk(self, entities, matrix=None, color_from_block: str = "#000000", layer_from_block: str | None = None) -> None:
        for entity in entities:
            self.seen += 1
            if self.seen % 50 == 0:
                self.deadline.check()
            kind = entity.dxftype()
            if kind == "ATTDEF" or entity.dxf.get("invisible", 0):
                continue  # attribute templates aren't drawn; nor are hidden objects
            layer = entity.dxf.get("layer", "0")
            if layer == "0" and layer_from_block:  # layer 0 in a block takes the INSERT's layer
                layer = layer_from_block
            if kind == "INSERT":
                if (found := self._layer(layer)) is not None and found.is_frozen():
                    self.drawing.skipped.add("hidden_layer")
                    continue
                self._insert(entity, matrix, self._color(entity, layer, color_from_block), layer)
                continue
            if self._hidden(layer):
                self.drawing.skipped.add("hidden_layer")
                continue
            if kind in _CURVES:
                self._curve(entity, matrix, self._color(entity, layer, color_from_block), layer)
            elif kind in ("HATCH", "MPOLYGON"):
                self._hatch(entity, matrix, self._color(entity, layer, color_from_block), layer)
            elif kind in _TEXT:
                self.drawing.skipped.add("text")
            elif kind in _PICTURES:
                self.drawing.skipped.add("picture")
            elif kind in _NOTES:
                self.drawing.skipped.add("dimension")
            else:
                self.drawing.skipped.add("other")

    def _insert(self, insert, matrix, color: str, layer: str) -> None:
        block = self._block(insert.dxf.get("name", ""))
        if block is None:
            self.drawing.skipped.add("damaged")
            return
        if self._is_xref(block):
            self.drawing.skipped.add("xref")
            return
        self.drawing.skipped.add("text", len(insert.attribs))
        try:
            base = insert.matrix44()
            ocs = insert.ocs()
        except Exception:  # noqa: BLE001 - a flat or broken placement
            self.drawing.skipped.add("damaged")
            return
        from ezdxf.math import Matrix44, Vec3

        rows, columns = self._grid(insert)
        row_gap, column_gap = insert.dxf.get("row_spacing", 0), insert.dxf.get("column_spacing", 0)
        turn = insert.dxf.get("rotation", 0)
        for row in range(rows):
            for column in range(columns):
                self.deadline.check()
                placed = base
                if row or column:
                    step = Vec3(column * column_gap, row * row_gap, 0)
                    shift = ocs.to_wcs(step.rotate_deg(turn) if turn else step)
                    placed = base @ Matrix44.translate(shift.x, shift.y, shift.z)
                self.walk(block, placed if matrix is None else placed @ matrix, color, layer)

    def _curve(self, entity, matrix, color: str, layer: str) -> None:
        from ezdxf import path as ezpath

        kind = entity.dxftype()
        if kind == "POLYLINE" and (entity.is_polygon_mesh or entity.is_poly_face_mesh):
            self.drawing.skipped.add("other")
            return
        if kind == "SPLINE":
            if (entity.dxf.get("degree", 3) > MAX_SPLINE_DEGREE
                    or max(len(entity.control_points), len(entity.fit_points)) > MAX_SPLINE_POINTS):
                self.drawing.skipped.add("damaged")
                return
            self._count(len(entity.control_points) + len(entity.fit_points))
        elif kind == "LWPOLYLINE":
            self._count(len(entity))
        elif kind == "POLYLINE":
            self._count(len(entity.vertices))
        else:
            self._count(8)
        try:
            subpaths = self._subpaths(ezpath.make_path(entity), matrix)
            width = self._width(entity, matrix)
        except ArtError:
            raise
        except Exception:  # noqa: BLE001 - one broken object doesn't stop the rest
            self.drawing.skipped.add("damaged")
            return
        if not subpaths:
            return
        closed = self._closed(entity)
        for sub in subpaths:
            if closed or (len(sub.segments) > 1 and math.dist(sub.start, sub.end) < 0.01):
                self._close_up(sub)
        dashed = self._dashed(entity, layer)
        if self.opts.closed_as_fills and all(sub.closed for sub in subpaths):
            self.found.append(_Closed(Item(subpaths, fill=color, fill_rule="evenodd", name=self._name(layer),
                                           dashed=dashed)))
            return
        self.found.append(Item(subpaths, stroke=color, stroke_width=width, name=self._name(layer), dashed=dashed,
                               join="round", cap="round" if width else "butt"))

    def _hatch(self, hatch, matrix, color: str, layer: str) -> None:
        from ezdxf import path as ezpath

        points = 0
        for boundary in hatch.paths:
            if hasattr(boundary, "vertices"):  # a polyline boundary
                points += len(boundary.vertices)
                continue
            for edge in getattr(boundary, "edges", []):
                if type(edge).__name__ == "SplineEdge":
                    cps = len(edge.control_points) + len(edge.fit_points)
                    if getattr(edge, "degree", 3) > MAX_SPLINE_DEGREE or cps > MAX_SPLINE_POINTS:
                        self.drawing.skipped.add("damaged")
                        return
                    points += cps
                else:
                    points += 8
        self._count(points)
        try:
            subpaths = [sub for p in ezpath.from_hatch(hatch) for sub in self._subpaths(p, matrix)]
        except ArtError:
            raise
        except Exception:  # noqa: BLE001
            self.drawing.skipped.add("damaged")
            return
        if not subpaths:
            self.drawing.skipped.add("damaged")
            return
        for sub in subpaths:
            self._close_up(sub)
        if getattr(hatch, "has_gradient_data", False) and hatch.gradient is not None:
            self.drawing.skipped.add("gradient")
            color = rgb_hex(*hatch.gradient.color1)
        elif not hatch.dxf.get("solid_fill", 1):
            self.drawing.skipped.add("hatch_pattern")
        rule = {1: "outer", 2: "ignore"}.get(hatch.dxf.get("hatch_style", 0), "evenodd")
        self.found.append(Item(subpaths, fill=color, fill_rule=rule, name=self._name(layer)))

    # ---------------------------------------------------------------- closed outlines as fills

    def items(self) -> list[Item]:
        """Everything found, in drawing order. Closed outlines that become fills are paired up by
        color and layer: an outline right inside another is its hole (an island inside the hole
        is filled again), so a letter O or a washer comes in with its hole."""
        from shapely.geometry import Polygon
        from shapely.strtree import STRtree

        groups: dict[tuple[str, str], list[int]] = {}
        for i, found in enumerate(self.found):
            if isinstance(found, _Closed):
                groups.setdefault((found.item.fill, found.item.name), []).append(i)
        holes_of: dict[int, list[int]] = {}
        consumed: set[int] = set()
        for members in groups.values():
            self.deadline.check()
            shapes = []
            for i in members:
                ring = ring_of(flatten(self.found[i].item.subpaths[0], close=True)[0])
                shapes.append(Polygon(ring) if len(ring) >= 3 else Polygon())
            tree = STRtree(shapes)
            twice: set[int] = set()  # an outline drawn again on top of itself
            for a, outline in enumerate(shapes):
                if a in twice or outline.is_empty:
                    continue
                for b in sorted(tree.query(outline.exterior.buffer(0.01), predicate="intersects").tolist()):
                    if b > a and b not in twice and abs(shapes[b].area - outline.area) <= 0.01 * outline.length \
                            and shapes[b].exterior.hausdorff_distance(outline.exterior) < 0.01:
                        twice.add(b)
                        consumed.add(members[b])
            containers: list[list[int]] = [[] for _ in members]
            for a, outer in enumerate(shapes):
                if a in twice or not outer.is_valid or outer.is_empty:
                    continue
                for b in tree.query(outer, predicate="contains").tolist():
                    if b != a and b not in twice and shapes[b].is_valid and outer.area > shapes[b].area:
                        containers[b].append(a)
            for b, held_by in enumerate(containers):
                if len(held_by) % 2 == 1:
                    parent = min(held_by, key=lambda a: (shapes[a].area, a))
                    holes_of.setdefault(members[parent], []).append(members[b])
                    consumed.add(members[b])
        out = []
        for i, found in enumerate(self.found):
            if i in consumed:
                continue
            if isinstance(found, _Closed):
                item = found.item
                item.subpaths = item.subpaths + [s for h in sorted(holes_of.get(i, [])) for s in self.found[h].item.subpaths]
                out.append(item)
            else:
                out.append(found)
        return out


def read(data: bytes, opts: Options, deadline: Deadline) -> Drawing:
    document, removed = _open(data)
    deadline.check()
    # ezdxf fills in a default for a missing $INSUNITS in a few cases, so check the file itself.
    units = document.header.get("$INSUNITS", 0) if b"$INSUNITS" in data else 0
    factor = UNIT_MM.get(units, 1.0)
    reader = _Reader(document, opts, deadline, factor)
    reader.drawing.skipped.add("damaged", removed)
    if units not in UNIT_MM:
        reader.drawing.scale_note = NO_UNITS
    model = document.modelspace()
    reader.expanded(model)
    reader.walk(model)
    reader.drawing.items = reader.items()
    return reader.drawing
