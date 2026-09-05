# CLPZ — Release, Signing & Update Strategy

Status: **pre-release (v1.0.0 candidate)**. This file records the decisions and
state required to publish the first public release. Environment config lives in
`PRODUCTION_CONFIG.md`; build/package automation lives in `packaging/`.

---

## 1. Version numbering

Semantic versions, `MAJOR.MINOR.PATCH`:

- `MAJOR` — incompatible product change or first public release.
- `MINOR` — new capability, backwards compatible.
- `PATCH` — bug fixes, no behaviour change.

The current version is stamped at build time from `packaging/clipforge.spec`
/ the installer script. Source of truth for the running build: the About /
diagnostics screen plus the artifact filename below.

## 2. Release artifact naming

One artifact per platform, versioned and checksummed:

```
CLPZ-<version>-Windows-x64-setup.exe      (example: CLPZ-1.0.0-Windows-x64-setup.exe)
```

Current build (v1.0.0 candidate): `ClipForge-1.0.0-Windows-x64.exe`
(279,327,796 bytes). See `packaging/RELEASE_SHA256.txt` for the recorded hash —
re-verify it whenever a new artifact is produced, and never ship an artifact
whose hash differs from the published value.

## 3. Release location & procedure (first public release)

1. Create a git tag `v1.0.0` on the release commit.
2. Build the installer locally: `python packaging/build_windows.py` (Windows only).
3. Compute SHA-256 and write it next to the artifact (`RELEASE_SHA256.txt`).
4. **Upload the installer as a GitHub Release asset** (releases page) — do not
   commit the 266 MB `.exe` to the repository (`.gitignore` already excludes
   `packaging/out/`, `packaging/build/`, `packaging/dist/`).
5. Paste the release notes + hash into the release body.
6. Point the public website's "Download for Windows" button at the GitHub
   Release asset URL (the website currently has **no** download link — wiring
   it up requires the hosting URL, which is an external blocker).

## 4. Update method (v1: manual)

No auto-updater for the first release. Simplest reliable flow:

- **Check:** user opens the website's download page or is told via the app
  About dialog to check for a newer release.
- **Download + install:** run the new installer over the old install.
- **Data safety:** all user data lives in `%LOCALAPPDATA%\CLPZ\data` and
  `~\Videos\CLPZ Clips` — never inside Program Files. Installing a new version
  never touches those folders, so updates are safe to run over the top.
- **Compatibility promise:** within the 1.x line, new installers read existing
  data directories unchanged. A future breaking change (2.0) must document a
  data migration before release.

## 5. Code signing

**Current status: unsigned.** No code-signing certificate is available in this
environment.

Consequences, documented rather than hidden:

- Windows SmartScreen will warn "Windows protected your PC" on first run.
  Users must click *More info → Run anyway*. The installer is a one-time
  download; the running app is not affected.
- The artifact is **not** faked as signed — no self-signed or repurposed
  certificate is used.

Before a wide launch, obtain an OV/EV code-signing certificate (Authenticode)
and sign both the installer and `clpz_server.exe`/`CLPZ.exe`, then validate
with `Get-AuthenticodeSignature` (Status must be `Valid`). This is an external
purchase decision — not performed automatically.

## 6. Known release limitations (recorded, not papered over)

1. **Website has no working Download action yet** — needs a hosting URL /
   GitHub Releases asset link (external).
2. **Browser → desktop authentication handoff is not implemented.** The public
   flow ends at signup/login on the website; the desktop app does not yet
   consume the web session. Users run the desktop app in private/local mode.
3. **Supabase is not activated** — no real project credentials exist in this
   environment (see chunk 19 report). Until activated, auth/credits use the
   local SQLite backend and website signup does not create a Supabase account.
4. **Unsigned binary** → SmartScreen warning (section 5).
5. **Vercel deployment not performed** — no Vercel project/token available;
   `vercel.json` and the static `frontend/` output are ready to deploy.

## 7. First-release checklist (Chunk 20)

- [ ] Host the installer (GitHub Release) and record final SHA-256
- [ ] Add real "Download for Windows" link to the website (React landing + legacy page)
- [ ] Activate Supabase project with `supabase_schema.sql` (reviewed, not yet run)
- [ ] Deploy static site to Vercel with `CLPZ_DEBUG=0`-equivalent env (marketing only; no backend on Vercel)
- [ ] Add real application screenshots to the landing page
- [ ] Decide signing purchase (SmartScreen) before wide launch
