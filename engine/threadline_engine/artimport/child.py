"""Artwork import's steps that can't be stopped, run in a one-use child process.

PDFium reads a page in one native call that can't be stopped, and a PDF of a few kilobytes can ask
it for gigabytes (forms inside forms, a compressed page that unpacks to millions of shapes). GEOS can
take as long over the outline of a wide line that doubles back on itself. So each PDF is read, and a
drawing's big wide strokes are outlined, by a copy of the engine started in a private mode
(WORKER_FLAG). The engine kills it at the time limit, or when a newer preview replaces this one; it
ends itself above CHILD_MEMORY (where the system can say how much it uses) and when the engine ends;
and a file that crashes a library crashes only the child. PDFium never runs in the engine itself.

The request goes in on the child's own stdin (a line of JSON, then the job's data) and the answer
comes back on its own stdout, as JSON (never pickle: the child has been working on an untrusted
file). Whatever else the child writes goes to stderr, which is the engine's log. It never gets the
engine's stdin or stdout, which carry the app's requests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from . import ArtError, Deadline, Options
from .model import Drawing, Item, Skipped, Subpath

# The engine's one command-line option: be this child (__main__.py refuses any other).
WORKER_FLAG = "--ludd-artwork-worker"
CHILD_MEMORY = 2 * 1024**3  # the child ends itself above this
MEMORY_EXIT = 77  # ... with this exit code
ENGINE_GONE_EXIT = 78  # it ends with this once the engine has ended
WATCH_S = 0.05  # how often it looks
POLL_S = 0.05  # how often the engine looks while it waits
EXIT_GRACE_S = 5.0  # after its answer is in, how long it has to end by itself
MAX_ANSWER = 256 * 1024 * 1024  # far more than the largest answer there is

PDF_TOO_MUCH_MEMORY = ("This PDF takes more memory to read than LUDD allows. Simplify it in your drawing program "
                       "(fewer shapes and copies), or save just the part you want as its own PDF, and import that.")
PDF_NO_ANSWER = ("LUDD couldn't read this PDF: it may be damaged or too complex. Save or export it again, simpler if "
                 "you can, and import that.")
_WIDE_LINE_FIX = ("Set a smaller Width, set Lines as to Running stitch, or turn that line into a shape in your "
                  "drawing program.")
OUTLINE_TOO_MUCH_MEMORY = "This drawing has a very wide line that takes too much memory to outline. " + _WIDE_LINE_FIX
OUTLINE_NO_ANSWER = "LUDD couldn't outline a very wide line in this drawing. " + _WIDE_LINE_FIX
NOT_STARTED = ("LUDD couldn't start its helper program for reading this drawing. Close some other programs and try "
               "again. If it still doesn't work, restart LUDD.")


# ---------------------------------------------------------------- in the engine


def worker_command() -> list[str]:
    """The engine itself as the child: the packaged engine runs its own program again, the engine
    from source this Python on the same engine code."""
    if getattr(sys, "frozen", False):
        return [sys.executable, WORKER_FLAG]
    return [sys.executable, "-m", "threadline_engine", WORKER_FLAG]


def worker_env() -> dict[str, str]:
    env = dict(os.environ)  # (the packaged program finds its unpacked files by these, and reuses them)
    if not getattr(sys, "frozen", False):
        here = str(Path(__file__).resolve().parents[2])  # the folder that holds this threadline_engine
        env["PYTHONPATH"] = os.pathsep.join(p for p in (here, env.get("PYTHONPATH")) if p)
    return env


def read_pdf(data: bytes, opts: Options, deadline: Deadline) -> Drawing:
    """pdf._read(data, opts), run in a child process that never outlives `deadline`."""
    reply = _ask({"job": "pdf", "options": asdict(opts)}, data, deadline, PDF_TOO_MUCH_MEMORY, PDF_NO_ANSWER)
    try:
        return from_wire(reply["drawing"])
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        raise ArtError(PDF_NO_ANSWER) from None


def outline_strokes(strokes: list[dict], deadline: Deadline) -> list:
    """What each of these wide strokes ({lines, width, cap, join, miter_limit}) covers, as GEOS
    geometry (widestroke.union), worked out in one child process that never outlives `deadline`."""
    import shapely

    data = json.dumps(strokes, allow_nan=False, separators=(",", ":")).encode()
    reply = _ask({"job": "outline"}, data, deadline, OUTLINE_TOO_MUCH_MEMORY, OUTLINE_NO_ANSWER)
    try:
        painted = [shapely.from_wkb(text) for text in reply["painted"]]  # exact: WKB keeps every number whole
        if len(painted) != len(strokes):
            raise ValueError("not an outline for each stroke")
    except (ValueError, KeyError, TypeError, shapely.errors.GEOSException):
        raise ArtError(OUTLINE_NO_ANSWER) from None
    return painted


def _ask(job: dict, data: bytes, deadline: Deadline, too_much_memory: str, no_answer: str) -> dict:
    """The child's reply to one job, or ArtError with why there is none."""
    deadline.check()
    request = {**job, "size": len(data), "seconds": deadline.left(), "memory": CHILD_MEMORY, "engine": os.getpid()}
    answer, code = _run(worker_command(), json.dumps(request).encode() + b"\n", data, deadline)
    if code == MEMORY_EXIT:
        raise ArtError(too_much_memory)
    try:
        reply = json.loads(answer)
        if "refused" in reply:
            raise ArtError(str(reply["refused"]))
        return reply
    except (ValueError, TypeError):
        print(f"artwork import: the {job['job']} child ended with code {code} and no answer", file=sys.stderr,
              flush=True)
        raise ArtError(no_answer) from None


