"""Lists of names for "One file per name", and the name templates kept in LUDD's data folder
(P5-D1)."""

from __future__ import annotations

import csv
import io
import itertools
import re
from pathlib import Path
from typing import Any

from . import project
from .storage import data_dir

MAX_ROWS = 2000
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEMPLATE_NAME = 80
_SAMPLE_ROWS = 50
_DELIMITERS = ("\t", ";", ",")  # a tie goes to the earlier one (a semicolon list may have decimal commas)

# A first row made only of these (a number may follow: line2, number 2) is a header.
_HEADER_WORDS = {"name", "first name", "last name", "full name", "first", "last", "nickname", "player", "player name",
                 "line", "text", "title", "team", "initials", "monogram", "number", "no", "num", "#", "jersey",
                 "jersey number", "size", "color", "file", "date", "message"}
# In a one-column list, these alone could be someone's name (Line, Num, No), so they aren't a header.
_ALSO_NAMES = {"line", "first", "last", "no", "num", "date", "size", "message"}
_SAME_AS = {"names": "name", "colour": "color", "thread": "color", "thread color": "color", "thread colour": "color",
            "filename": "file", "file name": "file"}

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED = re.compile(r"(con|prn|aux|nul|com\d|lpt\d)(\..*)?", re.IGNORECASE)  # Windows device names


class NamesError(Exception):
    rpc_code = -32000  # rpc.APP_ERROR


# ---------------------------------------------------------------- a list of names


def read_list(path: str) -> dict[str, Any]:
    """A CSV or text file of names: {"columns": [str], "rows": [[str]], "skipped": int}.

    Commas, semicolons or tabs, quoted fields and a byte-order mark are all fine. A first row of
    words like name, line2, number, color and file is a header; otherwise the first column is
    "name". Empty rows are left out; rows past MAX_ROWS are counted in "skipped"."""
    p = Path(path)
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            raise NamesError(f"{p.name} is too big for a list of names (over {MAX_FILE_BYTES // (1024 * 1024)} MB).")
        data = p.read_bytes()
    except OSError as exc:
        raise NamesError(f"Couldn't read {p.name}: it may have been moved or deleted.") from exc
    text = _decode(data, p.name)
    delimiter = _delimiter(text)
    options: dict[str, Any] = {"delimiter": delimiter or "\x1f"}  # \x1f: never in a list, so one column
    if delimiter is None and text.count('"') % 2:
        options["quoting"] = csv.QUOTE_NONE  # a lone quote mark mustn't swallow the lines after it
    try:
        found = [[c.strip().replace("\r\n", "\n").replace("\r", "\n") for c in row]
                 for row in csv.reader(io.StringIO(text, newline=""), **options)]
    except csv.Error as exc:
        raise NamesError(f"{p.name} can't be read as a list of names. Save it as CSV again, then load it.") from exc
    rows = [r for r in found if any(r)]
    width = max((max(i for i, c in enumerate(r) if c) + 1 for r in rows), default=0)
    if rows and _is_header(rows[0]):
        columns = _columns(rows[0], width)
        rows = rows[1:]
    else:
        columns = ["name"] + [f"column {i + 1}" for i in range(1, width)]
    if not rows:
        raise NamesError(f"There are no names in {p.name}.")
    table = [[r[i] if i < len(r) else "" for i in range(width)] for r in rows[:MAX_ROWS]]
    return {"columns": columns, "rows": table, "skipped": max(0, len(rows) - MAX_ROWS)}


def _decode(data: bytes, filename: str) -> str:
    if data.startswith(b"PK\x03\x04") or filename.lower().endswith((".xlsx", ".xls", ".ods", ".numbers")):
        raise NamesError(f"{filename} is a spreadsheet file. Save it as CSV first (File, Save As, CSV), then load that.")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):  # a spreadsheet's "Unicode Text"
        text = data.decode("utf-16", errors="replace")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("cp1252")  # a spreadsheet's plain "CSV" on Windows
            except UnicodeDecodeError:
                text = data.decode("latin-1")
    if "\x00" in text:
        raise NamesError(f"{filename} doesn't look like a list of names. Use a CSV or a plain text file.")
    return text


