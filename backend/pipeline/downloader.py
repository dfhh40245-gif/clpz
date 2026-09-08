"""Step 1 — download the source video with yt-dlp.

Proven download strategy based on actual YouTube behavior:
1. HLS combined formats (fastest, when available)
2. mweb client with format 18 (reliable fallback, 360p combined)
3. DASH with web client (higher quality, may need PO Token)

The mweb client is the key insight: it can download format 18 (combined
video+audio) for most videos, even when the web client is blocked by SABR
streaming and DASH formats return 403.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import proc as proc_mod

import config


class DownloadError(RuntimeError):
    pass


def _find_binary(name: str) -> str:
    """Locate a bundled binary, falling back to PATH."""
    is_windows = platform.system() == "Windows"
    exe_name = f"{name}.exe" if is_windows else name

    bin_dir = Path(__file__).resolve().parent.parent / "bin"
    candidate = bin_dir / exe_name
    if candidate.exists():
        return str(candidate)
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(
        f"{name} not found. Install it or place it in {bin_dir}"
    )


def _build_env() -> dict:
    """Build environment with ffmpeg in PATH so yt-dlp can find it."""
    env = os.environ.copy()
    try:
        ffmpeg = _find_binary("ffmpeg")
        ffmpeg_dir = str(Path(ffmpeg).parent)
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
    except FileNotFoundError:
        pass
    return env


def _build_base_cmd(cookies_file: Path | None = None) -> list[str]:
    """Build base yt-dlp command."""
    yt_dlp = _find_binary("yt-dlp")
    cmd = [yt_dlp, "--no-playlist"]

    if cookies_file and cookies_file.exists():
        cmd += ["--cookies", str(cookies_file)]
    elif config.YT_BROWSER_COOKIES:
        cmd += ["--cookies-from-browser", config.YT_BROWSER_COOKIES]

    return cmd


def _run_ytdlp(
    url: str,
    dest_dir: Path,
    out_tmpl: str,
    format_str: str | None = None,
    player_client: str | None = None,
    extra_args: list[str] | None = None,
    timeout: int = 300,
    job_id: str = "",
) -> tuple[dict, str]:
    """Run yt-dlp and return (metadata_dict, stderr_tail)."""
    cmd = _build_base_cmd(Path(config.COOKIES_FILE))

    if player_client:
        cmd += ["--extractor-args", f"youtube:player_client={player_client}"]

    if format_str:
        cmd += ["-f", format_str]

    cmd += [
        "--merge-output-format", "mp4",
        "--print-json",
        "--no-simulate",
        "--newline",
        "-o", out_tmpl,
        url,
    ]

    if extra_args:
        cmd += extra_args

    env = _build_env()

    try:
        proc = proc_mod.run(job_id, cmd, timeout=timeout, env=env)
    except FileNotFoundError as e:
        raise DownloadError(f"Could not find yt-dlp or ffmpeg: {e}")
    except subprocess.TimeoutExpired:
        raise DownloadError(
            f"Download timed out after {timeout} seconds."
        )

    if proc.returncode != 0:
        err = proc.stderr[-1000:] if proc.stderr else ""
        raise DownloadError(err)

    meta = _parse_json_output(proc.stdout)
    return meta, proc.stderr[-500:] if proc.stderr else ""


def _parse_json_output(stdout: str) -> dict:
    """Extract the JSON metadata object from yt-dlp stdout."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _classify_error(err: str, url: str) -> str:
    """Classify and return a user-friendly error message."""
    err_lower = err.lower()

    if "sign in to confirm" in err_lower or "not a bot" in err_lower:
        return (
            "YouTube bot-check blocked this download. "
            "Enable browser authentication and make sure you're "
            "logged into YouTube."
        )
    if "private" in err_lower or "unavailable" in err_lower:
        return "This YouTube video is private or unavailable."
    if "age" in err_lower and ("restrict" in err_lower or "sign" in err_lower):
        return (
            "This video requires YouTube sign-in due to age restrictions. "
            "Enable browser authentication."
        )
    if "only images" in err_lower or "no video formats" in err_lower:
        return "YouTube provided no downloadable video formats."
    if "http error 403" in err_lower:
        return "YouTube blocked the download request (403 Forbidden)."
    if "http error 404" in err_lower:
        return "Video not found. The URL may be incorrect."
    if "network" in err_lower or "connection" in err_lower:
        return "Network error. Check your internet connection."
    if "ffmpeg" in err_lower:
        return "FFmpeg could not merge the audio and video streams."

    return (
        f"YouTube download failed. The video may be private, "
        f"age-restricted, or the URL is wrong.\n{err}"
    )


