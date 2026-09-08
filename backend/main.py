"""CLPZ API."""
from __future__ import annotations

import logging
import math
import os, re, secrets, shutil, subprocess, threading, time, uuid
from pathlib import Path

log = logging.getLogger("clpz.api")

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator
from starlette.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

import auth as auth_mod, config, credits as credits_mod, jobs
import email_service
import gumroad as gumroad_mod

class _RateLimiter:
    """Sliding-window rate limiter with bounded memory.

    Buckets are pruned whenever ``is_rate_limited`` runs into a stale bucket
    and at least every ``_PRUNE_EVERY`` calls, so an unbounded number of
    unique keys cannot grow the dict forever.
    """
    _PRUNE_EVERY = 256

    def __init__(s,mr=20,ws=60):
        s.mr=mr;s.ws=ws;s.a={};s.l=threading.Lock();s._calls=0
    def is_rate_limited(s,k):
        n=time.monotonic()
        with s.l:
            s._calls += 1
            s.a.setdefault(k,[])
            s.a[k]=[t for t in s.a[k] if n-t<s.ws]
            if len(s.a[k])>=s.mr: return True
            s.a[k].append(n)
            if s._calls % s._PRUNE_EVERY == 0:
                stale=[kk for kk,vv in s.a.items() if not vv or n-vv[-1]>=s.ws]
                for kk in stale: s.a.pop(kk, None)
            return False
    def prune(s):
        n=time.monotonic()
        with s.l:
            stale=[kk for kk,vv in s.a.items() if not vv or n-vv[-1]>=s.ws]
            for kk in stale: s.a.pop(kk, None)

# Higher limits in debug mode for testing
if config.DEBUG:
    auth_rl=_RateLimiter(1000,60); forge_rl=_RateLimiter(1000,60); verify_rl=_RateLimiter(1000,60)
else:
    auth_rl=_RateLimiter(10,60); forge_rl=_RateLimiter(5,60); verify_rl=_RateLimiter(5,300)

def _cip(r):
    """Client IP for rate limiting.

    ``X-Forwarded-For`` is only honored when the request's socket peer is a
    configured trusted proxy.  Otherwise the real peer address is used, so a
    client cannot bypass limits by setting arbitrary forwarding headers.
    """
    peer = r.client.host if r.client else "?"
    if peer in config.TRUSTED_PROXIES:
        f = r.headers.get("x-forwarded-for")
        if f:
            return f.split(",")[0].strip()
    return peer

