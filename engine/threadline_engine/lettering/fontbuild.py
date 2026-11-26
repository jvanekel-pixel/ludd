"""A stitch font made from a folder of single-letter stitch files (P5-C1).

Each file is one letter, in any format LUDD opens. scan_letter_files shows each with the
character LUDD guesses from its name (guess_chars); build_from_files lines the letters up on one
baseline and saves them as a version 2 .luddfont, whose letters are the files' own stitches
(stitchglyphs.py sews them). The font keeps no file names or folders.

Where one of several equally good choices is made, a set rule picks it (files in name order, the
first of equals), and sizes are rounded before they're compared, so the same files make the same
font on every computer."""

from __future__ import annotations

import base64
import io
import math
import re
import string
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any

import pyembroidery as pe

from .. import design
from .fontfile import save_stitch_font
from .fonts import LetteringError

MAX_LETTER_FILES = 500  # far more than a font's letters, digits and punctuation
DEFAULT_GAP_PCT = 8.0  # between letters, as a percent of the capital height
GAP_PCT_RANGE = (-50.0, 100.0)  # below 0, letters overlap (scripts)
SPACE_SHARE = 0.35  # a space, as a share of the capital height (as in a converted font)
MAX_NAME = 100

CAPITALS_AND_DIGITS = string.ascii_uppercase + string.digits
TALL_LETTERS = "bdfhkl"
X_LETTERS = "acemnorsuvwxz"
X_SHARE = 0.68  # a small letter like x, as a share of the capital height, when the font has none
HANG_FROM_X = "gjpqy"  # hang below the line, their tops level with the small letters
HANG_A_LITTLE = ",;"
LITTLE_HANG = 0.15  # of the capital height
AT_TOP = "'\"^*"
AT_MIDDLE = "-+=~"

THUMB_PX = 128  # the longer side of a letter's picture
THUMB_MAX_PX_PER_MM = 20
# Colors for files that don't say theirs (DST, EXP), so each color stays a color change.
PLACEHOLDER_THREADS = (("#000000", "Black"), ("#c8102e", "Red"), ("#0047ab", "Blue"), ("#00843d", "Green"),
                       ("#f2a900", "Gold"), ("#6d2077", "Purple"))

# ---------------------------------------------------------------- which character is a file?

_SEPARATORS = " _-.+()[]{}"
_CASE_WORDS = {"upper", "uc", "cap", "lower", "lc", "small"}
_BEFORE = r"(?:[\W_]+|(?<=[a-z])(?=[A-Z]))"  # between a case word and its letter: a separator, or aB
_AFTER = r"(?:[\W_]+|(?=[A-Z][a-z]))"  # between a letter and its case word: a separator, or ACap
_MARKED = (  # (pattern, upper case?)
    (re.compile(rf"(?i:upper|uc|cap){_BEFORE}([^\W\d_])"), True),
    (re.compile(rf"([^\W\d_]){_AFTER}(?i:upper|cap)"), True),
    (re.compile(rf"(?i:lower|lc|small){_BEFORE}([^\W\d_])"), False),
    (re.compile(rf"([^\W\d_]){_AFTER}(?i:lower|small)"), False),
)
_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ampersand": "&", "and": "&", "period": ".", "dot": ".", "comma": ",",
    "exclam": "!", "exclamation": "!", "question": "?", "apostrophe": "'", "hyphen": "-", "dash": "-",
    "colon": ":", "semicolon": ";", "quote": '"', "slash": "/", "at": "@", "hash": "#", "number": "#",
    "heart": "♥",
}
_WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[^\W\d_A-Z]+|\d+")  # words in a name: Rose, A, uc, 4


def _tidy(text: str) -> str:
    """Accented letters put together (macOS names files with them apart), emoji style marks off."""
    return unicodedata.normalize("NFC", text).replace("\ufe0f", "").replace("\ufe0e", "")


def _one_char(text: str) -> bool:
    return len(text) == 1 and text.isprintable() and not text.isspace()


def guess_char(name: str) -> str:
    """The character a letter file's name stands for (what's left of it after the prefix and
    suffix every file shares), or "" when it isn't clear."""
    name = _tidy(name)
    for text in (name, name.strip(_SEPARATORS)):
        if _one_char(text):
            return text
        if text.casefold() in _WORDS:
            return _WORDS[text.casefold()]
        for pattern, upper in _MARKED:
            found = pattern.fullmatch(text)
            if found:
                letter = found.group(1)
                cased = letter.upper() if upper else letter.lower()
                return cased if len(cased) == 1 else letter
    return ""


