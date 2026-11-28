"""Artwork import (P7-D2): the vector paths on a PDF page, through art.preview. Each PDF is
written by the test, byte by byte."""

import math
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from shapely.geometry import LineString

from artimport_util import area_of, bounds, close, kinds, layout_of, line_of, preview, refusal, write
from threadline_engine import artimport, layout

MM = 72 / 25.4  # PDF units (points) in a millimeter


def build_pdf(objects: list[str], trailer: str = "") -> bytes:
    """A PDF of these objects (1, 2, 3 ...; the first is the catalog), with its table of offsets."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    table = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R {trailer} >>\nstartxref\n{table}\n%%EOF\n".encode()
    return bytes(out)


def stream(content: str, entries: str = "") -> str:
    return f"<< {entries} /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream"


def document(*contents: str, size=(200, 100), rotate=0, resources: str = "", extra: tuple = (),
             trailer: str = "") -> bytes:
    """One page per content stream. `extra` objects are numbered after the pages' (see first_extra)."""
    n = len(contents)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {n} >>"]
    for i, content in enumerate(contents):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] /Rotate {rotate} "
                       f"/Contents {4 + 2 * i} 0 R /Resources << {resources} >> >>")
        objects.append(stream(content))
    return build_pdf([*objects, *extra], trailer)


def first_extra(pages: int = 1) -> int:
    return 3 + 2 * pages


def pdf_file(tmp_path, data: bytes, name: str = "art.pdf"):
    return write(tmp_path, data, name)


def counts(result) -> dict:
    return {s["what"]: s["count"] for s in result["skipped"]}


# A red rectangle 72 x 36 points, and above it a blue 3 mm line 144 points long.
PROOF = f"1 0 0 rg 20 20 72 36 re f\n0 0 1 RG {3 * MM:.4f} w 20 80 m 164 80 l S"


def test_pdf_vector_paths(tmp_path):
    """P7-D2's success test: a filled path and a stroked path come in as two shapes of the right
    size, as an SVG's do."""
    result = preview(pdf_file(tmp_path, document(PROOF)))
    assert [(s["kind"], s["color"]) for s in result["shapes"]] == [("fill", "#ff0000"), ("satin", "#0000ff")]
    fill, line = result["shapes"]
    x0, y0, x1, y1 = bounds(fill)
    assert (x1 - x0, y1 - y0) == pytest.approx((25.4, 12.7), abs=0.01)
    assert line["geometry"]["width_mm"] == 3.0
    assert line_of(line).length == pytest.approx(50.8, abs=0.01)
    assert y0 > line_of(line).bounds[3]  # PDF's y points up: the rectangle is below the line
    assert close(result["size_mm"], (50.8, (84.25197 - 20) / MM), 0.02)
    assert result["scale_note"] is None and result["pages"] == 1
    design = layout.render(layout_of(result))
    assert len(design.items) == 2


def test_pdf_fill_rules_and_curves(tmp_path):
    nested = "10 10 60 60 re 25 25 30 30 re"
    both = preview(pdf_file(tmp_path, document(nested + " f")))  # nonzero: re draws both the same way round
    assert len(both["shapes"]) == 1 and "holes" not in both["shapes"][0]["geometry"]
    holed = preview(pdf_file(tmp_path, document(nested + " f*")))
    assert len(holed["shapes"][0]["geometry"]["holes"]) == 1
    k = 0.5523 * 36
    circle = (f"136 50 m 136 {50 + k} {100 + k} 86 100 86 c {100 - k} 86 64 {50 + k} 64 50 c "
              f"64 {50 - k} {100 - k} 14 100 14 c {100 + k} 14 136 {50 - k} 136 50 c h f")
    [round_one] = preview(pdf_file(tmp_path, document(circle)))["shapes"]
    assert area_of(round_one).area == pytest.approx(math.pi * (36 / MM) ** 2, rel=0.01)


