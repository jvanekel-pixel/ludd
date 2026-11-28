"""Stand-ins for artwork import's child process (artimport/child.py), for tests: the real child with
one thing made to go wrong. Each is a small script the test writes, run as the child in place of
the engine."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from threadline_engine.artimport import child

ENGINE = Path(__file__).resolve().parents[1]

_TEMPLATE = """\
import os, sys, time
sys.path.insert(0, {engine!r})
from threadline_engine.artimport import child, pdf

{body}
sys.exit(child.main())
"""

# A job that never ends (like a call into a library that can't be stopped), on a computer whose
# memory use can't be read: only the engine can end it. It says on stderr when it has started.
HANGS = """\
child.memory_used = lambda: None

def hang(*_):
    print(f"stand-in child: working pid={os.getpid()}", file=sys.stderr, flush=True)
    time.sleep(600)

child._JOBS = {name: hang for name in child._JOBS}
"""

# A library that writes to standard output (as native code can) while it reads.
NOISY = """\
read = pdf._read

def noisy(*args):
    os.write(1, b"noise on file descriptor 1 {noise}\\n")
    print("noise from print {noise}", flush=True)
    return read(*args)

pdf._read = noisy
"""

# Windows can't answer which version it is (WMI is slow or off, which happens under load), so
# Python would run "cmd /c ver" when a library asks. Says on stderr if anything is started.
NO_WMI = """\
import platform

def no_wmi(*_):
    raise OSError("WMI doesn't answer")

platform._wmi_query = no_wmi
sys.addaudithook(lambda event, args: event == "subprocess.Popen"
                 and os.write(2, f"stand-in child: starts {args[1]}\\n".encode()))
"""

# A library that crashes the process (no answer comes back).
CRASHES = """\
def crash(*_):
    os._exit(3)

child._JOBS = {name: crash for name in child._JOBS}
"""

# A child that answers with something that isn't an answer.
GARBLED = """\
def garbled():
    sys.stdin.buffer.read()
    os.write(1, b"{not json")
    os._exit(0)

child.main = garbled
"""


def alive(pid: int) -> bool:
    """Is process `pid` still running? (On Windows, os.kill(pid, 0) would end it.)"""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: no such process
        try:
            return kernel32.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def script(tmp_path: Path, body: str) -> list[str]:
    """The command that runs a stand-in child with `body` in it."""
    path = tmp_path / f"stand_in_{abs(hash(body)):x}.py"
    path.write_text(_TEMPLATE.format(engine=str(ENGINE), body=textwrap.dedent(body)), encoding="utf-8")
    return [sys.executable, str(path)]


class Started(list):
    """Every child process the engine starts, as it starts it (monkeypatch.setattr(child.subprocess,
    "Popen", started.popen))."""

    def __init__(self) -> None:
        super().__init__()
        self._real = subprocess.Popen

    def popen(self, command, **kwargs):
        process = self._real(command, **kwargs)
        self.append((process, command, kwargs))
        return process

    def watch(self, monkeypatch) -> "Started":
        monkeypatch.setattr(child.subprocess, "Popen", self.popen)
        return self

    def all_ended(self) -> bool:
        return all(process.poll() is not None for process, _, _ in self)