def _ascii_codes(names: list[str]) -> bool:
    """Every name is a character code from 33 to 126."""
    return bool(names) and all(re.fullmatch(r"[0-9]{2,3}", n) and 33 <= int(n) <= 126 for n in names)


def _same_start(names: list[str]) -> int:
    """How many characters every name starts with, ignoring case."""
    n = 0
    while n < min(len(x) for x in names) and len({x[n].casefold() for x in names}) == 1:
        n += 1
    return n


def _boundary(name: str, i: int) -> bool:
    """A name may be cut between name[i - 1] and name[i]: at a separator, between a letter and a
    digit, or between a small letter and a capital. Never between two digits or inside a word."""
    if not 0 < i < len(name):
        return True
    a, b = name[i - 1], name[i]
    if not a.isalnum() or not b.isalnum():
        return True
    return a.isdigit() != b.isdigit() or (a.islower() and b.isupper())


def _splits_number(name: str, i: int) -> bool:
    return 0 < i < len(name) and name[i - 1].isdigit() and name[i].isdigit()


def _keep_case_words(name: str, start: int, end: int) -> tuple[int, int]:
    """The shared prefix and suffix made shorter, so a word saying which case the letter is stays
    with it: upper_a.pes and a_lower.pes keep theirs."""
    while start:
        words = list(_WORD.finditer(name[:start]))
        if not words or words[-1].group().casefold() not in _CASE_WORDS or any(
                c.isalnum() for c in name[words[-1].end():start]):
            break
        start = words[-1].start()
    while end:
        tail = name[len(name) - end:]
        word = _WORD.search(tail)
        if not word or word.group().casefold() not in _CASE_WORDS or any(c.isalnum() for c in tail[:word.start()]):
            break
        end = len(tail) - word.end()
    return start, end


def _shared_ends(stems: list[str]) -> tuple[int, int]:
    """How much of every name, at its start and at its end, isn't about the letter."""
    names = sorted(set(stems))
    if len(names) < 2:
        return 0, 0

    def ending(rest: list[str]) -> int:  # each name keeps at least one character
        return min(_same_start([r[::-1] for r in rest]), min(len(r) for r in rest) - 1)

    start = min(_same_start(names), min(len(n) for n in names) - 1)
    rest = [n[start:] for n in names]
    end = ending(rest)
    # When all that differs is one character each (fonta, fontb, fontc), that's the letter.
    if len(names) >= 3 and all(len(r) - end == 1 for r in rest) and not any(
            _splits_number(n, start) or _splits_number(n, len(n) - end) for n in names):
        return _keep_case_words(names[0], start, end)
    while start and not all(_boundary(n, start) for n in names):
        start -= 1
    rest = [n[start:] for n in names]
    end = ending(rest)
    while end and not all(_boundary(r, len(r) - end) for r in rest):
        end -= 1
    return _keep_case_words(names[0], start, end)


def guess_chars(stems: list[str]) -> tuple[list[str], str, str]:
    """The character for each file name (without its ending), after taking off the prefix and
    suffix every file shares, with those two."""
    stems = [_tidy(s) for s in stems]
    if _ascii_codes(stems):
        return [chr(int(s)) for s in stems], "", ""
    start, end = _shared_ends(stems)
    rest = [s[start:len(s) - end] for s in stems]
    codes = [r.strip(_SEPARATORS) or r for r in rest]
    chars = [chr(int(c)) for c in codes] if _ascii_codes(codes) else [guess_char(r) for r in rest]
    first = min(stems, default="")
    return chars, first[:start], first[len(first) - end:]


# ---------------------------------------------------------------- reading a letter file


@dataclass
class _Letter:
    # Its colors in sewing order: (the file's thread or None, [(x mm, y mm, "s"/"j"/"t")]).
    runs: list[tuple[dict[str, str] | None, list[tuple[float, float, str]]]]
    box: tuple[float, float, float, float]  # round its needle drops: left, top, right, bottom (y down)

    @property
    def width(self) -> float:
        return round(self.box[2] - self.box[0], 3)

    @property
    def height(self) -> float:
        return round(self.box[3] - self.box[1], 3)


