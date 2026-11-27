"""Artwork import (P7-D1): DXF drawings, through art.preview. Each DXF is written by the test."""

import math
import time

import pytest
import shapely
from shapely.geometry import LineString, Point

from artimport_util import area_of, ask, bounds, close, kinds, layout_of, line_of, preview, refusal, write
from threadline_engine import layout
from threadline_engine.artimport import dxf as art_dxf


def make(tmp_path, build, units=4, name="art.dxf", version="R2010", binary=False):
    """A DXF made by `build(document, modelspace)`; `units` is $INSUNITS (4: mm)."""
    ezdxf = art_dxf.load_ezdxf()  # imported the way the engine does: no fonts read, no cache written
    doc = ezdxf.new(version)
    if units is not None:
        doc.header["$INSUNITS"] = units
    build(doc, doc.modelspace())
    path = tmp_path / name
    doc.saveas(path, fmt="bin" if binary else "asc")
    return path


def square(msp, x=0.0, y=0.0, side=20.0, **attribs):
    msp.add_lwpolyline([(x, y), (x + side, y), (x + side, y + side), (x, y + side)], close=True, dxfattribs=attribs)


def minimal(*pairs) -> str:
    """A bare DXF with no header (and so no units), from (group code, value) pairs of its entities."""
    tags = [(0, "SECTION"), (2, "ENTITIES"), *pairs, (0, "ENDSEC"), (0, "EOF")]
    return "".join(f"{code}\n{value}\n" for code, value in tags)


def line_tags(x1="0", y1="0", x2="10", y2="5"):
    return [(0, "LINE"), (8, "0"), (10, x1), (20, y1), (11, x2), (21, y2)]


def counts(result) -> dict:
    return {s["what"]: s["count"] for s in result["skipped"]}


# ---------------------------------------------------------------- units and axes


def test_dxf_inches_become_mm(tmp_path):
    def build(doc, msp):
        msp.add_line((0, 0), (1, 0))
        msp.add_line((0, 0), (0, 2))

    result = preview(make(tmp_path, build, units=1))
    assert result["size_mm"] == [25.4, 50.8] and result["scale_note"] is None


@pytest.mark.parametrize("units, length_mm", [(2, 304.8), (5, 10.0), (6, 1000.0), (9, 0.0254), (14, 100.0)])
def test_dxf_units(tmp_path, units, length_mm):
    path = make(tmp_path, lambda doc, msp: msp.add_line((0, 0), (100 / length_mm, 0)), units=units)
    assert close(preview(path)["size_mm"], (100, 0), 0.01)


@pytest.mark.parametrize("build_units", [0, None])
def test_a_dxf_with_no_units_reads_as_millimeters_and_says_so(tmp_path, build_units):
    path = (make(tmp_path, lambda doc, msp: msp.add_line((0, 0), (10, 5)), units=0) if build_units == 0
            else write(tmp_path, minimal(*line_tags()), "bare.dxf"))
    result = preview(path)
    assert result["size_mm"] == [10.0, 5.0] and "millimeters" in result["scale_note"]
    assert "Width" in result["scale_note"]


def test_dxf_y_axis_is_flipped(tmp_path):
    path = make(tmp_path, lambda doc, msp: msp.add_lwpolyline([(0, 0), (20, 0), (20, 10)]))
    [shape] = preview(path)["shapes"]
    assert [n[:2] for n in shape["geometry"]["nodes"]] == [[-10.0, 5.0], [10.0, 5.0], [10.0, -5.0]]


def test_a_binary_dxf_reads_too(tmp_path):
    path = make(tmp_path, lambda doc, msp: square(msp, side=12), binary=True)
    assert path.read_bytes().startswith(b"AutoCAD Binary DXF")
    assert preview(path)["size_mm"] == [12.0, 12.0]


# ---------------------------------------------------------------- lines and fills


def test_dxf_closed_outline_is_a_line_unless_asked(tmp_path):
    def build(doc, msp):
        square(msp)
        msp.add_circle((10, 10), 4)
        msp.add_lwpolyline([(30, 0), (40, 20)])

    path = make(tmp_path, build)
    plain = preview(path)
    assert kinds(plain) == ["run", "run", "run"]
    assert [s["geometry"].get("closed", False) for s in plain["shapes"]] == [True, True, False]
    filled = preview(path, closed_as_fills=True)
    assert kinds(filled) == ["fill", "run"]  # the circle is the square's hole
    [fill, _] = filled["shapes"]
    assert len(fill["geometry"]["holes"]) == 1
    assert area_of(fill).area == pytest.approx(400 - math.pi * 16, abs=0.5)


