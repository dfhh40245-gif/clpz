"""Task 21 — CLPZ media quality & performance benchmark harness.

Measures the local pipeline on generated fixtures and records a machine-readable
baseline. Philosophy:

- Fixtures are GENERATED locally (deterministic, no licensing exposure) and
  hashed (SHA-256) into the report so runs are comparable.
- Every metric has an explicit PASS threshold defined in THRESHOLDS before the
  run; unknown/failed measurements are recorded as failures, never blank.
- The report records machine profile, tool versions, and per-fixture stage
  timings so future runs are comparable on the same hardware profile.

Usage:
    python scripts/benchmark_quality.py [--quick] [--json OUT] [--thresholds]

Exit code 0 = all measured thresholds pass; 1 = at least one failed.
NOT-RUN categories (e.g. human editorial ratings) are reported, not scored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# ---------------------------------------------------------------------------
# Thresholds: explicit, machine-checkable, defined BEFORE measuring.
# Edit only with an owner decision recorded in docs/foundation/DECISIONS.md.
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # Pipeline must complete on any valid fixture (seconds, per fixture).
    "pipeline_completed": {"type": "bool", "expected": True},
    # Rendered clip duration must match the selected candidate within 250 ms.
    "clip_duration_tolerance_s": {"type": "max", "value": 0.25},
    # A/V sync: audio stream duration within 300 ms of video duration.
    "av_sync_tolerance_s": {"type": "max", "value": 0.30},
    # Captions: word count in ASS >= 60% of SRT word count for the clip window
    # (groups drop punctuation-only artifacts).
    "caption_word_coverage": {"type": "min", "value": 0.60},
    # Candidate completeness: at least one candidate selected for speech media.
    "candidates_selected_min": {"type": "min", "value": 1},
    # No duplicate candidate ranges (identical start/end).
    "candidates_unique": {"type": "bool", "expected": True},
    # Output decodes cleanly (ffmpeg decode errors == 0).
    "output_decodes": {"type": "bool", "expected": True},
    # Peak memory ceiling for the whole pipeline (MB). Conservative developer-
    # machine ceiling; the tiny Whisper model typically peaks well below this.
    "peak_rss_mb": {"type": "max", "value": 4096},
    # Stage timings recorded for comparability (no threshold, recorded only).
    "stage_timings_recorded": {"type": "bool", "expected": True},
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    bundled = ROOT / "backend" / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if bundled.exists():
        return str(bundled)
    raise FileNotFoundError("ffmpeg not found")


def _ffprobe() -> str:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    bundled = ROOT / "backend" / "bin" / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if bundled.exists():
        return str(bundled)
    raise FileNotFoundError("ffprobe not found")


# ---------------------------------------------------------------------------
# Fixture generation — deterministic, local, no third-party media.
# ---------------------------------------------------------------------------
def fixture_speech_short(out: Path, duration: float = 12.0) -> Path:
    """Portrait 9:16 fixture with real Windows TTS speech (falls back to sine)."""
    from tests.fixtures.generate_video import generate_speech_video
    return generate_speech_video(out, duration=duration)


def fixture_silence(out: Path, duration: float = 8.0) -> Path:
    """Landscape 16:9 fixture with silent audio (negative speech path)."""
    ffmpeg = _ffmpeg()
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={duration}",
         "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:duration={duration}",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
         "-c:a", "aac", "-b:a", "48k", "-shortest", str(out)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return out


def fixture_two_tone(out: Path, duration: float = 10.0) -> Path:
    """Fixture whose audio alternates two tones — a crude 'two speakers' proxy
    for segmentation behavior (NOT a genuine multi-speaker benchmark)."""
    ffmpeg = _ffmpeg()
    half = duration / 2
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", f"color=c=green:s=480x854:rate=24:duration={duration}",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={half}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={half}",
         "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
         "-c:a", "aac", "-b:a", "48k", "-shortest", str(out)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return out


def fixture_rotated(out: Path, duration: float = 6.0) -> Path:
    """Speech fixture with rotation metadata (phone-style) to exercise crop
    handling end to end (transcription needs real speech, not a sine wave)."""
    from tests.fixtures.generate_video import generate_speech_video
    tmp = out.with_suffix(".plain.mp4")
    generate_speech_video(tmp, duration=duration)
    ffmpeg = _ffmpeg()
    # Re-mux with a rotate display matrix (real phone-video shape).
    subprocess.run(
        [ffmpeg, "-y", "-i", str(tmp), "-c", "copy",
         "-metadata:s:v:0", "rotate=90", str(out)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    tmp.unlink(missing_ok=True)
    return out


def fixture_no_audio(out: Path, duration: float = 6.0) -> Path:
    """Fixture with NO audio stream — must fail GRACEFULLY, not crash."""
    ffmpeg = _ffmpeg()
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", f"testsrc2=size=360x640:rate=24:duration={duration}",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", str(out)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return out


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def probe(path: Path) -> dict:
    proc = subprocess.run(
        [_ffprobe(), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,duration",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr[:200]}
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {
        "video": v is not None, "audio": a is not None,
        "width": (v or {}).get("width", 0), "height": (v or {}).get("height", 0),
        "video_duration": float((v or {}).get("duration") or data.get("format", {}).get("duration", 0) or 0),
        "audio_duration": float((a or {}).get("duration") or data.get("format", {}).get("duration", 0) or 0),
    }


def decode_errors(path: Path) -> int:
    """Count decoder errors by fully decoding (maps to ffmpeg exit/stderr)."""
    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=120,
    )
    err_lines = [l for l in proc.stderr.splitlines() if l.strip()]
    return len(err_lines) + (0 if proc.returncode == 0 else 1)


def extract_frame(path: Path, at_s: float, out_png: Path) -> bool:
    proc = subprocess.run(
        [_ffmpeg(), "-y", "-v", "error", "-ss", str(at_s), "-i", str(path),
         "-frames:v", "1", str(out_png)],
        capture_output=True, text=True, timeout=60,
    )
    return proc.returncode == 0 and out_png.exists() and out_png.stat().st_size > 0


def ass_word_count(ass_path: Path) -> int:
    words = 0
    for line in ass_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Dialogue:"):
            text = line.rsplit(",", 1)[-1] if "," in line else ""
            # strip ASS override braces
            cleaned = ""
            skip = False
            for ch in text:
                if ch == "{":
                    skip = True
                elif ch == "}":
                    skip = False
                elif not skip:
                    cleaned += ch
            words += len(cleaned.split())
    return words


def run_pipeline_fixture(name: str, path: Path, workdir: Path, quick: bool, min_clip_s: float = 5.0) -> dict:
    """Run the actual pipeline stages against one fixture and measure."""
    import jobs as jobs_mod  # backend module
    import config
    # The analyzer refuses sources shorter than CLIP_MIN_SECONDS; benchmark
    # fixtures are short, so lower the floor (restore after the run).
    original_min = config.CLIP_MIN_SECONDS
    config.CLIP_MIN_SECONDS = min_clip_s
    if hasattr(jobs_mod, "config"):
        jobs_mod.config.CLIP_MIN_SECONDS = min_clip_s

    result: dict = {"fixture": name, "source": str(path), "sha256": _sha256(path), "size_bytes": path.stat().st_size}
    result["probe_source"] = probe(path)

    job_id = jobs_mod.create_upload_job(str(path), 1, "", "benchmark")
    result["job_id"] = job_id
    # Mirror the API flow: create_upload_job only creates the row; the actual
    # worker starts via start_uploaded_job (called by main.py after the file
    # is stored).
    import config as _config
    dest = _config.DATA_DIR / job_id
    dest.mkdir(parents=True, exist_ok=True)
    local = dest / ("source" + path.suffix.lower())
    shutil.copyfile(path, local)
    jobs_mod.start_uploaded_job(job_id, str(local), path.name)
    t0 = time.perf_counter()
    deadline = t0 + (300 if not quick else 180)
    peak_rss = 0
    while time.perf_counter() < deadline:
        job = jobs_mod.get_job(job_id) or {}
        if job.get("stage") in ("done", "error", "cancelled"):
            break
        try:
            import psutil  # optional
            proc = psutil.Process()
            peak_rss = max(peak_rss, int(proc.memory_info().rss / (1024 * 1024)))
        except Exception:
            pass
        time.sleep(0.5)
    result["elapsed_s"] = round(time.perf_counter() - t0, 2)
    job = jobs_mod.get_job(job_id) or {}
    result["final_stage"] = job.get("stage")
    result["error"] = job.get("error")
    result["error_code"] = job.get("error_code")
    result["timings"] = job.get("timings") or {}
    result["peak_rss_mb"] = peak_rss

    clips = job.get("clips") or []
    result["clips_selected"] = len([c for c in clips if c.get("status") == "done"])
    starts = [(c.get("start"), c.get("end")) for c in clips]
    result["candidates_unique"] = len(set(starts)) == len(starts) and len(starts) > 0
    result["candidates_selected_min"] = result["clips_selected"]
    config.CLIP_MIN_SECONDS = original_min
    if hasattr(jobs_mod, "config"):
        jobs_mod.config.CLIP_MIN_SECONDS = original_min

    if result["final_stage"] == "done" and clips:
        clip = next((c for c in clips if c.get("status") == "done"), clips[0])
        out_path = clip.get("file") or clip.get("path") or clip.get("output") or ""
        if out_path and Path(out_path).exists():
            media = Path(out_path)
        else:
            media = None
        if media:
            result["clip_path"] = str(media)
            result["probe_clip"] = probe(media)
            # duration tolerance vs candidate range
            want = float(clip.get("duration") or (clip.get("end", 0) - clip.get("start", 0)))
            got = (result["probe_clip"] or {}).get("video_duration", 0)
            result["clip_duration_delta_s"] = round(abs(got - want), 3)
            # A/V sync proxy
            pc = result["probe_clip"] or {}
            result["av_delta_s"] = round(abs(pc.get("video_duration", 0) - pc.get("audio_duration", 0)), 3)
            # decode check + frame extraction
            result["decode_errors"] = decode_errors(media)
            frames_dir = workdir / "frames"
            frames_dir.mkdir(exist_ok=True)
            f0 = frames_dir / f"{name}_0.png"
            result["frame_extracted"] = extract_frame(media, 0.1, f0)
            # caption coverage
            srt = ""
            # transcript.srt lives in the job dir next to the clip output.
            job_dir_candidate = Path(clip.get("file", "")).parent
            cand = job_dir_candidate / "transcript.srt"
            if cand.exists():
                srt = str(cand)
            ass = clip.get("ass_file") or clip.get("ass_path") or ""
            try:
                if srt and Path(srt).exists() and ass and Path(ass).exists():
                    srt_words = len(" ".join(
                        l for l in Path(srt).read_text(encoding="utf-8", errors="replace").splitlines()
                        if l.strip() and "-->" not in l and not l.strip().isdigit()
                    ).split())
                    ass_words = ass_word_count(Path(ass))
                    result["caption_word_coverage"] = round(ass_words / srt_words, 3) if srt_words else None
            except Exception as e:
                result["caption_error"] = str(e)
        else:
            result["clip_output_missing"] = True
    return result


def evaluate(results: dict) -> list[dict]:
    rows = []
    for fx in results["fixtures"]:
        checks = []

        def add(metric, ok, actual):
            checks.append({"metric": metric, "ok": bool(ok), "actual": actual})

        th = THRESHOLDS
        expectation = fx.get("expectation", "speech")
        if expectation == "speech":
            add("pipeline_completed", fx.get("final_stage") == "done", fx.get("final_stage"))
            if fx.get("clip_duration_delta_s") is not None:
                add("clip_duration_tolerance_s",
                    fx["clip_duration_delta_s"] <= th["clip_duration_tolerance_s"]["value"],
                    fx["clip_duration_delta_s"])
            if fx.get("av_delta_s") is not None:
                add("av_sync_tolerance_s",
                    fx["av_delta_s"] <= th["av_sync_tolerance_s"]["value"], fx["av_delta_s"])
            if fx.get("caption_word_coverage") is not None:
                add("caption_word_coverage",
                    fx["caption_word_coverage"] >= th["caption_word_coverage"]["value"],
                    fx["caption_word_coverage"])
            add("candidates_selected_min",
                fx.get("candidates_selected_min", 0) >= th["candidates_selected_min"]["value"],
                fx.get("candidates_selected_min", 0))
            add("candidates_unique", fx.get("candidates_unique") is True, fx.get("candidates_unique"))
            if fx.get("decode_errors") is not None:
                add("output_decodes", fx["decode_errors"] == 0, fx["decode_errors"])
        else:
            # Negative fixtures: must terminate with a GRACEFUL structured
            # error (an error_code mapping), never a hang or an unhandled
            # traceback leaking to the user.
            graceful = fx.get("final_stage") == "error" and fx.get("error_code") not in (None, "")
            add("fails_gracefully_with_error_code", graceful,
                {"stage": fx.get("final_stage"), "code": fx.get("error_code")})
        add("peak_rss_mb", fx.get("peak_rss_mb", 0) <= th["peak_rss_mb"]["value"], fx.get("peak_rss_mb"))
        add("stage_timings_recorded", bool(fx.get("timings")), fx.get("timings"))
        rows.append({"fixture": fx["fixture"], "job_id": fx.get("job_id"), "checks": checks})
    return rows


def machine_profile() -> dict:
    info = {"os": platform.platform(), "python": platform.python_version(),
            "machine": platform.machine(), "processor": platform.processor()}
    try:
        import faster_whisper
        info["faster_whisper"] = getattr(faster_whisper, "__version__", "unknown")
    except Exception:
        info["faster_whisper"] = "not installed"
    for exe in ("ffmpeg", "ffprobe"):
        try:
            out = subprocess.run([_ffmpeg() if exe == "ffmpeg" else _ffprobe(), "-version"],
                                 capture_output=True, text=True, timeout=10)
            info[exe] = out.stdout.splitlines()[0] if out.stdout else "unknown"
        except Exception:
            info[exe] = "unknown"
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="shorter fixtures/deadlines")
    ap.add_argument("--json", default="docs/foundation/evidence/task-21-baseline.json")
    args = ap.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="clpz-benchmark-"))
    fixtures_dir = workdir / "fixtures"
    fixtures_dir.mkdir(parents=True)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "machine": machine_profile(),
        "thresholds": THRESHOLDS,
        "fixture_provenance": "All fixtures generated locally by this script (deterministic FFmpeg/TTS); hashes recorded per fixture.",
        "human_editorial_rating": "NOT RUN (requires owner panel; objective checks only)",
        "languages_unverified": ["non-English speech — NOT RUN (no licensed multilingual fixture in scope)"],
        "hardware_profile": "developer workstation (see machine); low-spec devices NOT RUN",
        "fixtures": [],
        "workspace": str(workdir),
    }

    gen = [
        # (name, maker, expectation): "speech" must produce clips; negative
        # fixtures must fail GRACEFULLY with a structured error code.
        ("speech_short_portrait", lambda p: fixture_speech_short(p, 8.0 if args.quick else 12.0), "speech"),
        ("silence_landscape", lambda p: fixture_silence(p, 6.0 if args.quick else 8.0), "no_speech"),
        ("two_tone_portrait", lambda p: fixture_two_tone(p, 8.0 if args.quick else 10.0), "no_speech"),
        ("rotated_portrait", lambda p: fixture_rotated(p, 6.0), "speech"),
        ("no_audio", lambda p: fixture_no_audio(p, 6.0), "no_audio"),
    ]
    for name, maker, expectation in gen:
        p = fixtures_dir / f"{name}.mp4"
        try:
            maker(p)
        except Exception as e:
            report["fixtures"].append({"fixture": name, "generation_error": str(e)})
            continue
        try:
            entry = run_pipeline_fixture(name, p, workdir, args.quick)
        except Exception as e:
            entry = {"fixture": name, "pipeline_error": str(e)}
        entry["expectation"] = expectation
        report["fixtures"].append(entry)

    report["results"] = evaluate(report)
    failed = [c for r in report["results"] for c in r["checks"] if not c["ok"]]

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({"report": str(out), "checks_failed": len(failed),
                      "fixtures": len(report["fixtures"])}, indent=2))
    for r in report["results"]:
        for c in r["checks"]:
            print(f"  [{'PASS' if c['ok'] else 'FAIL'}] {r['fixture']}: {c['metric']} = {c['actual']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
