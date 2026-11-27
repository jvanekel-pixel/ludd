"""Artwork import (P7-D1): SVG drawings as fills, lines and satins, through art.preview."""

import math
import random

import pyembroidery as pe
import pytest
import shapely
from shapely.geometry import LineString, Point

import invariants
from artimport_util import (area_of, bounds, close, kinds, layout_of, line_of, outline_points, preview, refusal, svg,
                            write)
from threadline_engine import artimport, layout
from threadline_engine.artimport import convert as art_convert
from threadline_engine.artimport import svg as art_svg
from threadline_engine.digitize import stitches as dz

RED, BLUE, BLACK = "#ff0000", "#0000ff", "#000000"
SQUARE = '<rect x="10" y="10" width="20" height="20" fill="#ff0000"/>'


def _one(tmp_path, body, size=None, **options):
    result = preview(write(tmp_path, svg(body, size) if size else svg(body)), **options)
    assert len(result["shapes"]) == 1, result
    return result["shapes"][0], result


# ---------------------------------------------------------------- size and units


def test_real_size_from_mm_units(tmp_path):
    shape, result = _one(tmp_path, '<rect x="10" y="10" width="80" height="30" fill="#ff0000"/>')
    assert result["size_mm"] == [80.0, 30.0]
    assert result["scale_note"] is None
    assert close(bounds(shape), (-40, -15, 40, 15))  # centered on the artwork's middle


@pytest.mark.parametrize("size, wide, tall", [
    ('width="2in" height="1in" viewBox="0 0 200 100"', 50.8, 25.4),
    ('width="10cm" height="5cm" viewBox="0 0 200 100"', 100, 50),
    ('width="144pt" height="72pt" viewBox="0 0 200 100"', 50.8, 25.4),
    ('width="100mm" viewBox="0 0 200 100"', 100, 50),  # a missing side follows the viewBox
    ('height="50mm" viewBox="0 0 200 100"', 100, 50),
])
def test_physical_units_give_the_real_size(tmp_path, size, wide, tall):
    result = preview(write(tmp_path, svg('<rect width="200" height="100"/>', size)))
    assert close(result["size_mm"], (wide, tall)) and result["scale_note"] is None


@pytest.mark.parametrize("size", [
    'width="192" height="96"',
    'width="192px" height="96px"',
    'viewBox="0 0 192 96"',
    'width="100%" height="100%" viewBox="0 0 192 96"',
    "",
])
def test_pixels_assume_96_per_inch_with_a_note(tmp_path, size):
    result = preview(write(tmp_path, svg('<rect width="192" height="96"/>', size)))
    assert close(result["size_mm"], (50.8, 25.4))
    assert "96 pixels per inch" in result["scale_note"] and "Width" in result["scale_note"]


def test_width_rescales(tmp_path):
    body = ('<line x1="20" y1="25" x2="80" y2="25" stroke="#0000ff" stroke-width="4"/>'
            '<rect x="10" y="10" width="80" height="30" fill="#ff0000"/>')
    result = preview(write(tmp_path, svg(body)), width_mm=40)
    assert result["size_mm"] == [40.0, 15.0]
    line, fill = result["shapes"]
    assert close(bounds(fill), (-20, -7.5, 20, 7.5))
    assert line["kind"] == "satin" and line["geometry"]["width_mm"] == 2.0  # strokes scale too


def test_width_must_be_sensible(tmp_path):
    path = write(tmp_path, svg(SQUARE))
    assert "between 1 and 1000 mm" in refusal(path, width_mm=5000)
    assert "must be a number" in refusal(path, width_mm="wide")


def test_a_drawing_far_bigger_than_any_hoop_asks_for_a_width(tmp_path):
    path = write(tmp_path, svg('<rect width="3000" height="1000"/>',
                               'width="3000mm" height="1000mm" viewBox="0 0 3000 1000"'))
    message = refusal(path)
    assert "3.0 m wide" in message and "Set Width" in message
    assert preview(path, width_mm=90)["size_mm"] == [90.0, 30.0]


# ---------------------------------------------------------------- fills and fill rules