def test_closed_outlines_nest_by_color_and_layer(tmp_path):
    def build(doc, msp):
        doc.layers.add("Red", color=1)
        square(msp, 0, 0, 40, layer="Red")
        square(msp, 5, 5, 30, layer="Red")  # a hole in it
        square(msp, 10, 10, 20, layer="Red")  # an island in the hole
        square(msp, 15, 15, 10)  # another color: a fill of its own on top
        square(msp, 50, 0, 10, layer="Red")
        square(msp, 50, 0, 10, layer="Red")  # drawn twice: no hole, no loop

    result = preview(make(tmp_path, build), closed_as_fills=True)
    assert [(s["color"], len(s["geometry"].get("holes", []))) for s in result["shapes"]] == [
        ("#ff0000", 1), ("#ff0000", 0), ("#000000", 0), ("#ff0000", 1)]


def test_crossing_outlines_stay_two_fills(tmp_path):
    path = make(tmp_path, lambda doc, msp: (msp.add_circle((0, 0), 10), msp.add_circle((12, 0), 10)))
    result = preview(path, closed_as_fills=True)
    assert kinds(result) == ["fill", "fill"] and not any("holes" in s["geometry"] for s in result["shapes"])


def test_dxf_curves_come_in_at_their_size(tmp_path):
    def build(doc, msp):
        msp.add_circle((10, 10), 10)
        msp.add_arc((40, 10), 10, 0, 90)
        msp.add_ellipse((70, 10), major_axis=(10, 0), ratio=0.5)
        msp.add_spline([(85, 0), (90, 20), (95, 0), (100, 20)])
        msp.add_lwpolyline([(0, -10, 0, 0, 1.0), (20, -10)], format="xyseb")  # a bulge: a half circle
        msp.add_polyline2d([(30, -10), (35, -5), (40, -10)])
        msp.add_polyline3d([(45, -10, 3), (50, -5, 4), (55, -10, 5)])

    result = preview(make(tmp_path, build))
    shapes = result["shapes"]
    assert kinds(result) == ["run"] * 7
    # The drawing is 100 wide (x 0..100) and 40 tall (y -20..20, flipped), so its middle is (50, 0).
    assert close(result["size_mm"], (100, 40), 0.1)
    assert line_of(shapes[0]).hausdorff_distance(Point(-40, -10).buffer(10, 256).exterior) < 0.2
    quarter = LineString([(-10 + 10 * math.cos(a), -10 - 10 * math.sin(a)) for a in
                          (i * math.pi / 200 for i in range(101))])
    assert line_of(shapes[1]).hausdorff_distance(quarter) < 0.2
    assert close(bounds(shapes[2]), (10, -15, 30, -5), 0.2)
    assert close(bounds(shapes[4]), (-50, 10, -30, 20), 0.2)
    assert shapes[6]["geometry"]["nodes"][1][:2] == [0.0, 5.0]


def test_dxf_wide_polylines_come_in_as_satins(tmp_path):
    path = make(tmp_path, lambda doc, msp: msp.add_lwpolyline([(0, 0), (2, 0)], dxfattribs={"const_width": 0.12}),
                units=1)
    [shape] = preview(path)["shapes"]
    assert shape["kind"] == "satin" and shape["geometry"]["width_mm"] == pytest.approx(3.05, abs=0.01)


# ---------------------------------------------------------------- hatches


def hatch_with_hole(msp, color=1, style=0, island=False, **attribs):
    hatch = msp.add_hatch(color=color, dxfattribs={"hatch_style": style, **attribs})
    hatch.paths.add_polyline_path([(0, 0), (30, 0), (30, 30), (0, 30)], is_closed=True)
    hatch.paths.add_polyline_path([(5, 5), (25, 5), (25, 25), (5, 25)], is_closed=True)
    if island:
        hatch.paths.add_polyline_path([(10, 10), (20, 10), (20, 20), (10, 20)], is_closed=True)
    return hatch


def test_dxf_hatch_is_a_fill(tmp_path):
    result = preview(make(tmp_path, lambda doc, msp: hatch_with_hole(msp)))
    [shape] = result["shapes"]
    assert (shape["kind"], shape["color"]) == ("fill", "#ff0000")
    assert area_of(shape).area == pytest.approx(900 - 400, abs=0.5)


