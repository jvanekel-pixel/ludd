# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-14
- **Current Phase:** Phase 2: 1.0.1 Hardening & Release
- **Active Routing:** balanced
- **What Changed:** The owner decided all 20 open QA items (table in docs/QA-RESPONSE.md). Done: AI tracing model download pinned to one upstream revision with SHA-256 checks; GitHub Actions pinned by commit SHA plus `.github/dependabot.yml`; pinned shapes/pictures ignore arrows, R, Alt+H/V and resizing; Browse designs Refresh button; AI send preview shows LUDD's fixed instructions; US spelling in the app, manual, guide, KB and Help; jsdom added (`*.dom.test.tsx`); AGENTS.md fixed (networkx, onnxruntime, schemas, light fabric); stale root PDF deleted. Parked in BACKLOG.md: items 3, 7, 10, 14, thumbnails on disk, memory guard for .vp3/.hus (L-024), writing the other schemas. Committed as ed160f1 and pushed to origin/main with the owner's OK; nothing tagged.
- **Checks Run:** engine `CI=1 uv run --locked pytest -q` pass (650 passed, 1 skipped); `pnpm typecheck` pass; `pnpm test` pass (196). Not run: `pnpm build`, cargo test, `pnpm build:engine`, installer build, the app itself.
- **Blocked On Human:** Nothing. Optional: regenerate docs/LUDD-User-Manual.pdf (still the old wording).
- **Next Action:** Check the first CI run on GitHub is green on Windows, both Macs and Linux (the pinned Actions are untried); press Download in Settings → AI tracing once to confirm the model checksums. Then the second QA pass (docs/QA-PROMPT.md), then tag v1.0.1 only when the owner asks.