def test_filled_path_is_a_fill(tmp_path):
    shape, _ = _one(tmp_path, '<path d="M10 10 H60 V40 H10 Z" fill="#ff0000" '
                              'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" inkscape:label="Door"/>')
    assert (shape["kind"], shape["color"], shape["name"]) == ("fill", RED, "Door")
    assert [n[2] for n in shape["geometry"]["outline"]] == ["l", "l", "l", "l"]  # four straight sides
    assert "holes" not in shape["geometry"]
    assert area_of(shape).area == pytest.approx(1500, abs=0.1)


def _rings(inner_clockwise: bool) -> str:
    inner = "M20 20 H40 V30 H20 Z" if inner_clockwise else "M20 20 V30 H40 V20 Z"
    return f"M10 10 H60 V40 H10 Z {inner}"


@pytest.mark.parametrize("same_way", [True, False])
def test_evenodd_ring_is_a_hole(tmp_path, same_way):
    shape, _ = _one(tmp_path, f'<path d="{_rings(same_way)}" fill-rule="evenodd"/>')
    assert len(shape["geometry"]["holes"]) == 1
    assert area_of(shape).area == pytest.approx(1500 - 200, abs=0.1)


def test_nonzero_same_way_rings_have_no_hole(tmp_path):
    shape, _ = _one(tmp_path, f'<path d="{_rings(True)}"/>')
    assert "holes" not in shape["geometry"] and area_of(shape).area == pytest.approx(1500, abs=0.1)
    shape, _ = _one(tmp_path, f'<path d="{_rings(False)}"/>')
    assert len(shape["geometry"]["holes"]) == 1 and area_of(shape).area == pytest.approx(1300, abs=0.1)


def test_an_island_in_a_hole_is_a_fill_of_its_own(tmp_path):
    d = "M0 0 H40 V40 H0 Z M5 5 H35 V35 H5 Z M15 15 H25 V25 H15 Z"
    result = preview(write(tmp_path, svg(f'<path d="{d}" fill-rule="evenodd"/>')))
    assert [len(s["geometry"].get("holes", [])) for s in result["shapes"]] == [1, 0]
    assert sorted(round(area_of(s).area) for s in result["shapes"]) == [100, 700]


def test_a_path_that_crosses_itself_fills_both_halves(tmp_path):
    result = preview(write(tmp_path, svg('<path d="M0 0 L40 30 L40 0 L0 30 Z"/>')))
    assert kinds(result) == ["fill", "fill"]
    assert [round(area_of(s).area) for s in result["shapes"]] == [300, 300]


def test_overlapping_subpaths_follow_the_fill_rule(tmp_path):
    d = "M0 0 H20 V20 H0 Z M10 10 H30 V30 H10 Z"
    nonzero = preview(write(tmp_path, svg(f'<path d="{d}"/>')))
    assert len(nonzero["shapes"]) == 1 and area_of(nonzero["shapes"][0]).area == pytest.approx(700, abs=1)
    evenodd = preview(write(tmp_path, svg(f'<path d="{d}" fill-rule="evenodd"/>')))
    assert sum(area_of(s).area for s in evenodd["shapes"]) == pytest.approx(600, abs=1)


# ---------------------------------------------------------------- strokes


def test_thin_stroke_is_a_line(tmp_path):
    shape, _ = _one(tmp_path, '<path d="M10 25 H70" fill="none" stroke="#0000ff" stroke-width="0.5"/>')
    assert (shape["kind"], shape["color"]) == ("run", BLUE)
    assert "width_mm" not in shape["geometry"] and "closed" not in shape["geometry"]
    assert shape["geometry"]["nodes"] == [[-30.0, 0.0, "c"], [30.0, 0.0, "l"]]


def test_3mm_stroke_is_a_3mm_ribbon(tmp_path):
    shape, result = _one(tmp_path, '<path d="M10 25 H70" fill="none" stroke="#0000ff" stroke-width="3"/>')
    assert shape["kind"] == "satin" and shape["geometry"]["width_mm"] == 3.0
    assert close(line_of(shape).bounds, (-30, 0, 30, 0))
    assert close(result["size_mm"], (60, 3))  # the size counts the stroke's width


