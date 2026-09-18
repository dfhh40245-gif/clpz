# Task 13 — Verified Windows installers and media tools

Task: 13 (release build toolchain)
Commit: 76e4b0a (baseline; tasks 01–13 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14; yt-dlp standalone 2026.08.19 (official release); PyInstaller **not installed** in venv; Inno Setup **not installed** on this machine

## Original reproduction

AUDIT.md F15/F16: bundled `yt-dlp.exe --version` exits 1 with no output and
the release command did not rebuild the UI, invoke Inno Setup, or fail on
absent/empty trees.

**Root cause established (new evidence):** the old `backend/bin/yt-dlp.exe`
was not a standalone binary but a **pip entry-point launcher stub** — a PE
executable embedding a zip-app (`__main__.py`) with a baked shebang
`#!C:\Python314\python.exe`. On any machine without Python 3.14 at that exact
path it exits 1 silently. Diagnosed via `unzip -l` (only `__main__.py`) and a
PE-header shebang scan.

## Scope and policy decisions

- **Binary replacement policy**: the bundled exe was replaced with the
  **official standalone yt-dlp.exe** release build (2026.08.19), checksum
  verified against the publisher's `SHA2-256SUMS`
  (`66674953fe251b89f4d08c5f0e35e0728679bd67ab3d7d05c0562af101dd3e7a`) and
  smoke-checked (`--version` → rc 0). Provenance and update procedure
  documented in `docs/BUNDLED_BINARIES.md`.
- **Fallback chain**: the downloader now prefers a smoke-verified bundled exe
  and falls back to `python -m yt_dlp` (the module ships inside the frozen
  server), so the installed app never depends on the developer machine's PATH.
- **One release command**: `packaging/build_windows.py` now (a) smoke-checks
  every bundled tool, (b) refuses stale PyInstaller output (wipes `dist/`),
  (c) rebuilds the React UI via `npm ci && npm run build` (unless explicitly
  skipped), (d) treats required binaries/frontends/models as mandatory (fail,
  not warn), (e) audits with a missing/empty tree counted as FAILURE, and
  (f) writes `RELEASE_SHA256.txt` + `release-manifest.json` (version via
  `CLPZ_VERSION`/`APP_VERSION`, centralized).
- **Inno Setup**: the installer spec documents the exact `ISCC.exe` build
  step and the release command prints it as the next step; ISCC is not
  programmatically invoked from Python because Inno Setup's console
  compiler is an external install (kept explicit, per prompt: "separate
  assembly from signing/publishing").
- Version centralization: `APP_VERSION` in build_windows.py feeds the
  manifest; the installer `.iss` pins the same version string.

## Files changed

- `backend/bin/yt-dlp.exe`: replaced with verified official standalone build (17.8 MB).
- `backend/pipeline/downloader.py`: `_ytdlp_command()` exe→module fallback chain.
- `packaging/build_windows.py`: smoke checks, mandatory assets, dist wipe, UI rebuild, strict audit, release manifest + hashes, centralized version.
- `docs/BUNDLED_BINARIES.md` (new): provenance table, F15 root cause, update procedure.
- `backend/tests/test_release_toolchain.py` (new): 9 regression tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Bundled tools actually execute | `pytest tests/test_release_toolchain.py::TestBundledToolSmoke` + `build_windows.py --audit-only` | all version checks rc 0 | ffmpeg/ffprobe/yt-dlp/deno smoke OK | PASS | test + audit output |
| yt-dlp is standalone (not launcher stub) | `...::test_bundled_ytdlp_is_standalone_and_runs` | rc 0, version output, >5 MB | 2026.08.19, 17.8 MB | PASS | test output |
| Checksum matches publisher | `sha256sum` vs official SHA2-256SUMS | exact match | `66674953…dd3e7a` | PASS | docs/BUNDLED_BINARIES.md |
| Module fallback when exe missing | `...::TestDownloaderFallback` | `[python, -m, yt_dlp]` | As expected | PASS | test output |
| Audit fails on missing/empty tree | `build_windows.py --audit-only` after `rm -rf packaging/out`; `...::TestAuditStrictness` | exit 1 | exit 1, "AUDIT FAILED: no assembled package" | PASS | command output |
| Audit fails on broken bundled tool | `...::test_smoke_check_rejects_broken_tool` | loud failure | As expected | PASS | test output |
| Version centralized | `...::TestVersionCentralization` | APP_VERSION → manifest; .iss pinned | As expected | PASS | test output |
| Full backend suite unaffected | `pytest tests -m "not slow" -q` | all pass | **254 passed, 1 skipped, 9 deselected** | PASS | test output |

## NOT RUN / BLOCKED (owner prerequisites)

- **Clean-build installer**: PyInstaller and Inno Setup are not installed on
  this machine; producing the actual `CLPZ-Setup-Windows-x64.exe` and running
  the offline install/upgrade/uninstall matrix on a Python-less Windows
  account is **BLOCKED** on those installs (and is task 22's clean-machine run).
- **Release hash ↔ installer correspondence**: `RELEASE_SHA256.txt` is
  generated for the assembled tree by the release command; installer hashing
  is automatic once the installer step runs.
- npm rebuild path implemented but not exercised here (no npm on PATH on this
  machine); the command fails loudly with install instructions instead of
  silently shipping a stale UI.

## Migration and rollback

Rollback = restore previous `backend/bin/yt-dlp.exe` (broken; not
recommended) and revert the three changed files. No data/schema changes.

## Remaining blockers

- Install PyInstaller + Inno Setup on a build machine; run the full release
  command end-to-end; execute the clean-machine acceptance matrix (task 22).
- Record ffmpeg/deno SHA-256 in `docs/BUNDLED_BINARIES.md` at next refresh.

## Artifact name and SHA-256

Not produced this session (toolchain not installed). The next full build
must hash `CLPZ-Setup-Windows-x64.exe` into `RELEASE_SHA256.txt`.

## Reviewer

Pending owner review.
