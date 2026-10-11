"""Lettering: text from TrueType/OpenType fonts (or LUDD stitch fonts) as stitched letters.

Each letter's outline becomes fill objects (outer shapes with their holes). Two looks:
  satin  long side-to-side stitches across each stroke, like satin lettering (rows narrower
         than the maximum stitch become single stitches); the angle is chosen per letter to
         cross its strokes best
  fill   tatami, for big, bold letters

Text can run along a straight line, over an arc, under an arc, round a circle, or as a
three-letter monogram. Stitch fonts (.luddfont) are an open JSON format: letters as LUDD
objects, which can be made from any installed font and then hand-tuned.
"""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTCollection, TTFont
from shapely.geometry import Polygon

from .digitize import stitches as dz
from .storage import data_dir

FONT_EXTS = {".ttf", ".otf", ".ttc"}
STITCH_FONT_EXTS = {".luddfont", ".tlfont"}  # .tlfont: before the rename
STITCH_FONT_FORMATS = {"ludd-font", "threadline-font"}
SATIN_MAX_STITCH_MM = 7.0  # rows narrower than this sew as one satin-like stitch
SMALL_TEXT_MM = 5.0
INDEX_VERSION = 2


class LetteringError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- font discovery


def font_dirs() -> list[Path]:
    home = Path.home()
    if sys.platform == "win32":
        dirs = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    elif sys.platform == "darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library" / "Fonts"]
    else:
        dirs = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), home / ".local/share/fonts", home / ".fonts"]
    return dirs + [data_dir() / "fonts"]


def _names(font: TTFont) -> tuple[str, str]:
    name = font["name"]
    fam = name.getDebugName(16) or name.getDebugName(1) or ""
    sub = name.getDebugName(17) or name.getDebugName(2) or "Regular"
    return fam, sub


def list_fonts() -> list[dict[str, Any]]:
    """Installed fonts (family, style, file), plus LUDD stitch fonts. Indexed once and cached."""
    index_path = data_dir() / "font-index.json"
    try:
        cached = json.loads(index_path.read_text(encoding="utf-8"))
        if cached.get("version") != INDEX_VERSION:
            cached = {}
    except (OSError, json.JSONDecodeError):
        cached = {}
    old = cached.get("files", {})
    files: dict[str, Any] = {}
    for d in font_dirs():
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            ext = f.suffix.lower()
            if ext not in FONT_EXTS and ext not in STITCH_FONT_EXTS:
                continue
            key = str(f)
            try:
                mtime = f.stat().st_mtime
            except OSError:
                continue
            hit = old.get(key)
            if hit and hit["mtime"] == mtime:
                files[key] = hit
                continue
            entries = []
            try:
                if ext in STITCH_FONT_EXTS:
                    meta = json.loads(f.read_text(encoding="utf-8"))
                    entries.append({"family": meta.get("name") or f.stem, "style": "Stitch font", "index": 0, "kind": "stitch"})
                elif ext == ".ttc":
                    for i, font in enumerate(TTCollection(str(f), lazy=True).fonts):
                        fam, sub = _names(font)
                        if fam and "cmap" in font:
                            entries.append({"family": fam, "style": sub, "index": i, "kind": "outline"})
                else:
                    font = TTFont(str(f), lazy=True, fontNumber=0)
                    fam, sub = _names(font)
                    if fam and "cmap" in font:
                        entries.append({"family": fam, "style": sub, "index": 0, "kind": "outline"})
            except Exception:  # noqa: BLE001 - a damaged font file must not break the list
                entries = []
            files[key] = {"mtime": mtime, "entries": entries}
    try:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({"version": INDEX_VERSION, "files": files}), encoding="utf-8")
    except OSError:
        pass
    out = [{**e, "path": p} for p, v in files.items() for e in v["entries"]]
    # Symbol and icon fonts can't spell names; keep them but list text fonts first.
    out.sort(key=lambda e: (e["kind"] != "stitch", e["family"].lower(), e["style"] != "Regular", e["style"]))
    return out


def resolve_font(font: dict[str, Any]) -> dict[str, Any]:
    """The font itself if its file is here; otherwise the same family and style installed elsewhere
    (a project opened on another computer, or after a font was reinstalled)."""
    if Path(str(font.get("path", ""))).is_file():
        return font
    family, style = font.get("family"), font.get("style")
    if family:
        same = [f for f in list_fonts() if f["family"] == family]
        pick = next((f for f in same if f["style"] == style), same[0] if same else None)
        if pick:
            return {**font, "path": pick["path"], "index": pick["index"]}
    raise LetteringError(f"The font {family or Path(str(font.get('path'))).name} isn't installed on this computer; choose another")