@pytest.mark.parametrize("style, areas", [(0, [500, 100]), (1, [500]), (2, [900])], ids=["normal", "outer", "ignore"])
def test_hatch_island_styles(tmp_path, style, areas):
    result = preview(make(tmp_path, lambda doc, msp: hatch_with_hole(msp, style=style, island=True)))
    assert sorted(round(area_of(s).area) for s in result["shapes"]) == sorted(areas)


def test_hatch_edges_patterns_and_gradients(tmp_path):
    def build(doc, msp):
        hatch = msp.add_hatch(color=3)
        edges = hatch.paths.add_edge_path()
        edges.add_arc((10, 10), 8, 0, 360)
        pattern = msp.add_hatch(color=5)
        pattern.set_pattern_fill("ANSI31", scale=0.5)
        pattern.paths.add_polyline_path([(30, 0), (40, 0), (40, 10)], is_closed=True)
        gradient = msp.add_hatch()
        gradient.set_gradient(color1=(18, 52, 86), color2=(200, 100, 0))
        gradient.paths.add_polyline_path([(50, 0), (60, 0), (60, 10)], is_closed=True)

    result = preview(make(tmp_path, build))
    assert kinds(result) == ["fill"] * 3
    assert [s["color"] for s in result["shapes"]] == ["#00ff00", "#0000ff", "#123456"]
    assert area_of(result["shapes"][0]).area == pytest.approx(math.pi * 64, abs=1)
    assert counts(result) == {"hatch_pattern": 1, "gradient": 1}


# ---------------------------------------------------------------- blocks


def test_dxf_block_is_expanded(tmp_path):
    def build(doc, msp):
        inner = doc.blocks.new("DASH", base_point=(1, 0))
        inner.add_line((1, 0), (6, 0))
        outer = doc.blocks.new("PAIR")
        outer.add_blockref("DASH", (0, 0))
        outer.add_blockref("DASH", (0, 10))
        msp.add_blockref("PAIR", (100, 0), dxfattribs={"rotation": 90, "xscale": 2, "yscale": 2})
        msp.add_line((70, 0), (75, 0))

    result = preview(make(tmp_path, build))
    # PAIR, turned 90 degrees and twice the size, at (100, 0): its dashes go up from (100, 0) and
    # (80, 0) by 10; the lone line is at x 70..75. The drawing's middle is (85, 5), flipped.
    lines = [sorted(tuple(n[:2]) for n in s["geometry"]["nodes"]) for s in result["shapes"]]
    assert lines == [[(15.0, -5.0), (15.0, 5.0)], [(-5.0, -5.0), (-5.0, 5.0)], [(-15.0, 5.0), (-10.0, 5.0)]]


def test_a_multi_insert_is_expanded_into_a_grid(tmp_path):
    def build(doc, msp):
        block = doc.blocks.new("DOT")
        block.add_circle((0, 0), 1)
        msp.add_blockref("DOT", (0, 0)).grid(size=(2, 3), spacing=(10, 8))

    result = preview(make(tmp_path, build))
    assert len(result["shapes"]) == 6 and close(result["size_mm"], (18, 12), 0.1)
    centers = sorted((round(line_of(s).centroid.x), round(line_of(s).centroid.y)) for s in result["shapes"])
    assert centers == [(-8, -5), (-8, 5), (0, -5), (0, 5), (8, -5), (8, 5)]


def test_a_stretched_block_keeps_true_shapes(tmp_path):
    def build(doc, msp):
        block = doc.blocks.new("C")
        block.add_circle((0, 0), 5)
        msp.add_blockref("C", (0, 0), dxfattribs={"xscale": 3, "yscale": 1})

    [shape] = preview(make(tmp_path, build))["shapes"]
    assert close(bounds(shape), (-15, -5, 15, 5), 0.2)


# ---------------------------------------------------------------- layers and colors


def test_dxf_layer_color_is_used(tmp_path):
    def build(doc, msp):
        doc.layers.add("Red", color=1)
        doc.layers.add("Teal").rgb = (0, 128, 128)
        doc.layers.add("Paper", color=7)
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "Red"})
        msp.add_line((0, 1), (10, 1), dxfattribs={"layer": "Teal"})
        msp.add_line((0, 2), (10, 2), dxfattribs={"layer": "Paper"})  # 7 is black on paper
        msp.add_line((0, 3), (10, 3), dxfattribs={"layer": "Red", "color": 5})  # its own color wins
        msp.add_line((0, 4), (10, 4), dxfattribs={"true_color": 0x336699})
        block = doc.blocks.new("B")
        block.add_line((0, 0), (10, 0), dxfattribs={"color": 0})  # by block: the insert's color
        block.add_line((0, 1), (10, 1))  # layer 0, by layer: the insert's layer
        msp.add_blockref("B", (0, 10), dxfattribs={"layer": "Teal", "color": 6})

    result = preview(make(tmp_path, build))
    assert [s["color"] for s in result["shapes"]] == [
        "#ff0000", "#008080", "#000000", "#0000ff", "#336699", "#ff00ff", "#008080"]
    assert [s["name"] for s in result["shapes"]][:2] == ["Red", "Teal"]