def test_a_stroke_width_follows_its_transforms(tmp_path):
    shape, _ = _one(tmp_path, '<g transform="scale(2)"><line x1="5" y1="10" x2="40" y2="10" stroke="black" '
                              'stroke-width="1.5"/></g>')
    assert shape["geometry"]["width_mm"] == 3.0
    assert close(line_of(shape).bounds, (-35, 0, 35, 0))


def test_a_closed_stroke_is_a_closed_ribbon(tmp_path):
    shape, _ = _one(tmp_path, '<circle cx="50" cy="25" r="15" fill="none" stroke="black" stroke-width="2"/>')
    assert shape["kind"] == "satin" and shape["geometry"]["closed"] is True
    assert line_of(shape).hausdorff_distance(Point(0, 0).buffer(15, 256).exterior) < 0.2


def test_very_thick_stroke_is_a_fill_with_a_note(tmp_path):
    shape, result = _one(tmp_path, '<path d="M20 25 H80" stroke="#0000ff" stroke-width="15" fill="none"/>')
    assert (shape["kind"], shape["color"]) == ("fill", BLUE)
    assert close(bounds(shape), (-30, -7.5, 30, 7.5), 0.2)
    [note] = [w for w in result["warnings"] if w["code"] == "art_wide_stroke"]
    assert "wider than 12 mm" in note["message"] and "filled" in note["message"]


def test_a_thick_closed_stroke_keeps_its_middle_open(tmp_path):
    shape, _ = _one(tmp_path, '<rect x="25" y="10" width="40" height="30" fill="none" stroke="black" '
                              'stroke-width="14"/>')
    assert shape["kind"] == "fill" and len(shape["geometry"]["holes"]) == 1
    area = area_of(shape)
    assert area.contains(Point(-20, 0)) and not area.contains(Point(0, 0))


def test_lines_as_running_stitch_or_satin(tmp_path):
    body = ('<path d="M10 15 H60" stroke="black" stroke-width="0.5" fill="none"/>'
            '<path d="M10 35 H60" stroke="black" stroke-width="3" fill="none"/>')
    path = write(tmp_path, svg(body))
    assert kinds(preview(path)) == ["run", "satin"]
    assert kinds(preview(path, strokes="lines")) == ["run", "run"]
    satins = preview(path, strokes="satins")
    assert [s["geometry"]["width_mm"] for s in satins["shapes"]] == [1.0, 3.0]
    assert any(w["code"] == "art_thin_satin" and "1 mm satins" in w["message"] for w in satins["warnings"])
    assert "automatic, running stitch or satin" in refusal(path, strokes="fills")


def test_fill_and_stroke_make_two_shapes_fill_first(tmp_path):
    result = preview(write(tmp_path, svg('<rect x="10" y="10" width="40" height="20" fill="#ff0000" '
                                         'stroke="#0000ff" stroke-width="2"/>')))
    assert [(s["kind"], s["color"]) for s in result["shapes"]] == [("fill", RED), ("satin", BLUE)]
    assert result["shapes"][1]["geometry"]["closed"] is True


# ---------------------------------------------------------------- structure and styles


def test_groups_transforms_use_and_classes(tmp_path):
    body = """
      <defs><rect id="tile" width="8" height="4"/></defs>
      <g transform="translate(20,10)"><g transform="rotate(90)"><rect class="a" width="10" height="4"/></g></g>
      <use xlink:href="#tile" x="60" y="30" fill="#0000ff"/>
      <g fill="#00ff00"><rect x="40" y="2" width="6" height="6"/></g>
      <g display="none"><rect width="50" height="50"/></g>
      <rect width="50" height="50" visibility="hidden"/>
      <rect width="50" height="50" opacity="0"/>
      <rect x="1" y="1" width="3" height="3" fill="none"/>
      <style>.a { fill: #ff0000 } /* after the shapes it styles, as some programs write it */</style>
    """
    result = preview(write(tmp_path, svg(body)))
    assert [(s["kind"], s["color"]) for s in result["shapes"]] == [("fill", RED), ("fill", BLUE), ("fill", "#00ff00")]
    # The artwork runs from x 16 (turned rect) to 68 (the used tile), y 2 to 34.
    assert result["size_mm"] == [52.0, 32.0]
    turned, used, grouped = result["shapes"]
    assert close(bounds(turned), (-26, -8, -22, 2))
    assert close(bounds(used), (18, 12, 26, 16))
    assert close(bounds(grouped), (-2, -16, 4, -10))


