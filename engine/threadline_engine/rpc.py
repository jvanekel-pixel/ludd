"""Minimal JSON-RPC 2.0 server over newline-delimited stdio.

One JSON object per line in, one per line out. Logs go to stderr so stdout
stays a clean protocol channel.
"""

from __future__ import annotations

import inspect
import json
import sys
import threading
import time
import traceback
from typing import Any, Callable, TextIO

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# Expected, user-facing failures (bad file, unsupported format). Exceptions opt in via `rpc_code`.
APP_ERROR = -32000
# The answer to a newest-wins request that a newer one replaced (the app has stopped waiting for it).
REPLACED = "A newer preview replaced this one."

Handler = Callable[..., Any]


class Replaced(Exception):
    """A newest-wins request that a newer one replaced before it could run."""

    rpc_code = APP_ERROR

    def __init__(self) -> None:
        super().__init__(REPLACED)


class Ticket:
    """One request to a newest-wins method: when it came in, and whether a newer one has replaced
    it (the method that is running checks `replaced` and stops)."""

    def __init__(self) -> None:
        self.arrived = time.monotonic()
        self.replaced = threading.Event()


class _Newest:
    """A newest-wins method: the newest request's ticket, and the lock the running one holds."""

    def __init__(self) -> None:
        self.running = threading.Lock()
        self.guard = threading.Lock()  # around `latest`
        self.latest: Ticket | None = None


class Dispatcher:
    def __init__(self) -> None:
        self._methods: dict[str, Handler] = {}
        # Slow methods (AI calls over the network) answer from a thread, so the canvas keeps working.
        self._background: set[str] = set()
        self._newest: dict[str, _Newest] = {}
        self._here = threading.local()  # .ticket: the one of the request this thread is running
        # Set by engine.shutdown: stop reading once the current answer is sent.
        self.stopping = False
        # Held while a method runs on the main loop. A background method takes it around any part
        # that uses the engine's shared caches (render's), so the two never touch them at once.
        self.lock = threading.RLock()

    def method(self, name: str, background: bool = False, newest_wins: bool = False) -> Callable[[Handler], Handler]:
        """`newest_wins` (a background method): only one of its requests runs at a time, and a new
        one replaces all the older ones. The one running is told through its ticket(), and one still
        waiting is answered as replaced without running."""

        def register(fn: Handler) -> Handler:
            self._methods[name] = fn
            if background or newest_wins:
                self._background.add(name)
            if newest_wins:
                self._newest[name] = _Newest()
            return fn

        return register

    def ticket(self) -> Ticket | None:
        """The ticket of the newest-wins request this thread is running (None otherwise)."""
        return getattr(self._here, "ticket", None)

    def arrive(self, name: str) -> Ticket | None:
        """A new request for `name` is here: for a newest-wins method, its ticket, and every older
        request is replaced. (Others get None.)"""
        state = self._newest.get(name)
        if state is None:
            return None
        ticket = Ticket()
        with state.guard:
            if state.latest is not None:
                state.latest.replaced.set()
            state.latest = ticket
        return ticket

    def is_background(self, line: str) -> bool:
        return self._background_name(line) is not None

    def _background_name(self, line: str) -> str | None:
        """The method of a request line that is answered from a thread, else None."""
        try:
            req = json.loads(line)
        except (ValueError, RecursionError):  # handle_line answers it with a parse error
            return None
        method = req.get("method") if isinstance(req, dict) else None
        return method if isinstance(method, str) and method in self._background else None

    def handle_line(self, line: str, ticket: Ticket | None = None) -> dict[str, Any] | None:
        """Handle one request line. Returns the response, or None for notifications.
        Never raises: whatever goes wrong becomes an error answer, and the engine keeps serving.
        `ticket`: from arrive(), for a newest-wins request (one is made here if not given)."""
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
            result = self._run(method, fn, args, kwargs, ticket)
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

    def _run(self, name: str, fn: Handler, args, kwargs, ticket: Ticket | None) -> Any:
        state = self._newest.get(name)
        if state is None:
            return fn(*args, **kwargs)
        ticket = ticket or self.arrive(name)  # handle_line called directly: it arrives now
        while not state.running.acquire(timeout=0.05):
            if ticket.replaced.is_set():
                raise Replaced()
        try:
            if ticket.replaced.is_set():
                raise Replaced()
            before, self._here.ticket = self.ticket(), ticket
            try:
                return fn(*args, **kwargs)
            finally:
                self._here.ticket = before
        finally:
            state.running.release()

    def respond(self, line: str, ticket: Ticket | None = None) -> str | None:
        """The answer to one request line as one line of strict JSON (no NaN), or None."""
        try:
            resp = self.handle_line(line, ticket)
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

        def answer(line: str, ticket: Ticket | None = None) -> None:
            text = self.respond(line, ticket)
            if text is not None:
                with lock:  # responses may finish out of order; each is one whole line
                    stdout.write(text + "\n")
                    stdout.flush()

        running: list[threading.Thread] = []
        for line in stdin:
            if not line.strip():
                continue
            if (name := self._background_name(line)) is not None:
                # Its ticket is taken here, on the reading thread, so requests replace each other
                # in the order they came in, whichever thread gets going first.
                t = threading.Thread(target=answer, args=(line, self.arrive(name)), daemon=True)
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
