"""Rewrite the command table in docs/LUDD-KNOWLEDGE-BASE.md (between the COMMANDS markers) from the
app's command registry, so the help agent's list of commands and shortcuts always matches the app.
The registry is the core array in apps/desktop/src/actions.ts (CORE_COMMANDS, called COMMANDS
before) plus every registerCommands([...]) block in apps/desktop/src/cmd/*.ts, in file name order.

    python scripts/kb_commands.py           rewrite the table
    python scripts/kb_commands.py --check   write nothing; exit 1 if the table would change

Commands whose title or shortcut is built in code (a `${…}` template) are written out by the rules
in TEMPLATED below; the script fails if it meets one it doesn't know, so none is silently missed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "desktop" / "src"
KB = ROOT / "docs" / "LUDD-KNOWLEDGE-BASE.md"
START, END = "<!-- COMMANDS:START -->", "<!-- COMMANDS:END -->"
# How the core array in actions.ts starts: its name now, then the name it had before.
CORE_ARRAYS = ("export const CORE_COMMANDS: Command[] = [", "export const COMMANDS: Command[] = [")
REGISTER = "registerCommands(["

# Commands made in a loop or with a computed title: (id pattern, rows to write).
TEMPLATED = {
    "view.pan${k}": [(f"view.pan{k}", f"Arrow{k}", f"Move the view {k.lower()} 1 cm (while drawing)") for k in ("Left", "Right", "Up", "Down")],
    "view.zoom${k}": [(f"view.zoom{k}", str(k), f"Zoom to {k}× real size") for k in range(2, 10)],
    "stitch.jumpsToTrims": [("stitch.jumpsToTrims", "Mod+Shift+J", "Trim jumps longer than 3 mm")],
}


# ---------------------------------------------------------------- reading the TypeScript

_TOKEN = re.compile(
    r"(?P<comment>//[^\n]*|/\*.*?\*/)"
    r"|(?P<string>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"
    r"|(?P<mark>[`{}/])",
    re.S,
)
_TEMPLATE_TEXT = re.compile(r"(?:\\.|\$(?!\{)|[^`\\$])*", re.S)
_REGEX = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\[\n])+/")
# A "/" after one of these (or at the very start) opens a regular expression, not a division.
_BEFORE_REGEX = re.compile(r"(?:^|[(,=:\[!&|?{};+\-*%<>~^]|\b(?:return|typeof|case|in|of|new|delete|void|throw|else|do))$")


def _code_only(src: str) -> str:
    """`src` with comments and the insides of strings, templates and regular expressions blanked
    (same length, newlines kept), so brackets and calls are only found in real code."""
    out = list(src)

    def blank(a: int, b: int) -> None:
        out[a:b] = ["\n" if c == "\n" else " " for c in src[a:b]]

    braces = 0
    holes: list[int] = []  # for each open ${ in a template: the brace depth it began at

    def template(start: int) -> int:
        """Blank template text from `start`; return where code starts again."""
        end = _TEMPLATE_TEXT.match(src, start).end()
        blank(start, end)
        if src.startswith("${", end):
            holes.append(braces)
            return end + 2
        return end + 1

    pos = 0
    while m := _TOKEN.search(src, pos):
        start, pos = m.start(), m.end()
        if m["comment"]:
            blank(start, pos)
        elif m["string"]:
            blank(start + 1, pos - 1)
        elif m["mark"] == "`":
            pos = template(pos)
        elif m["mark"] == "{":
            braces += 1
        elif m["mark"] == "}":
            if holes and holes[-1] == braces:
                holes.pop()
                pos = template(pos)
            else:
                braces -= 1
        else:  # "/"
            last = start - 1
            while last >= 0 and out[last].isspace():
                last -= 1
            if _BEFORE_REGEX.search("".join(out[max(0, last - 12): last + 1])) and (found := _REGEX.match(src, start)):
                blank(start + 1, found.end() - 1)
                pos = found.end()
    return "".join(out)


def _array(src: str, code: str, opening: int, where: str) -> str:
    """The array that opens at `opening`, up to the "]" that closes it."""
    depth = 0
    for m in re.finditer(r"[\[\]]", code[opening:]):
        depth += 1 if m[0] == "[" else -1
        if depth == 0:
            return src[opening: opening + m.end()]
    sys.exit(f"kb_commands: the command array in {where} is never closed")


def registry_sources(src_dir: Path = SRC) -> list[str]:
    """The text that declares the app's commands: the core array in actions.ts, then each
    registerCommands([...]) block in cmd/*.ts, files in name order (test files left out)."""
    actions = src_dir / "actions.ts"
    text = actions.read_text(encoding="utf-8")
    code = _code_only(text)
    marker = next((m for m in CORE_ARRAYS if m in code), None)
    if marker is None:
        sys.exit(f"kb_commands: no command array ({CORE_ARRAYS[0]}...) in {actions}")
    blocks = [_array(text, code, code.index(marker) + len(marker) - 1, actions.name)]
    for path in sorted((src_dir / "cmd").glob("*.ts"), key=lambda p: p.name):
        if path.name.endswith(".test.ts"):
            continue  # a test registering made-up commands isn't the app's list
        text = path.read_text(encoding="utf-8")
        code = _code_only(text)
        for m in re.finditer(re.escape(REGISTER), code):
            blocks.append(_array(text, code, m.end() - 1, f"cmd/{path.name}"))
    return blocks


# ---------------------------------------------------------------- the table


def commands(blocks: Iterable[str]) -> list[tuple[str, str, str]]:
    """(id, shortcut, title) for every command declared in `blocks` (see registry_sources)."""
    rows: list[tuple[str, str, str]] = []
    seen_templates: set[str] = set()
    for body in blocks:
        # Each command object: an id, then (somewhere after it) a title and a shortcut.
        for m in re.finditer(r'id:\s*(["`])([^"`]+)\1', body):
            cid = m.group(2)
            chunk = body[m.end(): m.end() + 600]
            nxt = re.search(r"\bid:\s*[\"`]", chunk)
            if nxt:
                chunk = chunk[: nxt.start()]
            title = re.search(r'title:\s*(["`])([^"`]*)\1', chunk)
            key = re.search(r'shortcut:\s*(["`])([^"`]*)\1', chunk)
            templated = "${" in cid or (title and "${" in title.group(2)) or (key and "${" in key.group(2))
            if templated:
                if cid not in TEMPLATED:
                    sys.exit(f"kb_commands: add a TEMPLATED rule for the computed command {cid!r}")
                if cid not in seen_templates:
                    rows += TEMPLATED[cid]
                    seen_templates.add(cid)
                continue
            if not title or not key:
                continue
            rows.append((cid, key.group(2), title.group(2)))
    return rows


def table(rows: list[tuple[str, str, str]]) -> str:
    out = ["| Command | Shortcut | id |", "| --- | --- | --- |"]
    for cid, key, title in rows:
        k = key.replace("|", "\\|")
        out.append(f"| {title} | `{k}` | `{cid}` |")
    return "\n".join(out)


def main(argv: list[str] | None = None, *, src_dir: Path = SRC, kb_path: Path = KB) -> None:
    ap = argparse.ArgumentParser(prog="python scripts/kb_commands.py",
                                 description="Write the app's commands into the knowledge base.")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 if the table would change")
    check = ap.parse_args(argv).check
    rows = commands(registry_sources(src_dir))
    kb = kb_path.read_text(encoding="utf-8")
    a, b = kb.index(START) + len(START), kb.index(END)
    updated = kb[:a] + "\n" + table(rows) + "\n" + kb[b:]
    name = (kb_path.relative_to(ROOT) if kb_path.is_relative_to(ROOT) else kb_path).as_posix()
    if check:
        if updated != kb:
            sys.exit(f"kb_commands: the command table in {name} is out of date: run python scripts/kb_commands.py")
        print(f"kb_commands: the table of {len(rows)} commands in {name} is up to date")
        return
    kb_path.write_text(updated, encoding="utf-8")
    print(f"kb_commands: {len(rows)} commands written to {name}")


if __name__ == "__main__":
    main()
