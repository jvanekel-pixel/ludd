"""Lettering layout (Phase 5, track A): several lines, alignment, slant, envelopes, stacked letters
and changes to single letters, with the tiny font built in test_lettering.py (I, O, X and space)."""

import json
import math
import random

import pyembroidery as pe
import pytest
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from invariants import assert_sane
from snapshot_util import SNAPSHOT_DIR, check, digest_pattern, digest_pattern_steady
from threadline_engine import layout, lettering, project
from threadline_engine.digitize import stitches as dz
from threadline_engine.layout import objects as layout_objects
from threadline_engine.layout import text as text_pipeline

from test_layout_snapshots import CASES as OLD_CASES
from test_lettering import bounds, font_path, spec  # noqa: F401  (a tiny font built in the test)

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}
BLUE = {"color": "#2222cc", "name": "Blue", "catalog": "", "brand": ""}
FIRST_LINE_ONLY = "Text on a circle or a drawn line uses the first line only."


def _text(font, **kw):
    """A text item as LUDD 1.0.1 saved it, plus whatever `kw` adds."""
    return {"id": "t", "kind": "text", "text": "IOX", "font": {"path": font, "index": 0}, "size_mm": 12,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False, "thread": RED,
            "transform": {}, "threads": [], "ops": [], **kw}


def _lay(item):
    return {"items": [item], "merge_colors": False, "color_sort": False, "basting": {"enabled": False}}


def _objects(font, **kw):
    objs, _ = lettering.layout_text(spec(font, **kw))
    return objs


def _line(objs, n):
    return [o for o in objs if o["line"] == n]


def _letter(objs, n):
    return [o for o in objs if o["letter"] == n]


def _middle(objs):
    x0, y0, x1, y1 = bounds(objs)
    return (x0 + x1) / 2, (y0 + y1) / 2


def _polygon(o):
    g = o["geometry"]
    return Polygon([(n[0], n[1]) for n in g["outline"]], [[(n[0], n[1]) for n in h] for h in g.get("holes") or []])


def _column_at(objs, x):
    """(top, bottom) of the letters where the upright line at `x` crosses them."""
    hit = unary_union([_polygon(o) for o in objs]).intersection(LineString([(x, -100), (x, 100)]))
    assert not hit.is_empty, f"no letter at x = {x:.3f}"
    return hit.bounds[1], hit.bounds[3]


def _stitches(item):
    return layout.render(_lay(item)).pattern.stitches


# ---------------------------------------------------------------- lines and alignment


@pytest.mark.parametrize("line_spacing", [None, 0.8, 1.0, 2.0])
def test_two_lines_are_one_line_spacing_apart(font_path, line_spacing):
    kw = {} if line_spacing is None else {"line_spacing": line_spacing}
    objs, warnings = lettering.layout_text(spec(font_path, text="IO\nOI", **kw))
    assert not warnings
    assert [(o["letter"], o["line"]) for o in objs] == [(0, 0), (1, 0), (2, 1), (3, 1)]
    # I and O stand on the baseline, so a line's bottom is its baseline.
    gap = bounds(_line(objs, 1))[3] - bounds(_line(objs, 0))[3]
    assert gap == pytest.approx((line_spacing or 1.3) * 10, abs=0.05)
    # The block of lines sits on the text's position, as one line does.
    assert _middle(objs) == pytest.approx((0, 0), abs=0.05)


def test_line_spacing_stays_between_its_limits(font_path):
    def gap(value):
        objs = _objects(font_path, text="I\nI", line_spacing=value)
        return bounds(_line(objs, 1))[3] - bounds(_line(objs, 0))[3]

    assert gap(0.1) == pytest.approx(8, abs=0.05) and gap(9) == pytest.approx(30, abs=0.05)
    assert gap("wide") == pytest.approx(13, abs=0.05)  # not a number: the default


def test_blank_lines_take_room_between_but_not_around(font_path):
    one = _objects(font_path, text="IO")
    for text in ("IO\n", "\nIO", "\n\nIO\n\n"):
        assert bounds(_objects(font_path, text=text)) == pytest.approx(bounds(one), abs=1e-6), text
    spaced = _objects(font_path, text="I\n\nI")
    assert bounds(_line(spaced, 2))[3] - bounds(_line(spaced, 0))[3] == pytest.approx(26, abs=0.05)


@pytest.mark.parametrize("align,edge", [("left", lambda b: b[0]), ("center", lambda b: (b[0] + b[2]) / 2),
                                        ("right", lambda b: b[2])], ids=["left", "center", "right"])
