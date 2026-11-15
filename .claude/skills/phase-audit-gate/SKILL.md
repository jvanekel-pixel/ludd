---
name: phase-audit-gate
description: Run when every task in the active PLAN.md phase is checked. Verifies tests and build, reviews the diff, reports at most 5 findings, and updates health.
---

# Phase Audit Gate

1. Confirm every task in the active phase of `PLAN.md` is `- [x]`.
2. Run the test, typecheck and build commands from `AGENTS.md`. Record pass or fail.
3. Review `git diff` for the phase. Look for bugs, drift from `SPEC.md`, secrets, and violated project rules.
4. Report at most 5 concrete findings, ordered by severity (Critical, High, Medium, Low), each with file and line.
5. Park any extra findings and QoL ideas in `BACKLOG.md` as `- [ ]` lines.
6. Update `project.json`: `health.tests`, `health.build`, `health.lastAuditedPhase` (set to this phase number), and advance `phase` and `nextAction`.
7. Overwrite `HANDOFF.md` (<=25 lines). Start the next phase in a fresh chat.
