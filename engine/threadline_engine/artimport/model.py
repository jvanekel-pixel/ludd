"""What a reader (svg.py, dxf.py, pdf.py) hands to convert.py: painted paths in millimeters, at
the file's real size, y down, in the file's drawing order; what it had to leave out; and colors
as CSS writes them."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass, field
from typing import Any

Point = tuple[float, float]


@dataclass
class Subpath:
    """One unbroken piece of a path. A segment is ("L", end) or ("C", control1, control2, end)."""

    start: Point
    segments: list[tuple] = field(default_factory=list)
    closed: bool = False

    @property
    def end(self) -> Point:
        return self.segments[-1][-1] if self.segments else self.start


@dataclass
class Item:
    """One painted element. `stroke_width` is in mm (0: a plain line with no width of its own).
    `fill_rule`: "nonzero", "evenodd", or for DXF hatches "outer" or "ignore"."""

    subpaths: list[Subpath]
    fill: str | None = None
    fill_rule: str = "nonzero"
    stroke: str | None = None
    stroke_width: float = 0.0
    cap: str = "butt"
    join: str = "miter"
    miter_limit: float = 4.0
    name: str = ""
    dashed: bool = False


# What can be left out or changed, in the order it's reported: (one, several).
SKIPPED = {
    "text": ("1 piece of text left out: LUDD doesn't import text. Turn it into outlines (paths) in your drawing "
             "program, or type it with LUDD's Text tool.",
             "{n} pieces of text left out: LUDD doesn't import text. Turn them into outlines (paths) in your drawing "
             "program, or type them with LUDD's Text tool."),
    "picture": ("1 picture inside the file left out: artwork import brings in shapes only. To trace it, save it as an "
                "image and use Add a picture (Ctrl+I).",
                "{n} pictures inside the file left out: artwork import brings in shapes only. To trace one, save it as "
                "an image and use Add a picture (Ctrl+I)."),
    "link": ("1 link to another file or website left alone: LUDD reads only the file you chose.",
             "{n} links to other files or websites left alone: LUDD reads only the file you chose."),
    "gradient": ("1 gradient came in as one solid color, the gradient's first.",
                 "{n} gradients came in as solid colors, each gradient's first."),
    "pattern": ("1 pattern fill left out: give that shape a plain color to bring it in.",
                "{n} pattern fills left out: give those shapes a plain color to bring them in."),
    "clip": ("1 clip or mask ignored, so that shape comes in whole. Apply it in your drawing program first if that "
             "matters.",
             "{n} clips or masks ignored, so those shapes come in whole. Apply them in your drawing program first if "
             "that matters."),
    "dash": ("1 dashed line came in solid.", "{n} dashed lines came in solid."),
    "hatch_pattern": ("1 hatch pattern came in as a solid fill.", "{n} hatch patterns came in as solid fills."),
    "tiny": ("1 tiny piece left out: pieces under 1 mm² and lines under 1 mm long are too small to sew.",
             "{n} tiny pieces left out: pieces under 1 mm² and lines under 1 mm long are too small to sew."),
    "hidden_layer": ("1 object on a hidden or frozen layer left out: show the layer in your CAD program to bring it "
                     "in.",
                     "{n} objects on hidden or frozen layers left out: show the layers in your CAD program to bring "
                     "them in."),
    "dimension": ("1 dimension or note left out.", "{n} dimensions or notes left out."),
    "xref": ("1 linked drawing (xref) not opened: bind it into the drawing in your CAD program to bring it in.",
             "{n} linked drawings (xrefs) not opened: bind them into the drawing in your CAD program to bring them in."),
    "other": ("1 object LUDD doesn't read left out (such as a point, a 3D solid or a mesh).",
              "{n} objects LUDD doesn't read left out (such as points, 3D solids or meshes)."),
    "damaged": ("1 damaged shape left out.", "{n} damaged shapes left out."),
}


class Skipped(dict):
    """How many things of each kind were left out (or flattened)."""

    def add(self, what: str, n: int = 1) -> None:
        if what not in SKIPPED:
            raise KeyError(what)
        if n > 0:
            self[what] = self.get(what, 0) + n

    def report(self) -> list[dict[str, Any]]:
        return [{"what": what, "count": self[what], "message": (one if self[what] == 1 else many).format(n=self[what])}
                for what, (one, many) in SKIPPED.items() if self.get(what)]


@dataclass
class Drawing:
    items: list[Item] = field(default_factory=list)
    skipped: Skipped = field(default_factory=Skipped)
    scale_note: str | None = None
    pages: int = 1


# ---------------------------------------------------------------- colors

INVALID = "invalid"  # parse_color: not a color at all
_HEX = re.compile(r"#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})\Z")
_FUNCTION = re.compile(r"(rgba?|hsla?)\(([^()]{0,80})\)\Z")
_NUMBER = re.compile(r"[-+]?(?:\d{1,20}(?:\.\d{0,20})?|\.\d{1,20})(?:e[-+]?\d{1,3})?(%|deg)?\Z")


def rgb_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, int(c + 0.5))):02x}" for c in (r, g, b))


def parse_color(value: str | None) -> str | None:
    """"#rrggbb" for a CSS color; None for no paint ("none", or fully transparent); INVALID for
    anything else. (svgelements reads every color it doesn't know as black.)"""
    if value is None:
        return None
    s = value.strip().lower()
    if s in ("", "none", "transparent"):
        return None
    if len(s) > 100:
        return INVALID
    if m := _HEX.match(s):
        digits = m[1]
        if len(digits) <= 4:
            digits = "".join(c * 2 for c in digits)
        if len(digits) == 8 and digits[6:] == "00":
            return None
        return "#" + digits[:6]
    if m := _FUNCTION.match(s):
        return _function_color(m[1], m[2])
    if re.fullmatch(r"[a-z]{3,40}", s):
        from svgelements import Color

        c = Color(s)
        found = (c.red, c.green, c.blue)
        if found == (0, 0, 0) and s != "black":
            return INVALID  # svgelements reads a name it doesn't know as black
        return rgb_hex(*found)
    return INVALID


def _function_color(name: str, body: str) -> str | None:
    parts = [p for p in re.split(r"[\s,/]+", body.strip()) if p]
    if len(parts) not in (3, 4):
        return INVALID
    values = []
    for p in parts:
        m = _NUMBER.match(p)
        if not m:
            return INVALID
        values.append((float(p[: len(p) - len(m[1] or "")]), m[1] or ""))
    if len(values) == 4:
        alpha, unit = values[3]
        if alpha / (100 if unit == "%" else 1) <= 0:
            return None
    if name.startswith("rgb"):
        return rgb_hex(*(v * 2.55 if unit == "%" else v for v, unit in values[:3]))
    (h, _), (sat, _), (light, _) = values[:3]
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, max(0.0, min(1.0, light / 100)), max(0.0, min(1.0, sat / 100)))
    return rgb_hex(r * 255, g * 255, b * 255)
