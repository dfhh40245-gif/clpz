"""Task 07 — Transcript integrity regression tests.

Covers the task 07 acceptance checks:
- identical overlap produces one copy; jittered overlaps merge; deliberate
  repeated words remain; empty chunks work
- boundary words and segment timing stay ordered and within source duration
- malformed later word entries, NaN, reverse timestamps, and Unicode fixtures
  produce a controlled result
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline.transcriber import _merge_chunks  # noqa: E402
from pipeline import srt_parser  # noqa: E402


def _chunk(words, segments=None, language="en"):
    """Build a chunk result; segments default to a span over the valid words."""
    if segments is None:
        valid = [w for w in words if isinstance(w.get("start"), (int, float))
                 and isinstance(w.get("end"), (int, float))]
        segments = [{
            "start": valid[0]["start"], "end": valid[-1]["end"],
            "text": " ".join(w["word"] for w in words),
        }] if valid else []
    return {
        "language": language,
        "segments": segments,
        "words": words,
    }


class TestOverlapReconciliation:
    def test_identical_overlap_produces_one_copy(self):
        """F07 regression: 2 identical overlapping chunks → 2 words, 1 segment."""
        chunk = _chunk(
            [{"word": "hello", "start": 28, "end": 28.5},
             {"word": "world", "start": 28.5, "end": 29}])
        merged = _merge_chunks([chunk, chunk], 60)
        assert len(merged["words"]) == 2, merged["words"]
        assert len(merged["segments"]) == 1, merged["segments"]

    def test_jittered_overlap_merges(self):
        """Same overlap with small timing jitter still collapses to one copy."""
        c1 = _chunk([{"word": "hello", "start": 28.0, "end": 28.52},
                     {"word": "world", "start": 28.52, "end": 29.0}])
        c2 = _chunk([{"word": "hello", "start": 28.04, "end": 28.5},
                     {"word": "world", "start": 28.5, "end": 28.98}])
        merged = _merge_chunks([c1, c2], 60)
        assert len(merged["words"]) == 2

    def test_genuine_repeated_words_survive(self):
        """Deliberate repetition ('yeah, yeah') must not be deduplicated."""
        c1 = _chunk([
            {"word": "yeah", "start": 10.0, "end": 10.4},
            {"word": "yeah", "start": 12.0, "end": 12.4},
            {"word": "ok", "start": 13.0, "end": 13.4},
        ])
        merged = _merge_chunks([c1], 60)
        words = [w["word"] for w in merged["words"]]
        assert words == ["yeah", "yeah", "ok"], words

    def test_repeated_word_across_chunks_but_far_apart_survives(self):
        c1 = _chunk([{"word": "go", "start": 29.7, "end": 30.0}])
        c2 = _chunk([{"word": "go", "start": 40.0, "end": 40.3}])
        merged = _merge_chunks([c1, c2], 60)
        assert [w["word"] for w in merged["words"]] == ["go", "go"]

    def test_empty_chunks_are_tolerated(self):
        empty = {"segments": [], "words": [], "language": "unknown"}
        c = _chunk([{"word": "hi", "start": 1.0, "end": 1.5}])
        merged = _merge_chunks([empty, c, empty, c], 60)
        assert len(merged["words"]) == 1
        assert merged["language"] == "en"

    def test_language_carried_from_first_chunk(self):
        c1 = _chunk([], segments=[], language="fr")
        c2 = _chunk([{"word": "x", "start": 1.0, "end": 1.2}], language="en")
        merged = _merge_chunks([c1, c2], 60)
        assert merged["language"] == "fr"


class TestOrderingAndBounds:
    def test_words_and_segments_sorted_and_bounded(self):
        c1 = _chunk([
            {"word": "late", "start": 25.0, "end": 25.5},
            {"word": "early", "start": 5.0, "end": 5.5},
        ])
        merged = _merge_chunks([c1], 30.0)
        starts = [w["start"] for w in merged["words"]]
        assert starts == sorted(starts)
        assert all(w["end"] <= 30.0 + 1e-9 or w["start"] < 30.0 for w in merged["words"])
        seg_starts = [s["start"] for s in merged["segments"]]
        assert seg_starts == sorted(seg_starts)

    def test_words_beyond_source_duration_dropped(self):
        c1 = _chunk([
            {"word": "inside", "start": 10.0, "end": 10.5},
            {"word": "beyond", "start": 31.0, "end": 31.5},
        ])
        merged = _merge_chunks([c1], 30.0)
        assert [w["word"] for w in merged["words"]] == ["inside"]


class TestMalformedInputs:
    def test_malformed_later_entries_dropped(self):
        c1 = _chunk([
            {"word": "good", "start": 1.0, "end": 1.5},
            {"word": "bad", "start": "not-a-number", "end": 2.0},
            {"word": "alsobad", "start": 2.0},
        ])
        merged = _merge_chunks([c1], 60)
        assert [w["word"] for w in merged["words"]] == ["good"]

    def test_nan_and_reverse_timestamps_rejected(self):
        c1 = _chunk([
            {"word": "nan", "start": float("nan"), "end": 2.0},
            {"word": "rev", "start": 5.0, "end": 4.0},
            {"word": "neg", "start": -1.0, "end": 0.5},
            {"word": "ok", "start": 6.0, "end": 6.5},
        ])
        merged = _merge_chunks([c1], 60)
        assert [w["word"] for w in merged["words"]] == ["ok"]

    def test_transcribe_chunk_validates_entries(self):
        from pipeline.transcriber import _validate_timed_entries
        entries = [
            {"word": "ok", "start": 1.0, "end": 1.5},
            {"word": "", "start": 2.0, "end": 2.5},
            {"start": 3.0, "end": 3.5},
        ]
        clean = _validate_timed_entries(entries)
        assert len(clean) == 1 and clean[0]["word"] == "ok"


class TestSrtParser:
    def test_unicode_tokenization_keeps_non_ascii(self):
        """F07: fallback tokenization only matched ASCII alphanumerics."""
        srt = """1
