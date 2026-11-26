import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from threadline_engine.methods import dispatcher
from threadline_engine.rpc import Dispatcher

ROOT = Path(__file__).resolve().parents[2]


def call(method, params=None, id=1):
    req = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        req["params"] = params
    return dispatcher.handle_line(json.dumps(req))


def test_ping():
    assert call("ping") == {"jsonrpc": "2.0", "id": 1, "result": "pong"}


def test_engine_info():
    info = call("engine.info")["result"]
    assert info["version"]
    assert info["python"].startswith("3.12")


def test_unknown_method():
    assert call("nope")["error"]["code"] == -32601


def test_bad_params():
    assert call("ping", {"x": 1})["error"]["code"] == -32602


def test_parse_error():
    assert dispatcher.handle_line("{not json")["error"]["code"] == -32700


def test_invalid_request():
    assert dispatcher.handle_line('{"id": 3}')["error"]["code"] == -32600


def test_notification_gets_no_response():
    assert dispatcher.handle_line('{"jsonrpc": "2.0", "method": "ping"}') is None


def test_stdio_roundtrip():
    """The real process answers over stdio, one JSON line per request."""
    reqs = "".join(
        json.dumps({"jsonrpc": "2.0", "id": i, "method": "ping"}) + "\n" for i in range(3)
    )
    out = subprocess.run(
        [sys.executable, "-m", "threadline_engine"],
        input=reqs.encode(),
        capture_output=True,
        timeout=30,
        check=True,
    ).stdout.decode()
    lines = out.splitlines()
    assert [json.loads(l)["id"] for l in lines] == [0, 1, 2]
    assert all(json.loads(l)["result"] == "pong" for l in lines)


def test_shutdown_stops_the_engine_while_its_input_is_still_open():
    """engine.shutdown answers, then the process exits by itself (the app asks this when it quits,
    so the packaged engine can delete its unpacked files)."""
    p = subprocess.Popen([sys.executable, "-m", "threadline_engine"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    for i, m in enumerate(("ping", "engine.shutdown")):
        p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": m}) + "\n").encode())
    p.stdin.flush()  # left open: the engine must not wait for it to close
    assert p.wait(timeout=30) == 0
    lines = p.stdout.read().decode().splitlines()
    assert [json.loads(l)["result"] for l in lines] == ["pong", True]
    p.stdin.close()


# ---------------------------------------------------------------- QA phase 4: bad input never stops the engine


def test_qa_numbers_too_long_or_nesting_too_deep_are_parse_errors():
    huge = '{"jsonrpc":"2.0","id":2,"method":"ping","params":{"x":' + "1" * 5000 + "}}"
    deep = '{"jsonrpc":"2.0","id":3,"method":"ping","params":' + "[" * 100000 + "]" * 100000 + "}"
    for line in (huge, deep):
        assert dispatcher.is_background(line) is False
        assert dispatcher.handle_line(line)["error"]["code"] == -32700


def test_qa_results_json_cant_carry_become_errors_not_a_dead_engine():
    import numpy as np

    d = Dispatcher()
    d.method("nan")(lambda: {"x": math.nan})
    d.method("np")(lambda: {"n": np.int64(3)})
    d.method("ok")(lambda: 1)
    for m in ("nan", "np"):
        out = json.loads(d.respond(json.dumps({"jsonrpc": "2.0", "id": 7, "method": m})))
        assert out["id"] == 7 and out["error"]["code"] == -32603
    assert json.loads(d.respond('{"jsonrpc":"2.0","id":1,"method":"ok"}'))["result"] == 1
    assert d.respond('{"jsonrpc":"2.0","method":"ok"}') is None  # notification


def test_qa_a_bug_inside_a_method_is_not_called_bad_params_and_reads_plainly(capsys):
    d = Dispatcher()

    @d.method("adds")
    def adds(a):
        return a + "x"  # TypeError inside the method

    @d.method("needs")
    def needs(item):
        return item["path"]  # KeyError

    def call(m, p):
        return d.handle_line(json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}))["error"]

    e = call("adds", {"a": 1})
    assert e["code"] == -32603 and "Please report" in e["message"]
    assert "Traceback" in capsys.readouterr().err  # logged with where it happened
    assert call("adds", {"b": 1})["code"] == -32602  # a wrong name is the caller's mistake
    assert call("adds", [])["code"] == -32602
    e = call("needs", {"item": {}})
    assert e["code"] == -32603 and "missing (path)" in e["message"]


def test_qa_ids_of_the_wrong_kind_are_not_echoed():
    out = dispatcher.handle_line('{"jsonrpc":"2.0","id":{"a":1},"method":"ping"}')
    assert out["id"] is None and out["result"] == "pong"


