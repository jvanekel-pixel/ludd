"""Minimal JSON-RPC 2.0 server over newline-delimited stdio.

One JSON object per line in, one per line out. Logs go to stderr so stdout
stays a clean protocol channel.
"""

from __future__ import annotations

import inspect
import json
import sys
import threading
import traceback
from typing import Any, Callable, TextIO

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# Expected, user-facing failures (bad file, unsupported format). Exceptions opt in via `rpc_code`.
APP_ERROR = -32000

Handler = Callable[..., Any]


class Dispatcher:
    def __init__(self) -> None:
        self._methods: dict[str, Handler] = {}
        # Slow methods (AI calls over the network) answer from a thread, so the canvas keeps working.
        self._background: set[str] = set()
        # Set by engine.shutdown: stop reading once the current answer is sent.
        self.stopping = False
        # Held while a method runs on the main loop. A background method takes it around any part
        # that uses the engine's shared caches (render's), so the two never touch them at once.
        self.lock = threading.RLock()

    def method(self, name: str, background: bool = False) -> Callable[[Handler], Handler]:
        def register(fn: Handler) -> Handler:
            self._methods[name] = fn
            if background:
                self._background.add(name)
            return fn

        return register

    def is_background(self, line: str) -> bool:
        try:
            req = json.loads(line)
        except (ValueError, RecursionError):  # handle_line answers it with a parse error
            return False
        return isinstance(req, dict) and req.get("method") in self._background

    def handle_line(self, line: str) -> dict[str, Any] | None:
        """Handle one request line. Returns the response, or None for notifications.
        Never raises: whatever goes wrong becomes an error answer, and the engine keeps serving."""
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, PARSE_ERROR, f"Parse error: {exc.msg}")
        except (ValueError, RecursionError) as exc:  # numbers over 4300 digits, nesting too deep
            return _error(None, PARSE_ERROR, f"Parse error: {type(exc).__name__}")

        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
            rid = req.get("id") if isinstance(req, dict) else None
            return _error(rid if _valid_id(rid) else None, INVALID_REQUEST, "Invalid request")

        req_id = req.get("id") if _valid_id(req.get("id")) else None
        is_notification = "id" not in req
        method = req["method"]
        fn = self._methods.get(method)
        if fn is None:
            return None if is_notification else _error(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        params = req.get("params", {})
        if not isinstance(params, (list, dict)):
            return None if is_notification else _error(req_id, INVALID_PARAMS, "params must be an array or object")
        args, kwargs = (params, {}) if isinstance(params, list) else ([], params)
        try:
            # Wrong or missing parameter names are the caller's mistake; a TypeError from inside
            # the method is a bug in the engine and is reported (and logged) as one.
            inspect.signature(fn).bind(*args, **kwargs)
        except TypeError as exc:
            return None if is_notification else _error(req_id, INVALID_PARAMS, f"{method}: {exc}")
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - report every engine failure to the UI
            code = getattr(exc, "rpc_code", INTERNAL_ERROR)
            if code == INTERNAL_ERROR:
                print(f"engine error in {method}:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
                message = _unexpected(method, exc)
            else:
                message = str(exc)
            return None if is_notification else _error(req_id, code, message)

        return None if is_notification else {"jsonrpc": "2.0", "id": req_id, "result": result}

    def respond(self, line: str) -> str | None:
        """The answer to one request line as one line of strict JSON (no NaN), or None."""
        try:
            resp = self.handle_line(line)
            if resp is None:
                return None
            try:
                return json.dumps(resp, allow_nan=False)
            except (TypeError, ValueError, RecursionError) as exc:  # NaN, numpy numbers, sets...
                print(f"engine error: result can't be sent: {exc!r}", file=sys.stderr, flush=True)
                return json.dumps(_error(resp.get("id"), INTERNAL_ERROR, _unexpected("answer", exc)))
        except Exception as exc:  # noqa: BLE001 - one bad line must never stop the engine
            print(f"engine error answering a request: {exc!r}", file=sys.stderr, flush=True)
            return json.dumps(_error(None, INTERNAL_ERROR, "Something went wrong in LUDD's engine. Please report this."))

    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        lock = threading.Lock()

        def answer(line: str) -> None:
            text = self.respond(line)
            if text is not None:
                with lock:  # responses may finish out of order; each is one whole line
                    stdout.write(text + "\n")
                    stdout.flush()

        running: list[threading.Thread] = []
        for line in stdin:
            if not line.strip():
                continue
            if self.is_background(line):
                t = threading.Thread(target=answer, args=(line,), daemon=True)
                t.start()
                running = [r for r in running if r.is_alive()] + [t]
            else:
                with self.lock:
                    answer(line)
            if self.stopping:
                break
        # Input closed (or asked to stop): give answers already on their way a moment to finish.
        for t in running:
            t.join(timeout=1 if self.stopping else 10)


def _valid_id(v: Any) -> bool:
    """JSON-RPC ids are strings, numbers or null; anything else isn't echoed back."""
    return v is None or (isinstance(v, (str, int, float)) and not isinstance(v, bool))


def _unexpected(method: str, exc: BaseException) -> str:
    """A plain message for an engine bug (the traceback goes to the log)."""
    if isinstance(exc, KeyError) and exc.args:
        detail = f"something is missing ({exc.args[0]})"
    else:
        detail = str(exc) or type(exc).__name__
    return f"Something went wrong in LUDD's engine ({method}: {detail[:200]}). Please report this."


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
