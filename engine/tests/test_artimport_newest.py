"""art.preview: a newer preview replaces an older one, only one runs at a time, and the time limit
counts from when a request comes in. Through the engine's own serve loop, requests fed to it one at a
time."""

import io
import json
import re
import threading
import time
from pathlib import Path

import pytest

from artimport_child_util import HANGS, Started, alive, script
from test_artimport_pdf import PROOF, document, pdf_file
from threadline_engine import artimport
from threadline_engine.artimport import child
from threadline_engine.methods import dispatcher
from threadline_engine.rpc import REPLACED

ROOT = Path(__file__).resolve().parents[2]


def request(i: int, path: str) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": i, "method": "art.preview", "params": {"path": path}}) + "\n"


class Out(io.StringIO):
    """The engine's output, with when each answer came."""

    def __init__(self) -> None:
        super().__init__()
        self.when: dict[int, float] = {}

    def write(self, text: str) -> int:
        self.when[json.loads(text)["id"]] = time.monotonic()
        return super().write(text)


def serve(feed) -> tuple[dict, Out]:
    out = Out()
    dispatcher.serve(feed, out)
    answers = {a["id"]: a for a in map(json.loads, out.getvalue().splitlines())}
    return answers, out


def wait_until(what, seconds: float = 20.0) -> None:
    until = time.monotonic() + seconds
    while not what():
        assert time.monotonic() < until, "gave up waiting"
        time.sleep(0.01)


class StandIn:
    """Stands in for artimport.preview: "slow" runs until its deadline stops it, "stubborn" ignores
    its deadline until released (a step that can't be stopped partway), anything else answers."""

    def __init__(self) -> None:
        self.running = self.most = 0
        self.ran: list[str] = []
        self.release = threading.Event()
        self.lock = threading.Lock()

    def __call__(self, path, options=None, deadline=None):
        with self.lock:
            self.ran.append(path)
            self.running += 1
            self.most = max(self.most, self.running)
        try:
            if path.startswith("slow"):
                until = time.monotonic() + 20
                while not self.release.is_set() and time.monotonic() < until:
                    deadline.check()
                    time.sleep(0.01)
                deadline.check()
            elif path == "stubborn":
                self.release.wait(20)
            time.sleep(0.05)
            return {"path": path}
        finally:
            with self.lock:
                self.running -= 1


@pytest.fixture
def stand_in(monkeypatch):
    fake = StandIn()
    monkeypatch.setattr(artimport, "preview", fake)
    return fake


def test_a_newer_preview_stops_the_older_one_and_only_one_runs_at_a_time(stand_in):
    def feed():
        yield request(1, "slow")
        wait_until(lambda: stand_in.ran == ["slow"])
        yield request(2, "next")

    answers, out = serve(feed())
    assert answers[1]["error"] == {"code": -32000, "message": REPLACED}
    assert answers[2]["result"] == {"path": "next"}
    assert stand_in.most == 1 and out.when[1] < out.when[2]


def test_requests_replace_each_other_in_the_order_they_come_in(stand_in):
    """The reading thread gives each its place, so whichever thread gets going first, only the last
    one is answered with a drawing."""
    def feed():
        for i in range(1, 7):
            yield request(i, f"slow {i}")
        stand_in.release.set()

    answers, _ = serve(feed())
    assert [answers[i].get("error", {}).get("message") for i in range(1, 6)] == [REPLACED] * 5
    assert answers[6]["result"] == {"path": "slow 6"}
    assert stand_in.most == 1


def test_a_preview_replaced_while_waiting_never_runs(stand_in):
    """Behind a step that can't be stopped partway, a waiting preview that is itself replaced is
    answered at once, without running."""
    replaced_answered = []

    def feed():
        yield request(1, "stubborn")
        wait_until(lambda: stand_in.ran == ["stubborn"])
        yield request(2, "middle")
        yield request(3, "last")
        wait_until(lambda: 2 in out.when)
        replaced_answered.append(time.monotonic())
        stand_in.release.set()

    out = Out()
    dispatcher.serve(feed(), out)
    answers = {a["id"]: a for a in map(json.loads, out.getvalue().splitlines())}
    assert answers[2]["error"]["message"] == REPLACED and out.when[2] <= replaced_answered[0]
    assert answers[3]["result"] == {"path": "last"}
    assert stand_in.ran == ["stubborn", "last"] and stand_in.most == 1


def test_a_replaced_pdf_s_child_is_killed_before_the_next_one_starts(tmp_path, monkeypatch, capfd):
    """The older preview is stuck reading a PDF (a stand-in child that never ends): a newer one
    kills it, then reads its own file."""
    commands = iter([script(tmp_path, HANGS)])
    real = child.worker_command
    monkeypatch.setattr(child, "worker_command", lambda: next(commands, None) or real())
    running_when_started = []
    started = Started()
    real_popen = started.popen

    def popen(command, **kwargs):
        running_when_started.append([p.poll() is None for p, _, _ in started])
        return real_popen(command, **kwargs)

    monkeypatch.setattr(child.subprocess, "Popen", popen)
    path = str(pdf_file(tmp_path, document(PROOF)))
    said = []

    def feed():
        yield request(1, path)
        wait_until(lambda: said.append(capfd.readouterr().err) or "stand-in child: working" in "".join(said), 60)
        yield request(2, path)

    answers, _ = serve(feed())
    assert answers[1]["error"]["message"] == REPLACED
    assert [s["kind"] for s in answers[2]["result"]["shapes"]] == ["fill", "satin"]
    assert running_when_started == [[], [False]]  # the first had ended when the second started
    assert started.all_ended()
    worker = int(re.search(r"stand-in child: working pid=(\d+)", "".join(said))[1])
    wait_until(lambda: not alive(worker), 10)


def test_the_time_limit_counts_from_when_the_request_comes_in(monkeypatch):
    seen = []
    monkeypatch.setattr(artimport, "preview", lambda path, options=None, deadline=None: seen.append(deadline) or {})
    ticket = dispatcher.arrive("art.preview")
    ticket.arrived -= 7  # it waited 7 s for the preview before it to stop
    dispatcher.handle_line(request(1, "x.svg"), ticket)
    assert seen[0].until == pytest.approx(ticket.arrived + artimport.TIME_LIMIT_S)
    assert seen[0].replaced is ticket.replaced


def test_the_engine_gives_up_well_before_the_app_stops_waiting():
    source = (ROOT / "apps" / "desktop" / "src" / "feat" / "importArt.ts").read_text(encoding="utf-8")
    waited_ms = int(re.search(r"export const PREVIEW_MS = ([\d_]+);", source)[1].replace("_", ""))
    assert artimport.TIME_LIMIT_S == 60 and waited_ms >= (artimport.TIME_LIMIT_S + 45) * 1000
