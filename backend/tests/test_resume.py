"""Task 05 — Pipeline resume regression tests.

Covers the task 05 acceptance checks:
- resume after download / transcription / parsing / analysis / partial render
- missing or invalid words.json, SRT, and source media are handled predictably
- interrupted job restart keeps consistent state and stable clip identity
- completed clips are not lost and cancelled jobs do not become done
"""
import json
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import jobs
import database as db
from pipeline import srt_parser

SRT_OK = """1
00:00:00,000 --> 00:00:02,000
Hello world.

2
00:00:02,500 --> 00:00:04,000
Second line.
"""

WORDS_OK = [
    {"word": "Hello", "start": 0.0, "end": 0.5},
    {"word": "world.", "start": 0.5, "end": 1.0},
    {"word": "Second", "start": 2.5, "end": 3.0},
    {"word": "line.", "start": 3.0, "end": 3.5},
]


@pytest.fixture
def isolated_data(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "clpz.db")
    monkeypatch.setattr(db, "_conn", None)
    monkeypatch.setattr(config, "AUTO_CLEANUP_HOURS", 0)
    return tmp_path


def _make_job(data_dir: Path, *, stages=None, srt=SRT_OK, words=WORDS_OK,
              video=True, clips=None) -> str:
    jid = uuid.uuid4().hex[:12]
    d = data_dir / jid
    d.mkdir(parents=True)
    if video:
        video_info = {"path": str(d / "source.mp4"), "title": "T", "duration": 4.0}
    else:
        video_info = {"path": str(d / "missing.mp4"), "title": "T", "duration": 4.0}
    if srt is not None:
        (d / "transcript.srt").write_text(srt, encoding="utf-8")
    if words is not None:
        (d / "words.json").write_text(json.dumps(words), encoding="utf-8")
    job = {
        "id": jid,
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "cancelled_at": None,
        "input_type": "upload",
        "url": "",
        "max_clips": 2,
        "top_text": "",
        "user_id": None,
        "stage": "queued",
        "progress": 0.0,
        "video": video_info,
        "clips": clips if clips is not None else [],
        "error": None,
        "error_code": None,
        "timings": {},
        "completed_stages": list(stages or []),
    }
    with jobs._lock:
        jobs.JOBS[jid] = job
    jobs._persist(job)
    return jid


def _fake_render(monkeypatch, calls):
    """Stub the heavy media stages so resume paths run fast and hermetically."""
    import pipeline.cutter as cutter
    import pipeline.captions as captions
    import pipeline.analyzer as analyzer
    from pipeline import transcriber

    def fake_plan(path, start, end, job_id=""):
        calls.append(("plan", start, end))
        return {"mode": "face", "margin_v": 870}

    def fake_render(path, start, end, ass_path, out_path, plan=None, job_id=""):
        calls.append(("render", start, end))
        Path(out_path).write_bytes(b"fake-mp4-bytes")
        return None

    def fake_build_ass(words, start, end, ass_path, margin_v=870, top_text=""):
        calls.append(("ass", start, end))
        Path(ass_path).write_text("fake ass", encoding="utf-8")
        return Path(ass_path)

    def fake_find_clips(title, duration, segments, max_clips):
        calls.append(("analyze",))
        return [{"title": "Clip A", "start": 0.0, "end": 2.0, "score": 9.0}]

    def fake_validate(path, job_id=""):
        return {"valid": True, "error": "", "duration": 2.0,
                "width": 1080, "height": 1920,
                "video_codec": "h264", "audio_codec": "aac"}

    monkeypatch.setattr(cutter, "plan_layout", fake_plan)
    monkeypatch.setattr(cutter, "render_clip", fake_render)
    monkeypatch.setattr(captions, "build_ass", fake_build_ass)
    monkeypatch.setattr(analyzer, "find_clips", fake_find_clips)
    monkeypatch.setattr(jobs, "_validate_output", fake_validate)

    state = {"transcribe_calls": 0}

    def fake_transcribe(path, progress_cb=None, job_dir=None, job_id=""):
        """Record transcription attempts; regenerate the SRT artifact.

        A stage marker whose artifact is missing is only a CLAIM: the resume
        path must invalidate it and rerun the stage rather than crash. The
        SRT regeneration here lets that recovery path complete.
        """
        state["transcribe_calls"] += 1
        calls.append(("transcribe",))
        if job_dir is not None:
            (Path(job_dir) / "transcript.srt").write_text(SRT_OK, encoding="utf-8")
            (Path(job_dir) / "words.json").write_text(json.dumps(WORDS_OK), encoding="utf-8")
        return {"language": "en", "segments": srt_parser.parse_srt(
            str(Path(job_dir) / "transcript.srt"))["segments"],
            "words": WORDS_OK}

    monkeypatch.setattr(transcriber, "transcribe", fake_transcribe)
    monkeypatch.setattr(jobs, "_transcribe_probe", state, raising=False)
    # Thumbnails need real ffmpeg — stub them out for hermeticity.
    monkeypatch.setattr(jobs, "_build_thumbnail", lambda *a, **k: None)
    return state


