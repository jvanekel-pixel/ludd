import json
import subprocess
import sys

from threadline_engine.methods import dispatcher


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
