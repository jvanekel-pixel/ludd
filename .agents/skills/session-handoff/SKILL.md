---
name: session-handoff
description: Start and stop every work session cleanly. Use at the start of a session to load context, and at the end to write HANDOFF.md, update project.json and check off PLAN.md.
---

# Session Handoff

## At start
1. Read `AGENTS.md`, `HANDOFF.md`, and `project.json`.
2. Read only the active phase in `PLAN.md` (the `phase` number in `project.json`). Skip the others.
3. If the Command Center MCP is connected, call `get_project_context`.
4. Work on `nextAction` only. Park new ideas in `BACKLOG.md`.

## At stop
1. Run the quiet verification commands from `AGENTS.md` (summarize failures to <=30 lines).
2. Check off finished tasks as `- [x]` in `PLAN.md`. Only check a task that is verified in the repo.
3. Overwrite `HANDOFF.md` (<=25 non-empty lines) using its existing field labels: Updated, Current Phase, Active Routing, What Changed, Checks Run, Blocked On Human, Next Action.
4. Update `project.json`: `phase`, `nextAction`, `blockedOnHuman`, `lastSessionAt` (ISO-8601), `health.tests`, `health.build` (only values you actually ran).
5. Call `log_session` if the Command Center MCP is connected.
