"""Generate a synthetic video with REAL speech (via TTS) for Phase B soak tests.

The 30-min soak videos need actual spoken words so Whisper produces a real
transcript and the pipeline runs end-to-end (parse -> analyze -> render).
Strategy: build a 10s TTS speech clip (edge-tts if available, else beep-speech
fallback is NOT usable) and loop it with concat to fill the requested duration,
with testsrc2 visuals so frames differ over time.
"""
import subprocess
import sys
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FFMPEG = str(HERE.parent / "backend" / "bin" / "ffmpeg.exe")


def _tts_clip(out: Path, text: str, seconds: float) -> bool:
    """Try edge-tts (if installed) to synthesize a speech clip. Returns success."""
    exe = shutil.which("edge-tts")
    cmd = [exe, "--text", text, "--write-media", str(out)] if exe else \
          [sys.executable, "-m", "edge_tts", "--text", text, "--write-media", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 1000
    except Exception:
        return False


def gen(minutes: float, out: Path, w=640, h=360, fps=15):
    dur = int(minutes * 60)
    tmp = out.parent / "_tts_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    speech = tmp / "speech.mp3"
    made_speech = _tts_clip(
        speech,
        "Welcome back to the show. Today we are talking about how small teams "
        "can build great products fast. Let me walk you through the three big "
        "ideas that changed how we work. First, focus beats effort every time. "
        "Second, shipping early teaches you what customers actually want. "
        "Third, taste is a skill you can practice daily.",
        10)
    if made_speech:
        # Loop the speech clip to cover the full duration, with visuals.
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"testsrc2=duration={dur}:size={w}x{h}:rate={fps}",
            "-stream_loop", "-1", "-i", str(speech),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-c:a", "aac", "-b:a", "48k", "-shortest", str(out),
        ]
    else:
        # No TTS available: still generate the video (tone track). Soak tests
        # that need real transcription must use edge-tts.
        print("WARNING: edge-tts not available; using tone track (no speech)")
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"testsrc2=duration={dur}:size={w}x{h}:rate={fps}",
            "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-c:a", "aac", "-b:a", "48k", "-shortest", str(out),
        ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-400:]
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"generated {out} ({minutes} min, {out.stat().st_size/1e6:.1f} MB)")

if __name__ == "__main__":
    minutes = float(sys.argv[1])
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    gen(minutes, out)