def test_symbols_draw_only_through_use_and_fit_its_box(tmp_path):
    body = ('<symbol id="s" viewBox="0 0 2 1"><rect width="2" height="1" fill="#ff0000"/></symbol>'
            '<use href="#s" x="10" y="10" width="20" height="20"/><rect x="50" y="10" width="10" height="10"/>')
    result = preview(write(tmp_path, svg(body)))
    assert [(s["color"]) for s in result["shapes"]] == [RED, BLACK]
    # 20 x 10, in the middle of the use's 20 x 20 box (x 10 to 30, y 15 to 25).
    assert close(bounds(result["shapes"][0]), (-25, -2.5, -5, 7.5))


def test_masks_markers_and_clips_are_not_drawn_as_shapes(tmp_path):
    body = ('<mask id="m"><rect width="100" height="50"/></mask>'
            '<marker id="k"><rect width="100" height="50"/></marker>'
            '<clipPath id="c"><rect width="1" height="1"/></clipPath>'
            '<pattern id="p"><rect width="100" height="50"/></pattern>'
            '<metadata><rect width="100" height="50"/></metadata>'
            '<rect x="10" y="10" width="20" height="20" clip-path="url(#c)"/>')
    result = preview(write(tmp_path, svg(body)))
    assert len(result["shapes"]) == 1 and result["size_mm"] == [20.0, 20.0]
    assert [s for s in result["skipped"] if s["what"] == "clip"][0]["count"] == 1


def test_gradients_come_in_as_their_first_color_and_patterns_are_left_out(tmp_path):
    body = ('<defs><linearGradient id="stops"><stop offset="0" style="stop-color:#123456"/>'
            '<stop offset="1" stop-color="red"/></linearGradient>'
            '<radialGradient id="g" xlink:href="#stops"/><pattern id="p"/></defs>'
            '<rect x="10" y="10" width="20" height="20" fill="url(#g)"/>'
            '<rect x="40" y="10" width="20" height="20" fill="url(#p)"/>'
            '<rect x="70" y="10" width="20" height="20" fill="url(#missing) #00ff00"/>')
    result = preview(write(tmp_path, svg(body)))
    assert [s["color"] for s in result["shapes"]] == ["#123456", "#00ff00"]
    assert {s["what"]: s["count"] for s in result["skipped"]} == {"gradient": 1, "pattern": 1}


@pytest.mark.parametrize("paint, color", [
    ("Navy", "#000080"), ("#0f0", "#00ff00"), ("rgb(10, 20, 30)", "#0a141e"), ("rgb(100% 0% 0% / 0.5)", RED),
    ("hsl(240, 100%, 50%)", BLUE), ("currentColor", "#abcdef"), ("notacolor", BLACK),
])
def test_colors_come_across_as_they_are(tmp_path, paint, color):
    shape, _ = _one(tmp_path, f'<g color="#abcdef"><rect width="9" height="9" fill="{paint}"/></g>')
    assert shape["color"] == color


@pytest.mark.parametrize("attributes", ['fill="none"', 'fill="transparent"', 'fill="rgba(0,0,0,0)"',
                                        'fill-opacity="0"', 'style="fill:none"'])
def test_invisible_paint_makes_no_shape(tmp_path, attributes):
    result = preview(write(tmp_path, svg(f'<rect width="9" height="9" {attributes}/>')))
    assert result["shapes"] == [] and result["size_mm"] == [0.0, 0.0]
    assert any(w["code"] == "art_empty" for w in result["warnings"])


def test_dashes_come_in_solid_and_are_counted(tmp_path):
    shape, result = _one(tmp_path, '<path d="M0 5 H60" stroke="black" fill="none" stroke-dasharray="3 2"/>')
    assert shape["kind"] == "satin"
    assert [s for s in result["skipped"] if s["what"] == "dash"][0]["count"] == 1


