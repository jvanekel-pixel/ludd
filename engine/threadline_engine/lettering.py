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
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTCollection, TTFont
from shapely.geometry import Polygon

from .digitize import stitches as dz
from .storage import data_dir, read_json

FONT_EXTS = {".ttf", ".otf", ".ttc"}
STITCH_FONT_EXTS = {".luddfont", ".tlfont"}  # .tlfont: before the rename
STITCH_FONT_FORMATS = {"ludd-font", "threadline-font"}
SATIN_MAX_STITCH_MM = 6.8  # rows narrower than this sew as one satin-like stitch (under the 7 mm "long loose stitch" check, with room for rounding)
SMALL_TEXT_MM = 6.0  # below this, dots and thin parts start to drop out
INDEX_VERSION = 3  # 3: symbol fonts (no Latin letters) are marked and listed last


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
        cached = read_json(index_path)
        if not isinstance(cached, dict) or cached.get("version") != INDEX_VERSION:
            cached = {}  # an old, damaged or hand-edited index is simply rebuilt
    except (OSError, ValueError):
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
            hit = old.get(key) if isinstance(old, dict) else None
            if isinstance(hit, dict) and hit.get("mtime") == mtime and isinstance(hit.get("entries"), list):
                files[key] = hit
                continue
            entries = []
            try:
                if ext in STITCH_FONT_EXTS:
                    meta = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(meta, dict) and meta.get("format") in STITCH_FONT_FORMATS:
                        entries.append({"family": str(meta.get("name") or f.stem), "style": "Stitch font", "index": 0, "kind": "stitch"})
                elif ext == ".ttc":
                    for i, font in enumerate(TTCollection(str(f), lazy=True).fonts):
                        fam, sub = _names(font)
                        if fam and "cmap" in font:
                            entries.append({"family": fam, "style": sub, "index": i, "kind": "outline", "symbol": _is_symbol(font)})
                else:
                    font = TTFont(str(f), lazy=True, fontNumber=0)
                    fam, sub = _names(font)
                    if fam and "cmap" in font:
                        entries.append({"family": fam, "style": sub, "index": 0, "kind": "outline", "symbol": _is_symbol(font)})
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
    out.sort(key=lambda e: (e.get("kind") != "stitch", bool(e.get("symbol")), str(e.get("family", "")).lower(),
                            e.get("style") != "Regular", str(e.get("style", ""))))
    return out


def _is_symbol(font: TTFont) -> bool:
    """A symbol or icon font: typing letters gives nothing (Wingdings, Marlett...)."""
    try:
        cmap = font.getBestCmap() or {}
    except Exception:  # noqa: BLE001
        return False
    return not any(c in cmap for c in (ord("A"), ord("a"), ord("H")))


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


STAND_IN_FAMILIES = ("Arial", "Segoe UI", "Helvetica", "DejaVu Sans", "Liberation Sans")


def substitute_font() -> dict[str, Any] | None:
    """A standard font that's installed, to show text whose own font is missing."""
    outline = [f for f in list_fonts() if f.get("kind") == "outline" and not f.get("symbol")]
    for fam in STAND_IN_FAMILIES:
        same = [f for f in outline if f["family"] == fam]
        if same:
            return next((f for f in same if f["style"] == "Regular"), same[0])
    return outline[0] if outline else None


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
    kern: dict[tuple[str, str], int]  # the legacy 'kern' table
    gpos: list[Any] = field(default_factory=list)  # GPOS pair-kerning subtables (modern fonts kern here)
    _pairs: dict[tuple[str, str], int] = field(default_factory=dict)

    def kern_pair(self, left: str, right: str) -> int:
        """Kerning between two glyphs, font units (negative pulls them together)."""
        if not self.gpos:
            return self.kern.get((left, right), 0)
        key = (left, right)
        if key not in self._pairs:
            self._pairs[key] = _gpos_pair(self.gpos, left, right)
        return self._pairs[key]


