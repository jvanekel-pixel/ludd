"""Stitch fonts (.luddfont): reading one, saving one, and making one from an installed font to
hand-tune.

A version 1 font's letters are LUDD objects. A version 2 font's letters are stitches, made from
single-letter stitch files (fontbuild.py) and sewn as they are (stitchglyphs.py)."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ..design import RESERVED_NAMES
from ..storage import data_dir
from .fonts import STITCH_FONT_EXTS, STITCH_FONT_FORMATS, LetteringError, _glyph_shapes, _load

MAX_FONT_STEM = 80  # longest file name made from a font's name


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
    if f.get("threads") is not None and not isinstance(f["threads"], list):
        raise LetteringError(f"The stitch font {name} is damaged: its threads should be a list")
    for key in ("cap_height_mm", "space_mm"):
        if f.get(key) is not None:
            try:
                if not float(f[key]) > 0:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise LetteringError(f"The stitch font {name} is damaged: its {key} should be a number above 0") from exc
    return f


def stitch_font_dir() -> Path:
    """Where LUDD looks for your stitch fonts (and saves new ones)."""
    return data_dir() / "fonts"


def _free_path(folder: Path, stem: str, ext: str) -> Path:
    stem = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", stem).strip(" .")[:MAX_FONT_STEM].strip(" .") or "Stitch font"
    if stem.split(".")[0].strip().upper() in RESERVED_NAMES:
        stem = f"_{stem}"  # "CON.luddfont" can't be a file on Windows
    p = folder / f"{stem}{ext}"
    n = 1
    while p.exists():
        p = folder / f"{stem} ({n}){ext}"
        n += 1
    return p


def save_stitch_font(doc: dict[str, Any], dest: str = "", stem: str = "") -> Path:
    """Write a stitch font to `dest` (given a .luddfont ending if it has no stitch-font one), or as a
    new file in LUDD's fonts folder named after `stem`, where the font list finds it. The file
    appears only when it's complete. Raises OSError."""
    if dest:
        out = Path(dest)
        if out.suffix.lower() not in STITCH_FONT_EXTS:
            out = out.with_name(out.name + ".luddfont")  # the font list only looks for stitch-font files
        out.parent.mkdir(parents=True, exist_ok=True)
    else:
        stitch_font_dir().mkdir(parents=True, exist_ok=True)
        out = _free_path(stitch_font_dir(), stem, ".luddfont")
    fd, tmp = tempfile.mkstemp(prefix=".ludd-font-", suffix=".tmp", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, separators=(",", ":"))
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return out


EXTRA_CHARS = "‘’‚“”„–—…€•™"


def export_stitch_font(font: dict[str, Any], dest: str, chars: str, cap_height_mm: float = 12.0, style: str = "satin",
                       name: str = "") -> dict[str, Any]:
    """Convert an installed font into a LUDD stitch font (.luddfont) for hand-tuning.

    `chars` empty: every character the font can draw. `dest` empty: a new file in LUDD's fonts
    folder, where the font list finds it."""
    from .glyphs import _glyph_objects

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
        objs = _glyph_objects(_glyph_shapes(lf, gname, scale), style, cap_height_mm)
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
