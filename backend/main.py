"""CLPZ API. Run with:  uvicorn main:app --host 0.0.0.0 --port 8000

Optional auth: set CLIPFORGE_PASSWORD to require HTTP Basic auth (any username).
Recommended whenever the port is reachable beyond your own IP.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

import auth as auth_mod
import config
import credits as credits_mod
import jobs

_PASSWORD = os.getenv("CLIPFORGE_PASSWORD", "")
_security = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_security)):
    if not _PASSWORD:
        return

    ok = creds is not None and secrets.compare_digest(
        creds.password, _PASSWORD
    )

    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Basic"},
        )


def _get_session_user(request: Request) -> str | None:
    """Extract user_id from session cookie. Returns None if not logged in."""
    token = request.cookies.get("clpz_session", "")
    if not token:
        # Also check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return auth_mod.validate_session(token)


def get_current_user(request: Request) -> str:
    """Dependency: require authenticated user. Returns user_id."""
    user_id = _get_session_user(request)
    if not user_id:
        raise HTTPException(401, "Please log in.")
    return user_id


def optional_user(request: Request) -> str | None:
    """Dependency: optional authentication. Returns user_id or None."""
    return _get_session_user(request)


def _check_binaries():
    import platform
    import shutil

    bin_dir = Path(__file__).resolve().parent / "bin"
    is_windows = platform.system() == "Windows"

    missing = []
    for b in ("ffmpeg", "ffprobe", "yt-dlp"):
        # Check PATH first
        if shutil.which(b):
            continue
        # Check backend/bin/ (bundled binaries)
        exe_name = f"{b}.exe" if is_windows else b
        if (bin_dir / exe_name).exists():
            continue
        missing.append(b)

    if missing:
        raise SystemExit(
            f"Missing required tools on this machine: {', '.join(missing)}.\n"
            "ffmpeg/ffprobe: install via your OS (apt install ffmpeg / "
            "winget install Gyan.FFmpeg). yt-dlp: pip install -r "
            "requirements.txt inside the active virtualenv."
        )


app = FastAPI(
    title="CLPZ",
    dependencies=[Depends(require_auth)],
)

# Allow the OpenCut editor (running on a different port) to fetch clips
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_check_binaries()
jobs.load_saved_jobs()

# The original dashboard remains in frontend/index.html as a fallback.  The
# production shell below is the Manus-inspired, API-backed interface.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
LANDING = FRONTEND_DIR / "index.html"
AUTH_PAGE = FRONTEND_DIR / "auth.html"
DASHBOARD = FRONTEND_DIR / "clpz.html"

YT_RE = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?|shorts/|live/)|youtu\.be/)",
    re.I,
)


# ── Authentication endpoints ────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class ResetRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
def signup(req: SignupRequest):
    try:
        user = auth_mod.create_user(req.email, req.password, req.display_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Grant signup bonus exactly once (server-authoritative)
    credits_mod.ensure_signup_bonus(user["id"])
    token = auth_mod.create_session(user["id"])
    resp = JSONResponse({"user": user, "credits": credits_mod.get_balance(user["id"])})
    resp.set_cookie("clpz_session", token, httponly=True, samesite="lax", max_age=86400 * 7)
    return resp


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = auth_mod.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    # Ensure signup bonus was granted (idempotent)
    credits_mod.ensure_signup_bonus(user["id"])
    balance = credits_mod.get_balance(user["id"])
    token = auth_mod.create_session(user["id"])
    resp = JSONResponse({"user": user, "credits": balance})
    resp.set_cookie("clpz_session", token, httponly=True, samesite="lax", max_age=86400 * 7)
    return resp


@app.post("/api/auth/logout")
def logout(request: Request):
    token = request.cookies.get("clpz_session", "")
    if token:
        auth_mod.destroy_session(token)
    resp = JSONResponse({"message": "Logged out."})
    resp.delete_cookie("clpz_session")
    return resp


@app.get("/api/auth/me")
def get_me(user_id: str = Depends(get_current_user)):
    user = auth_mod.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user["credits"] = credits_mod.get_balance(user_id)
    return {"user": user}


@app.post("/api/auth/reset")
def reset_password(req: ResetRequest):
    try:
        ok = auth_mod.reset_password(req.email, req.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "No account found with that email.")
    return {"message": "Password reset successfully."}


# ── Credit endpoints ─────────────────────────────────────────────

@app.get("/api/credits/balance")
def credit_balance(user_id: str = Depends(get_current_user)):
    balance = credits_mod.get_balance(user_id)
    return {"balance": balance, "cost_per_forge": credits_mod.COST_PER_FORGE}


@app.get("/api/credits/transactions")
def credit_transactions(user_id: str = Depends(get_current_user)):
    txns = credits_mod.get_transactions(user_id)
    return {"transactions": txns}


class JobRequest(BaseModel):
    url: str
    max_clips: int = Field(
        default=config.MAX_CLIPS_DEFAULT,
        ge=1,
        le=10,
    )
    top_text: str = Field(
        default="",
        max_length=200,
    )
    auth_token: str = Field(default="")


def _job_payload(job: dict) -> dict:
    """Return the public job representation without creating another store.

    Media URLs are deterministic views of the persisted clip record.  The
    job JSON remains the single source of truth for rendered media metadata.
    """
    for clip in job.get("clips", []):
        if clip.get("status") != "done":
            continue
        index = clip.get("index")
        if index is None:
            continue
        refreshed = jobs.ensure_clip_metadata(job["id"], index)
        if refreshed:
            clip.update(refreshed)
        base = f"/api/jobs/{job['id']}/clips/{index}"
        clip["stream_url"] = f"{base}/stream"
        clip["download_url"] = base
        if jobs.clip_thumbnail_path(job["id"], index):
            clip["thumbnail_url"] = f"{base}/thumbnail"
    return job


@app.get("/", response_class=HTMLResponse)
def index():
    return LANDING.read_text(encoding="utf-8")


@app.get("/auth.html", response_class=HTMLResponse)
def auth_page():
    return AUTH_PAGE.read_text(encoding="utf-8")


@app.get("/app", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD.read_text(encoding="utf-8")


@app.post("/api/jobs")
def create_job(req: JobRequest, request: Request):
    url = req.url.strip()

    if not YT_RE.match(url):
        raise HTTPException(
            400,
            "That doesn't look like a YouTube URL.",
        )

    # Optional auth: associate job with user if logged in
    user_id = None
    if req.auth_token:
        user_id = auth_mod.validate_session(req.auth_token)
    if not user_id:
        user_id = _get_session_user(request)

    # Charge credits BEFORE creating the job (atomic check-and-deduct)
    if user_id:
        ok, remaining = credits_mod.check_and_charge(
            user_id, credits_mod.COST_PER_FORGE
        )
        if not ok:
            raise HTTPException(
                402,
                f"Not enough credits. You need {credits_mod.COST_PER_FORGE} credit(s) "
                f"but have {remaining}.",
            )
    else:
        remaining = None

    try:
        job_id = jobs.create_job(
            url,
            req.max_clips,
            req.top_text,
            user_id=user_id,
        )
    except Exception:
        # Refund if job creation failed after charge
        if user_id and remaining is not None:
            credits_mod.refund(
                user_id, credits_mod.COST_PER_FORGE,
                reason="Job creation failed — refund"
            )
        raise

    return {"job_id": job_id, "credits_remaining": remaining}


@app.get("/api/jobs")
def list_jobs():
    """List persisted projects for the Projects screen."""
    all_jobs = jobs.get_all_jobs()
    all_jobs.sort(key=lambda job: job.get("created_at", 0), reverse=True)
    return [_job_payload(job) for job in all_jobs]


@app.post("/api/jobs/upload")
async def upload_job(
    request: Request,
    file: UploadFile = File(...),
    max_clips: int = Form(config.MAX_CLIPS_DEFAULT),
    top_text: str = Form(""),
):
    if not file.filename:
        raise HTTPException(
            400,
            "No file selected.",
        )

    allowed = {
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".m4v",
        ".mpeg",
        ".mpg",
    }

    ext = Path(file.filename).suffix.lower()

    if ext not in allowed:
        raise HTTPException(
            400,
            "Unsupported video format.",
        )

    if not 1 <= max_clips <= 10:
        raise HTTPException(
            400,
            "max_clips must be between 1 and 10.",
        )

    user_id = _get_session_user(request)

    # Charge credits BEFORE creating the job (atomic check-and-deduct)
    if user_id:
        ok, remaining = credits_mod.check_and_charge(
            user_id, credits_mod.COST_PER_FORGE
        )
        if not ok:
            raise HTTPException(
                402,
                f"Not enough credits. You need {credits_mod.COST_PER_FORGE} credit(s) "
                f"but have {remaining}.",
            )
    else:
        remaining = None

    try:
        job_id = jobs.create_upload_job(
            filename=file.filename,
            max_clips=max_clips,
            top_text=top_text,
            user_id=user_id,
        )
    except Exception:
        if user_id and remaining is not None:
            credits_mod.refund(
                user_id, credits_mod.COST_PER_FORGE,
                reason="Upload job creation failed — refund"
            )
        raise

    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = job_dir / f"source{ext}"

    try:
        with video_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                out.write(chunk)

    except Exception:
        raise HTTPException(
            500,
            "Failed to save uploaded video.",
        )

    jobs.start_uploaded_job(
        job_id,
        str(video_path),
        file.filename,
    )

    return {"job_id": job_id, "credits_remaining": remaining}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get_job(job_id)

    if not job:
        raise HTTPException(404, "Job not found.")

    return _job_payload(job)


@app.post("/api/jobs/clear")
def clear_old_jobs():
    """Clear completed/errored jobs older than 24 hours."""
    jobs._cleanup_old_jobs(max_age_hours=24, keep_minimum=0)
    remaining = len(jobs.get_all_jobs())
    return {"message": f"Old jobs cleared. {remaining} job(s) remaining.", "remaining": remaining}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    """Retry a failed/cancelled job from the last completed stage."""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job.get("stage") not in ("error", "cancelled"):
        raise HTTPException(400, "Only failed or cancelled jobs can be retried.")

    # Clear the error state and mark as queued for reprocessing
    completed = list(job.get("completed_stages", []))
    with jobs._lock:
        jobs.JOBS[job_id].update({
            "stage": "queued",
            "error": None,
            "error_code": None,
            "progress": 0.0,
            "completed_stages": completed,
        })
        jobs._persist(jobs.JOBS[job_id])

    # Create a new cancel event
    jobs._cancel_events[job_id] = threading.Event()

    t = threading.Thread(target=jobs._run, args=(job_id,), daemon=True)
    t.start()

    return {"job_id": job_id, "resumed_from": completed}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    ok = jobs.cancel_job(job_id)
    if not ok:
        raise HTTPException(400, "Job cannot be cancelled.")
    return {"message": "Job cancelled.", "job_id": job_id}


@app.get("/api/diagnostics")
def diagnostics():
    """Return system diagnostic information."""
    import platform
    import shutil
    import psutil

    info = {
        "platform": platform.system(),
        "python": platform.python_version(),
    }

    # Binary checks
    for name in ("ffmpeg", "ffprobe", "yt-dlp"):
        info[name] = "found" if shutil.which(name) else "missing"

    # Whisper
    try:
        import faster_whisper
        info["whisper"] = f"v{faster_whisper.__version__}"
    except ImportError:
        info["whisper"] = "missing"

    # Memory
    try:
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / 1024**3, 1)
        info["ram_available_gb"] = round(mem.available / 1024**3, 1)
        info["ram_percent"] = mem.percent
    except Exception:
        info["ram"] = "unavailable"

    # Disk
    try:
        disk = psutil.disk_usage(str(config.DATA_DIR))
        info["disk_free_gb"] = round(disk.free / 1024**3, 1)
    except Exception:
        info["disk"] = "unavailable"

    # CPU count
    info["cpu_count"] = os.cpu_count() or 1

    # OpenCut
    info["opencut"] = "available" if _find_opencut_dir() else "missing"

    return info


@app.get("/api/jobs/{job_id}/clips/{index}")
def download_clip(job_id: str, index: int):
    path = jobs.clip_path(
        job_id,
        index,
    )

    if not path:
        raise HTTPException(404, "Clip not ready.")

    job = jobs.get_job(job_id)

    title = next(
        (
            c["title"]
            for c in job["clips"]
            if c["index"] == index
        ),
        f"clip_{index}",
    )

    safe = (
        re.sub(r"[^\w\- ]", "", title)
        .strip()
        .replace(" ", "_")
        or f"clip_{index}"
    )

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{safe}.mp4",
    )


@app.get("/api/jobs/{job_id}/clips/{index}/stream")
def stream_clip(job_id: str, index: int):
    """Play the real rendered MP4 inline without triggering a download."""
    path = jobs.clip_path(job_id, index)
    if not path:
        raise HTTPException(404, "Clip not ready.")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/jobs/{job_id}/clips/{index}/thumbnail")
def clip_thumbnail(job_id: str, index: int):
    """Serve the thumbnail extracted from the verified rendered clip."""
    path = jobs.clip_thumbnail_path(job_id, index)
    if not path:
        raise HTTPException(404, "Clip thumbnail not ready.")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/clips/{index}/ass")
def clip_ass(job_id: str, index: int):
    """Return the ASS subtitle file for a clip (used by the editor)."""
    job_dir = config.DATA_DIR / job_id
    job = jobs.get_job(job_id)
    clip = next((c for c in (job or {}).get("clips", []) if c.get("index") == index), {})
    ass_path = Path(clip.get("ass_file") or (job_dir / f"clip_{index}.ass"))
    if not ass_path.exists():
        raise HTTPException(404, "ASS file not found.")
    return FileResponse(
        ass_path,
        media_type="text/plain",
        filename=f"clip_{index}.ass",
    )


def _unique_path(directory: Path, filename: str) -> Path:
    """Return a unique file path in directory, appending (1), (2) etc. if needed."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".mp4"
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


