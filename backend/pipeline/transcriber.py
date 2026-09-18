"""Step 2 — transcribe with faster-whisper, word-level timestamps.

Outputs:
- In-memory dict: {language, segments, words}
- On disk: transcript.srt + words.json (inside the job directory)

For long videos, audio is processed in 30-second chunks to avoid loading
the entire waveform into a single giant NumPy array (which causes an
841 MiB complex128 STFT allocation failure on 8 GB machines)."""
from __future__ import annotations

import gc
import io
import json
import math
import os
import subprocess
import struct
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import numpy as np

import config
import proc as proc_mod

_model = None
_model_lock = threading.Lock()

# Chunk length for long videos (seconds).  Matches Whisper's default.
_CHUNK_SECONDS = 30
# Overlap to avoid cutting words at chunk boundaries (seconds).
_OVERLAP_SECONDS = 2
# Two word entries whose midpoints are closer than this are considered the
# same transcription of one token when their text matches (overlap dedupe).
_OVERLAP_DEDUPE_WINDOW = 0.6
# Audio parameters.
_SAMPLE_RATE = 16000
# Threshold: videos longer than this use chunked processing.
_CHUNKED_THRESHOLD = 120  # 2 minutes


def _get_model():
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        from faster_whisper import WhisperModel

        device = config.WHISPER_DEVICE
        compute = config.WHISPER_COMPUTE

        # Packaged app: use the bundled model dir when present so the app
        # works fully offline (falls back to hub download in dev).
        model_ref = config.WHISPER_MODEL
        bundled = os.environ.get("CLIPFORGE_MODEL_DIR", "")
        if bundled:
            bundled_path = Path(bundled)
            # Layout A: flat dir (model.bin directly inside)
            # Layout B: HF hub cache snapshot dir
            if (bundled_path / "model.bin").exists():
                model_ref = str(bundled_path)
            else:
                snap = bundled_path / f"models--Systran--faster-whisper-{model_ref}" / "snapshots"
                if snap.exists():
                    snaps = sorted(snap.glob("*"))
                    if snaps:
                        model_ref = str(snaps[0].resolve())

        if device == "auto":
            try:
                import ctranslate2

                device = (
                    "cuda"
                    if ctranslate2.get_cuda_device_count() > 0
                    else "cpu"
                )
            except Exception:
                device = "cpu"

        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"

        # ctranslate2's MKL allocator can fail transiently under memory
        # pressure (mkl_malloc: failed to allocate memory).  Retry a few
        # times with a short backoff; a one-off hiccup must not fail the job.
        last_err = None
        for attempt in range(3):
            try:
                _model = WhisperModel(
                    model_ref,
                    device=device,
                    compute_type=compute,
                )
                return _model
            except Exception as e:
                last_err = e
                if "mkl_malloc" in str(e) and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        raise last_err


def _find_bin(name: str) -> str:
    """Find a binary, checking backend/bin first."""
    import shutil
    found = shutil.which(name)
    if found:
        return found
    # Try backend/bin relative to this file
    candidate = Path(__file__).resolve().parent.parent / "bin" / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError(f"{name} not found on PATH or in backend/bin")