_KIND_OF = {pe.STITCH: "s", pe.JUMP: "j", pe.TRIM: "t"}


def _read_letter(path: Path) -> _Letter:
    """One letter file's stitches, color by color, without the moves before and after each color
    (the text adds its own between letters)."""
    pattern = design.load(path)
    colors: list[list[tuple[float, float, str]]] = [[]]  # one per thread, as design.summarize counts them
    for x, y, command in pattern.stitches:
        kind = command & pe.COMMAND_MASK
        if kind == pe.END:
            break
        if kind in (pe.COLOR_CHANGE, pe.NEEDLE_SET):
            colors.append([])
        elif kind in _KIND_OF:  # a stop inside a color is left out: it doesn't start a new one
            colors[-1].append((x / 10, y / 10, _KIND_OF[kind]))
    runs = []
    for n, recs in enumerate(colors):
        drops = [i for i, r in enumerate(recs) if r[2] == "s"]
        if drops:
            thread = design._thread(pattern.threadlist[n]) if n < len(pattern.threadlist) else None
            runs.append((thread, recs[drops[0]:drops[-1] + 1]))
    xs = [x for _, recs in runs for x, _, k in recs if k == "s"]
    ys = [y for _, recs in runs for _, y, k in recs if k == "s"]
    if not xs or not all(math.isfinite(v) for v in (*xs, *ys)):
        raise design.DesignError(f"Couldn't read {path.name}: no stitches found")
    return _Letter(runs, (min(xs), min(ys), max(xs), max(ys)))