def _gpos_subtables(font: TTFont) -> list[Any]:
    """The pair-adjustment subtables of the font's 'kern' feature (GPOS)."""
    if "GPOS" not in font:
        return []
    try:
        table = font["GPOS"].table
        if not table.FeatureList or not table.LookupList:
            return []
        indices = sorted({i for rec in table.FeatureList.FeatureRecord if rec.FeatureTag == "kern"
                          for i in rec.Feature.LookupListIndex})
        out = []
        for i in indices:
            lookup = table.LookupList.Lookup[i]
            for sub in lookup.SubTable:
                if lookup.LookupType == 9:  # extension: the real subtable is inside
                    sub = sub.ExtSubTable
                if getattr(sub, "LookupType", 2) == 2 and getattr(sub, "Format", 0) in (1, 2):
                    out.append(sub)
        return out
    except Exception:  # noqa: BLE001 - odd GPOS: fall back to the kern table
        return []


def _x_advance(value: Any) -> int:
    return int(getattr(value, "XAdvance", 0) or 0) if value is not None else 0


def _gpos_pair(subtables: list[Any], left: str, right: str) -> int:
    for sub in subtables:
        cov = sub.Coverage.glyphs
        if left not in cov:
            continue
        if sub.Format == 1:
            pairs = sub.PairSet[cov.index(left)].PairValueRecord
            for rec in pairs:
                if rec.SecondGlyph == right:
                    return _x_advance(rec.Value1)
        else:
            c1 = sub.ClassDef1.classDefs.get(left, 0) if sub.ClassDef1 else 0
            c2 = sub.ClassDef2.classDefs.get(right, 0) if sub.ClassDef2 else 0
            try:
                v = _x_advance(sub.Class1Record[c1].Class2Record[c2].Value1)
            except (IndexError, AttributeError):
                v = 0
            if v:
                return v
            # Class 0 of the second glyph means "no kerning in this subtable": try the next one.
    return 0


_fonts: dict[tuple[str, int, float], LoadedFont] = {}


def _stamp(path: str) -> float:
    """The file's change time, so a font replaced or edited on disk is read again."""
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


def font_stamp(font: dict[str, Any]) -> list[Any]:
    """What identifies a font file's current contents (path, change time, size): part of a cache key."""
    path = str((font or {}).get("path") or "")
    try:
        st = os.stat(path)
        return [path, st.st_mtime_ns, st.st_size]
    except OSError:
        return [path, 0, 0]


def _load(path: str, index: int = 0) -> LoadedFont:
    key = (path, index, _stamp(path))
    if key in _fonts:
        return _fonts[key]
    try:
        font = TTFont(path, fontNumber=index)
    except Exception as exc:  # noqa: BLE001
        raise LetteringError(f"Couldn't read the font {Path(path).name}") from exc
    cmap = font.getBestCmap() or {}
    glyphs = font.getGlyphSet()
    upm = font["head"].unitsPerEm
    # Letter height means the height of a capital H as drawn: measure it. The font's own cap-height
    # field is wrong in some fonts (script and East Asian fonts by up to a fifth).
    cap = 0.0
    if ord("H") in cmap:
        pen = _FlattenPen(glyphs, upm / 100)
        glyphs[cmap[ord("H")]].draw(pen)
        ys = [p[1] for c in pen.contours for p in c]
        cap = max(ys) - min(0.0, min(ys)) if ys else 0.0  # an H that dips below the line counts whole
    if cap <= 0 and "OS/2" in font and getattr(font["OS/2"], "sCapHeight", 0):
        cap = float(font["OS/2"].sCapHeight)
    cap = cap if cap > 0 else upm * 0.7
    kern: dict[tuple[str, str], int] = {}
    if "kern" in font:
        for table in font["kern"].kernTables:
            kern.update(getattr(table, "kernTable", {}) or {})
    lf = LoadedFont(font, glyphs, cmap, upm, cap, kern, _gpos_subtables(font))
    if len(_fonts) > 16:
        _fonts.pop(next(iter(_fonts)))
    _fonts[key] = lf
    return lf


def _signed_area(ring: list[tuple[float, float]]) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def _winding(pt: tuple[float, float], ring: list[tuple[float, float]]) -> int:
    """How many times a closed contour winds round a point (signed)."""
    px, py = pt
    w = 0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        side = (x1 - x0) * (py - y0) - (px - x0) * (y1 - y0)
        if y0 <= py < y1 and side > 0:
            w += 1
        elif y1 <= py < y0 and side < 0:
            w -= 1
    return w


