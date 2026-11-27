"""Hostile SVG files (artwork is untrusted input): each is refused in plain words, or its bad part
left out, quickly, and nothing but the chosen file is ever opened."""

import time

import pytest

from artimport_util import kinds, preview, refusal, svg, write

SQUARE = '<rect x="10" y="10" width="20" height="20" fill="#ff0000"/>'


def _quickly(path, seconds: float = 20.0, **options) -> str:
    started = time.perf_counter()
    message = refusal(path, **options)
    assert time.perf_counter() - started < seconds
    return message


# ---------------------------------------------------------------- XML


BOMB = """<?xml version="1.0"?>
<!DOCTYPE svg [
  <!ENTITY a "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
  <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
  <!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;">
]>
<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><title>&e;</title><rect width="5" height="5"/></svg>
"""
EXTERNAL = """<?xml version="1.0"?>
<!DOCTYPE svg [ <!ENTITY secret SYSTEM "{url}"> ]>
<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><text>&secret;</text><rect width="5" height="5"/></svg>
"""
PARAMETER = """<?xml version="1.0"?>
<!DOCTYPE svg [ <!ENTITY % remote SYSTEM "http://example.invalid/evil.dtd"> %remote; ]>
<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><rect width="5" height="5"/></svg>
"""


@pytest.mark.parametrize("text", [
    BOMB, EXTERNAL.format(url="file:///etc/passwd"), EXTERNAL.format(url="http://example.invalid/x"), PARAMETER,
], ids=["bomb", "local file", "web address", "parameter entity"])
def test_entities_are_refused(tmp_path, text):
    message = _quickly(write(tmp_path, text))
    assert "entities" in message and "plain SVG" in message


@pytest.mark.parametrize("order", ["utf-16-le", "utf-16-be"])
def test_entities_in_other_encodings_are_refused_too(tmp_path, order):
    """A byte search for "<!ENTITY" would miss these; the XML parser can't."""
    text = BOMB.replace('version="1.0"', 'version="1.0" encoding="UTF-16"')
    data = (chr(0xFEFF) + text).encode(order)  # with its byte order mark
    assert b"ENTITY" not in data
    assert "entities" in _quickly(write(tmp_path, data))


def test_a_doctype_without_entities_is_fine_and_nothing_is_fetched(tmp_path):
    text = ('<?xml version="1.0"?><!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
            '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">' + svg(SQUARE))
    assert kinds(preview(write(tmp_path, text))) == ["fill"]


@pytest.mark.parametrize("cut", [20, 90, -8])
def test_a_truncated_file_is_refused(tmp_path, cut):
    message = _quickly(write(tmp_path, svg(SQUARE + SQUARE)[:cut]))
    assert "damaged or cut off" in message


def test_nonsense_is_refused(tmp_path):
    assert "damaged or cut off" in _quickly(write(tmp_path, b"\x00\x01\x02<<<>>>" * 100))
    assert "damaged or cut off" in _quickly(write(tmp_path, svg("<g>" * 5 + SQUARE)))


# ---------------------------------------------------------------- links


def test_links_to_other_files_and_websites_are_left_alone(tmp_path):
    secret = tmp_path / "secret.svg"
    secret.write_text(svg('<rect id="s" width="50" height="50"/>'), encoding="utf-8")
    body = (SQUARE + f'<use href="{secret.as_uri()}#s"/><use xlink:href="http://example.invalid/a.svg#b"/>'
            f'<use href="secret.svg#s"/><image href="{secret.as_uri()}" width="9" height="9"/>'
            '<image xlink:href="https://example.invalid/pixel.png" width="9" height="9"/>'
            '<style>@import url(http://example.invalid/style.css); rect { fill: url(http://example.invalid/#g) }</style>')
    result = preview(write(tmp_path, svg(body)))
    assert kinds(result) == ["fill"]
    counts = {s["what"]: s["count"] for s in result["skipped"]}
    assert counts["link"] == 3 and counts["picture"] == 2


# ---------------------------------------------------------------- <use> loops and bombs


@pytest.mark.parametrize("body", [
    '<g id="a"><rect width="1" height="1"/><use href="#a"/></g>',
    '<g id="a"><use href="#b"/></g><g id="b"><use xlink:href="#a"/></g>',
    '<use id="u" href="#u"/>',
    '<defs><symbol id="s" viewBox="0 0 1 1"><use href="#s"/></symbol></defs><use href="#s"/>',
])
def test_a_use_loop_is_refused(tmp_path, body):
    assert "<use> that includes itself" in _quickly(write(tmp_path, svg(body)))


def test_copies_that_multiply_out_are_refused(tmp_path):
    parts = ['<g id="g0"><rect width="2" height="2"/></g>']
    parts += [f'<g id="g{k}">' + f'<use href="#g{k - 1}"/>' * 10 + "</g>" for k in range(1, 8)]
    assert "multiplies out" in _quickly(write(tmp_path, svg(f"<defs>{''.join(parts)}</defs><use href='#g7'/>")))


def test_symbol_copies_that_multiply_out_are_refused(tmp_path):
    parts = ['<symbol id="s0" viewBox="0 0 1 1"><rect width="1" height="1"/></symbol>']
    parts += [f'<symbol id="s{k}" viewBox="0 0 1 1">' + f'<use href="#s{k - 1}"/>' * 12 + "</symbol>"
              for k in range(1, 6)]
    assert "multiplies out" in _quickly(write(tmp_path, svg(f"{''.join(parts)}<use href='#s5'/>")))


