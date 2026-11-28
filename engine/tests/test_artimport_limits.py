"""Artwork import keeps its limits: the hostile samples of the Phase 7 audit (and a few more), each
written here and only as big as its rule needs. Each is refused in plain words, or read safely,
quickly; the refusals come from rules about the file (counts and sizes), never from the clock."""

import math
import time
import zlib

import pytest

from artimport_util import kinds, preview, refusal, svg, write
from test_artimport_dxf import make, minimal
from test_artimport_pdf import PROOF, build_pdf, document, stream
from threadline_engine.artimport import Deadline, child, dxf, pdf, svg as art_svg, svgclean

SQUARE = '<rect x="10" y="10" width="20" height="20" fill="#ff0000"/>'


def _star(n: int, r: float = 40.0) -> list[tuple[float, float]]:
    """A star of n points whose edges cross about n times n/2 times."""
    k = n // 2 - 1
    return [(50 + r * math.cos(2 * math.pi * (i * k % n) / n), 50 + r * math.sin(2 * math.pi * (i * k % n) / n))
            for i in range(n)]


def _points(pts) -> str:
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in pts)


def _grid_path(k: int, size: float = 90.0) -> str:
    """k bars across and k down, all in one path and all drawn the same way round: each pair of
    bars crosses four times."""
    out = []
    for i in range(k):
        t = 5 + size * i / k
        out.append(f"M5 {t:.3f}h{size}v0.05h-{size}z")
        out.append(f"M{t:.3f} 5h0.05v{size}h-0.05z")
    return "".join(out)


def _squares_path(n: int) -> str:
    """n squares one inside the next, in one path."""
    return "".join(f"M{50 - s:.4f} {50 - s:.4f}H{50 + s:.4f}V{50 + s:.4f}H{50 - s:.4f}Z"
                   for s in (1 + 40 * k / n for k in range(n)))


def _gradient(per_stop: int, stops: int = 49_700, shapes: int = 150) -> str:
    stop = '<stop offset="0" stop-opacity="0" style="' + "a:b;" * per_stop + '"/>'
    rects = "".join(f'<rect x="{i % 10}" y="{i // 10}" width="1" height="1" fill="url(#g)" stroke="url(#g)"/>'
                    for i in range(shapes))
    return svg(f'<defs><linearGradient id="g">{stop * stops}</linearGradient></defs>{rects}')


def _quickly(seconds: float, action):
    started = time.perf_counter()
    out = action()
    assert time.perf_counter() - started < seconds
    return out


# A guard against a blow-up, not a speed test: each refusal here is by a rule (its words name the
# rule), takes at most a few seconds on the computer the tests were written on, and this leaves ten
# times that for slower, busier ones. (Past 60 s the import's own time limit refuses with its
# "takes too long" words, which none of these accept.)
GUARD_S = 60.0


def _refused(tmp_path, data, name: str, fragment: str, seconds: float = GUARD_S, **options) -> str:
    path = write(tmp_path, data, name)
    message = _quickly(seconds, lambda: refusal(path, **options))
    assert fragment in message, message
    return message


# ---------------------------------------------------------------- SVG: closing, tangles, crowds

CLOSED = "closed too many times over"
TANGLED = "crosses or touches itself more than 20,000 times"
CROWDED = "outlines inside or on top of one another"


@pytest.mark.parametrize("zs", [2_100, 10_000, 40_000], ids=["just over", "10,000", "40,000"])
def test_a_path_closed_thousands_of_times_is_refused(tmp_path, zs):
    """"z" takes svgelements a walk back to the last "M": 40,000 of them took 148 s."""
    path = '<path d="M10 10 L20 10 L20 20 ' + "z" * zs + '" fill="red"/>'
    _refused(tmp_path, svg(path), "z.svg", CLOSED, 5)


