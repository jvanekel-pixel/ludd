"""Snapshots of whole-layout stitching that the digitize snapshots can't reach: lettering (with the
font built in test_lettering.py, so it's the same on any machine), knockdown and the basting box.

Snapshots live in tests/snapshots/layout.json. A changed output fails the test so it can be
reviewed; re-record with UPDATE_SNAPSHOTS=1 after checking the new output is right.
"""

import hashlib
import json

import pyembroidery as pe
import pytest

from snapshot_util import check
from threadline_engine import layout

from test_lettering import font_path  # noqa: F401  (a tiny font built in the test)

M = pe.COMMAND_MASK
RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}


def _text(font, **kw):
    return {"id": "t", "kind": "text", "text": "IOX", "font": {"path": font, "index": 0}, "size_mm": 12,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False, "thread": RED,
            "transform": {}, "threads": [], "ops": [], **kw}


def _square(i="s", x=0, y=0, w=20):
    nodes = [[x, y, "c"], [x + w, y, "c"], [x + w, y + w, "c"], [x, y + w, "c"]]
    return {"id": i, "kind": "fill", "geometry": {"outline": nodes}, "params": {}, "thread": RED,
            "transform": {}, "threads": [], "ops": []}


def _plain(items, **extra):
    return {"items": items, "merge_colors": False, "color_sort": False, "basting": {"enabled": False}, **extra}


CASES = {
    "lettering_satin_line": lambda f: _plain([_text(f)]),
    "lettering_fill_line": lambda f: _plain([_text(f, text="IO", style="fill")]),
    "lettering_satin_arc_up": lambda f: _plain([_text(f, text="IIIII", shape={"type": "arc_up", "radius_mm": 25})]),
    "lettering_monogram": lambda f: _plain([_text(f, text="IOI", monogram=True)]),
    "lettering_on_a_drawn_line": lambda f: _plain([_text(f, text="IO", shape={"type": "path", "nodes": [[-30, 10, "c"], [30, -10, "c"]]})]),
    "knockdown_under_a_square": lambda f: _plain([_square()], knockdown={"enabled": True, "margin_mm": 2}),
    "knockdown_under_text": lambda f: _plain([_text(f, text="IO", style="fill")], knockdown={"enabled": True, "margin_mm": 1.5}),
    "basting_box_round_two_squares": lambda f: {**_plain([_square("a"), _square("b", 40, 10, 10)]),
                                                "basting": {"enabled": True, "margin_mm": 5}},
}


def _digest(r):
    rounded = [[round(x, 2), round(y, 2), c & M] for x, y, c in r.pattern.stitches]
    return {
        "records": len(rounded),
        "stitches": sum(1 for *_, c in rounded if c == pe.STITCH),
        "jumps": sum(1 for *_, c in rounded if c == pe.JUMP),
        "trims": sum(1 for *_, c in rounded if c == pe.TRIM),
        "threads": [t.hex_color() for t in r.pattern.threadlist],
        "sha1": hashlib.sha1(json.dumps(rounded).encode()).hexdigest(),
    }


@pytest.mark.parametrize("name", sorted(CASES))
def test_layout_snapshot(name, font_path):  # noqa: F811
    check("layout", name, _digest(layout.render(CASES[name](font_path))))


def test_layout_snapshot_cases_show_what_they_name(font_path):  # noqa: F811
    """The recorded cases really contain lettering, a knockdown and a basting box (not an empty render)."""
    def threads(name):
        return [t.get("name") for t in layout.render_summary(CASES[name](font_path))["threads"]]

    assert threads("knockdown_under_a_square")[0].startswith("Knockdown") and len(threads("knockdown_under_a_square")) == 2
    assert threads("knockdown_under_text")[0].startswith("Knockdown")
    assert "Basting" in threads("basting_box_round_two_squares")
    for name in ("lettering_satin_line", "lettering_monogram", "lettering_on_a_drawn_line"):
        assert layout.render_summary(CASES[name](font_path))["info"]["stitches"] > 50
