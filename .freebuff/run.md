# ClipForge — preview run doc

FastAPI backend (`backend/`) serving a static single-page frontend (`frontend/index.html`) at `/`.
No Node/npm involved — this is a Python project.

## Reproduce artifacts (fresh checkout)

1. **No secret env files needed.** There is no `.env`/`.env.local` — every setting
   has a default in `backend/config.py` and is overridable via env vars. `backend/cookies.txt`
   (YouTube session cookies) is optional: if present, yt-dlp uses it automatically.
   Copy it from the main checkout only if the job you run gets YouTube bot-checks.
2. **Python venv** (already exists as `backend/.venv`, Windows layout):
   ```
   python -m venv backend/.venv
   backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
   ```
3. **System tools** (checked at startup by `backend/main.py::_check_binaries`; the app
   exits if missing): `ffmpeg` and `ffprobe` (`winget install Gyan.FFmpeg`), and `yt-dlp`
   (installed by requirements.txt, but must be on PATH — venv Scripts dir qualifies).

## Run the server

From the project root, with the venv active (or via its Scripts path):

```
cd backend
../backend/.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

- Default port **8000** (README + `main.py` docstring). Use another port if 8000 is busy.
- Frontend loads at `http://127.0.0.1:8000/` — the app reads `frontend/index.html` on each request.
- Optional auth: set `CLIPFORGE_PASSWORD` to require HTTP Basic on all routes.
- Jobs persist under `backend/data/<job_id>/`; finished clips survive restarts.

### Detached start (Windows, no bash needed)

```
powershell -NoProfile -Command "(Start-Process -FilePath 'C:\Users\oSSS\Desktop\clipforge-main\backend\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory 'C:\Users\oSSS\Desktop\clipforge-main\backend' -RedirectStandardOutput '<log>' -RedirectStandardError '<log>.err' -WindowStyle Hidden -PassThru).Id"
```

Confirm survival with `Get-Process -Id <pid>`, then wait for `http://127.0.0.1:8000/` to answer
before registering the preview.
