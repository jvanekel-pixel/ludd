"""Each character as a letter: the objects to stitch it, from an outline font's shapes or a
stitch font's own, with what couldn't be drawn."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from shapely.geometry import Polygon

from ..digitize import stitches as dz
from . import stitchglyphs
from .fontfile import _load_stitch_font
from .fonts import LetteringError, _glyph_shapes, _load

SATIN_MAX_STITCH_MM = 6.8  # rows narrower than this sew as one satin-like stitch (under the 7 mm "long loose stitch" check, with room for rounding)
SMALL_TEXT_MM = 6.0  # below this, dots and thin parts start to drop out, and underlay is left out
THIN_STROKE_MM = 0.8  # strokes thinner than this sew as a single line


def small_text_warning(smallest_mm: float) -> str:
    """Said when the smallest letters are under SMALL_TEXT_MM tall."""
    return (f"Letters {round(smallest_mm, 1):g} mm tall are hard to stitch clearly; underlay is left out so they "
            f"stay thin. {SMALL_TEXT_MM:g} mm or more is safer.")


def thin_stroke_warning(width_mm: float) -> str:
    """Said when a text's letters have strokes under THIN_STROKE_MM wide."""
    return (f"This font's strokes are only {round(width_mm, 1):g} mm wide at this size, so they sew as a single line. "
            "Use a bolder font or bigger letters.")


@dataclass
class Glyph:
    objects: list[dict[str, Any]]  # objects in mm, glyph origin at (0, 0) on the baseline, y down
    advance: float  # mm


@dataclass
class _Missing:
    """Characters a font couldn't draw (left out), and ones drawn as a near letter (é as e); also
    what building the letters found: each letter's stroke width (mm) and how many letters
    couldn't be sewn as True satin."""

    left_out: list[str] = field(default_factory=list)
    near: list[tuple[str, str]] = field(default_factory=list)
    stroke_widths: list[float] = field(default_factory=list)
    fell_back: int = 0

    def warnings(self, stitch_font: bool) -> list[str]:
        out = []
        if self.left_out:
            chars = " ".join(dict.fromkeys(self.left_out))
            out.append(f"Not in this font, so left out: {chars}. Pick another font to stitch them.")
        if self.near:
            pairs = ", ".join(f"{a} as {b}" for a, b in dict.fromkeys(self.near))
            out.append(f"Not in this {'stitch ' if stitch_font else ''}font, so drawn as the nearest letter: {pairs}.")
        if self.stroke_widths:
            ws = sorted(self.stroke_widths)
            typical = ws[len(ws) // 2]  # the median letter's: a full stop or a hyphen doesn't decide it
            if typical < THIN_STROKE_MM:
                out.append(thin_stroke_warning(typical))
        if self.fell_back:
            n = self.fell_back
            out.append(f"{n} letter{'s' if n != 1 else ''} couldn't be sewn as True satin, so "
                       f"{'they are' if n != 1 else 'it is'} sewn in Satin look.")
        return out


def stroke_width(shapes: list[Polygon]) -> float | None:
    """A letter's typical stroke width (mm): its biggest part taken as a bent bar of the same area
    and outline length (w = (P - sqrt(P² - 16A)) / 4), so a ring, a bar and a square dot all give
    their true thickness."""
    if not shapes:
        return None
    # Biggest part first; equal areas (rounded) by their place, never by floating-point order.
    big = min(shapes, key=lambda s: (-round(s.area, 6), round(s.bounds[0], 6), round(s.bounds[1], 6)))
    a, p = big.area, big.length
    return (p - math.sqrt(max(p * p - 16 * a, 0.0))) / 4


def _glyph_objects(shapes: list[Polygon], style: str, size_mm: float,
                   notes: _Missing | None = None) -> list[dict[str, Any]]:
    """The objects that stitch one outline letter's shapes (mm, from the letter's origin on the
    baseline), in the look `style` for letters `size_mm` tall.

    True satin ("columns") sews each stroke as its own column (satin.columns). A letter where that
    doesn't work is sewn whole in Satin look, never half and half; `notes` counts those."""
    if style == "columns":
        from . import satin

        try:
            return [o for shape in shapes for o in satin.columns(shape, size_mm)]
        except Exception:  # noqa: BLE001  (any failure: the whole letter in Satin look, never half sewn)
            if notes is not None:
                notes.fell_back += 1
            style = "satin"
    return [_fill_object(shape, style, size_mm) for shape in shapes]


def _outline_glyphs(text: str, path: str, index: int, size_mm: float, spacing_mm: float, style: str,
                    missing: _Missing | None = None,
                    shape_map: Callable[[Polygon], Polygon] | None = None) -> list[Glyph]:
    """`shape_map` changes each letter's shape about its own baseline before it is turned into
    objects (a slant), so the stitching is chosen for the shape as it is sewn."""
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
            shapes = _glyph_shapes(lf, gname, scale)
            if shape_map is not None:
                shapes = [shape_map(shape) for shape in shapes]
            if missing is not None and (w := stroke_width(shapes)) is not None:
                missing.stroke_widths.append(w)
            objs = _glyph_objects(shapes, style, size_mm, missing)
        out.append(Glyph(objs, adv))
        prev = gname
    return out


def _fill_object(shape: Polygon, style: str, size_mm: float | None = None) -> dict[str, Any]:
    """One letter shape as a fill: woven ("fill"), or rows across its strokes (Satin look, any
    other style). Letters under SMALL_TEXT_MM tall (`size_mm`) get no underlay, so they stay thin."""
    shape = shape.simplify(0.03)
    nodes = [[round(x, 3), round(y, 3), "c"] for x, y in list(shape.exterior.coords)[:-1]]
    holes = [[[round(x, 3), round(y, 3), "c"] for x, y in list(h.coords)[:-1]] for h in shape.interiors]
    if style == "fill":
        params = {"angle_deg": 45, "spacing_mm": 0.4, "stitch_mm": 3.5, "pull_comp_mm": 0.2, "underlay": ["edge", "tatami"]}
    else:
        params = {"angle_deg": _satin_angle(shape), "spacing_mm": 0.35, "stitch_mm": SATIN_MAX_STITCH_MM,
                  "pull_comp_mm": 0.25, "underlay": ["edge"]}
    if size_mm is not None and size_mm < SMALL_TEXT_MM:
        params["underlay"] = []  # an empty list, not None: fabrics.apply would add one back
    return {"kind": "fill", "geometry": {"outline": nodes, "holes": holes}, "params": params}


def _satin_angle(shape: Polygon) -> float:
    """The stitch angle that crosses this letter's strokes best: fewest rows too long for one stitch."""
    from shapely import affinity

    best = (math.inf, 0.0)
    for angle in (0, 30, 60, 90, 120, 150):
        rot = affinity.rotate(shape, -angle, origin=(0, 0))
        rows = dz._rows(rot, angle, 0.6, 0.0)
        long_len = sum(max(0.0, (x1 - x0) - SATIN_MAX_STITCH_MM) for segs in rows for x0, x1 in segs)
        # Avoid slivers. Rounded, so a row exactly 0.8 mm wide (a shadow's) counts the same on every computer.
        short_bias = sum(1 for segs in rows for x0, x1 in segs if round(x1 - x0, 6) < 0.8) * 0.2
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
            if "stitches" in g:  # a letter made of stitches (a version 2 stitch font)
                objs = stitchglyphs.letter_objects(f, g, k)
            else:
                objs = [dz.transform_geometry(o, _Scale(k), (0.0, 0.0)) for o in g.get("objects") or []
                        if isinstance(o, dict)]
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