def _glyph_shapes(lf: LoadedFont, gname: str, scale: float) -> list[Polygon]:
    """A letter's filled shapes in mm (y down), with its holes.

    Fonts fill by the non-zero winding rule: a place is inside the letter when the contours round it
    don't cancel out. So a hole is a contour drawn the other way, an island inside a hole (the C in
    a copyright sign) is filled again, and overlapping pieces of a script letter are stitched once.
    """
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    pen = _FlattenPen(lf.glyphs, lf.upm / 200)
    lf.glyphs[gname].draw(pen)
    contours = [c for c in pen.contours if abs(_signed_area(c)) > 1e-6]
    if not contours:
        return []
    lines = unary_union([LineString(c + [c[0]]) for c in contours])
    faces = [f for f in polygonize(lines) if f.area > 1e-6]
    keep = []
    for face in faces:
        p = face.representative_point()
        if sum(_winding((p.x, p.y), c) for c in contours) != 0:
            keep.append(face)
    if not keep:
        return []
    from shapely import affinity

    shape = affinity.scale(unary_union(keep), scale, -scale, origin=(0, 0)).buffer(0)
    if shape.is_empty:
        return []
    parts = shape.geoms if hasattr(shape, "geoms") else [shape]
    return [g for g in parts if g.geom_type == "Polygon" and g.area > 0.02]


# ---------------------------------------------------------------- stitch fonts (.luddfont)


def _load_stitch_font(path: str) -> dict[str, Any]:
    name = Path(path).name
    try:
        f = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError: not JSON, or not text at all
        raise LetteringError(f"Couldn't read the stitch font {name}") from exc
    if not isinstance(f, dict) or f.get("format") not in STITCH_FONT_FORMATS:
        raise LetteringError(f"{name} isn't a LUDD stitch font")
    if not isinstance(f.get("glyphs"), dict):
        raise LetteringError(f"The stitch font {name} has no letters in it")
    for key in ("cap_height_mm", "space_mm"):
        if f.get(key) is not None:
            try:
                if not float(f[key]) > 0:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise LetteringError(f"The stitch font {name} is damaged: its {key} should be a number above 0") from exc
    return f


# ---------------------------------------------------------------- layout


@dataclass
class Glyph:
    objects: list[dict[str, Any]]  # objects in mm, glyph origin at (0, 0) on the baseline, y down
    advance: float  # mm


@dataclass
class _Missing:
    """Characters a font couldn't draw (left out), and ones drawn as a near letter (é as e)."""

    left_out: list[str] = field(default_factory=list)
    near: list[tuple[str, str]] = field(default_factory=list)

    def warnings(self, stitch_font: bool) -> list[str]:
        out = []
        if self.left_out:
            chars = " ".join(dict.fromkeys(self.left_out))
            out.append(f"Not in this font, so left out: {chars}. Pick another font to stitch them.")
        if self.near:
            pairs = ", ".join(f"{a} as {b}" for a, b in dict.fromkeys(self.near))
            out.append(f"Not in this {'stitch ' if stitch_font else ''}font, so drawn as the nearest letter: {pairs}.")
        return out


def _outline_glyphs(text: str, path: str, index: int, size_mm: float, spacing_mm: float, style: str,
                    missing: _Missing | None = None) -> list[Glyph]:
    lf = _load(path, index)
    scale = size_mm / lf.cap
    out: list[Glyph] = []
    prev = None
    for ch in text:
        gname = lf.cmap.get(ord(ch))
        if gname is None and ch.isspace():
            gname = lf.cmap.get(ord(" "))
        if gname is None:
            if missing is not None:
                missing.left_out.append(ch)
            continue
        adv = lf.font["hmtx"][gname][0] * scale + spacing_mm
        if prev is not None and out:
            out[-1].advance += lf.kern_pair(prev, gname) * scale
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


def _near_letter(ch: str, have: dict[str, Any]) -> str | None:
    """A stand-in a stitch font does have: the other case, then the letter without its accent."""
    base = unicodedata.normalize("NFD", ch)[:1]
    for c in (ch.swapcase(), base, base.swapcase()):
        if len(c) == 1 and c != ch and isinstance(have.get(c), dict):
            return c
    return None


_PARAMS = {"fill": dz.FillParams, "run": dz.RunParams, "satin": dz.SatinParams}


def _check_letter_object(o: dict[str, Any]) -> None:
    """Raise ValueError/TypeError for a stitch-font object that can't be stitched (hand-editing slips)."""
    if not isinstance(o.get("geometry"), dict):
        raise ValueError("no geometry")
    dz.geometry_points(o)  # every node is a pair of numbers
    params = _PARAMS.get(str(o.get("kind")))
    if params is not None:
        params.from_dict(o.get("params") or {})