def test_alignment_left_center_right(font_path, align, edge):
    objs = _objects(font_path, text="IOOO\nI\n IO ", align=align)
    lines = [bounds(_line(objs, n)) for n in range(3)]
    assert [edge(b) for b in lines] == pytest.approx([edge(lines[0])] * 3, abs=0.05)
    x0, _, x1, _ = bounds(objs)
    assert (x0 + x1) / 2 == pytest.approx(0, abs=0.05)  # the widest line stays centred
    assert x1 - x0 == pytest.approx(lines[0][2] - lines[0][0], abs=0.05)


def test_center_is_the_default_alignment(font_path):
    assert _objects(font_path, text="IOO\nI") == _objects(font_path, text="IOO\nI", align="center")


def test_line_break_survives_cleaning():
    assert lettering._clean_text("A\nB") == "A\nB"
    assert lettering._clean_text("A\tB\vC\fD") == "A B C D"  # tabs and other breaks are spaces
    assert lettering._clean_text("A  B​C") == "A  BC"  # separators as spaces, invisible marks out


def test_crlf_is_one_break(font_path):
    assert lettering._clean_text("A\r\nB") == "A\nB" and lettering._clean_text("A\rB") == "A\nB"
    assert [o["line"] for o in _objects(font_path, text="I\r\nI")] == [0, 1]


def test_arch_lines_use_the_alignment(font_path):
    def angles(align):
        """Each line's leftmost and rightmost letter, as angles round the arch's centre."""
        objs = _objects(font_path, text="IIIII\nII", shape={"type": "arc_up", "radius_mm": 60}, align=align)
        c = _circle_through(*[_polygon(o).centroid.coords[0] for o in _line(objs, 0)[::2]])[0]
        out = []
        for n in (0, 1):
            a = [math.atan2(p[1] - c[1], p[0] - c[0]) for p in (_polygon(o).centroid.coords[0] for o in _line(objs, n))]
            out.append((min(a), max(a)))
        return out

    left, right, middle = angles("left"), angles("right"), angles("center")
    assert left[1][0] == pytest.approx(left[0][0], abs=0.02) and right[1][1] == pytest.approx(right[0][1], abs=0.02)
    assert sum(middle[1]) / 2 == pytest.approx(sum(middle[0]) / 2, abs=0.02)


def _circle_through(a, b, c):
    """The circle through three points: (centre, radius)."""
    (ax, ay), (bx, by), (cx, cy) = a, b, c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


@pytest.mark.parametrize("kind,first,second", [("arc_up", 45, 32), ("arc_down", 45, 58)])
def test_arch_lines_are_concentric(font_path, kind, first, second):
    """On an arch the lines sit on circles round one centre, 13 mm (the line spacing) apart: over
    the top the next line is inside, under the bottom it's outside."""
    objs, warnings = lettering.layout_text(spec(font_path, text="III\nIII", shape={"type": kind, "radius_mm": 40}))
    assert not warnings
    centres = [_polygon(o).centroid.coords[0] for o in objs]
    centre, radius = _circle_through(*centres[:3])
    assert radius == pytest.approx(first, abs=0.05)
    assert [math.dist(c, centre) for c in centres[3:]] == pytest.approx([second] * 3, abs=0.05)


def test_a_curve_too_small_for_its_lines_is_drawn_bigger(font_path):
    shape = {"type": "arc_up", "radius_mm": 12}
    objs, warnings = lettering.layout_text(spec(font_path, text="III\nIII\nIII", shape=shape))
    assert any("too small for this many lines" in w for w in warnings)
    centres = [_polygon(o).centroid.coords[0] for o in objs]
    centre, radius = _circle_through(*centres[:3])
    # The innermost line stands on a circle as wide as a letter is tall; the others 13 and 26 mm out.
    assert radius == pytest.approx(10 + 26 + 5, abs=0.05)
    assert [math.dist(c, centre) for c in centres[6:]] == pytest.approx([10 + 5] * 3, abs=0.05)
    # One line on a small curve is as it was.
    _, warnings = lettering.layout_text(spec(font_path, text="III", shape=shape))
    assert not any("too small" in w for w in warnings)


@pytest.mark.parametrize("shape", [{"type": "circle", "radius_mm": 20},
                                   {"type": "path", "nodes": [[-40, 0, "c"], [40, 0, "c"]]}], ids=["circle", "path"])