# ---------------------------------------------------------------- outlines


class _FlattenPen(BasePen):
    """Collects glyph contours as polylines, flattening curves into short segments."""

    def __init__(self, glyphset, tolerance: float):
        super().__init__(glyphset)
        self.tol = tolerance
        self.contours: list[list[tuple[float, float]]] = []
        self.cur: list[tuple[float, float]] = []

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        n = max(2, min(32, int(math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3)) // max(1, int(self.tol)) + 2))
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            ))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        n = max(2, min(32, int(math.dist(p0, p1) + math.dist(p1, p2)) // max(1, int(self.tol)) + 2))
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) >= 3:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


@dataclass
class LoadedFont:
    font: TTFont
    glyphs: Any
    cmap: dict[int, str]
    upm: int
    cap: float  # cap height, font units
    kern: dict[tuple[str, str], int]


_fonts: dict[tuple[str, int], LoadedFont] = {}


def _load(path: str, index: int = 0) -> LoadedFont:
    key = (path, index)
    if key in _fonts:
        return _fonts[key]
    try:
        font = TTFont(path, fontNumber=index)
    except Exception as exc:  # noqa: BLE001
        raise LetteringError(f"Couldn't read the font {Path(path).name}") from exc
    cmap = font.getBestCmap() or {}
    glyphs = font.getGlyphSet()
    upm = font["head"].unitsPerEm
    cap = 0.0
    if "OS/2" in font and getattr(font["OS/2"], "sCapHeight", 0):
        cap = float(font["OS/2"].sCapHeight)
    if not cap and ord("H") in cmap:
        pen = _FlattenPen(glyphs, upm / 100)
        glyphs[cmap[ord("H")]].draw(pen)
        ys = [p[1] for c in pen.contours for p in c]
        cap = max(ys) if ys else 0.0
    cap = cap or upm * 0.7
    kern: dict[tuple[str, str], int] = {}
    if "kern" in font:
        for table in font["kern"].kernTables:
            kern.update(getattr(table, "kernTable", {}) or {})
    lf = LoadedFont(font, glyphs, cmap, upm, cap, kern)
    if len(_fonts) > 16:
        _fonts.pop(next(iter(_fonts)))
    _fonts[key] = lf
    return lf


def _signed_area(ring: list[tuple[float, float]]) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def _glyph_shapes(lf: LoadedFont, gname: str, scale: float) -> list[Polygon]:
    """A letter's filled shapes in mm (y down), with its holes.

    Fonts fill by winding direction: contours drawn the same way as the letter's largest one add
    area, contours drawn the other way cut holes. Script fonts often overlap pieces of a letter;
    merging the adding contours means overlaps are stitched once, not twice.
    """
    pen = _FlattenPen(lf.glyphs, lf.upm / 200)
    lf.glyphs[gname].draw(pen)
    contours = [c for c in pen.contours if abs(_signed_area(c)) > 1e-6]
    if not contours:
        return []
    main = 1 if _signed_area(max(contours, key=lambda c: abs(_signed_area(c)))) > 0 else -1
    adds, cuts = [], []
    for c in contours:
        poly = Polygon([(x * scale, -y * scale) for x, y in c]).buffer(0)
        if poly.is_empty:
            continue
        (adds if (1 if _signed_area(c) > 0 else -1) == main else cuts).append(poly)
    from shapely.ops import unary_union

    shape = unary_union(adds)
    if cuts:
        shape = shape.difference(unary_union(cuts))
    shape = shape.buffer(0)
    if shape.is_empty:
        return []
    parts = shape.geoms if hasattr(shape, "geoms") else [shape]
    return [g for g in parts if g.geom_type == "Polygon" and g.area > 0.02]


# ---------------------------------------------------------------- stitch fonts (.luddfont)


def _load_stitch_font(path: str) -> dict[str, Any]:
    try:
        f = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LetteringError(f"Couldn't read the stitch font {Path(path).name}") from exc
    if f.get("format") not in STITCH_FONT_FORMATS:
        raise LetteringError(f"{Path(path).name} isn't a LUDD stitch font")
    return f


# ---------------------------------------------------------------- layout


@dataclass
class Glyph:
    objects: list[dict[str, Any]]  # objects in mm, glyph origin at (0, 0) on the baseline, y down
    advance: float  # mm


def _outline_glyphs(text: str, path: str, index: int, size_mm: float, spacing_mm: float, style: str) -> list[Glyph]:
    lf = _load(path, index)
    scale = size_mm / lf.cap
    out: list[Glyph] = []
    prev = None
    for ch in text:
        gname = lf.cmap.get(ord(ch))
        if gname is None:
            gname = lf.cmap.get(ord("?"))
            if gname is None:
                continue
        adv = lf.font["hmtx"][gname][0] * scale + spacing_mm
        if prev is not None and (prev, gname) in lf.kern and out:
            out[-1].advance += lf.kern[(prev, gname)] * scale
        objs = []
        if not ch.isspace():
            for shape in _glyph_shapes(lf, gname, scale):
                objs.append(_fill_object(shape, style))
        out.append(Glyph(objs, adv))
        prev = gname
    return out


def _fill_object(shape: Polygon, style: str) -> dict[str, Any]:
    shape = shape.simplify(0.03)
    nodes = [[round(x, 3), round(y, 3), "c"] for x, y in list(shape.exterior.coords)[:-1]]
    holes = [[[round(x, 3), round(y, 3), "c"] for x, y in list(h.coords)[:-1]] for h in shape.interiors]
    if style == "fill":
        params = {"angle_deg": 45, "spacing_mm": 0.4, "stitch_mm": 3.5, "pull_comp_mm": 0.2, "underlay": ["edge", "tatami"]}
    else:
        params = {"angle_deg": _satin_angle(shape), "spacing_mm": 0.35, "stitch_mm": SATIN_MAX_STITCH_MM,
                  "pull_comp_mm": 0.25, "underlay": ["edge"]}
    return {"kind": "fill", "geometry": {"outline": nodes, "holes": holes}, "params": params}


def _satin_angle(shape: Polygon) -> float:
    """The stitch angle that crosses this letter's strokes best: fewest rows too long for one stitch."""
    from shapely import affinity

    best = (math.inf, 0.0)
    for angle in (0, 30, 60, 90, 120, 150):
        rot = affinity.rotate(shape, -angle, origin=(0, 0))
        rows = dz._rows(rot, angle, 0.6, 0.0)
        long_len = sum(max(0.0, (x1 - x0) - SATIN_MAX_STITCH_MM) for segs in rows for x0, x1 in segs)
        short_bias = sum(1 for segs in rows for x0, x1 in segs if x1 - x0 < 0.8) * 0.2  # avoid slivers
        score = long_len + short_bias
        if score < best[0] - 1e-9:
            best = (score, float(angle))
    return best[1]


def _stitch_font_glyphs(text: str, path: str, size_mm: float, spacing_mm: float) -> list[Glyph]:
    f = _load_stitch_font(path)
    k = size_mm / float(f.get("cap_height_mm") or size_mm)
    out = []
    for ch in text:
        g = (f.get("glyphs") or {}).get(ch)
        if g is None:
            if ch.isspace():
                out.append(Glyph([], float(f.get("space_mm", 0.35 * f.get("cap_height_mm", size_mm))) * k + spacing_mm))
            continue
        objs = []
        for o in g.get("objects") or []:
            t = dz.transform_geometry(o, _Scale(k), (0.0, 0.0))
            objs.append(t)
        out.append(Glyph(objs, float(g.get("advance_mm", 0)) * k + spacing_mm))
    return out


@dataclass
class _Scale:
    """A Transform-like scale about the origin (for dz.transform_geometry)."""

    k: float
    x: float = 0.0
    y: float = 0.0
    rotate: float = 0.0
    flip_x: bool = False
    flip_y: bool = False

    @property
    def scale_x(self) -> float:
        return self.k

    @property
    def scale_y(self) -> float:
        return self.k


def _move(obj: dict[str, Any], fn) -> dict[str, Any]:
    """Map every node of an object with fn(x, y) -> (x, y)."""
    g = dict(obj.get("geometry") or {})
    for key in ("nodes", "rail_a", "rail_b", "outline"):
        if g.get(key):
            g[key] = [[*fn(n[0], n[1]), *n[2:]] for n in g[key]]
    if g.get("holes"):
        g["holes"] = [[[*fn(n[0], n[1]), *n[2:]] for n in h] for h in g["holes"]]
    return {**obj, "geometry": g}


def layout_text(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Objects for a text item, centred on (0, 0) in mm, plus warnings."""
    text = str(spec.get("text") or "")
    font = spec.get("font") or {}
    size = float(spec.get("size_mm") or 12)
    spacing = float(spec.get("spacing_mm") or 0)
    style = spec.get("style") or "satin"
    shape = spec.get("shape") or {"type": "line"}
    monogram = bool(spec.get("monogram"))
    if not text.strip():
        raise LetteringError("Type some text first")
    if not font.get("path"):
        raise LetteringError("Choose a font")
    font = resolve_font(font)
    if not 2 <= size <= 200:
        raise LetteringError("Letter height must be between 2 and 200 mm")
    warnings = []
    if size < SMALL_TEXT_MM:
        warnings.append(f"Letters {size:.1f} mm tall are hard to stitch clearly; {SMALL_TEXT_MM:.0f} mm or more is safer.")

    def glyphs_for(t: str, sz: float) -> list[Glyph]:
        if Path(str(font["path"])).suffix.lower() in STITCH_FONT_EXTS:
            return _stitch_font_glyphs(t, font["path"], sz, spacing)
        return _outline_glyphs(t, font["path"], int(font.get("index", 0)), sz, spacing, style)

    objects: list[dict[str, Any]] = []
    if monogram:
        letters = [c for c in text if not c.isspace()][:3]
        if len(letters) != 3:
            raise LetteringError("A monogram needs three letters, e.g. first, last and middle initials")
        sizes = [size * 0.7, size, size * 0.7]
        parts = []
        for c, s in zip(letters, sizes):
            got = glyphs_for(c, s)
            parts.append(got[0] if got else Glyph([], 0.0))
        gap = size * 0.12
        widths = [p.advance - spacing for p in parts]
        total = sum(widths) + 2 * gap
        x = -total / 2
        for p, w, s in zip(parts, widths, sizes):
            # Vertically centre each letter on the big letter's middle.
            dy = s / 2 - size / 2
            objects += [_move(o, lambda a, b, x0=x, dy=dy: (a + x0, b + size / 2 + dy)) for o in p.objects]
            x += w + gap
        return _centre(objects), warnings

    glyphs = glyphs_for(text, size)
    total = sum(g.advance for g in glyphs) - spacing
    kind = shape.get("type", "line")
    radius = float(shape.get("radius_mm", 40))
    pos = 0.0
    for g in glyphs:
        if kind == "line":
            dx = pos - total / 2
            objects += [_move(o, lambda a, b, dx=dx: (a + dx, b + size / 2)) for o in g.objects]
        else:
            centre = pos + g.advance / 2 - total / 2  # arc length to the letter's middle
            if kind == "arc_down":
                r = radius + size  # letters hang below the circle, reading left to right
                phi = math.pi / 2 - centre / r
                rot = phi - math.pi / 2
            else:  # arc_up and circle: letters stand on the circle, reading clockwise from the top
                r = radius
                phi = -math.pi / 2 + centre / r
                rot = phi + math.pi / 2
            cx, cy = r * math.cos(phi), r * math.sin(phi)
            ca, sa = math.cos(rot), math.sin(rot)
            half = g.advance / 2

            def place(a, b, half=half, ca=ca, sa=sa, cx=cx, cy=cy):
                lx = a - half
                return (lx * ca - b * sa + cx, lx * sa + b * ca + cy)

            objects += [_move(o, place) for o in g.objects]
        pos += g.advance
    if kind != "line" and total > 2 * math.pi * radius:
        warnings.append("The text is longer than the circle; make the circle bigger or the letters smaller.")
    return _centre(objects), warnings


def _centre(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Centre the visible letters (not their spacing) on (0, 0), so the text sits where it's placed."""
    pts = [p for o in objects for p in dz.geometry_points(o)]
    if not pts:
        return objects
    x0, y0, x1, y1 = dz.bounds(pts)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return [_move(o, lambda a, b: (a - mx, b - my)) for o in objects]


def export_stitch_font(font: dict[str, Any], dest: str, chars: str, cap_height_mm: float = 12.0, style: str = "satin",
                       name: str = "") -> dict[str, Any]:
    """Convert an installed font into a LUDD stitch font (.luddfont) for hand-tuning."""
    lf = _load(font["path"], int(font.get("index", 0)))
    scale = cap_height_mm / lf.cap
    glyphs = {}
    for ch in dict.fromkeys(chars):
        gname = lf.cmap.get(ord(ch))
        if gname is None or ch.isspace():
            continue
        objs = [_fill_object(s, style) for s in _glyph_shapes(lf, gname, scale)]
        glyphs[ch] = {"advance_mm": round(lf.font["hmtx"][gname][0] * scale, 3), "objects": objs}
    space = lf.cmap.get(ord(" "))
    doc = {
        "format": "ludd-font",
        "version": 1,
        "name": name or f"{font.get('family', Path(font['path']).stem)} ({style})",
        "cap_height_mm": cap_height_mm,
        "space_mm": round(lf.font["hmtx"][space][0] * scale, 3) if space else round(cap_height_mm * 0.35, 3),
        "source": Path(font["path"]).name,
        "glyphs": glyphs,
    }
    out = Path(dest)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc), encoding="utf-8")
    return {"path": str(out), "glyphs": len(glyphs)}