00:00:00,000 --> 00:00:02,000
Café naïve déjà

2
00:00:02,500 --> 00:00:04,000
Привет мир
"""
        p = Path(__file__).parent / "unicode_fixture.srt"
        p.write_text(srt, encoding="utf-8")
        try:
            result = srt_parser.parse_srt(str(p))
            words = " ".join(w["word"] for w in result["words"])
            assert "Café" in words and "naïve" in words and "déjà" in words
            assert "Привет" in words and "мир" in words
        finally:
            p.unlink(missing_ok=True)

    def test_every_words_json_entry_validated(self, tmp_path):
        """A malformed LATER entry is skipped, not trusted; valid ones survive."""
        srt = tmp_path / "t.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        (tmp_path / "words.json").write_text(json.dumps([
            {"word": "good", "start": 0.0, "end": 0.4},
            {"word": "nan", "start": float("nan"), "end": 0.8},
            {"word": "backwards", "start": 0.9, "end": 0.7},
            {"word": "good2", "start": 0.5, "end": 0.9},
        ]), encoding="utf-8")
        result = srt_parser.parse_srt(str(srt))
        words = [w["word"] for w in result["words"]]
        assert words == ["good", "good2"], words

    def test_all_invalid_words_json_falls_back_to_estimation(self, tmp_path):
        srt = tmp_path / "t.srt"
        srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nHello world\n", encoding="utf-8")
        (tmp_path / "words.json").write_text(json.dumps([
            {"word": "bad", "start": 5.0, "end": 2.0},
        ]), encoding="utf-8")
        result = srt_parser.parse_srt(str(srt))
        assert [w["word"] for w in result["words"]] == ["Hello", "world"]

    def test_millisecond_carry_and_order(self, tmp_path):
        srt = tmp_path / "t.srt"
        srt.write_text(
            "1\n00:00:00,990 --> 00:00:01,110\nHi\n\n"
            "2\n00:00:01,100 --> 00:00:02,000\nThere\n", encoding="utf-8")
        result = srt_parser.parse_srt(str(srt))
        segs = result["segments"]
        assert segs[0]["end"] == pytest.approx(1.110, abs=1e-6)
        assert segs[1]["start"] == pytest.approx(1.100, abs=1e-6)
        # Overlapping/carry timing is preserved (not silently reordered away)
        assert segs[0]["end"] > segs[1]["start"] - 0.02

    def test_reverse_timestamp_segment_skipped(self, tmp_path):
        srt = tmp_path / "t.srt"
        srt.write_text(
            "1\n00:00:02,000 --> 00:00:01,000\nReversed\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nValid\n", encoding="utf-8")
        result = srt_parser.parse_srt(str(srt))
        texts = [s["text"] for s in result["segments"]]
        assert texts == ["Valid"], texts
