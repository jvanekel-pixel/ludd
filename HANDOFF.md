# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-14
- **Current Phase:** Phase 2: 1.0.1 Hardening & Release
- **Active Routing:** balanced
- **What Changed:** Onboarded to Command Center: added AGENTS.md (old CLAUDE.md rules preserved inside it), CLAUDE.md (`@AGENTS.md`), SPEC.md, PLAN.md, project.json, DECISIONS.md, BACKLOG.md, INFO-REQUESTS.md, .env.example, _logs/.gitkeep, .gitignore entries and 4 skills in .claude/skills and .agents/skills. No app source code touched. The 1.0.1 working tree was then committed locally in 5 groups (engine, UI, Tauri/CI, docs, Command Center files); not pushed, not tagged (only tag is v1.0.0).
- **Checks Run:** `cd engine && uv run --locked pytest -q` pass (646 passed, 1 skipped); `pnpm typecheck` pass; `pnpm test` pass (192); `pnpm --filter @threadline/desktop build` pass. Not run: cargo test, `pnpm build:engine`, Tauri installer build.
- **Blocked On Human:** Decide the 20 open items in docs/QA-RESPONSE.md; approve pushing to GitHub.
- **Next Action:** With the owner's OK, push main and confirm CI is green on Windows, both Macs and Linux (nothing is pushed or tagged without the owner asking).
