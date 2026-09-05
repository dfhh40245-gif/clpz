"""Generate synthetic test videos for CLPZ automated testing.

Uses FFmpeg to create small deterministic test videos.
No external dependencies beyond FFmpeg (which CLPZ requires anyway).
"""
import subprocess
import shutil
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def _find_ffmpeg() -> str:
    """Find ffmpeg binary."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # Check bundled binaries
    import platform
    bin_dir = Path(__file__).resolve().parent.parent.parent / "bin"
    name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    if (bin_dir / name).exists():
        return str(bin_dir / name)
    raise FileNotFoundError("ffmpeg not found")


def _tts_wav(output_wav: Path, text: str, duration: float) -> bool:
    """Generate real speech via Windows SAPI TTS. Returns False if unavailable."""
    if shutil.which("powershell") is None:
        return False
    ps_script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Rate = 0; $s.SetOutputToWaveFile('{output_wav}'); "
        f"$s.Speak('{text}'); $s.Dispose()"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        return r.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 1000
    except Exception:
        return False


def generate_speech_video(output_path: Path, duration: float = 5.0) -> Path:
    """Generate a small video with synthetic speech-like audio.


[...existing docstring continues...]    Creates a 480x854 (9:16) video with:
    - Color bars (visual content)
    - Sine wave audio (speech-like frequency)
    - Duration: ~5 seconds
    - Size: ~50KB

    Returns the output path.
    """
    ffmpeg = _find_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prefer real TTS speech so Whisper produces a non-empty transcript.
    # Fall back to a sine wave (whisper finds no speech — valid for
    # negative-path tests) when SAPI is unavailable.
    tts_wav = output_path.with_suffix(".tts.wav")
    audio_inputs = (
        ["-f", "lavfi", "-i", f"sine=frequency=300:duration={duration}"]
        if not _tts_wav(tts_wav, "Welcome to the test video. This clip shows how captions appear on short vertical videos. First, we import a long video and pick the best moments automatically. Then the computer reframes everything to a vertical format with face tracking. Finally the captions are burned in and the clip is rendered and ready to post. This is the end of the demonstration. Thanks for watching the whole video.", duration)
        else ["-i", str(tts_wav)]
    )

    cmd = [
        ffmpeg, "-y",
        # Video: color bars at 9:16
        "-f", "lavfi", "-i",
        f"color=c=blue:s=480x854:d={duration},drawtext=text='TEST VIDEO':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        # Audio: real TTS speech when available, else sine wave
        *audio_inputs,
        # Encoding
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k",
        "-shortest",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Generated video is missing or empty")
    tts_wav.unlink(missing_ok=True)

    return output_path


def generate_no_audio_video(output_path: Path, duration: float = 3.0) -> Path:
    """Generate a video with no audio stream."""
    ffmpeg = _find_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i",
        f"color=c=red:s=480x854:d={duration}",
        "-an",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")

    return output_path


def generate_short_video(output_path: Path) -> Path:
    """Generate a very short video (1 second)."""
    return generate_speech_video(output_path, duration=1.0)


def validate_video(path: Path) -> dict:
    """Validate a video file using ffprobe.

    Returns dict with:
        valid: bool
        error: str (if invalid)
        has_video: bool
        has_audio: bool
        duration: float
        width: int
        height: int
        codec: str
    """
    import shutil
    import json

    result = {"valid": False, "error": "", "has_video": False, "has_audio": False,
              "duration": 0, "width": 0, "height": 0, "codec": ""}

    if not path.exists():
        result["error"] = "File does not exist"
        return result
    if path.stat().st_size == 0:
        result["error"] = "File is empty"
        return result

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        result["error"] = "ffprobe not found"
        return result

    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error",
             "-show_entries", "stream=codec_type,codec_name,width,height",
             "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            result["error"] = f"ffprobe failed: {proc.stderr[:200]}"
            return result

        probe = json.loads(proc.stdout)
        streams = probe.get("streams", [])
        fmt = probe.get("format", {})

        for s in streams:
            if s.get("codec_type") == "video":
                result["has_video"] = True
                result["width"] = s.get("width", 0)
                result["height"] = s.get("height", 0)
                result["codec"] = s.get("codec_name", "")
            elif s.get("codec_type") == "audio":
                result["has_audio"] = True

        result["duration"] = float(fmt.get("duration", 0))
        result["valid"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


# Generate fixtures on import if they don't exist
def ensure_fixtures():
    """Ensure test video fixtures exist."""
    speech_video = FIXTURES_DIR / "test_speech.mp4"
    if not speech_video.exists():
        generate_speech_video(speech_video)

    no_audio = FIXTURES_DIR / "test_no_audio.mp4"
    if not no_audio.exists():
        generate_no_audio_video(no_audio)

    short = FIXTURES_DIR / "test_short.mp4"
    if not short.exists():
        generate_short_video(short)

    return {
        "speech": speech_video,
        "no_audio": no_audio,
        "short": short,
    }
