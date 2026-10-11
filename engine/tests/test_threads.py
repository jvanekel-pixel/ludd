import pytest

from threadline_engine import threads
from threadline_engine.threads import ciede2000, hex_to_rgb, rgb_to_lab


# Reference pairs from Sharma, Wu & Dalal (2005), "The CIEDE2000 color-difference formula".
SHARMA = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]


@pytest.mark.parametrize("a,b,expected", SHARMA)
def test_ciede2000_reference_values(a, b, expected):
    assert ciede2000(a, b) == pytest.approx(expected, abs=1e-4)
    assert ciede2000(b, a) == pytest.approx(expected, abs=1e-4)


def test_lab_of_white_and_black():
    assert rgb_to_lab((255, 255, 255)) == pytest.approx((100, 0, 0), abs=0.01)
    assert rgb_to_lab((0, 0, 0)) == pytest.approx((0, 0, 0), abs=0.01)


def test_hex_parsing():
    assert hex_to_rgb("#ff8000") == (255, 128, 0)
    assert hex_to_rgb("f80") == (255, 136, 0)
    with pytest.raises(threads.ThreadError):
        hex_to_rgb("#zzzzzz")


def test_builtin_charts_listed():
    charts = threads.list_charts()
    ids = {c["id"]: c for c in charts}
    assert charts[0]["id"] == "my-threads" and charts[0]["count"] == 0 and charts[0]["mine"]
    assert ids["brother-palette"]["count"] == 64
    assert ids["janome"]["count"] > 50
    assert ids["brother-palette"]["builtin"] and ids["janome"]["builtin"]


def test_match_finds_exact_thread_first():
    chart = threads.get_chart("janome")
    t = chart["threads"][5]
    best = threads.match([t["color"]], "janome")[0][0]
    assert best["color"] == t["color"] and best["delta_e"] == 0
    assert best["brand"] == "Janome"


def test_csv_hex_and_rgb_columns():
    hex_csv = "Number,Color Name,Hex\n1000,Black,#000000\n1001,White,ffffff\n"
    assert threads.parse_csv(hex_csv) == [
        {"code": "1000", "name": "Black", "color": "#000000"},
        {"code": "1001", "name": "White", "color": "#ffffff"},
    ]
    rgb_csv = "code;name;R;G;B\n1278;True Orange;255;102;22\n"
    assert threads.parse_csv(rgb_csv) == [{"code": "1278", "name": "True Orange", "color": "#ff6616"}]


def test_csv_color_column_with_hex_values():
    assert threads.parse_csv("code,color\n5,#112233\n") == [{"code": "5", "name": "", "color": "#112233"}]


def test_csv_errors():
    with pytest.raises(threads.ThreadError, match="thread number"):
        threads.parse_csv("name,hex\nBlack,#000000\n")
    with pytest.raises(threads.ThreadError, match="color column"):
        threads.parse_csv("code,name\n1,Black\n")
    with pytest.raises(threads.ThreadError, match="No usable"):
        threads.parse_csv("code,hex\n1,notacolor\n")


def test_import_list_match_delete(tmp_path, isolated_data_dir):
    f = tmp_path / "madeira.csv"
    f.write_text("﻿Code,Name,Hex\n1278,True Orange,#ff6616\n1184,True Red,#bd1d44\nbad,,xyz\n", encoding="utf-8")
    summary = threads.import_csv(str(f), "Madeira Rayon 40")
    assert summary == {"id": "madeira-rayon-40", "name": "Madeira Rayon 40", "brand": "Madeira Rayon 40", "builtin": False, "count": 2, "mine": False}
    assert (isolated_data_dir / "threads" / "madeira-rayon-40.json").is_file()
    assert "madeira-rayon-40" in {c["id"] for c in threads.list_charts()}
    m = threads.match(["#fe6517"], "madeira-rayon-40", count=1)[0][0]
    assert m["code"] == "1278" and m["delta_e"] < 1
    threads.delete_chart("madeira-rayon-40")
    assert "madeira-rayon-40" not in {c["id"] for c in threads.list_charts()}
    with pytest.raises(threads.ThreadError):
        threads.delete_chart("janome")


def test_csv_vendor_style_headers():
    """Headers as exported by chart sites, e.g. "Madeira Code,Color Name,HEX,R,G,B,C,M,Y,K"."""
    text = "Madeira Code,Color Name,HEX,R,G,B,C,M,Y,K\n0101,Lemon Very Light,#EAE8BF,234,232,191,0,0.9,18.4,8.2\n"
    assert threads.parse_csv(text) == [{"code": "0101", "name": "Lemon Very Light", "color": "#eae8bf"}]
    assert threads.parse_csv("Thread #;Description;Red;Green;Blue\n17;Sky;10;20;30\n") == [
        {"code": "17", "name": "Sky", "color": "#0a141e"}
    ]


def test_my_threads_add_match_remove():
    assert threads.my_threads()["threads"] == []
    with pytest.raises(threads.ThreadError, match="no threads yet"):
        threads.match(["#ff0000"], "my-threads")
    janome = threads.get_chart("janome")["threads"][:2]
    threads.my_add([{**t, "brand": "Janome"} for t in janome])
    threads.my_add([{"name": "Amazon kit navy", "color": "#1e2a5a"}])  # custom spool, no number
    threads.my_add([{**janome[0], "brand": "Janome"}])  # already owned: no duplicate
    mine = threads.my_threads()["threads"]
    assert len(mine) == 3
    assert threads.list_charts()[0]["count"] == 3

    best = threads.match(["#1f2b5b"], "my-threads", count=1)[0][0]
    assert best["name"] == "Amazon kit navy" and best["brand"] == "" and best["delta_e"] < 1
    assert threads.match([janome[1]["color"]], "my-threads", count=1)[0][0]["brand"] == "Janome"

    threads.my_remove([{"brand": "", "code": "", "color": "#1e2a5a"}, {"brand": "Janome", "code": janome[0]["code"]}])
    assert [t["code"] for t in threads.my_threads()["threads"]] == [janome[1]["code"]]