def test_circle_uses_first_line_with_a_warning(font_path, shape):
    objs, warnings = lettering.layout_text(spec(font_path, text="IOI\nOO", shape=shape))
    assert FIRST_LINE_ONLY in warnings
    assert objs == _objects(font_path, text="IOI", shape=shape)
    # Nothing is lost with only blank lines after it, so nothing is said.
    for text in ("IOI\n", "IOI\n  "):
        assert FIRST_LINE_ONLY not in lettering.layout_text(spec(font_path, text=text, shape=shape))[1]
    # A blank first line doesn't count: the first line with letters is the one.
    objs, warnings = lettering.layout_text(spec(font_path, text="\nIOI", shape=shape))
    assert [o["letter"] for o in objs] == [0, 1, 2] and FIRST_LINE_ONLY not in warnings


def test_monogram_line_breaks_count_as_spaces(font_path):
    assert _objects(font_path, text="I\nO\nI", monogram=True) == _objects(font_path, text="IOI", monogram=True)


# ---------------------------------------------------------------- slant


def _edge(o, which):
    """A letter outline's lowest or highest points (its baseline or cap line), left to right."""
    pts = [(n[0], n[1]) for n in o["geometry"]["outline"]]
    y = (max if which == "bottom" else min)(p[1] for p in pts)
    return sorted(p for p in pts if abs(p[1] - y) < 1e-3)


@pytest.mark.parametrize("slant", [20, -12])
def test_slant_moves_tops_right_and_keeps_baseline(font_path, slant):
    (upright,), (leaning,) = _objects(font_path, text="I"), _objects(font_path, text="I", slant_deg=slant)
    for which in ("bottom", "top"):
        a, b = _edge(upright, which), _edge(leaning, which)
        assert b[0][1] == pytest.approx(a[0][1], abs=1e-3)  # same height
        assert b[-1][0] - b[0][0] == pytest.approx(a[-1][0] - a[0][0], abs=0.01)  # same width
    mid = lambda pts: (pts[0][0] + pts[-1][0]) / 2  # noqa: E731
    lean = mid(_edge(leaning, "top")) - mid(_edge(leaning, "bottom"))
    assert lean == pytest.approx(10 * math.tan(math.radians(slant)), abs=0.05)  # positive: tops move right
    # About its own baseline: before it is placed, the glyph's baseline points don't move at all.
    shaped = lettering._outline_glyphs("I", font_path, 0, 10, 0, "satin", shape_map=lettering.envelope.slant_shape(slant))
    plain = lettering._outline_glyphs("I", font_path, 0, 10, 0, "satin")
    assert _edge(shaped[0].objects[0], "bottom") == _edge(plain[0].objects[0], "bottom")
    assert shaped[0].advance == plain[0].advance


def test_slant_is_kept_between_30_degrees(font_path):
    assert _objects(font_path, text="I", slant_deg=75) == _objects(font_path, text="I", slant_deg=30)
    assert _objects(font_path, text="I", slant_deg=0) == _objects(font_path, text="I")


def test_slanted_satin_look_angle_is_rechosen(font_path):
    (upright,), (leaning,) = _objects(font_path, text="I"), _objects(font_path, text="I", slant_deg=20)
    assert upright["params"]["angle_deg"] == 0
    assert leaning["params"]["angle_deg"] != upright["params"]["angle_deg"]
    assert leaning["params"]["angle_deg"] == pytest.approx(20)  # still square across the leaning stem
    (back,) = _objects(font_path, text="I", slant_deg=-20)
    assert back["params"]["angle_deg"] == pytest.approx(160)
    # Woven (tatami) letters keep their own angle.
    assert _objects(font_path, text="I", style="fill", slant_deg=20)[0]["params"]["angle_deg"] == 45


def _bar_font(tmp_path):
    """A stitch font with one letter: a 2 x 10 mm bar sewn at 90 degrees."""
    bar = {"kind": "fill", "geometry": {"outline": [[0, 0, "c"], [2, 0, "c"], [2, -10, "c"], [0, -10, "c"]]},
           "params": {"angle_deg": 90}}
    doc = {"format": "ludd-font", "name": "Bars", "cap_height_mm": 10, "glyphs": {"I": {"advance_mm": 4, "objects": [bar]}}}
    path = tmp_path / "bars.luddfont"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def test_slant_shears_a_stitch_fonts_letters_and_their_angles(tmp_path):
    font = {"text": "I", "font": {"path": _bar_font(tmp_path)}, "size_mm": 10}
    (o,), _ = lettering.layout_text({**font, "slant_deg": 20})
    t = 10 * math.tan(math.radians(20))
    assert _edge(o, "top")[0][0] - _edge(o, "bottom")[0][0] == pytest.approx(t, abs=0.01)
    assert o["params"]["angle_deg"] == pytest.approx(110, abs=0.01)  # the upright rows lean with it