def test_closed_paths_copied_by_use_count_every_copy(tmp_path):
    """Each copy is read again: a path just inside the limit, copied five times, is over it."""
    once = '<path id="p" d="M0 0 L9 0 L9 9 ' + "z" * 1_000 + '" fill="red"/>'
    assert kinds(preview(write(tmp_path, svg(once)))) == ["fill"]
    _refused(tmp_path, svg(f"<defs>{once}</defs>" + '<use href="#p"/>' * 5), "copies.svg", CLOSED, 5)


def test_ordinary_closed_paths_come_in(tmp_path):
    squares = "".join(f"M{i % 90} {i // 90}h0.8v0.8h-0.8z" for i in range(1_500))
    long_one = "M0 60" + " l0.004 0" * 20_000 + " l0 1 z"
    result = preview(write(tmp_path, svg(f'<path d="{squares}" fill="red"/><path d="{long_one}" fill="blue"/>')))
    assert {s["color"] for s in result["shapes"]} <= {"#ff0000", "#0000ff"}


def test_a_gradient_is_read_once_however_often_it_is_used(tmp_path, monkeypatch):
    """A few thousand shapes painting with a gradient of thousands of stops (or with gradients that
    borrow its stops) used to read every stop for every shape: minutes."""
    seen_through = '<stop offset="0" stop-opacity="0"/>' * 2_000
    big = f'<linearGradient id="big">{seen_through}<stop offset="1" stop-color="#00ff00"/></linearGradient>'
    borrowers = "".join(f'<linearGradient id="b{i}" href="#big"/>' for i in range(40))
    shapes = "".join(f'<rect x="{i * 2}" width="1.5" height="30" fill="url(#b{i})" stroke="url(#big)"/>'
                     for i in range(40))
    calls = []
    real = svgclean._cascade
    monkeypatch.setattr(svgclean, "_cascade", lambda *a: calls.append(1) or real(*a))
    result = preview(write(tmp_path, svg(f"<defs>{big}{borrowers}</defs>{shapes}")))
    assert {s["color"] for s in result["shapes"]} == {"#00ff00"}
    assert len(calls) <= 2 * 2_001  # each stop looked up once: its opacity and its color


@pytest.mark.parametrize("per_stop", [20, 24])
def test_the_audit_gradient_samples_are_read_quickly(tmp_path, per_stop):
    path = write(tmp_path, _gradient(per_stop))
    result = _quickly(90, lambda: preview(path))  # about 7 s here: a guard, with the same room
    assert result["shapes"] == [] and {s["what"]: s["count"] for s in result["skipped"]} == {"gradient": 300}


def test_a_gradient_with_very_long_styles_is_still_refused(tmp_path):
    _refused(tmp_path, _gradient(640, stops=2_000), "g.svg", "more styles and transforms")


def test_the_time_limit_is_looked_at_for_every_element_and_paint(tmp_path, monkeypatch):
    class Counting(Deadline):
        checks = 0

        def check(self):
            self.checks += 1
            super().check()

    deadline = Counting()
    at = []
    real = art_svg._paint
    monkeypatch.setattr(art_svg, "_paint", lambda *a: at.append(deadline.checks) or real(*a))
    rects = "".join(f'<rect x="{i}" width="1" height="5" fill="red" stroke="blue"/>' for i in range(60))
    art_svg.read(svg(rects).encode(), deadline)
    assert len(at) == 120 and all(b > a for a, b in zip(at, at[1:]))  # between every two paints


@pytest.mark.parametrize("n", [221, 501], ids=["just over", "501"])
def test_a_star_that_crosses_itself_thousands_of_times_is_refused(tmp_path, n):
    """GEOS cutting one up took minutes (a 2,001-point star 55 s, 3,001 points over 8 GB)."""
    _refused(tmp_path, svg(f'<polygon points="{_points(_star(n))}" fill="red"/>'), "star.svg", TANGLED)


def test_a_grid_of_crossing_bars_is_refused(tmp_path):
    _refused(tmp_path, svg(f'<path d="{_grid_path(75)}" fill="red"/>'), "grid.svg", TANGLED, 10)


