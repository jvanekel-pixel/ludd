# INFO-REQUESTS

Missing keys, accounts, credentials and human decisions needed to run or ship the project. No secret values go in this file.

## Needed from the owner
- [x] Approve committing the uncommitted working tree (done; committed and pushed 2026-11-14)
- [x] Decide the 20 open items at the end of docs/QA-RESPONSE.md (decided and applied 2026-11-14)
- [ ] Look at the first CI run on GitHub (Actions tab) and press Download in Settings → AI tracing once, to confirm the pinned Actions and model checksums work
- [ ] Say when the software is about 95% done so machine stitch-outs can start (docs/stitchout-log.md)
- [ ] A Janome machine or tester for the JEF hoop and stop-code check (item 9), or accept it as unverified
- [ ] Confirm the name "LUDD" is free before promoting the first public release

## Secrets and accounts already set up (names only)
- GitHub repo `jvanekel-pixel/ludd` with repository secrets `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (updater signing; key file lives in `%USERPROFILE%\.tauri`, keep a password-manager copy)

## Optional, not required to run
- [ ] Apple Developer ID and a Windows code-signing certificate (removes SmartScreen/Gatekeeper warnings; paid)
- [ ] A user-supplied Anthropic or OpenAI-compatible API key for the optional AI add-on (entered in the app's Settings, never in the repo)