def _verify_download(path: Path, job_id: str = "") -> None:
    """Verify the downloaded file is a valid video."""
    if not path.exists():
        raise DownloadError("Download finished but no file was produced.")
    if path.stat().st_size == 0:
        raise DownloadError("Downloaded file is empty (0 bytes).")

    try:
        ffprobe = _find_binary("ffprobe")
        result = proc_mod.run(
            job_id,
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=codec_type,duration",
                "-show_entries", "format=duration",
                "-of", "json", str(path),
            ],
            timeout=30,
        )
        if result.returncode != 0:
            raise DownloadError("Downloaded file is not a valid video.")

        probe = json.loads(result.stdout)
        streams = probe.get("streams", [])
        has_video = any(s.get("codec_type") == "video" for s in streams)
        if not has_video:
            raise DownloadError("Downloaded file has no video stream.")

        fmt = probe.get("format", {})
        duration = float(fmt.get("duration", 0))
        if duration <= 0:
            raise DownloadError("Downloaded video has zero duration.")

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        if path.stat().st_size < 1024:
            raise DownloadError("Downloaded file is too small to be valid.")


def _get_duration_from_file(path: Path, job_id: str = "") -> float:
    """Get video duration using ffprobe."""
    try:
        ffprobe = _find_binary("ffprobe")
        result = proc_mod.run(
            job_id,
            [
                ffprobe, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            timeout=30,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0


def _try_download(
    url: str,
    dest_dir: Path,
    out_tmpl: str,
    format_str: str | None = None,
    player_client: str | None = None,
    extra_args: list[str] | None = None,
    timeout: int = 300,
    job_id: str = "",
) -> dict:
    """Attempt a single download. Returns result dict or raises DownloadError."""
    meta, stderr = _run_ytdlp(
        url, dest_dir, out_tmpl,
        format_str=format_str,
        player_client=player_client,
        extra_args=extra_args,
        timeout=timeout,
        job_id=job_id,
    )

    files = sorted(dest_dir.glob("source.*"))
    if not files:
        raise DownloadError("No file was produced.")

    path = files[0]
    _verify_download(path, job_id=job_id)

    title = meta.get("title", "Untitled video")
    duration = float(meta.get("duration") or 0.0)
    if duration <= 0:
        duration = _get_duration_from_file(path, job_id=job_id)

    return {
        "path": str(path),
        "title": title,
        "duration": duration,
    }


def _is_bot_check(err: str) -> bool:
    """Check if error is a bot-check / authentication error."""
    err_lower = err.lower()
    return any(phrase in err_lower for phrase in [
        "sign in to confirm", "not a bot",
    ])


def download(
    url: str,
    dest_dir: Path,
    progress_cb=None,
    browser_cookies: str | None = None,
    job_id: str = "",
) -> dict:
    """Download best <=1080p mp4. Returns {"path": ..., "title": ..., "duration": ...}.

    Proven strategy:
    1. Try mweb client with format 18 (combined 360p, most reliable)
    2. If mweb fails with bot-check, try browser cookies
    3. Try HLS formats if available
    4. Try DASH with web client (higher quality, may need PO Token)
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_dir / "source.%(ext)s")

    cookies_file = Path(config.COOKIES_FILE)
    last_error = None

    # Strategy 1: mweb client — most reliable for combined format download
    # Format 18 is a combined video+audio stream that works via mweb client
    # even when web client is blocked by SABR streaming.
    strategies = [
        {
            "name": "mweb combined",
            "format": "b[height<=1080][ext=mp4]/b[height<=1080]/b",
            "client": "mweb",
        },
        {
            "name": "mweb fallback",
            "format": None,
            "client": "mweb",
        },
        {
            "name": "HLS combined",
            "format": "b[height<=1080][protocol^=m3u8]/b[height<=1080]",
            "client": None,
        },
        {
            "name": "web combined",
            "format": "b[ext=mp4]/b",
            "client": "web",
        },
    ]

    for strategy in strategies:
        try:
            result = _try_download(
                url, dest_dir, out_tmpl,
                format_str=strategy["format"],
                player_client=strategy["client"],
                timeout=300,
                job_id=job_id,
            )
            return result

        except DownloadError as e:
            error_msg = str(e)
            last_error = e

            # Bot-check: try with browser cookies, then stop
            if _is_bot_check(error_msg):
                browser = browser_cookies or config.YT_BROWSER_COOKIES
                if browser:
                    try:
                        result = _try_download(
                            url, dest_dir, out_tmpl,
                            format_str=strategy["format"],
                            player_client=strategy["client"],
                            extra_args=["--cookies-from-browser", browser],
                            timeout=300,
                            job_id=job_id,
                        )
                        return result
                    except DownloadError:
                        pass
                break  # No point retrying other strategies for bot-check

            # Continue to next strategy for other errors
            continue

    if last_error:
        raise DownloadError(_classify_error(str(last_error), url))
    raise DownloadError("YouTube download failed for unknown reasons.")
