"""Minimal JSON-RPC 2.0 server over newline-delimited stdio.

One JSON object per line in, one per line out. Logs go to stderr so stdout
stays a clean protocol channel.
"""

from __future__ import annotations

import json
import sys
import threading
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
        except json.JSONDecodeError:
            return False
        return isinstance(req, dict) and req.get("method") in self._background

    def handle_line(self, line: str) -> dict[str, Any] | None:
        """Handle one request line. Returns the response, or None for notifications."""
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, PARSE_ERROR, f"Parse error: {exc.msg}")

        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
            return _error(req.get("id") if isinstance(req, dict) else None, INVALID_REQUEST, "Invalid request")

        req_id = req.get("id")
        is_notification = "id" not in req
        fn = self._methods.get(req["method"])
        if fn is None:
            return None if is_notification else _error(req_id, METHOD_NOT_FOUND, f"Method not found: {req['method']}")

        params = req.get("params", {})
        try:
            if isinstance(params, list):
                result = fn(*params)
            elif isinstance(params, dict):
                result = fn(**params)
            else:
                return _error(req_id, INVALID_PARAMS, "params must be an array or object")
        except TypeError as exc:
            return None if is_notification else _error(req_id, INVALID_PARAMS, str(exc))
        except Exception as exc:  # noqa: BLE001 - report every engine failure to the UI
            code = getattr(exc, "rpc_code", INTERNAL_ERROR)
            if code == INTERNAL_ERROR:
                print(f"engine error in {req['method']}: {exc!r}", file=sys.stderr, flush=True)
            return None if is_notification else _error(req_id, code, str(exc))

        return None if is_notification else {"jsonrpc": "2.0", "id": req_id, "result": result}

    def serve(self, stdin: TextIO, stdout: TextIO) -> None:
        lock = threading.Lock()

        def answer(line: str) -> None:
            resp = self.handle_line(line)
            if resp is not None:
                with lock:  # responses may finish out of order; each is one whole line
                    stdout.write(json.dumps(resp) + "\n")
                    stdout.flush()

        running: list[threading.Thread] = []
        for line in stdin:
            if not line.strip():
                continue
            if self.is_background(line):
                t = threading.Thread(target=answer, args=(line,), daemon=True)
                t.start()
                running.append(t)
            else:
                answer(line)
        # Input closed: give answers already on their way a moment to finish.
        for t in running:
            t.join(timeout=10)


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
