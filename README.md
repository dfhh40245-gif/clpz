# CLPZ

Turn long videos into short clips worth posting — fully on your machine.

Paste a YouTube URL or drop in a video file, and CLPZ finds the moments that
stand on their own, transcribes them word-by-word, and renders captioned,
face-aware 9:16 clips you can edit and export. Processing (download, whisper
transcription, rendering, editing) runs **locally** — your videos never leave
your computer.

**Product shape:** a desktop app (Windows) is the actual workspace. The public
website exists to showcase, explain pricing, and offer signup/download — it is
not the clipping workspace, and nothing is processed in the browser.

---

## Repository layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI server — auth, credits, jobs/pipeline API, serves all frontends |
| `backend/pipeline/` | yt-dlp download, faster-whisper transcription, ffmpeg rendering |
| `frontend/` | Vanilla HTML pages: landing (`index.html`), auth, dashboard, admin |
| `frontend-app/` | React (Vite) app — public landing + auth under `/new/*`; built to `dist/` |
| `desktop/` | Desktop wrapper (PyWebView) + frozen-app launcher logic |
| `packaging/` | Windows build/installer scripts; build outputs are git-ignored |
| `docs/` | `PRODUCTION_CONFIG.md` (env reference), `RELEASE.md` (release strategy) |
| `deploy/`, `scripts/` | Legacy server deploy helpers (kept for reference) |

## Development run (no login or credits required)

Requires Python 3.12+ and `ffmpeg`/`ffprobe` on PATH (or in `backend/bin/`).

```bash
pip install -r backend/requirements.txt          # + requirements_desktop.txt for the app
python run_desktop.py                            # desktop app (private mode)
# or serve just the web UI:
cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000
# → http://127.0.0.1:8000/new  (React landing), /app (dashboard), /admin
```

Optional dev env: `CLPZ_DEBUG=1` (default, loose limits + dev codes),
`CLPZ_ADMIN_EMAIL=<email>` marks an account admin. See `docs/PRODUCTION_CONFIG.md`
for every variable and the production checklist — the packaged app forces
`CLPZ_DEBUG=0` and stores user data under `%LOCALAPPDATA%\CLPZ\data` (never in
Program Files).

## Tests

```bash
cd backend
python -m pytest tests/ -m "not slow" -v -q     # fast suite (~90 tests)
python -m pytest tests/ -m "slow" -v -q         # full pipeline E2E (needs ffmpeg)
```

## Windows release

```bash
python packaging/build_windows.py                # builds the installer
```

The installer bundles the backend, ffmpeg/ffprobe/yt-dlp/deno, the whisper
model + VAD assets, and both frontends — **no Python install required** on the
target machine. Recorded build hash and the release/update/signing strategy
live in `packaging/RELEASE_SHA256.txt` and `docs/RELEASE.md`.

## Architecture notes

- **Private mode:** the dev `.bat`/local workflow works with no account.
  Web signup/login exists for the future hosted flow; browser-to-desktop
  session handoff is not implemented yet (documented limitation).
- **Auth/credits security:** every credit mutation is server-authoritative;
  account-owned jobs are only visible to their owner (or admin); admin
  endpoints require the admin account. One idempotency key maps to exactly
  one job, so a retried submission can never double-charge or create a
  duplicate job.
- **No cloud backend:** authentication, credits and jobs are stored locally
  in SQLite under the data directory. There is no Supabase or other hosted
  service dependency; processing (transcription, rendering) runs entirely on
  the user's machine.
