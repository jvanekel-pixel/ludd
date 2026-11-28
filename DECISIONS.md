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

### D-013: AI tracing model is pinned and checksummed (2026-11-14)
- Decision: the MobileSAM download comes from one fixed upstream revision, and each file is checked against its SHA-256 before it is kept.
- Why: a moving `main` branch could change or be tampered with, and the app runs the downloaded model.
- Alternatives rejected: keep fetching `main`; bundle the 45 MB model in the installer.
- Revisit if: upstream publishes a better model (update `REVISION` and the checksums in `ai/segment.py`).

### D-014: GitHub Actions pinned by commit SHA, Dependabot monthly (2026-11-14)
- Decision: every workflow action uses a full commit SHA with the version in a comment; Dependabot opens grouped monthly update PRs (actions, npm, cargo, uv).
- Why: the repo is public and builds the signed releases.
- Alternatives rejected: version tags only.
- Revisit if: Dependabot PRs become noise.

### D-015: US spelling in the app and docs (2026-11-14)
- Decision: Center, Millimeters, Licenses, color everywhere users read; code comments and internal names are left alone.
- Why: the body text was already US; the UK labels were the odd ones out.
- Alternatives rejected: UK spelling throughout.
- Revisit if: the app is localized.

### D-016: A pinned shape stays put (2026-11-14)
- Decision: pin blocks arrow keys, R, Alt+H/V and resize handles for shapes, and the arrows for pictures, with a note saying why.
- Why: pin means "can't be moved by accident"; moving it by keyboard broke that.
- Alternatives rejected: pin blocks dragging only.
- Revisit if: users want to nudge a pinned shape without unpinning.

### D-017: Open QA items kept as they are (2026-11-14)
- Decision: autosave stays off while the Recover banner is unanswered; wide satins only warn; pen-tool curve overshoot stays; the 400,000-stitch fill limit stays; crafted .vp3/.hus memory use is documented (L-024), not guarded; JEF codes wait for a Janome stitch-out. Full table in docs/QA-RESPONSE.md.
- Why: each fix would change existing designs, add a large mechanism, or needs hardware we don't have.
- Alternatives rejected: change defaults now.
- Revisit if: a user hits one of them in practice.

### D-018: Dependabot updates are reviewed and merged in combined PRs (2026-11-15)
- Decision: Dependabot groups only minor/patch updates; majors come one per PR. tauri-action and @types/node majors are ignored. Updates that must move together (Tauri JS + Rust plugins; Actions on neighbouring lines; dev tools sharing pnpm-lock.yaml) are merged as one combined PR after CI is green. Merged so far: #10 (Python), #16 (Tauri plugins + safe npm), #17 (five Actions), #18 (TypeScript 7, vitest 5, jsdom 31, @types/node 22). All other Dependabot PRs are closed; none are open.
- Why: each of those pairs fails alone (Tauri version check, lockfile conflicts), and tauri-action 1.0 would break release.yml.
- Alternatives rejected: merging Dependabot PRs one at a time as they come.
- Revisit if: the release workflow is moved to tauri-action 1.x (needs release.yml changes and a draft release check), or Vite is upgraded (then @vitejs/plugin-react 6, closed as #12, can follow).
- Open when work resumes: the CI run on main after #17 and #18 (e415eb3) was not checked; run `pnpm install` locally before the next build; Pillow 13 (passed all tests earlier) can come back as its own PR.

### D-019: Features first, stitch-outs once near the end (2026-11-24)
- Decision: Phase 2 is closed. Phases 3 to 14 are build phases; machine testing happens once, in Phase 15; fixes, the public manual and the 2.0 release are Phase 16. Tagging v1.0.1 is an owner action outside the phases.
- Why: the owner wants the gaps from the competitive review (docs/COMPETITIVE-REVIEW.md) closed while a larger plan is available, and D-012 already holds stitch-outs until the software is about 95% done.
- Alternatives rejected: stitch-out verification as Phase 3, before any new feature.
- Revisit if: a stitch-out shows a foundation problem (density, compensation). BUILDPLAN.md suggests an optional early look at six foundation rows after Phase 8.

### D-020: Build protocol: one spec per phase, one phase per session, planner and worker split (2026-11-24)
- Decision: each phase has one spec file in docs/phases/; BUILDPLAN.md says how a session runs. The top model plans and audits, Sonnet builds from the spec, tests and `scripts/check.py` do the reviewing, tracks inside a phase are built in parallel by workers in their own worktrees, and the heavy phases go first.
- Why: the owner's five rules for keeping token use low and results right the first time.
- Alternatives rejected: planning inside build sessions; one long session across phases; reviewing by re-reading code.
- Revisit if: specs keep failing their preflight (they are going stale faster than they are built).

### D-021: Phase 5 lettering decisions (2026-11-25)
- Decision: no look inside BX fonts (L-036: use the letter files that came with the font); True satin is a choice beside Satin look, not the default; installed-font letters under 6 mm sew without underlay (this changes how small text in existing designs sews); six built-in monogram frames (circle, double circle, diamond, square, scallop circle, laurel).
- Why: the owner confirmed the Phase 5 spec's recommended answers.
- Alternatives rejected: examining a BX font; True satin as the default before it has been sewn; keeping underlay on tiny letters.
- Revisit if: the Phase 15 stitch-outs show True satin sews better than Satin look, or small letters unravel without underlay.

### D-022: Phase 7 decisions: lines, sequencing and drawing tools (2026-11-26)
- Decision: artwork import uses svgelements and ezdxf (with pyparsing) for SVG and DXF, and pypdfium2 (PDFium) for PDF; in a branch LUDD chooses each shape's start and end and the order of shapes that don't overlap, and Branch moves the shapes next to each other in the sewing order; the five built-in stitch presets ship.
- Why: the owner answered yes to the two new-library questions and confirmed the Phase 7 spec's recommended answers to the rest.
- Alternatives rejected: a hand-written SVG-only reader and no DXF; no PDF library; no built-in presets.
- Revisit if: one of the libraries stops shipping wheels for a platform LUDD builds for, or the Phase 15 stitch-outs show a branch's hidden travel shows through.