ALLOWED=[o.strip() for o in os.getenv("CLPZ_ALLOWED_ORIGINS","http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()]

CSP="default-src 'self';script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;font-src 'self' https://fonts.gstatic.com;img-src 'self' data blob;connect-src 'self' https://*.supabase.co wss://*.supabase.co;media-src 'self' blob;frame-ancestors 'none'"

class SecMid(BaseHTTPMiddleware):
    async def dispatch(s,r,cn):
        resp=await cn(r)
        ct=resp.headers.get("content-type","")
        if "text/html" in ct: resp.headers["Content-Security-Policy"]=CSP
        resp.headers["X-Content-Type-Options"]="nosniff"
        resp.headers["X-Frame-Options"]="DENY"
        resp.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
        return resp

def _cookie_secure(request: Request) -> bool:
    """Whether the session cookie should carry the Secure flag.

    Loopback desktop mode serves plain HTTP on 127.0.0.1; forcing Secure
    there breaks every non-browser client (and is pointless — the traffic
    never leaves the machine).  The flag is set based on the actual request
    scheme, so an HTTPS deployment still gets a Secure cookie.  Set
    CLPZ_FORCE_SECURE_COOKIES=1 to force it regardless.
    """
    if config.FORCE_SECURE_COOKIES:
        return True
    return request.url.scheme == "https"


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


_JOB_ID_RE = re.compile(r"^[0-9a-f]{12}$")


def _check_job_access(job_id: str, request: Request) -> dict:
    """Validate job_id shape and enforce ownership when the job belongs to a user.

    Anonymous (desktop/local) jobs have no owner and stay accessible without
    auth, preserving the desktop workflow. Jobs created by a logged-in user
    can only be read/cancelled/retried/downloaded by that user (or an admin).
    Always returns 404 (never 403) so job ids cannot be probed.
    """
    if not _JOB_ID_RE.match(job_id):
        raise HTTPException(404, "Job not found.")
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    owner = job.get("user_id")
    if owner:
        uid = _get_session_user(request)
        if uid != owner:
            is_admin = False
            if uid:
                u = auth_mod.get_user_by_id(uid)
                is_admin = bool(u and ADMIN_EMAIL and u.get("email") == ADMIN_EMAIL)
            if not is_admin:
                raise HTTPException(404, "Job not found.")
    return job


def optional_user(request: Request) -> str | None:
    """Dependency: optional authentication. Returns user_id or None."""
    return _get_session_user(request)


ADMIN_EMAIL = os.getenv("CLPZ_ADMIN_EMAIL", "")


def require_admin(request: Request) -> str:
    """Dependency: require admin authorization. Returns user_id."""
    user_id = _get_session_user(request)
    if not user_id:
        raise HTTPException(401, "Please log in.")
    user = auth_mod.get_user_by_id(user_id)
    if not user or user.get("email") != ADMIN_EMAIL:
        raise HTTPException(403, "Admin access required.")
    return user_id


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

)

# CORS: configurable allowlist
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.add_middleware(SecMid)


def _json_safe(value):
    """Recursively replace non-finite floats (NaN/Infinity) with strings so a
    pydantic validation error mentioning a raw input like ``inf`` can still be
    serialized. Without this, FastAPI's 422 renderer itself raises
    ``ValueError: Out of range float values are not JSON compliant`` and the
    request ends up as a 500 instead of a proper validation response."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    # jsonable_encoder first: it stringifies pydantic's ctx exceptions (e.g.
    # the ValueError from a model_validator) and drops unserializable objects.
    # _json_safe second: it replaces non-finite floats so the response can
    # always be serialized even when the rejected input was NaN/Infinity.
    from fastapi.encoders import jsonable_encoder
    return JSONResponse(
        status_code=422,
        content={"detail": _json_safe(jsonable_encoder(exc.errors()))},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log the traceback server-side, return a generic 500."""
    import traceback
    print(f"[CLPZ] Unhandled error on {request.method} {request.url.path}:")
    traceback.print_exc()
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

_check_binaries()

# One-time migration from JSON files to SQLite
import database as db
print("CLPZ: Initializing database...")
db.migrate_from_json()
print("CLPZ: Database ready.")

jobs.load_saved_jobs()
jobs.start_maintenance()


def _limiter_prune_loop():
    """Background thread: keep rate-limiter memory bounded on long uptime."""
    while True:
        time.sleep(max(60, config.MAINTENANCE_INTERVAL_SECONDS))
        for lim in (auth_rl, forge_rl, verify_rl):
            try:
                lim.prune()
            except Exception:
                pass

if os.environ.get("CLPZ_DISABLE_MAINTENANCE") != "1":
    threading.Thread(target=_limiter_prune_loop, daemon=True, name="clpz-limiter-prune").start()

# The original dashboard remains in frontend/index.html as a fallback.  The
# production shell below is the Manus-inspired, API-backed interface.
# When frozen (PyInstaller), paths resolve to <install>/frontend and
# <install>/frontend-app-dist, prepared by the packaging step.
FRONTEND_DIR = Path(os.environ.get("CLIPFORGE_FRONTEND_DIR") or (Path(__file__).resolve().parent.parent / "frontend"))
LANDING = FRONTEND_DIR / "index.html"
AUTH_PAGE = FRONTEND_DIR / "auth.html"
DASHBOARD = FRONTEND_DIR / "clpz.html"
ADMIN_PAGE = FRONTEND_DIR / "admin.html"

# React app (built with Vite + Tailwind)
REACT_APP_DIR = Path(os.environ.get("CLIPFORGE_REACT_DIR") or (Path(__file__).resolve().parent.parent / "frontend-app" / "dist"))

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
    current_password: str
    new_password: str


class VerifyRequest(BaseModel):
    email: str
    code: str


class RequestVerificationRequest(BaseModel):
    email: str


@app.post("/api/auth/signup")
def signup(request: Request, req: SignupRequest):
    if auth_rl.is_rate_limited("signup:" + _cip(request)):
        raise HTTPException(429, "Too many signup attempts. Please try again later.")
    try:
        user = auth_mod.create_user(req.email, req.password, req.display_name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Grant signup bonus exactly once (server-authoritative)
    credits_mod.ensure_signup_bonus(user["id"])
    token = auth_mod.create_session(user["id"])
    user["email_verified"] = False
    resp = JSONResponse({"user": user, "credits": credits_mod.get_balance(user["id"]), "email_verified": False})
    resp.set_cookie("clpz_session", token, httponly=True, samesite="strict", secure=_cookie_secure(request), max_age=86400 * 7)
    return resp


@app.post("/api/auth/login")
def login(request: Request, req: LoginRequest):
    if auth_rl.is_rate_limited("login:" + _cip(request)):
        raise HTTPException(429, "Too many login attempts. Please try again later.")
    user = auth_mod.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    # Check email verification status
    email_verified = auth_mod.is_email_verified(user["id"])
    # Ensure signup bonus was granted (idempotent)
    credits_mod.ensure_signup_bonus(user["id"])
    balance = credits_mod.get_balance(user["id"])
    token = auth_mod.create_session(user["id"])
    user["email_verified"] = email_verified
    resp = JSONResponse({"user": user, "credits": balance, "email_verified": email_verified})
    resp.set_cookie("clpz_session", token, httponly=True, samesite="strict", secure=_cookie_secure(request), max_age=86400 * 7)
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
    user["email_verified"] = auth_mod.is_email_verified(user_id)
    return {"user": user}


@app.post("/api/auth/reset")
def reset_password(req: ResetRequest):
    user = auth_mod.authenticate_user(req.email, req.current_password)
    if not user:
        raise HTTPException(401, "Current password is incorrect.")
    try:
        auth_mod.set_password(user["id"], req.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    auth_mod.destroy_all_user_sessions(user["id"])
    return {"message": "Password reset successfully. Please log in again."}


# ── Email verification endpoints --------------------------------

@app.post("/api/auth/request-verification")
def request_verification(request: Request, req: RequestVerificationRequest):
    """Send a verification code to the user's email."""
    if verify_rl.is_rate_limited("verif:" + _cip(request)):
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = req.email.strip().lower()
    user = auth_mod.get_user_by_email(email)
    if not user:
        raise HTTPException(404, "No account found with that email.")
    if auth_mod.is_email_verified(user["id"]):
        return {"message": "Email already verified."}
    code = auth_mod.generate_verification_code(user["id"], "signup")
    email_service.send_verification_email(email, code, "signup")
    resp = {"message": "Verification code sent to your email."}
    if config.DEBUG:
        resp["code"] = code  # Dev-only: allows testing without email
    return resp


@app.post("/api/auth/verify-email")
def verify_email(request: Request, req: VerifyRequest):
    """Verify email with 6-digit code."""
    if verify_rl.is_rate_limited("verify:" + _cip(request)):
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = req.email.strip().lower()
    user = auth_mod.get_user_by_email(email)
    if not user:
        raise HTTPException(404, "No account found with that email.")
    if auth_mod.is_email_verified(user["id"]):
        return {"message": "Email already verified."}
    if not auth_mod.verify_code(user["id"], req.code, "signup"):
        raise HTTPException(400, "Invalid or expired verification code.")
    auth_mod.mark_email_verified(user["id"])
    return {"message": "Email verified successfully."}



class ForgotPasswordRequest(BaseModel):
    email: str


class ResetWithCodeRequest(BaseModel):
    email: str
    code: str
    new_password: str


@app.post("/api/auth/forgot-password")
def forgot_password(request: Request, req: ForgotPasswordRequest):
    """Send a password reset code to the user's email."""
    if verify_rl.is_rate_limited("forgot:" + _cip(request)):
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = req.email.strip().lower()
    user = auth_mod.get_user_by_email(email)
    if not user:
        # Don't reveal whether account exists
        return {"message": "If an account exists, a reset code has been sent."}
    code = auth_mod.generate_verification_code(user["id"], "reset")
    email_service.send_password_reset_email(email, code)
    resp = {"message": "If an account exists, a reset code has been sent."}
    if config.DEBUG:
        resp["code"] = code  # Dev-only
    return resp


@app.post("/api/auth/reset-with-code")
def reset_with_code(request: Request, req: ResetWithCodeRequest):
    """Reset password using a 6-digit code sent via email."""
    if verify_rl.is_rate_limited("reset:" + _cip(request)):
        raise HTTPException(429, "Too many requests. Please try again later.")
    email = req.email.strip().lower()
    user = auth_mod.get_user_by_email(email)
    if not user:
        raise HTTPException(400, "Invalid or expired reset code.")
    if not auth_mod.verify_code(user["id"], req.code, "reset"):
        raise HTTPException(400, "Invalid or expired reset code.")
    try:
        auth_mod.set_password(user["id"], req.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    auth_mod.destroy_all_user_sessions(user["id"])
    return {"message": "Password reset successfully. Please log in with your new password."}

# ── Credit endpoints ─────────────────────────────────────────────

@app.get("/api/credits/balance")
def credit_balance(user_id: str = Depends(get_current_user)):
    balance = credits_mod.get_balance(user_id)
    return {"balance": balance, "cost_per_forge": credits_mod.COST_PER_FORGE}


@app.get("/api/credits/transactions")
def credit_transactions(user_id: str = Depends(get_current_user)):
    txns = credits_mod.get_transactions(user_id)
    return {"transactions": txns}


# ── Gumroad webhook ──────────────────────────────────────────────

@app.post("/api/payments/gumroad/webhook")
async def gumroad_webhook(request: Request):
    """Receive Gumroad ping webhooks.

    Security: HMAC-SHA256 signature verification over the raw body.
    Idempotency: duplicate sale ids are recorded once — credits are never
    granted twice for the same Gumroad transaction.
    """
    raw = await request.body()
    signature = request.headers.get("x-gumroad-signature", "")
    if not gumroad_mod.verify_signature(raw, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")
    data = gumroad_mod._parse_payload(raw)
    if data is None:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    result = gumroad_mod.process_webhook(data)
    return {"ok": True, **result}


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
    idempotency_key: str = Field(default="")


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


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_PAGE.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index():
    return LANDING.read_text(encoding="utf-8")


@app.get("/auth.html", response_class=HTMLResponse)
def auth_page():
    return AUTH_PAGE.read_text(encoding="utf-8")


@app.get("/app", response_class=HTMLResponse)
def dashboard():
    return DASHBOARD.read_text(encoding="utf-8")


# ── React App (Vite + Tailwind) ───────────────────────────────
# Serve the built React app when available.  Falls back to vanilla HTML.
if REACT_APP_DIR.exists() and (REACT_APP_DIR / "index.html").exists():
    # Mount static assets (JS, CSS, images) from the React build
    _react_assets = REACT_APP_DIR / "assets"
    if _react_assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_react_assets)), name="react-assets")

    def _react_index():
        # no-cache: index.html must revalidate (hashed assets can cache forever)
        return FileResponse(
            str(REACT_APP_DIR / "index.html"),
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    # React app routes — catch-all for client-side routing
    @app.get("/new", response_class=HTMLResponse)
    def react_root():
        return _react_index()

    @app.get("/new/{path:path}", response_class=HTMLResponse)
    def react_catch_all(path: str = ""):
        return _react_index()

    @app.get("/favicon.png")
    def react_favicon():
        f = REACT_APP_DIR / "favicon.png"
        if f.exists():
            return FileResponse(str(f), media_type="image/png")
        raise HTTPException(404, "Not found")


@app.post("/api/jobs")
def create_job(req: JobRequest, request: Request):
    if forge_rl.is_rate_limited("forge:" + _cip(request)):
        raise HTTPException(429, "Too many requests. Please wait before trying again.")
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

    # Stable idempotency key: the frontend sends one per submission attempt.
    # When absent, a random key is generated (each such request is a NEW
    # logical submission).  Keys are NEVER derived from the current second,
    # so rapid retries cannot collide into duplicate jobs/charges.
    idempotency_key = req.idempotency_key or uuid.uuid4().hex

    job_id, is_new, remaining = jobs.create_job_idempotent(
        url, req.max_clips, req.top_text,
        user_id=user_id, idempotency_key=idempotency_key,
    )
    if job_id is None:
        raise HTTPException(
            402,
            f"Not enough credits. You need {credits_mod.COST_PER_FORGE} credit(s) "
            f"but have {remaining}.",
        )
    if not is_new:
        log.info("deduplicated forge submission (key %s -> job %s)", idempotency_key[:12], job_id)
    return {"job_id": job_id, "credits_remaining": remaining}


def _job_visible_to(job: dict, user_id: str | None, is_admin: bool) -> bool:
    """Whether a caller may see a job in the shared list.

    Anonymous (desktop/local) jobs have no owner and remain visible to
    everyone — that keeps the private .bat workflow working without login.
    Account-owned jobs are visible only to that account (or an admin) so one
    user can never enumerate another user's projects or clip metadata.
    """
    owner = job.get("user_id")
    if not owner:
        return True
    if is_admin:
        return True
    return bool(user_id) and owner == user_id


@app.get("/api/jobs")
def list_jobs(request: Request):
    """List persisted projects for the Projects screen (scoped to caller)."""
    uid = _get_session_user(request)
    is_admin = False
    if uid:
        u = auth_mod.get_user_by_id(uid)
        is_admin = bool(u and ADMIN_EMAIL and u.get("email") == ADMIN_EMAIL)
    visible = [j for j in jobs.get_all_jobs() if _job_visible_to(j, uid, is_admin)]
    visible.sort(key=lambda job: job.get("created_at", 0), reverse=True)
    return [_job_payload(job) for job in visible]


@app.post("/api/jobs/upload")
async def upload_job(
    request: Request,
    file: UploadFile = File(...),
    max_clips: int = Form(config.MAX_CLIPS_DEFAULT),
    top_text: str = Form(""),
    idempotency_key: str = Form(""),
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

    # One logical upload (by idempotency key) = one job = one charge.
    idempotency_key = idempotency_key or uuid.uuid4().hex
    job_id, is_new, remaining = jobs.create_upload_job_idempotent(
        filename=file.filename,
        max_clips=max_clips,
        top_text=top_text,
        user_id=user_id,
        idempotency_key=idempotency_key,
    )
    if job_id is None:
        raise HTTPException(
            402,
            f"Not enough credits. You need {credits_mod.COST_PER_FORGE} credit(s) "
            f"but have {remaining}.",
        )
    if not is_new:
        # Duplicate submit of the same upload: return the original job untouched.
        return {"job_id": job_id, "credits_remaining": remaining}

    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    video_path = job_dir / f"source{ext}"

    MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
    try:
        with video_path.open("wb") as out:
            written = 0
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    video_path.unlink(missing_ok=True)
                    jobs.cancel_job(job_id)
                    if user_id and remaining is not None:
                        credits_mod.refund(
                            user_id, credits_mod.COST_PER_FORGE,
                            reason="Upload too large — refund"
                        )
                    raise HTTPException(
                        413,
                        "Video is too large. Maximum upload size is 2 GB.",
                    )

                out.write(chunk)

    except HTTPException:
        raise
    except Exception:
        # Post-charge failure: refund idempotently, cancel the job, remove the
        # key mapping and any partial file.  Never leave a charged, stuck job.
        video_path.unlink(missing_ok=True)
        jobs.cancel_job(job_id)
        db.delete_idempotency_job_by_key(idempotency_key)
        if user_id and remaining is not None:
            credits_mod.refund(
                user_id, credits_mod.COST_PER_FORGE,
                related_id=job_id,
                reason="Upload failed after charge — refund",
            )
        raise HTTPException(
            500,
            "Failed to save uploaded video.",
        )

    # Quick ffprobe validation — reject obviously corrupted files early
    try:
        import shutil as _shutil
        ffprobe_bin = jobs._find_bin("ffprobe")
        probe_result = subprocess.run(
            [
                ffprobe_bin, "-v", "error",
                "-show_entries", "stream=codec_type",
                "-show_entries", "format=duration",
                "-of", "json", str(video_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if probe_result.returncode != 0:
            video_path.unlink(missing_ok=True)
            jobs.cancel_job(job_id)
            if user_id and remaining is not None:
                credits_mod.refund(
                    user_id, credits_mod.COST_PER_FORGE,
                    reason="Upload validation failed — refund"
                )
            raise HTTPException(
                400,
                "The uploaded file is not a valid video. "
                "Please upload a valid MP4, MOV, or MKV file."
            )
    except HTTPException:
        raise
    except Exception:
        pass  # If ffprobe is missing or errors, let the pipeline handle it

    jobs.start_uploaded_job(
        job_id,
        str(video_path),
        file.filename,
    )

    return {"job_id": job_id, "credits_remaining": remaining}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, request: Request):
    job = _check_job_access(job_id, request)
    return _job_payload(job)


@app.post("/api/jobs/clear")
def clear_old_jobs(request: Request, _admin_id: str = Depends(require_admin)):
    """Clear completed/errored jobs older than 24 hours (admin only)."""
    jobs._cleanup_old_jobs(max_age_hours=24, keep_minimum=0)
    remaining = len(jobs.get_all_jobs())
    log.info("admin cleared old jobs; %d remaining", remaining)
    return {"message": f"Old jobs cleared. {remaining} job(s) remaining.", "remaining": remaining}


@app.post("/api/jobs/reset")
def reset_jobs(request: Request):
    """Reset all job state. Debug builds only (used by the test suite)."""
    if not config.DEBUG:
        raise HTTPException(404, "Not found.")
    jobs.reset_for_testing()
    return {"message": "Jobs reset."}


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str, request: Request):
    """Retry a failed/cancelled job from the last completed stage."""
    job = _check_job_access(job_id, request)
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
def cancel_job(job_id: str, request: Request):
    """Cancel a running or queued job."""
    _check_job_access(job_id, request)
    ok = jobs.cancel_job(job_id)
    if not ok:
        raise HTTPException(400, "Job cannot be cancelled.")
    return {"message": "Job cancelled.", "job_id": job_id}



# ── Admin endpoints ─────────────────────────────────────────────

@app.get("/api/admin/users")
def admin_list_users(request: Request, admin_id: str = Depends(require_admin)):
    """List all users (admin only)."""
    users = db.get_all_users()
    for u in users:
        u["credits"] = credits_mod.get_balance(u["id"])
    return {"users": users, "total": db.count_users()}


@app.get("/api/admin/stats")
def admin_stats(request: Request, admin_id: str = Depends(require_admin)):
    """System statistics (admin only)."""
    import platform
    import psutil
    stats = db.get_stats()
    stats["platform"] = platform.system()
    stats["python"] = platform.python_version()
    try:
        mem = psutil.virtual_memory()
        stats["ram_total_gb"] = round(mem.total / 1024**3, 1)
        stats["ram_available_gb"] = round(mem.available / 1024**3, 1)
    except Exception:
        pass
    return stats


@app.post("/api/admin/credits/add")
def admin_add_credits(
    request: Request,
    user_id: str,
    amount: int,
    reason: str = "",
    _admin_id: str = Depends(require_admin),
):
    """Add credits to a user (admin only)."""
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive.")
    if not auth_mod.get_user_by_id(user_id):
        raise HTTPException(404, "User not found.")
    new_bal = credits_mod.add_credits(user_id, amount, "admin_grant", reason or "Admin credit grant")
    return {"user_id": user_id, "new_balance": new_bal}


@app.post("/api/admin/credits/remove")
def admin_remove_credits(
    request: Request,
    user_id: str,
    amount: int,
    reason: str = "",
    _admin_id: str = Depends(require_admin),
):
    """Remove credits from a user (admin only)."""
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive.")
    if not auth_mod.get_user_by_id(user_id):
        raise HTTPException(404, "User not found.")
    # Use check_and_charge to safely deduct
    ok, remaining = credits_mod.check_and_charge(user_id, amount)
    if not ok:
        raise HTTPException(400, f"Cannot remove {amount} credits. User has {remaining}.")
    db.log_transaction(user_id, -amount, "admin_removal", reason or "Admin credit removal")
    return {"user_id": user_id, "new_balance": remaining}


@app.get("/api/admin/transactions/{user_id}")
def admin_user_transactions(
    request: Request,
    user_id: str,
    limit: int = 50,
    _admin_id: str = Depends(require_admin),
):
    """View transactions for a user (admin only)."""
    txns = credits_mod.get_transactions(user_id, limit=limit)
    return {"transactions": txns}




@app.get("/api/admin/users/search")
def admin_search_users(
    request: Request,
    q: str = "",
    _admin_id: str = Depends(require_admin),
):
    """Search users by email (admin only)."""
    if not q:
        return {"users": []}
    conn = db._get_conn()
    rows = conn.execute(
        "SELECT id, email, display_name, email_verified, created_at, plan "
        "FROM users WHERE email LIKE ? ORDER BY created_at DESC LIMIT 50",
        (f"%{q.lower()}%",),
    ).fetchall()
    users = [dict(r) for r in rows]
    for u in users:
        u["credits"] = credits_mod.get_balance(u["id"])
    return {"users": users}


@app.get("/api/admin/jobs")
def admin_list_jobs(
    request: Request,
    limit: int = 50,
    _admin_id: str = Depends(require_admin),
):
    """List all jobs (admin only)."""
    all_jobs = jobs.get_all_jobs()
    all_jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    return {"jobs": all_jobs[:limit], "total": len(all_jobs)}



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

    # Editor
    info["editor"] = "built-in"

    return info


@app.get("/api/jobs/{job_id}/clips/{index}")
def download_clip(job_id: str, index: int, request: Request):
    _check_job_access(job_id, request)
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
def stream_clip(job_id: str, index: int, request: Request):
    """Play the real rendered MP4 inline without triggering a download."""
    _check_job_access(job_id, request)
    path = jobs.clip_path(job_id, index)
    if not path:
        raise HTTPException(404, "Clip not ready.")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/jobs/{job_id}/clips/{index}/thumbnail")
def clip_thumbnail(job_id: str, index: int, request: Request):
    """Serve the thumbnail extracted from the verified rendered clip."""
    _check_job_access(job_id, request)
    path = jobs.clip_thumbnail_path(job_id, index)
    if not path:
        raise HTTPException(404, "Clip thumbnail not ready.")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/clips/{index}/ass")
def clip_ass(job_id: str, index: int, request: Request):
    """Return the ASS subtitle file for a clip (used by the editor)."""
    _check_job_access(job_id, request)
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
def save_clip(job_id: str, index: int, request: Request):
    """Save a rendered clip to the user's Videos/CLPZ Clips folder."""
    _check_job_access(job_id, request)
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



class TextOverlay(BaseModel):
    """A single text overlay, validated before it reaches the FFmpeg filter graph."""
    text: str = Field(default="", max_length=200)
    x: float = Field(default=540, ge=-10000, le=10000, allow_inf_nan=False)
    y: float = Field(default=960, ge=-10000, le=10000, allow_inf_nan=False)
    size: float = Field(default=48, ge=4, le=400, allow_inf_nan=False)
    color: str = Field(default="white", max_length=32, pattern=r"^[A-Za-z0-9#@]*$")


class EditRequest(BaseModel):
    trim_start: float | None = Field(default=None, ge=0, le=86400, allow_inf_nan=False)
    trim_end: float | None = Field(default=None, ge=0, le=86400, allow_inf_nan=False)
    text_overlays: list[TextOverlay] = Field(default_factory=list, max_length=10)
    top_text: str | None = Field(default=None, max_length=200)
    volume: float = Field(default=1.0, ge=0, le=2.0, allow_inf_nan=False)
    muted: bool = False
    speed: float = Field(default=1.0, ge=0.25, le=4.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _trim_range_is_valid(self):
        ts, te = self.trim_start, self.trim_end
        if ts is not None and te is not None and ts > te:
            raise ValueError("trim_start must be less than or equal to trim_end")
        return self


@app.post("/api/jobs/{job_id}/clips/{index}/edit")
def edit_clip(job_id: str, index: int, req: EditRequest, request: Request):
    """Re-render a clip with editor modifications. Returns the edited clip URL."""
    job = _check_job_access(job_id, request)

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

    # Text overlays (already validated by the typed model; escape for the
    # drawtext filter and disable %-expansion so client text cannot break out
    # of the filter graph).
    for overlay in req.text_overlays:
        text = (
            overlay.text
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace(":", "\\:")
            .replace(",", "\\,")
        )
        x = int(round(overlay.x))
        y = int(round(overlay.y))
        size = int(round(overlay.size))
        color = overlay.color or "white"
        vf_parts.append(
            f"drawtext=text='{text}':fontsize={size}:fontcolor={color}:expansion=none"
            f":x=(w-text_w)/2+{x-int(config.OUT_WIDTH/2)}:y=(h-text_h)/2+{y-int(config.OUT_HEIGHT/2)}"
        )

    # Trim: apply BEFORE -i so it operates on the source timeline,
    # not the output timeline (which would be affected by speed filters).
    cmd = [ffmpeg_exe, "-y"]
    if req.trim_start:
        cmd += ["-ss", f"{req.trim_start:.2f}"]
    if req.trim_end:
        cmd += ["-to", f"{req.trim_end:.2f}"]
    cmd += ["-i", str(src_path)]

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
