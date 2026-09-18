"""R02 — transcription hard-deadline regression tests.

Verifies the three properties the review required:

1. A stuck transcription child is force-terminated at the configured deadline
   (plus a stated cleanup tolerance) and the job fails with TRANSCRIBE_TIMEOUT.
2. The worker slot is released afterwards (a next worker can acquire it).
3. The next queued job actually runs to completion.

These tests exercise the REAL production boundary: the parent-side supervision
loop, deadline, kill and cleanup in pipeline/transcriber.py run unmodified.
Only the child's command is redirected (via the ``_child_command`` seam) to
controlled wrapper scripts, routed per job via the payload filename prefix:
a hang wrapper for the stuck job, and a success wrapper for the follow-up job
so the queue visibly drains. No Whisper model is downloaded or loaded.
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
import jobs
from pipeline import transcriber
from tests.test_remediation import isolated_data  # noqa: F401  (fixture)
from tests.test_resume import _make_job, _fake_render

# conftest forces supervision off for the suite; this module turns it back ON
# because it tests the real supervised boundary.
pytestmark = pytest.mark.usefixtures("supervision_on")

DEADLINE_SECONDS = 2.0
# deadline + child interpreter startup + Windows teardown jitter.
KILL_TOLERANCE_SECONDS = 15.0
JOIN_TIMEOUT = DEADLINE_SECONDS + KILL_TOLERANCE_SECONDS + 20

# ── Child wrappers ─────────────────────────────────────────────────
# Both wrappers run the REAL child entry point (``_child_main``) after
# stubbing only ``transcribe``; crash traces go to <marker>.wrappererr
# because the parent devnulls the child's stderr.

HANG_WRAPPER = """\
import sys, time, traceback
try:
    backend, marker = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]
    sys.path.insert(0, backend)
    import pipeline.transcriber as t
    open(marker, 'w').write('armed')
    t.transcribe = lambda *a, **k: time.sleep(10**6)
    sys.argv = ['transcriber.py'] + rest
    t._child_main()
except SystemExit:
    raise
except BaseException:
    open(sys.argv[2] + '.wrappererr', 'w').write(traceback.format_exc())
    raise
"""

SUCCESS_WRAPPER = """\
import json, sys, traceback
from pathlib import Path
try:
    backend, marker = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]
    sys.path.insert(0, backend)
    import pipeline.transcriber as t
    open(marker, 'w').write('ran')
    payload = json.loads(Path(sys.argv[sys.argv.index('--payload') + 1])
                         .read_text(encoding='utf-8'))
    job_dir = payload.get('job_dir')
    words = [
        {"word": "Hello", "start": 0.0, "end": 0.5},
        {"word": "world.", "start": 0.5, "end": 1.0},
        {"word": "Second", "start": 2.5, "end": 3.0},
        {"word": "line.", "start": 3.0, "end": 3.5},
    ]
    srt = ("1\\n00:00:00,000 --> 00:00:02,000\\nHello world.\\n\\n"
           "2\\n00:00:02,500 --> 00:00:04,000\\nSecond line.\\n")
    if job_dir:
        Path(job_dir, 'transcript.srt').write_text(srt, encoding='utf-8')
        Path(job_dir, 'words.json').write_text(
            json.dumps(words), encoding='utf-8')
    t.transcribe = lambda *a, **k: {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Hello world."},
            {"start": 2.5, "end": 4.0, "text": "Second line."},
        ],
        "words": words,
    }
    sys.argv = ['transcriber.py'] + rest
    t._child_main()
except SystemExit:
    raise
except BaseException:
    open(sys.argv[2] + '.wrappererr', 'w').write(traceback.format_exc())
    raise