def test_basic_shapes(tmp_path):
    body = """
      <rect x="2" y="2" width="20" height="10"/>
      <rect x="26" y="2" width="20" height="10" rx="4"/>
      <circle cx="58" cy="8" r="6"/>
      <ellipse cx="80" cy="8" rx="12" ry="6"/>
      <line x1="2" y1="20" x2="30" y2="20" stroke="black" stroke-width="0.4"/>
      <polyline points="36,18 46,28 56,18" fill="none" stroke="black" stroke-width="0.4"/>
      <polygon points="70,18 90,18 80,34"/>
    """
    result = preview(write(tmp_path, svg(body)))
    assert kinds(result) == ["fill", "fill", "fill", "fill", "run", "run", "fill"]
    cx, cy = 47, 18  # the artwork runs from x 2 to 92, y 2 to 34
    expected = [(2, 2, 22, 12), (26, 2, 46, 12), (52, 2, 64, 14), (68, 2, 92, 14), (2, 20, 30, 20),
                (36, 18, 56, 28), (70, 18, 90, 34)]
    assert result["size_mm"] == [90.0, 32.0]
    for shape, (x0, y0, x1, y1) in zip(result["shapes"], expected):
        assert close(bounds(shape), (x0 - cx, y0 - cy, x1 - cx, y1 - cy), 0.2), shape
    assert area_of(result["shapes"][1]).area == pytest.approx(200 - (4 - math.pi) * 16, abs=1.5)
    assert len(result["shapes"][6]["geometry"]["outline"]) == 3


@pytest.mark.parametrize("radius", [1.5, 4, 6])
def test_a_circle_becomes_few_points(tmp_path, radius):
    shape, _ = _one(tmp_path, f'<circle cx="30" cy="25" r="{radius}"/>')
    nodes = shape["geometry"]["outline"]
    assert len(nodes) <= 16
    drawn = LineString([*outline_points(nodes), outline_points(nodes)[0]])
    exact = Point(0, 0).buffer(radius, 512).exterior
    assert drawn.hausdorff_distance(exact) <= 0.2


def test_an_arc_is_drawn_where_the_path_says(tmp_path):
    shape, _ = _one(tmp_path, '<path d="M 20 25 A 15 8 30 1 1 44 28" fill="none" stroke="black" stroke-width="0.3"/>')
    from svgelements import Arc, Path

    arc = [s for s in Path("M 20 25 A 15 8 30 1 1 44 28").segments() if isinstance(s, Arc)][0]
    exact = LineString([(p.x, p.y) for p in (arc.point(i / 400) for i in range(401))])
    cx, cy = (exact.bounds[0] + exact.bounds[2]) / 2, (exact.bounds[1] + exact.bounds[3]) / 2
    assert line_of(shape).hausdorff_distance(shapely.affinity.translate(exact, -cx, -cy)) < 0.1


def test_skewed_and_mirrored_shapes_keep_their_curves(tmp_path):
    shape, _ = _one(tmp_path, '<g transform="translate(60,5) scale(-1,1) skewX(20)"><ellipse cx="20" cy="15" rx="12" '
                              'ry="8"/></g>')
    t = math.tan(math.radians(20))
    exact = [(60 - (20 + 12 * math.cos(a) + t * (15 + 8 * math.sin(a))), 5 + 15 + 8 * math.sin(a))
             for a in (i * math.tau / 720 for i in range(720))]
    xs, ys = [p[0] for p in exact], [p[1] for p in exact]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    expected = shapely.Polygon([(x - cx, y - cy) for x, y in exact])
    assert area_of(shape).exterior.hausdorff_distance(expected.exterior) < 0.2


def test_sharp_corners_stay_sharp(tmp_path):
    shape, _ = _one(tmp_path, '<path d="M10 10 L60 10 C 60 30 40 40 35 40 C 30 40 10 30 10 10 Z"/>')
    nodes = shape["geometry"]["outline"]
    points = {(n[0], n[1]) for n in nodes}
    assert {(-25.0, -15.0), (25.0, -15.0)} <= points  # both ends of the straight top, exactly
    assert [n for n in nodes if (n[0], n[1]) == (25.0, -15.0)][0][2] == "l"
    assert area_of(shape).bounds[1] == pytest.approx(-15, abs=0.01)  # the top stays straight


