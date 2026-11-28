"""The one-use child process that reads PDFs and outlines big wide strokes (artimport/child.py):
what it answers is exactly what the engine would work out itself; it is killed at the time limit and
ends itself above its memory limit or once the engine ends; it never shows a console window or
writes to the engine's output; and it can never turn into a second engine."""

import json
import re
import subprocess
import sys
import threading
import time

import pytest

from artimport_child_util import CRASHES, ENGINE, GARBLED, HANGS, NO_WMI, NOISY, Started, alive, script
from artimport_util import ask, preview, refusal, svg, write
from test_artimport_pdf import MM, PROOF, build_pdf, document, first_extra, pdf_file, stream
from threadline_engine import artimport
from threadline_engine.artimport import Deadline, Options, child, geometry, pdf

SQUARE = '<rect x="10" y="10" width="20" height="20" fill="#ff0000"/>'


def _rich_pdf() -> bytes:
    """Two pages; the second turned, with curves, strokes, a form, dashes, a clip, a picture and
    text: everything the child sends back."""
    form = first_extra(2)
    image = form + 1
    k = 0.5523 * 36
    second = (f"0.2 0.4 0.6 rg 136 50 m 136 {50 + k} {100 + k} 86 100 86 c {100 - k} 86 64 {50 + k} 64 50 c h f* "
              f"[4 2] 0 d 1 0 1 RG {2.5 * MM:.4f} w 1 J 2 j 10 10 m 40.123456 77.7 l S [] 0 d "
              "q 0 0 30 30 re W n 20 20 40 40 re f Q q 1 0 0 1 100 10 cm /F Do Q q 9 0 0 9 5 5 cm /Im Do Q "
              "BT /F1 12 Tf 10 80 Td (Hi) Tj ET")
    extra = (stream("0 1 0 rg 0 0 10 10 re f 0 0 m 3.3333333 7.7777777 l S", "/Type /XObject /Subtype /Form "
                    "/BBox [0 0 100 100] /Matrix [1.5 0.2 -0.2 1.5 0 0]"),
             stream("\x00\x00\x00", "/Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB "
                                    "/BitsPerComponent 8"))
    resources = (f"/XObject << /F {form} 0 R /Im {image} 0 R >> "
                 "/Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >>")
    return document(PROOF, second, rotate=90, resources=resources, extra=extra)


def test_the_child_reads_a_page_exactly_as_the_engine_would():
    data = _rich_pdf()
    for page in (0, 1):
        options = Options(page=page)
        here = pdf._read(data, options, Deadline())
        there = child.read_pdf(data, options, Deadline())
        assert there == here
        assert repr(there.items) == repr(here.items)  # every float whole, -0.0 included
    assert there.pages == 2 and there.skipped and there.items


def test_big_wide_strokes_are_outlined_in_one_child_exactly_as_here(tmp_path, monkeypatch):
    """GEOS can take minutes and gigabytes over a wide line that doubles back, in a call that can't
    be stopped: lines of many points are outlined in the child, all of a drawing's together."""
    wave = " ".join(f"{5 + i * 0.1:.3f},{25 + 4 * ((i // 7) % 2) + (i % 3) * 0.05:.3f}" for i in range(600))
    ring = " ".join(f"{60 + (20 + (i % 2) * 0.4) * c:.4f},{25 + (20 + (i % 2) * 0.4) * s:.4f}"
                    for i, (c, s) in enumerate(_circle(500)))
    path = write(tmp_path, svg(f'<polyline points="{wave}" fill="none" stroke="#aa0000" stroke-width="14"/>'
                               f'<polygon points="{ring}" fill="none" stroke="#0000aa" stroke-width="13" '
                               'stroke-linejoin="round"/>'
                               '<path d="M5 45 L95 45" stroke="#00aa00" stroke-width="15"/>'))
    started = Started().watch(monkeypatch)
    there = preview(path)
    jobs = [command for _, command, _ in started]
    assert len(jobs) == 1  # one child for both big ones; the straight line is outlined in the engine
    monkeypatch.setattr(geometry, "OUTLINE_IN_CHILD", 10**9)
    here = preview(path)
    assert there == here and len(started) == 1
    assert [s["color"] for s in there["shapes"]][0] == "#aa0000"


