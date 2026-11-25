"""The tooling: scripts/check.py (reading each tool's output, the verdict, running the stages),
scripts/kb_commands.py (the command registry in actions.ts and cmd/*.ts) and snapshot_util.py.

The canned outputs are cut down from real runs of pytest, vitest 5 and tsc 7 on throwaway failing
tests. check.py never runs a real stage here (that would run these tests again): the runner is faked.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import snapshot_util
import test_digitize
import test_layout_snapshots
from threadline_engine import layout
from threadline_engine.digitize.stitches import generate

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = Path(__file__).parent / "snapshots"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(f"ludd_script_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


check = _script("check")
kb_commands = _script("kb_commands")


def pairs(parsed):
    return [(f.name, f.message) for f in parsed.failures]


# ---------------------------------------------------------------- pytest

PYTEST_FAIL = r"""FFFEE.EFFs.F                                                             [100%]
=================================== ERRORS ====================================
__________________ ERROR at setup of test_zz_missing_fixture __________________
file C:\work\ludd\engine\tests\test_zz.py, line 14
  def test_zz_missing_fixture(zz_missing_fixture):
E       fixture 'zz_missing_fixture' not found
>       available fixtures: cache, capfd, tmp_path
>       use 'pytest --fixtures [testpath]' for help on them.

C:\work\ludd\engine\tests\test_zz.py:14
__________________ ERROR at setup of test_zz_broken_fixture ___________________

    @pytest.fixture
    def zz_broken():
>       raise RuntimeError("fixture blew up\nwith a second line")
E       RuntimeError: fixture blew up
E       with a second line

tests\test_zz.py:20: RuntimeError
____________________ ERROR at teardown of test_zz_teardown ____________________

    @pytest.fixture
    def zz_bad_teardown():
        yield
>       raise ValueError("teardown blew up")
E       ValueError: teardown blew up

tests\test_zz.py:30: ValueError
================================== FAILURES ===================================
_______________________________ test_zz_compare _______________________________

    def test_zz_compare():
>       assert ["Pattern", "Loop size"] == ["Pattern"], "the panel shows the wrong rows"
E       AssertionError: the panel shows the wrong rows
E       assert ['Pattern', 'Loop size'] == ['Pattern']
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

tests\test_zz.py:6: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_zz.py::test_zz_compare - AssertionError: the panel shows the wrong rows
assert ['Pattern', 'Loop size'] == ['Pattern']

  Left contains one more item: 'Loop size'
FAILED tests/test_zz.py::test_zz_params[insert a stop at the needle - Stops and trims] - AssertionError: assert 59 < 5
 +  where 59 = len('insert a stop at the needle - Stops and trims')
FAILED tests/test_zz.py::test_zz_params[plain] - AssertionError: assert 5 < 5
 +  where 5 = len('plain')