def test_a_thin_rectangle_keeps_its_four_corners(tmp_path):
    shape, _ = _one(tmp_path, '<rect x="10" y="10" width="60" height="1.2"/>')
    assert len(shape["geometry"]["outline"]) == 4
    assert area_of(shape).area == pytest.approx(72, abs=0.1)


# ---------------------------------------------------------------- order, skips and flags


def test_file_order_is_sewing_order(tmp_path):
    body = ('<rect x="10" y="10" width="10" height="10" fill="#ff0000"/>'
            '<g><circle cx="40" cy="20" r="8" fill="#0000ff"/></g>'
            '<path d="M5 40 H90" stroke="#00ff00" fill="none"/>'
            '<rect x="12" y="12" width="6" height="6" fill="#ff0000"/>')
    result = preview(write(tmp_path, svg(body)))
    assert [s["color"] for s in result["shapes"]] == [RED, BLUE, "#00ff00", RED]


def test_text_and_pictures_are_skipped_and_counted(tmp_path):
    body = (SQUARE + '<text x="3" y="20">Hi <tspan>there</tspan></text><text x="3" y="30">Again</text>'
            '<image width="20" height="20" href="data:image/png;base64,iVBORw0KGgo="/>'
            '<image width="20" height="20" xlink:href="https://example.invalid/cat.png"/>'
            '<use href="elsewhere.svg#thing"/>'
            '<g display="none"><text>hidden</text></g>')
    result = preview(write(tmp_path, svg(body)))
    assert kinds(result) == ["fill"]
    counts = {s["what"]: s["count"] for s in result["skipped"]}
    assert counts == {"text": 2, "picture": 2, "link": 1}
    assert all(s["message"] and str(s["count"]) in s["message"] for s in result["skipped"] if s["count"] > 1)


@pytest.mark.parametrize("broken, damaged", [
    ('<path/>', 0),  # no path data at all, as some programs write it
    ('<path style="fill:red"/>', 0),
    ('<path d="A 1 1 0 0 1 3 3"/>', 1),  # an arc with nowhere to start from
    ('<path d="M 0 0 C 1 1 2 2"/>', 0),  # cut short: what comes before is kept
    ('<path d="M 5 5 H"/>', 0),
])
def test_a_broken_path_does_not_stop_the_rest(tmp_path, broken, damaged):
    result = preview(write(tmp_path, svg(SQUARE + broken)))
    assert kinds(result)[0] == "fill" and result["size_mm"][0] >= 20
    assert sum(s["count"] for s in result["skipped"] if s["what"] == "damaged") == damaged


def test_tiny_pieces_are_dropped_and_counted(tmp_path):
    body = (SQUARE + '<rect x="50" y="10" width="0.9" height="0.9"/>'
            '<line x1="60" y1="10" x2="60.5" y2="10" stroke="black"/>'
            '<line x1="10" y1="40" x2="40" y2="40" stroke="black" stroke-width="0.3"/>')
    result = preview(write(tmp_path, svg(body)))
    assert kinds(result) == ["fill", "run"]  # the line's own default fill has no area at all: not counted
    assert {s["what"]: s["count"] for s in result["skipped"]} == {"tiny": 2}


def test_an_invisible_line_fill_does_not_change_the_size(tmp_path):
    result = preview(write(tmp_path, svg(SQUARE + '<path d="M0 0 L99 49"/>')))
    assert result["size_mm"] == [20.0, 20.0]


def test_background_rectangle_is_flagged(tmp_path):
    logo = '<circle cx="30" cy="25" r="10" fill="#ff0000"/><circle cx="60" cy="25" r="8" fill="#0000ff"/>'
    path = write(tmp_path, svg('<rect width="100" height="50" fill="white"/>' + logo))
    result = preview(path)
    assert [s.get("background", False) for s in result["shapes"]] == [True, False, False]
    assert close(result["size_mm"], (48, 20), 0.1)  # the background doesn't count toward the size
    assert preview(path, width_mm=96)["size_mm"] == [96.0, 40.0]
    # Asked to keep it, the size, the middle and the width are the whole drawing's.
    kept = preview(path, keep_background=True)
    assert kept["size_mm"] == [100.0, 50.0] and kept["shapes"][0]["background"] is True
    assert close(bounds(kept["shapes"][0]), (-50, -25, 50, 25))
    assert preview(path, keep_background=True, width_mm=50)["size_mm"] == [50.0, 25.0]