def _stitch_font_glyphs(text: str, path: str, size_mm: float, spacing_mm: float, missing: _Missing | None = None) -> list[Glyph]:
    f = _load_stitch_font(path)
    cap = float(f.get("cap_height_mm") or size_mm)
    k = size_mm / cap
    glyphs = f["glyphs"]
    kern = f.get("kern") if isinstance(f.get("kern"), dict) else {}
    out: list[Glyph] = []
    prev = ""
    try:
        for ch in text:
            key = ch if isinstance(glyphs.get(ch), dict) else None
            if key is None and ch.isspace():
                out.append(Glyph([], float(f.get("space_mm") or 0.35 * cap) * k + spacing_mm))
                prev = ""
                continue
            if key is None:
                key = _near_letter(ch, glyphs)
                if missing is not None:
                    if key is None:
                        missing.left_out.append(ch)
                    else:
                        missing.near.append((ch, key))
                if key is None:
                    continue
            g = glyphs[key]
            if prev and out and isinstance(kern.get(prev + key), (int, float)):
                out[-1].advance += float(kern[prev + key]) * k
            objs = [dz.transform_geometry(o, _Scale(k), (0.0, 0.0)) for o in g.get("objects") or [] if isinstance(o, dict)]
            for o in objs:
                _check_letter_object(o)  # checked now, not half way through stitching
            out.append(Glyph(objs, float(g.get("advance_mm") or 0) * k + spacing_mm))
            prev = key
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as exc:
        raise LetteringError(f"The stitch font {Path(path).name} is damaged (the letter {ch!r}); open it in a text "
                             "editor to fix it, or pick another font") from exc
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


def turn_with(obj: dict[str, Any], t: Any) -> dict[str, Any]:
    """A letter's stitch angle turned, mirrored and stretched with it (`t` like a layout Transform:
    rotate in degrees, scale_x/scale_y, flip_x/flip_y), so satin stitches still cross the strokes."""
    p = obj.get("params") or {}
    if obj.get("kind") != "fill" or p.get("angle_deg") is None:
        return obj
    a = math.radians(float(p["angle_deg"]))
    vx = math.cos(a) * (-1.0 if getattr(t, "flip_x", False) else 1.0) * float(getattr(t, "scale_x", 1.0))
    vy = math.sin(a) * (-1.0 if getattr(t, "flip_y", False) else 1.0) * float(getattr(t, "scale_y", 1.0))
    deg = math.degrees(math.atan2(vy, vx)) + float(getattr(t, "rotate", 0.0))
    deg = round(deg % 180.0, 3)
    if deg >= 180.0:
        deg = 0.0
    return {**obj, "params": {**p, "angle_deg": deg}}


@dataclass
class _Turn:
    """A plain turn (degrees), for turn_with."""

    rotate: float