FAILED tests/test_zz.py::test_zz_fail_call - Failed: no snapshot recorded for zz: run the tests locally, review and commit snapshots/digitize.json
FAILED tests/test_zz.py::test_zz_raises - KeyError: 'nope'
FAILED tests/test_zz.py::TestZzGroup::test_zz_method - assert [1] == [2] - never
6 failed, 2 passed, 1 skipped, 2 warnings, 3 errors in 0.98s
"""

PYTEST_COLLECT = r"""
=================================== ERRORS ====================================
________________ ERROR collecting tests/test_zz_collect.py ________________
ImportError while importing test module 'C:\work\ludd\engine\tests\test_zz_collect.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\test_zz_collect.py:2: in <module>
    import zz_module_that_does_not_exist  # noqa: F401
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'zz_module_that_does_not_exist'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.26s
"""

PYTEST_PASS = """........................................................................ [ 10%]
..........                                                               [100%]
657 passed, 1 skipped in 93.67s (0:01:33)
"""


def test_parse_pytest_names_every_failure_and_error_with_the_first_line_of_its_message():
    p = check.parse_pytest(PYTEST_FAIL)
    assert p.summary == "2 passed, 6 failed, 3 errors, 1 skipped"  # warnings are left out
    assert p.failed == 9
    assert pairs(p) == [
        ("error at setup of test_zz_missing_fixture", "fixture 'zz_missing_fixture' not found"),
        ("error at setup of test_zz_broken_fixture", "RuntimeError: fixture blew up"),
        ("error at teardown of test_zz_teardown", "ValueError: teardown blew up"),
        ("tests/test_zz.py::test_zz_compare", "the panel shows the wrong rows"),
        ("tests/test_zz.py::test_zz_params[insert a stop at the needle - Stops and trims]", "assert 59 < 5"),
        ("tests/test_zz.py::test_zz_params[plain]", "assert 5 < 5"),
        ("tests/test_zz.py::test_zz_fail_call",
         "no snapshot recorded for zz: run the tests locally, review and commit snapshots/digitize.json"),
        ("tests/test_zz.py::test_zz_raises", "KeyError: 'nope'"),
        ("tests/test_zz.py::TestZzGroup::test_zz_method", "assert [1] == [2] - never"),
    ]


def test_parse_pytest_names_a_module_that_cannot_be_imported():
    p = check.parse_pytest(PYTEST_COLLECT)
    assert p.summary == "1 error" and p.failed == 1
    assert pairs(p) == [("error collecting tests/test_zz_collect.py",
                         "ModuleNotFoundError: No module named 'zz_module_that_does_not_exist'")]


def test_parse_pytest_does_not_list_an_error_twice_when_the_summary_names_it():
    # With -rfE (not what check.py runs) the short summary names errors too.
    out = PYTEST_COLLECT.replace("!!!!!!!!!!!!!!!!!!! Interrupted",
                                 "=========================== short test summary info ===========================\n"
                                 "ERROR tests/test_zz_collect.py\n!!!!!!!!!!!!!!!!!!! Interrupted")
    assert [f.name for f in check.parse_pytest(out).failures] == ["error collecting tests/test_zz_collect.py"]


@pytest.mark.parametrize("output, summary", [
    (PYTEST_PASS, "657 passed, 1 skipped"),
    ("\n658 deselected in 2.78s\n", "658 deselected"),
    ("\nno tests ran in 0.01s\n", "no tests ran"),
    ("============== 3 passed, 1 xfailed, 1 xpassed, 4 warnings in 1.00s ==============\n",
     "3 passed, 1 xfailed, 1 xpassed"),
    ("2 passed, 3 subtests passed in 0.10s\n", "2 passed"),
    # A line a test printed that looks like a result is not one: only the short summary counts.
    ("----- Captured stdout call -----\nFAILED to reach the hoop\n3 passed in 1.00s\n", "3 passed"),
    ("\x1b[32m\x1b[1m657 passed\x1b[0m, \x1b[33m1 skipped\x1b[0m in 93.67s\n", "657 passed, 1 skipped"),
    ("error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.\n", ""),
])
def test_parse_pytest_counts(output, summary):
    p = check.parse_pytest(output)
    assert p.summary == summary and p.failures == [] and p.failed == 0


# ---------------------------------------------------------------- vitest

VITEST_FAIL = """$ pnpm --filter @threadline/desktop test
$ vitest run

 RUN  v5.1.0 C:/work/ludd/apps/desktop

 ❯ src/zz_suite.test.ts (0 test)
 ❯ src/components/zz.test.ts (7 tests | 5 failed | 1 skipped) 23ms
   ❯ zz tmp suite (7)
     × compares arrays 14ms
     × compares numbers 2ms
     ❯ nested one (1)
       × throws an error with two lines 1ms
     × same failure 1 2ms
     × same failure 2 1ms

⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/zz_suite.test.ts [ src/zz_suite.test.ts ]
Error: Cannot find module './zz-does-not-exist' imported from C:/work/ludd/apps/desktop/src/zz_suite.test.ts
 ❯ src/zz_suite.test.ts:3:1
      3| import { nope } from "./zz-does-not-exist";
       | ^

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/6]⎯


⎯⎯⎯⎯⎯⎯⎯ Failed Tests 5 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/components/zz.test.ts > zz tmp suite > compares arrays
AssertionError: expected [ 'Pattern', 'Loop size' ] to deeply equal [ 'Pattern' ]

- Expected
+ Received

  [
    "Pattern",
+   "Loop size",
  ]

 ❯ src/components/zz.test.ts:6:49

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/6]⎯

 FAIL  src/components/zz.test.ts > zz tmp suite > compares numbers
AssertionError: expected 2 to be 3 // Object.is equality

- 3
+ 2

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[3/6]⎯

 FAIL  src/components/zz.test.ts > zz tmp suite > nested one > throws an error with two lines
Error: boom: first line
second line
 ❯ src/components/zz.test.ts:13:13

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[4/6]⎯

 FAIL  src/components/zz.test.ts > zz tmp suite > same failure 1
 FAIL  src/components/zz.test.ts > zz tmp suite > same failure 2
AssertionError: expected 'a' to be 'b' // Object.is equality

Expected: "b"
Received: "a"

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[5/6]⎯


 Test Files  2 failed (2)
      Tests  5 failed | 1 passed | 1 skipped (7)
   Start at  18:27:36
   Duration  326ms (transform 42%, tests 23%, import 20%, worker 15%, environment 1%)

[ELIFECYCLE] Test failed. See above for more details.
Error: ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL

  × "pnpm recursive run" failed in C:\\work\\ludd\\apps\\desktop
"""

VITEST_UNHANDLED = """ RUN  v5.1.0 C:/work/ludd/apps/desktop

⎯⎯⎯⎯⎯⎯ Unhandled Errors ⎯⎯⎯⎯⎯⎯

Vitest caught 1 unhandled error during the test run.
This might cause false positive tests. Resolve unhandled errors to make sure your tests are not affected.

⎯⎯⎯⎯⎯ Uncaught Exception ⎯⎯⎯⎯⎯
Error: late error after the test
 ❯ Timeout._onTimeout src/zz_unhandled.test.ts:6:11
      6|     throw new Error("late error after the test");
       |           ^

This error originated in "src/zz_unhandled.test.ts" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯


 Test Files  1 passed (1)
      Tests  1 passed (1)
     Errors  1 error
   Start at  18:31:36