@pytest.mark.parametrize("body", [
    SQUARE,  # a drawing that is only a rectangle has no background
    '<circle cx="30" cy="25" r="10"/><rect width="100" height="50" fill="white"/>',  # drawn on top, not under
    '<circle cx="50" cy="25" r="25" fill="white"/><circle cx="50" cy="25" r="8"/>',  # not a rectangle
    '<rect x="10" y="10" width="20" height="20"/><circle cx="70" cy="25" r="10"/>',  # covers too little
])
def test_other_shapes_are_not_called_background(tmp_path, body):
    result = preview(write(tmp_path, svg(body)))
    assert not any(s.get("background") for s in result["shapes"])


def test_a_huge_background_behind_a_small_drawing_is_left_out(tmp_path):
    body = '<rect width="2000" height="1500" fill="white"/><circle cx="1000" cy="750" r="20" fill="#ff0000"/>'
    result = preview(write(tmp_path, svg(body, 'width="2000mm" height="1500mm" viewBox="0 0 2000 1500"')))
    assert result["size_mm"] == [40.0, 40.0] and [s["color"] for s in result["shapes"]] == [RED]
    assert any(w["code"] == "art_big_background" for w in result["warnings"])


# ---------------------------------------------------------------- limits


def _rects(n: int) -> str:
    return "".join(f'<rect x="{(i % 100) * 1.5}" y="{(i // 100) * 1.5}" width="1.2" height="1.2"/>' for i in range(n))


def test_too_many_shapes_is_refused(tmp_path):
    size = 'width="150mm" height="40mm" viewBox="0 0 150 40"'
    message = refusal(write(tmp_path, svg(_rects(2001), size)))
    assert "more than 2,000 shapes" in message and "Simplify" in message
    assert len(preview(write(tmp_path, svg(_rects(2000), size)))["shapes"]) == 2000


def test_many_shapes_warn(tmp_path):
    size = 'width="150mm" height="40mm" viewBox="0 0 150 40"'
    many = preview(write(tmp_path, svg(_rects(201), size)))
    assert [w for w in many["warnings"] if w["code"] == "art_many_shapes"]
    assert not preview(write(tmp_path, svg(_rects(200), size)))["warnings"]


def test_too_many_stitches_is_refused_before_they_are_laid_out(tmp_path):
    path = write(tmp_path, svg('<rect width="900" height="900"/>', 'width="900mm" height="900mm"'
                               ' viewBox="0 0 900 900"'))
    assert "stitches" in refusal(path) and "smaller Width" in refusal(path)
    assert preview(path, width_mm=100)["shapes"]


def test_huge_files_are_refused(tmp_path):
    path = tmp_path / "big.svg"
    path.write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>" + b" " * (20 * 1024 * 1024) + b"</svg>")
    assert "bigger than 20 MB" in refusal(path)


def test_other_files_are_refused_in_plain_words(tmp_path):
    assert "SVG, DXF and PDF" in refusal(write(tmp_path, "x", "notes.txt"))
    assert ".svgz" in refusal(write(tmp_path, b"\x1f\x8b\x08\x00junk", "art.svgz"))
    assert ".svgz" in refusal(write(tmp_path, b"\x1f\x8b\x08\x00junk", "hidden.svg"))
    assert "isn't there" in refusal(tmp_path / "gone.svg")
    assert "empty" in refusal(write(tmp_path, "  ", "empty.svg"))
    assert "isn't an SVG" in refusal(write(tmp_path, "<html><body/></html>", "page.svg"))


# ---------------------------------------------------------------- the engine sews them


