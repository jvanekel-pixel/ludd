# BUILDPLAN: how LUDD gets built from here

Static on purpose, like `AGENTS.md`: no dates, counts or status. Live state is in `HANDOFF.md`, `project.json` and the checkboxes in `PLAN.md`. The spec for each phase is one file in `docs/phases/`.

## 1. The five rules

| # | Rule | What it means here |
| --- | --- | --- |
| 1 | **Plan in chat, build in Claude Code.** | Architecture and specs are written in a planning chat and saved as one file per phase (`docs/phases/PHASE-NN-*.md`). A build session never re-plans. If a spec is wrong, the session stops that track and writes the question down; the spec is fixed in a planning chat. |
| 2 | **One phase per session.** | A fresh session per phase. It reads this file, that phase's file and `HANDOFF.md`, and nothing else unless the phase file points at it. |
| 3 | **Match the model to the job.** | The top model plans, refreshes specs and audits. A cheaper model builds from the spec. Section 3 has the table. |
| 4 | **Let tests do the reviewing.** | Every item ships with the tests its spec names. The session lead judges work by `python scripts/check.py` and the numbers in a worker's report, not by reading the worker's code. |
| 5 | **Front-load the heavy builds.** | Heavy phases run while the larger plan is active, with tracks in parallel. Lighter months are for spec refreshes, one track per session, and the stitch-outs. Section 8 has the order. |

## 2. Where things live

| File | Holds | Who writes it |
| --- | --- | --- |
| `PLAN.md` | Phases and checkboxes (the Command Center tracker) | Session lead, at stop |
| `docs/phases/README.md` | Phase index, ID blocks, reserved shortcuts, rules every phase inherits | Planning chat |
| `docs/phases/PHASE-NN-*.md` | One phase's whole spec | Planning chat; a build session may add a dated "Build notes" section at the end, nothing else |
| `HANDOFF.md` | 25 lines from the last session | Session lead, at stop (overwrite) |
| `project.json` | Phase number, next action, health | Session lead, at stop |
| `DECISIONS.md` | Durable decisions (`D-NNN`) | Session lead, when the owner decides something |
| `BACKLOG.md` | Ideas that turned up mid-build | Anyone; never built without the owner pulling them into a phase |

## 3. Roles and models

| Role | Does | Model |
| --- | --- | --- |
| Planner | Writes and refreshes phase specs | Top model (Fable 5.2 where the plan offers it, otherwise Opus 5.5), in a planning chat |
| Session lead | Runs one phase: preflight, Step 0, launches workers, integrates, writes docs | Sonnet 5.5 |
| Worker | Builds one track from the spec, tests first | Sonnet 5.5 |
| Hard-track worker | Builds a track the phase file marks **Hard** | Opus 5.5 or the top model, for that track only |
| Scout | Read-only lookups (find a function, summarize a log) | Haiku 5.5 |
| Auditor | Phase audit and release audit | Top model, in its own short session; Antigravity as `AGENTS.md` says |

Choose the session's model in the app's model picker before sending the kickoff prompt. The lead sets each worker's model when it launches it.

## 4. A phase session, step by step

**Start**
1. Run the `session-handoff` skill's start steps. Read this file's sections 4 to 7, the phase file, `HANDOFF.md`.
2. Confirm the owner's answers to the phase's "Owner decisions". No answer means the spec's "If no answer" column.
3. Run the phase's **Preflight** table. A failed check means the spec is stale or a dependency is missing: stop and say which check.
4. Run `python scripts/check.py`. It must print `RESULT: PASS` before anything changes. Note the counts. (Phase 3 builds this script; until it exists use the commands in `AGENTS.md`.)

**Step 0: contracts before code**
5. Create the phase branch (`phase-NN/<slug>`) from `main`.
6. Do the phase file's Step 0 yourself: types, RPC stubs and their names in `rpc_methods.json`, feature flags, command registrations with stub handlers, empty modules. After it, every track has fixed names to build against and no two tracks need the same file.
7. `python scripts/check.py`, then commit. Workers start from this commit.

**Fan out**
8. Launch one worker per track, all in one message so they run together. Each gets its own git worktree, the model the phase file names, and the brief in section 5. If the phase has waves, launch one wave at a time.
9. While they work, do nothing that touches their files. Prepare the docs payload text.

**Integrate**
10. As each worker reports, read only its report (20 lines). Merge track branches in the order the phase file gives. Run `python scripts/check.py` after each merge.
11. A red check after a merge: read the failing test's name and message, fix the integration (not the worker's design), re-run. Two failed attempts at the same error: stop, as section 9 says.

**Docs**
12. Write the phase's docs payload in one pass: `docs/CHANGELOG.md`, `docs/LUDD-KNOWLEDGE-BASE.md`, `docs/USER-MANUAL.md`, `engine/threadline_engine/ai/helpdocs.py`, `docs/stitchout-log.md`. Run `python scripts/kb_commands.py`.