"""

VITEST_PASS = """
 RUN  v5.1.0 C:/work/ludd/apps/desktop


 Test Files  44 passed (44)
      Tests  241 passed (241)
   Start at  18:20:34
   Duration  3.96s
"""


def test_parse_vitest_names_failed_suites_and_tests_with_the_first_line_of_the_error():
    p = check.parse_vitest(VITEST_FAIL)
    assert p.summary == "1 passed, 5 failed, 1 skipped"
    assert p.failed == 6  # five tests and a file that did not load
    boom = "components/zz.test.ts > zz tmp suite > "
    assert pairs(p) == [
        ("zz_suite.test.ts", "Error: Cannot find module './zz-does-not-exist' imported from "
                             "C:/work/ludd/apps/desktop/src/zz_suite.test.ts"),
        (boom + "compares arrays", "expected [ 'Pattern', 'Loop size' ] to deeply equal [ 'Pattern' ]"),
        (boom + "compares numbers", "expected 2 to be 3"),
        (boom + "nested one > throws an error with two lines", "Error: boom: first line"),
        # Two tests with the same error share one block of output.
        (boom + "same failure 1", "expected 'a' to be 'b'"),
        (boom + "same failure 2", "expected 'a' to be 'b'"),
    ]


def test_parse_vitest_reports_an_error_outside_any_test():
    p = check.parse_vitest(VITEST_UNHANDLED)
    assert p.summary == "1 passed, 1 error" and p.failed == 1
    assert pairs(p) == [("unhandled error in zz_unhandled.test.ts", "Error: late error after the test")]


@pytest.mark.parametrize("output, summary", [
    (VITEST_PASS, "241 passed"),
    (VITEST_PASS.replace("241 passed (241)", "241 skipped (241)"), "241 skipped"),
    ("      Tests  2 passed | 1 todo (3)\n", "2 passed, 1 todo"),
    ("\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m241 passed\x1b[39m\x1b[22m\x1b[90m (241)\x1b[39m\n", "241 passed"),
    ("No test files found, exiting with code 1\n", ""),
    # What a test logs is not a failed test: those are listed under the "Failed ..." headings.
    ("stdout | src/a.test.ts > logs\n FAIL  is only a word here\n\n      Tests  2 passed (2)\n", "2 passed"),
])
def test_parse_vitest_counts(output, summary):
    p = check.parse_vitest(output)
    assert p.summary == summary and p.failures == [] and p.failed == 0


# ---------------------------------------------------------------- tsc

TSC_FAIL = """$ pnpm --filter @threadline/desktop typecheck
$ tsc --noEmit
src/zz_types.ts(2,14): error TS2322: Type 'string' is not assignable to type 'number'.
src/components/Zz.tsx(8,10): error TS2304: Cannot find name 'zzMissing'.
src/zz_types.ts(14,7): error TS2741: Property 'y' is missing in type '{ x: number; }' but required in type '{ x: number; y: number; }'.
  'y' is declared here.
[ELIFECYCLE] Command failed with exit code 1.
Error: ERR_PNPM_RECURSIVE_RUN_FIRST_FAIL
"""

TSC_PRETTY = """src/zz_types.ts:2:14 - error TS2322: Type 'string' is not assignable to type 'number'.

2 export const zzNumber: number = "not a number";
               ~~~~~~~~

error TS5083: Cannot read file 'tsconfig.zz.json'.

Found 2 errors in the same file, starting at: src/zz_types.ts:2
"""


def test_parse_tsc_names_each_error_by_file_and_place():
    p = check.parse_tsc(TSC_FAIL)
    assert p.summary == "3 errors" and p.failed == 3
    assert pairs(p)[:2] == [
        ("src/zz_types.ts(2,14)", "TS2322: Type 'string' is not assignable to type 'number'."),
        ("src/components/Zz.tsx(8,10)", "TS2304: Cannot find name 'zzMissing'."),
    ]


def test_parse_tsc_reads_the_pretty_format_and_errors_without_a_file():
    p = check.parse_tsc(TSC_PRETTY)
    assert pairs(p) == [
        ("src/zz_types.ts(2,14)", "TS2322: Type 'string' is not assignable to type 'number'."),
        ("tsc", "TS5083: Cannot read file 'tsconfig.zz.json'."),
    ]


def test_parse_tsc_says_nothing_when_it_passes():
    p = check.parse_tsc("$ pnpm --filter @threadline/desktop typecheck\n$ tsc --noEmit\n")
    assert (p.summary, p.failures, p.failed) == ("", [], 0)


# ---------------------------------------------------------------- the verdict

EXAMPLE = """LUDD check  (phase-03/build-seams @ 1a2b3c4)
engine  PASS   712 passed, 1 skipped          41 s
types   PASS                                   9 s
ui      FAIL   243 passed, 2 failed           22 s
          components/ObjectPanel.dom.test.tsx > stipple hides Density
            expected [ 'Pattern', 'Loop size' ] to equal [ 'Pattern' ]
          …