# ---------------------------------------------------------------- envelopes

AMOUNT = 0.5


def _expected_column(kind, u, top, bottom):
    """The (top, bottom) the spec's table gives at u, for a box from `top` to `bottom`."""
    a, h, middle, s = AMOUNT, bottom - top, (top + bottom) / 2, math.sin(math.pi * u)
    factor = {"bulge": 1 + 0.8 * a * s, "pinch": 1 - 0.6 * a * s, "pennant_right": 1 - 0.7 * a * u,
              "pennant_left": 1 - 0.7 * a * (1 - u)}.get(kind)
    if factor is not None:
        return middle - h / 2 * factor, middle + h / 2 * factor
    if kind == "wave":
        dy = 0.35 * a * h * math.sin(2 * math.pi * u)
        return top + dy, bottom + dy
    if kind == "arch_top":
        return bottom - h * (1 + 0.8 * a * s), bottom
    return top, top + h * (1 + 0.8 * a * s)  # arch_bottom


@pytest.mark.parametrize("kind", ["bulge", "pinch", "pennant_right", "pennant_left", "wave", "arch_top", "arch_bottom"])
def test_each_envelope_keeps_width_and_changes_height_as_specified(font_path, kind):
    plain = _objects(font_path, text="IIIII")
    bent, warnings = lettering.layout_text(spec(font_path, text="IIIII", envelope={"type": kind, "amount": AMOUNT}))
    assert not warnings
    x0, y0, x1, y1 = bounds(plain)
    bx0, _, bx1, _ = bounds(bent)
    assert (bx0, bx1) == pytest.approx((x0, x1), abs=0.01)  # as wide as before
    # u = 0, 0.5 and 1 (the first, middle and last I), and 0.25 and 0.75 (where a wave is highest and lowest).
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = min(max(x0 + u * (x1 - x0), x0 + 0.001), x1 - 0.001)
        assert _column_at(bent, x) == pytest.approx(_expected_column(kind, u, y0, y1), abs=0.05), u


def test_envelope_amount_defaults_to_half_and_stays_in_range(font_path):
    def height(envelope):
        b = bounds(_objects(font_path, text="III", envelope=envelope))
        return b[3] - b[1]

    assert height({"type": "bulge"}) == pytest.approx(height({"type": "bulge", "amount": 0.5}))
    assert height({"type": "bulge", "amount": 7}) == pytest.approx(height({"type": "bulge", "amount": 1}))
    assert _objects(font_path, text="III", envelope={"type": "bulge", "amount": 0}) == _objects(font_path, text="III")
    objs, warnings = lettering.layout_text(spec(font_path, text="III", envelope={"type": "spiral", "amount": 1}))
    assert objs == _objects(font_path, text="III") and any("left straight" in w for w in warnings)


def test_envelope_bends_a_straight_stem(font_path):
    """Outlines are cut into short pieces first, so an I's straight sides can bend."""
    def left_side(o):
        """How far the letter's left side strays from a straight line, between 4 mm either side
        of the middle (clear of the top and bottom edges)."""
        poly = _polygon(o)
        x0, _, x1, _ = poly.bounds
        pts = [(poly.intersection(LineString([(x0 - 1, y), (x1 + 1, y)])).bounds[0], y) for y in range(-4, 5)]
        a, b = pts[0], pts[-1]
        ux, uy = (b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b)
        return max(abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux) for p in pts)

    (straight,) = _objects(font_path, text="I", slant_deg=20)
    (bent,) = _objects(font_path, text="I", slant_deg=20, envelope={"type": "bulge", "amount": 1})
    assert left_side(straight) < 0.01 and left_side(bent) == pytest.approx(0.17, abs=0.03)  # a clear bow
    # An upright I's top, straight before, gets points far off its line from a wave.
    (waved,) = _objects(font_path, text="I", envelope={"type": "wave", "amount": 1})
    xs = [n[0] for n in waved["geometry"]["outline"]]
    inner = [n for n in waved["geometry"]["outline"] if n[1] < 0 and min(xs) + 0.01 < n[0] < max(xs) - 0.01]
    assert inner and max(abs(n[1] + 5) for n in inner) > 1