def test_hidden_layers_are_left_out_and_counted(tmp_path):
    def build(doc, msp):
        doc.layers.add("Off").off()
        doc.layers.add("Frozen").freeze()
        msp.add_line((0, 0), (10, 0))
        msp.add_line((0, 5), (10, 5), dxfattribs={"layer": "Off"})
        msp.add_line((0, 9), (10, 9), dxfattribs={"layer": "Frozen"})
        msp.add_line((0, 9), (10, 9), dxfattribs={"invisible": 1})

    result = preview(make(tmp_path, build))
    assert kinds(result) == ["run"] and counts(result) == {"hidden_layer": 2}


def test_dashed_layers_come_in_solid(tmp_path):
    def build(doc, msp):
        doc.linetypes.add("DASHED", pattern=[0.6, 0.5, -0.1])
        doc.layers.add("Cut", linetype="DASHED")
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "Cut"})

    assert counts(preview(make(tmp_path, build))) == {"dash": 1}


def test_text_pictures_and_dimensions_are_skipped_and_counted(tmp_path):
    def build(doc, msp):
        square(msp)
        msp.add_text("Hello")
        msp.add_mtext("World")
        image = doc.add_image_def(filename="photo.png", size_in_pixel=(10, 10))
        msp.add_image(image, insert=(0, 0), size_in_units=(5, 5))
        msp.add_linear_dim(base=(0, -5), p1=(0, 0), p2=(20, 0)).render()
        msp.add_point((3, 3))

    result = preview(make(tmp_path, build))
    assert kinds(result) == ["run"]
    assert counts(result) == {"text": 2, "picture": 1, "dimension": 1, "other": 1}


def test_an_empty_dxf_says_there_is_nothing(tmp_path):
    result = preview(make(tmp_path, lambda doc, msp: None))
    assert result["shapes"] == [] and any(w["code"] == "art_empty" for w in result["warnings"])


def test_imported_dxf_shapes_render(tmp_path):
    def build(doc, msp):
        square(msp, side=30)
        msp.add_circle((15, 15), 8)
        msp.add_lwpolyline([(40, 0), (60, 30)], dxfattribs={"const_width": 3})

    result = preview(make(tmp_path, build), closed_as_fills=True)
    design = layout.render(layout_of(result))
    assert [i["id"] for i in design.items] == ["a0", "a1"] and len(design.pattern.stitches) > 100


# ---------------------------------------------------------------- hostile files


def _quickly(path, seconds=20.0, **options) -> str:
    started = time.perf_counter()
    message = refusal(path, **options)
    assert time.perf_counter() - started < seconds
    return message


def test_a_block_that_inserts_itself_is_refused(tmp_path):
    def build(doc, msp):
        block = doc.blocks.new("LOOP")
        block.add_line((0, 0), (1, 0))
        block.add_blockref("loop", (1, 0))  # block names ignore case
        msp.add_blockref("LOOP", (0, 0))

    assert "inserts itself" in _quickly(make(tmp_path, build))


def test_blocks_that_insert_each_other_are_refused(tmp_path):
    def build(doc, msp):
        a, b = doc.blocks.new("A"), doc.blocks.new("B")
        a.add_blockref("B", (0, 0))
        b.add_blockref("A", (0, 0))
        msp.add_blockref("A", (0, 0))

    assert "inserts itself" in _quickly(make(tmp_path, build))


def test_blocks_nested_too_deep_are_refused(tmp_path):
    def build(doc, msp):
        doc.blocks.new("L0").add_line((0, 0), (1, 0))
        for k in range(1, 30):
            doc.blocks.new(f"L{k}").add_blockref(f"L{k - 1}", (0, 0))
        msp.add_blockref("L29", (0, 0))

    assert "more than 16 deep" in _quickly(make(tmp_path, build))


def test_a_huge_multi_insert_is_refused_before_it_is_built(tmp_path):
    def build(doc, msp):
        doc.blocks.new("DOT").add_circle((0, 0), 1)
        msp.add_blockref("DOT", (0, 0)).grid(size=(30_000, 30_000), spacing=(5, 5))

    assert "more than 50,000 objects" in _quickly(make(tmp_path, build), 5)


