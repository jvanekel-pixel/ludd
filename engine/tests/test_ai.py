"""M9: the AI add-on. All model calls go to a fake server on this computer; no real service, no key."""

import io
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from threadline_engine import methods
from threadline_engine.ai import advisor, help, providers, settings
from threadline_engine.ai.providers import AIError, Request
from threadline_engine.rpc import Dispatcher


def sq(x0, y0, x1, y1):
    return [[x0, y0, "c"], [x1, y0, "c"], [x1, y1, "c"], [x0, y1, "c"]]


LAYOUT = {"items": [
    {"id": "big", "kind": "fill", "geometry": {"outline": sq(0, 0, 40, 30)}, "params": {"angle_deg": 45, "spacing_mm": 0.4}},
    {"id": "thin", "kind": "fill", "geometry": {"outline": sq(0, 40, 40, 42)}, "params": {}},
    {"id": "col", "kind": "satin", "params": {},
     "geometry": {"rail_a": [[0, 50, "c"], [30, 50, "c"]], "rail_b": [[0, 54, "c"], [30, 54, "c"]]}},
]}


class Fake:
    """A pretend AI service: records what it was sent and answers with `reply`."""

    def __init__(self, reply_for):
        self.reply_for = reply_for
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                fake.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
                status, payload = fake.reply_for(self.path, body)
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


ADVICE = {
    "objects": [
        {"id": "big", "stitch_type": "fill", "angle_deg": 135, "density": "normal", "underlay": None, "reason": "Turn the angle so it differs from its neighbour."},
        {"id": "thin", "stitch_type": "satin", "angle_deg": None, "density": None, "underlay": None, "reason": "Only 2 mm wide: a satin looks smoother."},
        {"id": "col", "stitch_type": "satin", "angle_deg": None, "density": None, "underlay": None, "reason": "Already right."},
        {"id": "ghost", "stitch_type": "fill", "reason": "Not a shape that was sent."},
        {"id": "big", "stitch_type": "zigzag", "reason": "Not a stitch type."},
    ],
    "order": ["thin", "big", "col"],
    "order_reason": "Sew the thin shape first, under the big one.",
}


@pytest.fixture
def ollama():
    def reply(path, body):
        if path != "/api/chat":
            return 404, {"error": "no"}
        user = body["messages"][-1]
        content = json.dumps(ADVICE) if body.get("format") == "json" else "ready"
        if "Guide sections" in user["content"]:
            content = "Turn on Have the machine cut jump threads in Save for machine."
        return 200, {"message": {"role": "assistant", "content": content}}

    f = Fake(reply)
    settings.save({"mode": "local", "local": {"url": f.url, "model": "qwen2.5vl:7b"}})
    yield f
    f.close()


# ---------------------------------------------------------------- off by default, no network


