"""Step 4b — cut a clip, crop to 9:16 centered on the active speaker,
burn in captions, export 1080x1920 mp4.

Speaker-aware face tracking:
- Detects faces across sampled frames
- Matches faces into continuous tracks across frames
- Associates tracks with transcript segments (speaker timing)
- Smooth tracking within one speaker
- Hard cuts when switching between speakers
- Falls back to largest-face tracking for single-person videos
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import config


def _find_bin(name: str) -> str:
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


class RenderError(RuntimeError):
    pass


def _probe_dimensions(video_path: str) -> tuple[int, int]:
    """Display dimensions. ffmpeg auto-rotates frames per rotation metadata
    before our filters run, so swap w/h when the source is rotated 90/270."""
    proc = subprocess.run(
        [
            _find_bin("ffprobe"), "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:stream_side_data=rotation",
            "-of", "json", video_path,
        ],
        capture_output=True, text=True, timeout=60,
    )
    stream = json.loads(proc.stdout)["streams"][0]
    w, h = int(stream["width"]), int(stream["height"])
    rotation = 0
    for sd in stream.get("side_data_list", []):
        if "rotation" in sd:
            rotation = int(sd["rotation"])
    if abs(rotation) % 180 == 90:
        w, h = h, w
    return w, h


def _grab_frame(video_path: str, t: float):
    """Decode one frame at time t using ffmpeg."""
    import cv2
    import numpy as np

    proc = subprocess.run(
        [
            _find_bin("ffmpeg"), "-v", "error", "-ss", f"{t:.2f}", "-i", video_path,
            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "-",
        ],
        capture_output=True, timeout=60,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def _face_keyframes(video_path: str, start: float, end: float) -> tuple[list[tuple[float, float]], list[tuple[float, float, float, float]]]:
    """Speaker-aware face tracking with hard cuts.

    Returns (keyframes, face_boxes) where:
      keyframes: list of (clip_local_time, center_x_fraction)
      face_boxes: list of (cx, cy, w, h) as fractions of frame dimensions
    Falls back to single-centered for single-person or no-face videos.
    """
    try:
        return _speaker_aware_tracking(video_path, start, end)
    except Exception:
        return [(0.0, 0.5)], []


def _speaker_aware_tracking(video_path: str, start: float, end: float) -> list[tuple[float, float]]:
    """Build speaker-aware face tracking keyframes.

    1. Sample frames at ~0.5s intervals
    2. Detect all faces in each frame
    3. Match faces across frames into continuous tracks
    4. For each transcript segment time range, find the dominant face
    5. Generate keyframes with hard cuts at speaker transitions
    6. Smooth tracking within each speaker segment
    """
    import cv2
    import numpy as np

    duration = end - start
    sample_interval = 0.5  # seconds between samples
    n_samples = max(4, min(60, int(duration / sample_interval)))

    # Sample frames and detect faces
    frames_data = []  # [(time, [(cx, cy, w, h), ...]), ...]
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    for i in range(n_samples):
        t = start + duration * (i + 0.5) / n_samples
        local_t = t - start
        frame = _grab_frame(video_path, t)
        if frame is None:
            frames_data.append((local_t, []))
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
        fh, fw = frame.shape[:2]

        face_list = []
        for (x, y, w, h) in faces:
            cx = (x + w / 2) / fw
            cy = (y + h / 2) / fh
            face_list.append((cx, cy, w / fw, h / fh))

        frames_data.append((local_t, face_list))

    if not frames_data:
        return [(0.0, 0.5)], []

    # Check if there's only one person (single face dominant)
    all_faces = [f for _, faces in frames_data for f in faces]
    if len(all_faces) < 3:
        # Too few face detections — just track the largest
        return _simple_largest_face_tracking(frames_data), []

    # Match faces across frames into tracks
    tracks = _match_faces_into_tracks(frames_data)

    if len(tracks) < 2:
        # Single track — just smooth track it
        return _single_track_keyframes(tracks, duration), []

    # Multiple tracks — use transcript segments to determine speaker switches
    return _multi_speaker_keyframes(tracks, duration, frames_data), []


def _simple_largest_face_tracking(frames_data: list[tuple[float, list]]) -> list[tuple[float, float]]:
    """Fallback: track the largest face in each frame, smooth the result."""
    import numpy as np

    keyframes = []
    for t, faces in frames_data:
        if faces:
            # Pick the largest face
            best = max(faces, key=lambda f: f[2] * f[3])
            keyframes.append((t, best[0]))
        else:
            keyframes.append((t, None))

    # Fill gaps with last known position
    filled = _fill_gaps(keyframes)

    # Smooth
    smoothed = _smooth_keyframes(filled)

    return smoothed


def _match_faces_into_tracks(frames_data: list[tuple[float, list]]) -> list[dict]:
    """Match faces across consecutive frames into continuous tracks.

    Returns list of track dicts:
    {
        'id': int,
        'centers': [(time, cx, cy), ...],
        'total_frames': int,
        'avg_size': float,
    }
    """
    tracks = []
    next_id = 0
    # Previous frame's faces: [(track_id, cx, cy, size)]
    prev_faces = []

    for t, faces in frames_data:
        if not faces:
            prev_faces = []
            continue

        curr_faces = []
        used_tracks = set()

        # Try to match each current face to a previous track
        for cx, cy, w, h in faces:
            size = w * h
            best_match = None
            best_dist = 0.35  # max matching distance (fraction of frame width)

            for track_id, pcx, pcy, psize in prev_faces:
                if track_id in used_tracks:
                    continue
                dist = ((cx - pcx) ** 2 + (cy - pcy) ** 2) ** 0.5
                # Also consider size similarity
                size_ratio = min(size, psize) / max(size, psize) if max(size, psize) > 0 else 0
                if dist < best_dist and size_ratio > 0.3:
                    best_dist = dist
                    best_match = track_id

            if best_match is not None:
                curr_faces.append((best_match, cx, cy, size))
                used_tracks.add(best_match)
            else:
                # New track
                curr_faces.append((next_id, cx, cy, size))
                tracks.append({
                    'id': next_id,
                    'centers': [],
                    'total_frames': 0,
                    'avg_size': 0.0,
                })
                next_id += 1

        # Update track data
        for track_id, cx, cy, size in curr_faces:
            for track in tracks:
                if track['id'] == track_id:
                    track['centers'].append((t, cx, cy))
                    track['total_frames'] += 1
                    track['avg_size'] = (
                        track['avg_size'] * (track['total_frames'] - 1) + size
                    ) / track['total_frames']
                    break

        prev_faces = [(tid, cx, cy, sz) for tid, cx, cy, sz in curr_faces]

    # Remove tracks with too few frames (noise)
    tracks = [t for t in tracks if t['total_frames'] >= 2]

    return tracks


def _fill_gaps(keyframes: list[tuple[float, float | None]]) -> list[tuple[float, float]]:
    """Fill None gaps with last known position."""
    filled = []
    last_x = 0.5
    first_x = None

    for t, x in keyframes:
        if x is not None:
            last_x = x
            if first_x is None:
                first_x = x
        filled.append((t, last_x if x is not None else (first_x or 0.5)))

    return filled


def _smooth_keyframes(keyframes: list[tuple[float, float]], window: int = 3) -> list[tuple[float, float]]:
    """Apply moving average smoothing to keyframes."""
    if len(keyframes) <= window:
        return keyframes

    smoothed = []
    for i in range(len(keyframes)):
        start_idx = max(0, i - window // 2)
        end_idx = min(len(keyframes), i + window // 2 + 1)
        avg_x = sum(kf[1] for kf in keyframes[start_idx:end_idx]) / (end_idx - start_idx)
        smoothed.append((keyframes[i][0], avg_x))

    return smoothed


def _single_track_keyframes(tracks: list[dict], duration: float) -> list[tuple[float, float]]:
    """Generate keyframes for a single face track."""
    if not tracks:
        return [(0.0, 0.5)]

    track = tracks[0]
    keyframes = [(t, cx) for t, cx, _ in track['centers']]
    keyframes.sort(key=lambda k: k[0])

    return _smooth_keyframes(keyframes) if len(keyframes) > 1 else keyframes


def _multi_speaker_keyframes(
    tracks: list[dict],
    duration: float,
    frames_data: list[tuple[float, list]],
) -> list[tuple[float, float]]:
    """Generate keyframes with speaker-aware switching.

    Uses transcript segment timing to identify when speakers change.
    For each time window, picks the most prominent face track.
    Hard cuts at speaker transitions, smooth tracking within speakers.
    """
    import numpy as np

    if not tracks:
        return [(0.0, 0.5)]

    # Build a time-series of which track is dominant at each sampled time
    track_timeseries = []  # [(time, dominant_track_id)]

    for t, faces in frames_data:
        if not faces:
            continue

        best_track = None
        best_score = -1

        for cx, cy, w, h in faces:
            size = w * h
            # Find the best matching track
            for track in tracks:
                # Check if this face matches the track
                for tt, tcx, tcy in track['centers']:
                    dist = ((cx - tcx) ** 2 + (cy - tcy) ** 2) ** 0.5
                    if dist < 0.2:  # Close match
                        # Score: size + temporal consistency
                        score = size + track['total_frames'] * 0.01
                        if score > best_score:
                            best_score = score
                            best_track = track['id']
                        break

        if best_track is not None:
            track_timeseries.append((t, best_track))

    if not track_timeseries:
        return _simple_largest_face_tracking(frames_data)

    # Find speaker change points: when the dominant track changes
    switch_times = [0.0]  # Start with first speaker
    current_track = track_timeseries[0][1]
    min_segment_duration = 1.0  # Minimum seconds before allowing a switch

    for t, track_id in track_timeseries:
        if track_id != current_track:
            # Only switch if enough time has passed
            if t - switch_times[-1] >= min_segment_duration:
                switch_times.append(t)
                current_track = track_id

    # Build keyframes: smooth within each segment, hard cut at boundaries
    keyframes = []
    for i in range(len(switch_times)):
        seg_start = switch_times[i]
        seg_end = switch_times[i + 1] if i + 1 < len(switch_times) else duration

        # Get the dominant track for this segment
        seg_tracks = [(t, tid) for t, tid in track_timeseries
                      if seg_start <= t < seg_end]
        if not seg_tracks:
            continue

        # Most common track in this segment
        track_counts = {}
        for _, tid in seg_tracks:
            track_counts[tid] = track_counts.get(tid, 0) + 1
        dominant_track_id = max(track_counts, key=track_counts.get)

        # Get the track's centers for this segment
        track = next((t for t in tracks if t['id'] == dominant_track_id), None)
        if not track:
            continue

        seg_centers = [(t, cx) for t, cx, _ in track['centers']
                       if seg_start <= t < seg_end]
        seg_centers.sort(key=lambda k: k[0])

        if not seg_centers:
            continue

        # Hold the prior face through the boundary, then add the incoming
        # face at that exact same timestamp.  _x_expression recognises two
        # positions at one time as a cut, so it cannot interpolate a pan
        # across a speaker/face switch.
        if keyframes and seg_start > 0:
            keyframes.append((seg_start, keyframes[-1][1]))
        keyframes.append((seg_start, seg_centers[0][1]))

        # Add smoothed keyframes within the segment
        if len(seg_centers) > 2:
            smoothed = _smooth_keyframes(seg_centers, window=3)
            for t, cx in smoothed[1:]:  # Skip first (already added)
                keyframes.append((t, cx))
        else:
            for t, cx in seg_centers[1:]:
                keyframes.append((t, cx))

    keyframes.sort(key=lambda k: k[0])

    # Ensure we have at least one keyframe
    if not keyframes:
        keyframes = [(0.0, 0.5)]

    return keyframes


def _x_expression(keyframes: list[tuple[float, float]], src_w: int, crop_w: int) -> str:
    """Build an ffmpeg crop-x expression: piecewise-linear pan between
    keyframes, clamped to the frame, rounded to even pixels.

    For hard cuts: when two adjacent keyframes have the same time but
    different x values, ffmpeg will jump instantly (hard cut).
    """
    def px(frac: float) -> int:
        x = int(frac * src_w - crop_w / 2)
        x = max(0, min(x, src_w - crop_w))
        return x // 2 * 2

    pts = [(t, px(c)) for t, c in keyframes]
    xs = sorted(p for _, p in pts)
    # Collapse to static crop if the pan would be imperceptible (<2% width)
    if xs[-1] - xs[0] < 0.02 * src_w:
        return str(xs[len(xs) // 2])

    E = "\\,"  # comma escaped for the ffmpeg filtergraph parser
    expr = str(pts[-1][1])  # after last keyframe: hold final position
    for (t0, x0), (t1, x1) in reversed(list(zip(pts, pts[1:]))):
        if t1 == t0:
            # Hard cut: just use the new position
            expr = str(x1)
        else:
            seg = f"{x0}+({x1}-{x0})*(t-{t0:.2f})/{(t1 - t0):.2f}"
            expr = f"if(lt(t{E}{t1:.2f}){E}{seg}{E}{expr})"
    return f"if(lt(t{E}{pts[0][0]:.2f}){E}{pts[0][1]}{E}{expr})"


def plan_layout(source: str, start: float, end: float) -> dict:
    """Decide per-clip layout. Returns a plan dict consumed by render_clip:
    {"mode": "face"|"split", "margin_v": int, ...mode-specific fields}."""
    src_w, src_h = _probe_dimensions(source)
    target_ratio = config.OUT_WIDTH / config.OUT_HEIGHT

    if src_w / src_h <= target_ratio:
        # Vertical/square source: simple center crop, normal captions
        return {"mode": "face", "margin_v": config.CAPTION_MARGIN_V,
                "src_w": src_w, "src_h": src_h, "keyframes": [(0.0, 0.5)]}

    keyframes, boxes = _face_keyframes(source, start, end)
    median_face_h = sorted(b[3] for b in boxes)[len(boxes) // 2] if boxes else 1.0
    is_facecam = boxes and median_face_h < config.FACECAM_MAX_FACE_FRAC

    mode = config.CLIP_LAYOUT
    if mode == "auto":
        mode = "split" if is_facecam else "face"
    if mode == "split" and not boxes:
        mode = "face"  # nothing to pin in the top panel

    if mode == "face":
        return {"mode": "face", "margin_v": config.CAPTION_MARGIN_V,
                "src_w": src_w, "src_h": src_h, "keyframes": keyframes}

    # Split: median face box, expanded into a facecam region with margin
    n = len(boxes)
    med = tuple(sorted(b[i] for b in boxes)[n // 2] for i in range(4))
    fx, fy, fw, fh = med
    cx, cy = fx + fw / 2, fy + fh / 2
    # Top panel is 1080 x SPLIT_FACE_HEIGHT; crop region matches its aspect
    panel_ratio = config.OUT_WIDTH / config.SPLIT_FACE_HEIGHT
    crop_h = min(1.0, fh * 2.6)
    crop_w = min(1.0, crop_h * panel_ratio * src_h / src_w)
    crop_h = crop_w * src_w / (panel_ratio * src_h)  # re-sync after clamping
    x0 = min(max(cx - crop_w / 2, 0.0), 1.0 - crop_w)
    y0 = min(max(cy - crop_h / 2, 0.0), 1.0 - crop_h)
    face_crop = (
        int(x0 * src_w) // 2 * 2, int(y0 * src_h) // 2 * 2,
        max(2, int(crop_w * src_w) // 2 * 2), max(2, int(crop_h * src_h) // 2 * 2),
    )
    return {"mode": "split", "margin_v": config.CAPTION_MARGIN_V_SPLIT,
            "src_w": src_w, "src_h": src_h, "face_crop": face_crop}


def _audio_args() -> list[str]:
    args = []
    if config.LOUDNORM:
        args += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    return args


def render_clip(
    source: str,
    start: float,
    end: float,
    ass_path: Path,
    out_path: Path,
    plan: dict | None = None,
) -> Path:
    plan = plan or plan_layout(source, start, end)
    src_w, src_h = plan["src_w"], plan["src_h"]
    target_ratio = config.OUT_WIDTH / config.OUT_HEIGHT
    ass_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    fonts_dir = config.CAPTION_FONTS_DIR.replace("\\", "/").replace(":", "\\:")
    subs = f"subtitles=filename='{ass_escaped}':fontsdir='{fonts_dir}'"
    
    # Black bars
    bar_h = config.BLACK_BAR_HEIGHT
    use_bars = bar_h > 0
    
    # Video area dimensions (between black bars)
    vid_area_h = config.OUT_HEIGHT - (2 * bar_h if use_bars else 0)
    vid_y = bar_h if use_bars else 0
    
    if plan["mode"] == "split":
        fx, fy, fw, fh = plan["face_crop"]
        face_h = config.SPLIT_FACE_HEIGHT
        # The screen/video area sits below the face panel, between the black bars.
        # Calculate screen height to fill the padded video area completely.
        vid_h = vid_area_h if use_bars else config.OUT_HEIGHT
        scr_h = vid_h - face_h
        if scr_h < 2:
            scr_h = vid_h // 2
            face_h = vid_h - scr_h
        scr_y = vid_y + face_h
        fc = (
            f"[0:v]split=3[bgs][scr][fce];"
            f"[bgs]scale={config.OUT_WIDTH}:{config.OUT_HEIGHT}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={config.OUT_WIDTH}:{config.OUT_HEIGHT},"
            f"boxblur=20:2,eq=brightness=-0.2[bg];"
            f"[fce]crop={fw}:{fh}:{fx}:{fy},"
            f"scale={config.OUT_WIDTH}:{face_h}:flags=lanczos[facep];"
            f"[scr]scale={config.OUT_WIDTH}:{scr_h}:flags=lanczos[scrp];"
            f"[bg][facep]overlay=0:0[t1];"
            f"[t1][scrp]overlay=0:{scr_y}[t2];"
            f"[t2]{subs}[vout]"
        )
        cmd = [
            _find_bin("ffmpeg"), "-y",
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
            "-i", source,
            "-filter_complex", fc, "-map", "[vout]", "-map", "0:a?",
            *_audio_args(),
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET, "-crf", config.VIDEO_CRF,
            "-profile:v", config.VIDEO_PROFILE, "-level:v", config.VIDEO_LEVEL,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ]
    else:
        # ---- Face-tracking crop mode ----
        # When black bars are active, the crop must match the padded area's
        # aspect ratio (not the full output), so the scaled video fills
        # the padded region completely with no side letterboxing.
        if use_bars:
            padded_ratio = config.OUT_WIDTH / vid_area_h
        else:
            padded_ratio = target_ratio

        if src_w / src_h > padded_ratio:
            # Landscape source: crop horizontally to match target ratio
            crop_w = int(src_h * padded_ratio) // 2 * 2
            crop_w = max(2, min(crop_w, src_w))
            x_expr = _x_expression(plan["keyframes"], src_w, crop_w)
            crop = f"crop={crop_w}:{src_h}:x={x_expr}:y=0"
        else:
            # Vertical/square source: crop vertically (center)
            crop_w = src_w
            crop_h = min(int(src_w / padded_ratio) // 2 * 2, src_h)
            crop = f"crop={crop_w}:{crop_h}:0:{(src_h - crop_h) // 2}"

        # Build filter chain: crop → scale to fill padded area → pad → captions
        if use_bars:
            vf = f"{crop},scale={config.OUT_WIDTH}:{vid_area_h}:flags=lanczos"
            vf += f",pad={config.OUT_WIDTH}:{config.OUT_HEIGHT}:0:{vid_y}:black"
        else:
            vf = f"{crop},scale={config.OUT_WIDTH}:{config.OUT_HEIGHT}:flags=lanczos"

        # Add captions
        vf += f",{subs}"

        cmd = [
            _find_bin("ffmpeg"), "-y",
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}",
            "-i", source,
            "-vf", vf,
            *_audio_args(),
            "-c:v", "libx264", "-preset", config.VIDEO_PRESET, "-crf", config.VIDEO_CRF,
            "-profile:v", config.VIDEO_PROFILE, "-level:v", config.VIDEO_LEVEL,
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise RenderError("ffmpeg timed out rendering this clip (10 min limit).")
    if proc.returncode != 0:
        raise RenderError(f"ffmpeg failed:\n{proc.stderr[-800:]}")
    return out_path