def test_a_wide_stroke_along_a_tangled_line_is_refused(tmp_path):
    line = f'<polyline points="{_points(_star(221))}" fill="none" stroke="red" stroke-width="20"/>'
    _refused(tmp_path, svg(line), "wide.svg", TANGLED, 10)


@pytest.mark.parametrize("what", ["star", "grid"])
def test_shapes_that_cross_a_few_thousand_times_still_come_in(tmp_path, what):
    """Under the limit: a 101-point star (about 5,000 crossings) and a grid of 50 bars each way
    (10,000) are read as before."""
    body = (f'<polygon points="{_points(_star(101))}" fill="red" fill-rule="evenodd"/>' if what == "star"
            else f'<path d="{_grid_path(50, 60)}" fill="red"/>')
    path = write(tmp_path, svg(body, 'width="100mm" height="100mm" viewBox="0 0 100 100"'))
    assert preview(path, width_mm=300)["shapes"]


def test_thousands_of_outlines_one_inside_another_are_refused(tmp_path):
    """Working out which holds which compares them in pairs: 4,000 squares took 68 s."""
    _refused(tmp_path, svg(f'<path d="{_squares_path(2_100)}" fill="red" fill-rule="evenodd"/>'), "nest.svg",
             CROWDED)


def test_many_separate_outlines_in_one_path_come_in(tmp_path):
    dots = "".join(f"M{(i % 100)} {i // 100}h0.8v0.8h-0.8z" for i in range(3_000))
    frame = "M-5 -5h110v50h-110z"
    result = preview(write(tmp_path, svg(f'<path d="{frame}{dots}" fill="red" fill-rule="evenodd"/>')),
                     width_mm=500)
    assert len(result["shapes"]) == 1 and len(result["shapes"][0]["geometry"]["holes"]) == 3_000


@pytest.mark.parametrize("size", ['width="5' + " " * 60_000 + 'mm?" height="5mm"',
                                  'width="100mm" height="5' + " " * 60_000 + '?"'],
                         ids=["width", "height"])
def test_a_size_followed_by_a_very_long_run_of_spaces_is_read_at_once(tmp_path, size):
    """The size pattern backtracked over every space: 60,000 took over 20 s, 19 MB would never end."""
    path = write(tmp_path, svg(SQUARE, size + ' viewBox="0 0 100 50"'))
    assert kinds(_quickly(5, lambda: preview(path))) == ["fill"]


def test_paint_that_names_an_address_is_read_by_hand(tmp_path):
    """The url(...) pattern took tens of seconds over a few thousand spaces, for every shape."""
    body = '<rect x="1" width="5" height="5" fill="url(' + " " * 3_990 + 'x"/>'
    path = write(tmp_path, svg(body * 3 + SQUARE))
    assert kinds(_quickly(5, lambda: preview(path))) == ["fill"]


def test_a_very_long_class_never_reaches_svgelements(tmp_path):
    """The second audit's sweep: svgelements takes every name in a class attribute through its styles
    for every copy of the shape, so a 4,000-character one copied 24,900 times kept its one call,
    which nothing can stop, busy for 24 s. A class over MAX_CLASS is left out (the drawing still
    comes in)."""
    long_class = "a " * 300  # 600 characters
    body = f'<defs><rect id="r" class="{long_class}" width="5" height="5" fill="red"/></defs><use href="#r"/>'
    assert long_class.strip().encode() not in svgclean.prepare(svg(body).encode()).data
    assert kinds(preview(write(tmp_path, svg(body)))) == ["fill"]
    short = body.replace(long_class, "a " * 200)  # 400 characters: kept
    assert ("a " * 200).strip().encode() in svgclean.prepare(svg(short).encode()).data


