"""LUDD's checks in one command, with a verdict a session can read at a glance.

    python scripts/check.py          engine tests, typecheck, UI tests, knowledge-base command table
    python scripts/check.py --all    the same, plus the desktop build and the Rust tests

--engine / --ui run one side; -k EXPR goes to pytest -k and vitest -t; --record SUITES re-records
snapshot suites (sets UPDATE_SNAPSHOTS); --json prints the results as JSON. Without --record the
stages run with CI=1, so a missing snapshot fails instead of being written. Each stage's full
output is kept in _logs/check-<stage>.log. Exit code 0 (pass) or 1. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 30  # the whole verdict
MAX_FAILURES = 6  # failing tests named per stage, two lines each
WIDTH = 150  # longer lines are cut, so a line of the verdict is one line on screen
SIDECARS = "apps/desktop/src-tauri/binaries"  # the Rust tests need the frozen engine here


@dataclass
class Failure:
    name: str
    message: str = ""


@dataclass
class Parsed:
    summary: str = ""
    failures: list[Failure] = field(default_factory=list)
    failed: int = 0  # how many failed, which can be more than are named


@dataclass
class Result:
    name: str
    status: str  # PASS, FAIL or SKIP
    summary: str = ""
    seconds: float | None = None
    failures: list[Failure] = field(default_factory=list)
    failed: int = 0
    log: str = ""  # from the repository root


# ---------------------------------------------------------------- reading each tool's output

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
# pnpm's own lines after a failed script, which say nothing about why.
_NOISE = re.compile(r"^\s*(\[ELIFECYCLE\]|Error: ERR_PNPM_|[×│]|\$ )")


def _lines(output: str) -> list[str]:
    return _ANSI.sub("", output).replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _counted(n: int, word: str) -> str:
    return f"{n} {word}" + ("s" if word == "error" and n != 1 else "")


def _tidy(message: str) -> str:
    """An error's first line, without the words that only say it is one."""
    for prefix in ("AssertionError: ", "Failed: "):
        message = message.removeprefix(prefix)
    return message.removesuffix(" // Object.is equality").strip()


_PYTEST_TOTAL = re.compile(r"^(?:=+ )?(?P<counts>\d+ [a-z][a-z ]*(?:, \d+ [a-z][a-z ]*)*|no tests ran) in [\d.]+s\b")
_PYTEST_ERROR = re.compile(r"^_+ ERROR (?P<what>(?:at (?:setup|teardown) of|collecting) .+?) _+$")
# A node id can hold " - " inside its [parameters], so those are taken whole.
_PYTEST_FAILED = re.compile(r"^FAILED (?P<id>[^\[]+?(?:\[.*?\](?= - |$))?)(?: - (?P<message>.*))?$")


def parse_pytest(output: str) -> Parsed:
    """pytest -q -rf: the counts, each error (from its own section, since -rf leaves errors out of
    the short summary) and each failed test, with the first line of its message."""
    lines = _lines(output)
    totals: dict[str, int] = {}
    summary = ""
    for line in reversed(lines):
        if m := _PYTEST_TOTAL.match(line.strip()):
            totals = {"error" if word.startswith("error") else word: int(n)
                      for n, word in re.findall(r"(\d+) ([a-z]+)", m["counts"])}
            shown = ("passed", "failed", "error", "skipped", "deselected", "xfailed", "xpassed")
            summary = ", ".join(_counted(totals[w], w) for w in shown if w in totals) or m["counts"]
            break
    errors: list[Failure] = []
    error = None  # the error section being read: its first "E " line is its message
    for line in lines:
        if m := _PYTEST_ERROR.match(line):
            error = Failure(f"error {m['what']}")
            errors.append(error)
        elif line.startswith(("_____", "=====")):
            error = None
        elif error and not error.message and line.startswith("E "):
            error.message = _tidy(line[1:].strip())
    # Failed tests come from the short summary only: a test's own printing could look like it.
    short = max((i for i, line in enumerate(lines) if "short test summary info" in line), default=len(lines))
    found = errors + [Failure(m["id"], _tidy(m["message"] or ""))
                      for line in lines[short:] if (m := _PYTEST_FAILED.match(line))]
    failed = totals.get("failed", 0) + totals.get("error", 0)
    return Parsed(summary, found, max(failed, len(found)))