def _run(command: list[str], request: bytes, data: bytes, deadline: Deadline) -> tuple[bytes, int]:
    """(what the child wrote to its stdout, its exit code). The child is dead when this returns or
    raises, whether it ended by itself or the deadline (or a newer preview) ended it."""
    try:
        # CREATE_NO_WINDOW: no console window flashes up on Windows.
        child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=worker_env(),
                                 creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except OSError as exc:
        print(f"artwork import: the child didn't start: {exc}", file=sys.stderr, flush=True)
        raise ArtError(NOT_STARTED) from None
    answer: list[bytes] = []

    def send() -> None:
        try:
            child.stdin.write(request)
            child.stdin.write(data)
            child.stdin.close()
        except (OSError, ValueError):
            pass  # it ended first; its exit code says why

    def receive() -> None:
        size = 0
        try:
            while chunk := child.stdout.read(1 << 20):
                size += len(chunk)
                if size > MAX_ANSWER:
                    answer.clear()  # no real answer is this big: it counts as none
                    return
                answer.append(chunk)
        except (OSError, ValueError):
            pass

    # Threads, so a child that reads or writes nothing can't hold the engine past the deadline.
    sender, receiver = threading.Thread(target=send, daemon=True), threading.Thread(target=receive, daemon=True)
    try:
        sender.start()
        receiver.start()
        while receiver.is_alive():
            deadline.check()
            receiver.join(POLL_S)
        try:
            child.wait(EXIT_GRACE_S)  # the whole answer is in
        except subprocess.TimeoutExpired:
            pass
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()
        for thread in (sender, receiver):
            if thread.ident is not None:
                thread.join(5)
        for pipe in (child.stdin, child.stdout):
            try:
                pipe.close()
            except (OSError, ValueError):
                pass
    return b"".join(answer), child.returncode


# ---------------------------------------------------------------- the PDF's drawing, there and back


def to_wire(drawing: Drawing) -> dict:
    items = [{**vars(item), "subpaths": [[sub.start, sub.segments, sub.closed] for sub in item.subpaths]}
             for item in drawing.items]
    return {"items": items, "skipped": dict(drawing.skipped), "scale_note": drawing.scale_note, "pages": drawing.pages}


def from_wire(wire: dict) -> Drawing:
    """to_wire's drawing back, exactly (JSON carries every float whole); points and segments are
    tuples again."""

    def point(p) -> tuple[float, float]:
        return (p[0], p[1])

    items = []
    for fields in wire["items"]:
        subpaths = [Subpath(point(start), [(segment[0], *map(point, segment[1:])) for segment in segments], closed)
                    for start, segments, closed in fields.pop("subpaths")]
        items.append(Item(subpaths, **fields))
    skipped = Skipped()
    for what, count in wire["skipped"].items():
        skipped.add(what, count)
    return Drawing(items, skipped, wire["scale_note"], wire["pages"])


# ---------------------------------------------------------------- in the child


def _no_version_command() -> None:
    """pypdfium2 and shapely ask platform.system() as they load, and on some Windows computers
    Python answers by running "cmd /c ver". So the child, which starts no other program, answers
    that without it: Python then takes the version from sys.getwindowsversion()."""
    import platform

    platform._syscmd_ver = lambda system="", release="", version="", supported_platforms=(): (system, release, version)