@pytest.mark.parametrize("raw, target, after", [
    ("url(#g)", "#g", ""), ("url( #g )  red", "#g", "red"), ("URL('#g') none", "#g", "none"),
    ('url("#g")', "#g", ""), ("url(http://example.invalid/a.svg#b) blue", "http://example.invalid/a.svg#b", "blue"),
    ("url(#g", "", ""), ("url('#g)", "", ""), ("url(#g') red", "", ""), ("url(a(b) red", "", ""),
    ("url('" + "x" * 2_001 + "') red", "", ""), ("url()", "", ""),
])
def test_url_paint_reads_as_it_did(raw, target, after):
    assert art_svg._url(raw) == (target, after)


def test_a_very_long_run_of_spaces_in_points_is_taken_out(tmp_path):
    """svgelements takes minutes over one (its pattern for pairs of numbers backtracks)."""
    points = "10,10\n\t 40,10" + " " * 50_000 + "40,40 " + "1" * 40 + " " * 50_000 + "x"
    prepared = svgclean.prepare(svg(f'<polygon points="{points}" fill="red"/>').encode())
    assert b"  " not in prepared.data.split(b'points="')[1].split(b'"')[0]
    path = write(tmp_path, svg('<polygon points="10,10\n\t 40,10   40,40" fill="red"/>'))
    assert [n[:2] for n in preview(path)["shapes"][0]["geometry"]["outline"]] == [[-15.0, -15.0], [15.0, -15.0],
                                                                                  [15.0, 15.0]]


# ---------------------------------------------------------------- the audit's other SVG and DXF samples


def _gen_dxf(entities: str = "", blocks: str = "") -> str:
    parts = [f"0\nSECTION\n2\nBLOCKS\n{blocks}0\nENDSEC\n"] if blocks else []
    return "".join(parts) + f"0\nSECTION\n2\nENTITIES\n{entities}0\nENDSEC\n0\nEOF\n"


def _line(x1=0, y1=0, x2=10, y2=10) -> str:
    return f"0\nLINE\n8\n0\n10\n{x1}\n20\n{y1}\n30\n0\n11\n{x2}\n21\n{y2}\n31\n0\n"


def _block(name: str, body: str, flags: int = 0) -> str:
    return f"0\nBLOCK\n8\n0\n2\n{name}\n70\n{flags}\n10\n0\n20\n0\n30\n0\n3\n{name}\n{body}0\nENDBLK\n8\n0\n"


def _insert(name: str, x: int = 0) -> str:
    return f"0\nINSERT\n8\n0\n2\n{name}\n10\n{x}\n20\n0\n30\n0\n"


def _blocks_10x10() -> str:
    blocks = _block("B0", _line())
    for i in range(1, 11):
        blocks += _block(f"B{i}", "".join(_insert(f"B{i - 1}", k) for k in range(10)))
    return _gen_dxf(_insert("B10"), blocks)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
SVG10 = svg('<rect width="10" height="10"/>')
HUGE = svg('<rect x="1e308" y="0" width="1e308" height="10"/>')
LEVELS = "".join(f'<g id="l{i}">' + "".join(f'<use href="#l{i - 1}" x="{k}"/>' for k in range(10)) + "</g>"
                 for i in range(1, 11))
ENTITY = '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]>' + svg("<text>&b;</text>")
_CUT = _gen_dxf(_line() + _line(10, 10, 20, 0) + "0\nLWPOLYLINE\n8\n0\n90\n3\n70\n1\n10\n0\n20\n0\n10\n10\n20\n0\n"
                "10\n10\n20\n10\n")