def test_envelope_chooses_the_satin_angle_again(font_path):
    bent = _objects(font_path, text="OIO", envelope={"type": "pinch", "amount": 1})
    for o in bent:
        assert o["params"]["angle_deg"] == lettering._satin_angle(_polygon(o))
    assert {o["params"]["angle_deg"] for o in _objects(font_path, text="OIO", style="fill",
                                                       envelope={"type": "bulge", "amount": 1})} == {45}


def test_envelope_carries_a_stitch_fonts_angles(tmp_path):
    font = {"text": "III", "font": {"path": _bar_font(tmp_path)}, "size_mm": 10}
    bent, _ = lettering.layout_text({**font, "envelope": {"type": "wave", "amount": 1}})
    # The upright rows stay upright where only the height changes.
    assert [o["params"]["angle_deg"] for o in bent] == pytest.approx([90, 90, 90], abs=0.01)
    flat = {"kind": "fill", "geometry": {"outline": [[0, 0, "c"], [10, 0, "c"], [10, 2, "c"], [0, 2, "c"]]},
            "params": {"angle_deg": 0}}
    (out,) = lettering.envelope.bend([flat], "wave", 1.0, "carry")
    # Flat rows follow the wave's slope at the middle, where it runs down at about 23.5 degrees.
    assert out["params"]["angle_deg"] == pytest.approx(156.6, abs=0.5)
    assert flat["params"] == {"angle_deg": 0}


def test_envelope_bends_satin_columns_rung_by_rung():
    """A True satin column bends with the letters and keeps its stitches as close together."""
    column = {"kind": "satin", "geometry": {"rail_a": [[0, -1, "l"], [20, -1, "l"]], "rail_b": [[0, 1, "l"], [20, 1, "l"]]},
              "params": {"spacing_mm": 0.36, "underlay": "auto", "comp_by_width": True}}
    (bent,) = lettering.envelope.bend([column], "bulge", 1.0, "keep")
    a, b = bent["geometry"]["rail_a"], bent["geometry"]["rail_b"]
    assert len(a) == len(b) > 15
    for p, q in zip(a, b):
        assert math.dist(p[:2], q[:2]) == pytest.approx(2 * (1 + 0.8 * math.sin(math.pi * p[0] / 20)), abs=0.01)
    mids = [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q in zip(a, b)]
    assert max(math.dist(m, n) for m, n in zip(mids, mids[1:])) <= 1.001
    before, after = dz.generate(column)[0], dz.generate(bent)[0]
    assert_sane(after, inside=Polygon([(n[0], n[1]) for n in a] + [(n[0], n[1]) for n in b[::-1]]), tolerance_mm=0.6)
    assert len(after) == pytest.approx(len(before), rel=0.12)  # no denser than before


def test_envelope_moves_stitched_letters_and_keeps_their_stitches():
    part = {"kind": "stitches", "letter": 0, "line": 0,
            "geometry": {"nodes": [[0, 0, "s"], [6, 0, "s"], [6, -10, "j"], [0, -10, "s"], [3, -5, "t"]]}}
    (out,) = lettering.envelope.bend([part], "arch_top", 1.0, "carry")
    nodes = out["geometry"]["nodes"]
    assert [n[2] for n in nodes] == ["s", "s", "j", "s", "t"] and len(nodes) == 5  # no stitches added
    assert [n[0] for n in nodes] == [0, 6, 6, 0, 3]
    assert [n[1] for n in nodes] == pytest.approx([0, 0, -10, -10, -9], abs=0.01)  # the top arches up in the middle
    assert part["geometry"]["nodes"][4] == [3, -5, "t"]  # the letter passed in is untouched
    sheared = lettering.envelope.slant_object(part, 45)["geometry"]["nodes"]
    assert [(n[0], n[1], n[2]) for n in sheared] == [(0, 0, "s"), (6, 0, "s"), (16, -10, "j"), (10, -10, "s"), (8, -5, "t")]


# ---------------------------------------------------------------- vertical


def test_vertical_stacks_letters(font_path):
    objs, warnings = lettering.layout_text(spec(font_path, text="IOI", spacing_mm=1, vertical=True))
    assert not warnings and [o["letter"] for o in objs] == [0, 1, 2]
    letters = [bounds(_letter(objs, n)) for n in range(3)]
    assert [(b[0] + b[2]) / 2 for b in letters] == pytest.approx([0, 0, 0], abs=0.01)  # one column
    step = 10 * 1.15 + 1
    assert [b[3] - letters[0][3] for b in letters] == pytest.approx([0, step, 2 * step], abs=0.05)  # top to bottom
    assert (letters[0][1] + letters[2][3]) / 2 == pytest.approx(0, abs=0.05)  # centred on the text's position


