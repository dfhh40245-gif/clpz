"""Job manager. Each job runs the full pipeline in a worker thread.
State is mirrored to data/<job_id>/job.json so finished jobs survive restarts
(a job mid-run when the server dies is marked as interrupted on reload).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import subprocess
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
import credits as credits_mod
import database as db
import proc as proc_mod
from pipeline import (
    analyzer,
    captions,
    cutter,
    downloader,
    srt_parser,
    transcriber,
)

JOBS: dict[str, dict] = {}
_lock = threading.Lock()
# Cancellation events — keyed by job_id
_cancel_events: dict[str, threading.Event] = {}
# Serializes the dedupe->charge->create->map sequence so one logical
# submission (by idempotency key) can never create more than one job.
_job_create_lock = threading.Lock()

# Heavy stages (download/transcribe/render) saturate the machine, so jobs
# beyond this limit wait in "queued" until a slot frees up.
# CLPZ_TEST_WORKERS=0 pins the semaphore to zero: every job stays "queued" and
# no worker runs — a TEST-ONLY gate so ledger tests observe charges/refunds
# deterministically without disabling legitimate refund logic. Any explicit
# positive value overrides the default; unset keeps the default of 1.
_TEST_WORKERS = os.getenv("CLPZ_TEST_WORKERS")
if _TEST_WORKERS is not None:
    MAX_CONCURRENT_JOBS = max(0, int(_TEST_WORKERS))
else:
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
# Maximum number of jobs waiting to run. Admission beyond this returns an
# explicit queue-full response BEFORE charging (task 11).
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "8"))
_slots = threading.Semaphore(MAX_CONCURRENT_JOBS)
_admissions: set[str] = set()
_queue_lock = threading.Lock()

# ── Task 11: bounded edit renders ────────────────────────────────────
# Editor re-renders are FFmpeg-heavy like pipeline renders and historically
# bypassed all slot control (F12). They get their own small budget (default:
# share the pipeline worker count) plus a bounded wait, so an editor burst
# fails fast (HTTP 503) instead of growing worker load unbounded.
EDIT_RENDER_CONCURRENCY = max(1, int(os.getenv(
    "EDIT_RENDER_CONCURRENCY", str(max(1, MAX_CONCURRENT_JOBS)))))
EDIT_QUEUE_WAIT_SECONDS = float(os.getenv("EDIT_QUEUE_WAIT_SECONDS", "5"))
# Hard deadline for one edit re-render. subprocess.run(timeout=...) kills the
# child even if the ffmpeg process ignores cooperative signals.
EDIT_RENDER_DEADLINE_SECONDS = float(os.getenv("EDIT_RENDER_DEADLINE_SECONDS", "300"))
_edit_semaphore = threading.Semaphore(EDIT_RENDER_CONCURRENCY)

# Maximum accepted webhook body (task 11: bound before parsing).
WEBHOOK_MAX_BYTES = 1 * 1024 * 1024


class QueueFullError(RuntimeError):
    """Raised when admission is refused because the queue is at capacity.

    The API layer maps this to HTTP 503 (task 11). For charged submissions
    the charge is refunded before the error escapes, so a queue-full reject
    never costs the user a credit.
    """


class RenderTimeoutError(RuntimeError):
    """An edit re-render exceeded its hard deadline (task 11)."""


def try_acquire_slot(job_id: str) -> bool:
    """Bounded admission for one unit of heavy work (task 11).

    Counts one pending submission against MAX_QUEUE_DEPTH. Returns False
    when the queue is full — the caller must reject the request (HTTP 503)
    BEFORE charging/creating work. The reservation is released by the
    worker thread only after it acquires an execution slot, or on cancellation
    or creation failure. Each job ID owns one reservation, so repeated cleanup
    cannot accidentally release a different job's place in the queue.
    """
    with _queue_lock:
        if job_id in _admissions or len(_admissions) >= MAX_QUEUE_DEPTH:
            return False
        _admissions.add(job_id)
        return True


def queue_depth() -> int:
    with _queue_lock:
        return len(_admissions)


def _release_admission(job_id: str) -> None:
    """Release one admission reservation (queue count only).

    The ``_slots`` semaphore is released by ``_run``'s ``with`` block; this
    only retires the pending-work reservation taken by ``try_acquire_slot``.
    """
    with _queue_lock:
        _admissions.discard(job_id)


class JobTimeoutError(RuntimeError):
    """Raised when a job exceeds its absolute deadline."""


def _check_cancelled(job_id: str):
    """Raise if this job has been cancelled."""
    ev = _cancel_events.get(job_id)
    if ev and ev.is_set():
        raise RuntimeError("Job cancelled by user.")


def _check_deadline(job_id: str, deadline: float):
    """Raise if this job has exceeded its absolute deadline."""
    if time.monotonic() > deadline:
        proc_mod.kill_job(job_id)
        raise JobTimeoutError(
            f"Job timed out after {config.JOB_TIMEOUT_SECONDS:.0f}s."
        )


def _check_stop(job_id: str, deadline: float | None = None):
    """Combined cancellation + deadline guard used at every stage boundary."""
    _check_cancelled(job_id)
    if deadline is not None:
        _check_deadline(job_id, deadline)


def _check_cancelled(job_id: str):
    """Raise if this job has been cancelled."""
    ev = _cancel_events.get(job_id)
    if ev and ev.is_set():
        raise RuntimeError("Job cancelled by user.")


class IdempotencyConflict(Exception):
    """Same scoped idempotency key reused with a DIFFERENT request payload.

    Raised by create_*_idempotent when the fingerprint of the incoming
    request does not match the fingerprint recorded for that scoped key.
    The API layer maps this to HTTP 409 (task 09): replay must return the
    ORIGINAL result for the SAME request, never a different or stale job.
    """


def idempotency_scope(user_id: str | None) -> str:
    """Local-workspace identity lifetime for idempotency scopes (task 09).

    Logged-in users are scoped by account id; anonymous desktop callers are
    scoped as the single local workspace ("anon"). This is intentional for
    a single-user local app: anonymous work belongs to the machine, not to
    a cross-user public namespace. Keys are additionally bound to the
    operation and payload fingerprint, so "anon" scope cannot collide with
    account work that shares a key string.
    """
    return f"user:{user_id}" if user_id else "anon"


def canonical_fingerprint(*parts: str) -> str:
    """Stable SHA-256 fingerprint of the canonical request payload.

    All semantic request fields are joined with a separator that cannot
    appear in the values (unit separator) so different field orders/values
    produce different digests.
    """
    import hashlib
    return hashlib.sha256("\x1f".join(parts).encode("utf-8", "surrogatepass")).hexdigest()


def file_fingerprint(path, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 of a file's contents, read in bounded chunks (task 09).

    Never buffers the whole file into RAM, so 2 GB uploads can be
    fingerprinted safely. Returns the hex digest.
    """
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def cancel_job(job_id: str) -> bool:
    """Cancel a running or queued job. Returns True if cancelled.

    Idempotent: a job that is already done/errored/cancelled returns False.
    Sets the cancellation flag AND terminates any live subprocess tree so the
    underlying work actually stops rather than just changing a database flag.
    """
    cancelled = False
    try:
        with _lock:
            job = JOBS.get(job_id)
            if not job or job.get("stage") in ("done", "error", "cancelled"):
                return False
            ev = _cancel_events.get(job_id)
            if ev:
                ev.set()
            cancelled = True
            _update_no_lock(job_id, stage="cancelled", error="Cancelled by user.", cancelled_at=time.time())
    finally:
        if cancelled:
            # An upload may never start a worker. Clean up even if writing
            # the cancellation state failed; the event is already set.
            _release_admission(job_id)
            proc_mod.kill_job(job_id)
    return True