kb      PASS
RESULT: FAIL (ui)   full output: _logs/check-ui.log"""


def test_render_looks_like_the_example():
    results = [
        check.Result("engine", "PASS", "712 passed, 1 skipped", 41.2, log="_logs/check-engine.log"),
        check.Result("types", "PASS", "", 9.0, log="_logs/check-types.log"),
        check.Result("ui", "FAIL", "243 passed, 2 failed", 21.6,
                     [check.Failure("components/ObjectPanel.dom.test.tsx > stipple hides Density",
                                    "expected [ 'Pattern', 'Loop size' ] to equal [ 'Pattern' ]")],
                     2, "_logs/check-ui.log"),
        check.Result("kb", "PASS", "", 0.1, log="_logs/check-kb.log"),
    ]
    assert check.render("LUDD check  (phase-03/build-seams @ 1a2b3c4)", results) == EXAMPLE


def _many(stage: str, n: int = 300):
    failures = [check.Failure(f"tests/test_{stage}.py::test_case[{i}]", f"assert {i} == -1") for i in range(n)]
    return check.Result(stage, "FAIL", f"412 passed, {n} failed", 93.0, failures, n, f"_logs/check-{stage}.log")


def test_render_fits_a_300_failure_run_in_30_lines():
    out = ["=========================== short test summary info ==========================="]
    out += [f"FAILED tests/test_x.py::test_case[{i}] - AssertionError: assert {i} == -1" for i in range(300)]
    out += ["300 failed, 412 passed in 93.00s"]
    p = check.parse_pytest("\n".join(out))
    assert p.failed == 300
    results = [check.Result("engine", "FAIL", p.summary, 93.0, p.failures, p.failed, "_logs/check-engine.log"),
               check.Result("types", "PASS", "", 9.0), check.Result("ui", "PASS", "241 passed", 4.0),
               check.Result("kb", "PASS")]
    lines = check.render("LUDD check  (b @ 1234567)", results).splitlines()
    assert len(lines) <= 30
    assert sum(line.startswith("          tests/") for line in lines) == 6  # at most six per stage
    assert "          …" in lines
    assert lines[-1] == "RESULT: FAIL (engine)   full output: _logs/check-engine.log"


def test_render_shares_30_lines_between_every_failing_stage():
    names = ["engine", "types", "ui", "kb", "build", "rust"]
    lines = check.render("LUDD check", [_many(n) for n in names]).splitlines()
    assert len(lines) <= 30
    for name in names:
        assert any(line.startswith(f"{name:<8}FAIL") for line in lines)
        assert any(line.startswith(f"          tests/test_{name}.py") for line in lines), name
    assert lines.count("          …") == len(names)
    assert lines[-1] == "RESULT: FAIL (engine, types, ui, kb, build, rust)   full output: _logs/check-<stage>.log"


def test_render_gives_one_failing_stage_all_the_room_it_may_use():
    lines = check.render("LUDD check", [_many("engine", 4)]).splitlines()
    assert sum(line.startswith("          tests/") for line in lines) == 4
    assert "          …" not in lines


def test_render_keeps_every_line_one_line():
    long = check.Failure("a" * 400, "first\nsecond\tthird " + "b" * 400)
    out = check.render("LUDD check", [check.Result("ui", "FAIL", "1 failed", 1.0, [long], 1, "_logs/check-ui.log")])
    lines = out.splitlines()
    assert len(lines) == 5 and max(map(len, lines)) <= 150
    assert lines[3].startswith("            first second third bbb") and lines[3].endswith("…")


def test_render_shows_skips_and_passes():
    results = [check.Result("engine", "PASS", "657 passed, 1 skipped", 93.0),
               check.Result("rust", "SKIP", "no engine sidecar (pnpm build:engine)")]
    assert check.render("LUDD check", results).splitlines() == [
        "LUDD check",
        "engine  PASS   657 passed, 1 skipped          93 s",
        "rust    SKIP   no engine sidecar (pnpm build:engine)",
        "RESULT: PASS",
    ]


# ---------------------------------------------------------------- flags


def plan(*argv):
    return check.plan(check.arguments().parse_args(list(argv)))


@pytest.mark.parametrize("argv, names", [
    ([], ["engine", "types", "ui", "kb"]),
    (["--all"], ["engine", "types", "ui", "kb", "build", "rust"]),
    (["--engine"], ["engine"]),
    (["--ui"], ["types", "ui", "kb"]),
    (["--engine", "--ui"], ["engine", "types", "ui", "kb"]),
    (["--all", "--engine"], ["engine"]),
    (["--all", "--ui"], ["types", "ui", "kb", "build", "rust"]),
])
def test_flags_choose_the_stages(argv, names):
    assert [s.name for s in plan(*argv)] == names


def test_the_stage_commands():
    cmds = {s.name: (s.command, s.cwd) for s in plan("--all")}
    assert cmds["engine"] == (["uv", "run", "--locked", "pytest", "-q", "-rf"], "engine")
    assert cmds["types"] == (["pnpm", "typecheck"], ".")
    assert cmds["ui"] == (["pnpm", "test"], ".")
    assert cmds["kb"] == ([sys.executable, "scripts/kb_commands.py", "--check"], ".")
    assert cmds["build"] == (["pnpm", "--filter", "@threadline/desktop", "build"], ".")
    assert cmds["rust"] == (["cargo", "test", "--locked", "--lib", "--manifest-path",
                             "apps/desktop/src-tauri/Cargo.toml"], ".")


def test_k_reaches_pytest_and_vitest_exactly_as_typed():
    cmds = {s.name: (s.command, s.cwd) for s in plan("-k", "fill&satin|run^")}
    assert cmds["engine"][0][-2:] == ["-k", "fill&satin|run^"]
    # Not through pnpm: on Windows its .cmd shim cuts an expression at & or |.
    assert cmds["ui"] == (["node", "node_modules/vitest/vitest.mjs", "run", "-t", "fill&satin|run^"], "apps/desktop")
    assert cmds["types"][0] == ["pnpm", "typecheck"]


def test_ci_is_set_unless_recording():
    base = {"PATH": "x", "UPDATE_SNAPSHOTS": "1", "FORCE_COLOR": "1"}
    env = check.stage_env(None, base)
    assert env["CI"] == "1" and "UPDATE_SNAPSHOTS" not in env  # a checking run never records
    assert env["NO_COLOR"] == "1" and "FORCE_COLOR" not in env and env["PATH"] == "x"
    env = check.stage_env("digitize,layout", base)
    assert env["UPDATE_SNAPSHOTS"] == "digitize,layout" and "CI" not in env
    assert base == {"PATH": "x", "UPDATE_SNAPSHOTS": "1", "FORCE_COLOR": "1"}  # not changed in place


# ---------------------------------------------------------------- running the stages


class FakeRun:
    """Stands in for subprocess.run: {stage: (exit code, output)}; anything else passes silently."""

    def __init__(self, replies=None):
        self.replies = replies or {}
        self.calls = {}

    def __call__(self, argv, **kwargs):
        words = [Path(argv[0]).name, *argv[1:]]
        if "rev-parse" in words:
            out = "abc1234\n" if "--short" in words else "phase-03/track-c\n"
            return subprocess.CompletedProcess(argv, 0, out.encode(), None)
        stage = ("engine" if "pytest" in words else "rust" if words[0] == "cargo" else
                 "build" if "build" in words else "types" if "typecheck" in words else
                 "kb" if "scripts/kb_commands.py" in words else "ui")
        self.calls[stage] = (argv, kwargs)
        code, out = self.replies.get(stage, (0, ""))
        return subprocess.CompletedProcess(argv, code, out if isinstance(out, bytes) else out.encode(), None)


def which_all(*missing):
    return lambda name: None if name in missing else f"/tools/{name}"


def run_main(tmp_path, capsys, *argv, replies=None, missing=()):
    fake = FakeRun(replies)
    code = check.main(list(argv), root=tmp_path, run=fake, which=which_all(*missing))
    return code, capsys.readouterr().out, fake


def test_a_passing_run_exits_0_and_keeps_each_full_output(tmp_path, capsys):
    code, out, fake = run_main(tmp_path, capsys, replies={"engine": (0, PYTEST_PASS), "ui": (0, VITEST_PASS)})
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "LUDD check  (phase-03/track-c @ abc1234)"
    assert [line.split()[:2] for line in lines[1:5]] == [["engine", "PASS"], ["types", "PASS"], ["ui", "PASS"], ["kb", "PASS"]]
    assert "657 passed, 1 skipped" in lines[1] and lines[-1] == "RESULT: PASS" and len(lines) == 6
    assert (tmp_path / "_logs" / "check-engine.log").read_text(encoding="utf-8").endswith(PYTEST_PASS)
    assert sorted(p.name for p in (tmp_path / "_logs").iterdir()) == [
        "check-engine.log", "check-kb.log", "check-types.log", "check-ui.log"]
    argv, kwargs = fake.calls["engine"]
    assert argv[0] == "/tools/uv" and kwargs["cwd"] == tmp_path / "engine"  # found with shutil.which
    assert kwargs["env"]["CI"] == "1" and kwargs["stdin"] == subprocess.DEVNULL
    assert fake.calls["ui"][0][0] == "/tools/pnpm"
    assert fake.calls["kb"][0][0] == sys.executable


def test_a_failing_stage_exits_1_and_names_its_log(tmp_path, capsys):
    code, out, _ = run_main(tmp_path, capsys, replies={"ui": (1, VITEST_FAIL)})
    lines = out.splitlines()
    assert code == 1 and len(lines) <= 30
    assert any(line.startswith("ui      FAIL   1 passed, 5 failed, 1 skipped") for line in lines)
    assert "          zz_suite.test.ts" in lines
    assert lines[-1] == "RESULT: FAIL (ui)   full output: _logs/check-ui.log"


def test_output_that_is_not_utf8_is_still_read(tmp_path, capsys):
    code, out, _ = run_main(tmp_path, capsys, "--engine", replies={"engine": (0, b"\x85 \xd7\n3 passed in 1.0s\n")})
    assert code == 0 and "3 passed" in out
    assert "�" in (tmp_path / "_logs" / "check-engine.log").read_text(encoding="utf-8")


def test_a_stage_that_fails_without_naming_a_test_shows_its_last_line(tmp_path, capsys):
    reply = "error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.\n"
    code, out, _ = run_main(tmp_path, capsys, "--engine", replies={"engine": (2, reply)})
    assert code == 1 and "exit code 2" in out and "The lockfile at `uv.lock` needs to be updated" in out


def test_a_stale_command_table_says_how_to_fix_it(tmp_path, capsys):
    reply = ("kb_commands: the command table in docs/LUDD-KNOWLEDGE-BASE.md is out of date: "
             "run python scripts/kb_commands.py\n")
    code, out, _ = run_main(tmp_path, capsys, "--ui", replies={"kb": (1, reply)})
    assert code == 1 and "run python scripts/kb_commands.py" in out


def test_a_missing_tool_fails_that_stage(tmp_path, capsys):
    code, out, fake = run_main(tmp_path, capsys, missing=("uv",))
    assert code == 1 and "uv not found on PATH" in out and "engine" not in fake.calls
    assert "types" in fake.calls  # the other stages still run


def test_recording_sets_update_snapshots_and_not_ci(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CI", raising=False)  # this test itself may run under check.py
    code, out, fake = run_main(tmp_path, capsys, "--engine", "--record", "digitize,layout")
    env = fake.calls["engine"][1]["env"]
    assert code == 0 and env["UPDATE_SNAPSHOTS"] == "digitize,layout" and "CI" not in env
    assert "recording digitize,layout" in out.splitlines()[0]


@pytest.mark.parametrize("cargo, sidecar, note", [
    (False, True, "cargo not found"),
    (True, False, "no engine sidecar (pnpm build:engine)"),
    (True, True, None),
])
def test_rust_is_skipped_with_a_note_without_cargo_or_the_sidecar(tmp_path, capsys, cargo, sidecar, note):
    binaries = tmp_path / "apps" / "desktop" / "src-tauri" / "binaries"
    binaries.mkdir(parents=True)
    if sidecar:
        (binaries / "threadline-engine-x86_64-pc-windows-msvc.exe").write_bytes(b"")
    code, out, fake = run_main(tmp_path, capsys, "--all", missing=() if cargo else ("cargo",))
    rust = next(line for line in out.splitlines() if line.startswith("rust"))
    assert code == 0
    if note:
        assert rust.split(None, 2) == ["rust", "SKIP", note] and "rust" not in fake.calls
    else:
        assert rust.split()[1] == "PASS" and "rust" in fake.calls


def test_k_that_matches_no_engine_test_is_a_skip_not_a_failure(tmp_path, capsys):
    replies = {"engine": (5, "\n658 deselected in 2.78s\n")}
    code, out, _ = run_main(tmp_path, capsys, "-k", "ObjectPanel", replies=replies)
    assert code == 0 and "engine  SKIP   no engine tests match -k" in out
    code, out, _ = run_main(tmp_path, capsys, "--engine", replies=replies)
    assert code == 1  # without -k, collecting nothing is a failure


def test_json_gives_the_same_results(tmp_path, capsys):
    code, out, _ = run_main(tmp_path, capsys, "--json", replies={"engine": (1, PYTEST_FAIL)})
    data = json.loads(out)
    assert code == 1
    assert (data["branch"], data["commit"], data["result"], data["failed"]) == (
        "phase-03/track-c", "abc1234", "FAIL", ["engine"])
    engine = data["stages"][0]
    assert (engine["name"], engine["status"], engine["summary"], engine["failed"], engine["log"]) == (
        "engine", "FAIL", "2 passed, 6 failed, 3 errors, 1 skipped", 9, "_logs/check-engine.log")
    assert len(engine["failures"]) == 6 and set(engine["failures"][0]) == {"name", "message"}
    assert [s["name"] for s in data["stages"]] == ["engine", "types", "ui", "kb"]


def test_a_cargo_failure_names_the_test(tmp_path, capsys):
    cargo = """running 2 tests
