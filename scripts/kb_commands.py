"""Rewrite the command table in docs/LUDD-KNOWLEDGE-BASE.md (between the COMMANDS markers) from the
app's command registry (COMMANDS in apps/desktop/src/actions.ts), so the help agent's list of
commands and shortcuts always matches the app.

    python scripts/kb_commands.py

Commands whose title or shortcut is built in code (a `${…}` template) are written out by the rules
in TEMPLATED below; the script fails if it meets one it doesn't know, so none is silently missed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ROOT / "apps" / "desktop" / "src" / "actions.ts"
KB = ROOT / "docs" / "LUDD-KNOWLEDGE-BASE.md"
START, END = "<!-- COMMANDS:START -->", "<!-- COMMANDS:END -->"

# Commands made in a loop or with a computed title: (id pattern, rows to write).
TEMPLATED = {
    "view.pan${k}": [(f"view.pan{k}", f"Arrow{k}", f"Move the view {k.lower()} 1 cm (while drawing)") for k in ("Left", "Right", "Up", "Down")],
    "view.zoom${k}": [(f"view.zoom{k}", str(k), f"Zoom to {k}× real size") for k in range(2, 10)],
    "stitch.jumpsToTrims": [("stitch.jumpsToTrims", "Mod+Shift+J", "Trim jumps longer than 3 mm")],
}


def commands(src: str) -> list[tuple[str, str, str]]:
    body = src[src.index("export const COMMANDS: Command[] = ["):]
    rows: list[tuple[str, str, str]] = []
    seen_templates: set[str] = set()
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


def main() -> None:
    rows = commands(ACTIONS.read_text(encoding="utf-8"))
    kb = KB.read_text(encoding="utf-8")
    a, b = kb.index(START) + len(START), kb.index(END)
    KB.write_text(kb[:a] + "\n" + table(rows) + "\n" + kb[b:], encoding="utf-8")
    print(f"kb_commands: {len(rows)} commands written to {KB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