"""


@pytest.fixture
def supervision_on(monkeypatch):
    monkeypatch.setattr(config, "TRANSCRIBE_SUPERVISED", True)
    monkeypatch.setattr(
        config, "TRANSCRIBE_DEADLINE_SECONDS", DEADLINE_SECONDS)
    yield


def _write_wrapper(tmp_path, name, body):
    d = tmp_path / "wrappers"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    return p


def _route_commands(routes, real_command):
    """Route each job's child to its wrapper; unmatched jobs use the real
    production command. Routing key: payload filename prefix ``<job_id>-``
    (assigned by ``_payload_paths``)."""
    backend_dir = str(Path(__file__).resolve().parent.parent)

    def command(script_arg, payload_path, result_path, err_path):
        name = Path(payload_path).name
        for job_id, (marker, wrapper) in routes.items():
            if name.startswith(f"{job_id}-"):
                return [
                    sys.executable, str(wrapper), backend_dir, str(marker),
                    "--payload", str(payload_path),
                    "--result", str(result_path),
                    "--err", str(err_path),
                ]
        return real_command(script_arg, payload_path, result_path, err_path)

    return command


# ── 1. Stuck child dies at the deadline ────────────────────────────

def test_stuck_child_terminated_at_deadline(isolated_data, monkeypatch, tmp_path):
    marker = tmp_path / "hang-marker"
    hang_wrapper = _write_wrapper(tmp_path, "hang_wrapper.py", HANG_WRAPPER)
    real_command = transcriber._child_command

    jid = _make_job(isolated_data, stages=["download"])
    monkeypatch.setattr(
        transcriber, "_child_command",
        _route_commands({jid: (marker, hang_wrapper)}, real_command))

    started = time.monotonic()
    jobs._run_pipeline(jid)
    elapsed = time.monotonic() - started

    job = jobs.get_job(jid)
    assert job["stage"] == "error", f"expected error, got {job['stage']}"
    assert job["error_code"] == "TRANSCRIBE_TIMEOUT", job["error_code"]
    assert marker.exists(), "child never reached the hang point"
    assert elapsed < DEADLINE_SECONDS + KILL_TOLERANCE_SECONDS, (
        f"stage took {elapsed:.1f}s; deadline enforcement failed")


# ── 2+3. Worker released; next queued job runs ─────────────────────

def test_worker_released_and_next_job_runs(isolated_data, monkeypatch, tmp_path):
    hang_marker = tmp_path / "hang-marker"
    success_marker = tmp_path / "success-marker"
    hang_wrapper = _write_wrapper(tmp_path, "hang_wrapper.py", HANG_WRAPPER)
    success_wrapper = _write_wrapper(
        tmp_path, "success_wrapper.py", SUCCESS_WRAPPER)

    _fake_render(monkeypatch, [])
    monkeypatch.setattr(jobs, "_build_thumbnail", lambda *a, **k: None)

    stuck_id = _make_job(isolated_data, stages=["download"])
    follow_id = _make_job(isolated_data, stages=["download"])
    monkeypatch.setattr(
        transcriber, "_child_command",
        _route_commands(
            {stuck_id: (hang_marker, hang_wrapper),
             follow_id: (success_marker, success_wrapper)},
            transcriber._child_command))

    results = {}

    def run(job_id):
        jobs._run(job_id)
        results[job_id] = jobs.get_job(job_id)

    threads = [threading.Thread(target=run, args=(stuck_id,), daemon=True),
               threading.Thread(target=run, args=(follow_id,), daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=JOIN_TIMEOUT)
        assert not t.is_alive(), "worker thread never finished"

    stuck = results[stuck_id]
    follow = results[follow_id]

    assert stuck["stage"] == "error"
    assert stuck["error_code"] == "TRANSCRIBE_TIMEOUT"
    assert hang_marker.exists(), "stuck child never armed"
    assert follow["stage"] == "done", (
        f"next queued job did not complete: {follow['stage']} "
        f"/ {follow.get('error_code')}")
    assert success_marker.exists(), "follow-up child never ran"
    # Slot really released: another worker can be acquired right now.
    assert jobs._slots.acquire(timeout=1), "worker slot was not released"
    jobs._slots.release()


# ── Unit: configuration surface without spawning processes ─────────

def test_supervised_deadline_uses_configured_seconds(supervision_on):
    assert config.TRANSCRIBE_DEADLINE_SECONDS == DEADLINE_SECONDS
    assert config.TRANSCRIBE_SUPERVISED is True
