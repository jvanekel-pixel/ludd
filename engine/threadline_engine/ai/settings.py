"""AI settings: off, local (Ollama) or cloud (the user's own key), and which features are on.

Settings live in the user's data folder (ai.json). The API key is kept apart (ai-key.bin) and, on
Windows, encrypted for the signed-in user with DPAPI; the UI only ever learns whether one is set.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..storage import data_dir

DEFAULTS: dict[str, Any] = {
    "mode": "off",  # off | local | cloud
    "local": {"url": "http://localhost:11434", "model": "qwen2.5vl:7b"},
    "cloud": {
        "provider": "anthropic",  # anthropic | openai (any OpenAI-compatible service)
        "model": "claude-sonnet-5-5",
        "base_url": "https://api.openai.com/v1",
        # Optional, for the cost estimate shown before sending: the provider's price per million tokens.
        "price_in": None,
        "price_out": None,
    },
    "features": {"advisor": True, "help": True},
}
MODES = ("off", "local", "cloud")
CLOUD_PROVIDERS = ("anthropic", "openai")


class AISettingsError(Exception):
    rpc_code = -32000


def _file() -> Path:
    return data_dir() / "ai.json"


def _key_file() -> Path:
    return data_dir() / "ai-key.bin"


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in (over or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        elif k in out:
            out[k] = v
    return out


def load() -> dict[str, Any]:
    try:
        saved = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        saved = {}
    return _merge(DEFAULTS, saved if isinstance(saved, dict) else {})


def public() -> dict[str, Any]:
    """Settings for the UI: never the key itself."""
    s = load()
    s["has_key"] = get_key() is not None
    return s


def save(patch: dict[str, Any]) -> dict[str, Any]:
    s = _merge(load(), patch or {})
    if s["mode"] not in MODES:
        raise AISettingsError(f"Unknown AI setting: {s['mode']}")
    if s["cloud"]["provider"] not in CLOUD_PROVIDERS:
        raise AISettingsError(f"Unknown AI service: {s['cloud']['provider']}")
    for url in (s["local"]["url"], s["cloud"]["base_url"]):
        if not str(url).startswith(("http://", "https://")):
            raise AISettingsError(f"That address doesn't look right: {url}")
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=1), encoding="utf-8")
    return public()


# ---------------------------------------------------------------- the API key


def set_key(key: str | None) -> dict[str, Any]:
    f = _key_file()
    if not key:
        f.unlink(missing_ok=True)
        return public()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(_protect(key.strip().encode("utf-8")))
    if sys.platform != "win32":
        os.chmod(f, 0o600)
    return public()


def get_key() -> str | None:
    try:
        data = _key_file().read_bytes()
    except OSError:
        return None
    try:
        return _unprotect(data).decode("utf-8") or None
    except (OSError, ValueError):
        return None


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out))  # 0x1: no UI
    if not ok:
        raise OSError("Couldn't read the saved key; enter it again")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def _protect(data: bytes) -> bytes:
    if sys.platform == "win32":
        return b"DPAPI" + _dpapi(data, True)
    return b"PLAIN" + base64.b64encode(data)  # file is readable by this user only (chmod 600)


def _unprotect(data: bytes) -> bytes:
    if data.startswith(b"DPAPI") and sys.platform == "win32":
        return _dpapi(data[5:], False)
    if data.startswith(b"PLAIN"):
        return base64.b64decode(data[5:])
    raise ValueError("unknown key format")