def _rollback_failed_submission(job_id: str, user_id: str | None,
                                reason: str, idempotency_key: str = "") -> None:
    """Release failed admission and refund only a committed debit for this job."""
    _release_admission(job_id)
    try:
        cancel_job(job_id)
    except Exception:
        logging.getLogger(__name__).warning("failed to cancel rejected job %s", job_id,
                                            exc_info=True)
    try:
        db.delete_idempotency_jobs_by_job(job_id)
    except Exception:
        logging.getLogger(__name__).warning("failed to remove mapping for %s", job_id,
                                            exc_info=True)
    if user_id:
        try:
            if db.job_was_charged(user_id, job_id):
                credits_mod.refund(user_id, credits_mod.COST_PER_FORGE,
                                   related_id=job_id, reason=reason)
                if idempotency_key:
                    db.delete_idempotency_for_user(idempotency_key, user_id)
        except Exception:
            logging.getLogger(__name__).warning("failed to refund rejected job %s", job_id,
                                                exc_info=True)


def create_job_idempotent(
    url: str,
    max_clips: int,
    top_text: str,
    user_id: str | None,
    idempotency_key: str = "",
) -> tuple[str | None, bool, int | None]:
    """Atomically dedupe-by-SCOPE+key, charge, create, and map a job.

    Returns ``(job_id, is_new, remaining)`` where ``is_new`` is True only when
    a brand-new job was created and charged.  Reusing the same scoped key
    with the SAME canonical request returns the ORIGINAL job_id with no
    second charge.  The same key with a DIFFERENT payload raises
    ``IdempotencyConflict`` (mapped to HTTP 409 upstream, task 09) — and a
    key used by a different principal simply maps to a different scope, so
    unrelated work is never deduplicated together (F09).

    ``job_id`` is None when the user has insufficient credits.
    """
    scope = idempotency_scope(user_id)
    fingerprint = canonical_fingerprint("forge", url, str(max_clips), top_text)
    with _job_create_lock:
        if idempotency_key:
            existing = db.get_job_id_for_idempotency(scope, idempotency_key)
            if existing:
                stored_fp = db.get_idempotency_fingerprint(scope, idempotency_key)
                if stored_fp and stored_fp != fingerprint:
                    raise IdempotencyConflict(
                        "This submission key was already used with different "
                        "settings. Reload the page to start a new submission."
                    )
                remaining = credits_mod.get_balance(user_id) if user_id else None
                return existing, False, remaining

        # Bounded admission (task 11): refuse BEFORE charging when the queue
        # is saturated, so a burst never stacks unbounded pending work.
        job_id = uuid.uuid4().hex[:12]
        if not try_acquire_slot(job_id):
            raise QueueFullError(
                "The processing queue is full. Please try again in a moment."
            )

        try:
            if user_id:
                ok, remaining = credits_mod.check_and_charge(
                    user_id, credits_mod.COST_PER_FORGE, related_id=job_id,
                    idempotency_key=idempotency_key
                )
                if not ok:
                    _release_admission(job_id)
                    return None, False, remaining
            else:
                remaining = None
        except Exception:
            _rollback_failed_submission(job_id, user_id,
                                        "Forge charge failed — refund", idempotency_key)
            raise

        try:
            create_job(url, max_clips, top_text, user_id=user_id, job_id=job_id)
        except Exception:
            # A failed persist/thread start may occur after the debit commits.
            _rollback_failed_submission(job_id, user_id,
                                        "Job creation failed — refund", idempotency_key)
            raise
        if idempotency_key:
            try:
                db.save_idempotency_job(idempotency_key, job_id, user_id,
                                        scope=scope, fingerprint=fingerprint)
            except Exception:
                _rollback_failed_submission(job_id, user_id,
                                            "Forge mapping failed — refund", idempotency_key)
                raise
        return job_id, True, remaining


def _update_no_lock(job_id: str, **kwargs):
    """Update job state without acquiring the lock (caller must hold it)."""
    job = JOBS.get(job_id)
    if job is None:
        return
    job.update(kwargs)
    _persist(job)


def _update(job_id: str, **kwargs):
    with _lock:
        job = JOBS.get(job_id)
        if job is None:
            # Job was cleared/reset while its worker thread was mid-flight.
            return
        job.update(kwargs)
        _persist(job)