_VITEST_TOTAL = re.compile(r"^\s*Tests\s+(?P<counts>.+?)\s+\(\d+\)\s*$")
_VITEST_ERRORS = re.compile(r"^\s*Errors\s+(\d+) errors?\s*$")
_VITEST_FAIL = re.compile(r"^\s*FAIL\s+(?P<name>\S.*?)\s*$")
_VITEST_SUITE = re.compile(r"^(\S+) \[ \1 \]$")  # a file that didn't load: "x [ x ]"
_VITEST_UNHANDLED = re.compile(r"^⎯+ (Uncaught Exception|Unhandled Rejection|Unhandled Error) ⎯+$")


def parse_vitest(output: str) -> Parsed:
    """vitest run: the counts, then each failed file or test with the first line of its error,
    and any error thrown outside a test."""
    lines = _lines(output)
    totals: dict[str, int] = {}
    errors = suites = 0
    failures: list[Failure] = []
    waiting: list[str] = []  # FAIL lines waiting for their error (tests failing alike share one)
    listing = False  # past a "Failed Suites" or "Failed Tests" heading (earlier FAILs are logs)
    for i, line in enumerate(lines):
        if m := _VITEST_TOTAL.match(line):
            totals = {word: int(n) for n, word in re.findall(r"(\d+) ([a-z]+)", m["counts"])}
        elif m := _VITEST_ERRORS.match(line):
            errors = int(m[1])
        elif m := re.search(r"⎯ Failed (Suites|Tests) (\d+) ⎯", line):
            listing = True
            if m[1] == "Suites":
                suites = int(m[2])
        elif listing and (m := _VITEST_FAIL.match(line)):
            suite = _VITEST_SUITE.match(m["name"])
            waiting.append((suite[1] if suite else m["name"]).removeprefix("src/"))
        elif waiting and line.strip():
            failures += [Failure(name, _tidy(line.strip())) for name in waiting]
            waiting = []
        elif _VITEST_UNHANDLED.match(line.strip()):
            after = lines[i + 1:]
            message = next((text.strip() for text in after if text.strip()), "")
            origin = next((m[1] for text in after if (m := re.search(r'originated in "(.+?)" test file', text))), "")
            name = f"unhandled error in {origin.removeprefix('src/')}" if origin else "unhandled error"
            failures.append(Failure(name, message))
    failures += [Failure(name) for name in waiting]
    parts = [_counted(totals[w], w) for w in ("passed", "failed", "skipped", "todo") if w in totals]
    if errors:
        parts.append(_counted(errors, "error"))
    failed = totals.get("failed", 0) + suites + errors
    return Parsed(", ".join(parts), failures, max(failed, len(failures)))


_TSC = (
    re.compile(r"^(?P<file>[^\s()][^()]*?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<message>.*)$"),
    re.compile(r"^(?P<file>[^\s()][^()]*?):(?P<line>\d+):(?P<col>\d+) - error (?P<code>TS\d+): (?P<message>.*)$"),
    re.compile(r"^error (?P<code>TS\d+): (?P<message>.*)$"),
)


def parse_tsc(output: str) -> Parsed:
    """tsc --noEmit, plain or --pretty: one failure per error, named by file and place."""
    failures = []
    for line in _lines(output):
        if m := next(filter(None, (pattern.match(line) for pattern in _TSC)), None):
            at = m.groupdict()
            where = f"{at['file']}({at['line']},{at['col']})" if at.get("file") else "tsc"
            failures.append(Failure(where, f"{at['code']}: {at['message']}"))
    n = len(failures)
    return Parsed(_counted(n, "error") if n else "", failures, n)


def parse_kb(output: str) -> Parsed:
    """kb_commands.py --check says in one line what is wrong."""
    said = [Failure(line.removeprefix("kb_commands: ")) for line in _lines(output) if line.startswith("kb_commands: ")]
    return Parsed("", said, len(said))


def parse_build(output: str) -> Parsed:
    """The desktop build: tsc's errors (it type-checks first), else the lines that say error."""
    types = parse_tsc(output)
    if types.failures:
        return types
    errors = [Failure(line.strip()) for line in _lines(output) if "error" in line.lower() and not _NOISE.match(line)]
    return Parsed("", errors, len(errors))


def parse_cargo(output: str) -> Parsed:
    """cargo test: the totals and each failed test with what it panicked with, else compile errors."""
    lines = _lines(output)
    totals = [m for line in lines if (m := re.match(r"^test result: \w+\. (\d+) passed; (\d+) failed", line))]
    passed, failed = sum(int(m[1]) for m in totals), sum(int(m[2]) for m in totals)
    summary = f"{passed} passed" + (f", {failed} failed" if failed else "") if totals else ""
    failures = []
    for line in lines:
        if m := re.match(r"^test (\S+) \.\.\. FAILED$", line):
            header = f"---- {m[1]} stdout ----"
            body = lines[lines.index(header) + 1:] if header in lines else []
            failures.append(Failure(m[1], " ".join([text.strip() for text in body if text.strip()][:2])))
    if not failures:
        failures = [Failure(line) for line in lines if re.match(r"^error(\[\w+\])?: ", line)]
    return Parsed(summary, failures, max(failed, len(failures)))


