"""Fonts: which are installed, an outline font as loaded, its kerning, and each letter's shapes."""

from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTCollection, TTFont
from shapely.geometry import Polygon

from ..storage import data_dir, read_json

FONT_EXTS = {".ttf", ".otf", ".ttc"}
STITCH_FONT_EXTS = {".luddfont", ".tlfont"}  # .tlfont: before the rename
STITCH_FONT_FORMATS = {"ludd-font", "threadline-font"}
INDEX_VERSION = 4  # 4: stitch fonts whose letters are stitches say so; 3: symbol fonts are marked and listed last


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
                        entry = {"family": str(meta.get("name") or f.stem), "style": "Stitch font", "index": 0, "kind": "stitch"}
                        glyphs = meta.get("glyphs")
                        if isinstance(glyphs, dict) and any(isinstance(g, dict) and "stitches" in g for g in glyphs.values()):
                            entry["made_of"] = "stitches"  # letters made of stitches, from letter files
                        entries.append(entry)
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
