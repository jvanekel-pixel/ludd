# Releasing LUDD

Releases are built by GitHub Actions (`.github/workflows/release.yml`) for Windows, Mac (Apple
chip and Intel) and Linux, and uploaded to a **draft** release. Nothing is public until you press
Publish on the draft.

## One-time setup

1. **Repository.** The updater looks for releases at
   `https://github.com/jvanekel-pixel/ludd/releases/latest/download/latest.json`
   (`apps/desktop/src-tauri/tauri.conf.json` → `plugins.updater.endpoints`). If the repository has
   another name, change that address before the first release.
2. **Update-signing key.** Updates are signed so the app only installs genuine ones. The key pair
   was generated on the owner's PC (Oct 11, 2026):
   - private key: `%USERPROFILE%\.tauri\ludd-updater.key`
   - its password: `%USERPROFILE%\.tauri\ludd-updater.password.txt`
   - public key: in `tauri.conf.json` (`plugins.updater.pubkey`)

   Add two **repository secrets** (GitHub → Settings → Secrets and variables → Actions):
   `TAURI_SIGNING_PRIVATE_KEY` (the whole contents of the .key file) and
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` (the password). Then keep a copy of both somewhere safe,
   such as a password manager: **if the key is lost, installed copies can't be updated** (people
   would have to download the next version by hand). Never commit them; `.gitignore` blocks `*.key`.
   To set the secrets from a terminal:

   ```bash
   gh secret set TAURI_SIGNING_PRIVATE_KEY < "$USERPROFILE/.tauri/ludd-updater.key"
   gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD < "$USERPROFILE/.tauri/ludd-updater.password.txt"
   ```

## Each release

1. Update the version in `apps/desktop/src-tauri/tauri.conf.json`, `apps/desktop/package.json`,
   `apps/desktop/src-tauri/Cargo.toml`, `engine/pyproject.toml` and `engine/threadline_engine/__init__.py`.
2. Update `docs/CHANGELOG.md` and `docs/release-notes.md` (the text on the release page).
3. If the samples changed: `uv run --project engine python scripts/make_samples.py`.
4. Commit, then tag and push: `git tag v1.0.1 && git push origin main v1.0.1`.
5. Wait for the Release workflow (about 20 minutes), open the draft on the Releases page, check
   the files are there (four installers plus `latest.json`), and press **Publish**. Installed
   copies see the update the next time they start.

## Code signing (optional, recommended)

Without it, LUDD installs and runs fine, but Windows shows "Windows protected your PC" (More
info → Run anyway) and macOS asks you to allow it in Privacy & Security. Signing removes those
warnings for everyone.

- **Windows.** Options, cheapest first: [SignPath Foundation](https://signpath.org/) signs
  open-source projects for free (you apply); Microsoft's Azure Trusted Signing is a low monthly fee
  with identity checks; or buy a code-signing certificate from a certificate authority (typically
  a few hundred dollars a year). With a `.pfx` certificate, add the secrets `WINDOWS_CERTIFICATE`
  (the .pfx file, base64-encoded) and `WINDOWS_CERTIFICATE_PASSWORD`; the workflow signs
  automatically when they're present. Other services need a `signCommand` in `tauri.conf.json`
  (see the Tauri docs on Windows code signing).
- **Mac.** Needs an Apple Developer account ($99 a year). Add the `APPLE_*` secrets listed in the
  workflow; the build then signs and notarizes the app.

## Building an installer on your own PC

```bash
pnpm build:engine
pnpm tauri build --config '{"bundle":{"createUpdaterArtifacts":false}}'
```

The installer lands in `apps/desktop/src-tauri/target/release/bundle/nsis/`. (Leave out the
`--config` part only if the two `TAURI_SIGNING_*` variables are set, as in the workflow.)