def _persist(job: dict):
    """Persist a job snapshot durably (task 10).

    Authority contract (ADR-0001 / task 10): SQLite is the AUTHORITATIVE job
    record; job.json is a derived restart-recovery snapshot. Order matters:
    the authoritative write happens first; the snapshot uses atomic file
    replacement (write temp + os.replace) so a crash mid-write can never
    leave a half-written job.json.

    Persistence failures are NO LONGER silently swallowed: the SQLite error
    propagates to the pipeline worker (which marks the job failed with a
    persistence error) and job.json failures are logged with the job id.
    """
    try:
        db.save_job(job)
    except Exception:
        logging.getLogger(__name__).warning(
            "SQLite persist failed for job %s", job.get("id"), exc_info=True)
        raise
    try:
        _write_job_snapshot(job)
    except OSError:
        logging.getLogger(__name__).warning(
            "job.json snapshot write failed for job %s (SQLite record intact)",
            job.get("id"), exc_info=True)


def _write_job_snapshot(job: dict) -> None:
    """Atomically refresh the derived JSON copy of one committed job."""
    d = config.DATA_DIR / job["id"]
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "job.json.tmp"
    tmp.write_text(json.dumps(job), encoding="utf-8")
    os.replace(tmp, d / "job.json")


def _validate_output(path: Path, job_id: str = "", *, expect_audio: bool = True) -> dict:
    """Validate a rendered clip using ffprobe and a real decode pass.

    ``format.duration`` is deliberately treated as the authoritative duration:
    the requested transcript range is useful provenance, but frame boundaries
    mean it is not necessarily the duration of the encoded MP4.

    ``expect_audio=False`` accepts an intentionally silent export (task 06):
    audio requirements stay strict for normal renders but a muted export with
    no audio stream is valid rather than an error.
    """
    import json as _json
    result = {"valid": False, "error": ""}
    if not path.exists():
        result["error"] = "Output file does not exist."
        return result
    if path.stat().st_size == 0:
        result["error"] = "Output file is empty."
        return result
    try:
        ffprobe = _find_bin("ffprobe")
        proc = proc_mod.run(
            job_id,
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,duration,width,height,pix_fmt",
                "-show_entries", "format=duration,size",
                "-of", "json", str(path),
            ],
            timeout=30,
        )
        if proc.returncode != 0:
            result["error"] = "ffprobe returned non-zero exit code."
            return result
        probe = _json.loads(proc.stdout)
        streams = probe.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not video_stream:
            result["error"] = "No video stream found."
            return result
        if not audio_stream:
            # Intentionally silent exports (muted edit) are valid without audio.
            if not expect_audio:
                result["valid"] = True
                fmt = probe.get("format", {})
                duration = float(fmt.get("duration", 0))
                if duration <= 0:
                    result["error"] = "Zero duration."
                    result["valid"] = False
                    return result
                result["duration"] = duration
                result["size"] = int(fmt.get("size", 0))
                result["width"] = int(video_stream.get("width", 0))
                result["height"] = int(video_stream.get("height", 0))
                result["video_codec"] = video_stream.get("codec_name", "")
                result["audio_codec"] = None
                result["pix_fmt"] = video_stream.get("pix_fmt")
                result["decoded_frame"] = True
                return result
            result["error"] = "No audio stream found."
            return result
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        if duration <= 0:
            result["error"] = "Zero duration."
            return result

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if (width, height) != (config.OUT_WIDTH, config.OUT_HEIGHT):
            result["error"] = (
                f"Unexpected dimensions {width}x{height}; expected "
                f"{config.OUT_WIDTH}x{config.OUT_HEIGHT}."
            )
            return result

        video_codec = video_stream.get("codec_name", "")
        audio_codec = audio_stream.get("codec_name", "")
        if video_codec not in {"h264", "avc1"}:
            result["error"] = f"Unexpected video codec: {video_codec or 'unknown'}."
            return result
        if audio_stream and audio_codec != "aac":
            result["error"] = f"Unexpected audio codec: {audio_codec or 'unknown'}."
            return result

        # ffprobe only inspects container metadata. Decode one video frame as a
        # final guard against a corrupt stream that happens to have a valid MOOV.
        decode = proc_mod.run(
            job_id,
            [
                _find_bin("ffmpeg"), "-v", "error", "-i", str(path),
                "-map", "0:v:0", "-frames:v", "1", "-f", "null", os.devnull,
            ],
            timeout=60,
        )
        if decode.returncode != 0:
            result["error"] = "Video stream could not be decoded."
            return result

        result["valid"] = True
        result["duration"] = duration
        result["size"] = int(fmt.get("size", 0))
        result["width"] = width
        result["height"] = height
        result["video_codec"] = video_codec
        result["audio_codec"] = audio_codec
        result["pix_fmt"] = video_stream.get("pix_fmt")
        result["decoded_frame"] = True
    except Exception as e:
        result["error"] = f"Validation failed: {e}"
    return result


def _build_thumbnail(path: Path, duration: float, out_path: Path, job_id: str = "") -> Path:
    """Create a compact, real preview image from the rendered clip."""
    timestamp = max(0.0, min(duration * 0.45, max(0.0, duration - 0.1)))
    proc = proc_mod.run(
        job_id,
        [
            _find_bin("ffmpeg"), "-y", "-v", "error",
            "-ss", f"{timestamp:.3f}", "-i", str(path),
            "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", str(out_path),
        ],
        timeout=60,
    )
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Thumbnail generation failed.")
    return out_path


def load_saved_jobs():
    """Restore committed SQLite state; JSON import happened in migration v4."""
    # A failed database read must stop startup rather than silently promote
    # possibly stale JSON to authority. The snapshot is a derived copy.
    all_db_jobs = db.get_all_jobs()

    def interrupted(job: dict) -> bool:
        if job.get("stage") in ("done", "error", "cancelled"):
            return False
        job["stage"] = "error"
        job["error"] = (
            "Server restarted while this job was running. Submit it again."
        )
        return True

    for job in all_db_jobs:
        job_dir = config.DATA_DIR / job["id"]
        if not job_dir.exists() and job.get("stage") in ("done", "error", "cancelled"):
            # Terminal metadata with no project directory is a broken ghost.
            db.delete_job(job["id"])
            db.delete_idempotency_jobs_by_job(job["id"])
            continue
        if interrupted(job):
            db.save_job(job)
        with _lock:
            JOBS[job["id"]] = job
        try:
            _write_job_snapshot(job)
        except OSError:
            logging.getLogger(__name__).warning(
                "Could not refresh job snapshot for %s", job["id"], exc_info=True)

    # Automatic retention cleanup is strictly opt-in.  A restart never
    # silently removes completed projects unless CLIPFORGE_AUTO_CLEANUP_HOURS
    # is explicitly set to a positive value.
    if config.AUTO_CLEANUP_HOURS > 0:
        _cleanup_old_jobs(max_age_hours=config.AUTO_CLEANUP_HOURS)