test tests::keeps_the_key ... ok
test tests::finds_the_engine ... FAILED

failures:

---- tests::finds_the_engine stdout ----
thread 'tests::finds_the_engine' panicked at src/lib.rs:10:9:
assertion `left == right` failed

test result: FAILED. 1 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""
    p = check.parse_cargo(cargo)
    assert p.summary == "1 passed, 1 failed" and p.failed == 1
    assert p.failures[0].name == "tests::finds_the_engine"
    assert "panicked at src/lib.rs:10:9" in p.failures[0].message
    compile_error = "error[E0425]: cannot find value `x` in this scope\nerror: could not compile `ludd` (lib test)\n"
    assert check.parse_cargo(compile_error).failures[0].name.startswith("error[E0425]")


def test_a_build_failure_shows_the_type_errors_or_the_error_lines():
    assert check.parse_build(TSC_FAIL).failures[0].name == "src/zz_types.ts(2,14)"
    vite = "vite v6.0.0 building for production...\nerror during build:\nRollupError: Could not resolve \"./nope\"\n"
    names = [f.name for f in check.parse_build(vite).failures]
    assert names == ["error during build:", 'RollupError: Could not resolve "./nope"']


# ---------------------------------------------------------------- kb_commands.py

ACTIONS = r'''import type { Command } from "./commands";

// export const CORE_COMMANDS: Command[] = [ is declared below.
const helper = { id: "not.a.command", title: "Helper", shortcut: "F12" };

export const CORE_COMMANDS: Command[] = [
  // A comment with a lone ] bracket, an apostrophe's quote and a " mark.
  { id: "app.one", title: "One", shortcut: "Mod+1", run: () => [1].join("]") },
  /* ] */
  {
    id: "app.two",
    title: "Two [brackets] it's",
    shortcut: "[",
    enabled: () => /["'\]]+/.test("x") && 4 / 2 > 1,
    run: () => info(`] ${[1, 2].map((n) => `${n}]`).join("")} [`),
  },
  ...[1, 2].map((k) => ({ id: `view.zoom${k}`, title: `Zoom ${k}`, shortcut: String(k) })),
  { id: "app.three", title: "Three", shortcut: "]" },
];

export const after = { id: "after.the.block", title: "After", shortcut: "Z" };
'''