**Verify and stop**
13. `python scripts/check.py --all`. Check each line of the phase's "Done when".
14. Stop contract (`AGENTS.md`): tick the finished tasks in `PLAN.md`; overwrite `HANDOFF.md` with what the phase file's Handoff section asks for; update `project.json`; `log_session` to Command Center.
15. Tell the owner what was built, the check result, and what is waiting on them. Do not push, open a pull request, tag or merge until they say so.

**Commits.** `AGENTS.md` says never to commit without the owner asking. The kickoff prompt is where the owner asks: it allows local commits on the phase branch and its track branches, and nothing else. Without that line, build the tracks one after another in the working tree and commit nothing.

## 5. Worker rules

The lead launches each worker with this brief, filled in:

```
Build Track <X> of Phase <N> of LUDD. You are one of several workers building in parallel.

Read: docs/phases/PHASE-<NN>-<slug>.md, section 7, "Track <X>" (and the sections it points to),
and docs/phases/README.md "Rules every phase inherits". Read nothing else unless the track names it.

Your worktree should be at <commit> on <phase branch>. Check with git log -1; if not, stop.
Create branch phase-<NN>/track-<x> and commit there.

Rules:
1. Tests first. Write the tests the track lists, see them fail, then make them pass.
2. Touch only the files under "Owns". If you need a change elsewhere, do not make it: report it.
3. Do not edit CHANGELOG, the knowledge base, the manual, helpdocs or stitchout-log. The lead writes docs.
4. No existing snapshot may change unless the track says so. Record new ones with
   python scripts/check.py --record <suite>.
5. If the spec is wrong or unclear: pick the reading that passes the listed tests and note it,
   or, if no reading does, stop and report. Do not redesign.
6. Two failed attempts at the same error: stop and report (two-strike rule).
7. Finish with python scripts/check.py on your branch.

Report, in 20 lines or fewer: branch and last commit; the check.py verdict line by line;
each listed test not passing, with its one-line reason; each spec deviation; any file outside
"Owns" you needed. No code in the report.
```

A worktree has no `node_modules`, no engine virtual environment and no `fixtures/` at first: `pnpm install --frozen-lockfile` once, and `uv run --locked` builds the environment on first use. Fewer engine tests run without `fixtures/`; that is expected.

## 6. Tests do the reviewing

- A track is done when its listed tests pass and `check.py` is green on its branch. The lead does not read the diff to decide that.
- What the lead does read: the worker's report; `git diff --stat` against the Step 0 commit (to see that only owned files changed); the names of new tests (to see the listed ones exist); for stitch changes, the new snapshot entries' counts.
- Stitch types are judged by numbers: the invariants in `engine/tests/invariants.py` (inside the shape, no stitch over 7 mm, repeatable, moves with the shape), coverage and density figures the spec asks for, and snapshots. A snapshot that changes without the spec saying so is a bug in the change.
- Thread on fabric is judged in Phase 15. Until then every stitch-changing item adds its row to "Pending machine tests".
- **Phase audit** (every phase): a fresh session on the top model runs the `phase-audit-gate` skill. Its inputs are `check.py --all`, the diff stat, and the phase's "Done when". It reports at most five findings and stamps `project.json`.
- **Release audit** (at each release checkpoint): the top model runs `docs/QA-PROMPT.md` against everything since the last release.

## 7. Building in tandem

- A **track** is a set of items that share files with no other track in its phase. Each phase file lists what a track owns. Tracks are sized for one worker in one context.
- **Step 0** exists so tracks never need the same file: anything shared (a type union, a registry list, the method list) is edited once, up front.
- **Waves**: where a track needs another's output, the phase file puts it in a later wave.
- **Lighter months (one track per session):** run Step 0 in the first session and commit. Then one session per track, each given the worker brief directly, on the phase branch. Integrate in a last short session. The spec is the same; only the pace changes.
- **Two phases at once:** phases the index marks as depending only on Phase 3 can run in two sessions, each on its own branch in its own worktree. The second to merge rebases. Expect small, mechanical conflicts where both add a line: `design/types.ts`, `project.py` feature flags, `rpc_methods.json`, `cmd/index.ts`, `design/fillPatterns.ts`, the changelog and the knowledge base. Keep both sides. Phase 12's language track is the exception: it touches nearly every UI file and runs with nothing else in flight.

## 8. Order and pace

Heavy phases first, in number order: 3, 4, 5, 6, 7, 8, 9, 10. These are the multi-track builds; run them while the larger plan is active, one phase per session, a phase audit after each.

