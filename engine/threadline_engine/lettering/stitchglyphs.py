"""Letters made of stitches: the glyphs of a version 2 stitch font (P5-C1).

A stitched letter is a letter part of kind "stitches" whose geometry.nodes are its stitches
([x, y, k] in mm from the letter's origin on the baseline, y down; k is "s" stitch, "j" jump or
"t" trim), so placing, slanting, bending and single-letter changes move it like any other part:
they move the nodes and keep each one's kind.

A version 2 glyph is {"advance_mm", "stitches": [[x, y, k], ...], "blocks": [[start, end,
color], ...]}: one block for each of its colors, in sewing order, with color numbers into the
font's "threads".

Within 20% of the size the font was made at, letters resize like stitch files: the same
stitches, closer together or further apart. Further than that, their fills, satins and lines are
rebuilt at the new size with the same spacing and stitch length, as "Rebuild stitches at this
size" does for a stitch file (repair/rebuild.py)."""

from __future__ import annotations

import re
from typing import Any

import pyembroidery as pe

from .fontfile import _load_stitch_font
from .fonts import LetteringError

REBUILD_PAST = 0.2  # more than 20% bigger or smaller than the font's own height
_FAR_MM = 100_000  # no letter's stitch is this far from its origin

_COMMAND = {"s": pe.STITCH, "j": pe.JUMP, "t": pe.TRIM}
_KIND = {command: kind for kind, command in _COMMAND.items()}
_CACHE_MAX = 512
_rebuilt_cache: dict[tuple, tuple] = {}  # (scale, a color's stitches) -> the stitches rebuilt


def _far(scale: float) -> bool:
    return round(abs(scale - 1.0), 4) > REBUILD_PAST  # rounded: 12 / 10 is just 20%, not more


def _nodes(raw: Any) -> list[tuple[float, float, str]]:
    """A glyph's stitches, checked (ValueError or TypeError for a hand-editing slip)."""
    if not isinstance(raw, list):
        raise TypeError("stitches")
    out = []
    for node in raw:
        x, y, kind = node[0], node[1], node[2]
        # (Comparing refuses NaN, infinity and absurd numbers; text raises TypeError.)
        if kind not in _COMMAND or not (-_FAR_MM < x < _FAR_MM and -_FAR_MM < y < _FAR_MM):
            raise ValueError("stitch")
        out.append((float(x), float(y), kind))
    return out


def _blocks(glyph: dict[str, Any], count: int, colors: int) -> list[tuple[int, int, int]]:
    """The glyph's color blocks (start, end, color number); the whole glyph in one color if it has none."""
    raw = glyph.get("blocks")
    if raw is None:
        return [(0, count, 0)]
    if not isinstance(raw, list):
        raise TypeError("blocks")
    out = []
    for block in raw:
        start, end, color = block
        if not all(type(v) is int for v in block) or not 0 <= start <= end <= count or not 0 <= color < max(colors, 1):
            raise ValueError("block")
        out.append((start, end, color))
    return out


def _thread(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not re.fullmatch(r"#[0-9a-fA-F]{6}", str(raw.get("color"))):
        raise ValueError("thread")
    return {key: str(raw.get(key) or "") for key in ("color", "name", "catalog", "brand")}


def _rebuild(run: tuple[tuple[float, float, str], ...], scale: float) -> tuple:
    """One color of a letter at `scale`: its fills, satins and lines stitched again at their own
    spacing and stitch length, the rest resized as they are."""
    # Imported here: the repairs import the layout, which imports lettering.
    from ..layout.model import Block
    from ..repair import rebuild

    records = [[x * 10, y * 10, _COMMAND[kind], 0, -1] for x, y, kind in run]  # rebuild works in 0.1 mm
    try:
        blocks, _, _ = rebuild.remake([Block({}, records, [], None, True)], 0, (scale, scale), (0.0, 0.0),
                                      lambda span: span)
        return tuple((round(r[0] / 10, 3), round(r[1] / 10, 3), _KIND[r[2]]) for r in blocks[0].recs)
    except Exception:  # noqa: BLE001 - a letter that can't be rebuilt is resized as it is, as the note says
        return tuple((round(x * scale, 3), round(y * scale, 3), kind) for x, y, kind in run)


def _resized(run: list[tuple[float, float, str]], scale: float) -> list[list[Any]]:
    if not _far(scale):
        return [[round(x * scale, 3), round(y * scale, 3), kind] for x, y, kind in run]
    key = (round(scale, 6), tuple(run))
    hit = _rebuilt_cache.get(key)
    if hit is None:
        hit = _rebuild(tuple(run), scale)
        if len(_rebuilt_cache) >= _CACHE_MAX:
            _rebuilt_cache.pop(next(iter(_rebuilt_cache)))
        _rebuilt_cache[key] = hit
    return [list(node) for node in hit]


def letter_objects(font: dict[str, Any], glyph: dict[str, Any], scale: float) -> list[dict[str, Any]]:
    """A version 2 font's glyph as letter parts, scaled by `scale`: one per color block of the
    glyph, each with its color number ("color_index", 0 first) and, in a font with several
    colors, the font's thread for that color ("thread"). A one-color font's parts have no thread:
    they sew in the text's."""
    threads = font.get("threads") or []
    several = len(threads) > 1
    nodes = _nodes(glyph.get("stitches"))
    parts = []
    for start, end, color in _blocks(glyph, len(nodes), len(threads)):
        run = nodes[start:end]
        if not any(kind == "s" for _, _, kind in run):
            continue
        part: dict[str, Any] = {"kind": "stitches", "geometry": {"nodes": _resized(run, scale)}, "color_index": color}
        if several:
            part["thread"] = _thread(threads[color])
        parts.append(part)
    return parts


def size_notes(path: str, size_mm: float) -> list[str]:
    """What to say about letters `size_mm` tall from the stitch font at `path` (layout_text asks
    once per text): stitched letters resize like stitch files, so far from the font's own height
    they're rebuilt, and say so."""
    try:
        font = _load_stitch_font(path)
    except LetteringError:
        return []  # reading the letters says what's wrong with it
    if not any(isinstance(g, dict) and "stitches" in g for g in font["glyphs"].values()):
        return []  # letters made of shapes sew well at any size
    own = float(font.get("cap_height_mm") or size_mm)
    scale = size_mm / own
    if not _far(scale):
        return []
    return [f"Letters {size_mm:g} mm tall are {scale * 100:.0f}% of the size this stitched font was made at "
            f"({own:.1f} mm). Past 20% bigger or smaller, LUDD rebuilds their fills, satins and lines at the new "
            "size where it can and resizes the rest as they are, so check the preview before you sew."]


def records(obj: dict[str, Any]) -> list[tuple[float, float, int]]:
    """A "stitches" part's stitches as (x mm, y mm, pyembroidery command)."""
    try:
        return [(float(n[0]), float(n[1]), _COMMAND[n[2]]) for n in obj["geometry"]["nodes"]]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LetteringError("A letter from the stitched font is damaged; pick another font") from exc
