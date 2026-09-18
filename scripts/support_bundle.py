"""CLPZ support bundle — redacted diagnostic collection (task 22).

Collects what an operator needs to diagnose a failed install/processing run
WITHOUT collecting credentials, raw media, transcripts, or user database
content:

- versions and machine profile (from /api/diagnostics when a server is
  running, or a local import fallback)
- last N job records: ids, stages, error CODES, timings, completed stages.
  URL fields are reduced to host; media paths reduced to filename+size.
- log metadata only (whether the known files exist and their sizes)
- an approved environment-setting presence summary (never names supplied by
  the environment and never values)

Usage:
    python scripts/support_bundle.py [--jobs 20] [--out DIR]

Exit 0 on success. The output is a single JSON file safe to attach to a
support request (no credentials, media, transcripts, logs, or user content).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Defense-in-depth for text that an operator may inspect locally.  The bundle
# deliberately does NOT include arbitrary text: regexes cannot prove that an
# unknown log/error string contains no customer content.
SECRET_PATTERNS = [
    re.compile(r"(?i)(\bauthorization\s*:\s*bearer\s+)[A-Za-z0-9._-]+"),
    re.compile(
        r'''(?ix)((?:["']?(?:authorization|cookie|set-cookie|x-api-key|api[_-]?key|token|password|secret)["']?)
        \s*[:=]\s*)(?:"[^"]*"|'[^']*'|\S+)'''
    ),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{5,}"),  # JWTs
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s@]+@"),  # URL credentials
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)sbps?_[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(?:dodo(?:payments)?|gumroad|stripe)_[a-z0-9_]{12,}\b"),
]

APPROVED_ENV_NAMES = (
    "CLPZ_DEBUG",
    "CLPZ_REQUIRE_CAPABILITY",
    "MAX_CONCURRENT_JOBS",
    "MAX_QUEUE_DEPTH",
    "TRANSCRIBE_SUPERVISED",
    "TRANSCRIBE_DEADLINE_SECONDS",
)

APPROVED_DIAGNOSTIC_FIELDS = {
    "platform", "python", "ffmpeg", "ffprobe", "yt-dlp", "whisper",
    "ram_total_gb", "ram_available_gb", "ram_percent", "disk_free_gb",
    "cpu_count", "editor",
}
APPROVED_JOB_STAGES = {
    "queued", "downloading", "transcribing", "analyzing", "selecting",
    "rendering", "done", "error", "cancelled",
}
APPROVED_JOB_FIELDS = {
    "id", "stage", "error_code", "timings", "completed_stages",
    "created_at", "started_at", "completed_at", "progress", "input_type",
    "max_clips",
}
APPROVED_TOOL_STATUSES = {"found", "missing", "not-on-PATH", "not installed"}
APPROVED_TIMING_NAMES = {"download", "transcribe", "analyze", "select", "render", "total"}


def redact_text(text: str) -> str:
    out = text
    for rx in SECRET_PATTERNS:
        if rx.pattern.startswith("(?ix)(") or "authorization" in rx.pattern:
            out = rx.sub(lambda match: match.group(1) + "[REDACTED]", out)
        elif "://" in rx.pattern:
            out = rx.sub(lambda match: match.group(1) + "[REDACTED]@", out)
        else:
            out = rx.sub("[REDACTED]", out)
    return out


def env_summary() -> dict:
    return {name: "[SET]" for name in APPROVED_ENV_NAMES if name in os.environ}


def _safe_number(value, *, minimum: float = 0, maximum: float = 1e12):
    """Return finite numeric diagnostics only; reject booleans and text."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < minimum or value > maximum:
        return None
    return value


def _safe_label(value, allowed: set[str] | None = None, limit: int = 80):
    if not isinstance(value, str) or len(value) > limit or "\n" in value or "\r" in value:
        return None
    if allowed is not None and value not in allowed:
        return None
    return value


def sanitize_diagnostics(raw: object) -> dict:
    """Keep only the fixed, typed diagnostics contract from a local API."""
    if not isinstance(raw, dict):
        return {}
    clean = {}
    for key in APPROVED_DIAGNOSTIC_FIELDS:
        value = raw.get(key)
        if key in {"ram_total_gb", "ram_available_gb", "ram_percent", "disk_free_gb", "cpu_count"}:
            safe = _safe_number(value, maximum=1e9)
        elif key in {"ffmpeg", "ffprobe", "yt-dlp"}:
            safe = _safe_label(value, APPROVED_TOOL_STATUSES)
        elif key == "whisper":
            safe = _safe_label(value, {"missing", "not installed"})
            if safe is None and isinstance(value, str) and re.fullmatch(r"v[0-9][0-9A-Za-z._-]{0,30}", value):
                safe = value
        elif key == "platform":
            safe = _safe_label(value)
            if safe and not re.fullmatch(r"[A-Za-z0-9 ._-]+", safe):
                safe = None
        elif key == "python":
            safe = _safe_label(value)
            if safe and not re.fullmatch(r"[0-9][0-9A-Za-z._-]{0,31}", safe):
                safe = None
        elif key == "editor":
            safe = _safe_label(value, {"built-in"})
        else:
            safe = None
        if safe is not None:
            clean[key] = safe
    return clean