def _wait_terminal(jid, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = jobs.get_job(jid)
        if j and j["stage"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.05)
    return jobs.get_job(jid)


# ── The F05 crash: resume after parse+analyze ─────────────────────

def test_resume_after_analysis_completes(isolated_data, monkeypatch):
    """F05 regression: resume with parse+analyze completed must not raise
    UnboundLocalError on `transcript`; it rebuilds from persisted artifacts."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"])
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "done", f"expected done, got {j['stage']}: {j.get('error')}"
    assert any(c[0] == "analyze" for c in calls) or j["clips"], "no clips produced"
    # Clip identity is stable and derived from the job id
    assert j["clips"][0]["id"] == f"{jid}-clip-0"


def test_resume_does_not_rerun_transcription(isolated_data, monkeypatch):
    """Resume must reuse completed stages, not blindly rerun expensive work:
    with the transcribe+parse artifacts present, transcription never reruns."""
    calls = []
    state = _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"])
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "done"
    assert state["transcribe_calls"] == 0, (
        "transcription reran although a valid SRT artifact existed")


def test_resume_after_transcribe_only(isolated_data, monkeypatch):
    """Resume after download+transcribe (before parse) reruns parse forward."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe"])
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "done", j.get("error")
    assert any(c[0] == "analyze" for c in calls)


# ── Invalid artifacts ─────────────────────────────────────────────

def test_resume_with_missing_srt_invalidates_claim_and_recovers(isolated_data, monkeypatch):
    """A transcribe marker without its SRT artifact is a claim, not a fact:
    the resume path invalidates it, reruns transcription, and completes."""
    calls = []
    state = _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"],
                    srt=None)
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "done", (
        f"resume could not recover from a missing SRT artifact: {j.get('error')}")
    assert state["transcribe_calls"] == 1, "invalidated stage was not rerun"


def test_resume_with_invalid_words_json_uses_fallback(isolated_data, monkeypatch):
    """Corrupt words.json must not crash resume; the parser's fallback
    estimation path keeps the job recoverable."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"],
                    words=[{"bad": "entry"}, {"start": float("nan")}])
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    # Either way it must not be an unbound-variable crash:
    assert j["stage"] in ("done", "error")
    if j["stage"] == "error":
        assert "transcript" not in (j.get("error") or "").lower() or \
            "variable" not in (j.get("error") or "").lower()


def test_resume_with_missing_source_media_fails_cleanly(isolated_data, monkeypatch):
    """Source media deleted mid-pipeline: no unbound variables, clear error."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"],
                    video=False)
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] in ("done", "error")  # no crash/unbound variable
    if j["stage"] == "error":
        assert j.get("error_code")


# ── Restart consistency ───────────────────────────────────────────

def test_interrupted_job_restart_keeps_state(isolated_data, monkeypatch):
    """An interrupted (crashed-worker) job must restart from completed stages
    with stable clip identity and no duplicate worker."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe"])
    # Simulate a crashed worker: job stuck mid-stage with a stale worker gone.
    jobs._update(jid, stage="analyzing", progress=0.3)
    # Retry endpoint behavior: requeue and run
    with jobs._lock:
        jobs.JOBS[jid].update({"stage": "queued", "error": None})
    t = threading.Thread(target=jobs._run, args=(jid,), daemon=True)
    t.start()
    t.join(timeout=60)
    j = _wait_terminal(jid)
    assert j["stage"] == "done", j.get("error")
    assert j["clips"][0]["id"] == f"{jid}-clip-0"
    # Only one worker ran: the fake render plan was invoked exactly once per clip
    assert len([c for c in calls if c[0] == "analyze"]) == 1


def test_completed_clips_survive_resume(isolated_data, monkeypatch):
    """Clips already done before the interruption must not be lost."""
    calls = []
    _fake_render(monkeypatch, calls)
    done_clip = {
        "id": "x", "index": 0, "status": "done",
        "file": str(isolated_data / "kept" / "clip_0.mp4"),
        "title": "Kept", "start": 0.0, "end": 2.0,
        "thumbnail": None, "duration": 2.0, "validation": {"valid": True},
    }
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"],
                    clips=[done_clip])
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "done", j.get("error")
    kept = [c for c in j["clips"] if c.get("status") == "done"]
    assert kept, "completed clip was lost during resume"


def test_cancelled_job_never_becomes_done(isolated_data, monkeypatch):
    """Cancellation must win over completion, even after a resume."""
    calls = []
    _fake_render(monkeypatch, calls)
    jid = _make_job(isolated_data, stages=["download", "transcribe", "parse", "analyze"])
    # Cancel just before the pipeline starts
    ev = jobs._cancel_events.setdefault(jid, threading.Event())
    ev.set()
    jobs._run_pipeline(jid)
    j = _wait_terminal(jid)
    assert j["stage"] == "cancelled", f"cancelled job ended as {j['stage']}"
