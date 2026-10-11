"""AI providers: one small interface, three ways to answer.

- Off: no model; every feature that needs one hides.
- Ollama: a model running on this computer (or the user's own server), via its HTTP API.
  Models are unloaded right after each answer (keep_alive 0), so they don't hold on to the
  graphics card's memory while you work.
- Cloud: Anthropic, or any OpenAI-compatible service, with the user's own key.

Only the standard library is used for HTTP, so the add-on adds nothing to install.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from . import settings as ai_settings

TIMEOUT_S = 120
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AIError(Exception):
    rpc_code = -32000  # shown to the user as is


@dataclass
class Request:
    """What a feature wants to ask: shown to the user before a cloud call, then sent."""

    system: str
    text: str
    images: list[bytes] = field(default_factory=list)  # PNG
    json_out: bool = False
    max_tokens: int = 1500


class Provider:
    name = "off"
    model = ""
    cloud = False
    capabilities: frozenset[str] = frozenset()

    def ask(self, req: Request) -> str:  # pragma: no cover - Off never gets here
        raise AIError("AI is off. Turn it on in Settings to use this.")


class Off(Provider):
    pass


def _post(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8", "replace")).get("error", "")
            if isinstance(detail, dict):
                detail = detail.get("message", "")
        except (ValueError, OSError):
            pass
        if exc.code in (401, 403):
            raise AIError("The AI service didn't accept the key. Check it in Settings.") from exc
        if exc.code == 404:
            raise AIError(f"The AI service doesn't know that model or address. {detail}".strip()) from exc
        if exc.code == 429:
            raise AIError("The AI service says you've hit a limit; wait a moment and try again.") from exc
        raise AIError(f"The AI service answered with an error ({exc.code}). {detail}".strip()) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AIError(f"Couldn't reach the AI service at {url.split('/v1')[0].split('/api')[0]}. Is it running?") from exc
    except ValueError as exc:
        raise AIError("The AI service sent back something that isn't JSON") from exc


class Ollama(Provider):
    name = "ollama"

    def __init__(self, url: str, model: str) -> None:
        self.url = url.rstrip("/")
        self.model = model
        vision = any(k in model.lower() for k in ("vl", "llava", "vision", "gemma3", "llama4", "minicpm-v", "moondream"))
        self.capabilities = frozenset({"chat", "vision"} if vision else {"chat"})

    def ask(self, req: Request) -> str:
        msg: dict[str, Any] = {"role": "user", "content": req.text}
        if req.images:
            msg["images"] = [base64.b64encode(i).decode("ascii") for i in req.images]
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": req.system}, msg],
            "stream": False,
            "keep_alive": 0,  # free the graphics card as soon as the answer is in
            "options": {"temperature": 0.2, "num_predict": req.max_tokens},
        }
        if req.json_out:
            body["format"] = "json"
        r = _post(f"{self.url}/api/chat", body, {})
        return str((r.get("message") or {}).get("content", ""))


class Anthropic(Provider):
    name = "anthropic"
    cloud = True
    capabilities = frozenset({"chat", "vision"})

    def __init__(self, key: str, model: str, url: str | None = None) -> None:
        self.key, self.model, self.url = key, model, url or ANTHROPIC_URL

    def ask(self, req: Request) -> str:
        content: list[dict[str, Any]] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(i).decode("ascii")}}
            for i in req.images
        ]
        content.append({"type": "text", "text": req.text})
        body = {"model": self.model, "max_tokens": req.max_tokens, "system": req.system,
                "messages": [{"role": "user", "content": content}]}
        r = _post(self.url, body, {"x-api-key": self.key, "anthropic-version": ANTHROPIC_VERSION})
        return "".join(b.get("text", "") for b in r.get("content") or [] if b.get("type") == "text")


class OpenAICompatible(Provider):
    name = "openai"
    cloud = True
    capabilities = frozenset({"chat", "vision"})

    def __init__(self, key: str, model: str, base_url: str) -> None:
        self.key, self.model, self.base_url = key, model, base_url.rstrip("/")

    def ask(self, req: Request) -> str:
        parts: list[dict[str, Any]] = [{"type": "text", "text": req.text}]
        parts += [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(i).decode("ascii")}}
                  for i in req.images]
        body = {"model": self.model, "max_tokens": req.max_tokens, "temperature": 0.2,
                "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": parts}]}
        r = _post(f"{self.base_url}/chat/completions", body, {"authorization": f"Bearer {self.key}"})
        choices = r.get("choices") or [{}]
        return str((choices[0].get("message") or {}).get("content", ""))


def current(feature: str | None = None) -> Provider:
    """The provider the settings choose, or Off (also when the feature is switched off)."""
    s = ai_settings.load()
    if s["mode"] == "off" or (feature and not s["features"].get(feature, False)):
        return Off()
    if s["mode"] == "local":
        return Ollama(s["local"]["url"], s["local"]["model"])
    key = ai_settings.get_key()
    if not key:
        raise AIError("Add your API key in Settings → AI to use the cloud.")
    c = s["cloud"]
    if c["provider"] == "anthropic":
        return Anthropic(key, c["model"])
    return OpenAICompatible(key, c["model"], c["base_url"])


def require(feature: str, capability: str) -> Provider:
    p = current(feature)
    if isinstance(p, Off):
        raise AIError("This needs the AI add-on. Turn it on in Settings → AI (it's off by default).")
    if capability not in p.capabilities:
        raise AIError(f"The model {p.model} can't look at pictures. Choose a vision model in Settings → AI.")
    return p


# ---------------------------------------------------------------- preview and cost


def estimate(req: Request, provider: Provider) -> dict[str, Any]:
    """What will be sent and roughly what it costs, for the "before you send" check."""
    tokens_in = (len(req.system) + len(req.text)) // 4 + 1100 * len(req.images)  # about 1,100 per small picture
    s = ai_settings.load()["cloud"]
    cost = None
    if provider.cloud and s.get("price_in") is not None and s.get("price_out") is not None:
        cost = round((tokens_in * float(s["price_in"]) + req.max_tokens * float(s["price_out"])) / 1_000_000, 4)
    return {
        "provider": provider.name,
        "model": provider.model,
        "cloud": provider.cloud,
        "text": req.text,
        "images": [{"bytes": len(i), "data_url": "data:image/png;base64," + base64.b64encode(i).decode("ascii")} for i in req.images],
        "tokens_in": tokens_in,
        "tokens_out_max": req.max_tokens,
        "cost_usd_max": cost,
    }


def extract_json(text: str) -> Any:
    """The JSON object in a model's answer (models sometimes wrap it in ``` fences or prose)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise AIError("The model's answer wasn't in the expected form, so nothing was changed. Try again.")
    try:
        return json.loads(text[start:end + 1])
    except ValueError as exc:
        raise AIError("The model's answer wasn't in the expected form, so nothing was changed. Try again.") from exc


def test_connection() -> dict[str, Any]:
    """A tiny question to check the settings work."""
    p = current()
    if isinstance(p, Off):
        raise AIError("AI is off")
    answer = p.ask(Request(system="Reply with the single word: ready", text="Are you there?", max_tokens=10))
    return {"ok": bool(answer.strip()), "provider": p.name, "model": p.model, "vision": "vision" in p.capabilities}