def _circle(n):
    import math

    return [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---------------------------------------------------------------- how it ends


def _forms_bomb(levels: int = 7) -> bytes:
    """A few kilobytes: forms inside forms, each drawing the one inside it ten times, so loading
    the page makes ten million objects (over 2 GB)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Contents 4 0 R "
               "/Resources << /XObject << /F 5 0 R >> >> >>", stream("/F Do")]
    for level in range(levels, 0, -1):
        number = 5 + (levels - level)
        if level == 1:
            objects.append(stream("1 0 0 rg 0 0 1 1 re f", "/Type /XObject /Subtype /Form /BBox [0 0 200 100]"))
        else:
            objects.append(stream(" ".join(["/F Do"] * 10), "/Type /XObject /Subtype /Form /BBox [0 0 200 100] "
                                  f"/Resources << /XObject << /F {number + 1} 0 R >> >>"))
    return build_pdf(objects)


def test_the_child_ends_itself_above_its_memory_limit(tmp_path, monkeypatch):
    """The limit is 2 GB; a smaller one here, so the test takes little memory."""
    assert child.CHILD_MEMORY == 2 * 1024**3
    monkeypatch.setattr(child, "CHILD_MEMORY", 300 * 1024**2)
    started = Started().watch(monkeypatch)
    message = refusal(pdf_file(tmp_path, _forms_bomb()))
    assert message == child.PDF_TOO_MUCH_MEMORY
    assert started.all_ended() and [p.returncode for p, _, _ in started] == [child.MEMORY_EXIT]
    monkeypatch.undo()
    assert preview(pdf_file(tmp_path, document(PROOF)))["shapes"]  # and the next import works


def test_the_time_limit_ends_a_child_that_cannot_be_stopped(tmp_path, monkeypatch, capfd):
    """The one test of the time limit itself (passed in short): the stand-in child is stuck in a
    job that never ends, where memory can't be read, and the engine kills it at the limit. Nothing
    is left running, and the next import works."""
    monkeypatch.setattr(artimport, "TIME_LIMIT_S", 6.0)  # long enough for the stand-in to start anywhere
    monkeypatch.setattr(child, "worker_command", lambda: script(tmp_path, HANGS))
    started = Started().watch(monkeypatch)
    threads = threading.active_count()
    before = time.perf_counter()
    message = refusal(pdf_file(tmp_path, document(PROOF)))
    assert time.perf_counter() - before < 30
    assert message == artimport.TOO_SLOW
    [(process, _, _)] = started
    assert process.returncode is not None and process.returncode != child.MEMORY_EXIT
    # The process that did the work is gone too (on Windows a virtual environment's python is a
    # launcher that starts a second one, which must end with it).
    worker = int(re.search(r"stand-in child: working pid=(\d+)", capfd.readouterr().err)[1])
    until = time.perf_counter() + 10
    while (alive(worker) or threading.active_count() > threads) and time.perf_counter() < until:
        time.sleep(0.05)
    assert not alive(worker)
    assert threading.active_count() <= threads, threading.enumerate()  # nothing still working here
    monkeypatch.undo()
    assert preview(pdf_file(tmp_path, document(PROOF)))["shapes"]


@pytest.mark.parametrize("body", [CRASHES, GARBLED], ids=["crashes", "no real answer"])
def test_a_child_that_fails_is_reported_in_plain_words(tmp_path, monkeypatch, body):
    monkeypatch.setattr(child, "worker_command", lambda: script(tmp_path, body))
    started = Started().watch(monkeypatch)
    assert refusal(pdf_file(tmp_path, document(PROOF))) == child.PDF_NO_ANSWER
    assert started.all_ended()
    monkeypatch.undo()
    assert preview(pdf_file(tmp_path, document(PROOF)))["shapes"]


def test_a_child_that_cannot_start_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(child, "worker_command", lambda: [str(tmp_path / "no-such-program")])
    assert refusal(pdf_file(tmp_path, document(PROOF))) == child.NOT_STARTED


# A stand-in engine: it starts a child that never finishes, then gets killed.
_ENGINE_THAT_IS_KILLED = """\
import sys
sys.path.insert(0, sys.argv[1])
from threadline_engine.artimport import Deadline, Options, child
child.worker_command = lambda: [sys.executable, sys.argv[2]]
child.read_pdf(b"%PDF-1.7 never read", Options(), Deadline(600))
"""


def test_no_child_is_left_behind_when_the_engine_is_killed(tmp_path):
    """The stand-in child is stuck; the engine is killed outright (as Windows' End task or a crash
    would). The child shares the engine's stderr, so that pipe only closes once both are gone."""
    engine = tmp_path / "engine_that_is_killed.py"
    engine.write_text(_ENGINE_THAT_IS_KILLED, encoding="utf-8")
    stand_in = script(tmp_path, HANGS)[1]
    process = subprocess.Popen([sys.executable, str(engine), str(ENGINE), stand_in], stderr=subprocess.PIPE,
                               stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    lines: list[bytes] = []
    reader = threading.Thread(target=lambda: lines.extend(iter(process.stderr.readline, b"")), daemon=True)
    reader.start()
    try:
        until = time.monotonic() + 60
        while not any(b"stand-in child: working" in line for line in lines) and time.monotonic() < until:
            time.sleep(0.05)
        assert any(b"stand-in child: working" in line for line in lines), lines
        assert process.poll() is None
        process.kill()  # no chance to tidy up: the child must notice by itself
        process.wait(30)
        reader.join(20)
        assert not reader.is_alive(), "the child outlived the engine"
    finally:
        if process.poll() is None:
            process.kill()


@pytest.mark.parametrize("job", ["pdf", "wide line"])
def test_the_child_starts_no_other_program(tmp_path, monkeypatch, capfd, job):
    """Even when a library asks which Windows this is and Windows doesn't answer at once (Python
    would then run "cmd /c ver"), for a PDF and for a wide line."""
    monkeypatch.setattr(child, "worker_command", lambda: script(tmp_path, NO_WMI))
    if job == "pdf":
        path = pdf_file(tmp_path, document(PROOF))
    else:
        wave = " ".join(f"{5 + i * 0.15:.3f},{20 + 5 * ((i // 8) % 2)}" for i in range(450))
        path = write(tmp_path, svg(f'<polyline points="{wave}" fill="none" stroke="red" stroke-width="14"/>'))
    assert preview(path)["shapes"]
    assert "stand-in child: starts" not in capfd.readouterr().err


@pytest.mark.skipif(sys.platform != "win32", reason="console windows are a Windows thing")
def test_no_console_window_is_ever_shown(tmp_path, monkeypatch):
    started = Started().watch(monkeypatch)
    preview(pdf_file(tmp_path, document(PROOF)))
    [(_, _, kwargs)] = started
    assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_the_child_is_the_engine_itself_in_its_private_mode(monkeypatch):
    assert child.worker_command() == [sys.executable, "-m", "threadline_engine", child.WORKER_FLAG]
    assert child.worker_env()["PYTHONPATH"].split(";" if sys.platform == "win32" else ":")[0] == str(ENGINE)
    monkeypatch.setattr(sys, "frozen", True, raising=False)  # the packaged engine runs its own program
    assert child.worker_command() == [sys.executable, child.WORKER_FLAG]


# ---------------------------------------------------------------- it can't spoil the engine's output


def test_what_a_library_prints_never_spoils_the_answer(tmp_path, monkeypatch, capfd):
    monkeypatch.setattr(child, "worker_command", lambda: script(tmp_path, NOISY.format(noise="here")))
    result = preview(pdf_file(tmp_path, document(PROOF)))
    assert [s["kind"] for s in result["shapes"]] == ["fill", "satin"]
    out, err = capfd.readouterr()
    assert "noise" not in out  # nothing on the engine's own output
    assert "noise on file descriptor 1 here" in err and "noise from print here" in err  # it's in the log


def test_over_json_rpc_every_line_the_engine_writes_is_an_answer(tmp_path):
    """The real engine over stdio, with previews that use the child."""
    wave = " ".join(f"{5 + i * 0.1:.3f},{20 + 6 * ((i // 9) % 2)}" for i in range(500))
    drawing = write(tmp_path, svg(f'<polyline points="{wave}" fill="none" stroke="red" stroke-width="14"/>'))
    document_ = pdf_file(tmp_path, document(PROOF))
    engine = subprocess.Popen([sys.executable, "-m", "threadline_engine"], cwd=ENGINE, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    try:
        answers = []
        for i, path in enumerate((document_, drawing), start=1):
            engine.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": "art.preview",
                                           "params": {"path": str(path)}}) + "\n")
            engine.stdin.flush()
            answers.append(engine.stdout.readline())
        engine.stdin.close()
        answers += engine.stdout.read().splitlines()
        assert engine.wait(60) == 0
    finally:
        if engine.poll() is None:
            engine.kill()
    parsed = [json.loads(line) for line in answers]
    assert [a["id"] for a in parsed] == [1, 2] and all(a["result"]["shapes"] for a in parsed), parsed