def test_imported_shapes_render_and_pass_invariants(tmp_path):
    body = """
      <rect width="100" height="60" fill="#ffffff"/>
      <path d="M10 10 H45 V40 H10 Z M18 18 V32 H37 V18 Z" fill="#cc0000"/>
      <path d="M55 12 C 70 2 85 22 95 12" fill="none" stroke="#000000" stroke-width="0.5"/>
      <circle cx="70" cy="35" r="12" fill="none" stroke="#0000cc" stroke-width="3"/>
      <path d="M12 50 L40 45 L70 55 L92 46" fill="none" stroke="#006600" stroke-width="14"/>
      <path d="M48 8 l4 8 l-8 0 Z" fill="#ffcc00" stroke="#000000" stroke-width="1.2"/>
    """
    result = preview(write(tmp_path, svg(body, 'width="100mm" height="60mm" viewBox="0 0 100 60"')))
    assert kinds(result) == ["fill", "fill", "run", "satin", "fill", "fill", "satin"]
    design = layout.render(layout_of(result))
    assert len(design.items) == len(result["shapes"])
    for i, shape in enumerate(result["shapes"]):
        recs = [(x / 10, y / 10, cmd & pe.COMMAND_MASK) for (x, y, cmd), owner in zip(design.pattern.stitches, design.item_of)
                if owner == i and cmd & pe.COMMAND_MASK in (pe.STITCH, pe.JUMP, pe.TRIM)]
        if shape["kind"] == "fill":
            covered = area_of(shape)
        else:
            width = shape["geometry"].get("width_mm", 0.0)  # satins are mitred at corners, as the engine sews them
            covered = line_of(shape).buffer(width / 2 + 0.01, join_style="mitre", mitre_limit=2.0)
        invariants.assert_sane(recs, inside=covered, tolerance_mm=0.6)
        assert sum(1 for r in recs if r[2] == pe.STITCH) > 10, shape["kind"]


# ---------------------------------------------------------------- the same on every computer


def _nudge(drawing, rng):
    """Every point of a drawing one last digit up or down, as another computer's maths could."""
    def f(p):
        return tuple(math.nextafter(v, rng.choice((-math.inf, math.inf))) for v in p)

    for item in drawing.items:
        for sub in item.subpaths:
            sub.start = f(sub.start)
            sub.segments = [(seg[0], *(f(p) for p in seg[1:])) for seg in sub.segments]
    return drawing


ART = svg("""
  <circle cx="30" cy="25" r="12" fill="#cc0000" stroke="#000000" stroke-width="2"/>
  <path d="M50 10 L90 40 L90 10 L50 40 Z" fill="#0000cc"/>
  <path d="M45 45 C 55 30 65 60 75 45 S 95 30 98 44" stroke="#00aa00" stroke-width="1.5" fill="none"/>
  <path d="M5 45 L40 45" stroke="#000000" stroke-width="13" fill="none" stroke-linecap="round"/>
  <ellipse cx="15" cy="10" rx="11" ry="6" transform="rotate(23 15 10)"/>
  <rect x="60" y="2" width="12" height="7" fill="#aa00aa"/>
  <path d="M30 2 H44 V16 H30 Z M38 9 H52 V23 H38 Z" fill-rule="evenodd"/>
  <path d="M76 2 H88 V14 H76 Z M79 5 H85 V11 H79 Z" fill-rule="evenodd"/>
""")


@pytest.mark.parametrize("seed", range(1, 7))
def test_the_same_shapes_with_the_last_digit_changed(seed):
    deadline, options = artimport.Deadline(), artimport.Options()
    plain = art_convert.convert(art_svg.read(ART.encode(), deadline), options, deadline)
    nudged = art_convert.convert(_nudge(art_svg.read(ART.encode(), deadline), random.Random(seed)), options, deadline)
    assert nudged == plain


def test_crossing_outlines_come_out_the_same_however_they_are_drawn(tmp_path):
    """GEOS cuts crossing paths apart: its pieces must come out in one order, from one start point."""
    a = preview(write(tmp_path, svg('<path d="M0 0 H30 V30 H0 Z M20 20 H50 V45 H20 Z" fill-rule="evenodd"/>')))
    b = preview(write(tmp_path, svg('<path d="M50 45 H20 V20 H50 Z M30 30 V0 H0 V30 Z" fill-rule="evenodd"/>')))
    assert a["shapes"] == b["shapes"]