def _get_duration(video_path: str, job_id: str = "") -> float:
    """Get video duration in seconds using ffprobe.

    Task 11: routed through proc.py so the child is registered against the
    job and is terminated on cancellation/shutdown instead of running on
    as an untracked process.
    """
    result = proc_mod.run(
        job_id,
        [
            _find_bin("ffprobe"),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        timeout=30,
    )
    return float(result.stdout.strip())


def _extract_audio_chunk(
    video_path: str, start_sec: float, end_sec: float, job_id: str = ""
) -> np.ndarray:
    """Extract a chunk of audio as float32 mono 16kHz numpy array.

    Uses ffmpeg to decode only the requested time range, keeping memory
    bounded regardless of total video length.
    """
    duration = end_sec - start_sec
    cmd = [
        _find_bin("ffmpeg"),
        "-y",
        "-ss", str(start_sec),
        "-t", str(duration),
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(_SAMPLE_RATE),
        "-ac", "1",
        "-f", "s16le",
        "pipe:1",
    ]
    # Task 11: registered subprocess (terminable on cancellation) with its
    # own bounded timeout so a wedged extraction cannot hang the worker.
    proc = proc_mod.run(
        job_id, cmd, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio extraction failed: {proc.stderr[-200:].decode(errors='replace')}"
        )
    raw = proc.stdout
    if not raw:
        return np.array([], dtype=np.float32)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def _fmt_srt_ts(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def _write_srt(segments: list[dict], path: Path) -> None:
    """Write segments to a standard SRT file."""
    lines = []
    for i, seg in enumerate(segments, 1):
        start_ts = _fmt_srt_ts(seg["start"])
        end_ts = _fmt_srt_ts(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start_ts} --> {end_ts}")
        lines.append(seg["text"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_words(words: list[dict], path: Path) -> None:
    """Write precise word timestamps to a JSON file."""
    path.write_text(json.dumps(words), encoding="utf-8")


def _transcribe_chunk(model, audio: np.ndarray, offset: float, task: str,
                      language: str | None = None) -> dict:
    """Transcribe a single audio chunk and return raw results.

    ``language`` (task 07): carried through to the chunk result so the merged
    transcript reports the actually detected language instead of a hardcoded
    'unknown'.
    """
    if len(audio) == 0:
        return {"segments": [], "words": [], "language": language or "unknown"}

    transcribe_kwargs = dict(
        task=task,
        word_timestamps=True,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        temperature=0,
    )
    if language:
        transcribe_kwargs["language"] = language
    seg_iter, info = model.transcribe(
        audio,
        **transcribe_kwargs,
    )

    segments, words = [], []
    for seg in seg_iter:
        segments.append({
            "start": round(seg.start + offset, 3),
            "end": round(seg.end + offset, 3),
            "text": seg.text.strip(),
        })
        for w in seg.words or []:
            words.append({
                "start": round(w.start + offset, 3),
                "end": round(w.end + offset, 3),
                "word": w.word.strip(),
            })

    # Validate every word/segment entry, not only the first (task 07):
    # malformed later entries (NaN, reverse timing) are dropped rather than
    # corrupting the merged transcript.
    segments = _validate_timed_entries(segments)
    words = _validate_timed_entries(words)

    return {"segments": segments, "words": words,
            "language": getattr(info, "language", language or "unknown")}


def _validate_timed_entries(entries: list[dict]) -> list[dict]:
    """Keep only finite, ordered, nonnegative-duration entries (task 07)."""
    clean = []
    for e in entries:
        try:
            start = float(e.get("start"))
            end = float(e.get("end"))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(start) and math.isfinite(end)):
            continue
        if start < 0 or end < start:
            continue
        text = e.get("word", e.get("text", ""))
        if not isinstance(text, str) or not text.strip():
            continue
        clean.append(e)
    return clean


def _merge_chunks(
    chunk_results: list[dict],
    total_duration: float,
) -> dict:
    """Merge chunked transcription results into a single transcript.

    Task 07: overlapping chunk intervals are reconciled by *interval*, not by
    a global same-text heuristic. Within the overlap region between
    consecutive chunks, duplicate words (same normalized text within a small
    time window) are collapsed to one copy; genuine repeated speech outside
    the overlap windows is preserved verbatim. Language metadata is carried
    from the first chunk that provides it instead of being dropped.
    """
    all_segments = []
    all_words = []
    language = "unknown"

    # Collect per-chunk overlap windows (chunk i and i+1 share
    # [end_i - overlap, end_i] when the chunker used overlap; reconstructed
    # here from the data itself: words whose times appear in both chunks).
    for i, chunk in enumerate(chunk_results):
        if language == "unknown":
            language = chunk.get("language", "unknown") or "unknown"
        all_segments.extend(chunk.get("segments", []))
        all_words.extend(chunk.get("words", []))

    all_segments = _validate_timed_entries(all_segments)
    all_words = _validate_timed_entries(all_words)

    # Sort by start time before reconciliation
    all_segments.sort(key=lambda s: (s["start"], s["end"]))
    all_words.sort(key=lambda w: (w["start"], w["end"]))

    # Overlap reconciliation: collapse near-identical duplicates that occur
    # when two chunks transcribed the same audio region. Two words are the
    # same copy when text matches (case/punctuation-insensitive) AND their
    # midpoints are within _OVERLAP_DEDUPE_WINDOW seconds. Genuine repeats
    # (deliberately repeated words) are usually separated by more time or by
    # intervening words, so they survive.
    if all_words:
        deduped = [all_words[0]]
        for w in all_words[1:]:
            prev = deduped[-1]
            if _same_transcribed_copy(w, prev):
                # Keep the earlier copy; extend nothing (timings are absolute).
                continue
            deduped.append(w)
        all_words = deduped

    # Segments: dedupe identical spans produced by two chunks (same text and
    # near-identical timing), which otherwise duplicate caption lines.
    if all_segments:
        seg_deduped = [all_segments[0]]
        for s in all_segments[1:]:
            prev = seg_deduped[-1]
            if (
                s["text"].strip().lower() == prev["text"].strip().lower()
                and abs(s["start"] - prev["start"]) < 0.4
                and abs(s["end"] - prev["end"]) < 0.4
            ):
                continue
            seg_deduped.append(s)
        all_segments = seg_deduped

    # Clamp to source bounds and keep ordering
    if total_duration and total_duration > 0:
        all_segments = [s for s in all_segments if s["start"] < total_duration]
        all_words = [w for w in all_words if w["start"] < total_duration]

    return {
        "language": language,
        "segments": all_segments,
        "words": all_words,
    }


def _same_transcribed_copy(a: dict, b: dict) -> bool:
    """True when two word entries are the same transcription of one spoken
    token (duplicate from an overlapping chunk), not genuine repeated speech."""
    def _norm(t: str) -> str:
        return "".join(ch for ch in t.lower() if ch.isalnum())
    na, nb = _norm(a.get("word", "")), _norm(b.get("word", ""))
    if not na or na != nb:
        return False
    mid_a = (a["start"] + a["end"]) / 2.0
    mid_b = (b["start"] + b["end"]) / 2.0
    return abs(mid_a - mid_b) < _OVERLAP_DEDUPE_WINDOW


# ── R02: supervised (cancellable) transcription boundary ────────────

# The child inherits the FULL parent environment (home, PATH, SYSTEMROOT and
# friends are needed by config.py's Path.home(), shutil.which and Python
# itself). These keys are additionally ensured/overridden below:
#   CLIPFORGE_MODEL_DIR — kept if set, else "" so job_dir is never mistaken
#                         for a bundled-model directory by the child.
#   CLPZ_TRANSCRIBE_CHILD — "1", diagnostic marker (also used by tests).
#   PYTHONPATH — backend dir prepended so `import config` resolves in dev.
_CHILD_ENV_SENTINEL = "CLPZ_TRANSCRIBE_CHILD"


class TranscribeTimeoutError(RuntimeError):
    """Raised when supervised transcription exceeds its hard deadline (R02).

    The child process is force-terminated before this is raised; the job
    layer maps it to the TRANSCRIBE_TIMEOUT error code.
    """


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort force-kill of the supervised child (R02).

    The child is a single-purpose interpreter; terminate() is normally
    sufficient (on Windows it is TerminateProcess). kill() is the fallback
    for platforms where terminate() is a SIGTERM the child could ignore.
    Never raises: a failed kill must not mask the original deadline error.
    """
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass


def _relay_progress(progress_path: Path, progress_cb) -> None:
    """Forward the child's latest progress sample to the job callback."""
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
        p = float(data.get("progress", 0.0))
    except (OSError, ValueError, AttributeError):
        return
    if p > 0:
        progress_cb(min(p, 1.0))


def _child_main():
    """Entry point for the supervised transcription child process.

    Rebuilds config from the environment (config.py reads os.getenv at
    import), runs one transcription, serializes the result to a JSON file and
    exits 0. Any failure exits non-zero with the message in --err. Failure to
    even import/parse arguments is reported via the JSON file or stderr.
    """
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--err", required=True)
    args = parser.parse_args()

    try:
        from pipeline import transcriber as _t  # imports config

        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        video_path = payload["video_path"]
        job_dir = payload.get("job_dir") or None
        progress_path = payload.get("progress_path")

        last_progress = [0.0]

        def _progress(p: float) -> None:
            last_progress[0] = max(last_progress[0], p)
            if progress_path:
                try:
                    Path(progress_path).write_text(
                        json.dumps({"progress": last_progress[0]}),
                        encoding="utf-8")
                except OSError:
                    pass  # progress reporting is best-effort

        result = _t.transcribe(
            video_path,
            progress_cb=_progress,
            job_dir=job_dir,
            job_id=payload.get("job_id", ""),
        )
        Path(args.result).write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8")
        sys.exit(0)
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001 — report everything to the parent
        try:
            Path(args.err).write_text(
                f"{type(e).__name__}: {e}", encoding="utf-8")
        except OSError:
            pass
        sys.exit(1)


def _child_command(script: str, payload_path: Path, result_path: Path,
                   err_path: Path) -> list[str]:
    """Command line for one supervised transcription child.

    A separate function (not inlined) so the hermetic test suite can redirect
    the child to a controlled script while the parent-side supervision loop,
    deadline and kill logic stay exactly as in production.
    """
    return [
        sys.executable, script,
        "--payload", str(payload_path),
        "--result", str(result_path),
        "--err", str(err_path),
    ]


def _payload_paths(job_id: str):
    """Dedicated exchange directory for the supervised child's files.

    Kept out of the job directory (which backs up projects and must contain
    only durable artifacts) and out of the data root (support bundles).
    """
    base = Path(tempfile.gettempdir()) / "clpz-transcribe-supervision"
    base.mkdir(parents=True, exist_ok=True)
    prefix = f"{job_id or 'job'}-{uuid.uuid4().hex[:8]}-"
    return base, prefix


def _cleanup_paths(base, prefix):
    """Remove the supervision exchange files (payload/result/err/progress)."""
    import glob as _glob
    for f in _glob.glob(str(base / f"{prefix}*")):
        try:
            Path(f).unlink(missing_ok=True)
        except OSError:
            pass


def _supervised_transcribe(video_path, job_dir, job_id, progress_cb=None) -> dict:
    """Run one transcription in a supervised child process (R02).

    The child is a ``spawn``-ed interpreter running pipeline.transcriber as
    __main__, so a hung Whisper model does not hang the worker thread: at the
    deadline the child is force-terminated and TRANSCRIBE_TIMEOUT is raised.
    The parent never loads the model, so the worker stays responsive.
    """
    import uuid

    base, prefix = _payload_paths(job_id)
    payload_path = base / f"{prefix}payload.json"
    result_path = base / f"{prefix}result.json"
    err_path = base / f"{prefix}err.txt"
    progress_path = base / f"{prefix}progress.json"

    try:
        payload = {
            "video_path": str(video_path),
            "job_dir": str(job_dir) if job_dir is not None else None,
            "job_id": job_id,
            "progress_path": str(progress_path),
        }
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        child_env = os.environ.copy()
        child_env.setdefault("CLIPFORGE_MODEL_DIR", "")
        child_env[_CHILD_ENV_SENTINEL] = "1"
        backend_dir = str(Path(__file__).resolve().parent.parent)
        py_path = child_env.get("PYTHONPATH")
        child_env["PYTHONPATH"] = backend_dir + (
            (os.pathsep + py_path) if py_path else "")

        proc = subprocess.Popen(
            _child_command(__file__, payload_path, result_path, err_path),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as e:
        _cleanup_paths(base, prefix)
        raise RuntimeError(f"Transcription supervisor failed to start: {e}") from e

    deadline = time.monotonic() + config.TRANSCRIBE_DEADLINE_SECONDS
    timed_out = False
    try:
        while True:
            try:
                proc.wait(timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                pass
            if progress_cb is not None:
                _relay_progress(progress_path, progress_cb)
            if time.monotonic() > deadline:
                timed_out = True
                break
    except BaseException:
        # Parent interrupted (shutdown): kill the child and re-raise.
        _kill_process_tree(proc)
        _cleanup_paths(base, prefix)
        raise

    if timed_out:
        _kill_process_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        _cleanup_paths(base, prefix)
        raise TranscribeTimeoutError(
            f"Transcription exceeded its hard deadline of "
            f"{config.TRANSCRIBE_DEADLINE_SECONDS:.0f}s and was terminated."
        )

    if proc.returncode != 0:
        err_text = ""
        try:
            err_text = err_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        _cleanup_paths(base, prefix)
        if not err_text:
            err_text = f"transcription child exited with code {proc.returncode}"
        raise RuntimeError(f"Transcription failed: {err_text}")

    try:
        raw = result_path.read_text(encoding="utf-8")
    except OSError as e:
        _cleanup_paths(base, prefix)
        raise RuntimeError(
            "Transcription child exited successfully but produced no result.") from e
    result = json.loads(raw)
    _cleanup_paths(base, prefix)
    return result


def transcribe_supervised(video_path, progress_cb=None, job_dir=None,
                          job_id: str = "") -> dict:
    """``transcribe`` with a hard, enforceable deadline (R02).

    In supervised mode the call runs in a spawned child process which the
    parent force-terminates at ``TRANSCRIBE_DEADLINE_SECONDS`` — a hung model
    can no longer hold a worker slot indefinitely. When supervision is
    disabled (TRANSCRIBE_SUPERVISED=0), falls back to the legacy in-process
    ``transcribe`` so existing in-process test stubs keep working.
    """
    if getattr(config, "TRANSCRIBE_SUPERVISED", False):
        return _supervised_transcribe(video_path, job_dir, job_id,
                                      progress_cb=progress_cb)
    return transcribe(video_path, progress_cb=progress_cb, job_dir=job_dir,
                      job_id=job_id)


def transcribe(video_path: str, progress_cb=None, job_dir: str | Path | None = None,
               job_id: str = "") -> dict:
    """Transcribe a video and save transcript files.

    For short videos (< 2 min), the entire audio is processed at once.
    For longer videos, audio is extracted in 30-second chunks with 2-second
    overlap to keep memory usage bounded.

    Args:
        video_path: Path to the video file.
        progress_cb: Optional callback(progress: float) for progress updates.
        job_dir: If provided, saves transcript.srt and words.json here.

    Returns:
        {"language": str, "segments": [...], "words": [...]}

        segments: [{start, end, text}]
        words:    [{start, end, word}]
    """
    model = _get_model()

    task = (
        config.WHISPER_TASK
        if config.WHISPER_TASK in ("transcribe", "translate")
        else "transcribe"
    )

    # Get total duration to decide chunking strategy
    duration = _get_duration(video_path, job_id=job_id)

    if duration <= _CHUNKED_THRESHOLD:
        # Short video: process all at once (fast, low memory overhead)
        seg_iter, info = model.transcribe(
            video_path,
            task=task,
            word_timestamps=True,
            vad_filter=True,
            beam_size=1,
            best_of=1,
            temperature=0,
        )

        segments, words = [], []
        total = info.duration or 1.0

        for seg in seg_iter:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })
            for w in seg.words or []:
                words.append({
                    "start": w.start,
                    "end": w.end,
                    "word": w.word.strip(),
                })
            if progress_cb:
                progress_cb(min(seg.end / total, 1.0))

        result = {
            "language": info.language,
            "segments": segments,
            "words": words,
        }
    else:
        # Long video: chunked processing to avoid memory explosion
        chunk_len = _CHUNK_SECONDS
        overlap = _OVERLAP_SECONDS
        step = chunk_len - overlap
        chunks = []
        start = 0.0
        while start < duration:
            end = min(start + chunk_len, duration)
            chunks.append((start, end))
            start += step

        total_chunks = len(chunks)
        chunk_results = []

        import threading as _threading
        chunk_lang_holder = _threading.Event()  # reuse .set()/.is_set() as a flag holder
        chunk_lang_holder.value = None  # detected language once known

        for i, (chunk_start, chunk_end) in enumerate(chunks):
            audio = _extract_audio_chunk(
                video_path, chunk_start, chunk_end, job_id=job_id
            )

            chunk_result = _transcribe_chunk(
                model, audio, chunk_start, task,
                language=chunk_lang_holder.value,
            )
            # Carry the first chunk's detected language through (task 07):
            # subsequent chunks pass it explicitly so Whisper does not
            # re-detect per chunk; the merged result reports a real language.
            if chunk_lang_holder.value is None:
                detected = chunk_result.get("language")
                if detected and detected != "unknown":
                    chunk_lang_holder.value = detected
            chunk_results.append(chunk_result)

            # Free audio memory immediately
            del audio
            gc.collect()

            if progress_cb:
                progress_cb((i + 1) / total_chunks)

        result = _merge_chunks(chunk_results, duration)

    if not result["segments"]:
        # Fail loudly here rather than writing an empty SRT whose parse error
        # misattributes the failure downstream ("SRT file is empty").
        raise RuntimeError(
            "No speech detected in this audio — Whisper produced no segments."
        )

    # Save transcript files to job directory
    if job_dir is not None:
        job_dir = Path(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        _write_srt(result["segments"], job_dir / "transcript.srt")
        _write_words(result["words"], job_dir / "words.json")

    return result


if __name__ == "__main__":
    # Spawned child entry point (R02): python transcriber.py --payload ...
    # runs exactly one supervised transcription and exits.
    _child_main()