# ---------------------------------------------------------------- it can never be a second engine


PING = b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'


@pytest.mark.parametrize("options", [[child.WORKER_FLAG], [child.WORKER_FLAG, "--more"], ["--multiprocessing-fork"],
                                     ["serve"]], ids=["child", "child and more", "another tool's", "a word"])
def test_a_copy_of_the_engine_started_with_options_never_answers_requests(options):
    done = subprocess.run([sys.executable, "-m", "threadline_engine", *options], input=PING * 3, capture_output=True,
                          timeout=60, cwd=ENGINE)
    assert done.returncode == 2 and done.stdout == b"", (done.returncode, done.stdout, done.stderr[-500:])


def test_the_child_takes_only_its_own_jobs():
    lines = (b'{"job":"shell","size":0,"seconds":1,"memory":1,"engine":1}\n', b'{"size":0}\n', b"\n", b"[1]\n")
    for line in lines:
        done = subprocess.run([sys.executable, "-m", "threadline_engine", child.WORKER_FLAG], input=line,
                              capture_output=True, timeout=60, cwd=ENGINE)
        assert done.returncode == 2 and done.stdout == b"", (line, done.stdout, done.stderr[-500:])


def test_a_pdf_that_the_child_refuses_keeps_its_own_words(tmp_path):
    assert "has 1 page" in refusal(pdf_file(tmp_path, document(PROOF)), page=3)
    assert ask(write(tmp_path, svg(SQUARE)))["result"]["shapes"]