SHAPES = '''import { registerCommands } from "../commands";

const PREVIEW = { id: "not.registered", title: "No", shortcut: "N" };

registerCommands([
  { id: "shape.heart", title: "Add a heart", shortcut: "Mod+Alt+4", run: () => void add("heart") },
  { id: "shape.hexagon", title: "Add a hexagon", shortcut: "Mod+Alt+5", run: () => void add("hexagon") },
  { id: "shape.ring", title: "Add a ring", shortcut: "Mod+Alt+6", run: () => void add("ring") },
  { id: "shape.arrow", title: "Add an arrow", shortcut: "Mod+Alt+7", run: () => void add("arrow") },
  { id: "shape.frame", title: "Add a frame", shortcut: "Mod+Alt+8", run: () => void add("frame") },
]);

export const later = { id: "also.not.registered", title: "No", shortcut: "Y" };
'''


def make_src(tmp_path, actions=ACTIONS, files=None) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "actions.ts").write_text(actions, encoding="utf-8")
    if files is not None:
        (src / "cmd").mkdir()
        for name, text in files.items():
            (src / "cmd" / name).write_text(text, encoding="utf-8")
    return src


def ids(src: Path):
    return [cid for cid, _, _ in kb_commands.commands(kb_commands.registry_sources(src))]


