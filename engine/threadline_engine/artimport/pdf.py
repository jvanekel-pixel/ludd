"""PDF artwork (P7-D2): the vector paths on one page, read through PDFium's path calls (through
pypdfium2). PDF units are real (72 to the inch), forms are opened one level deep, and the page's
own rotation is applied. Text, pictures and shadings are counted and left out. Nothing is rendered,
scripts never run and links are never followed.

PDFium isn't safe to call from two threads at once (art.preview runs on its own thread), so one
lock is held round every call, and everything opened is closed before it's let go.
"""

from __future__ import annotations

import ctypes
import math
import threading

from . import MAX_COORDINATE, ArtError, Deadline, Options
from .model import Drawing, Item, Point, Subpath

PT_MM = 25.4 / 72
MAX_OBJECTS = 50_000  # on the page, forms included
MAX_SEGMENTS = 300_000
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_lock = threading.Lock()


def read(data: bytes, opts: Options, deadline: Deadline) -> Drawing:
    if b"%PDF-" not in data[:1024]:
        raise ArtError("This file isn't a PDF. Save or export it again as a PDF.")
    if b"%%EOF" not in data[-4096:]:  # PDFium would repair a cut file and read part of it
        raise ArtError("This PDF is cut off or damaged (it doesn't end the way a PDF does). Save or export it again.")
    with _lock:
        deadline.check()  # (it may have waited for another preview)
        return _read(data, opts, deadline)


def _read(data: bytes, opts: Options, deadline: Deadline) -> Drawing:
    import pypdfium2  # noqa: F401 - loads and starts PDFium
    import pypdfium2.raw as pdfium

    document = pdfium.FPDF_LoadMemDocument64(data, len(data), None)  # `data` outlives it
    if not document:
        error = pdfium.FPDF_GetLastError()
        if error == pdfium.FPDF_ERR_PASSWORD:
            raise ArtError("This PDF is locked with a password. Save a copy without the password from a PDF program "
                           "and import that.")
        if error == pdfium.FPDF_ERR_SECURITY:
            raise ArtError("This PDF is protected in a way LUDD can't open. Save an unprotected copy from a PDF "
                           "program and import that.")
        raise ArtError("LUDD couldn't read this PDF: it may be damaged. Save or export it again.")
    try:
        pages = pdfium.FPDF_GetPageCount(document)
        if pages < 1:
            raise ArtError("LUDD found no pages in this PDF. Save or export it again.")
        if opts.page >= pages:
            raise ArtError(f"This PDF has {pages} page{'s' if pages > 1 else ''}: choose one of them.")
        page = pdfium.FPDF_LoadPage(document, opts.page)
        if not page:
            raise ArtError(f"LUDD couldn't read page {opts.page + 1} of this PDF. Save or export it again.")
        try:
            reader = _Page(pdfium, deadline, pdfium.FPDFPage_GetRotation(page))
            for i in range(reader.count(pdfium.FPDFPage_CountObjects(page))):
                reader.object(pdfium.FPDFPage_GetObject(page, i), _IDENTITY, 0)
        finally:
            pdfium.FPDF_ClosePage(page)
    finally:
        pdfium.FPDF_CloseDocument(document)
    reader.drawing.pages = pages
    return reader.drawing


def _then(first: tuple, second: tuple) -> tuple:
    """The matrix (a, b, c, d, e, f) that applies `first`, then `second`."""
    a1, b1, c1, d1, e1, f1 = first
    a2, b2, c2, d2, e2, f2 = second
    return (a1 * a2 + b1 * c2, a1 * b2 + b1 * d2, c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2)