def test_pdf_transforms_scale_strokes_and_forms_are_opened_once(tmp_path):
    form = first_extra()
    inner = form + 1
    forms = (
        stream(f"0 1 0 rg 0 0 10 10 re f /Inner Do", f"/Type /XObject /Subtype /Form /BBox [0 0 100 100] "
               f"/Matrix [2 0 0 2 0 0] /Resources << /XObject << /Inner {inner} 0 R >> >>"),
        stream("0 0 0 rg 50 50 10 10 re f", "/Type /XObject /Subtype /Form /BBox [0 0 100 100]"),
    )
    content = (f"q 2 0 0 2 0 0 cm {1.5 * MM:.4f} w 5 40 m 60 40 l S Q\n"
               f"q 1 0 0 1 100 10 cm /Outer Do Q")
    result = preview(pdf_file(tmp_path, document(content, resources=f"/XObject << /Outer {form} 0 R >>",
                                                 extra=forms)))
    line, tile = result["shapes"]
    assert line["geometry"]["width_mm"] == 3.0  # the width grows with the page's transform
    assert line_of(line).length == pytest.approx(110 / MM, abs=0.01)
    assert tile["color"] == "#00ff00"
    x0, y0, x1, y1 = bounds(tile)
    assert (x1 - x0, y1 - y0) == pytest.approx((20 / MM, 20 / MM), abs=0.01)  # the form's own matrix
    lx = line_of(line).bounds
    assert x0 - lx[0] == pytest.approx((100 - 10) / MM, abs=0.02)  # where the form was placed
    assert counts(result) == {"nested_form": 1}


@pytest.mark.parametrize("rotate, wide, tall", [(0, 60, 20), (90, 20, 60), (180, 60, 20), (270, 20, 60)])
def test_pdf_page_rotation(tmp_path, rotate, wide, tall):
    content = f"0 0 0 rg 10 10 {60 * MM:.4f} {5 * MM:.4f} re f 10 10 {5 * MM:.4f} {20 * MM:.4f} re f"  # an L
    result = preview(pdf_file(tmp_path, document(content, rotate=rotate)))
    assert close(result["size_mm"], (wide, tall), 0.02)
    corner = [bounds(s) for s in result["shapes"]]
    upright = corner[1]  # the upright of the L, where it ends up as the page is shown
    ends = {0: upright[0] < 0 and upright[1] < 0, 90: upright[1] < 0 and upright[0] < 0,
            180: upright[2] > 0 and upright[3] > 0, 270: upright[3] > 0 and upright[2] > 0}
    assert ends[rotate], corner


def test_pdf_colors_dashes_and_what_is_left_out(tmp_path):
    image = first_extra()
    shading = image + 1
    objects = (
        stream("\x00\x00\x00", "/Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB "
                               "/BitsPerComponent 8"),
        "<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [0 0 10 0] /Function << /FunctionType 2 /Domain [0 1] "
        "/C0 [1 0 0] /C1 [0 0 1] /N 1 >> >>",
    )
    content = ("0.5 g 10 10 20 20 re f\n0 1 1 0 k 40 10 20 20 re f\n"
               "[4 2] 0 d 0 0 0 RG 0.5 w 10 60 m 90 60 l S [] 0 d\n"
               "q 10 0 0 10 120 20 cm /Im Do Q\nq 150 20 20 20 re W n /Sh sh Q\n"
               "BT /F1 12 Tf 10 80 Td (Hello) Tj ET\n100 80 m 120 90 l n")
    resources = (f"/XObject << /Im {image} 0 R >> /Shading << /Sh {shading} 0 R >> "
                 "/Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >>")
    result = preview(pdf_file(tmp_path, document(content, resources=resources, extra=objects)))
    assert [s["color"] for s in result["shapes"]][:1] == ["#808080"]
    assert result["shapes"][1]["color"].startswith("#e") or result["shapes"][1]["color"].startswith("#f")  # CMYK red
    assert kinds(result) == ["fill", "fill", "run"]  # the path painted by neither fill nor stroke is nothing
    assert counts(result) == {"picture": 1, "text": 1, "shading": 1, "dash": 1}