def backup_project(job_id: str, dest_dir: str | Path | None = None) -> dict:
    """Archive one project's durable artifacts with a checksum manifest (task 10).

    Copies source media, transcript (SRT), word timings, rendered clips,
    thumbnails and job.json into a timestamped folder under
    ``<data>/project-backups/`` and writes ``manifest.json`` recording each
    file's SHA-256 and size. Media files are copied, not moved — the
    original project is never touched.

    Returns {ok, path, manifest} on success; {ok: False, error} on failure.
    """
    import hashlib
    job = get_job(job_id)
    if job is None:
        return {"ok": False, "error": f"job {job_id} not found"}
    job_dir = config.DATA_DIR / job_id
    if not job_dir.exists():
        return {"ok": False, "error": f"job directory missing: {job_dir}"}

    base = Path(dest_dir) if dest_dir else config.DATA_DIR / "project-backups"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = base / f"{job_id}-{stamp}"
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"cannot create backup dir: {e}"}

    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    files: list[dict] = []
    errors: list[str] = []
    for f in sorted(job_dir.iterdir()):
        if not f.is_file():
            continue
        target = dest / f.name
        try:
            shutil.copy2(f, target)
            files.append({
                "name": f.name,
                "sha256": _sha256(target),
                "size": target.stat().st_size,
            })
        except OSError as e:
            errors.append(f"{f.name}: {e}")

    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "created_at": time.time(),
        "stage": job.get("stage"),
        "input_type": job.get("input_type"),
        "source": job.get("video", {}).get("path") if job.get("video") else None,
        "files": files,
        "errors": errors,
    }
    try:
        tmp = dest / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(tmp, dest / "manifest.json")
    except OSError as e:
        errors.append(f"manifest: {e}")

    return {"ok": not errors, "path": str(dest), "files": len(files),
            "errors": errors, "manifest": manifest}


def reset_for_testing():
    """Reset all in-memory job state. For test isolation only."""
    global JOBS, _slots, _edit_semaphore
    with _lock:
        for event in _cancel_events.values():
            event.set()
        JOBS.clear()
    with _queue_lock:
        _admissions.clear()
    with _edit_registry_lock:
        _edit_registry.clear()
    # Recreate semaphore to reset slots
    _slots = threading.Semaphore(MAX_CONCURRENT_JOBS)
    _edit_semaphore = threading.Semaphore(EDIT_RENDER_CONCURRENCY)


def _cleanup_old_jobs(max_age_hours: int = 24, keep_minimum: int = 3):
    """Remove old completed/errored jobs to prevent disk bloat.

    Keeps at least ``keep_minimum`` jobs regardless of age.
    Only removes jobs in 'done' or 'error' stages.
    """
    import shutil
    import time as _time

    now = _time.time()
    cutoff = now - (max_age_hours * 3600)

    # Collect all jobs with their modification times
    candidates = []
    for f in config.DATA_DIR.glob("*/job.json"):
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
            stage = job.get("stage", "")
            if stage not in ("done", "error"):
                continue
            mtime = f.stat().st_mtime
            candidates.append((mtime, job["id"], f.parent))
        except Exception:
            continue

    # Sort by modification time (oldest first)
    candidates.sort(key=lambda x: x[0])

    # Keep at least keep_minimum, remove the rest if old enough
    to_remove = candidates[:len(candidates) - keep_minimum] if len(candidates) > keep_minimum else []

    removed = 0
    for mtime, job_id, job_dir in to_remove:
        if mtime < cutoff:
            try:
                shutil.rmtree(job_dir, ignore_errors=True)
                with _lock:
                    JOBS.pop(job_id, None)
                # Keep the filesystem and database consistent: a deleted job
                # must not come back from SQLite on the next restart.
                db.delete_job(job_id)
                db.delete_idempotency_jobs_by_job(job_id)
                removed += 1
            except Exception:
                pass

    if removed:
        logging.getLogger(__name__).info(
            "[cleanup] Removed %d old jobs (>%sh)", removed, max_age_hours
        )


def create_job(url: str, max_clips: int, top_text: str = "", user_id: str | None = None,
               job_id: str | None = None) -> str:
    job_id = job_id or uuid.uuid4().hex[:12]
    _cancel_events[job_id] = threading.Event()

    with _lock:
        JOBS[job_id] = {
            "id": job_id,
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "cancelled_at": None,
            "input_type": "youtube",
            "url": url,
            "max_clips": max_clips,
            "top_text": top_text,
            "user_id": user_id,
            "stage": "queued",
            "progress": 0.0,
            "video": None,
            "clips": [],
            "error": None,
            "timings": {},
            "error_code": None,
            "completed_stages": [],
        }
        _persist(JOBS[job_id])

    t = threading.Thread(target=_run, args=(job_id,), daemon=True)
    t.start()

    return job_id