def test_qa_a_stray_byte_on_the_input_doesnt_stop_the_engine():
    def ping(i):
        return b'{"jsonrpc":"2.0","id":%d,"method":"ping"}\n' % i

    big = b'{"jsonrpc":"2.0","id":3,"method":"ping","params":{"x":' + b"1" * 5000 + b"}}\n"
    out = subprocess.run([sys.executable, "-m", "threadline_engine"], input=ping(1) + b"\xff\n" + ping(2) + big + ping(4),
                         capture_output=True, timeout=60, check=True).stdout.decode()
    answers = {json.loads(l)["id"]: json.loads(l) for l in out.splitlines()}
    assert answers[1]["result"] == answers[2]["result"] == answers[4]["result"] == "pong"


def test_qa_a_slow_quality_check_doesnt_hold_up_a_render(monkeypatch):
    import io
    import time

    from threadline_engine import quality

    real = quality.check

    def slow(*a, **k):
        time.sleep(1.0)
        return real(*a, **k)

    monkeypatch.setattr(quality, "check", slow)
    run = {"id": "r", "kind": "run", "geometry": {"nodes": [[0, 0, "c"], [10, 0, "c"]]}, "params": {},
           "thread": {"color": "#000000"}}
    lay = {"items": [run]}
    lines = [json.dumps({"jsonrpc": "2.0", "id": "check", "method": "layout.check", "params": {"layout": lay}}),
             json.dumps({"jsonrpc": "2.0", "id": "render", "method": "layout.render", "params": {"layout": lay}})]
    out = io.StringIO()
    dispatcher.serve(io.StringIO("\n".join(lines) + "\n"), out)
    ids = [json.loads(l)["id"] for l in out.getvalue().splitlines()]
    assert ids == ["render", "check"]  # the render didn't wait for the check
    assert "result" in json.loads(out.getvalue().splitlines()[1])


# ---------------------------------------------------------------- every method is wired up


