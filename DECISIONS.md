# DECISIONS

Durable log so future sessions do not re-litigate these. Newest decisions go below the template. Never delete a decision; mark it superseded.

## Template
```
### D-NNN: <Title> (YYYY-MM-DD)
- Decision: <what was chosen>
- Why: <1-2 sentences>
- Alternatives rejected: <list>
- Revisit if: <condition>
```

### D-001: Tauri 2 + React + TypeScript + Vite shell (2026-10-11)
- Decision: Tauri 2 (Rust) desktop shell with a React 19 / TypeScript / Vite UI; PixiJS for the stitch canvas, SVG overlay for handles; Zustand for state with a command pattern for undo.
- Why: small installers on Windows/Mac/Linux, built-in updater, bundled sidecar support, and the owner already knows React.
- Alternatives rejected: Electron (size), a native UI toolkit (skills), Immer (plain immutable updates were enough).
- Revisit if: WebGL performance on 100k+ stitch designs becomes a problem.

### D-002: Python 3.12 engine as a JSON-RPC sidecar (2026-10-11)
- Decision: all stitch math, file I/O and vision run in a Python sidecar over JSON-RPC 2.0 on stdio, frozen with PyInstaller. The UI only draws and sends commands.
- Why: the embroidery ecosystem (pyembroidery, shapely, OpenCV) lives in Python.
- Alternatives rejected: porting to Rust or TypeScript; networkx (planned, never needed).
- Revisit if: sidecar size or startup time becomes a release blocker. The dev server starts the engine itself (`vite-engine-bridge.ts`).

### D-003: Objects are the source of truth; stitches are derived (2026-10-11)
- Decision: designs store shapes and parameters in millimetres; stitches are regenerated and cached by object hash; 0.1 mm conversion happens only at export. Imported stitch files are edited in a separate stitch-edit mode.
- Why: resizing never wrecks density, and projects outlive the app.
- Revisit if: never without a migration plan.

### D-004: Project format is a zip (`.ludd`) with embedded reference images (2026-10-11)
- Decision: `design.json` plus the original image bytes and placement; `.thl` projects still open.
- Why: owner requirement after Embrilliance lost a source image after a reboot. Test: save, delete the original, reopen.
- Revisit if: file size becomes a problem.

### D-005: GPL-3.0-or-later (2026-10-11)
- Decision: license is GPL-3.0-or-later; code may be adapted from Ink/Stitch with credit and their notices kept.
- Why: lets proven satin, fill and lettering code be ported.
- Alternatives rejected: MIT (would force clean-room stitch algorithms).

### D-006: PES primary, JEF second (2026-10-11)
- Decision: Brother PE550D is the target; PES is primary and JEF must export correctly; golden tests cover both. PES files run from (0, 0) like Embrilliance writes them. Cut-stops mode exists because the PE550D only cuts at color changes.
- Why: the owner's machine. JEF hoop and stop codes still need a Janome stitch-out.

### D-007: AI is optional, off by default, behind providers (2026-10-11)
- Decision: `engine/threadline_engine/ai/providers.py` offers Off / Ollama / Anthropic or OpenAI-compatible with the user's own key. The core makes no network calls. Nothing is auto-applied; every suggestion is previewed and accepted or dismissed. MobileSAM (Apache-2.0) is an optional download; onnxruntime is skipped on Intel Macs.
- Why: no account, billing or server to run; works offline forever.

### D-008: Name LUDD, internal identifiers stay (2026-10-11)
- Decision: product name is LUDD (was Threadline). `threadline_engine`, the `threadline-engine` sidecar, `THREADLINE_DATA_DIR` and npm package names stay. `.thl`, `.tlfont` and the old `Threadline` data folder keep working.
- Why: renaming internals risks breaking saved data for no user benefit.

### D-009: GitHub Releases with signed updater, unsigned installers (2026-10-11)
- Decision: `release.yml` builds on `v*` tags into one DRAFT release, then writes `latest.json` once at the end; the owner presses Publish. Updater key lives in `%USERPROFILE%\.tauri` (never committed). Installers are not code-signed (paid certificates).
- Why: one draft for all builds avoids partial public releases.
- Revisit if: SmartScreen/Gatekeeper warnings stop friends from installing.

### D-010: Brand and theming via CSS tokens (2026-10-11)
- Decision: ink #121114, bone #EEE9DF, techno yellow #C8FF2E; Archivo and Space Mono bundled (OFL); light and dark follow the system; canvas fabric stays light.

### D-011: UX is "Don't make me think" (2026-10-11)
- Decision: default view shows only what a beginner needs; adjustables live behind "More options" or the ⋯ menu, never removed; every command is in the registry with a shortcut; Embrilliance keys are reused where they exist.

### D-012: Machine testing deferred (2026-10-11)
- Decision: no stitch-outs until the owner says the software is about 95% done; tests are queued in `docs/stitchout-log.md`.
