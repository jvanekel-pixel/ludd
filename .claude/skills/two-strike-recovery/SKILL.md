---
name: two-strike-recovery
description: Stop editing after two consecutive failures on the same error. Log it and escalate instead of looping.
---

# Two-Strike Recovery

Trigger: the same command or error has failed twice in a row after you changed code.

1. Stop editing. Do not try a third variation.
2. Record in `HANDOFF.md` (still <=25 lines): the exact command, the error trimmed to <=30 lines, and the files you touched.
3. Set `project.json` `blockedOnHuman` if a human is needed; otherwise leave it null.
4. Escalate, in this order:
   - a fresh chat with only `HANDOFF.md` as context,
   - an Antigravity audit of the failing area,
   - a Human Task Card (see the `human-task-card` skill).
5. Do not revert unrelated work to "make it pass".
