"""Central configuration. Everything overridable via environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# Secure by default: debug mode (relaxed rate limits, dev-only code leak in
# verification responses, /api/jobs/reset endpoint) must be opted INTO via
# CLPZ_DEBUG=1.  The packaged desktop launcher and the test suite set it
# explicitly; a bare server deployment now runs with production settings.
DEBUG = os.getenv("CLPZ_DEBUG", "0") == "1"
DATA_DIR = Path(os.getenv("CLIPFORGE_DATA", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ---- YouTube download ----
# Path to a Netscape-format cookies.txt exported from a logged-in YouTube
# session. Needed on EC2/datacenter IPs where YouTube bot-checks anonymous
# downloads. If the file exists, it is used automatically.
COOKIES_FILE = os.getenv("YT_COOKIES_FILE", str(BASE_DIR / "cookies.txt"))
# Browser name for cookie extraction (e.g. "chrome", "brave", "edge", "firefox").
# When set, yt-dlp extracts cookies from the browser session automatically.
# Only used when the cookies.txt file does not exist.
YT_BROWSER_COOKIES = os.getenv("YT_BROWSER_COOKIES", "")

# ---- Whisper ----
# "small" is a good speed/quality tradeoff on CPU. Use "medium" or "large-v3"
# on a GPU instance (g4dn.xlarge) for best captions.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")  # auto / cpu / cuda
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "auto")  # int8 on cpu, float16 on gpu
# "transcribe": captions in the spoken language. "translate": captions in
# English regardless of spoken language (Whisper's built-in X->English mode).
WHISPER_TASK = os.getenv("WHISPER_TASK", "transcribe")

# ---- Layout ----
# auto: per-clip decision — big face => face-tracked crop; small corner face
# (facecam over screen share) => split layout (face top, screen bottom).
# Force with "face" or "split".
CLIP_LAYOUT = os.getenv("CLIP_LAYOUT", "auto")
# Face is treated as a facecam (=> split) when its height is under this
# fraction of the frame height.
FACECAM_MAX_FACE_FRAC = float(os.getenv("FACECAM_MAX_FACE_FRAC", "0.22"))
SPLIT_FACE_HEIGHT = 640          # top panel height in the 1080x1920 output
CAPTION_MARGIN_V_SPLIT = int(os.getenv("CAPTION_MARGIN_V_SPLIT", "150"))

# ---- Audio ----
# Normalize loudness to the -14 LUFS short-form platform target.
LOUDNORM = os.getenv("LOUDNORM", "1") == "1"

# ---- Clip settings ----
MAX_CLIPS_DEFAULT = int(os.getenv("MAX_CLIPS_DEFAULT", "5"))
CLIP_MIN_SECONDS = float(os.getenv("CLIP_MIN_SECONDS", "15"))
CLIP_MAX_SECONDS = float(os.getenv("CLIP_MAX_SECONDS", "60"))

# ---- Performance ----
# Clips rendered in parallel. 1 for low-RAM machines (8GB), 2 for 16GB+.
RENDER_WORKERS = int(os.getenv("RENDER_WORKERS", "1"))
# Absolute deadline for a single job (download + transcribe + render).
# Whisper runs in a supervised subprocess (R02), so a hung transcription is
# terminated at TRANSCRIBE_DEADLINE_SECONDS; the job deadline remains as a
# backstop for stages that are not individually supervised.
JOB_TIMEOUT_SECONDS = float(os.getenv("JOB_TIMEOUT_SECONDS", "3600"))
# R02: run Whisper in a supervised child process so a hung model is killed at
# a hard deadline instead of holding a worker slot forever. Set to "0" to
# fall back to the legacy in-process call (used by the hermetic test suite,
# which stubs transcription in-process).
TRANSCRIBE_SUPERVISED = os.getenv("TRANSCRIBE_SUPERVISED", "1").strip().lower() not in ("0", "false", "no", "off")
# Hard deadline for one supervised transcription stage. Applies whether the
# child produced partial output or hung silently: at expiry the child is
# force-killed and the job fails with TRANSCRIBE_TIMEOUT.
TRANSCRIBE_DEADLINE_SECONDS = float(os.getenv("TRANSCRIBE_DEADLINE_SECONDS", "3600"))
# How often background maintenance (session/idempotency/cancel-event pruning)
# runs.  A restart never removes completed projects automatically.
MAINTENANCE_INTERVAL_SECONDS = int(os.getenv("MAINTENANCE_INTERVAL_SECONDS", "3600"))
# Automatic retention cleanup is opt-in: 0 disables it (a restart never
# silently removes completed projects).  Set a positive value (hours) to
# enable automatic cleanup of old done/error jobs.
AUTO_CLEANUP_HOURS = int(os.getenv("CLIPFORGE_AUTO_CLEANUP_HOURS", "0"))
# Comma-separated list of trusted reverse-proxy IPs.  ``X-Forwarded-For`` is
# only honored when the socket peer is in this list; otherwise the actual
# peer address is used for rate limiting, so clients cannot spoof their
# identity by setting arbitrary headers.
TRUSTED_PROXIES = set(
    p.strip() for p in os.getenv("CLPZ_TRUSTED_PROXIES", "").split(",") if p.strip()
)
# Force the session cookie's Secure flag even over plain HTTP.  Default: the
# cookie is Secure only when the request arrived over HTTPS (loopback HTTP
# works for every client without weakening an externally-exposed deployment).
FORCE_SECURE_COOKIES = os.getenv("CLPZ_FORCE_SECURE_COOKIES", "0") == "1"

# ---- Output video ----
OUT_WIDTH = 1080
OUT_HEIGHT = 1920
# CRF 18 = visually lossless, good quality without huge files
VIDEO_CRF = os.getenv("VIDEO_CRF", "18")
# medium = good balance of speed and quality for 8GB RAM machines
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
# Two-pass-like quality with high profile for better compression
VIDEO_PROFILE = os.getenv("VIDEO_PROFILE", "high")
VIDEO_LEVEL = os.getenv("VIDEO_LEVEL", "4.1")

# ---- Credits ----
# Cost per clip-generation job (configurable, central)
COST_PER_FORGE = int(os.getenv("COST_PER_FORGE", "1"))
# Free credits granted on signup (once per account)
SIGNUP_BONUS = int(os.getenv("SIGNUP_BONUS", "10"))

# ---- Black bars + top text ----
# Height of black bars on top/bottom (pixels). 0 = disabled.
BLACK_BAR_HEIGHT = int(os.getenv("BLACK_BAR_HEIGHT", "120"))
# Top text that stays for the whole clip (e.g., title). Empty = disabled.
TOP_TEXT = os.getenv("TOP_TEXT", "")
# Top text font size
TOP_TEXT_FONT_SIZE = int(os.getenv("TOP_TEXT_FONT_SIZE", "36"))
# Top text color (ASS BGR format)
TOP_TEXT_COLOR = os.getenv("TOP_TEXT_COLOR", "&H00FFFFFF")

# ---- Caption styling (ASS) ----
# Inter Bold — bundled locally in backend/fonts/
CAPTION_FONT = os.getenv("CAPTION_FONT", "Inter")
CAPTION_FONT_SIZE = int(os.getenv("CAPTION_FONT_SIZE", "72"))
# No highlight animation — static white text only
CAPTION_HIGHLIGHT = "&H00FFFFFF"  # white (ASS is BGR)
# Word grouping: 1-2 words normally, up to 3 for fast speech
CAPTION_MAX_WORDS = int(os.getenv("CAPTION_MAX_WORDS", "3"))
# Max characters per caption page (incl. spaces)
CAPTION_MAX_CHARS = int(os.getenv("CAPTION_MAX_CHARS", "14"))
# No background box — BorderStyle 1 in ASS (outline + shadow only)
CAPTION_BOX = False
CAPTION_BOX_COLOR = "&H00000000"
# Vertical position: pixels from the bottom edge (PlayRes 1080x1920).
# 700 =~ 36% up — lower-middle, well above Shorts/Reels UI overlays,
# comfortable space from both top and bottom edges.
CAPTION_MARGIN_V = int(os.getenv("CAPTION_MARGIN_V", "870"))
# Font directory for ASS subtitles — bundled Inter Bold
CAPTION_FONTS_DIR = str(BASE_DIR / "fonts")

# ---- User clips output ----
# Where finished clips are saved when the user clicks Download.
# Defaults to Videos\CLPZ Clips in the current user's home directory.
CLIPS_DIR = Path(os.getenv("CLIPFORGE_CLIPS_DIR", str(Path.home() / "Videos" / "CLPZ Clips")))