def create_upload_job_idempotent(
    filename: str,
    max_clips: int,
    top_text: str,
    user_id: str | None,
    idempotency_key: str = "",
    content_fingerprint: str = "",
) -> tuple[str | None, bool, int | None]:
    """Upload equivalent of ``create_job_idempotent``: one scoped key = one job.

    The HTTP endpoint must stage, validate, and hash the media *before*
    calling this function.  That makes the complete content+options digest
    available before an existing idempotency mapping can be accepted.  A
    caller without a content fingerprint is retained only for internal
    construction tests; it cannot safely deduplicate an upload replay.
    """
    scope = idempotency_scope(user_id)
    if idempotency_key and not content_fingerprint:
        raise ValueError(
            "content_fingerprint is required when creating an idempotent upload"
        )
    options_fingerprint = canonical_fingerprint("upload", filename, str(max_clips), top_text)
    fingerprint = ("sha256:file:" + content_fingerprint + "|opts:" + options_fingerprint
                   if content_fingerprint else options_fingerprint)
    with _job_create_lock:
        if idempotency_key:
            existing = db.get_job_id_for_idempotency(scope, idempotency_key)
            if existing:
                stored_fp = db.get_idempotency_fingerprint(scope, idempotency_key)
                # A production upload has a digest.  A legacy mapping which
                # lacks one cannot prove that the newly staged media is the
                # same file, so fail closed instead of replaying stale work.
                if stored_fp != fingerprint:
                    raise IdempotencyConflict(
                        "This submission key was already used with a different "
                        "upload or settings. Reload the page to start a new submission."
                    )
                remaining = credits_mod.get_balance(user_id) if user_id else None
                return existing, False, remaining

        # Bounded admission (task 11): refuse BEFORE charging when the queue
        # is saturated, so a burst never stacks unbounded pending work.
        job_id = uuid.uuid4().hex[:12]
        if not try_acquire_slot(job_id):
            raise QueueFullError(
                "The processing queue is full. Please try again in a moment."
            )

        try:
            if user_id:
                ok, remaining = credits_mod.check_and_charge(
                    user_id, credits_mod.COST_PER_FORGE, related_id=job_id,
                    idempotency_key=idempotency_key
                )
                if not ok:
                    _release_admission(job_id)
                    return None, False, remaining
            else:
                remaining = None
        except Exception:
            _rollback_failed_submission(job_id, user_id,
                                        "Upload charge failed — refund", idempotency_key)
            raise

        try:
            create_upload_job(filename, max_clips, top_text, user_id=user_id,
                              job_id=job_id)
        except Exception:
            _rollback_failed_submission(job_id, user_id,
                                        "Upload job creation failed — refund", idempotency_key)
            raise
        if idempotency_key:
            try:
                db.save_idempotency_job(idempotency_key, job_id, user_id,
                                        scope=scope, fingerprint=fingerprint)
            except Exception:
                _rollback_failed_submission(job_id, user_id,
                                            "Upload mapping failed — refund", idempotency_key)
                raise
        return job_id, True, remaining


def create_upload_job(filename: str, max_clips: int, top_text: str = "",
                      user_id: str | None = None, job_id: str | None = None) -> str:
    """Create a job for a locally uploaded video."""
    job_id = job_id or uuid.uuid4().hex[:12]
    _cancel_events[job_id] = threading.Event()

    with _lock:
        JOBS[job_id] = {
            "id": job_id,
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "failed_at": None,
            "cancelled_at": None,
            "input_type": "upload",
            "url": "",
            "max_clips": max_clips,
            "top_text": top_text,
            "user_id": user_id,
            "stage": "queued",
            "progress": 0.0,
            "video": None,
            "clips": [],
            "error": None,
            "timings": {},
            "error_code": None,
            "completed_stages": [],
        }
        _persist(JOBS[job_id])

    return job_id


def _find_bin(name: str) -> str:
    """Find a binary, checking backend/bin first."""
    import platform
    import shutil as _shutil
    is_windows = platform.system() == "Windows"
    exe_name = f"{name}.exe" if is_windows else name
    bin_dir = Path(__file__).resolve().parent / "bin"
    candidate = bin_dir / exe_name
    if candidate.exists():
        return str(candidate)
    found = _shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} not found. Install it or place it in {bin_dir}"
    )


def _classify_error(error_msg: str) -> str:
    """Classify an error message into a structured error code."""
    msg = error_msg.lower()
    if "cancelled" in msg:
        return "CANCELLED"
    if "timed out" in msg:
        return "JOB_TIMEOUT"
    if "hard deadline" in msg:
        return "TRANSCRIBE_TIMEOUT"
    if "transcription failed" in msg:
        if "oom" in msg or "memory" in msg or "allocat" in msg:
            return "TRANSCRIPTION_OOM"
        return "TRANSCRIPTION_FAILED"
    if "no speech detected" in msg:
        return "NO_SPEECH"
    if "srt file is empty" in msg or "transcript could not be parsed" in msg or "empty transcript" in msg:
        return "NO_SPEECH"
    if "no valid clips" in msg or "no clips" in msg:
        return "ANALYZER_EMPTY"
    if "ffmpeg failed" in msg or "render" in msg:
        if "filter" in msg:
            return "FFMPEG_FILTER_FAILED"
        return "FFMPEG_FAILED"
    if "output validation" in msg:
        return "OUTPUT_INVALID"
    if "download" in msg and "failed" in msg:
        if "403" in msg or "forbidden" in msg:
            return "YTDLP_403"
        if "bot" in msg or "sign in" in msg:
            return "YTDLP_BOT_CHECK"
        if "unavailable" in msg or "private" in msg:
            return "YTDLP_UNAVAILABLE"
        if "timeout" in msg:
            return "YTDLP_TIMEOUT"
        return "YTDLP_FAILED"
    if "not found" in msg:
        return "MISSING_DEPENDENCY"
    return "UNKNOWN"


def start_uploaded_job(
    job_id: str,
    video_path: str,
    filename: str,
):
    """Attach an uploaded video to an existing job and start processing.
    Whisper transcription runs automatically."""
    try:
        _start_uploaded_job_impl(job_id, video_path, filename)
    except Exception:
        # No worker owns this reservation if setup or thread startup fails.
        _release_admission(job_id)
        raise