@app.post("/api/jobs/{job_id}/clips/{index}/save")
def save_clip(job_id: str, index: int):
    """Save a rendered clip to the user's Videos/CLPZ Clips folder."""
    path = jobs.clip_path(job_id, index)
    if not path:
        raise HTTPException(404, "Clip not ready.")

    clips_dir = config.CLIPS_DIR
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Build a clean filename from the clip title
    job = jobs.get_job(job_id)
    title = next(
        (c["title"] for c in job["clips"] if c["index"] == index),
        f"clip_{index}",
    )
    safe = (
        re.sub(r"[^\w\- ]", "", title)
        .strip()
        .replace(" ", "_")
        or f"clip_{index}"
    )
    dest = _unique_path(clips_dir, f"{safe}.mp4")

    shutil.copy2(str(path), str(dest))

    return {
        "saved_to": str(dest),
        "filename": dest.name,
        "folder": str(clips_dir),
    }


# ── OpenCut integration ──────────────────────────────────────────────
_opencut_proc: subprocess.Popen | None = None
_opencut_port: int = 0
_opencut_lock = threading.Lock()


def _find_opencut_dir() -> Path | None:
    """Locate the OpenCut classic checkout relative to the backend."""
    for candidate in [
        Path(__file__).resolve().parent.parent / "OpenCut",
        Path(__file__).resolve().parent.parent / "opencut",
    ]:
        if (candidate / "apps" / "web" / ".next" / "standalone").exists():
            return candidate
        if (candidate / "apps" / "web" / "package.json").exists():
            return candidate
    return None


