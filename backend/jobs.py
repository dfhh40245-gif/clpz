"""Job manager. Each job runs the full pipeline in a worker thread.
State is mirrored to data/<job_id>/job.json so finished jobs survive restarts
(a job mid-run when the server dies is marked as interrupted on reload).
"""
from __future__ import annotations

import copy
import json
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

# Heavy stages (download/transcribe/render) saturate the machine, so jobs
# beyond this limit wait in "queued" until a slot frees up.
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
_slots = threading.Semaphore(MAX_CONCURRENT_JOBS)


def _check_cancelled(job_id: str):
    """Raise if this job has been cancelled."""
    ev = _cancel_events.get(job_id)
    if ev and ev.is_set():
        raise RuntimeError("Job cancelled by user.")


def cancel_job(job_id: str) -> bool:
    """Cancel a running or queued job. Returns True if cancelled."""
    with _lock:
        job = JOBS.get(job_id)
        if not job:
            return False
        if job.get("stage") in ("done", "error", "cancelled"):
            return False
        ev = _cancel_events.get(job_id)
        if ev:
            ev.set()
        _update_no_lock(job_id, stage="cancelled", error="Cancelled by user.", cancelled_at=time.time())
    return True


def _update_no_lock(job_id: str, **kwargs):
    """Update job state without acquiring the lock (caller must hold it)."""
    JOBS[job_id].update(kwargs)
    _persist(JOBS[job_id])


def _update(job_id: str, **kwargs):
    with _lock:
        JOBS[job_id].update(kwargs)
        _persist(JOBS[job_id])