def _start_uploaded_job_impl(job_id: str, video_path: str, filename: str):
    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = proc_mod.run(
            job_id,
            [
                _find_bin("ffprobe"),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            timeout=30,
        )

        duration = float(result.stdout.strip())
    except Exception:
        duration = 0.0

    video = {
        "path": video_path,
        "title": Path(filename).stem,
        "duration": duration,
    }

    _update(
        job_id,
        video=video,
        stage="queued",
        progress=0.0,
    )

    t = threading.Thread(target=_run, args=(job_id,), daemon=True)
    t.start()


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = JOBS.get(job_id)
        return copy.deepcopy(job) if job else None


def get_all_jobs() -> list[dict]:
    """Return a list of all current jobs (deep copies)."""
    with _lock:
        return [copy.deepcopy(j) for j in JOBS.values()]


def _update_clip(job_id: str, index: int, **kwargs):
    """Mutate one clip's fields under the lock, then persist."""
    with _lock:
        job = JOBS.get(job_id)
        if job is None:
            return
        for c in job["clips"]:
            if c["index"] == index:
                c.update(kwargs)

        _persist(job)


def _run(job_id: str):
    # Keep this job in the bounded pending queue until it really owns a
    # worker. Timed acquisition lets queued cancellations exit promptly.
    acquired = False
    slots = _slots
    try:
        while not acquired:
            if _cancel_events.get(job_id) and _cancel_events[job_id].is_set():
                return
            acquired = slots.acquire(timeout=0.1)
        _release_admission(job_id)
        if _cancel_events.get(job_id) and _cancel_events[job_id].is_set():
            return
        _run_pipeline(job_id)
    finally:
        if acquired:
            slots.release()
        _release_admission(job_id)


# ── Task 11: watchdog registry for edit re-renders ──────────────────
# The pipeline has its own absolute deadline; edit re-renders run inside a
# request handler where a wedged ffmpeg previously blocked a worker slot
# forever. ``note_edit_started``/``note_edit_finished`` register the render
# with the watchdog thread, which force-fails anything past its deadline.

_edit_registry: dict[str, dict] = {}   # key "job:idx" -> {"proc_name", "started", "deadline"}
_edit_registry_lock = threading.Lock()
_watchdog_started = False


def note_edit_started(job_id: str, index: int, output_name: str) -> None:
    """Register an in-flight edit re-render with the watchdog."""
    key = f"{job_id}:{index}"
    with _edit_registry_lock:
        _edit_registry[key] = {
            "output": output_name,
            "started": time.monotonic(),
            "deadline": time.monotonic() + EDIT_RENDER_DEADLINE_SECONDS,
        }


def note_edit_finished(job_id: str, index: int) -> None:
    """Deregister a completed edit re-render (success or handled failure)."""
    with _edit_registry_lock:
        _edit_registry.pop(f"{job_id}:{index}", None)


def _watchdog_sweep() -> None:
    """Force-fail edit renders that outlived their hard deadline.

    Because the endpoint runs ``subprocess.run(timeout=...)``, the child is
    already killed by the timeout path; the watchdog is the second line of
    defense for pathological cases (kill signal swallowed, IO hang) and it
    clears the slot reservation so the budget can never leak.
    """
    now = time.monotonic()
    expired = []
    with _edit_registry_lock:
        for key, info in list(_edit_registry.items()):
            if now > info["deadline"]:
                expired.append((key, info))
                _edit_registry.pop(key, None)
    for key, info in expired:
        job_id, _, idx = key.partition(":")
        logging.getLogger(__name__).warning(
            "[watchdog] edit render %s exceeded its %ss deadline; forcing failure",
            key, EDIT_RENDER_DEADLINE_SECONDS,
        )
        try:
            # Kill any surviving registered subprocess for this job and
            # remove the partial output so no truncated file is promoted.
            proc_mod.kill_job(job_id)
            stale_out = config.DATA_DIR / job_id / (
                info.get("output") or f"clip_{idx}_edited.mp4"
            )
            Path(stale_out).unlink(missing_ok=True)
        except Exception:
            logging.getLogger(__name__).warning(
                "[watchdog] cleanup for %s failed", key, exc_info=True)


def _watchdog_loop() -> None:
    while True:
        try:
            _watchdog_sweep()
        except Exception:
            logging.getLogger(__name__).warning("watchdog sweep failed", exc_info=True)
        time.sleep(5)


def start_watchdog() -> None:
    """Start the edit-render watchdog thread once (idempotent)."""
    global _watchdog_started
    if _watchdog_started:
        return
    _watchdog_started = True
    threading.Thread(target=_watchdog_loop, daemon=True, name="clpz-watchdog").start()


def _run_pipeline(job_id: str):
    job = get_job(job_id)
    if job is None:
        # Job was cleared/reset while its worker was queued or starting.
        return
    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Mark the authoritative start time
    _update(job_id, started_at=time.time())

    # Absolute deadline for the whole job (backstop for stages that are not
    # individually supervised; transcription now has its own hard deadline
    # via transcriber.transcribe_supervised, R02).
    deadline = time.monotonic() + config.JOB_TIMEOUT_SECONDS

    # Check disk space — need at least 2GB free for a typical job
    try:
        import psutil
        disk = psutil.disk_usage(str(config.DATA_DIR))
        if disk.free < 2 * 1024**3:  # 2 GB
            _update(job_id, stage="error", error="Not enough disk space. Need at least 2 GB free.", error_code="DISK_FULL", failed_at=time.time())
            # Task 08: a charged job that fails before any work must refund
            # exactly once (same policy as any other failure path).
            if job.get("user_id"):
                try:
                    credits_mod.refund(
                        job["user_id"],
                        credits_mod.COST_PER_FORGE,
                        related_id=job_id,
                        reason="Insufficient disk space — refund",
                    )
                except Exception:
                    pass
            return
    except ImportError:
        pass

    timings = {}
    completed_stages = list(job.get("completed_stages", []))

    def _timed(name):
        class _T:
            def __enter__(self):
                self.t0 = time.monotonic()

            def __exit__(self, *a):
                timings[name] = round(
                    time.monotonic() - self.t0, 1
                )
                _update(job_id, timings=dict(timings))

        return _T()

    def _mark_complete(stage: str):
        if stage not in completed_stages:
            completed_stages.append(stage)
            _update(job_id, completed_stages=list(completed_stages))

    try:
        # 1. Download (skip if already completed or video uploaded)
        existing = job.get("video")
        if "download" in completed_stages and existing:
            video = existing
            _update(job_id, video=video, progress=1.0)
        elif existing and Path(existing.get("path", "")).exists():
            video = existing
            _update(job_id, video=video, progress=1.0)
        else:
            _check_stop(job_id, deadline)
            _update(job_id, stage="downloading", progress=0.0)

            with _timed("download"):
                video = downloader.download(
                    job["url"], job_dir, job_id=job_id,
                )

            _update(job_id, video=video, progress=1.0)
        _mark_complete("download")

        # 2. Transcribe (skip if SRT already exists)
        srt_path = job_dir / "transcript.srt"
        words_path = job_dir / "words.json"

        if "transcribe" in completed_stages and srt_path.exists():
            pass  # Already transcribed
        else:
            _check_stop(job_id, deadline)
            _update(job_id, stage="transcribing", progress=0.0)

            try:
                with _timed("transcribe"):
                    # R02: supervised boundary — in production the model runs
                    # in a child process that is force-terminated at a hard
                    # deadline (TRANSCRIBE_DEADLINE_SECONDS), so a hung model
                    # cannot hold this worker slot indefinitely.
                    raw_transcript = transcriber.transcribe_supervised(
                        video["path"],
                        progress_cb=lambda p: _update(job_id, progress=p),
                        job_dir=job_dir,
                        job_id=job_id,
                    )
            except Exception as e:
                raise RuntimeError(f"Transcription failed: {e}") from e
        _mark_complete("transcribe")

        # 3. Parse (skip if already parsed and clips exist)
        if not srt_path.exists():
            raise RuntimeError("Transcription produced no SRT file.")

        transcript = None
        if "parse" in completed_stages and "analyze" in completed_stages:
            # Resume path (F05): the stage markers claim parse+analyze are done,
            # but ``transcript`` was never assigned in this process. Rebuild it
            # from the persisted artifacts (SRT + optional words.json) and
            # validate before trusting the markers.
            _update(job_id, stage="parsing", progress=0.0)
            try:
                with _timed("parse"):
                    transcript = srt_parser.parse_srt(str(srt_path))
            except Exception as e:
                raise RuntimeError(
                    f"Saved transcript artifact is invalid during resume: {e}") from e
            if not transcript["segments"]:
                raise RuntimeError(
                    "Saved transcript is empty during resume — cannot pick clips.")
        else:
            _update(job_id, stage="parsing", progress=0.0)

            try:
                with _timed("parse"):
                    transcript = srt_parser.parse_srt(str(srt_path))
            except Exception as e:
                raise RuntimeError(f"Generated transcript could not be parsed: {e}") from e

            if not transcript["segments"]:
                raise RuntimeError("No speech detected in this video — cannot pick clips.")

        duration = video["duration"] or (
            transcript["segments"][-1]["end"] if transcript["segments"] else 0
        )
        _mark_complete("parse")

        # 4. Analyze
        _check_stop(job_id, deadline)
        _update(job_id, stage="analyzing", progress=0.0)

        with _timed("analyze"):
            found = analyzer.find_clips(
                video["title"], duration, transcript["segments"], job["max_clips"],
            )

        clips = [
            {
                **c,
                "id": f"{job_id}-clip-{i}",
                "index": i,
                "status": "pending",
                "file": None,
                "thumbnail": None,
                "duration": None,
                "validation": None,
            }
            for i, c in enumerate(found)
        ]
        _update(job_id, clips=clips, progress=1.0)
        _mark_complete("analyze")

        # 5. Render
        _check_stop(job_id, deadline)
        _update(job_id, stage="tracking", progress=0.0)

        done_count = {"n": 0}
        count_lock = threading.Lock()

        def _render_one(i, clip):
            _check_stop(job_id, deadline)
            _update_clip(job_id, i, status="tracking")

            out_path = job_dir / f"clip_{i}.mp4"
            ass_path = job_dir / f"clip_{i}.ass"
            thumbnail_path = job_dir / f"clip_{i}.jpg"

            try:
                plan = cutter.plan_layout(
                    video["path"], clip["start"], clip["end"], job_id=job_id,
                )
                _check_stop(job_id, deadline)
                _update(job_id, stage="rendering")
                _update_clip(job_id, i, status="rendering")

                ass_path = captions.build_ass(
                    transcript["words"], clip["start"], clip["end"],
                    ass_path,
                    margin_v=plan["margin_v"],
                    top_text=job.get("top_text", ""),
                )

                cutter.render_clip(
                    video["path"], clip["start"], clip["end"],
                    ass_path, out_path, plan=plan, job_id=job_id,
                )
                _check_stop(job_id, deadline)

                # Post-render validation
                validation = _validate_output(out_path, job_id=job_id)
                if not validation["valid"]:
                    raise RuntimeError(f"Output validation failed: {validation['error']}")

                _build_thumbnail(out_path, validation["duration"], thumbnail_path, job_id=job_id)

                caption_words = [
                    word for word in transcript["words"]
                    if word["end"] > clip["start"] and word["start"] < clip["end"]
                ]

                _update_clip(
                    job_id, i, status="done",
                    file=str(out_path), layout=plan["mode"],
                    thumbnail=str(thumbnail_path),
                    ass_file=str(ass_path),
                    duration=validation["duration"],
                    requested_duration=round(clip["end"] - clip["start"], 3),
                    validation=validation,
                    render_plan=plan,
                    caption_words=caption_words,
                )
                ok = True

            except Exception as clip_err:
                # A cancellation/timeout must abort the whole job, not just
                # mark this clip failed (which would end in "error").
                ev = _cancel_events.get(job_id)
                if (ev and ev.is_set()) or isinstance(clip_err, JobTimeoutError):
                    raise
                out_path.unlink(missing_ok=True)
                _update_clip(job_id, i, status="failed", error=str(clip_err)[:300])
                ok = False

            with count_lock:
                done_count["n"] += 1
                _update(job_id, progress=done_count["n"] / len(clips))

            return ok

        with _timed("render"):
            with ThreadPoolExecutor(
                max_workers=config.RENDER_WORKERS
            ) as pool:
                results = list(
                    pool.map(
                        lambda ic: _render_one(*ic),
                        enumerate(clips),
                    )
                )

        if not any(results):
            raise RuntimeError(
                "All clips failed to render. Check ffmpeg on this machine.",
            )

        _mark_complete("render")
        # Cancellation wins over completion: never commit a "done" job the
        # user already cancelled.
        _check_stop(job_id, deadline)
        _update(job_id, stage="finalizing", progress=1.0)
        _check_stop(job_id, deadline)
        _update(job_id, stage="done", progress=1.0, completed_at=time.time())

    except Exception as e:
        traceback.print_exc()
        proc_mod.kill_job(job_id)
        # Cancellation wins even when the surfaced exception is a side effect
        # of the kill (e.g. RenderError from terminated ffmpeg): if the user
        # cancelled this job, the terminal state must be "cancelled".
        ev = _cancel_events.get(job_id)
        is_cancelled = bool(ev and ev.is_set()) or "cancelled" in str(e).lower()
        is_timeout = isinstance(e, JobTimeoutError)
        error_code = "CANCELLED" if is_cancelled else ("JOB_TIMEOUT" if is_timeout else _classify_error(str(e)))
        stage = "cancelled" if is_cancelled else "error"
        terminal_ts = {
            "cancelled_at": time.time() if is_cancelled else None,
            "failed_at": time.time() if not is_cancelled else None,
        }
        terminal_ts = {k: v for k, v in terminal_ts.items() if v is not None}
        try:
            _update(job_id, stage=stage, error=str(e), error_code=error_code, **terminal_ts)
        except Exception:
            # Task 10: a persistence failure must not prevent the refund or
            # crash the worker thread; the in-memory state is already terminal.
            logging.getLogger(__name__).warning(
                "terminal state persist failed for job %s", job_id, exc_info=True)

        # Refund credits on failure (not on cancellation — user chose that)
        if not is_cancelled and job.get("user_id"):
            try:
                credits_mod.refund(
                    job["user_id"],
                    credits_mod.COST_PER_FORGE,
                    related_id=job_id,
                    reason=f"Pipeline failed ({error_code}) — refund",
                )
            except Exception:
                pass  # Best-effort; log but don't crash


_maintenance_started = False


def _run_maintenance():
    """Periodic housekeeping: prune stale sessions, idempotency records,
    finished cancel-events and dead subprocess handles.  Runs in the
    background; safe to call from a daemon thread."""
    # Sleep BEFORE the first pass so we never fire writes during startup
    # (or during test fixture setup right after import).
    interval = max(60, config.MAINTENANCE_INTERVAL_SECONDS)
    time.sleep(interval)
    while True:
        try:
            db.cleanup_expired_sessions()
            with _lock:
                active_ids = set(JOBS.keys())
            db.cleanup_old_idempotency(active_job_ids=active_ids)
        except Exception:
            logging.getLogger(__name__).warning("maintenance db cleanup failed", exc_info=True)
        try:
            with _lock:
                stale = [jid for jid, ev in _cancel_events.items()
                         if ev.is_set() and jid not in JOBS]
                for jid in stale:
                    _cancel_events.pop(jid, None)
                for jid in list(_cancel_events.keys()):
                    proc_mod.prune(jid)
        except Exception:
            logging.getLogger(__name__).warning("maintenance in-memory cleanup failed", exc_info=True)
        time.sleep(interval)


def start_maintenance():
    """Start the background maintenance thread once (idempotent).

    Disabled when CLPZ_DISABLE_MAINTENANCE=1 (used by the test suite so
    background writes never contend with test fixture DB access).
    """
    global _maintenance_started
    if _maintenance_started:
        return
    if os.environ.get("CLPZ_DISABLE_MAINTENANCE") == "1":
        return
    _maintenance_started = True
    t = threading.Thread(target=_run_maintenance, daemon=True, name="clpz-maintenance")
    t.start()


def clip_path(job_id: str, index: int) -> Path | None:
    job = get_job(job_id)

    if not job:
        return None

    for c in job["clips"]:
        if c["index"] == index and c["file"]:
            p = Path(c["file"])
            if p.exists():
                return p
            # Try relative to the job directory
            job_dir = Path(config.DATA_DIR) / job_id
            alt = job_dir / f"clip_{index}.mp4"
            if alt.exists():
                return alt

    return None


def clip_thumbnail_path(job_id: str, index: int) -> Path | None:
    """Return the verified thumbnail for a rendered clip, when available."""
    job = get_job(job_id)
    if not job:
        return None

    for c in job.get("clips", []):
        if c.get("index") != index:
            continue
        thumbnail = c.get("thumbnail")
        if thumbnail:
            p = Path(thumbnail)
            if p.exists():
                return p
        fallback = config.DATA_DIR / job_id / f"clip_{index}.jpg"
        if fallback.exists():
            return fallback

    return None


def ensure_clip_metadata(job_id: str, index: int) -> dict | None:
    """Backfill legacy clip metadata from its already-rendered MP4 once.

    Early CLPZ jobs saved only a nested duration result.  This function is
    intentionally idempotent: it validates and thumbnails an old output once,
    persists the richer record, then future reads are cheap.
    """
    job = get_job(job_id)
    if not job:
        return None
    clip = next((c for c in job.get("clips", []) if c.get("index") == index), None)
    if not clip or clip.get("status") != "done":
        return clip

    path = clip_path(job_id, index)
    if not path:
        return clip

    validation = clip.get("validation") or {}
    validation_fields = {"duration", "width", "height", "video_codec", "audio_codec", "decoded_frame"}
    updates: dict = {}
    if not validation_fields.issubset(validation):
        refreshed = _validate_output(path)
        if refreshed.get("valid"):
            validation = refreshed
            updates["validation"] = validation

    if validation.get("valid") and clip.get("duration") is None:
        updates["duration"] = validation["duration"]
    if clip.get("requested_duration") is None:
        updates["requested_duration"] = round(clip.get("end", 0) - clip.get("start", 0), 3)
    if not clip.get("id"):
        updates["id"] = f"{job_id}-clip-{index}"

    thumbnail = clip_thumbnail_path(job_id, index)
    if thumbnail is None and validation.get("valid"):
        try:
            thumbnail = _build_thumbnail(
                path,
                validation["duration"],
                config.DATA_DIR / job_id / f"clip_{index}.jpg",
            )
        except Exception:
            thumbnail = None
    if thumbnail is not None and clip.get("thumbnail") != str(thumbnail):
        updates["thumbnail"] = str(thumbnail)

    if updates:
        _update_clip(job_id, index, **updates)
        clip.update(updates)
    return clip