def test_vertical_lines_become_columns(font_path):
    objs = _objects(font_path, text="IO\nOII", vertical=True, line_spacing=1.5)
    first, second = _line(objs, 0), _line(objs, 1)
    assert _middle(first)[0] == pytest.approx(-7.5, abs=0.05) and _middle(second)[0] == pytest.approx(7.5, abs=0.05)
    assert bounds(first)[1] == pytest.approx(bounds(second)[1], abs=0.01)  # the columns start level
    assert bounds(_letter(objs, 4))[3] - bounds(_letter(objs, 2))[3] == pytest.approx(23, abs=0.05)


def test_vertical_spaces_leave_a_gap(font_path):
    objs = _objects(font_path, text="I I", vertical=True)
    assert bounds(_letter(objs, 1))[3] - bounds(_letter(objs, 0))[3] == pytest.approx(23, abs=0.05)
    assert bounds(_objects(font_path, text="II ", vertical=True)) == pytest.approx(
        bounds(_objects(font_path, text="II", vertical=True)), abs=1e-6)  # a space at the end changes nothing


@pytest.mark.parametrize("extra,like,words", [
    ({"vertical": True, "shape": {"type": "arc_up", "radius_mm": 25}}, {"shape": {"type": "arc_up", "radius_mm": 25}}, "stacked"),
    ({"vertical": True, "shape": {"type": "circle", "radius_mm": 25}}, {"shape": {"type": "circle", "radius_mm": 25}}, "stacked"),
    ({"envelope": {"type": "wave", "amount": 1}, "shape": {"type": "arc_down", "radius_mm": 25}},
     {"shape": {"type": "arc_down", "radius_mm": 25}}, "envelope"),
    ({"envelope": {"type": "wave", "amount": 1}, "shape": {"type": "path", "nodes": [[-40, 0, "c"], [40, 0, "c"]]}},
     {"shape": {"type": "path", "nodes": [[-40, 0, "c"], [40, 0, "c"]]}}, "envelope"),
    ({"envelope": {"type": "wave", "amount": 1}, "vertical": True}, {"vertical": True}, "envelope"),
], ids=["vertical-arch", "vertical-circle", "envelope-arch", "envelope-path", "envelope-vertical"])
def test_what_doesnt_combine_is_left_off_and_said(font_path, extra, like, words):
    objs, warnings = lettering.layout_text(spec(font_path, text="IOI", **extra))
    assert objs == _objects(font_path, text="IOI", **like)
    assert any(words in w.lower() and "left off" in w for w in warnings), warnings


# ---------------------------------------------------------------- single letters


def _parts(font, edits=None, **kw):
    return text_pipeline.text_letters(_text(font, text=kw.pop("text", "IOI"), size_mm=10,
                                            **({"letter_edits": edits} if edits else {}), **kw))[0]


def test_letter_move_turn_size(font_path):
    plain = _parts(font_path)
    edited = _parts(font_path, {"1": {"dx_mm": 3, "dy_mm": -2, "rotate": 90, "scale": 1.5}})
    for n in (0, 2):  # the letters beside it don't move
        assert [o["geometry"] for o in _letter(edited, n)] == [o["geometry"] for o in _letter(plain, n)]
    (before,), (after,) = _letter(plain, 1), _letter(edited, 1)
    x0, y0, x1, y1 = bounds([before])
    ax0, ay0, ax1, ay1 = bounds([after])
    assert ((ax0 + ax1) / 2, (ay0 + ay1) / 2) == pytest.approx(((x0 + x1) / 2 + 3, (y0 + y1) / 2 - 2), abs=0.01)
    assert (ax1 - ax0, ay1 - ay0) == pytest.approx(((y1 - y0) * 1.5, (x1 - x0) * 1.5), abs=0.01)  # turned and bigger
    assert after["params"]["angle_deg"] == pytest.approx((before["params"]["angle_deg"] + 90) % 180)
    assert len(after["geometry"]["holes"]) == 1
    assert _parts(font_path) == plain  # the letters kept for next time weren't changed