CORE_IDS = ["app.one", "app.two", "view.zoom2", "view.zoom3", "view.zoom4", "view.zoom5", "view.zoom6",
            "view.zoom7", "view.zoom8", "view.zoom9", "app.three"]
SHAPE_IDS = ["shape.heart", "shape.hexagon", "shape.ring", "shape.arrow", "shape.frame"]


def test_kb_reads_only_the_core_array_when_there_is_no_cmd_folder(tmp_path):
    assert ids(make_src(tmp_path)) == CORE_IDS


def test_kb_reads_the_array_under_its_old_name_too(tmp_path):
    assert ids(make_src(tmp_path, ACTIONS.replace("CORE_COMMANDS", "COMMANDS"))) == CORE_IDS


def test_kb_prefers_the_core_array_over_a_combined_list(tmp_path):
    combined = ACTIONS + '\nexport const COMMANDS: Command[] = [...CORE_COMMANDS, { id: "no.twice", title: "T", shortcut: "U" }];\n'
    assert ids(make_src(tmp_path, combined)) == CORE_IDS


def test_kb_reads_each_cmd_file_in_name_order(tmp_path):
    files = {
        "zeta.ts": 'registerCommands([{ id: "zeta.x", title: "Zeta", shortcut: "Mod+Alt+9", run() {} }]);\n',
        "shapes.ts": SHAPES,
        # Only imports, with a comment that mentions the call.
        "index.ts": '// Each module here calls registerCommands([ ... ]) when it loads.\nimport "./shapes";\nimport "./zeta";\n',
        "helpers.ts": 'export const X = { id: "not.a.command", title: "X", shortcut: "X" };\n',
        # A test registering made-up commands is not the app's list.
        "shapes.test.ts": 'registerCommands([{ id: "fake.cmd", title: "Fake", shortcut: "F9" }]);\n',
    }
    src = make_src(tmp_path, files=files)
    assert ids(src) == CORE_IDS + SHAPE_IDS + ["zeta.x"]
    rows = kb_commands.commands(kb_commands.registry_sources(src))
    assert ("shape.heart", "Mod+Alt+4", "Add a heart") in rows


def test_kb_says_so_when_the_command_array_is_missing_or_never_closes(tmp_path):
    with pytest.raises(SystemExit, match="command array"):
        kb_commands.registry_sources(make_src(tmp_path, "export const OTHER = [];\n"))
    (tmp_path / "again").mkdir()
    with pytest.raises(SystemExit, match="never closed"):
        kb_commands.registry_sources(make_src(tmp_path / "again", "export const CORE_COMMANDS: Command[] = [\n"))


