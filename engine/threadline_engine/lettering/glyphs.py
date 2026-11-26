"""Each character as a letter: the objects to stitch it, from an outline font's shapes or a
stitch font's own, with what couldn't be drawn."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon

from ..digitize import stitches as dz
from .fontfile import _load_stitch_font
from .fonts import LetteringError, _glyph_shapes, _load

SATIN_MAX_STITCH_MM = 6.8  # rows narrower than this sew as one satin-like stitch (under the 7 mm "long loose stitch" check, with room for rounding)
SMALL_TEXT_MM = 6.0  # below this, dots and thin parts start to drop out


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