# ---------------------------------------------------------------- the verdict


def _flat(text: str) -> str:
    return " ".join(text.split())


def _stage_line(r: Result) -> str:
    summary = _flat(r.summary)
    line = f"{r.name:<8}{r.status:<7}" + (f"{summary:<30}" if len(summary) < 30 else f"{summary} ")
    if r.seconds is not None and r.status != "SKIP" and round(r.seconds) >= 1:
        line += f"{round(r.seconds):>3} s"
    return line.rstrip()


def _named(r: Result, n: int) -> list[str]:
    """A failed stage's lines when it shows its first `n` failures ("…" when there are more)."""
    lines = []
    for f in r.failures[:n]:
        lines.append(" " * 10 + _flat(f.name))
        if f.message:
            lines.append(" " * 12 + _flat(f.message))
    if max(r.failed, len(r.failures)) > n:
        lines.append(" " * 10 + "…")
    return lines


def _share(failing: list[Result], room: int) -> dict[str, int]:
    """How many failures each failed stage shows: one more each, in turn, while they all fit."""
    shown = {r.name: 0 for r in failing}
    for n in range(1, MAX_FAILURES + 1):
        for r in failing:
            if n <= len(r.failures):
                trial = {**shown, r.name: n}
                if sum(len(_named(x, trial[x.name])) for x in failing) <= room:
                    shown = trial
    return shown


def render(title: str, results: list[Result]) -> str:
    """The verdict, at most MAX_LINES lines: the title, a line per stage with the failures it
    has room to name, and RESULT."""
    failing = [r for r in results if r.status == "FAIL"]
    shown = _share(failing, MAX_LINES - len(results) - 2)
    out = [title]
    for r in results:
        out.append(_stage_line(r))
        if r.status == "FAIL":
            out += _named(r, shown[r.name])
    out = [line if len(line) <= WIDTH else line[: WIDTH - 1] + "…" for line in out]
    if not failing:
        return "\n".join([*out, "RESULT: PASS"])
    logs = [r.log for r in failing if r.log]
    where = ", ".join(logs) if len(logs) <= 2 else "_logs/check-<stage>.log"
    verdict = f"RESULT: FAIL ({', '.join(r.name for r in failing)})" + (f"   full output: {where}" if logs else "")
    return "\n".join([*out, verdict])