def test_groups_nested_too_deep_are_refused(tmp_path):
    body = "<g>" * 100 + SQUARE + "</g>" * 100
    assert "nested more than 64 deep" in _quickly(write(tmp_path, svg(body)))
    chain = ['<rect id="c0" width="5" height="5"/>']
    chain += [f'<g id="c{k}"><use href="#c{k - 1}"/></g>' for k in range(1, 40)]
    assert "nested more than 64 deep" in _quickly(write(tmp_path, svg("".join(chain))))


def test_too_many_elements_are_refused(tmp_path):
    assert "more than 50,000 elements" in _quickly(write(tmp_path, svg("<g/>" * 50_001)))


# ---------------------------------------------------------------- size bombs


def test_a_million_point_path_is_refused(tmp_path):
    d = "M0 0" + "".join(f"L{i % 90} {i % 40}" for i in range(1_000_000))
    path = write(tmp_path, svg(f'<path d="{d}" fill="none" stroke="black"/>'))
    assert path.stat().st_size < 20 * 1024 * 1024
    assert "more points than LUDD imports" in _quickly(path, 30)


def test_a_path_copied_many_times_is_refused(tmp_path):
    d = "M0 0" + " L1 1 L2 0" * 3000
    body = f'<path id="p" d="{d}"/>' + '<use href="#p"/>' * 100
    assert "more points than LUDD imports" in _quickly(write(tmp_path, svg(body)))


def test_a_long_path_within_bounds_is_read_in_good_time(tmp_path):
    d = "M0 0" + "".join(f"L{(i % 300) * 0.3:.1f} {(i // 300) * 0.15 + (i % 2) * 0.1:.2f}" for i in range(60_000))
    path = write(tmp_path, svg(f'<path d="{d}" fill="none" stroke="black" stroke-width="0.3"/>'))
    started = time.perf_counter()
    result = preview(path)
    assert time.perf_counter() - started < 30 and kinds(result) == ["run"]


@pytest.mark.parametrize("attribute", [
    'd="M0 0 L{} 1"', 'points="0,0 {},1 2,2"', 'transform="translate({})"', 'width="{}"', 'stroke-width="{}"',
])
def test_absurdly_long_numbers_are_refused_quickly(tmp_path, attribute):
    body = f"<path {attribute.format('1' * 100_000)} fill=\"red\"/>"
    assert "digits long" in _quickly(write(tmp_path, svg(body)), 5)


@pytest.mark.parametrize("body", [
    '<style>' + "a" * 200_000 + '</style>' + SQUARE,
    '<style>' + " " * 200_000 + "rect" + '</style>' + SQUARE,
    '<style>' + "/*" * 100_000 + '</style>' + SQUARE,
    '<g transform="' + "scale(" * 700 + '">' + SQUARE + "</g>",
    '<g transform="' + "translate(1 " * 700 + '">' + SQUARE + "</g>",
    '<rect width="20" height="20" x="10" y="10" fill="rgb(' + "1 " * 3000 + '"/>',
], ids=["style without braces", "spaces", "open comments", "open parens", "garbage transform", "garbage color"])
def test_patterns_that_could_take_forever_finish_quickly(tmp_path, body):
    started = time.perf_counter()
    result = preview(write(tmp_path, svg(body)))
    assert time.perf_counter() - started < 10 and len(result["shapes"]) == 1


def test_too_much_styling_is_refused(tmp_path):
    css = "rect{" + ";".join(f"--v{i}:{'x' * 400}" for i in range(500)) + "}"
    body = f"<style>{css}</style>" + SQUARE * 100
    assert "styles and transforms" in _quickly(write(tmp_path, svg(body)))


@pytest.mark.parametrize("body", [
    '<rect x="1e300" width="10" height="10"/><rect width="10" height="10"/>',
    '<path d="M0 0 L1e18 1e18 L10 10 Z"/>',
    '<g transform="scale(1e30 1e30)"><rect width="10" height="10"/></g>',
])
def test_absurd_coordinates_are_refused_before_curves_are_flattened(tmp_path, body):
    assert "far outside any real drawing" in _quickly(write(tmp_path, svg(body)), 5)


def test_a_huge_curve_is_refused_by_its_size_not_flattened(tmp_path):
    path = write(tmp_path, svg('<circle cx="0" cy="0" r="1e8"/>'))
    assert "far bigger than any hoop" in _quickly(path, 5)


def test_shapes_geos_cannot_work_out_are_refused_in_plain_words(tmp_path, monkeypatch):
    from shapely.errors import GEOSException

    from threadline_engine.artimport import geometry

    def broken(*_args, **_kwargs):
        raise GEOSException("TopologyException: side location conflict")

    monkeypatch.setattr(geometry, "fill_regions", broken)
    assert "couldn't work out the shapes" in refusal(write(tmp_path, svg(SQUARE)))


def test_a_time_limit_ends_a_slow_import(tmp_path, monkeypatch):
    from threadline_engine import artimport

    monkeypatch.setattr(artimport, "TIME_LIMIT_S", -1.0)
    assert "takes too long" in refusal(write(tmp_path, svg(SQUARE)))