def test_letter_edits_move_every_part_of_the_letter_together():
    two = [{"kind": "run", "letter": 0, "geometry": {"nodes": [[0, 0, "c"], [2, 0, "c"]]}, "params": {}},
           {"kind": "run", "letter": 0, "geometry": {"nodes": [[0, -4, "c"], [2, -4, "c"]]}, "params": {}}]
    kept = json.dumps(two)
    out = text_pipeline._apply_letter_edits(two, {"letter_edits": {"0": {"scale": 2}}})
    # Both parts grow about the middle of the letter, (1, -2), not each about its own middle.
    assert [[n[:2] for n in o["geometry"]["nodes"]] for o in out] == [[[-1, 2], [3, 2]], [[-1, -6], [3, -6]]]
    assert json.dumps(two) == kept


def test_letter_thread_makes_a_new_block_in_order(font_path):
    s = layout.render_summary(_lay(_text(font_path, text="IOI", letter_edits={"1": {"thread": BLUE}})))
    assert [s["threads"][b["thread"]]["color"] for b in s["blocks"]] == ["#cc2222", "#2222cc", "#cc2222"]
    assert [(r["letters"], r["slots"]) for r in s["items"][0]["runs"]] == [([0], []), ([1], []), ([2], [])]


def test_letter_angle_override(font_path):
    plain = _parts(font_path)
    edited = _parts(font_path, {"0": {"angle_deg": 30}, "2": {"angle_deg": 200, "rotate": 45}})
    assert [o["params"]["angle_deg"] for o in edited] == [30, plain[1]["params"]["angle_deg"], 20]
    assert _stitches(_text(font_path, text="I", letter_edits={"0": {"angle_deg": 60}})) != _stitches(_text(font_path, text="I"))


def test_edits_past_the_end_are_dropped(font_path):
    edits = {"2": {"thread": BLUE}, "5": {"dx_mm": 5, "scale": 2}, "x": {"dy_mm": 1}, "-1": {"dy_mm": 1}}
    assert _stitches(_text(font_path, text="IO", letter_edits=edits)) == _stitches(_text(font_path, text="IO"))


def test_damaged_letter_edits_are_ignored(font_path):
    junk = {"0": {"dx_mm": "far", "rotate": None, "scale": -2, "angle_deg": "up", "thread": {"name": "no color"}}, "1": 7}
    assert _stitches(_text(font_path, text="IO", letter_edits=junk)) == _stitches(_text(font_path, text="IO"))


def test_changing_one_letter_does_not_lay_the_text_out_again(font_path, monkeypatch):
    """The layout is kept while only single letters change, so nudging one stays quick."""
    calls = []
    real = lettering.layout_text
    monkeypatch.setattr(lettering, "layout_text", lambda spec_: calls.append(spec_) or real(spec_))
    text_pipeline._text_cache.clear()
    seen = [_parts(font_path, {"1": {"dx_mm": n}}) for n in (1, 2, 3)]
    assert len(calls) == 1 and calls[0]["letter_edits"] is None
    assert [bounds(_letter(s, 1))[0] for s in seen] == pytest.approx([bounds(_letter(seen[0], 1))[0] + n for n in (0, 1, 2)])


def test_letters_break_into_shapes_where_they_were_moved(font_path):
    item = _text(font_path, text="IO\nI", letter_edits={"2": {"dx_mm": 4, "thread": BLUE}})
    shapes = layout.text_to_shapes(item)["objects"]
    assert [o["thread"]["color"] for o in shapes] == ["#cc2222", "#cc2222", "#2222cc"]
    assert "\n" not in "".join(o["name"] for o in shapes) and shapes[0]["name"] == "IO I 1"
    plain = layout.text_to_shapes(_text(font_path, text="IO\nI"))["objects"]
    assert bounds([shapes[2]])[0] == pytest.approx(bounds([plain[2]])[0] + 4, abs=0.01)


# ---------------------------------------------------------------- old text, snapshots


def test_old_text_item_renders_exactly_as_before(font_path):
    """A text saved by LUDD 1.0.1 (none of the new settings) sews record for record as before: its
    stitches match the snapshots recorded before this phase, and the new defaults change nothing."""
    recorded = json.loads((SNAPSHOT_DIR / "layout.json").read_text(encoding="utf-8"))
    for name in [k for k in OLD_CASES if k.startswith("lettering")]:
        assert digest_pattern(layout.render(OLD_CASES[name](font_path)).pattern) == recorded[name], name
    old = _text(font_path)
    defaults = _text(font_path, align="center", line_spacing=1.3, slant_deg=0, vertical=False, letter_edits={})
    assert _stitches(old) == _stitches(defaults)


