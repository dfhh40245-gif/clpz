"""Step 4a — generate .ass captions for one clip.

Style: Inter Bold, lowercase white text, no background box, 1-2 words
per group (max 3), subtle shadow for readability, centered in lower third.

Design principles:
- Clean, modern, simple, professional
- Actual Inter Bold font, lowercase
- Static white text, no color animation
- No background box, no blur effects
- Subtle shadow for readability only
- Precise word timestamps from words.json (never invented)
"""
from __future__ import annotations

from pathlib import Path

import config


def _ts(seconds: float) -> str:
    """Format seconds as ASS timestamp H:MM:SS.cc"""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _header(margin_v: int) -> str:
    """Build ASS header with Inter Bold font, no background, subtle shadow.

    BorderStyle 1 = outline + shadow (no box).
    Shadow gives subtle readability without any visible background.
    """
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.OUT_WIDTH}
PlayResY: {config.OUT_HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{config.CAPTION_FONT},{config.CAPTION_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H80000000,&H00000000,-1,0,0,0,100,100,1.5,0,1,2,2,2,0,0,{margin_v},1
Style: Top,{config.CAPTION_FONT},{config.TOP_TEXT_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H80000000,&H00000000,-1,0,0,0,100,100,1.5,0,1,2,0,8,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _group_words(words: list[dict]) -> list[list[dict]]:
    """Group words into caption pages for optimal readability.

    Target: 1-2 words normally, up to 3 for fast speech.
    Breaks at:
    - Natural pauses (>0.3s gap between words)
    - Sentence boundaries (periods, !, ?)
    - Phrase boundaries (commas) with 2+ words
    - Maximum word count (3 words)
    - Character limit (16 chars)

    The grouping adapts to speech timing — fast speech gets more words,
    slow speech gets fewer words.
    """
    pages = []
    cur = []

    for w in words:
        if not w["word"].strip():
            continue

        should_break = False
        if cur:
            # Break on natural pause (>0.3s gap)
            gap = w["start"] - cur[-1]["end"]
            if gap > 0.3:
                should_break = True
            # Break on sentence boundary
            elif cur[-1]["word"].rstrip().endswith((".", "!", "?")):
                should_break = True
            # Break on phrase boundary (comma) with 2+ words
            elif len(cur) >= 2 and cur[-1]["word"].rstrip().endswith(","):
                should_break = True
            # Break on max words (3)
            elif len(cur) >= config.CAPTION_MAX_WORDS:
                should_break = True
            # Break on character limit
            elif sum(len(p["word"]) for p in cur) + len(w["word"]) > config.CAPTION_MAX_CHARS:
                should_break = True

        if should_break and cur:
            pages.append(cur)
            cur = []

        cur.append(w)

    if cur:
        pages.append(cur)

    return pages


def _esc(text: str) -> str:
    """Escape text for ASS subtitle format. Output lowercase."""
    return text.replace("\\", "").replace("{", "").replace("}", "").lower()


def build_ass(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    out_path: Path,
    margin_v: int | None = None,
    top_text: str = "",
) -> Path:
    """Build ASS captions — static white lowercase text, no background.

    Groups words into 1-3 word caption groups, then creates non-overlapping
    dialogue lines. Text is always static white — no color animation,
    no highlighting, no effects. Just clean professional subtitles.

    If top_text is provided, adds a permanent subtitle at the top of the frame
    for the entire clip duration.
    """
    # Filter words to only those within this clip's time range
    local = [
        {
            "start": w["start"] - clip_start,
            "end": w["end"] - clip_start,
            "word": w["word"],
        }
        for w in words
        if w["end"] > clip_start and w["start"] < clip_end and w["word"].strip()
    ]

    lines = [_header(margin_v if margin_v is not None else config.CAPTION_MARGIN_V)]

    # Add top text as a permanent subtitle (whole clip duration)
    if top_text:
        top_text_clean = top_text.replace("{", "").replace("}", "")
        clip_duration = clip_end - clip_start
        lines.append(
            f"Dialogue: 1,0:{_ts(0)[2:]},0:{_ts(clip_duration)[2:]},Top,,0,0,0,,{top_text_clean}\n"
        )

    for page in _group_words(local):
        if not page:
            continue

        page_start = page[0]["start"]
        page_end = page[-1]["end"]

        # One dialogue line per page — static white text, no animation
        text = " ".join(_esc(pw["word"]) for pw in page)
        lines.append(
            f"Dialogue: 0,{_ts(page_start)},{_ts(page_end)},Cap,,0,0,0,,{text}\n"
        )

    out_path.write_text("".join(lines), encoding="utf-8")
    return out_path
