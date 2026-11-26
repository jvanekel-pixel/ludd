"""Reading a list of names for "One file per name", and name templates kept in LUDD's data
folder (P5-D1). Every test uses the temporary data folder (conftest.py)."""

import pytest

from threadline_engine import names, project
from threadline_engine.names import NamesError

RED = {"color": "#cc2222", "name": "Red", "catalog": "", "brand": ""}


def _list(tmp_path, content: str | bytes, name: str = "names.csv") -> dict:
    path = tmp_path / name
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return names.read_list(str(path))


def test_read_list_plain_names(tmp_path):
    got = _list(tmp_path, "Emma\nJack\n\n   \nOlivia Grace\r\n  Noah  \n", "names.txt")
    assert got == {"columns": ["name"], "rows": [["Emma"], ["Jack"], ["Olivia Grace"], ["Noah"]], "skipped": 0}


def test_read_list_header_semicolons_quotes_bom(tmp_path):
    text = 'Name;Number;Colour\r\n"Smith; Jr.";7;#ff0000\r\nZoë;12;\r\n"Ann ""A""";3;1001\r\n'
    got = _list(tmp_path, b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert got["columns"] == ["name", "number", "color"]
    assert got["rows"] == [["Smith; Jr.", "7", "#ff0000"], ["Zoë", "12", ""], ['Ann "A"', "3", "1001"]]
    assert got["skipped"] == 0


@pytest.mark.parametrize("sep", [",", ";", "\t"])
def test_read_list_two_columns_for_two_placeholders(tmp_path, sep):
    got = _list(tmp_path, sep.join(["name", "number"]) + "\nEmma" + sep + "7\nJack" + sep + "12\n")
    assert got == {"columns": ["name", "number"], "rows": [["Emma", "7"], ["Jack", "12"]], "skipped": 0}


def test_read_list_second_column_without_a_header(tmp_path):
    got = _list(tmp_path, "Emma,7\nJack,12\nMia\n")
    assert got["columns"] == ["name", "column 2"]
    assert got["rows"] == [["Emma", "7"], ["Jack", "12"], ["Mia", ""]]


def test_read_list_header_words(tmp_path):
    got = _list(tmp_path, "Name,Line 2,File Name,Thread,Number\nA,B,c,d,1\n")
    assert got["columns"] == ["name", "line2", "file", "color", "number"]
    # Not every cell is a header word: the first row is a name.
    got = _list(tmp_path, "Emma,Rose\nJack,Lee\n")
    assert got["columns"] == ["name", "column 2"] and len(got["rows"]) == 2


@pytest.mark.parametrize("first", ["Line", "Num", "No", "Date", "First", "Last", "Size", "Message"])
def test_read_list_keeps_a_first_name_that_is_also_a_header_word(tmp_path, first):
    # In a one-column list these can be someone's name, so no one's file goes missing.
    assert _list(tmp_path, f"{first}\nKari\n", "names.txt")["rows"] == [[first], ["Kari"]]


@pytest.mark.parametrize("header", ["Name", "First Name", "Player", "Line 1", "Initials", "Number"])
def test_read_list_one_column_headers(tmp_path, header):
    assert _list(tmp_path, f"{header}\nKari\n", "names.txt")["rows"] == [["Kari"]]


def test_read_list_a_comma_in_one_name_is_not_a_second_column(tmp_path):
    got = _list(tmp_path, "Emma\nSammy Davis, Jr.\nJack\nOlivia\n", "names.txt")
    assert got["columns"] == ["name"]
    assert got["rows"][1] == ["Sammy Davis, Jr."]


def test_read_list_one_column_with_a_header_and_empty_trailing_cells(tmp_path):
    got = _list(tmp_path, "names,,\nEmma,,\nJack,,\n")
    assert got == {"columns": ["name"], "rows": [["Emma"], ["Jack"]], "skipped": 0}


def test_read_list_stops_at_2000_and_says_so(tmp_path):
    got = _list(tmp_path, "name\n" + "".join(f"N{i}\n\n" for i in range(2005)))
    assert len(got["rows"]) == 2000 and got["skipped"] == 5
    assert got["rows"][0] == ["N0"] and got["rows"][-1] == ["N1999"]
    assert _list(tmp_path, "".join(f"N{i}\n" for i in range(2000)))["skipped"] == 0


def test_read_list_excel_ansi_and_unicode_text(tmp_path):
    ansi = "name,number\nZoë,7\nJosé,8\n".encode("cp1252")
    assert _list(tmp_path, ansi)["rows"] == [["Zoë", "7"], ["José", "8"]]
    unicode_text = "name\tnumber\nZoë\t7\n".encode("utf-16")  # Excel's "Unicode Text": UTF-16 with its mark
    assert _list(tmp_path, unicode_text, "names.txt") == {"columns": ["name", "number"], "rows": [["Zoë", "7"]], "skipped": 0}


def test_read_list_a_cell_with_two_lines(tmp_path):
    got = _list(tmp_path, 'name,number\n"Happy\r\nBirthday",1\n')
    assert got["rows"] == [["Happy\nBirthday", "1"]]


@pytest.mark.parametrize("content,filename,words", [
    (b"", "empty.csv", "no names"),
    (b"name,number\n\n", "header.csv", "no names"),
    (b"PK\x03\x04\x14\x00\x00\x00", "team.xlsx", "Save it as CSV"),
    (b"\x00\x01\x02\x00binary", "photo.csv", "doesn't look like"),
    (b"a\n" * (3 * 1024 * 1024), "huge.txt", "too big"),
])
def test_read_list_refuses_in_plain_words(tmp_path, content, filename, words):
    with pytest.raises(NamesError, match=words):
        _list(tmp_path, content, filename)


def test_read_list_missing_file(tmp_path):
    with pytest.raises(NamesError, match="Couldn't read"):
        names.read_list(str(tmp_path / "gone.csv"))


def _layout(**text):
    item = {"id": "t", "kind": "text", "text": "Name", "font": {"family": "Arial", "style": "Regular"}, "size_mm": 15,
            "spacing_mm": 0, "style": "satin", "shape": {"type": "line"}, "monogram": False, "thread": RED,
            "transform": {}, "threads": [], "ops": [], "placeholder": True, "bind": "number", "fit_width_mm": 60, **text}
    return {"title": "Team set", "layout": {"items": [item], "merge_colors": False, "color_sort": False}, "images": []}


def test_templates_are_saved_in_the_data_folder_and_listed(isolated_data_dir):
    assert names.list_templates() == []
    saved = names.save_template("Team shirts", _layout())
    assert saved["name"] == "Team shirts"
    path = isolated_data_dir / "templates" / "Team shirts.ludd"
    assert path.is_file() and saved["path"] == str(path)
    names.save_template("bibs", _layout())
    listed = names.list_templates()
    assert [t["name"] for t in listed] == ["bibs", "Team shirts"]  # in name order, whatever the case
    assert listed[1]["path"] == str(path) and listed[1]["saved_at"] > 0
    opened = project.open_project(str(path))
    item = opened["layout"]["items"][0]
    assert (item["placeholder"], item["bind"], item["fit_width_mm"]) == (True, "number", 60)
    assert opened["title"] == "Team shirts"


def test_saving_a_template_never_replaces_one_unasked(isolated_data_dir):
    names.save_template("Team shirts", _layout(text="Old"))
    with pytest.raises(NamesError, match="already"):
        names.save_template("Team shirts", _layout(text="New"))
    path = isolated_data_dir / "templates" / "Team shirts.ludd"
    assert project.open_project(str(path))["layout"]["items"][0]["text"] == "Old"
    names.save_template("Team shirts", _layout(text="New"), replace=True)
    assert project.open_project(str(path))["layout"]["items"][0]["text"] == "New"
    assert len(names.list_templates()) == 1


@pytest.mark.parametrize("name,stem", [("../../evil", "_.._evil"), ("a/b:c?", "a_b_c_"), ("  Kids.  ", "Kids"),
                                       ("CON", "_CON"), ("x" * 200, "x" * 80)])
def test_a_template_name_makes_a_safe_file_name(isolated_data_dir, name, stem):
    saved = names.save_template(name, _layout())
    assert saved["name"] == stem
    assert [p.name for p in (isolated_data_dir / "templates").iterdir()] == [f"{stem}.ludd"]


@pytest.mark.parametrize("name", ["", "   ", "...", None])
def test_a_template_needs_a_name(isolated_data_dir, name):
    with pytest.raises(NamesError, match="name"):
        names.save_template(name, _layout())


def test_a_template_needs_a_design(isolated_data_dir):
    with pytest.raises(NamesError, match="design"):
        names.save_template("x", None)
