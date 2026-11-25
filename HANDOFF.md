# Session Handoff (Overwrite Every Session — <=25 Lines)

- **Updated:** 2026-11-24
- **Current Phase:** Phase 2: 1.0.1 Hardening & Release (only the owner's model-download check and the v1.0.1 tag left); first Phase 4 item started early at the owner's request
- **Active Routing:** balanced
- **What Changed:** Merged to main today: #19 (Phase 1 audit notes, D-018), #20 (QA pass 2 report + 29 fixes), #21 (owner's 10 QA decisions, stitch output changes), #22 (3 Phase 1 audit fixes). CI on main green.
  This branch (`feat/stitch-estimate`): sewing time and thread estimate (F-406). `design/estimate.ts` (stitches ÷ machine speed; thread = stitch + uncut jump lengths + 1 mm per stitch; bobbin = 1/3), shown in the Design section (Sewing time, Thread, Thread used per color). Machine profiles gain optional `speed_spm` (PE550D and generic Janome 650; null = 600) in profiles.py, machine.schema.json, types.ts.
- **Checks Run:** `pnpm typecheck` pass; `pnpm test` pass (44 files, 241); engine pytest pass (657 passed, 1 skipped; this worktree has no git-ignored fixtures/, so the fixture tests aren't collected). Not run: the app by hand, cargo test.
- **Two-Strike (installer):** `pnpm tauri build --config '{"bundle":{"createUpdaterArtifacts":false}}'` on main failed twice at the NSIS bundling step with "os error 32: file in use" (after "NSIS.exe is outdated / directory missing files. Recreating it"). No LUDD/NSIS process was running. Likely antivirus holding the freshly downloaded NSIS tools in %LOCALAPPDATA%\tauri\NSIS. Engine freeze + smoke and the Rust build both passed. Workaround: CI's `ludd-windows` artifact from the main run.
- **Blocked On Human:** Owner OK to download the CI installer artifact (or to retry after excluding %LOCALAPPDATA%\tauri from the antivirus); owner checks Settings > AI tracing > Download once; owner OK to commit/PR this branch.
- **Next Action:** PR this branch after the owner's OK; tag v1.0.1 when the owner asks; stitch-out row not needed (no stitch output change).
