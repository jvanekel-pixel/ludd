"""The in-app Help guide (ai/helpdocs.py) must stay true to the app and agree with the manual."""

import re
from pathlib import Path

import pytest

from threadline_engine.ai import help, helpdocs

ROOT = Path(__file__).resolve().parents[2]
ACTIONS = ROOT / "apps" / "desktop" / "src" / "actions.ts"
MANUAL = ROOT / "docs" / "USER-MANUAL.md"

KEY = re.compile(r"\b((?:Ctrl|Shift|Alt)\+(?:(?:Ctrl|Shift|Alt)\+)*(?:F\d+|[A-Za-z0-9]\b|comma|\[|\]))")


def _registered() -> set[str]:
    src = ACTIONS.read_text(encoding="utf-8")
    keys = {k.lower() for k in re.findall(r'shortcut: "([^"]+)"', src)}
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