def test_pdf_clips_that_cut_a_shape_are_counted(tmp_path):
    """Many programs clip every page to a box that holds everything: only a clip that cuts counts."""
    form = first_extra()
    objects = (stream("0 0 50 50 re f", "/Type /XObject /Subtype /Form /BBox [0 0 30 30]"),)  # cut by its BBox
    content = ("q 0 0 200 100 re W n 10 10 20 20 re f Q\n"  # a box round the whole page: nothing cut
               "q 60 20 20 20 re W n 60 20 40 40 re f Q\n"  # a smaller box: cut
               "q 120 50 m 150 90 l 180 50 l h W n 110 40 80 55 re f Q\n"  # a triangle: cut
               "q 1 0 0 1 20 50 cm /F Do Q")
    result = preview(pdf_file(tmp_path, document(content, resources=f"/XObject << /F {form} 0 R >>", extra=objects)))
    assert len(result["shapes"]) == 4  # the shapes come in whole
    assert counts(result) == {"clip": 3}


def test_pdf_pages(tmp_path):
    two = document("1 0 0 rg 10 10 72 72 re f", "0 0 1 rg 10 10 36 36 re f")
    path = pdf_file(tmp_path, two)
    first, second = preview(path), preview(path, page=1)
    assert (first["pages"], second["pages"]) == (2, 2)
    assert first["shapes"][0]["color"] == "#ff0000" and second["shapes"][0]["color"] == "#0000ff"
    assert second["size_mm"] == [12.7, 12.7]
    assert "has 2 pages" in refusal(path, page=2)
    assert "whole number" in refusal(path, page=-1)


def test_a_page_of_pictures_says_there_is_nothing_to_sew(tmp_path):
    image = first_extra()
    objects = (stream("\x00\x00\x00", "/Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB "
                                      "/BitsPerComponent 8"),)
    result = preview(pdf_file(tmp_path, document("q 200 0 0 100 0 0 cm /Im Do Q",
                                                 resources=f"/XObject << /Im {image} 0 R >>", extra=objects)))
    assert result["shapes"] == [] and counts(result) == {"picture": 1}
    assert any(w["code"] == "art_empty" for w in result["warnings"])


# ---------------------------------------------------------------- hostile files


def _quickly(path, seconds=20.0, **options) -> str:
    started = time.perf_counter()
    message = refusal(path, **options)
    assert time.perf_counter() - started < seconds
    return message


def test_a_locked_pdf_is_refused(tmp_path):
    lock = "<< /Filter /Standard /V 1 /R 2 /O <" + "11" * 32 + "> /U <" + "22" * 32 + "> /P -4 >>"
    data = document(PROOF, extra=(lock,), trailer=f"/Encrypt {first_extra()} 0 R /ID [<{'ab' * 16}> <{'ab' * 16}>]")
    message = _quickly(pdf_file(tmp_path, data))
    assert "password" in message and "without the password" in message


@pytest.mark.parametrize("cut", [30, 0.5, 0.95])
def test_a_truncated_pdf_is_refused(tmp_path, cut):
    data = document(PROOF)
    data = data[:cut] if isinstance(cut, int) else data[: int(len(data) * cut)]
    assert "cut off or damaged" in _quickly(pdf_file(tmp_path, data))


def test_broken_and_false_pdfs_are_refused(tmp_path):
    assert "isn't a PDF" in _quickly(pdf_file(tmp_path, b"<svg/>"))
    assert "may be damaged" in _quickly(pdf_file(tmp_path, b"%PDF-1.7\n" + b"\x00" * 500 + b"\n%%EOF\n"))


def test_a_pdf_over_50_mb_is_refused(tmp_path):
    path = tmp_path / "big.pdf"
    with open(path, "wb") as fh:
        fh.truncate(50 * 1024 * 1024 + 1)
    assert "bigger than 50 MB" in refusal(path)


