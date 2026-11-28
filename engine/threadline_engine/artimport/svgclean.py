"""Making an untrusted SVG safe to hand to svgelements, which is only ever given what this module
writes.

1. The XML parser itself (expat) refuses any entity declaration, so an entity bomb or an external
   entity never gets as far as being read, whatever the file's encoding.
2. Every <use> is followed on paper first: loops, and sizes that multiply out too far, are refused
   before anything is built.
3. The drawing is rebuilt from a short list of elements and attributes. Pictures and text become
   empty markers (counted, never opened), links to other files and websites are dropped, scripts,
   filters, masks and other extras are left out, and the stylesheet and transforms are rewritten
   in a plain form (svgelements reads them with patterns that can take forever on odd input).
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable
from xml.parsers import expat

from . import ArtError
from .model import INVALID, parse_color

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
INKSCAPE_LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"

MAX_ELEMENTS = 50_000  # in the file, and once every <use> is expanded
MAX_DEPTH = 64  # groups inside groups, <use> included
MAX_ATTRIBUTES = 256  # on one element
MAX_PATH_NUMBERS = 600_000  # numbers in path and point data, once every <use> is expanded
MAX_CLOSE_WORK = 2_000_000  # steps svgelements takes working out where each "z" goes back to, in all
MAX_CSS = 256 * 1024  # characters of stylesheet
MAX_TEXT_WORK = 5_000_000  # characters of styles and transforms svgelements has to read, in all
MAX_TRANSFORM = 20_000  # characters of one shape's transforms, its groups' included
MAX_VALUE = 4000  # characters of any other attribute
MAX_DIGITS = 40  # in one number

# Elements kept as they are (a symbol only draws when a <use> points at it).
_KEEP = frozenset({"svg", "g", "defs", "use", "symbol", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon"})
_AS_GROUP = frozenset({"a", "switch"})
_MARKERS = {"text": "luddText", "image": "luddImage"}
_GEOMETRY = ("d", "points", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height",
             "viewBox", "preserveAspectRatio")
_PAINT = ("fill", "fill-opacity", "fill-rule", "stroke", "stroke-opacity", "stroke-width", "stroke-linecap",
          "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray", "color", "vector-effect", "display",
          "visibility", "opacity", "clip-path", "mask")
_NAMES = ("id", "class", "data-name", INKSCAPE_LABEL)

_DIGITS = re.compile(r"\d{%d}" % (MAX_DIGITS + 1))
_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_SELECTOR = re.compile(r"\*|[A-Za-z][\w-]{0,100}|[#.][^\s.#:>+~\[\]{},;*()]{1,200}|[A-Za-z][\w-]{0,100}\.[^\s.#:>+~\[\]{},;*()]{1,200}")
_TRANSFORM_PART = re.compile(r"[\s,]*(matrix|translate|translatex|translatey|scale|scalex|scaley|rotate|skew|skewx|skewy)"
                             r"\s*\(([^()]{0,600})\)", re.IGNORECASE)
_PLAIN_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_PATH_TOKEN = re.compile(r"[MmZz]|" + _PLAIN_NUMBER)  # what close_work counts in path data
_PARAMETER = re.compile(_PLAIN_NUMBER + r"(px|pt|pc|mm|cm|in|q|deg|rad|grad|turn)?", re.IGNORECASE)
# How many numbers each transform takes, and whether they may carry units (svgelements stops on
# "scale(2px)", and with it on the whole file).
_PARAMETERS = {"matrix": ((6,), False), "translate": ((1, 2), True), "translatex": ((1,), True),
               "translatey": ((1,), True), "scale": ((1, 2), False), "scalex": ((1,), False), "scaley": ((1,), False),
               "rotate": ((1, 3), True), "skew": ((1, 2), True), "skewx": ((1,), True), "skewy": ((1,), True)}
# Matched against the text with its ends stripped: with a \s* at each end as well, this took minutes
# on a long run of spaces.
_LENGTH = re.compile(r"(" + _PLAIN_NUMBER + r")\s*([a-zA-Z%]{0,4})")

PX_PER = {"": 1.0, "px": 1.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0, "pt": 96 / 72, "pc": 16.0, "q": 96 / 101.6}
_REAL_UNITS = frozenset({"mm", "cm", "in", "pt", "pc", "q"})


def _too_complex(why: str) -> ArtError:
    return ArtError(f"This SVG {why}. Simplify it in your drawing program (fewer shapes, copies and points), save it "
                    "again and import that.")


def split_tag(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        namespace, _, local = tag[1:].partition("}")
        return namespace, local
    return "", tag


def _local(el: ET.Element) -> str | None:
    """The element's name if it is SVG's own (or has no namespace), else None."""
    namespace, local = split_tag(el.tag)
    return local if namespace in (SVG_NS, "") else None


def _href(el: ET.Element) -> str | None:
    """The same one svgelements follows: plain href before xlink:href."""
    return el.get("href", el.get(XLINK_HREF))


# ---------------------------------------------------------------- 1. the XML itself


def check_xml(data: bytes) -> None:
    count = depth = 0

    def refuse_entity(*_args) -> None:
        raise ArtError("This SVG declares XML entities, which LUDD doesn't read (they can be used to attack a "
                       "program). Open it in your drawing program, save it again as a plain SVG and import that.")

    def start(_name: str, attributes: dict) -> None:
        nonlocal count, depth
        count += 1
        depth += 1
        if count > MAX_ELEMENTS:
            raise _too_complex(f"has more than {MAX_ELEMENTS:,} elements")
        if depth > MAX_DEPTH:
            raise _too_complex(f"has groups nested more than {MAX_DEPTH} deep")
        if len(attributes) > MAX_ATTRIBUTES:
            raise _too_complex("has an element with hundreds of settings")

    def end(_name: str) -> None:
        nonlocal depth
        depth -= 1

    parser = expat.ParserCreate()
    parser.EntityDeclHandler = refuse_entity
    parser.UnparsedEntityDeclHandler = refuse_entity
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(data, True)
    except expat.ExpatError:
        raise ArtError("This SVG is damaged or cut off (it isn't complete XML). Save it again from your drawing "
                       "program.") from None
    except (LookupError, ValueError):
        raise ArtError("This SVG uses a text encoding LUDD can't read. Save it again as UTF-8.") from None


# ---------------------------------------------------------------- stylesheets


def _without_comments(text: str) -> str:
    out, i = [], 0
    while True:
        start = text.find("/*", i)
        if start < 0:
            out.append(text[i:])
            return " ".join(out)
        out.append(text[i:start])
        end = text.find("*/", start + 2)
        if end < 0:
            return " ".join(out)
        i = end + 2


def declarations(text: str) -> dict[str, str]:
    """"name: value" pairs from a style attribute or a rule, keeping only what svgelements reads
    safely."""
    found: dict[str, str] = {}
    for part in text.split(";"):
        name, colon, value = part.partition(":")
        name, value = name.strip().lower(), value.strip()
        if (important := value.lower().rfind("!important")) >= 0:
            value = value[:important].strip()
        if not colon or not name or not value or len(name) > 60 or len(value) > 500:
            continue
        if ":" in value or "//" in value or "/*" in value or "{" in value or "}" in value:
            continue
        if name == "font" or value.lower() == "inherit":
            continue
        found[name] = value
    return found


@dataclass
class Stylesheet:
    """CSS rules by selector (the kinds svgelements understands: *, tag, #id, .class, tag.class)."""

    rules: dict[str, dict[str, str]] = field(default_factory=dict)

    def matching(self, tag: str, element_id: str | None, classes: str) -> list[dict[str, str]]:
        """The rules for an element, in the order svgelements applies them."""
        selectors = ["*", tag]
        if element_id is not None:
            selectors.append(f"#{element_id}")
        for name in classes.split():
            selectors += [f".{name}", f"{tag}.{name}"]
        return [self.rules[s] for s in selectors if s in self.rules]

    def size(self, tag: str, element_id: str | None, classes: str) -> int:
        return sum(sum(len(k) + len(v) + 2 for k, v in rule.items()) for rule in self.matching(tag, element_id, classes))

    def text(self) -> str:
        return "\n".join(f"{sel}{{{';'.join(f'{k}:{v}' for k, v in rule.items())}}}" for sel, rule in self.rules.items())


def parse_css(texts: list[str]) -> Stylesheet:
    if sum(len(t) for t in texts) > MAX_CSS:
        raise _too_complex("has a very long stylesheet")
    sheet = Stylesheet()

    def rule(prelude: str, body: str) -> None:
        prelude = prelude.strip()
        if prelude.startswith("@") or "{" in body:
            return
        found = declarations(body)
        found.pop("transform", None)  # CSS transforms in rules aren't applied
        if not found:
            return
        for selector in prelude.split(","):
            selector = selector.strip()
            if _SELECTOR.fullmatch(selector):
                sheet.rules.setdefault(selector, {}).update(found)

    for text in texts:
        depth, prelude, body = 0, [], []
        for token in re.split(r"([{};])", _without_comments(text)):
            if depth == 0:
                if token == "{":
                    depth, body = 1, []
                elif token in (";", "}"):  # the end of an @import and the like
                    prelude = []
                else:
                    prelude.append(token)
                continue
            if token == "{":
                depth += 1
            elif token == "}":
                depth -= 1
                if depth == 0:
                    rule("".join(prelude), "".join(body))
                    prelude = []
                    continue
            body.append(token)
    return sheet


def _cascade(el: ET.Element, sheet: Stylesheet, name: str) -> str | None:
    """A presentation property of an element: its attribute, then the stylesheet, then style=""."""
    value = el.get(name)
    for rules in sheet.matching(_local(el) or "", el.get("id"), el.get("class", "")):
        value = rules.get(name, value)
    return declarations(el.get("style", "")).get(name, value)


def valid_transform(text: str) -> bool:
    """A well-formed transform list (browsers ignore any other, and so does LUDD)."""
    at = 0
    while m := _TRANSFORM_PART.match(text, at):
        counts, units = _PARAMETERS[m[1].lower()]
        parameters = [p for p in re.split(r"[\s,]+", m[2].strip()) if p]
        if len(parameters) not in counts:
            return False
        for p in parameters:
            found = _PARAMETER.fullmatch(p) if len(p) <= MAX_DIGITS + 12 else None
            if not found or (found[1] and not units):
                return False
        at = m.end()
    return not text[at:].strip(" \t\r\n,")


# ---------------------------------------------------------------- 2. how far every <use> goes


def _ids(root: ET.Element) -> dict[str, ET.Element]:
    """Elements by id as svgelements finds them: the last with an id wins."""
    return {el.attrib["id"]: el for el in root.iter() if "id" in el.attrib}


def close_work(d: str, stop: int = MAX_CLOSE_WORK) -> int:
    """About how many steps svgelements takes over the "z"s of this path data: for each one it
    walks back, piece by piece, to the last "M" or "m", so a path closed thousands of times takes it
    minutes. Counting stops once past `stop`."""
    if "z" not in d and "Z" not in d:
        return 0
    work = since = 0
    for found in _PATH_TOKEN.finditer(d):
        token = found[0]
        if token in ("M", "m"):
            since = 0
            continue
        since += 1  # a piece takes at least one number, or is a "z" itself
        if token in ("Z", "z"):
            work += since
            if work > stop:
                break
    return work


@dataclass
class _Cost:
    elements: int
    numbers: int
    closes: int  # close_work of its paths
    height: int
    styles: int  # characters of styles and transforms read for this subtree (its parents' not counted)
    transform: int  # the longest chain of transforms inside it


_CLOSED_TOO_OFTEN = "has paths too long, or closed too many times over, for LUDD to read"


def check_budget(root: ET.Element, sheet: Stylesheet, check: Callable[[], None] | None = None) -> None:
    """Refuse loops, and drawings that multiply out too far, following every <use> as svgelements
    does."""
    ids = _ids(root)
    memo: dict[int, _Cost] = {}
    open_now: set[int] = set()
    cap = 10**12

    def cost(el: ET.Element, depth: int) -> _Cost:
        if depth > MAX_DEPTH:
            raise _too_complex(f"has groups nested more than {MAX_DEPTH} deep")
        key = id(el)
        if key in open_now:
            raise ArtError("This SVG has a <use> that includes itself, so it never ends. Remove that copy in your "
                           "drawing program (or ungroup it) and save the file again.")
        if (known := memo.get(key)) is not None:
            if depth + known.height > MAX_DEPTH:
                raise _too_complex(f"has groups nested more than {MAX_DEPTH} deep")
            return known
        open_now.add(key)
        if check:
            check()
        tag = _local(el) or ""
        own_transform = len(el.get("transform", ""))
        total = _Cost(1, len(_NUMBER.findall(el.get("d", ""))) + len(_NUMBER.findall(el.get("points", ""))),
                      close_work(el.get("d", "")) if tag == "path" else 0, 0,
                      sheet.size(tag, el.get("id"), el.get("class", "")) + len(el.get("style", "")) + own_transform,
                      own_transform)
        if total.closes > MAX_CLOSE_WORK:
            raise _too_complex(_CLOSED_TOO_OFTEN)
        inside = list(el)
        if tag == "use" and (href := _href(el)) and href.startswith("#") and (target := ids.get(href[1:])) is not None:
            inside.append(target)
        for child in inside:
            c = cost(child, depth + 1)
            total.elements = min(cap, total.elements + c.elements)
            total.numbers = min(cap, total.numbers + c.numbers)
            total.closes = min(cap, total.closes + c.closes)  # each copy is worked through again
            total.height = max(total.height, c.height + 1)
            total.styles = min(cap, total.styles + c.styles + own_transform * c.elements)
            total.transform = max(total.transform, own_transform + c.transform)
            if total.elements > MAX_ELEMENTS:
                raise _too_complex(f"multiplies out to more than {MAX_ELEMENTS:,} elements with its copies")
            if total.numbers > MAX_PATH_NUMBERS:
                raise _too_complex("has far more points than LUDD imports")
            if total.closes > MAX_CLOSE_WORK:
                raise _too_complex(_CLOSED_TOO_OFTEN)
        open_now.discard(key)
        memo[key] = total
        return total

    total = cost(root, 1)
    if total.elements > MAX_ELEMENTS:
        raise _too_complex(f"multiplies out to more than {MAX_ELEMENTS:,} elements with its copies")
    if total.numbers > MAX_PATH_NUMBERS:
        raise _too_complex("has far more points than LUDD imports")
    if total.styles > MAX_TEXT_WORK or total.transform > MAX_TRANSFORM:
        raise _too_complex("has more styles and transforms than LUDD can read")


def _check_digits(root: ET.Element, css: list[str]) -> None:
    """No number may be absurdly long: svgelements' patterns take forever on one. Checked wherever
    it reads numbers (never in links, where a picture's data has long runs)."""
    read = (*_GEOMETRY, *_PAINT, "transform", "style")
    values = (el.get(name, "") for el in root.iter() for name in read)
    if any(_DIGITS.search(value) for value in (*css, *values)):
        raise ArtError(f"This SVG has a number more than {MAX_DIGITS} digits long, so LUDD doesn't read it. Save it "
                       "again from your drawing program.")


# ---------------------------------------------------------------- gradients and patterns


def paint_servers(root: ET.Element, sheet: Stylesheet,
                  check: Callable[[], None] | None = None) -> Callable[[str], tuple | None]:
    """What url(#id) paint points at: ("gradient", its first color or None), ("pattern",), or None.
    Each element's stops are read once, however many gradients and shapes use them."""
    ids = _ids(root)
    read_stops: dict[int, tuple[bool, str | None]] = {}
    answers: dict[str, tuple | None] = {}

    def own_stops(el: ET.Element) -> tuple[bool, str | None]:
        """Whether `el` has stops, and the first color among them."""
        if (known := read_stops.get(id(el))) is not None:
            return known
        stops = [s for s in el if _local(s) == "stop"]
        color = None
        for stop in stops:
            if check:
                check()
            opacity = (_cascade(stop, sheet, "stop-opacity") or "1").strip()
            try:
                seen_through = float(opacity.rstrip("%")) <= 0
            except ValueError:
                seen_through = False
            if seen_through:
                continue
            color = parse_color(_cascade(stop, sheet, "stop-color") or "black")
            if color == INVALID:
                color = "#000000"
            if color is not None:
                break
        read_stops[id(el)] = (bool(stops), color)
        return read_stops[id(el)]

    def first_color(el: ET.Element) -> str | None:
        seen: set[int] = set()
        while el is not None and id(el) not in seen and len(seen) < 20:
            seen.add(id(el))
            has_stops, color = own_stops(el)
            if has_stops:
                return color
            href = _href(el) or ""
            el = ids.get(href[1:]) if href.startswith("#") else None
        return None

    def look_up(element_id: str) -> tuple | None:
        el = ids.get(element_id)
        tag = _local(el) if el is not None else None
        if tag in ("linearGradient", "radialGradient"):
            return ("gradient", first_color(el))
        if tag == "pattern":
            return ("pattern",)
        return None

    def find(element_id: str) -> tuple | None:
        if element_id not in answers:
            answers[element_id] = look_up(element_id)
        return answers[element_id]

    return find


# ---------------------------------------------------------------- the size of the drawing


def _length(text: str | None) -> tuple[float, str] | None:
    """A length and its unit ("100mm"), or None for a missing, relative (%, em) or odd one."""
    m = _LENGTH.fullmatch((text or "").strip())
    if not m:
        return None
    value, unit = float(m[1]), m[2].lower()
    return (value, unit) if unit in PX_PER and math.isfinite(value) else None


def _size(text: str | None) -> tuple[float, str] | None:
    found = _length(text)
    return found if found and found[0] > 0 else None


def view_box(text: str | None) -> tuple[float, float, float, float] | None:
    parts = [p for p in re.split(r"[\s,]+", (text or "").strip()) if p]
    if len(parts) != 4:
        return None
    try:
        x, y, w, h = (float(p) for p in parts)
    except ValueError:
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return None
    if w <= 0 or h <= 0:
        raise ArtError("This SVG's viewBox has no size, so there is nothing in it to import.")
    return x, y, w, h


def viewport(root: ET.Element) -> tuple[float | None, float | None, bool]:
    """The drawing's width and height in CSS pixels (96 to the inch), and whether the file says its
    real size (in mm, cm, in, pt or pc)."""
    box = view_box(root.get("viewBox"))
    w, h = _size(root.get("width")), _size(root.get("height"))
    given = [side for side in (w, h) if side is not None]
    real = bool(given) and all(unit in _REAL_UNITS for _, unit in given)
    wide = w[0] * PX_PER[w[1]] if w else None
    tall = h[0] * PX_PER[h[1]] if h else None
    if box:
        if wide is None and tall is None:
            wide, tall = box[2], box[3]
        elif tall is None:
            tall = wide * box[3] / box[2]
        elif wide is None:
            wide = tall * box[2] / box[3]
    return wide, tall, real


# ---------------------------------------------------------------- 3. rebuilding it


@dataclass
class Prepared:
    data: bytes  # the rebuilt drawing, all svgelements ever sees
    paint: Callable[[str], tuple | None]
    real_size: bool
    links: int = 0  # <use>s pointing at other files or websites, left out
    clips: int = 0  # clips and masks, ignored


class _Builder:
    def __init__(self, root: ET.Element) -> None:
        self.ids = _ids(root)
        self.links = 0
        self.clips = 0
        box = view_box(root.get("viewBox"))
        wide, tall, _ = viewport(root)
        # What a <use> of a symbol is sized to when it doesn't say.
        self.page = (box[2], box[3]) if box else (wide or 100.0, tall or 100.0)
        self.made = 0

    def attributes(self, el: ET.Element, keep_ids: bool) -> dict[str, str]:
        out: dict[str, str] = {}
        for name in (*_GEOMETRY, *_PAINT, *_NAMES):
            value = el.get(name)
            if value is None or (name == "id" and not keep_ids):
                continue
            if name not in ("d", "points") and len(value) > MAX_VALUE:
                continue
            # (svgelements takes minutes over a long run of spaces in "points".)
            if name in ("class", "points"):
                value = " ".join(value.split())
            elif name == "preserveAspectRatio":
                value = " ".join(p for p in value.split() if p != "defer")
            elif value.strip().lower() == "inherit":
                continue
            out[name] = value
        style = declarations(el.get("style", "")[: MAX_VALUE * 4])
        transforms = [el.get("transform", ""), style.pop("transform", "")]
        good = " ".join(t for t in transforms if t.strip() and len(t) <= MAX_VALUE and valid_transform(t))
        if good:
            out["transform"] = good
        if style:
            out["style"] = ";".join(f"{k}:{v}" for k, v in style.items())
        if any(name in ("clip-path", "mask") and value.strip().lower() != "none"
               for name, value in [*out.items(), *style.items()]):
            self.clips += 1
        return out

    def element(self, el: ET.Element, keep_ids: bool = True) -> ET.Element | None:
        self.made += 1
        if self.made > MAX_ELEMENTS * 2:
            raise _too_complex(f"multiplies out to more than {MAX_ELEMENTS:,} elements with its copies")
        tag = _local(el)
        if tag is None:
            return None
        if tag in _MARKERS:
            marker = ET.Element(f"{{{SVG_NS}}}{_MARKERS[tag]}", self.attributes(el, keep_ids))
            for name in _GEOMETRY:
                marker.attrib.pop(name, None)
            return marker
        if tag in _AS_GROUP:
            new = ET.Element(f"{{{SVG_NS}}}g", self.attributes(el, keep_ids))
        elif tag in _KEEP:
            new = ET.Element(f"{{{SVG_NS}}}{tag}", self.attributes(el, keep_ids))
        else:
            return None
        if tag == "path" and new.get("d") is None:
            new.set("d", "")  # (svgelements stops on a path without any)
        if tag == "use":
            href = _href(el)
            if href and not href.startswith("#"):
                self.links += 1
            elif href:
                target = self.ids.get(href[1:])
                if target is not None and _local(target) == "symbol" and view_box(target.get("viewBox")):
                    return self.symbol_copy(el, target, keep_ids)
                new.set("href", href)
        self.children(el, new, keep_ids)
        return new

    def children(self, el: ET.Element, new: ET.Element, keep_ids: bool) -> None:
        for child in el:
            built = self.element(child, keep_ids)
            if built is None:
                continue
            if split_tag(built.tag)[1] == "symbol" and split_tag(new.tag)[1] != "defs":
                # A symbol draws only through a <use>: kept where a <use> finds it, but not drawn.
                holder = ET.SubElement(new, f"{{{SVG_NS}}}defs")
                holder.append(built)
            else:
                new.append(built)

    def symbol_copy(self, use: ET.Element, symbol: ET.Element, keep_ids: bool) -> ET.Element:
        """A <use> of a symbol with a viewBox, as a group holding a copy of the symbol sized into
        the use's box (svgelements doesn't size symbols)."""
        x0, y0, bw, bh = view_box(symbol.get("viewBox"))

        def pixels(found: tuple[float, str] | None, otherwise: float) -> float:
            return found[0] * PX_PER[found[1]] if found else otherwise

        x, y = pixels(_length(use.get("x")), 0.0), pixels(_length(use.get("y")), 0.0)
        width = pixels(_size(use.get("width", symbol.get("width"))), self.page[0])
        height = pixels(_size(use.get("height", symbol.get("height"))), self.page[1])
        sx, sy = width / bw, height / bh
        aspect = (symbol.get("preserveAspectRatio") or "xMidYMid meet").split() or ["xMidYMid"]
        if aspect[0] != "none":
            sx = sy = max(sx, sy) if "slice" in aspect else min(sx, sy)
        align = aspect[0].lower()
        tx = x - x0 * sx + (width - bw * sx) * (0.5 if "xmid" in align else 1.0 if "xmax" in align else 0.0)
        ty = y - y0 * sy + (height - bh * sy) * (0.5 if "ymid" in align else 1.0 if "ymax" in align else 0.0)
        outer = self.attributes(use, keep_ids)
        for name in _GEOMETRY:
            outer.pop(name, None)
        group = ET.Element(f"{{{SVG_NS}}}g", outer)
        group.set("transform", f"{outer.get('transform', '')} translate({tx!r} {ty!r}) scale({sx!r} {sy!r})".strip())
        inner = self.attributes(symbol, False)
        for name in _GEOMETRY:
            inner.pop(name, None)
        body = ET.SubElement(group, f"{{{SVG_NS}}}g", inner)
        self.children(symbol, body, False)
        return group


def without_broken_paths(data: bytes) -> tuple[bytes, int]:
    """A rebuilt drawing with the path data svgelements stops on (an arc cut short, say) left
    out, and how many paths that was."""
    from svgelements import Path

    root = ET.fromstring(data)  # our own rebuilt drawing
    broken = 0
    for el in root.iter(f"{{{SVG_NS}}}path"):
        try:
            Path().parse(el.get("d", ""))
        except ValueError:
            pass  # it keeps what comes before the mistake, as a browser does
        except Exception:  # noqa: BLE001
            el.set("d", "")
            broken += 1
    return ET.tostring(root, encoding="utf-8"), broken


def prepare(data: bytes, check: Callable[[], None] | None = None) -> Prepared:
    """Check an SVG and rebuild it safely (see above). `check`: called as the work goes on."""
    check_xml(data)
    if check:
        check()
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise ArtError("This SVG is damaged or cut off (it isn't complete XML). Save it again from your drawing "
                       "program.") from None
    if _local(root) != "svg":
        raise ArtError("This file isn't an SVG drawing.")
    css = ["".join(el.itertext()) for el in root.iter() if _local(el) == "style"]
    _check_digits(root, css)
    sheet = parse_css(css)
    check_budget(root, sheet, check)
    paint = paint_servers(root, sheet, check)
    wide, tall, real = viewport(root)
    builder = _Builder(root)
    clean = builder.element(root)
    if wide is not None:
        clean.set("width", repr(wide))
    if tall is not None:
        clean.set("height", repr(tall))
    if sheet.rules:
        style = ET.Element(f"{{{SVG_NS}}}style")
        style.text = sheet.text()
        clean.insert(0, style)
    check_budget(clean, sheet, check)  # what svgelements gets, with symbol copies
    return Prepared(ET.tostring(clean, encoding="utf-8"), paint, real, builder.links, builder.clips)