def _clean_text(text: str) -> str:
    """Composed accents (e + combining acute -> é), line breaks and tabs as spaces, invisible marks out."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\t\n\r\v\f  ]", " ", text)
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def layout_text(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Objects for a text item, centred on (0, 0) in mm, plus warnings."""
    text = _clean_text(str(spec.get("text") or ""))
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
    warnings: list[str] = []
    try:
        font = resolve_font(font)
    except LetteringError:
        # Not on this computer (a project from another PC, an uninstalled font): show the text in a
        # standard font and say so, rather than refusing to open the whole design.
        stand_in = substitute_font()
        if not stand_in:
            raise
        warnings.append(f"The font {font.get('family') or 'used here'} isn't installed on this computer, so it's shown in "
                        f"{stand_in['family']}. Install it, or pick another font in the Lettering panel.")
        font = {**font, "path": stand_in["path"], "index": stand_in["index"]}
    if not 2 <= size <= 200:
        raise LetteringError("Letter height must be between 2 and 200 mm")
    smallest = size * 0.7 if monogram else size  # a monogram's side letters are smaller
    if smallest < SMALL_TEXT_MM:
        warnings.append(f"Letters {smallest:.1f} mm tall are hard to stitch clearly (dots and thin parts drop out); "
                        f"{SMALL_TEXT_MM:.0f} mm or more is safer.")

    is_stitch_font = Path(str(font["path"])).suffix.lower() in STITCH_FONT_EXTS
    missing = _Missing()

    def glyphs_for(t: str, sz: float) -> list[Glyph]:
        if is_stitch_font:
            return _stitch_font_glyphs(t, font["path"], sz, spacing, missing)
        return _outline_glyphs(t, font["path"], int(font.get("index", 0)), sz, spacing, style, missing)

    def done(objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        if not objects:
            if missing.left_out:
                raise LetteringError("This font has none of these letters. Pick another font.")
            raise LetteringError("Nothing to stitch: these letters are empty or too small in this font.")
        return objects, warnings + missing.warnings(is_stitch_font)

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
        return done(_centre(objects, vertical=False))

    glyphs = glyphs_for(text, size)
    total = sum(g.advance for g in glyphs) - spacing
    kind = shape.get("type", "line")
    radius = float(shape.get("radius_mm", 40))
    if kind == "path":
        closed = bool(shape.get("closed"))
        objects, length = _along_path(glyphs, total, size, shape.get("nodes") or [], closed)
        if total > length + 0.5:
            warnings.append(f"The text is longer than its line ({total:.0f} mm of letters on {length:.0f} mm), so letters "
                            f"{'overlap' if closed else 'past the ends pile up there'}. Make the line longer or the letters smaller.")
        return done(objects)
    if kind == "circle" and glyphs and total < 2 * math.pi * radius:
        # Round the whole circle: share the spare room out between the letters.
        extra = (2 * math.pi * radius - total - spacing) / len(glyphs)
        glyphs = [Glyph(g.objects, g.advance + extra) for g in glyphs]
        total = sum(g.advance for g in glyphs) - spacing
    pos = 0.0
    for g in glyphs:
        if kind == "line":
            dx = pos - total / 2
            objects += [_move(o, lambda a, b, dx=dx: (a + dx, b + size / 2)) for o in g.objects]
        else:
            centre = pos + g.advance / 2 - total / 2  # arc length to the letter's middle
            if kind == "arc_down":
                # Letters hang below the circle, reading left to right. Their tops are on the circle,
                # so they're spaced along it there; spaced along the lower baseline, the tops collide.
                r = radius + size
                phi = math.pi / 2 - centre / radius
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

            turn = _Turn(math.degrees(rot))
            objects += [turn_with(_move(o, place), turn) for o in g.objects]
        pos += g.advance
    if kind != "line" and total > 2 * math.pi * radius + 0.5:
        warnings.append("The text is longer than the circle; make the circle bigger or the letters smaller.")
    # Straight text keeps its baseline where it is (names with and without a y or g line up).
    return done(_centre(objects, vertical=kind != "line"))


def _along_path(glyphs: list[Glyph], total: float, size: float, nodes: list, closed: bool) -> tuple[list[dict[str, Any]], float]:
    """Letters standing on a line you drew (its points are in the text's own frame), centred on
    the middle of the line. Not re-centred: the letters stay on the line. Also returns the line's
    length (letters that don't fit sit at its ends).

    A line drawn right to left still reads left to right, upright. On a closed line the letters
    stand outside it, centred at its top."""
    from .digitize.paths import cumulative, flatten, point_at

    poly, _ = flatten(nodes, closed)
    if closed and poly:
        poly = poly + [poly[0]]
    if len(poly) < 2:
        raise LetteringError("Draw a line for the text to follow (at least two points)")
    if closed:
        if _signed_area(poly[:-1]) < 0:
            poly = poly[::-1]
    elif poly[-1][0] < poly[0][0] - 1e-6:
        poly = poly[::-1]
    cum = cumulative(poly)
    length = cum[-1]
    if length < 1.0:
        raise LetteringError("The line is too short for the text to follow; draw a longer line")
    if closed:
        top = min(range(len(poly) - 1), key=lambda i: (poly[i][1], poly[i][0]))
        middle = cum[top]
    else:
        middle = length / 2

    def at(s: float):
        if closed:
            s %= length
        return point_at(poly, cum, min(max(s, 0.0), length))

    objects: list[dict[str, Any]] = []
    pos = 0.0
    for g in glyphs:
        s_mid = middle + (pos + g.advance / 2 - total / 2)
        if not closed:
            s_mid = min(max(s_mid, 0.0), length)
        p = at(s_mid)
        if closed:
            a, b = at(s_mid - 0.5), at(s_mid + 0.5)
        else:
            a, b = at(max(0.0, s_mid - 0.5)), at(min(length, s_mid + 0.5))
        rot = math.atan2(b[1] - a[1], b[0] - a[0])
        ca, sa = math.cos(rot), math.sin(rot)
        half = g.advance / 2

        def place(x, y, half=half, ca=ca, sa=sa, px=p[0], py=p[1]):
            lx = x - half
            return (lx * ca - y * sa + px, lx * sa + y * ca + py)

        turn = _Turn(math.degrees(rot))
        objects += [turn_with(_move(o, place), turn) for o in g.objects]
        pos += g.advance
    return objects, length


def _centre(objects: list[dict[str, Any]], vertical: bool = True) -> list[dict[str, Any]]:
    """Centre the visible letters (not their spacing) on (0, 0), so the text sits where it's placed.
    `vertical=False`: only side to side (the baseline stays put)."""
    pts = [p for o in objects for p in dz.geometry_points(o)]
    if not pts:
        return objects
    x0, y0, x1, y1 = dz.bounds(pts)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2 if vertical else 0.0
    return [_move(o, lambda a, b: (a - mx, b - my)) for o in objects]


def stitch_font_dir() -> Path:
    """Where LUDD looks for your stitch fonts (and saves new ones)."""
    return data_dir() / "fonts"


def _free_path(folder: Path, stem: str, ext: str) -> Path:
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", stem).strip(" .") or "Stitch font"
    p = folder / f"{stem}{ext}"
    n = 1
    while p.exists():
        p = folder / f"{stem} ({n}){ext}"
        n += 1
    return p


EXTRA_CHARS = "‘’‚“”„–—…€•™"


def export_stitch_font(font: dict[str, Any], dest: str, chars: str, cap_height_mm: float = 12.0, style: str = "satin",
                       name: str = "") -> dict[str, Any]:
    """Convert an installed font into a LUDD stitch font (.luddfont) for hand-tuning.

    `chars` empty: every character the font can draw. `dest` empty: a new file in LUDD's fonts
    folder, where the font list finds it."""
    if not isinstance(font, dict) or not font.get("path"):
        raise LetteringError("Pick a font to convert first")
    if Path(str(font.get("path", ""))).suffix.lower() in STITCH_FONT_EXTS:
        raise LetteringError("This is already a stitch font; pick an ordinary font to convert")
    lf = _load(font["path"], int(font.get("index", 0)))
    scale = cap_height_mm / lf.cap
    if not chars:
        # Latin letters with their accents, digits and punctuation: what names and words need.
        chars = "".join(chr(c) for c in sorted(lf.cmap)
                        if (c < 0x250 or chr(c) in EXTRA_CHARS) and chr(c).isprintable() and not chr(c).isspace())
    glyphs: dict[str, Any] = {}
    gnames: dict[str, str] = {}
    for ch in dict.fromkeys(chars):
        gname = lf.cmap.get(ord(ch))
        if gname is None or ch.isspace():
            continue
        objs = [_fill_object(s, style) for s in _glyph_shapes(lf, gname, scale)]
        if not objs:
            continue
        glyphs[ch] = {"advance_mm": round(lf.font["hmtx"][gname][0] * scale, 3), "objects": objs}
        gnames[ch] = gname
    kern: dict[str, float] = {}
    for a, ga in gnames.items():
        for b, gb in gnames.items():
            k = lf.kern_pair(ga, gb)
            if k:
                kern[a + b] = round(k * scale, 3)
    space = lf.cmap.get(ord(" "))
    family = font.get("family") or Path(font["path"]).stem
    doc = {
        "format": "ludd-font",
        "version": 1,
        "name": name or f"{family} ({style})",
        "cap_height_mm": cap_height_mm,
        "space_mm": round(lf.font["hmtx"][space][0] * scale, 3) if space else round(cap_height_mm * 0.35, 3),
        "source": Path(font["path"]).name,
        "glyphs": glyphs,
        "kern": kern,
    }
    if dest:
        out = Path(dest)
        if out.suffix.lower() not in STITCH_FONT_EXTS:
            out = out.with_name(out.name + ".luddfont")  # the font list only looks for stitch-font files
    else:
        stitch_font_dir().mkdir(parents=True, exist_ok=True)
        out = _free_path(stitch_font_dir(), f"{family} {style}", ".luddfont")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc), encoding="utf-8")
    return {"path": str(out), "glyphs": len(glyphs), "folder": str(out.parent)}