def _persist(job: dict):
    try:
        d = config.DATA_DIR / job["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "job.json").write_text(json.dumps(job), encoding="utf-8")
    except OSError:
        pass
    # Also persist to SQLite for reliability
    try:
        db.save_job(job)
    except Exception:
        pass


def _validate_output(path: Path) -> dict:
    """Validate a rendered clip using ffprobe and a real decode pass.

    ``format.duration`` is deliberately treated as the authoritative duration:
    the requested transcript range is useful provenance, but frame boundaries
    mean it is not necessarily the duration of the encoded MP4.
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
        proc = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,duration,width,height,pix_fmt",
                "-show_entries", "format=duration,size",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=30,
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
        if audio_codec != "aac":
            result["error"] = f"Unexpected audio codec: {audio_codec or 'unknown'}."
            return result

        # ffprobe only inspects container metadata. Decode one video frame as a
        # final guard against a corrupt stream that happens to have a valid MOOV.
        decode = subprocess.run(
            [
                _find_bin("ffmpeg"), "-v", "error", "-i", str(path),
                "-map", "0:v:0", "-frames:v", "1", "-f", "null", os.devnull,
            ],
            capture_output=True,
            text=True,
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


def _build_thumbnail(path: Path, duration: float, out_path: Path) -> Path:
    """Create a compact, real preview image from the rendered clip."""
    timestamp = max(0.0, min(duration * 0.45, max(0.0, duration - 0.1)))
    proc = subprocess.run(
        [
            _find_bin("ffmpeg"), "-y", "-v", "error",
            "-ss", f"{timestamp:.3f}", "-i", str(path),
            "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", str(out_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Thumbnail generation failed.")
    return out_path


def load_saved_jobs():
    """Called at startup: restore finished/errored jobs from disk and SQLite."""
    # Load from JSON files on disk
    for f in config.DATA_DIR.glob("*/job.json"):
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if job.get("stage") not in ("done", "error"):
            job["stage"] = "error"
            job["error"] = (
                "Server restarted while this job was running. "
                "Submit it again."
            )

        with _lock:
            JOBS.setdefault(job["id"], job)

    # Also load any jobs from SQLite that aren't already loaded
    try:
        all_db_jobs = db.get_all_jobs()
        for job in all_db_jobs:
            if job.get("stage") not in ("done", "error"):
                job["stage"] = "error"
                job["error"] = (
                    "Server restarted while this job was running. "
                    "Submit it again."
                )
            with _lock:
                if job["id"] not in JOBS:
                    JOBS[job["id"]] = job
                    # Also write JSON file for backward compatibility
                    try:
                        d = config.DATA_DIR / job["id"]
                        d.mkdir(parents=True, exist_ok=True)
                        (d / "job.json").write_text(json.dumps(job), encoding="utf-8")
                    except OSError:
                        pass
    except Exception:
        pass

    # Never silently delete a user's rendered projects on server startup.
    # Retention can be explicitly enabled in configuration.
    if config.AUTO_CLEANUP_HOURS > 0:
        _cleanup_old_jobs(max_age_hours=config.AUTO_CLEANUP_HOURS)


def reset_for_testing():
    """Reset all in-memory job state. For test isolation only."""
    global JOBS, _slots
    with _lock:
        JOBS.clear()
    # Recreate semaphore to reset slots
    _slots = threading.Semaphore(MAX_CONCURRENT_JOBS)


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
                shutil.rmtree(job_dir)
                with _lock:
                    JOBS.pop(job_id, None)
                removed += 1
            except Exception:
                pass

    if removed:
        print(f"[cleanup] Removed {removed} old jobs (>{max_age_hours}h)")


def create_job(url: str, max_clips: int, top_text: str = "", user_id: str | None = None) -> str:
    job_id = uuid.uuid4().hex[:12]
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


def create_upload_job(filename: str, max_clips: int, top_text: str = "", user_id: str | None = None) -> str:
    """Create a job for a locally uploaded video."""
    job_id = uuid.uuid4().hex[:12]
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
    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    import subprocess

    try:
        result = subprocess.run(
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
            capture_output=True,
            text=True,
            check=True,
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
        for c in JOBS[job_id]["clips"]:
            if c["index"] == index:
                c.update(kwargs)

        _persist(JOBS[job_id])


def _run(job_id: str):
    with _slots:
        _run_pipeline(job_id)


def _run_pipeline(job_id: str):
    job = get_job(job_id)
    job_dir = config.DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Mark the authoritative start time
    _update(job_id, started_at=time.time())

    # Check disk space — need at least 2GB free for a typical job
    try:
        import psutil
        disk = psutil.disk_usage(str(config.DATA_DIR))
        if disk.free < 2 * 1024**3:  # 2 GB
            _update(job_id, stage="error", error="Not enough disk space. Need at least 2 GB free.", error_code="DISK_FULL", failed_at=time.time())
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
            _check_cancelled(job_id)
            _update(job_id, stage="downloading", progress=0.0)

            with _timed("download"):
                video = downloader.download(
                    job["url"], job_dir,
                )

            _update(job_id, video=video, progress=1.0)
        _mark_complete("download")

        # 2. Transcribe (skip if SRT already exists)
        srt_path = job_dir / "transcript.srt"
        words_path = job_dir / "words.json"

        if "transcribe" in completed_stages and srt_path.exists():
            pass  # Already transcribed
        else:
            _check_cancelled(job_id)
            _update(job_id, stage="transcribing", progress=0.0)

            try:
                with _timed("transcribe"):
                    raw_transcript = transcriber.transcribe(
                        video["path"],
                        progress_cb=lambda p: _update(job_id, progress=p),
                        job_dir=job_dir,
                    )
            except Exception as e:
                raise RuntimeError(f"Transcription failed: {e}") from e
        _mark_complete("transcribe")

        # 3. Parse (skip if already parsed and clips exist)
        if not srt_path.exists():
            raise RuntimeError("Transcription produced no SRT file.")

        if "parse" in completed_stages and "analyze" in completed_stages:
            pass  # Already parsed and analyzed
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
        _check_cancelled(job_id)
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
        _check_cancelled(job_id)
        _update(job_id, stage="tracking", progress=0.0)

        done_count = {"n": 0}
        count_lock = threading.Lock()

        def _render_one(i, clip):
            _check_cancelled(job_id)
            _update_clip(job_id, i, status="tracking")

            out_path = job_dir / f"clip_{i}.mp4"
            ass_path = job_dir / f"clip_{i}.ass"
            thumbnail_path = job_dir / f"clip_{i}.jpg"

            try:
                plan = cutter.plan_layout(video["path"], clip["start"], clip["end"])
                _check_cancelled(job_id)
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
                    ass_path, out_path, plan=plan,
                )

                # Post-render validation
                validation = _validate_output(out_path)
                if not validation["valid"]:
                    raise RuntimeError(f"Output validation failed: {validation['error']}")

                _build_thumbnail(out_path, validation["duration"], thumbnail_path)

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
        _update(job_id, stage="finalizing", progress=1.0)
        _update(job_id, stage="done", progress=1.0, completed_at=time.time())

    except Exception as e:
        traceback.print_exc()
        is_cancelled = "cancelled" in str(e).lower()
        error_code = "CANCELLED" if is_cancelled else _classify_error(str(e))
        stage = "cancelled" if is_cancelled else "error"
        terminal_ts = {
            "cancelled_at": time.time() if is_cancelled else None,
            "failed_at": time.time() if not is_cancelled else None,
        }
        terminal_ts = {k: v for k, v in terminal_ts.items() if v is not None}
        _update(job_id, stage=stage, error=str(e), error_code=error_code, **terminal_ts)

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