def _sample_params(tmp: Path) -> dict[str, dict]:
    from PIL import Image

    png = tmp / "pic.png"
    im = Image.new("RGB", (60, 60), "white")
    for x in range(15, 45):
        for y in range(15, 45):
            im.putpixel((x, y), (200, 20, 20))
    im.save(png)
    pes = tmp / "flower.pes"
    shutil.copy(ROOT / "samples" / "Flower.pes", pes)
    csv = tmp / "chart.csv"
    csv.write_text("Code,Name,Hex\n1001,Red,#ff0000\n1002,Blue,#0000ff\n", encoding="utf-8")
    (tmp / "folder").mkdir()
    shutil.copy(pes, tmp / "folder" / "a.pes")
    T = {"x": 0, "y": 0, "rotate": 0, "scale_x": 1, "scale_y": 1, "flip_x": False, "flip_y": False}
    th = {"color": "#aa0000", "name": "Red", "catalog": "", "brand": ""}
    sq = [[0, 0, "c"], [30, 0, "c"], [30, 20, "c"], [0, 20, "c"]]
    fill = {"id": "a", "kind": "fill", "geometry": {"outline": sq}, "params": {}, "thread": th, "transform": T,
            "threads": [], "ops": []}
    fill2 = {**fill, "id": "b", "geometry": {"outline": [[20, 0, "c"], [50, 0, "c"], [50, 20, "c"], [20, 20, "c"]]}}
    lay = {"items": [fill], "merge_colors": False, "color_sort": False, "basting": {"enabled": False, "margin_mm": 5}}
    place = {"x": 0, "y": 0, "width_mm": 30, "height_mm": 30, "rotate": 0}
    hoop = {"id": "h", "width_mm": 100, "height_mm": 100}
    proj = {"title": "t", "layout": lay, "images": []}
    saved = str(tmp / "p.ludd")
    return {
        "ping": {}, "engine.info": {}, "engine.shutdown": {}, "formats.list": {},
        "design.open": {"path": str(pes)},
        "design.preview_export": {"src": str(pes), "ext": "jef"},
        "design.export": {"src": str(pes), "dest": str(tmp / "out.jef")},
        "design.convert_folder": {"src_dir": str(tmp / "folder"), "dest_dir": str(tmp / "conv"), "ext": "jef"},
        "machines.list": {}, "threads.charts": {}, "threads.chart": {"id": "janome"},
        "threads.import_csv": {"path": str(csv), "name": "Mine"},
        "threads.delete_chart": {"id": "mine"},
        "threads.my_add": {"spools": [{"code": "1", "color": "#ff0000"}]},
        "threads.my_remove": {"spools": [{"code": "1", "color": "#ff0000"}]},
        "threads.match": {"colors": ["#ff0000"], "chart": "janome"},
        "layout.render": {"layout": lay},
        "layout.preview_export": {"layout": lay, "ext": "pes"},
        "layout.export": {"layout": lay, "dest": str(tmp / "lay.pes")},
        "layout.check": {"layout": lay},
        "layout.split_plan": {"layout": lay, "hoop": hoop},
        "layout.export_split": {"layout": lay, "dest": str(tmp / "split.pes"), "hoop": hoop},
        "applique.export_svg": {"layout": lay, "dest": str(tmp / "cut.svg")},
        "layout.optimize_order": {"layout": lay},
        "layout.optimize_jumps": {"layout": lay},
        "repair.preview": {"layout": lay, "item_id": "a", "ops": []},
        "fonts.scan_letter_files": {"folder": str(tmp / "folder")},
        "fonts.build_from_files": {"letters": [{"path": str(pes), "char": "A"}], "name": "Mine"},
        "names.read_list": {"path": str(csv)},
        "names.list_templates": {},
        "names.save_template": {"name": "Mine", "project_data": proj},
        "fabrics.list": {},
        "image.load": {"path": str(png)},
        "project.save": {"path": saved, "project_data": proj},
        "project.open": {"path": saved},
        "project.autosave": {"project_data": proj},
        "project.recovery": {},
        "project.restore": {},
        "project.discard_recovery": {},
        "trace.info": {"path": str(png)},
        "trace.suggest": {"path": str(png), "placement": place, "points": [[0, 0], [3, 0]]},
        "trace.digitize_all": {"path": str(png), "placement": place},
        "trace.region": {"path": str(png), "placement": place, "at": [0, 0]},
        "shape.offset": {"layout": lay, "ids": ["a"], "distance_mm": 2},
        "shape.split": {"obj": fill, "a": [15, -5], "b": [15, 25]},
        "shape.merge": {"objs": [fill, fill2]},
        "shape.cut_out": {"target": fill, "cutters": [fill2]},
        "shape.satin_fill": {"outline": fill["geometry"]["outline"]},
        "shape.set_end": {"obj": fill, "which": "end", "at": [0, 0]},
        "text.to_shapes": {"item": {"id": "t", "kind": "text", "text": "A", "font": {"path": "missing.ttf", "index": 0}, "size_mm": 10, "style": "satin"}},
        "text.letter_frame": {"item": {"id": "t", "kind": "text", "transform": {"x": 5, "rotate": 90}}, "at": [5, 2]},
        "library.scan": {"folder": str(tmp / "folder")},
        "ai.trace_model": {}, "ai.trace_model_remove": {},
        "ai.settings": {}, "ai.save_settings": {"patch": {"mode": "off"}}, "ai.set_key": {"key": None},
        "ai.test": {}, "ai.advisor_preview": {"layout": lay}, "ai.advise": {"layout": lay},
        "help.search": {"query": "satin"}, "help.preview": {"question": "what is satin?"},
        "help.ask": {"question": "what is satin?", "use_ai": False},
        "fonts.list": {},
        "fonts.export_stitch_font": {"font": _a_font(), "dest": str(tmp / "f.luddfont"), "chars": "A"},
    }


def _a_font() -> dict:
    from threadline_engine import lettering

    outline = [f for f in lettering.list_fonts() if f.get("kind") == "outline" and not f.get("symbol")]
    if not outline:
        pytest.skip("no installed font to try lettering with")
    return outline[0]


NETWORK = {"ai.trace_model_download"}  # downloads a model: never in tests


def test_qa_every_engine_method_answers_through_the_dispatcher(tmp_path):
    """Each method, called the way the UI calls it, gives a result or a plain user-facing error
    (-32000), never 'method not found', 'invalid params' or an engine bug (-32603)."""
    params = _sample_params(tmp_path)
    missing = set(dispatcher._methods) - set(params) - NETWORK
    assert not missing, f"add sample params for {sorted(missing)}"
    try:
        for i, (m, p) in enumerate(params.items()):
            out = dispatcher.handle_line(json.dumps({"jsonrpc": "2.0", "id": i, "method": m, "params": p}))
            assert "result" in out or out["error"]["code"] == -32000, (m, out.get("error"))
            json.dumps(out, allow_nan=False)  # strict JSON, as the UI parses it
    finally:
        dispatcher.stopping = False  # engine.shutdown


def test_qa_every_method_the_ui_calls_exists():
    call = re.compile(r'\bcall\s*(?:<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>)?\(\s*"([^"]+)"', re.S)
    used = set()
    for f in (ROOT / "apps" / "desktop" / "src").rglob("*.ts*"):
        if ".test." not in f.name:
            used |= set(call.findall(f.read_text(encoding="utf-8")))
    assert used and used <= set(dispatcher._methods), sorted(used - set(dispatcher._methods))