| When | Do |
| --- | --- |
| Larger plan | Phases 3 to 10 with tracks in parallel; hard tracks on the stronger model |
| Lighter months | Phase 11 and 12 one track per session; refresh the specs of phases still ahead; Phase 15 (the owner at the machine); Phase 16 fixes; maintenance |
| Either | Phases 13 and 14 are extras: build them whole on a larger-plan month, or their tracks one at a time |

**Spec refresh.** Before a phase from 11 on is built (or any phase more than a month after its spec was written), spend one planning chat on it: run its Preflight, fix what has drifted, answer its owner decisions. Prompt in section 10.

**Release checkpoints** (the owner's call each time; `docs/RELEASING.md` has the steps):

| Version | After | Carries |
| --- | --- | --- |
| 1.0.1 | Phase 2, before Phase 3 merges | The hardening work and the sewing time estimate |
| 1.1 | Phases 3 to 5 | Repair bought designs, lettering |
| 1.2 | Phases 6 to 8 | Fills, lines, specialty |
| 1.3 | Phases 9 to 12 | Pictures, library, learning, machines |
| 2.0 | Phases 15 and 16 | Everything, checked on the machine |

Until a release is cut, changelog entries go under the unreleased heading and version numbers stay as they are.

**Stitch-outs.** Deferred to Phase 15 by the owner (D-012, D-019). One recommendation that stays the owner's choice: after Phase 8, when every stitch-changing engine feature is in, a short session at the machine on the six rows marked "foundation" in `docs/phases/PHASE-15-stitch-out-verification.md` would catch a density or compensation problem before five more phases are built on it.

## 9. When something goes wrong

| Situation | Do |
| --- | --- |
| Preflight fails | Stop. Report the check. The spec needs a refresh. |
| The spec contradicts the code | Small: take the reading that passes the listed tests, add one line to the phase file's "Build notes". Large: stop the track, write the question under "Blocked On Human" in `HANDOFF.md`. |
| A worker reports red | Read its report. If the cause is in its own files, send it back once with the failing test. If it needs a file it does not own, the lead makes that change. |
| Two failed attempts at one error | Two-strike rule: stop, log it in `HANDOFF.md`, tell the owner. Each phase file names what ships anyway. |
| A snapshot changed that should not have | Treat as a bug. Never re-record to make it pass. |
| A track will not fit the session | Stop after the last green merge. Write what is left in `HANDOFF.md`. The rest is its own session. |
| A good idea appears mid-build | `BACKLOG.md`. Not this phase. |
| An owner decision is unanswered | The spec's "If no answer" column. Never guess past it. |
| A held item's decision is "no" | Move its line from `PLAN.md` to `BACKLOG.md` with the reason and the `L-` entry that records the gap. Do not tick it. |
| The session's checkout lacks `fixtures/` (a worktree) | Fewer engine tests run. Say so in `HANDOFF.md`; the owner's main checkout or the next session there runs the full set. |

## 10. Prompts

**Start a phase** (fresh session, Sonnet 5.5 chosen in the model picker):

```
Build Phase <N> of LUDD.

Read, in this order and nothing else yet: BUILDPLAN.md sections 4 to 7,
docs/phases/PHASE-<NN>-<slug>.md, HANDOFF.md. If the phase file is not in your checkout, stop
and tell me (the plan has not reached this branch).

Follow BUILDPLAN.md section 4 exactly: preflight, Step 0, then fan the tracks out to parallel
workers, each in its own worktree with the model the phase file names; integrate; docs; check;
stop contract.

You may commit locally on branch phase-<NN>/<slug> and its track branches. Do not push, open a
pull request, tag, merge into main or publish anything until I say so.

Owner decisions for this phase: <your answers, or "use the spec's defaults">.

If preflight fails or the spec does not match the code, stop and tell me. Do not improvise.
```

**One track at a time** (lighter months; Step 0 already committed on the phase branch):

```
Build Track <X> of Phase <N> of LUDD on branch phase-<NN>/<slug>, yourself, no workers.
Read BUILDPLAN.md section 5 and follow its worker rules; read the track in
docs/phases/PHASE-<NN>-<slug>.md. You may commit locally on that branch. Do not push.
Finish with python scripts/check.py and a 20-line report.
```

**Audit a phase** (fresh session, top model):

```
Audit Phase <N> of LUDD with the phase-audit-gate skill. Inputs: python scripts/check.py --all,
git diff --stat main...phase-<NN>/<slug>, and the "Done when" list in
docs/phases/PHASE-<NN>-<slug>.md. Read code only where a check or a done-when line points you.
At most five findings, worst first. Change nothing except what the skill stamps.
```

**Refresh a spec** (planning chat, top model):

```
Refresh docs/phases/PHASE-<NN>-<slug>.md for LUDD before it is built. Run its Preflight against
the code as it is now, read the modules it names, and update the file where names, files or
behavior have drifted. Keep its structure and its IDs. List the owner decisions I still need to
answer. Change no code.
```