class _Page:
    def __init__(self, pdfium, deadline: Deadline, rotation: int) -> None:
        self.pdfium, self.deadline, self.rotation = pdfium, deadline, rotation % 4
        self.drawing = Drawing()
        self.objects = 0
        self.segments = 0

    def count(self, n: int) -> int:
        self.objects += max(0, n)
        if self.objects > MAX_OBJECTS:
            raise ArtError(f"This PDF page has more than {MAX_OBJECTS:,} objects, too many to import. Save just the "
                           "drawing you want, simplified, and import that.")
        return max(0, n)

    def object(self, obj, outer: tuple, depth: int) -> None:
        if not obj:
            self.drawing.skipped.add("damaged")
            return
        self.deadline.check()
        pdfium = self.pdfium
        kind = pdfium.FPDFPageObj_GetType(obj)
        if kind == pdfium.FPDF_PAGEOBJ_PATH:
            self.path(obj, outer)
        elif kind == pdfium.FPDF_PAGEOBJ_FORM:
            if depth:  # one level of forms is enough for the programs that make them
                self.drawing.skipped.add("nested_form")
                return
            inside = _then(self.matrix(obj), outer)
            for i in range(self.count(pdfium.FPDFFormObj_CountObjects(obj))):
                self.object(pdfium.FPDFFormObj_GetObject(obj, i), inside, depth + 1)
        elif kind == pdfium.FPDF_PAGEOBJ_TEXT:
            self.drawing.skipped.add("text")
        elif kind == pdfium.FPDF_PAGEOBJ_IMAGE:
            self.drawing.skipped.add("picture")
        elif kind == pdfium.FPDF_PAGEOBJ_SHADING:
            self.drawing.skipped.add("shading")
        else:
            self.drawing.skipped.add("other")

    def matrix(self, obj) -> tuple:
        m = self.pdfium.FS_MATRIX()
        if not self.pdfium.FPDFPageObj_GetMatrix(obj, ctypes.byref(m)):
            return _IDENTITY
        return (m.a, m.b, m.c, m.d, m.e, m.f)

    def color(self, getter, obj) -> str | None:
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        if not getter(obj, ctypes.byref(r), ctypes.byref(g), ctypes.byref(b), ctypes.byref(a)) or a.value == 0:
            return None
        return f"#{r.value & 255:02x}{g.value & 255:02x}{b.value & 255:02x}"

    def path(self, obj, outer: tuple) -> None:
        pdfium = self.pdfium
        fill_mode, stroked = ctypes.c_int(), pdfium.FPDF_BOOL()
        if not pdfium.FPDFPath_GetDrawMode(obj, ctypes.byref(fill_mode), ctypes.byref(stroked)):
            self.drawing.skipped.add("damaged")
            return
        fill = self.color(pdfium.FPDFPageObj_GetFillColor, obj) if fill_mode.value else None
        stroke = self.color(pdfium.FPDFPageObj_GetStrokeColor, obj) if stroked.value else None
        if not fill and not stroke:
            return  # paints nothing (a clipping path, say)
        matrix = _then(self.matrix(obj), outer)
        subpaths = self.subpaths(obj, matrix)
        if not subpaths:
            return
        if self.clipped(obj):
            self.drawing.skipped.add("clip")
        width = 0.0
        if stroke:
            w = ctypes.c_float()
            if pdfium.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(w)):
                a, b, c, d, _, _ = matrix
                width = w.value * math.sqrt(abs(a * d - b * c)) * PT_MM
            if not (0 <= width <= MAX_COORDINATE):
                width = 0.0
        caps = {pdfium.FPDF_LINECAP_ROUND: "round", pdfium.FPDF_LINECAP_PROJECTING_SQUARE: "square"}
        joins = {pdfium.FPDF_LINEJOIN_ROUND: "round", pdfium.FPDF_LINEJOIN_BEVEL: "bevel"}
        self.drawing.items.append(Item(
            subpaths, fill=fill, fill_rule="evenodd" if fill_mode.value == pdfium.FPDF_FILLMODE_ALTERNATE else "nonzero",
            stroke=stroke, stroke_width=width, cap=caps.get(pdfium.FPDFPageObj_GetLineCap(obj), "butt"),
            join=joins.get(pdfium.FPDFPageObj_GetLineJoin(obj), "miter"), miter_limit=10.0,
            dashed=bool(stroke) and pdfium.FPDFPageObj_GetDashCount(obj) > 0))

    def clipped(self, obj) -> bool:
        """Does a clip cut this shape? A box that holds all of it doesn't (many programs put one
        round every page); any other clip is counted. A form's box is a clip, in the form's own
        coordinates, like the shape's bounds there."""
        pdfium = self.pdfium
        clip = pdfium.FPDFPageObj_GetClipPath(obj)
        paths = pdfium.FPDFClipPath_CountPaths(clip) if clip else 0
        if paths <= 0:
            return False
        sides = [ctypes.c_float() for _ in range(4)]
        if not pdfium.FPDFPageObj_GetBounds(obj, *(ctypes.byref(s) for s in sides)):
            return False
        left, bottom, right, top = (s.value for s in sides)
        x, y = ctypes.c_float(), ctypes.c_float()
        for i in range(min(paths, 16)):
            n = pdfium.FPDFClipPath_CountPathSegments(clip, i)
            if not 4 <= n <= 6:  # not a plain box (and never read through a long one)
                return True
            xs, ys = set(), set()
            for j in range(n):
                segment = pdfium.FPDFClipPath_GetPathSegment(clip, i, j)
                if (not segment or pdfium.FPDFPathSegment_GetType(segment) == pdfium.FPDF_SEGMENT_BEZIERTO
                        or not pdfium.FPDFPathSegment_GetPoint(segment, ctypes.byref(x), ctypes.byref(y))):
                    return True
                xs.add(round(x.value, 2))
                ys.add(round(y.value, 2))
            if len(xs) != 2 or len(ys) != 2:
                return True
            if left < min(xs) - 0.5 or bottom < min(ys) - 0.5 or right > max(xs) + 0.5 or top > max(ys) + 0.5:
                return True
        return False

    def subpaths(self, obj, matrix: tuple) -> list[Subpath]:
        pdfium = self.pdfium
        n = pdfium.FPDFPath_CountSegments(obj)
        self.segments += max(0, n)
        if self.segments > MAX_SEGMENTS:
            raise ArtError("This PDF page has more points than LUDD imports. Save just the drawing you want, "
                           "simplified, and import that.")
        a, b, c, d, e, f = matrix
        x, y = ctypes.c_float(), ctypes.c_float()
        turn = self.rotation

        def place(px: float, py: float) -> Point:
            vx, vy = (a * px + c * py + e) * PT_MM, -(b * px + d * py + f) * PT_MM  # PDF's y points up
            if turn:  # the page's /Rotate, clockwise as shown
                vx, vy = ((-vy, vx), (-vx, -vy), (vy, -vx))[turn - 1]
            if not (abs(vx) <= MAX_COORDINATE and abs(vy) <= MAX_COORDINATE):  # false for NaN too
                raise ArtError("This PDF has points far outside any real drawing. Save or export it again.")
            return vx, vy

        out: list[Subpath] = []
        current: Subpath | None = None
        bezier: list[Point] = []
        for i in range(max(0, n)):
            if i % 1000 == 999:
                self.deadline.check()
            segment = pdfium.FPDFPath_GetPathSegment(obj, i)
            kind = pdfium.FPDFPathSegment_GetType(segment)
            if not segment or not pdfium.FPDFPathSegment_GetPoint(segment, ctypes.byref(x), ctypes.byref(y)):
                continue
            point = place(x.value, y.value)
            if kind == pdfium.FPDF_SEGMENT_MOVETO or current is None:
                if current is not None and current.segments:
                    out.append(current)
                current, bezier = Subpath(point), []
                if kind == pdfium.FPDF_SEGMENT_MOVETO:
                    continue
            if kind == pdfium.FPDF_SEGMENT_LINETO:
                current.segments.append(("L", point))
            elif kind == pdfium.FPDF_SEGMENT_BEZIERTO:
                bezier.append(point)
                if len(bezier) < 3:
                    continue
                current.segments.append(("C", *bezier))
                bezier = []
            if pdfium.FPDFPathSegment_GetClose(segment):
                if math.dist(current.end, current.start) > 1e-9:
                    current.segments.append(("L", current.start))
                current.closed = True
                if current.segments:
                    out.append(current)
                current = None
        if current is not None and current.segments:
            out.append(current)
        return out