def to_json(results: list[Result], branch: str, commit: str, record: str | None) -> str:
    """The same results as render, as JSON."""
    failed = [r.name for r in results if r.status == "FAIL"]
    stages = [{**asdict(r), "failures": [asdict(f) for f in r.failures[:MAX_FAILURES]]} for r in results]
    return json.dumps({"branch": branch, "commit": commit, "recording": record,
                       "result": "FAIL" if failed else "PASS", "failed": failed, "stages": stages},
                      indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- the stages


@dataclass
class Stage:
    name: str
    side: str  # "engine" or "ui"
    command: list[str]
    cwd: str  # from the repository root
    parse: Callable[[str], Parsed]


def arguments() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python scripts/check.py", description="Run LUDD's checks; print a short verdict.")
    ap.add_argument("--all", action="store_true", help="also the desktop build and the Rust tests")
    ap.add_argument("--engine", action="store_true", help="only the engine side")
    ap.add_argument("--ui", action="store_true", help="only the UI side")
    ap.add_argument("-k", metavar="EXPR", help="passed to pytest -k and vitest -t")
    ap.add_argument("--record", metavar="SUITES", help="re-record these snapshot suites (a comma list, or all)")
    ap.add_argument("--json", action="store_true", help="print the results as JSON")
    return ap


def plan(opts: argparse.Namespace) -> list[Stage]:
    if opts.k:
        # vitest is run with node, not `pnpm test`: on Windows pnpm is a .cmd file, and cmd.exe
        # cuts an expression at & or | (and drops ^) before pnpm sees it, so other tests would run.
        ui_tests = Stage("ui", "ui", ["node", "node_modules/vitest/vitest.mjs", "run", "-t", opts.k],
                         "apps/desktop", parse_vitest)
    else:
        ui_tests = Stage("ui", "ui", ["pnpm", "test"], ".", parse_vitest)
    engine_k = ["-k", opts.k] if opts.k else []
    stages = [
        Stage("engine", "engine", ["uv", "run", "--locked", "pytest", "-q", "-rf", *engine_k], "engine", parse_pytest),
        Stage("types", "ui", ["pnpm", "typecheck"], ".", parse_tsc),
        ui_tests,
        Stage("kb", "ui", [sys.executable, "scripts/kb_commands.py", "--check"], ".", parse_kb),
    ]
    if opts.all:
        stages += [
            Stage("build", "ui", ["pnpm", "--filter", "@threadline/desktop", "build"], ".", parse_build),
            Stage("rust", "ui", ["cargo", "test", "--locked", "--lib", "--manifest-path",
                                 "apps/desktop/src-tauri/Cargo.toml"], ".", parse_cargo),
        ]
    if opts.engine != opts.ui:  # one side asked for (both is the same as neither)
        stages = [s for s in stages if s.side == ("engine" if opts.engine else "ui")]
    return stages


def stage_env(record: str | None, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The stages' environment: CI=1, so a missing snapshot fails instead of being written,
    unless recording, which sets UPDATE_SNAPSHOTS and leaves CI alone. Plain output."""
    env = dict(os.environ if base is None else base)
    env.pop("UPDATE_SNAPSHOTS", None)  # one left in the shell would record during a check
    env.pop("FORCE_COLOR", None)
    env["NO_COLOR"] = "1"
    if record:
        env["UPDATE_SNAPSHOTS"] = record
    else:
        env["CI"] = "1"
    return env


def _rust_skip(root: Path, which) -> str | None:
    if not which("cargo"):
        return "cargo not found"
    if not any((root / SIDECARS).glob("threadline-engine-*")):
        return "no engine sidecar (pnpm build:engine)"
    return None


def run_stage(stage: Stage, env: dict[str, str], root: Path, run, which, k: str | None = None) -> Result:
    if stage.name == "rust" and (why := _rust_skip(root, which)):
        return Result(stage.name, "SKIP", why)
    tool = stage.command[0]
    program = tool if os.path.isabs(tool) else which(tool)  # on Windows, pnpm is pnpm.cmd
    if not program:
        return Result(stage.name, "FAIL", f"{tool} not found on PATH")
    started = time.monotonic()
    try:
        done = run([program, *stage.command[1:]], cwd=root / stage.cwd, env=env, stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as err:
        return Result(stage.name, "FAIL", f"couldn't run {tool}: {err}")
    seconds = round(time.monotonic() - started, 1)
    output = done.stdout.decode("utf-8", errors="replace")
    log = root / "_logs" / f"check-{stage.name}.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(f"$ {subprocess.list2cmdline(stage.command)}\n{output}", encoding="utf-8", newline="")
    found = stage.parse(output)
    result = Result(stage.name, "PASS" if done.returncode == 0 else "FAIL", found.summary, seconds,
                    log=log.relative_to(root).as_posix())
    if stage.name == "engine" and k and done.returncode == 5:  # pytest: -k matched nothing
        result.status, result.summary = "SKIP", "no engine tests match -k"
    elif result.status == "FAIL":
        result.failures, result.failed = found.failures, found.failed
        if not result.failures:  # nothing named: show how it ended
            last = next((line.strip() for line in reversed(_lines(output)) if line.strip() and not _NOISE.match(line)), "")
            result.failures, result.failed = [Failure(f"exit code {done.returncode}", last)], max(result.failed, 1)
    return result


def _git(root: Path, run, which) -> tuple[str, str]:
    """(branch, short commit), blank without git."""
    git = which("git")
    answers = []
    for flag in ("--abbrev-ref", "--short"):
        try:
            done = run([git, "rev-parse", flag, "HEAD"], cwd=root, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) if git else None
        except OSError:
            done = None
        answers.append(done.stdout.decode("utf-8", errors="replace").strip() if done and done.returncode == 0 else "")
    return answers[0], answers[1]


def main(argv: list[str] | None = None, *, root: Path = ROOT, run=subprocess.run, which=shutil.which) -> int:
    opts = arguments().parse_args(argv)
    branch, commit = _git(root, run, which)
    env = stage_env(opts.record)
    results = [run_stage(stage, env, root, run, which, opts.k) for stage in plan(opts)]
    if opts.json:
        print(to_json(results, branch, commit, opts.record))
    else:
        title = f"LUDD check  ({branch} @ {commit})" if commit else "LUDD check"
        print(render(title + (f"  recording {opts.record}" if opts.record else ""), results))
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # "…" and any test name, even into a pipe
    sys.exit(main())
