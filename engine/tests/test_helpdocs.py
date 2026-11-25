"""The in-app Help guide (ai/helpdocs.py) must stay true to the app and agree with the manual."""

import importlib.util
import re
from pathlib import Path

import pytest

from threadline_engine.ai import help, helpdocs

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "apps" / "desktop" / "src"
ACTIONS = SRC / "actions.ts"
MANUAL = ROOT / "docs" / "USER-MANUAL.md"

KEY = re.compile(r"\b((?:Ctrl|Shift|Alt)\+(?:(?:Ctrl|Shift|Alt)\+)*(?:F\d+|[A-Za-z0-9]\b|comma|\[|\]))")


def _kb_commands():
    """scripts/kb_commands.py, which knows where the app declares its commands."""
    spec = importlib.util.spec_from_file_location("kb_commands", ROOT / "scripts" / "kb_commands.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registered(src_dir: Path = SRC) -> set[str]:
    blocks = _kb_commands().registry_sources(src_dir)
    keys = {k.lower() for block in blocks for k in re.findall(r'shortcut: "([^"]+)"', block)}
    # view.zoom2..9 are made in a loop
    return keys | {str(n) for n in range(2, 10)}


def _norm(k: str) -> str:
    return k.replace("Ctrl", "Mod").replace("comma", ",").lower()


@pytest.mark.skipif(not ACTIONS.exists(), reason="needs the desktop app's source next to the engine")
def test_every_shortcut_in_help_is_a_real_command():
    have = _registered()
    named = set(KEY.findall(helpdocs.GUIDE))
    assert len(named) > 40  # the shortcut list is really there
    assert sorted(k for k in named if _norm(k) not in have) == []


@pytest.mark.skipif(not MANUAL.exists(), reason="needs docs/USER-MANUAL.md")
def test_every_shortcut_in_the_manual_is_a_real_command():
    have = _registered()
    named = set(KEY.findall(MANUAL.read_text(encoding="utf-8")))
    assert sorted(k for k in named if _norm(k) not in have) == []


def test_shortcuts_declared_in_cmd_files_are_real_commands(tmp_path):
    (tmp_path / "actions.ts").write_text(
        'export const CORE_COMMANDS: Command[] = [\n  { id: "a.b", title: "B", shortcut: "Mod+B" },\n];\n'
        'const other = { shortcut: "F11" };\n', encoding="utf-8")
    (tmp_path / "cmd").mkdir()
    (tmp_path / "cmd" / "shapes.ts").write_text(
        'import { registerCommands } from "../commands";\nregisterCommands([\n'
        + "".join(f'  {{ id: "shape.s{n}", title: "Add shape {n}", shortcut: "Mod+Alt+{n}" }},\n' for n in range(4, 9))
        + "]);\n", encoding="utf-8")
    have = _registered(tmp_path)
    named = KEY.findall("Ctrl+B, then Ctrl+Alt+4, Ctrl+Alt+5, Ctrl+Alt+6, Ctrl+Alt+7 or Ctrl+Alt+8.")
    assert len(named) == 6 and sorted(k for k in named if _norm(k) not in have) == []
    assert "mod+alt+9" not in have and "f11" not in have  # only the command lists count


def test_help_says_what_the_app_does_now():
    g = helpdocs.GUIDE
    assert "Shape tab" not in g  # the panel has folding sections, no tabs
    assert "pencil in Sewing order or F2" not in g  # the pencil changes the thread; rename is F2 / double-click
    assert "about 6 mm" in g and "about 5 mm" not in g  # small-text advice, as in lettering.SMALL_TEXT_MM
    assert "fonts folder" in g  # Save as stitch font saves where the font list looks
    assert "marks for trimming" in g  # cut-stops only cut marked jumps unless asked


@pytest.mark.parametrize(
    "question, title",
    [
        ("batch convert a folder of designs", "Batch convert a folder"),
        ("insert a stop at the needle", "Stops and trims at the needle, knockdown and basting"),
        ("rename a layer", "Selecting several things, groups, pinning and renaming"),
        ("restart engine", "If the engine stops"),
    ],
)
def test_help_finds_topics_the_manual_covers(question, title):
    assert help.search(question)[0]["title"] == title