SNAPSHOT_CASES = {
    "two_lines_left": {"text": "IOX\nIO", "align": "left"},
    "slant_15": {"slant_deg": 15},
    "bulge": {"text": "IOXIO", "envelope": {"type": "bulge", "amount": 0.5}},
    "pennant_right": {"text": "IOXIO", "envelope": {"type": "pennant_right", "amount": 0.5}},
    "wave": {"text": "IOXIO", "envelope": {"type": "wave", "amount": 0.5}},
    "vertical": {"vertical": True},
    "letter_moved_recolored": {"letter_edits": {"1": {"dx_mm": 2, "dy_mm": -1.5, "thread": BLUE}}},
    "done_when_1": {"text": "IOX\nIO", "slant_deg": 12, "envelope": {"type": "bulge", "amount": 0.5},
                    "letter_edits": {"1": {"dy_mm": -2.5, "thread": BLUE}}},
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshots(name, font_path):  # noqa: F811
    rendered = layout.render(_lay(_text(font_path, **SNAPSHOT_CASES[name])))
    check("lettering_layout", name, digest_pattern_steady(rendered.pattern))


class _LastDigitNoise:
    """The math module with every sine and cosine off by one last digit, up or down or not at all,
    at random: what another computer's maths library can give."""

    def __init__(self, seed):
        self._rng = random.Random(seed)

    def __getattr__(self, name):
        real = getattr(math, name)
        if name not in ("sin", "cos"):
            return real

        def nudged(x):
            v = real(x)
            return math.nextafter(v, self._rng.choice((-math.inf, v, math.inf))) if v else v

        return nudged


def _forget_stitches():
    """Empty what a render keeps, so the next one works every stitch out again."""
    text_pipeline._text_cache.clear()
    layout_objects._object_cache.clear()
    lettering.extras._cache.clear()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshots_do_not_hang_on_the_last_digit_of_a_sine(seed, font_path, monkeypatch):  # noqa: F811
    """Every snapshot case gives its recorded stitches with the last digit of each sine and cosine
    nudged. (The "bulge" case once failed on both Macs and passed on Windows and Linux: a stitch in
    the middle of a row sat exactly on a rounding step, and that last digit chose which way it
    rounded. snapshot_util.digest_pattern_steady is the cure.)"""
    recorded = json.loads((SNAPSHOT_DIR / "lettering_layout.json").read_text(encoding="utf-8"))
    _forget_stitches()
    try:
        monkeypatch.setattr(dz, "math", _LastDigitNoise(seed))
        monkeypatch.setattr(lettering.envelope, "math", _LastDigitNoise(seed + 100))
        for name in sorted(SNAPSHOT_CASES):
            rendered = layout.render(_lay(_text(font_path, **SNAPSHOT_CASES[name])))
            assert digest_pattern_steady(rendered.pattern) == recorded[name], name
    finally:
        monkeypatch.undo()
        _forget_stitches()  # nothing worked out with the nudged maths may reach another test


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_snapshot_cases_pass_the_invariants(name, font_path):  # noqa: F811
    blocks = layout.render(_lay(_text(font_path, **SNAPSHOT_CASES[name]))).blocks
    assert blocks
    for blk in blocks:
        assert_sane([(r[0] / 10, r[1] / 10, r[2]) for r in blk.recs])


def test_done_when_1(font_path, tmp_path):
    """Two lines, slanted, in an envelope, with one letter moved and recolored, from a saved
    project."""
    item = _text(font_path, **SNAPSHOT_CASES["done_when_1"])
    saved = project.save(str(tmp_path / "name.ludd"), {"layout": _lay(item), "images": []})
    reopened = project.open_project(saved["path"])["layout"]["items"][0]
    assert _stitches(reopened) == _stitches(item)
    s = layout.render_summary(_lay(item))
    assert [s["threads"][b["thread"]]["color"] for b in s["blocks"]] == ["#cc2222", "#2222cc", "#cc2222"]
    letters = s["items"][0]["letters"]
    assert sorted({p["line"] for p in letters}) == [0, 1] and [p["letter"] for p in letters] == [0, 1, 2, 3, 4]
    assert s["items"][0]["runs"][1]["letters"] == [1]
    plain = layout.render_summary(_lay({**item, "letter_edits": {}}))["items"][0]["letters"]
    dy = lambda p: sum(q[1] for q in p["ring"]) / len(p["ring"])  # noqa: E731
    assert dy(letters[1]) == pytest.approx(dy(plain[1]) - 2.5, abs=0.01)
    assert not any(w["code"].startswith("text_") for w in s["warnings"])