def _start_opencut() -> int:
    """Start the OpenCut production server (on-demand). Returns the port."""
    global _opencut_proc, _opencut_port
    with _opencut_lock:
        if _opencut_proc and _opencut_proc.poll() is None:
            return _opencut_port

        oc_dir = _find_opencut_dir()
        if not oc_dir:
            raise HTTPException(500, "OpenCut not found.")

        web_dir = oc_dir / "apps" / "web"
        bun = _find_bun()
        if not bun:
            raise HTTPException(500, "Bun not found.")

        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            _opencut_port = s.getsockname()[1]

        env = os.environ.copy()
        env["PORT"] = str(_opencut_port)
        env["HOST"] = "127.0.0.1"

        _opencut_proc = subprocess.Popen(
            [bun, "run", "start"],
            cwd=str(web_dir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for the server to be ready
        import urllib.request
        for _ in range(30):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{_opencut_port}/", timeout=2
                )
                return _opencut_port
            except Exception:
                continue

        raise HTTPException(500, "OpenCut failed to start.")


def _find_bun() -> str | None:
    """Find the bun executable."""
    bun = shutil.which("bun")
    if bun:
        return bun
    # Check common Windows locations
    for candidate in [
        Path.home() / ".bun" / "bin" / "bun.exe",
        Path("C:/Users") / os.getenv("USERNAME", "") / ".bun" / "bin" / "bun.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    return None


@app.post("/api/edit")
def start_editor(job_id: str, clip_index: int):
    """Start OpenCut editor for a specific clip. Returns the editor URL."""
    path = jobs.clip_path(job_id, clip_index)
    if not path:
        raise HTTPException(404, "Clip not ready.")

    port = _start_opencut()

    return {
        "url": f"http://127.0.0.1:{port}/projects",
        "clip_path": str(path),
        "clip_url": f"http://127.0.0.1:8000/api/jobs/{job_id}/clips/{clip_index}",
        "port": port,
    }


@app.get("/api/edit/status")
def editor_status():
    """Check if OpenCut is running."""
    running = _opencut_proc is not None and _opencut_proc.poll() is None
    return {
        "running": running,
        "port": _opencut_port if running else None,
        "url": f"http://127.0.0.1:{_opencut_port}" if running else None,
    }


class EditRequest(BaseModel):
    trim_start: float | None = Field(default=None, ge=0)
    trim_end: float | None = Field(default=None, ge=0)
    text_overlays: list[dict] = Field(default_factory=list)
    top_text: str | None = None
    volume: float = Field(default=1.0, ge=0, le=2.0)
    muted: bool = False
    speed: float = Field(default=1.0, ge=0.25, le=4.0)


@app.post("/api/jobs/{job_id}/clips/{index}/edit")
def edit_clip(job_id: str, index: int, req: EditRequest):
    """Re-render a clip with editor modifications. Returns the edited clip URL."""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    clip = next((c for c in job["clips"] if c["index"] == index), None)
    if not clip or clip.get("status") != "done":
        raise HTTPException(404, "Clip not ready.")

    src_path = jobs.clip_path(job_id, index)
    if not src_path:
        raise HTTPException(404, "Source clip file not found.")

    job_dir = config.DATA_DIR / job_id
    out_path = job_dir / f"clip_{index}_edited.mp4"

    # Build FFmpeg filter chain
    import platform
    is_windows = platform.system() == "Windows"
    ffmpeg_exe = str(Path(__file__).resolve().parent / "bin" / ("ffmpeg.exe" if is_windows else "ffmpeg"))
    if not Path(ffmpeg_exe).exists():
        ffmpeg_exe = shutil.which("ffmpeg") or "ffmpeg"

    vf_parts = []
    af_parts = []

    # Speed adjustment
    if req.speed != 1.0:
        vf_parts.append(f"setpts={1.0/req.speed}*PTS")
        af_parts.append(f"atempo={min(req.speed, 2.0)}")
        if req.speed > 2.0:
            af_parts.append(f"atempo={min(req.speed/2.0, 2.0)}")

    # Text overlays
    for overlay in req.text_overlays:
        text = overlay.get("text", "").replace("'", "\\'").replace(":", "\\:")
        x = overlay.get("x", 540)
        y = overlay.get("y", 960)
        size = overlay.get("size", 48)
        color = overlay.get("color", "white")
        vf_parts.append(
            f"drawtext=text='{text}':fontsize={size}:fontcolor={color}"
            f":x=(w-text_w)/2+{x-int(config.OUT_WIDTH/2)}:y=(h-text_h)/2+{y-int(config.OUT_HEIGHT/2)}"
        )

    cmd = [ffmpeg_exe, "-y", "-i", str(src_path)]

    if req.muted:
        cmd += ["-an"]
    elif req.volume != 1.0:
        af_parts.append(f"volume={req.volume}")

    if vf_parts:
        cmd += ["-vf", ",".join(vf_parts)]
    if af_parts:
        cmd += ["-af", ",".join(af_parts)]

    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-profile:v", "high", "-level:v", "4.1",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
    ]

    # Trim
    if req.trim_start is not None or req.trim_end is not None:
        if req.trim_start:
            cmd += ["-ss", f"{req.trim_start:.2f}"]
        if req.trim_end:
            cmd += ["-to", f"{req.trim_end:.2f}"]

    cmd.append(str(out_path))

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {proc.stderr[-500:]}")
    except Exception as e:
        raise HTTPException(500, f"Edit render failed: {e}")

    # Validate output
    validation = jobs._validate_output(out_path)
    if not validation.get("valid"):
        out_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Edited output invalid: {validation.get('error', 'unknown')}")

    # Save to user's clips folder
    clips_dir = config.CLIPS_DIR
    clips_dir.mkdir(parents=True, exist_ok=True)
    title = clip.get("title", f"clip_{index}")
    safe = re.sub(r"[^\w\- ]", "", title).strip().replace(" ", "_") or f"clip_{index}"
    dest = _unique_path(clips_dir, f"{safe}_edited.mp4")
    shutil.copy2(str(out_path), str(dest))

    return {
        "saved_to": str(dest),
        "filename": dest.name,
        "folder": str(clips_dir),
        "message": "Edited clip saved.",
    }