def test_ai_is_off_by_default_and_never_touches_the_network(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network used with AI off")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    assert settings.public()["mode"] == "off"
    with pytest.raises(AIError, match="off by default"):
        advisor.advise(LAYOUT, [], None)
    r = help.ask("how do I cut jump threads")
    assert r["answer"] is None and r["sections"][0]["title"].startswith("Cutting jump threads")


def test_a_feature_switched_off_stays_off(ollama):
    settings.save({"features": {"advisor": False}})
    with pytest.raises(AIError, match="needs the AI add-on"):
        advisor.advise(LAYOUT, [], None)
    assert not ollama.requests


# ---------------------------------------------------------------- settings and the key


def test_settings_merge_and_check():
    s = settings.save({"mode": "cloud", "cloud": {"model": "claude-haiku-5-5"}})
    assert s["cloud"]["model"] == "claude-haiku-5-5" and s["cloud"]["provider"] == "anthropic"
    with pytest.raises(settings.AISettingsError):
        settings.save({"mode": "sometimes"})
    with pytest.raises(settings.AISettingsError):
        settings.save({"local": {"url": "ftp://x"}})


def test_key_is_stored_scrambled_and_never_shown():
    settings.set_key("sk-test-1234")
    assert settings.get_key() == "sk-test-1234"
    assert b"sk-test-1234" not in settings._key_file().read_bytes() or not settings._key_file().read_bytes().startswith(b"DPAPI")
    pub = settings.public()
    assert pub["has_key"] is True and "sk-test-1234" not in json.dumps(pub)
    settings.set_key(None)
    assert settings.public()["has_key"] is False


def test_cloud_without_a_key_explains():
    settings.save({"mode": "cloud"})
    with pytest.raises(AIError, match="API key"):
        providers.current()


# ---------------------------------------------------------------- providers


def test_ollama_gets_pictures_json_and_unloads(ollama):
    r = advisor.advise(LAYOUT, [], None)
    body = ollama.requests[-1]["body"]
    assert body["keep_alive"] == 0 and body["format"] == "json" and len(body["messages"][-1]["images"]) == 3
    assert r["proposals"]


def test_anthropic_request_shape():
    seen = {}

    def reply(path, body):
        seen.update(body)
        return 200, {"content": [{"type": "text", "text": "ready"}]}

    f = Fake(reply)
    try:
        p = providers.Anthropic("k", "claude-sonnet-5-5", url=f.url + "/v1/messages")
        assert p.ask(Request(system="s", text="hi", images=[b"\x89PNG"])) == "ready"
        assert f.requests[-1]["headers"]["x-api-key"] == "k"
        assert seen["messages"][0]["content"][0]["type"] == "image" and seen["system"] == "s"
    finally:
        f.close()


def test_openai_compatible_and_errors():
    def reply(path, body):
        if body["model"] == "bad":
            return 401, {"error": {"message": "invalid key"}}
        return 200, {"choices": [{"message": {"content": "ready"}}]}

    f = Fake(reply)
    try:
        assert providers.OpenAICompatible("k", "m", f.url + "/v1").ask(Request("s", "hi")) == "ready"
        assert f.requests[-1]["path"] == "/v1/chat/completions"
        with pytest.raises(AIError, match="didn't accept the key"):
            providers.OpenAICompatible("k", "bad", f.url + "/v1").ask(Request("s", "hi"))
    finally:
        f.close()
    with pytest.raises(AIError, match="Couldn't reach"):
        providers.Ollama("http://127.0.0.1:9", "m").ask(Request("s", "hi"))


def test_json_is_found_inside_fences_and_prose():
    assert providers.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert providers.extract_json('Sure! {"a": 2} Hope that helps.') == {"a": 2}
    with pytest.raises(AIError, match="expected form"):
        providers.extract_json("no json here")


def test_estimate_shows_what_is_sent_and_cost_only_with_prices():
    settings.save({"mode": "cloud", "cloud": {"price_in": 3.0, "price_out": 15.0}})
    req = Request(system="s" * 400, text="t" * 400, images=[b"x" * 10], max_tokens=1000)
    p = providers.Anthropic("k", "claude-sonnet-5-5")
    e = providers.estimate(req, p)
    assert e["text"] == req.text and len(e["images"]) == 1 and e["cloud"]
    assert e["cost_usd_max"] == pytest.approx((e["tokens_in"] * 3 + 1000 * 15) / 1e6, abs=1e-4)
    settings.save({"cloud": {"price_in": None}})
    assert providers.estimate(req, p)["cost_usd_max"] is None


# ---------------------------------------------------------------- Stitch Advisor


def test_advisor_keeps_only_valid_changes():
    out = advisor.validate(ADVICE, LAYOUT["items"])
    by = {p["id"]: p for p in out["proposals"]}
    assert by["big"]["change"] == {"angle_deg": 135}  # density already normal: not proposed
    assert by["thin"]["change"]["stitch_type"] == "satin"
    assert "col" not in by  # no change
    assert out["dropped"] == 2  # an unknown shape, a made-up stitch type
    assert out["order"]["ids"] == ["thin", "big", "col"]


def test_advisor_rejects_a_bad_answer_and_a_bad_order():
    with pytest.raises(AIError, match="expected form"):
        advisor.validate({"suggestions": []}, LAYOUT["items"])
    out = advisor.validate({"objects": [], "order": ["big", "big", "col"]}, LAYOUT["items"])
    assert out["order"] is None and out["dropped"] == 1


def test_advisor_sees_the_picture_under_the_shape(tmp_path):
    pic = tmp_path / "pic.png"
    Image.new("RGB", (100, 100), (0, 200, 0)).save(pic)
    images = [{"path": str(pic), "x": 20, "y": 15, "width_mm": 60, "height_mm": 60, "rotate": 0, "visible": True}]
    png = advisor.render_crop(LAYOUT["items"][0], images)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert max(im.size) <= advisor.CROP_PX
    assert im.getpixel((im.width // 2, im.height // 2)) == (0, 200, 0)  # the green picture, not a blank


def test_advisor_summary_numbers():
    s = advisor.summarize(LAYOUT["items"][2])
    assert s["column_width_mm"]["typical"] == pytest.approx(4, abs=0.1)
    f = advisor.summarize(LAYOUT["items"][0])
    assert f["size_mm"] == [40, 30] and f["widest_mm"] == pytest.approx(30, abs=0.5)


# ---------------------------------------------------------------- Help


def test_help_answers_from_the_guide(ollama):
    r = help.ask("How do I stop cutting jump threads by hand?")
    assert r["ai"] and "cut jump threads" in r["answer"]
    sent = ollama.requests[-1]["body"]["messages"][-1]["content"]
    assert "Cutting jump threads" in sent  # the matching guide section went with the question


def test_help_search_finds_topics():
    assert help.search("too big for my hoop")[0]["title"].startswith("Hoop too small")
    assert help.search("which stabilizer for a t-shirt")[0]["title"] == "Fabric and stabilizer"
    assert help.search("") == []


# ---------------------------------------------------------------- engine stays responsive


def test_background_methods_answer_without_blocking():
    d = Dispatcher()
    gate = threading.Event()

    @d.method("slow", background=True)
    def slow():
        gate.wait(5)
        return "slow"

    @d.method("fast")
    def fast():
        gate.set()
        return "fast"

    out = io.StringIO()
    lines = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "slow"}) + "\n"
                        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "fast"}) + "\n")
    d.serve(lines, out)
    for _ in range(50):
        if out.getvalue().count("\n") == 2:
            break
        threading.Event().wait(0.05)
    answers = [json.loads(l) for l in out.getvalue().splitlines()]
    assert [a["id"] for a in answers] == [2, 1]  # the fast one wasn't held up


def test_rpc_methods_registered():
    for m in ("ai.settings", "ai.save_settings", "ai.set_key", "ai.test", "ai.advisor_preview", "ai.advise", "help.search", "help.ask"):
        assert m in methods.dispatcher._methods