def _thumbnail(letter: _Letter) -> str:
    """The letter's stitches as a see-through PNG exactly the size of its box, so the dialog can
    also stand it on the preview's baseline."""
    from PIL import Image, ImageDraw

    from ..library import _hex_rgb

    left, top, right, bottom = letter.box
    w, h = max(right - left, 0.1), max(bottom - top, 0.1)
    per_mm = min(THUMB_PX / max(w, h), THUMB_MAX_PX_PER_MM)
    size = (max(1, round(w * per_mm)), max(1, round(h * per_mm)))
    big = per_mm * 2  # drawn twice the size, then shrunk, for smooth lines
    img = Image.new("RGBA", (size[0] * 2, size[1] * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for n, (thread, recs) in enumerate(letter.runs):
        color = thread["color"] if thread else PLACEHOLDER_THREADS[n % len(PLACEHOLDER_THREADS)][0]
        last = None
        for x, y, kind in recs:
            point = ((x - left) * big, (y - top) * big)
            if kind == "s" and last:
                draw.line([last, point], fill=(*_hex_rgb(color), 255), width=max(2, round(0.35 * big)))
            last = point if kind == "s" else None
    buf = io.BytesIO()
    img.resize(size, Image.Resampling.LANCZOS).save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _letter_paths(folder: str, files: list[str] | None) -> list[Path]:
    """The files to look at, in name order: the ones picked, or the designs in a folder."""
    if files:
        if not isinstance(files, list):
            raise LetteringError("Choose a folder of letter files first")
        found = [Path(f) for f in dict.fromkeys(str(f) for f in files)]
    elif folder:
        root = Path(folder)
        if not root.is_dir():
            raise LetteringError(f"Couldn't find the folder {root.name or folder}")
        readable = design._readable()
        try:
            found = [p for p in root.iterdir() if p.suffix.lower().lstrip(".") in readable and p.is_file()
                     and not p.name.startswith("._")]  # "._" files are what macOS leaves on USB sticks
        except OSError as exc:
            raise LetteringError(f"Couldn't read that folder: {exc.strerror or exc}") from exc
        if not found:
            raise LetteringError("No embroidery files in that folder. Pick the folder with one design file for "
                                 "each letter.")
    else:
        raise LetteringError("Choose a folder of letter files first")
    if len(found) > MAX_LETTER_FILES:
        raise LetteringError(f"That's {len(found)} designs, more than a font needs (at most {MAX_LETTER_FILES}). "
                             "Pick a folder with just one design file for each letter.")
    return sorted(found, key=lambda p: (p.name.casefold(), p.name, str(p)))


def scan_letter_files(folder: str = "", files: list[str] | None = None) -> dict[str, Any]:
    """The letter files in `folder` (or the `files` named): {"files": [{path, name, guess,
    thumb, width_mm, height_mm, stitches, colors}], "common": {prefix, suffix}}. A file that
    can't be read is listed with an "error"."""
    found: list[dict[str, Any]] = []
    read: list[tuple[int, str]] = []  # (place in `found`, name without its ending)
    for path in _letter_paths(folder, files):
        entry: dict[str, Any] = {"path": str(path), "name": path.name, "guess": "", "thumb": "", "width_mm": 0.0,
                                 "height_mm": 0.0, "stitches": 0, "colors": 0}
        try:
            letter = _read_letter(path)
            entry.update(thumb=_thumbnail(letter), width_mm=letter.width, height_mm=letter.height,
                         stitches=sum(1 for _, recs in letter.runs for r in recs if r[2] == "s"),
                         colors=len(letter.runs))
            read.append((len(found), path.stem))
        except Exception as exc:  # noqa: BLE001 - one damaged file mustn't hide the others
            entry["error"] = str(exc)[:200]
        found.append(entry)
    chars, prefix, suffix = guess_chars([stem for _, stem in read])
    for (i, _), char in zip(read, chars):
        found[i]["guess"] = char
    return {"files": found, "common": {"prefix": prefix, "suffix": suffix}}


# ---------------------------------------------------------------- building the font


def _number(value: Any, problem: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LetteringError(problem) from None
    if isinstance(value, bool) or not math.isfinite(number):
        raise LetteringError(problem)
    return number


def _checked(letters: Any) -> list[tuple[Path, str, float | None]]:
    """(file, character, nudge or None) for each letter, or one message naming every file without
    a character of its own and every character given to two files."""
    if not isinstance(letters, list) or not letters:
        raise LetteringError("Choose at least one letter file")
    picked: list[tuple[Path, str, float | None]] = []
    nameless: list[str] = []
    used: dict[str, list[str]] = {}
    for entry in letters:
        if not isinstance(entry, dict) or not entry.get("path"):
            raise LetteringError("Each letter needs its file")
        path = Path(str(entry["path"]))
        char = _tidy(str(entry.get("char") or ""))
        if not _one_char(char):
            nameless.append(path.name)
            continue
        dy = entry.get("dy_mm")
        if dy is not None:
            dy = _number(dy, f"The nudge for {path.name} should be a number")
        used.setdefault(char, []).append(path.name)
        picked.append((path, char, dy))
    problems = [f"{char} is given to more than one file ({', '.join(names)})"
                for char, names in used.items() if len(names) > 1]
    if nameless:
        problems.append(f"no single character is given for {', '.join(nameless)}")
    if problems:
        raise LetteringError(f"The font wasn't made: {'; '.join(problems)}. Give each file one character of its "
                             "own, or leave it out.")
    return picked


def _cap_height(heights: dict[str, float]) -> float:
    """The median height of the capitals and digits (else worked out from the small letters)."""
    for wanted in (lambda c: c in CAPITALS_AND_DIGITS, str.isupper, lambda c: c in TALL_LETTERS):
        found = [h for c, h in heights.items() if wanted(c)]
        if found:
            return round(max(median(found), 1.0), 3)
    small = [h for c, h in heights.items() if c in X_LETTERS]
    value = median(small) / X_SHARE if small else median(heights.values())
    return round(max(value, 1.0), 3)


def _drop(char: str, height: float, cap: float, x_height: float) -> float:
    """How far below the baseline a letter's bottom goes (mm; above it when negative)."""
    if char in HANG_FROM_X:
        return height - x_height  # its top level with the small letters'
    if char in HANG_A_LITTLE:
        return LITTLE_HANG * cap
    if char in AT_TOP:
        return height - cap
    if char in AT_MIDDLE:
        return (height - cap) / 2
    return 0.0


def _placeholder(n: int) -> dict[str, str]:
    color, name = PLACEHOLDER_THREADS[n % len(PLACEHOLDER_THREADS)]
    return {"color": color, "name": name, "catalog": "", "brand": ""}


def _colors(letters: list[_Letter]) -> tuple[list[dict[str, str]], list[list[int]]]:
    """The font's threads in sewing order, and each letter's color numbers, one for each of its
    file's colors.

    A font whose letters each have one color is a one-color font (it sews in the text's thread),
    whatever colors the files were saved in. Otherwise the letters' colors are merged into one
    order that keeps each letter's own: a color used again after another gets a number of its
    own, so what covers what stays the same. Letters with the most colors set the order."""
    if all(len(letter.runs) == 1 for letter in letters):
        threads = [letter.runs[0][0] for letter in letters if letter.runs[0][0]]
        keys = [t["color"].lower() for t in threads]
        most = threads[keys.index(max(keys, key=keys.count))] if threads else _placeholder(0)  # first of equals
        return [most], [[0] for _ in letters]
    # A file that doesn't say its colors (DST) matches by place: its first color, its second...
    keys = [[t["color"].lower() if t else f"color {k}" for k, (t, _) in enumerate(letter.runs)] for letter in letters]
    order: list[dict[str, Any]] = []
    chosen: list[list[dict[str, Any]]] = [[] for _ in letters]
    for i in sorted(range(len(letters)), key=lambda n: (-len(keys[n]), n)):
        at = 0
        for k, key in enumerate(keys[i]):
            j = next((j for j in range(at, len(order)) if order[j]["key"] == key), None)
            if j is None:
                # A new color goes before the first of this letter's later colors already there.
                j = next((j for later in keys[i][k + 1:] for j in range(at, len(order)) if order[j]["key"] == later),
                         len(order))
                order.insert(j, {"key": key, "thread": letters[i].runs[k][0]})
            chosen[i].append(order[j])
            at = j + 1
    number = {id(slot): n for n, slot in enumerate(order)}
    threads = [slot["thread"] or _placeholder(n) for n, slot in enumerate(order)]
    return threads, [[number[id(slot)] for slot in slots] for slots in chosen]


def build_from_files(letters: list[dict[str, Any]], name: str, gap_pct: float = DEFAULT_GAP_PCT,
                     dest: str = "") -> dict[str, Any]:
    """A version 2 .luddfont from `letters` [{path, char, dy_mm?}]: {path, glyphs,
    cap_height_mm, folder}. `dest` empty: a new file in LUDD's fonts folder.

    Each letter stands with its own bottom on the baseline, except those that hang or sit high
    (_drop); `dy_mm` instead puts its bottom that far below the baseline (above, if negative)."""
    name = _tidy(str(name or "")).strip()[:MAX_NAME].strip()
    if not name:
        raise LetteringError("Give the font a name")
    gap_pct = _number(gap_pct, "The letter gap should be a number")
    low, high = GAP_PCT_RANGE
    if not low <= gap_pct <= high:
        raise LetteringError(f"The letter gap is a percent of the capital height, from {low:g} to {high:g}")
    picked = _checked(letters)
    read = []
    for path, _, _ in picked:
        try:
            read.append(_read_letter(path))
        except Exception as exc:  # noqa: BLE001 - say which file, whatever is wrong with it
            raise LetteringError(f"Couldn't use {path.name}: {exc}") from exc

    heights = {char: letter.height for (_, char, _), letter in zip(picked, read)}
    cap = _cap_height(heights)
    small = [h for c, h in heights.items() if c in X_LETTERS]
    x_height = median(small) if small else X_SHARE * cap
    threads, numbers = _colors(read)
    gap = gap_pct / 100 * cap

    glyphs: dict[str, Any] = {}
    for (_, char, dy), letter, colors in zip(picked, read, numbers):
        left, _, right, bottom = letter.box
        drop = dy if dy is not None else _drop(char, letter.height, cap, x_height)
        move_x, move_y = gap / 2 - left, drop - bottom  # in the middle of its space, on the baseline
        stitches: list[list[Any]] = []
        blocks = []
        for (_, recs), color in zip(letter.runs, colors):
            start = len(stitches)
            stitches += [[round(x + move_x, 3), round(y + move_y, 3), k] for x, y, k in recs]
            blocks.append([start, len(stitches), color])
        glyphs[char] = {"advance_mm": round(max(right - left + gap, 0.1), 3), "stitches": stitches, "blocks": blocks}

    doc = {"format": "ludd-font", "version": 2, "name": name, "cap_height_mm": cap,
           "space_mm": round(SPACE_SHARE * cap, 3), "threads": threads, "glyphs": glyphs, "kern": {}}
    try:
        out = save_stitch_font(doc, dest, name)
    except OSError as exc:
        raise LetteringError(f"Couldn't save the font: {exc.strerror or exc}") from exc
    return {"path": str(out), "glyphs": len(glyphs), "cap_height_mm": cap, "folder": str(out.parent)}
