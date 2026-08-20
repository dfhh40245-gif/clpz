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
import subprocess
import struct
import tempfile
import threading
from pathlib import Path

import numpy as np

import config

_model = None
_model_lock = threading.Lock()

# Chunk length for long videos (seconds).  Matches Whisper's default.
_CHUNK_SECONDS = 30
# Overlap to avoid cutting words at chunk boundaries (seconds).
_OVERLAP_SECONDS = 2
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

        _model = WhisperModel(
            config.WHISPER_MODEL,
            device=device,
            compute_type=compute,
        )

        return _model


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


def _get_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            _find_bin("ffprobe"),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _extract_audio_chunk(
    video_path: str, start_sec: float, end_sec: float
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
    proc = subprocess.run(
        cmd, capture_output=True, timeout=120,
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


def _transcribe_chunk(model, audio: np.ndarray, offset: float, task: str) -> dict:
    """Transcribe a single audio chunk and return raw results."""
    if len(audio) == 0:
        return {"segments": [], "words": []}

    seg_iter, info = model.transcribe(
        audio,
        task=task,
        word_timestamps=True,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        temperature=0,
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

    return {"segments": segments, "words": words}


def _merge_chunks(
    chunk_results: list[dict],
    total_duration: float,
) -> dict:
    """Merge chunked transcription results into a single transcript.

    Deduplicates overlapping words at chunk boundaries by checking if
    the same word text appears within 0.3s of the same timestamp.
    """
    all_segments = []
    all_words = []
    language = "unknown"

    for i, chunk in enumerate(chunk_results):
        if not chunk["segments"]:
            continue
        # Use the first chunk's language detection
        if i == 0:
            language = chunk.get("language", "unknown")
        all_segments.extend(chunk["segments"])
        all_words.extend(chunk["words"])

    # Deduplicate words at chunk boundaries
    if all_words:
        deduped = [all_words[0]]
        for w in all_words[1:]:
            prev = deduped[-1]
            # Skip if same word text within 0.3s of the same position
            if (
                w["word"].lower() == prev["word"].lower()
                and abs(w["start"] - prev["start"]) < 0.3
            ):
                continue
            deduped.append(w)
        all_words = deduped

    # Sort by start time
    all_segments.sort(key=lambda s: s["start"])
    all_words.sort(key=lambda w: w["start"])

    return {
        "language": language,
        "segments": all_segments,
        "words": all_words,
    }


def transcribe(video_path: str, progress_cb=None, job_dir: str | Path | None = None) -> dict:
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
    duration = _get_duration(video_path)

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

        for i, (chunk_start, chunk_end) in enumerate(chunks):
            audio = _extract_audio_chunk(
                video_path, chunk_start, chunk_end
            )

            chunk_result = _transcribe_chunk(
                model, audio, chunk_start, task
            )
            chunk_result["language"] = "unknown"
            chunk_results.append(chunk_result)

            # Free audio memory immediately
            del audio
            gc.collect()

            if progress_cb:
                progress_cb((i + 1) / total_chunks)

        result = _merge_chunks(chunk_results, duration)

    # Save transcript files to job directory
    if job_dir is not None:
        job_dir = Path(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        _write_srt(result["segments"], job_dir / "transcript.srt")
        _write_words(result["words"], job_dir / "words.json")

    return result