def machine_profile() -> dict:
    info = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "machine": platform.machine(),
    }
    for exe in ("ffmpeg", "ffprobe", "yt-dlp"):
        import shutil
        info[exe] = "found" if shutil.which(exe) else "not-on-PATH"
    try:
        import faster_whisper
        info["faster_whisper"] = getattr(faster_whisper, "__version__", "installed")
    except Exception:
        info["faster_whisper"] = "not installed"
    return info


def collect_from_api(base: str, jobs_n: int) -> dict | None:
    """Pull diagnostics + job summaries from a running local server."""
    try:
        import requests
    except Exception:
        return None
    diag = None
    try:
        r = requests.get(f"{base}/api/diagnostics", timeout=5)
        if r.status_code == 200:
            diag = sanitize_diagnostics(r.json())
    except Exception:
        pass
    jobs = []
    try:
        r = requests.get(f"{base}/api/jobs", timeout=10)
        if r.status_code == 200:
            data = r.json()
            rows = data.get("projects", data) if isinstance(data, dict) else data
            for row in rows[:jobs_n]:
                jobs.append(_redact_job(row))
    except Exception:
        pass
    if diag is None and not jobs:
        return None
    return {"diagnostics": diag, "jobs": jobs}


def collect_from_data_dir(data_dir: Path, jobs_n: int) -> dict:
    """Offline fallback: read the local SQLite job table read-only."""
    import sqlite3
    out = {"diagnostics": None, "jobs": [], "offline_status": "no-database"}
    db = data_dir / "clpz.db"
    if not db.exists():
        return out
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, stage, error_code, timings, created_at, completed_at "
            "FROM jobs ORDER BY created_at DESC LIMIT ?", (jobs_n,)
        ).fetchall()
        out["jobs"] = [_redact_job(dict(r)) for r in rows]
        out["offline_status"] = "ok"
    except Exception:
        # Database exception text can embed a local path or user data.
        out["offline_status"] = "unavailable"
    finally:
        conn.close()
    return out


def _redact_job(row: dict) -> dict:
    """Reduce a job to non-content, typed diagnostic fields only."""
    keep = {}
    job_id = _safe_label(row.get("id"), limit=64)
    if job_id and re.fullmatch(r"[a-fA-F0-9]{12}|[a-fA-F0-9]{32}", job_id):
        keep["id"] = job_id
    stage = _safe_label(row.get("stage"), APPROVED_JOB_STAGES, limit=24)
    if stage:
        keep["stage"] = stage
    error_code = _safe_label(row.get("error_code"), limit=64)
    if error_code and re.fullmatch(r"[A-Z0-9_]+", error_code):
        keep["error_code"] = error_code
    for key in ("created_at", "started_at", "completed_at"):
        safe = _safe_number(row.get(key), maximum=4e9)
        if safe is not None:
            keep[key] = safe
    progress = _safe_number(row.get("progress"), maximum=1)
    if progress is not None:
        keep["progress"] = progress
    if row.get("input_type") in {"url", "upload"}:
        keep["input_type"] = row["input_type"]
    max_clips = row.get("max_clips")
    if isinstance(max_clips, int) and not isinstance(max_clips, bool) and 1 <= max_clips <= 10:
        keep["max_clips"] = max_clips
    completed = row.get("completed_stages")
    if isinstance(completed, list):
        keep["completed_stages"] = [stage for stage in completed
                                    if _safe_label(stage, APPROVED_JOB_STAGES, limit=24)]
    timings = row.get("timings")
    if isinstance(timings, dict):
        safe_timings = {}
        for name, duration in timings.items():
            if name in APPROVED_TIMING_NAMES:
                safe = _safe_number(duration, maximum=86400)
                if safe is not None:
                    safe_timings[name] = safe
        keep["timings"] = safe_timings
    return keep


def log_metadata(data_dir: Path) -> dict:
    """Report known log presence without exporting arbitrary log content."""
    metadata = {}
    for name in ("server_stdout.log", "server_stderr.log"):
        p = data_dir / name
        try:
            metadata[name] = {"present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0}
        except OSError:
            metadata[name] = {"present": False, "bytes": 0}
    return metadata


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=20)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--out", default=str(ROOT / "support-bundle"))
    args = ap.parse_args()

    # Resolve the data dir the same way the app does (without importing it).
    data_dir = Path(os.environ.get("CLIPFORGE_DATA") or (Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "CLPZ"))

    bundle = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "CLPZ support bundle (redacted)",
        "machine": machine_profile(),
        "env_summary": env_summary(),
        "data_dir_exists": data_dir.exists(),
    }

    live = collect_from_api(args.api, args.jobs)
    if live:
        bundle["source"] = "live API"
        bundle.update(live)
    else:
        bundle["source"] = "offline (data dir)"
        bundle.update(collect_from_data_dir(data_dir, args.jobs))

    bundle["log_metadata"] = log_metadata(data_dir)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"clpz-support-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(bundle, indent=2, default=str))
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