def _delimiter(text: str) -> str | None:
    """What separates the columns, or None for one name per line. It has to be in at least half
    the rows (or in a header row), so one name with a comma ("Davis, Jr.") stays one name."""
    best, best_score = None, 0
    for d in _DELIMITERS:
        try:
            reader = csv.reader(io.StringIO(text, newline=""), delimiter=d)
            sample = list(itertools.islice((r for r in reader if any(c.strip() for c in r)), _SAMPLE_ROWS))
        except csv.Error:
            continue
        split = sum(1 for r in sample if len(r) > 1)
        if not split or not (split * 2 >= len(sample) or (len(sample[0]) > 1 and _is_header(sample[0]))):
            continue
        if d == "\t":
            return d  # names don't have tabs in them
        if split > best_score:
            best, best_score = d, split
    return best


def _word(cell: str) -> str:
    """A header cell tidied: "File_Name" -> "file", "Line 2" -> "line2"."""
    word = " ".join(cell.replace("_", " ").replace("-", " ").lower().split()).rstrip(".:")
    base, number = re.fullmatch(r"(.*?)\s*(\d*)", word, re.DOTALL).groups()
    return _SAME_AS.get(base, base) + number


def _is_header(row: list[str]) -> bool:
    words = [_word(c) for c in row if c.strip()]
    if len(words) == 1 and words[0] in _ALSO_NAMES:
        return False
    return bool(words) and all(re.sub(r"\d+$", "", w) in _HEADER_WORDS for w in words)


def _columns(header: list[str], width: int) -> list[str]:
    """The header's column names, tidied and each used once."""
    out: list[str] = []
    for i in range(width):
        name = _word(header[i]) if i < len(header) and header[i].strip() else f"column {i + 1}"
        unique, n = name, 2
        while unique in out:
            unique, n = f"{name} ({n})", n + 1
        out.append(unique)
    return out


# ---------------------------------------------------------------- name templates


def _templates_dir() -> Path:
    return data_dir() / "templates"


def list_templates() -> list[dict[str, Any]]:
    """The saved name templates, in name order: [{"name", "path", "saved_at"}]."""
    folder = _templates_dir()
    if not folder.is_dir():
        return []
    out = []
    for f in folder.iterdir():
        if f.suffix.lower() != project.EXT or f.name.startswith("."):
            continue
        try:
            if f.is_file():
                out.append({"name": f.stem, "path": str(f), "saved_at": f.stat().st_mtime})
        except OSError:
            continue
    return sorted(out, key=lambda t: (t["name"].lower(), t["name"]))


def _file_stem(name: Any) -> str:
    """A template's name as a file name every computer takes."""
    stem = _UNSAFE.sub("_", name.strip()) if isinstance(name, str) else ""
    stem = stem.lstrip(". ")[:MAX_TEMPLATE_NAME].rstrip(". ")
    if not stem:
        raise NamesError("Give the template a name.")
    return f"_{stem}" if _RESERVED.fullmatch(stem) else stem


def save_template(name: str, project_data: dict[str, Any], replace: bool = False) -> dict[str, Any]:
    """Save a design (the same data as a project) as a name template in the data folder.
    One with the same name is only replaced when `replace` says so."""
    stem = _file_stem(name)
    if not isinstance(project_data, dict) or not isinstance(project_data.get("layout"), dict):
        raise NamesError("There's no design to save as a template.")
    dest = _templates_dir() / f"{stem}{project.EXT}"
    if dest.exists() and not replace:
        raise NamesError(f"A template named {stem} already exists.")
    data = {**project_data, "title": stem, "layout": {**project_data["layout"], "title": stem}}
    saved = project.save(str(dest), data)
    return {"name": stem, "path": saved["path"]}