def test_a_multi_insert_with_no_spacing_is_one_copy_and_quick(tmp_path):
    def build(doc, msp):
        doc.blocks.new("DOT").add_circle((0, 0), 5)
        ref = msp.add_blockref("DOT", (0, 0))
        ref.dxf.row_count = ref.dxf.column_count = 30_000  # all in one place: ezdxf would count to 900 million

    path = make(tmp_path, build)
    started = time.perf_counter()
    assert len(preview(path)["shapes"]) == 1 and time.perf_counter() - started < 10


def test_blocks_that_multiply_out_are_refused(tmp_path):
    def build(doc, msp):
        doc.blocks.new("B0").add_line((0, 0), (1, 0))
        for k in range(1, 7):
            block = doc.blocks.new(f"B{k}")
            for i in range(10):
                block.add_blockref(f"B{k - 1}", (i, 0))
        msp.add_blockref("B6", (0, 0))

    assert "more than 50,000 objects" in _quickly(make(tmp_path, build))


def test_xrefs_and_pictures_are_not_opened(tmp_path):
    secret = tmp_path / "secret.dxf"
    secret.write_text(minimal(*line_tags()), encoding="utf-8")

    def build(doc, msp):
        square(msp)
        xref = doc.blocks.new("XR", dxfattribs={"flags": 4})
        xref.block.dxf.xref_path = str(secret)
        msp.add_blockref("XR", (0, 0))
        image = doc.add_image_def(filename=str(secret), size_in_pixel=(4, 4))
        msp.add_image(image, insert=(0, 0), size_in_units=(5, 5))

    result = preview(make(tmp_path, build))
    assert kinds(result) == ["run"] and counts(result) == {"xref": 1, "picture": 1}


@pytest.mark.parametrize("value", ["nan", "inf", "1e400", "1e15"])
def test_nan_and_absurd_coordinates_are_refused(tmp_path, value):
    path = write(tmp_path, minimal(*line_tags(x2=value)), "bad.dxf")
    assert "far outside any real drawing" in _quickly(path, 5)


def test_an_absurd_spline_is_refused_before_it_is_flattened(tmp_path):
    path = make(tmp_path, lambda doc, msp: msp.add_spline([(0, 0), (1e14, 1e14), (2e14, 0), (3e14, 1e14)]))
    assert "far outside any real drawing" in _quickly(path, 10)


def test_a_huge_drawing_asks_for_a_width(tmp_path):
    path = make(tmp_path, lambda doc, msp: msp.add_circle((0, 0), 5e5))
    assert "far bigger than any hoop" in _quickly(path, 5)
    assert preview(path, width_mm=80)["size_mm"] == [80.0, 80.0]


def test_a_spline_of_absurd_degree_is_left_out(tmp_path):
    def build(doc, msp):
        square(msp)
        spline = msp.add_spline([(0, 0), (1, 1), (2, 0)])
        spline.dxf.degree = 500

    result = preview(make(tmp_path, build))
    assert kinds(result) == ["run"] and counts(result) == {"damaged": 1}


def test_too_many_points_are_refused(tmp_path):
    points = [(i % 500 * 0.2, i // 500 * 0.2) for i in range(300_001)]
    path = make(tmp_path, lambda doc, msp: msp.add_lwpolyline(points))
    assert "more points than LUDD imports" in _quickly(path, 60)


@pytest.mark.parametrize("cut", [0.5, 0.9])
def test_a_truncated_dxf_is_refused(tmp_path, cut):
    path = make(tmp_path, lambda doc, msp: square(msp))
    data = path.read_bytes()
    path.write_bytes(data[: int(len(data) * cut)])
    assert "cut off or damaged" in _quickly(path)


def test_other_files_called_dxf_are_refused(tmp_path):
    assert "DWG" in _quickly(write(tmp_path, b"AC1032\x00\x00EOF", "drawing.dxf"))
    message = _quickly(write(tmp_path, b"this is not a drawing\nEOF\n", "junk.dxf"))
    assert "couldn't read this DXF" in message


def test_a_dxf_over_50_mb_is_refused(tmp_path):
    path = tmp_path / "big.dxf"
    with open(path, "wb") as fh:
        fh.truncate(50 * 1024 * 1024 + 1)
    assert "bigger than 50 MB" in refusal(path)


def test_nothing_is_added_by_a_refusal(tmp_path):
    answer = ask(write(tmp_path, b"junk\nEOF", "junk.dxf"))
    assert set(answer) == {"jsonrpc", "id", "error"}