def _pdf_job(request: dict, data: bytes, deadline: Deadline) -> dict:
    from . import pdf

    return {"drawing": to_wire(pdf._read(data, Options(**request["options"]), deadline))}


def _outline_job(request: dict, data: bytes, deadline: Deadline) -> dict:
    import shapely

    from . import widestroke

    painted = []
    for stroke in json.loads(data):
        deadline.check()
        painted.append(shapely.to_wkb(widestroke.union(**stroke), hex=True))
    return {"painted": painted}


_JOBS = {"pdf": _pdf_job, "outline": _outline_job}


def main() -> int:
    """The child: takes one job, does it, writes one answer, and ends. Returns its exit code."""
    # The answer goes out on a copy of stdout. Anything else written to stdout from here on (by
    # PDFium, say) goes to stderr, so it can't spoil the answer.
    answer_to = os.dup(1)
    try:
        os.dup2(2, 1)
    except OSError:  # no stderr at all
        os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
    sys.stdout = sys.stderr
    line = sys.stdin.buffer.readline(65536)
    try:
        request = json.loads(line)
        job = _JOBS[request["job"]]
        size, seconds = int(request["size"]), float(request["seconds"])
        memory, engine = int(request["memory"]), int(request["engine"])
    except (ValueError, KeyError, TypeError):
        # Anything else (the app's JSON-RPC, say) isn't answered.
        print("artwork child: not a job from LUDD's engine", file=sys.stderr, flush=True)
        return 2
    watch(engine, memory)  # before any of the file is looked at
    _no_version_command()  # before any library loads
    data = sys.stdin.buffer.read(size)
    if len(data) != size:
        return 2  # the engine ended while it was sending the job
    try:
        reply = job(request, data, Deadline(seconds))
    except ArtError as exc:
        reply = {"refused": str(exc)}
    except MemoryError:
        os._exit(MEMORY_EXIT)
    # Anything else ends the child with a traceback and no answer, which the engine says plainly.
    with os.fdopen(answer_to, "wb") as out:
        out.write(json.dumps(reply, allow_nan=False, separators=(",", ":")).encode())
    return 0


def watch(engine: int, limit: int) -> None:
    """From now on this process ends itself if the engine ends (so no child is left behind), or
    once it uses more than `limit` bytes of memory. Where this system can't say how much it uses,
    the engine's time limit still holds."""
    gone, used = engine_gone(engine), memory_used

    def look() -> None:
        while True:
            if gone():
                os._exit(ENGINE_GONE_EXIT)
            now = used()
            if now is not None and now > limit:
                os._exit(MEMORY_EXIT)
            time.sleep(WATCH_S)

    threading.Thread(target=look, daemon=True, name="artwork-child-watch").start()


def engine_gone(pid: int) -> Callable[[], bool]:
    """A check that says whether the engine (process `pid`) has ended."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE: only to see it end
        if not handle:
            ended = ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: no such process
            return lambda: ended
        return lambda: kernel32.WaitForSingleObject(handle, 0) == 0  # WAIT_OBJECT_0: it ended
    started_by = os.getppid()

    def gone() -> bool:
        if os.getppid() != started_by:  # whoever started this process has ended
            return True
        try:
            os.kill(pid, 0)  # signal 0: only asks whether it is there
        except ProcessLookupError:
            return True
        except OSError:
            pass
        return False

    return gone


def memory_used() -> int | None:
    """The memory this process uses, in bytes (Windows: committed; Linux: resident and swapped;
    macOS: the most resident so far), or None where there's no way to ask."""
    global _windows_reader
    try:
        if sys.platform == "win32":
            if _windows_reader is None:
                _windows_reader = _windows_committed()
            return _windows_reader()
        if sys.platform.startswith("linux"):
            with open("/proc/self/status", "rb") as fh:
                used = sum(int(line.split()[1]) for line in fh if line.startswith((b"VmRSS:", b"VmSwap:")))
            return used * 1024 or None
        if sys.platform == "darwin":
            import resource

            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    except (OSError, ValueError, ImportError, AttributeError):
        return None
    return None


_windows_reader: Callable[[], int | None] | None = None


def _windows_committed() -> Callable[[], int | None]:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]

    def read() -> int | None:
        counters = Counters(cb=ctypes.sizeof(Counters))
        if not kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return counters.PagefileUsage  # what it has committed, in use or not

    return read