_CUT = _CUT[: len(_CUT) // 2]  # cut half way, between a group code and its value


@pytest.mark.parametrize("name, data, fragment", [
    ("svg_entity.svg", ENTITY, "XML entities"),
    ("svg_use_self.svg", svg('<g id="a"><rect width="10" height="10"/><use href="#a"/></g>'), "includes itself"),
    ("svg_use_self_direct.svg", svg('<use id="u" href="#u"/><rect width="10" height="10"/>'), "includes itself"),
    ("svg_use_10x10.svg", svg(f"<defs><rect id='l0' width='1' height='1'/>{LEVELS}</defs><use href='#l10'/>"),
     "multiplies out"),
    ("svg_deep_groups.svg", svg("<g>" * 65 + SQUARE + "</g>" * 65), "nested more than 64 deep"),
    ("svg_huge_1e308.svg", HUGE, "far outside any real drawing"),
    ("svg_viewbox_tiny.svg", svg('<rect width="10" height="10"/>', 'width="100mm" viewBox="0 0 1e-30 1e-30"'),
     "far outside any real drawing"),
    ("svg_gzip.svg", b"\x1f\x8b\x08\x00" + b"\x00" * 20, "compressed SVG"),
    ("png_as.svg", PNG, "damaged or cut off"),
    ("png_as.dxf", PNG, "cut off or damaged"),
    ("png_as.pdf", PNG, "isn't a PDF"),
    ("dxf_as.svg", _gen_dxf(_line()), "damaged or cut off"),
    ("pdf_as.svg", document(PROOF), "damaged or cut off"),
    ("svg_as.pdf", SVG10, "isn't a PDF"),
    ("svg_as.dxf", SVG10, "cut off or damaged"),
    ("pdf_as.dxf", document(PROOF), "couldn't read this DXF"),
    ("dxf_self_insert.dxf", _gen_dxf(_insert("A"), _block("A", _line() + _insert("A"))), "inserts itself"),
    ("dxf_blocks_10x10.dxf", _blocks_10x10(), "more than 50,000 objects"),
    ("dxf_huge.dxf", _gen_dxf(_line(x2="1e308")), "aren't numbers"),
    ("dxf_nan.dxf", _gen_dxf(_line(x2="nan") + _line()), "aren't numbers"),
    ("dxf_inf.dxf", _gen_dxf(_line(x2="inf") + _line()), "aren't numbers"),
    ("dxf_cut.dxf", _CUT, "cut off or damaged"),
    ("dxf_cut_with_eof.dxf", _CUT + "0\nEOF\n", "couldn't read this DXF"),
    ("dxf_binary_garbage.dxf", b"AutoCAD Binary DXF\r\n\x1a\x00" + bytes(range(256)) * 8 + b"EOF\x00",
     "couldn't read this DXF"),
    ("dxf_binary_cut.dxf", b"AutoCAD Binary DXF\r\n\x1a\x00\x00\x00SECTION\x00\x02\x00ENTITIES\x00\x00\x00LINE\x00"
     b"\x08\x00EOF", "couldn't read this DXF"),
])
def test_audit_sample_is_refused(tmp_path, name, data, fragment):
    _refused(tmp_path, data, name, fragment, closed_as_fills=name.endswith(".dxf"))


def test_audit_samples_that_are_read_safely(tmp_path):
    doctype = ('<?xml version="1.0"?><!DOCTYPE svg SYSTEM "file:///C:/Windows/win.ini">' + SVG10)
    assert kinds(preview(write(tmp_path, doctype, "d.svg"))) == ["fill"]
    nan = svg('<rect x="NaN" y="inf" width="10" height="Infinity"/><path d="M0 0 L NaN 5 L 10 10z"/>')
    assert preview(write(tmp_path, nan, "n.svg"))["shapes"] == []
    for size in ('width="0" height="0"', 'width="1e300mm" height="1e300mm" viewBox="0 0 1e-300 1e-300"'):
        assert kinds(preview(write(tmp_path, svg('<rect width="10" height="10"/>', size), "w.svg"))) == ["fill"]
    xref = _gen_dxf(_insert("X") + _line(), _block("X", "", flags=4))
    result = preview(write(tmp_path, xref, "x.dxf"))
    assert kinds(result) == ["run"] and {s["what"] for s in result["skipped"]} == {"xref"}


# ---------------------------------------------------------------- DXF: too much for ezdxf to read


def _never_read(monkeypatch):
    """ezdxf reading the whole file is the step that can't be stopped: it mustn't be reached."""
    from ezdxf import recover
    from ezdxf.document import Drawing

    def read(*_a, **_k):
        raise AssertionError("ezdxf started reading a file it should have refused first")

    dxf.load_ezdxf()
    monkeypatch.setattr(recover, "read", read)
    monkeypatch.setattr(Drawing, "load", classmethod(read))


@pytest.mark.parametrize("code, newline", [("0", "\n"), (" 000", "\r\n"), ("+0 ", "\n")],
                         ids=["as written", "padded, CRLF", "signed"])
def test_a_dxf_with_too_many_objects_is_refused_before_ezdxf_reads_it(tmp_path, monkeypatch, code, newline):
    """49 MB of lines took ezdxf 70 s. The records are counted as ezdxf reads them, however their
    codes are written."""
    one = f"{code}{newline}LINE{newline}8{newline}0{newline}10{newline}1{newline}20{newline}2{newline}"
    text = f"0{newline}SECTION{newline}2{newline}ENTITIES{newline}" + one * 100_001 + \
           f"0{newline}ENDSEC{newline}0{newline}EOF{newline}"
    _never_read(monkeypatch)
    _refused(tmp_path, text.encode(), "many.dxf", "more than 100,000 objects")


def test_objects_in_unused_blocks_count_too(tmp_path, monkeypatch):
    _never_read(monkeypatch)
    unused = _block("UNUSED", "0\nPOINT\n8\n0\n10\n1\n20\n1\n" * 100_001)
    _refused(tmp_path, _gen_dxf(_line(), unused), "blocks.dxf", "purge unused blocks")


def test_a_binary_dxf_with_too_many_objects_is_refused_too(tmp_path, monkeypatch):
    # An R12 line is a short record (9 pairs, with 1-byte codes), so 100,001 of them stay under the
    # limit on pairs and reach the one on objects.
    path = make(tmp_path, lambda doc, msp: msp.add_line((0, 0), (1, 1)), binary=True, name="bin.dxf", version="R12")
    data = path.read_bytes()
    start = data.index(b"\x00LINE\x00", data.index(b"ENTITIES"))
    end = data.index(b"\x00ENDSEC\x00", start)
    path.write_bytes(data[:start] + data[start:end] * 100_001 + data[end:])
    _never_read(monkeypatch)
    assert "more than 100,000 objects" in _quickly(GUARD_S, lambda: refusal(path))


def test_a_dxf_with_far_too_much_in_it_is_refused_by_its_length(tmp_path, monkeypatch):
    _never_read(monkeypatch)
    comments = "999\nx\n" * 3_000_001
    _refused(tmp_path, comments + _gen_dxf(_line()), "long.dxf", "far more in it")


_APPID = "0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nAPPID\n70\n1\n0\nAPPID\n2\nACAD\n70\n0\n0\nENDTAB\n0\nENDSEC\n"


def _one_line_with_extra_data(pieces: int) -> bytes:
    """A DXF with one LINE carrying `pieces` of extended data: one object, however much it holds."""
    return (_APPID + _gen_dxf(_line() + "1001\nACAD\n" + "1000\nx\n" * pieces)).encode()


def test_one_object_carrying_too_much_is_refused_by_the_count_before_the_read(tmp_path, monkeypatch):
    """The second Phase 7 audit: one LINE with 2.95 million pieces of extended data was let through,
    and ezdxf's one read of it took over half a minute, which nothing can stop. Over a million pairs
    of lines is refused by the count."""
    _never_read(monkeypatch)
    path = write(tmp_path, _one_line_with_extra_data(1_000_000), "extra.dxf")
    assert "far more in it than LUDD imports" in refusal(path)
    # Just under a million is counted through and read (the count alone is checked here: the read
    # itself takes seconds).
    dxf.load_ezdxf()
    assert dxf._check_size(_one_line_with_extra_data(999_000), Deadline()) is None


def _old_polyline(vertices: int, layer: str = "8\n0\n") -> str:
    """`layer`: each vertex's own layer pair ("" for the shortest record LUDD can be given)."""
    corners = "".join(f"0\nVERTEX\n{layer}10\n{i % 500 * 0.2}\n20\n{i // 500 * 0.3}\n" for i in range(vertices))
    return _gen_dxf(f"0\nPOLYLINE\n8\n0\n66\n1\n70\n0\n{corners}0\nSEQEND\n8\n0\n")


def test_old_style_polylines_are_counted_by_their_points(tmp_path, monkeypatch):
    """Each vertex of an old-style (R12) polyline is a record of its own, so they are counted apart:
    a drawing with more than 100,000 of them (within LUDD's 300,000 points) gets past the count
    (reading it all takes a while), and one with more than 300,000 is refused before ezdxf. (Only
    records of three pairs reach that many within the limit on pairs.)"""
    assert kinds(preview(write(tmp_path, _old_polyline(50), "old.dxf"))) == ["run"]
    dxf.load_ezdxf()
    dxf._check_size(_old_polyline(100_500).encode(), Deadline())
    _never_read(monkeypatch)
    _refused(tmp_path, _old_polyline(300_001, layer=""), "older.dxf", "more points than LUDD imports")


def test_a_dxf_closed_outline_that_crosses_itself_thousands_of_times_is_refused(tmp_path):
    path = make(tmp_path, lambda doc, msp: msp.add_lwpolyline(_star(221), close=True), name="star.dxf")
    assert TANGLED in _quickly(10, lambda: refusal(path, closed_as_fills=True))
    assert kinds(preview(path)) == ["run"]  # as a line it needs no cutting up


def test_thousands_of_dxf_outlines_one_inside_another_are_refused(tmp_path):
    def build(doc, msp):
        for k in range(2_100):
            s = 1 + 40 * k / 2_100
            msp.add_lwpolyline([(-s, -s), (s, -s), (s, s), (-s, s)], close=True)

    path = make(tmp_path, build, name="nest.dxf")
    assert CROWDED in _quickly(GUARD_S, lambda: refusal(path, closed_as_fills=True))


# ---------------------------------------------------------------- PDF


def _pages(n: int) -> bytes:
    kids = " ".join(f"{4 + i} 0 R" for i in range(n))
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{kids}] /Count {n} >>",
               stream("1 0 0 rg 20 20 72 36 re f")]
    return build_pdf(objects + ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 3 0 R >>"] * n)


def _lying_page_tree() -> bytes:
    return build_pdf(["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R 2 0 R] /Count 1000000 >>",
                      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 4 0 R >>",
                      stream("0 0 10 10 re f")])


@pytest.mark.parametrize("data", [_pages(2_001), _lying_page_tree()], ids=["2,001 pages", "claims a million"])
def test_a_pdf_with_more_than_2000_pages_is_refused(tmp_path, data):
    _refused(tmp_path, data, "pages.pdf", "more than 2,000 pages")


def test_a_pdf_with_2000_pages_comes_in(tmp_path):
    assert preview(write(tmp_path, _pages(pdf.MAX_PAGES), "p.pdf"))["pages"] == 2_000


def _flate_page(megabytes: int) -> bytes:
    """A page whose compressed content unpacks to millions of tiny paths."""
    tiny = b"0 0 m 1 1 l S\n"
    packed = zlib.compress(tiny * (megabytes * 1024 * 1024 // len(tiny)), 9)
    body = (f"<< /Filter /FlateDecode /Length {len(packed)} >>\nstream\n").encode() + packed + b"\nendstream"
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 4 0 R >>"]
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for number, item in enumerate([*(o.encode() for o in objects), body], start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + item + b"\nendobj\n"
    table = len(out)
    out += f"xref\n0 5\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    return bytes(out + f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{table}\n%%EOF\n".encode())


def test_a_compressed_page_that_unpacks_to_gigabytes_is_refused_by_memory(tmp_path, monkeypatch):
    """200 MB unpacked took over 4 GB. The child's limit is 2 GB; a smaller one here."""
    monkeypatch.setattr(child, "CHILD_MEMORY", 300 * 1024**2)
    _refused(tmp_path, _flate_page(20), "flate.pdf", "takes more memory to read")


@pytest.mark.parametrize("name, data", [
    ("pdf_garbage_xref.pdf", document(PROOF).replace(b"xref", b"xrxf").replace(b"0000000", b"9999999")),
    ("pdf_huge_mediabox.pdf", build_pdf(["<< /Type /Catalog /Pages 2 0 R >>",
                                         "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                                         "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1e38 1e38] /Contents 4 0 R >>",
                                         stream("1 0 0 rg 20 20 72 36 re f")])),
    ("pdf_form_self.pdf", build_pdf(["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                                     "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 4 0 R "
                                     "/Resources << /XObject << /F 5 0 R >> >> >>", stream("/F Do"),
                                     stream("1 0 0 rg 0 0 10 10 re f /F Do",
                                            "/Type /XObject /Subtype /Form /BBox [0 0 200 100] "
                                            "/Resources << /XObject << /F 5 0 R >> >>")])),
])
def test_audit_pdfs_that_are_read_safely(tmp_path, name, data):
    # About 1 s here, with a child process to start: on a heavily loaded computer that start alone
    # can take many seconds, so the guard has the same room as the refusals'.
    result = _quickly(GUARD_S, lambda: preview(write(tmp_path, data, name)))
    assert result["shapes"] and result["pages"] == 1


def test_a_pdf_star_that_crosses_itself_thousands_of_times_is_refused(tmp_path):
    pts = _star(221)
    content = f"1 0 0 rg {pts[0][0]:.3f} {pts[0][1]:.3f} m " + " ".join(f"{x:.3f} {y:.3f} l" for x, y in pts[1:])
    _refused(tmp_path, document(content + " h f"), "star.pdf", TANGLED)


# ---------------------------------------------------------------- and the next import still works


def _ordinary(tmp_path) -> list:
    drawing = write(tmp_path, svg(SQUARE), "ok.svg")
    cad = write(tmp_path, minimal((0, "LINE"), (8, "0"), (10, 0), (20, 0), (11, 10), (21, 0)), "ok.dxf")
    page = write(tmp_path, document(PROOF), "ok.pdf")
    return [(drawing, ["fill"]), (cad, ["run"]), (page, ["fill", "satin"])]


#: One hostile file of each kind that is refused: (name, its bytes, part of the refusal).
REFUSALS = {
    "closed too often": ("z.svg", lambda: svg('<path d="M0 0 L9 0 ' + "z" * 2_100 + '"/>'), CLOSED),
    "tangled": ("star.svg", lambda: svg(f'<polygon points="{_points(_star(221))}"/>'), TANGLED),
    "crowded": ("nest.svg", lambda: svg(f'<path d="{_squares_path(2_100)}"/>'), CROWDED),
    "too many dxf objects": (
        "many.dxf", lambda: "0\nSECTION\n2\nENTITIES\n" + "0\nPOINT\n8\n0\n" * 100_001 + "0\nENDSEC\n0\nEOF\n",
        "more than 100,000 objects"),
    "too many pages": ("pages.pdf", _lying_page_tree, "more than 2,000 pages"),
    "too much memory": ("memory.pdf", lambda: _flate_page(20), "takes more memory"),
    "damaged": ("broken.pdf", lambda: b"%PDF-1.7\n" + b"\x00" * 100 + b"\n%%EOF\n", "damaged"),
}


@pytest.mark.parametrize("what", list(REFUSALS))
def test_an_import_still_works_after_each_kind_of_refusal(what, tmp_path, monkeypatch):
    ordinary = _ordinary(tmp_path)
    bad = tmp_path / "bad"
    bad.mkdir()
    name, data, fragment = REFUSALS[what]
    monkeypatch.setattr(child, "CHILD_MEMORY", 300 * 1024**2)
    assert fragment in refusal(write(bad, data(), name))
    for path, expected in ordinary:
        assert kinds(preview(path)) == expected, f"after {name}"