def test_kb_check_writes_nothing_and_fails_until_the_table_is_current(tmp_path, capsys):
    src = make_src(tmp_path, files={"shapes.ts": SHAPES})
    doc = tmp_path / "KB.md"
    doc.write_text(f"intro\n{kb_commands.START}\nan old table\n{kb_commands.END}\ntail\n", encoding="utf-8")
    before = doc.read_bytes()
    with pytest.raises(SystemExit, match="run python scripts/kb_commands.py"):
        kb_commands.main(["--check"], src_dir=src, kb_path=doc)
    assert doc.read_bytes() == before
    kb_commands.main([], src_dir=src, kb_path=doc)
    text = doc.read_text(encoding="utf-8")
    assert "| Add a frame | `Mod+Alt+8` | `shape.frame` |" in text and text.startswith("intro\n") and text.endswith("tail\n")
    written = doc.read_bytes()
    kb_commands.main(["--check"], src_dir=src, kb_path=doc)  # current: no exit
    assert doc.read_bytes() == written
    capsys.readouterr()


@pytest.mark.skipif(not (ROOT / "apps" / "desktop" / "src" / "actions.ts").exists(),
                    reason="needs the desktop app's source next to the engine")
def test_kb_reads_the_real_registry():
    rows = kb_commands.commands(kb_commands.registry_sources())
    found = {cid for cid, _, _ in rows}
    assert {"file.save", "shape.star", "view.zoom9", "view.panLeft", "player.slowerAlt"} <= found
    assert len(rows) > 150


# ---------------------------------------------------------------- snapshot_util.py


@pytest.fixture
def snapdir(tmp_path, monkeypatch):
    folder = tmp_path / "snapshots"
    monkeypatch.setattr(snapshot_util, "SNAPSHOT_DIR", folder)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("UPDATE_SNAPSHOTS", raising=False)
    return folder


def test_snapshot_check_records_a_missing_entry_then_compares(snapdir):
    snapshot_util.check("digitize", "b", {"records": 1})
    snapshot_util.check("digitize", "a", {"stitches": 2, "records": 3})
    assert (snapdir / "digitize.json").read_text() == (
        '{\n "a": {\n  "records": 3,\n  "stitches": 2\n },\n "b": {\n  "records": 1\n }\n}\n')
    snapshot_util.check("digitize", "b", {"records": 1})
    with pytest.raises(AssertionError, match="b stitches changed; review, then re-record with UPDATE_SNAPSHOTS=1"):
        snapshot_util.check("digitize", "b", {"records": 2})


def test_snapshot_check_fails_on_a_missing_entry_in_ci(snapdir, monkeypatch):
    monkeypatch.setenv("CI", "1")
    message = "no snapshot recorded for x: run the tests locally, review and commit snapshots/layout.json"
    with pytest.raises(pytest.fail.Exception, match=message):
        snapshot_util.check("layout", "x", {})
    assert not (snapdir / "layout.json").exists()


@pytest.mark.parametrize("value, records", [
    ("1", True), ("all", True), ("layout", True), ("digitize,layout", True), ("digitize, layout", True),
    ("digitize", False), ("layouts", False), ("0", False), ("", False),
])
def test_update_snapshots_records_every_suite_or_only_the_named_ones(snapdir, monkeypatch, value, records):
    snapshot_util.check("layout", "x", {"v": 1})
    monkeypatch.setenv("UPDATE_SNAPSHOTS", value)
    monkeypatch.setenv("CI", "1")
    if records:
        snapshot_util.check("layout", "x", {"v": 2})
        snapshot_util.check("layout", "new", {"v": 3})
        assert json.loads((snapdir / "layout.json").read_text()) == {"x": {"v": 2}, "new": {"v": 3}}
    else:
        with pytest.raises(AssertionError):
            snapshot_util.check("layout", "x", {"v": 2})
        with pytest.raises(pytest.fail.Exception):
            snapshot_util.check("layout", "new", {"v": 3})


@pytest.mark.parametrize("suite", ["digitize", "layout"])
def test_re_recording_a_committed_file_leaves_it_unchanged(snapdir, monkeypatch, suite):
    snapdir.mkdir()
    shutil.copy(SNAPSHOTS / f"{suite}.json", snapdir / f"{suite}.json")
    stored = json.loads((snapdir / f"{suite}.json").read_text())
    name = sorted(stored)[0]
    monkeypatch.setenv("UPDATE_SNAPSHOTS", suite)
    snapshot_util.check(suite, name, stored[name])
    def lines_only(path):  # a Windows checkout has CRLF line ends
        return path.read_bytes().replace(b"\r\n", b"\n")

    assert lines_only(snapdir / f"{suite}.json") == lines_only(SNAPSHOTS / f"{suite}.json")


@pytest.mark.parametrize("name", ["run_bean", "fill_bowtie", "applique_with_hole_run_tack"])
def test_digest_recs_is_what_test_digitize_records(name):
    recs = generate(test_digitize.SNAPSHOT_CASES[name])[0]
    stored = json.loads((SNAPSHOTS / "digitize.json").read_text())
    assert snapshot_util.digest_recs(recs) == test_digitize._digest(recs) == stored[name]


@pytest.mark.parametrize("name", ["knockdown_under_a_square", "basting_box_round_two_squares"])
def test_digest_pattern_is_what_test_layout_snapshots_records(name):
    rendered = layout.render(test_layout_snapshots.CASES[name](None))  # these two need no font
    stored = json.loads((SNAPSHOTS / "layout.json").read_text())
    assert snapshot_util.digest_pattern(rendered.pattern) == test_layout_snapshots._digest(rendered) == stored[name]