def test_a_huge_page_is_not_rendered(tmp_path):
    """The page's size doesn't matter: nothing is drawn as pixels, only the paths are read."""
    data = document("1 0 0 rg 100000 100000 72 72 re f", size=(1_000_000, 1_000_000))
    started = time.perf_counter()
    result = preview(pdf_file(tmp_path, data))
    assert result["size_mm"] == [25.4, 25.4] and time.perf_counter() - started < 10


def test_a_path_across_a_huge_page_asks_for_a_width(tmp_path):
    data = document("0 0 0 RG 0 0 m 1000000 0 l S", size=(1_000_000, 100))
    assert "far bigger than any hoop" in _quickly(pdf_file(tmp_path, data))
    assert preview(pdf_file(tmp_path, data), width_mm=100)["size_mm"][0] == 100.0


def test_absurd_pdf_coordinates_are_refused(tmp_path):
    scale = "1000000 0 0 1000000 0 0 cm "  # twice: a million million times
    data = document(f"{scale}{scale}0 0 0 RG 0 0 m 1 0 l S")
    assert "far outside any real drawing" in _quickly(pdf_file(tmp_path, data), 5)


def test_only_the_asked_page_of_many_is_read(tmp_path):
    pages = ["0 0 0 rg 10 10 50 50 re f"] + ["0 0 m 10 10 l S " * 200] * 799
    path = pdf_file(tmp_path, document(*pages))
    started = time.perf_counter()
    result = preview(path)
    assert result["pages"] == 800 and len(result["shapes"]) == 1 and time.perf_counter() - started < 10


def test_too_many_points_on_a_page_are_refused(tmp_path):
    content = "0 0 m " + "1 1 l 2 0 l " * 160_000 + "S"
    assert "more points than LUDD imports" in _quickly(pdf_file(tmp_path, document(content)), 30)


def test_too_many_objects_on_a_page_are_refused(tmp_path):
    content = "0 0 m 10 10 l S\n" * 50_001
    assert "more than 50,000 objects" in _quickly(pdf_file(tmp_path, document(content)), 30)


def test_previews_at_once_each_get_their_own_answer(tmp_path):
    """PDFium isn't thread-safe, so each PDF is read in a process of its own: previews running at
    once each get their own right answer. (Through the dispatcher a newer one would replace an
    older: test_artimport_newest.py.)"""
    paths = []
    for i in range(6):
        side = 36 * (i + 1)
        paths.append((pdf_file(tmp_path, document(f"1 0 0 rg 10 10 {side} {side} re f\n" + "0 0 m 5 5 l S\n" * 300,
                                                  size=(500, 500)), f"{i}.pdf"), side / MM))
    answers: dict[int, dict] = {}

    def run(i, path):
        answers[i] = artimport.preview(str(path))

    threads = [threading.Thread(target=run, args=(i, p)) for i, (p, _) in enumerate(paths)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    for i, (_, side) in enumerate(paths):
        result = answers[i]
        fill = [s for s in result["shapes"] if s["kind"] == "fill"][0]
        x0, y0, x1, y1 = bounds(fill)
        assert (x1 - x0, y1 - y0) == pytest.approx((side, side), abs=0.02)


def test_pdfium_is_never_loaded_in_the_engine(tmp_path):
    """Every PDFium call (which can't be stopped, and which a bad file can make crash or fill the
    memory) happens in a one-use child process: the engine never even loads the library."""
    form = first_extra()
    data = document(PROOF + " q /F Do Q", resources=f"/XObject << /F {form} 0 R >>",
                    extra=(stream("0 0 m 9 9 l S", "/Type /XObject /Subtype /Form /BBox [0 0 10 10]"),))
    path = pdf_file(tmp_path, data)
    code = ("import sys; from threadline_engine import artimport; "
            "print(len(artimport.preview(sys.argv[1])['shapes']), "
            "sorted(m for m in sys.modules if m.startswith('pypdfium2')))")
    engine = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=120,
                          cwd=engine)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.split() == ["3", "[]"], done.stdout  # the proof's two shapes and the form's line
