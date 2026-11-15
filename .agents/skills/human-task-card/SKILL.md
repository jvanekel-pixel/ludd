---
name: human-task-card
description: Format a blocker that only the human can resolve as a short, checkable task card.
---

# Human Task Card

Pick the first method that works, in this priority: Script, then PowerShell, then Browser UI, then Manual.

Format:

```
HUMAN TASK: <short title>
Method: <Script | PowerShell | Browser UI | Manual>
Goal: <one sentence>
Steps (<=5):
1. ...
2. ...
Done when: <one observable condition, e.g. a command output or a visible page state>
```

Rules:
- Never ask for secret values in chat; say where the human should put them.
- Never use more than 5 steps. If more are needed, split into two cards.
- Copy the blocker into `project.json` `blockedOnHuman` and into `HANDOFF.md` "Blocked On Human".
- List standing needs in `INFO-REQUESTS.md`.
