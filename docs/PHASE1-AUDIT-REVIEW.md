# Phase 1 audit: review and fix list

Reviewed 2026-11-15 against `main` at e7dde6e (uncommitted: the audit's own edits to BACKLOG.md, HANDOFF.md, project.json).
The audit was the Phase-Close Audit Gate for Phase 1 (M0–M10, v1.0.0). Each finding below was checked in the code, not taken from the audit's word.

## Verdict

**Nothing critical.** No data loss, no crash, nothing that reaches the network, nothing a user of the shipped app can be hurt by.
The audit's findings are accurate. Its severity order overstates two of them (see below).
All three open items are safe to fix in a normal Phase 2 session. Per BACKLOG.md, get the owner's OK first.

## Open items, in the order I'd fix them

| # | Item | Verified | Real severity | Effort |
|---|------|----------|---------------|--------|
| 1 | **S (Zoom to the selection) ignores multi-select.** `zoomSelected()` (`apps/desktop/src/actions.ts:1774`) zooms to `targetId()` only. With several items selected (Shift+click, Ctrl+A, a group) it zooms to the primary one; with no primary it does nothing. | Yes | Low, but **user-visible**: the only one a hobbyist will notice | Small |
| 2 | **AI key file is briefly world-readable on macOS/Linux.** `set_key()` (`engine/threadline_engine/ai/settings.py:137-139`) writes `ai-key.bin` then chmods it to 600, so for a moment it has umask permissions (usually 644). Off Windows the key is only base64 (`_protect`, line 180), not encrypted. | Yes | Low: needs another local user on the same machine at that instant, and AI is off by default and user-keyed. The write is also not atomic (a crash mid-write leaves a broken key file; the user just re-enters it). | Small for the atomic 600 write; larger for a keychain (new dependency, e.g. `keyring`, plus bundling and tests on each OS) |
| 3 | **Dev engine bridge.** `apps/desktop/vite-engine-bridge.ts:78-99` has no body size cap, and a JSON-RPC notification (no `id`) would leave a `pending` entry and an open HTTP response. | Yes | Very low: dev-only (`apply: "serve"`), already limited to localhost origins, and **the UI never sends notifications** (`RpcClient` only makes calls), so the leak can't happen today. | Small |

## Fix notes

1. `zoomSelected()`: if an image is selected keep the current path; otherwise use `selectionGeometry(selectionIds()).box` and `requestZoom("box", { box })` when it's non-null. `selectionGeometry` already handles moved items and objects without render bounds. Add a UI test (several items selected → zoom box covers all of them). No KB/CHANGELOG change is strictly needed if the KB already says "zoom to the selection", but check F-entries for S and add a CHANGELOG line ("S now zooms to all selected items").
2. `set_key()`: write to a temp file created with `os.open(tmp, O_WRONLY|O_CREAT|O_EXCL, 0o600)` in the same folder, fsync, then `os.replace` (same pattern as `storage.write_json`). That fixes both the permission window and atomicity. Leave the keychain as a separate BACKLOG item; it's a design decision (new dependency) for the owner. Add a pytest that checks the mode is 600 on non-Windows (skip on Windows).
3. Bridge: reject bodies over a few MB with 413; if `msg.id` is undefined, forward to the engine and answer 204 immediately without adding to `pending`.

## What the audit said was fixed: confirmed on `main`

- Tauri CSP has `connect-src 'self' ipc: http://ipc.localhost` (`tauri.conf.json:24`).
- `threads.py` validates `chart_id` with `_check_id()` before building paths (lines 200, 301).
- `print.ts` routes colors through `safeColor()` (lines 29, 98).
- `project.py` has `MAX_IMAGE_PIXELS` and `MAX_MEMBER_BYTES` limits.
- `updates.ts` stops the engine before `pending.install()`.
- No duplicate `player.*` command IDs remain.

These were shipped bugs in v1.0.0 and are fixed for v1.0.1. Nothing to do except make sure v1.0.1 actually ships.

## Problems with the audit itself (not with the code)

- **HANDOFF.md was overwritten** and lost the Phase 2 history (QA decisions done, CI fixes at 46b0de4, what was pushed). It's in git (`git show HEAD:HANDOFF.md`) if needed. Another session is building right now and will overwrite HANDOFF.md again at its stop, so don't hand-merge anything into it until that session finishes.
- `project.json` was reformatted (the `platforms` array split over lines) and gained `blockedSinceAt: null`. Harmless, but noisy in the diff.
- Not run in the audit: `cargo test`, `pnpm build:engine`, the installer build, or the app itself. CI covered the installer at 46b0de4.
- The three audit edits (BACKLOG.md, HANDOFF.md, project.json) are uncommitted. Commit them together with, or after, the other session's work, only when the owner asks.

## Suggested order for the next fix session

1. Wait for the building session to finish; check `git status` for overlap with `actions.ts` or `ai/settings.py`.
2. Ask the owner to OK BACKLOG items 1–3 above.
3. Fix 1, then 2 (atomic write only), then 3. Run engine tests, `pnpm typecheck`, `pnpm test`.
4. Tick the BACKLOG lines, update CHANGELOG/KB for item 1.
