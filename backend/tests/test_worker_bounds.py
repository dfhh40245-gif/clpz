"""Task 11 — bounded media workers and cancellation regression tests.

Covers the task 11 acceptance checks:
- a saturated queue refuses new submissions BEFORE charging (QueueFullError)
  and the admission bound self-heals once workers finish
- a wedged edit render that outlives its hard deadline is force-failed by
  the watchdog: subprocess killed, partial output removed, slot released
- edit renders share a bounded semaphore; concurrent bursts beyond the
  budget fail fast instead of growing worker load unbounded
- cancellation keeps its cooperative reason and stays terminal
- oversized webhook bodies are rejected before parsing (F13 ordering)
"""
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from unittest import mock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

import config  # noqa: E402
import credits as credits_mod  # noqa: E402
import database as db  # noqa: E402
import jobs  # noqa: E402
from tests.test_remediation import isolated_data  # noqa: F401, E402  (fixture)
from tests.conftest import TestServer  # noqa: E402


def _user_with_credits(prefix="w11", credits=10):
    uid = uuid.uuid4().hex
    db.create_user(uid, f"{prefix}_{uuid.uuid4().hex[:8]}@test.com", "h", "s")
    if credits:
        db.add_credits(uid, credits, txn_type="purchase")
    return uid


def _stub_pipeline(monkeypatch):
    """Stub every heavy stage so started jobs terminate quickly and fully
    offline (no yt-dlp network attempts, no real ffprobe/whisper)."""
    monkeypatch.setattr(
        jobs.downloader, "download",
        lambda url_, dest_dir, job_id="": {
            "path": str(dest_dir / "source.mp4"), "title": "t", "duration": 1.0})
    monkeypatch.setattr(
        jobs.transcriber, "transcribe",
        lambda path, progress_cb=None, job_dir=None, job_id="": {
            "language": "en", "segments": [], "words": []})
    monkeypatch.setattr(
        jobs.analyzer, "find_clips",
        lambda title, duration, segments, max_clips: [])


# ── Admission: a saturated queue refuses before charging ────────────────


def test_queue_full_refuses_before_charge(isolated_data, monkeypatch):
    """Real submissions remain counted while execution slots are occupied."""
    uid = _user_with_credits("qf11")
    _stub_pipeline(monkeypatch)
    blocked_workers = threading.Semaphore(0)
    monkeypatch.setattr(jobs, "_slots", blocked_workers)
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 2)

    first, new, _ = jobs.create_job_idempotent(
        "https://www.youtube.com/watch?v=qf11a", 2, "",
        user_id=uid, idempotency_key="qf-first")
    assert new and first
    second, new, _ = jobs.create_job_idempotent(
        "https://www.youtube.com/watch?v=qf11b", 2, "",
        user_id=uid, idempotency_key="qf-second")
    assert new and second
    assert jobs.queue_depth() == 2
    try:
        with pytest.raises(jobs.QueueFullError):
            jobs.create_job_idempotent(
                "https://www.youtube.com/watch?v=qf11c", 2, "",
                user_id=uid, idempotency_key="qf-third")

        # Only the two accepted submissions charged credits. A full-queue
        # rejection does not consume its idempotency key.
        assert db.get_credit_balance(uid) == 8
        duplicate, is_new, _ = jobs.create_job_idempotent(
            "https://www.youtube.com/watch?v=qf11b", 2, "",
            user_id=uid, idempotency_key="qf-second")
        assert duplicate == second and not is_new

        assert jobs.cancel_job(first)
        assert jobs.queue_depth() == 1
        replacement, is_new, _ = jobs.create_job_idempotent(
            "https://www.youtube.com/watch?v=qf11c", 2, "",
            user_id=uid, idempotency_key="qf-third")
        assert replacement and is_new and jobs.queue_depth() == 2
        assert db.get_credit_balance(uid) == 7
    finally:
        blocked_workers.release()
        blocked_workers.release()

    deadline = time.time() + 10
    while time.time() < deadline and jobs.queue_depth():
        time.sleep(0.05)
    assert jobs.queue_depth() == 0
    assert jobs.get_job(first)["stage"] == "cancelled"
    txns = [t for t in db.get_transactions(uid) if t.get("type") == "forge"]
    assert len(txns) == 3


def test_depth_bound_enforced_and_self_heals(isolated_data):
    """try_acquire_slot refuses past MAX_QUEUE_DEPTH and the reservation
    returns once the worker starts (admission accounting self-heals)."""
    with mock.patch.object(jobs, "MAX_QUEUE_DEPTH", 2):
        assert jobs.try_acquire_slot("a")
        assert jobs.try_acquire_slot("b")
        assert not jobs.try_acquire_slot("c"), "bound not enforced"
        # Dequeue job 'a': reservation retires.
        jobs._release_admission("a")
        jobs._release_admission("a")  # repeat must not free another job
        assert jobs.queue_depth() == 1
        assert jobs.try_acquire_slot("d"), "reservation did not self-heal"
        # Clean up this test's reservations (global counter).
        jobs._release_admission("b")
        jobs._release_admission("d")


def test_http_queue_saturation_and_cancel(monkeypatch):
    """The real API returns 503 while two jobs wait for zero workers."""
    monkeypatch.setenv("CLPZ_TEST_WORKERS", "0")
    monkeypatch.setenv("MAX_QUEUE_DEPTH", "2")
    server = TestServer()
    try:
        server.start()
        session = requests.Session()
        session.headers.update({"X-CLPZ-Capability": server.capability_token})
        signup = session.post(f"{server.base_url}/api/auth/signup", json={
            "email": f"r01_{uuid.uuid4().hex[:8]}@test.com",
            "password": "pass123456",
        }, timeout=10)
        assert signup.status_code == 200, signup.text

        def submit(index):
            return session.post(f"{server.base_url}/api/jobs", json={
                "url": f"https://youtube.com/watch?v=r01{index}",
                "max_clips": 1,
                "idempotency_key": f"r01-{index}",
            }, timeout=10)

        first, second = submit(1), submit(2)
        assert first.status_code == second.status_code == 200
        assert submit(3).status_code == 503
        balance = session.get(f"{server.base_url}/api/credits/balance", timeout=10)
        assert balance.json()["balance"] == 8
        jid = first.json()["job_id"]
        cancelled = session.post(f"{server.base_url}/api/jobs/{jid}/cancel", timeout=10)
        assert cancelled.status_code == 200
        assert submit(3).status_code == 200
        assert submit(4).status_code == 503
        retry = session.post(f"{server.base_url}/api/jobs/{jid}/retry", timeout=10)
        assert retry.status_code == 503
        second_jid = second.json()["job_id"]
        assert session.post(f"{server.base_url}/api/jobs/{second_jid}/cancel", timeout=10).status_code == 200
        retry = session.post(f"{server.base_url}/api/jobs/{jid}/retry", timeout=10)
        assert retry.status_code == 200
        assert submit(4).status_code == 503
    finally:
        server.stop()
        if server._data_dir:
            shutil.rmtree(server._data_dir, ignore_errors=True)


@pytest.mark.parametrize("terminal", ["done", "error"])
def test_reservation_and_worker_slot_release_on_terminal(isolated_data, monkeypatch, terminal):
    """A real submission frees its reservation and execution slot on exit."""
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    worker_slots = threading.Semaphore(1)
    monkeypatch.setattr(jobs, "_slots", worker_slots)
    finished = threading.Event()

    def finish(job_id):
        jobs._update(job_id, stage=terminal)
        finished.set()

    monkeypatch.setattr(jobs, "_run_pipeline", finish)
    job_id, is_new, _ = jobs.create_job_idempotent(
        f"https://youtube.com/watch?v=r01{terminal}", 1, "", user_id=None)
    assert is_new and job_id
    assert finished.wait(5)
    deadline = time.time() + 5
    acquired = worker_slots.acquire(blocking=False)
    while time.time() < deadline and not acquired:
        time.sleep(0.01)
        acquired = worker_slots.acquire(blocking=False)
    assert acquired, "worker slot leaked after terminal exit"
    assert jobs.queue_depth() == 0
    assert jobs.get_job(job_id)["stage"] == terminal
    worker_slots.release()


@pytest.mark.parametrize("kind", ["forge", "upload"])
def test_creation_failure_releases_reservation(isolated_data, monkeypatch, kind):
    """A failed persist before worker start cannot consume queue capacity."""
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    monkeypatch.setattr(jobs, "_persist", mock.Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        if kind == "forge":
            jobs.create_job_idempotent("https://youtube.com/watch?v=r01fail", 1, "", None)
        else:
            jobs.create_upload_job_idempotent("source.mp4", 1, "", None)
    assert jobs.queue_depth() == 0


def test_upload_cancel_and_start_failure_release_reservations(isolated_data, monkeypatch):
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    cancelled, _, _ = jobs.create_upload_job_idempotent("cancel.mp4", 1, "", None)
    assert jobs.queue_depth() == 1
    assert jobs.cancel_job(cancelled)
    assert jobs.queue_depth() == 0

    failed, _, _ = jobs.create_upload_job_idempotent("fail.mp4", 1, "", None)
    assert jobs.queue_depth() == 1
    monkeypatch.setattr(jobs, "_find_bin", lambda name: name)
    monkeypatch.setattr(jobs.proc_mod, "run", lambda *args, **kwargs: mock.Mock(stdout="1"))
    monkeypatch.setattr(jobs, "_update", mock.Mock(side_effect=OSError("persist failed")))
    with pytest.raises(OSError, match="persist failed"):
        jobs.start_uploaded_job(failed, "source.mp4", "fail.mp4")
    assert jobs.queue_depth() == 0


@pytest.mark.parametrize("kind", ["forge", "upload"])
def test_mapping_failure_cancels_refunds_and_releases(isolated_data, monkeypatch, kind):
    uid = _user_with_credits("mapfail")
    monkeypatch.setattr(jobs, "_slots", threading.Semaphore(0))
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    monkeypatch.setattr(db, "save_idempotency_job",
                        mock.Mock(side_effect=OSError("mapping failed")))
    key = f"mapfail-{kind}"
    with pytest.raises(OSError, match="mapping failed"):
        if kind == "forge":
            jobs.create_job_idempotent("https://youtube.com/watch?v=mapfail", 1, "",
                                       uid, idempotency_key=key)
        else:
            jobs.create_upload_job_idempotent("mapfail.mp4", 1, "", uid,
                                              idempotency_key=key,
                                              content_fingerprint="mapfail-content")
    assert jobs.queue_depth() == 0
    assert db.get_credit_balance(uid) == 10
    assert db.check_idempotency(key) is None


@pytest.mark.parametrize("kind", ["forge", "upload"])
def test_charge_exception_releases_reservation(isolated_data, monkeypatch, kind):
    uid = _user_with_credits("chargefail")
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    monkeypatch.setattr(credits_mod, "check_and_charge",
                        mock.Mock(side_effect=OSError("ledger unavailable")))
    with pytest.raises(OSError, match="ledger unavailable"):
        if kind == "forge":
            jobs.create_job_idempotent("https://youtube.com/watch?v=chargefail", 1, "", uid)
        else:
            jobs.create_upload_job_idempotent("chargefail.mp4", 1, "", uid)
    assert jobs.queue_depth() == 0


@pytest.mark.parametrize("kind", ["forge", "upload"])
def test_charge_commit_then_exception_refunds_and_releases(isolated_data, monkeypatch, kind):
    uid = _user_with_credits("commitfail")
    monkeypatch.setattr(jobs, "MAX_QUEUE_DEPTH", 1)
    original_charge = credits_mod.check_and_charge

    def charge_then_fail(*args, **kwargs):
        original_charge(*args, **kwargs)
        raise OSError("response lost after commit")

    monkeypatch.setattr(credits_mod, "check_and_charge", charge_then_fail)
    key = f"commitfail-{kind}"
    with pytest.raises(OSError, match="response lost after commit"):
        if kind == "forge":
            jobs.create_job_idempotent("https://youtube.com/watch?v=commitfail", 1,
                                       "", uid, idempotency_key=key)
        else:
            jobs.create_upload_job_idempotent("commitfail.mp4", 1, "", uid,
                                              idempotency_key=key,
                                              content_fingerprint="commitfail-content")
    assert jobs.queue_depth() == 0
    assert db.get_credit_balance(uid) == 10
    assert db.check_idempotency(key) is None


def test_admission_release_frees_depth_after_worker_starts(isolated_data, monkeypatch):
    """The full create->worker path retires its reservation so depth returns
    to 0 once the worker thread has started running."""
    uid = _user_with_credits("ar11")
    url = "https://www.youtube.com/watch?v=ar11"
    _stub_pipeline(monkeypatch)

    # The stubbed pipeline finds no clips -> terminal ANALYZER_EMPTY error.
    jid, is_new, _ = jobs.create_job_idempotent(
        url, 2, "", user_id=uid, idempotency_key="ar-key")
    assert is_new

    deadline = time.time() + 10
    while time.time() < deadline and jobs.queue_depth() != 0:
        time.sleep(0.05)
    assert jobs.queue_depth() == 0, "admission reservation leaked"
    jobs.reset_for_testing()


# ── Edit renders: bounded, deadline-enforced, watchdog-swept ───────────


def test_edit_semaphore_bounds_concurrent_renders():
    """The edit budget admits only EDIT_RENDER_CONCURRENCY holders; extra
    acquire attempts time out (HTTP 503 path)."""
    acquired = []
    deadline = time.time() + 5
    while len(acquired) < jobs.EDIT_RENDER_CONCURRENCY and time.time() < deadline:
        if jobs._edit_semaphore.acquire(blocking=False):
            acquired.append(1)
    assert len(acquired) == jobs.EDIT_RENDER_CONCURRENCY
    # Budget exhausted: a bounded-wait acquire must fail fast.
    assert not jobs._edit_semaphore.acquire(
        blocking=True, timeout=jobs.EDIT_QUEUE_WAIT_SECONDS)
    for _ in acquired:
        jobs._edit_semaphore.release()


def test_watchdog_sweep_kills_deadline_exceeded_render(monkeypatch, tmp_path):
    """A registered edit render past its deadline is force-failed: the job's
    subprocesses are killed and the partial output file is removed."""
    killed = {"job": None}
    monkeypatch.setattr(
        jobs.proc_mod, "kill_job",
        lambda job_id: killed.__setitem__("job", job_id) or 1)

    jid = "wdg" + uuid.uuid4().hex[:6]
    (tmp_path / jid).mkdir()
    stale = tmp_path / jid / "clip_0_edited_abcd1234.mp4"
    stale.write_bytes(b"partial")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    jobs.note_edit_started(jid, 0, "clip_0_edited_abcd1234.mp4")
    # Pretend the render started long ago and should already be dead.
    with jobs._edit_registry_lock:
        jobs._edit_registry[f"{jid}:0"]["deadline"] = time.monotonic() - 1

    jobs._watchdog_sweep()

    assert killed["job"] == jid, "watchdog did not kill the wedged render"
    assert not stale.exists(), "partial output must be removed"
    with jobs._edit_registry_lock:
        assert f"{jid}:0" not in jobs._edit_registry, "registration leaked"


def test_watchdog_leaves_healthy_renders_alone():
    jid = "ok" + uuid.uuid4().hex[:6]
    killed = []
    with mock.patch.object(jobs.proc_mod, "kill_job", lambda job_id: killed.append(job_id)):
        jobs.note_edit_started(jid, 1, "clip_1_edited.mp4")
        jobs._watchdog_sweep()  # deadline is in the future
        assert not killed
        jobs.note_edit_finished(jid, 1)  # normal completion path
        jobs._watchdog_sweep()
        assert not killed


def test_edit_deadline_error_maps_to_504():
    """The endpoint maps RenderTimeoutError to 504 (gateway timeout), not a
    generic 500 — matching the task's 'hard deadline, responsive API' gate."""
    from pathlib import Path as _P
    src = (_P(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    i = src.find("def edit_clip")
    j = src.find("\n@app.", i + 10)
    body = src[i:j]
    assert "EDIT_RENDER_DEADLINE_SECONDS" in body
    assert "504" in body and "RenderTimeoutError" in body


# ── Wedge survivability: the sweep hard-kills a stubborn child ──────────


def test_proc_kill_survives_stubborn_child(tmp_path):
    """proc.kill_job's tree-kill actually terminates a child that ignores
    SIGTERM (the F12 'cannot interrupt a stuck worker' class)."""
    wedge = tmp_path / "wedge.py"
    wedge.write_text(
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, str(wedge)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        assert proc.stdout.readline().strip() == "ready"
        import proc as proc_mod
        proc_mod.register("wedge-job", proc)
        proc_mod.kill_job("wedge-job")
        assert proc.poll() is not None, "stubborn child survived kill_job"
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


# ── Cancellation remains cooperative and terminal ───────────────────────


def test_cancelled_job_records_reason(isolated_data, monkeypatch):
    """Cancelled jobs end with the cooperative reason recorded, terminal."""
    uid = _user_with_credits("cx11")
    _stub_pipeline(monkeypatch)

    def slow_download(url_, dest_dir, job_id=""):
        # Sleep in small increments so cancellation is observed promptly.
        for _ in range(30):
            jobs._check_cancelled(job_id)
            time.sleep(0.1)
        return {"path": str(dest_dir / "s.mp4"), "title": "t", "duration": 1.0}

    monkeypatch.setattr(jobs.downloader, "download", slow_download)
    jid, _, _ = jobs.create_job_idempotent(
        "https://www.youtube.com/watch?v=cx11", 2, "",
        user_id=uid, idempotency_key="cx-key")
    # Wait until the worker has actually started (reservation retired).
    deadline = time.time() + 10
    while time.time() < deadline and jobs.queue_depth() != 0:
        time.sleep(0.05)
    assert jobs.cancel_job(jid) is True
    deadline = time.time() + 5
    job = None
    while time.time() < deadline:
        job = jobs.get_job(jid)
        if job and job["stage"] == "cancelled":
            break
        time.sleep(0.05)
    assert job and job["stage"] == "cancelled"
    assert "cancel" in (job.get("error") or "").lower()
    # Cancellation refunds nothing (user chose it) but the reservation is gone.
    assert jobs.queue_depth() == 0
    jobs.reset_for_testing()


def test_job_cancelled_after_webhook_sig_check():
    """F13 regression: the webhook size bound applies before payload parse."""
    from pathlib import Path as _P
    src = (_P(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    i = src.find("def gumroad_webhook")
    j = src.find("\n@app.", i + 10)
    body = src[i:j]
    cap_at = body.find("WEBHOOK_MAX_BYTES")
    parse_at = body.find("_parse_payload")
    assert 0 < cap_at < parse_at, "size cap must run before parsing"


# ── Transcriber audio extraction goes through proc.py (task 11 coverage) ─


def test_transcriber_extraction_uses_proc_registry(monkeypatch, tmp_path):
    """The chunked transcriber's ffmpeg audio extraction must register its
    child with proc.py so cancellation can terminate it (F12)."""
    import pipeline.transcriber as t
    import numpy as np

    # A long video routes through the chunked extraction path.
    monkeypatch.setattr(t, "_get_duration", lambda p, job_id="": 200.0)

    captured = {}

    def fake_extract(path, start, end, job_id=""):
        captured["job_id"] = job_id
        return np.zeros(t._SAMPLE_RATE, dtype=np.float32)

    monkeypatch.setattr(t, "_extract_audio_chunk", fake_extract)

    chunk_results = [
        {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
         "words": [{"start": 0.0, "end": 0.5, "word": "hello"}],
         "language": "en"},
    ]

    def fake_chunk(model, audio, offset, task, language=None):
        return (chunk_results.pop(0) if chunk_results
                else {"segments": [], "words": [], "language": "en"})

    monkeypatch.setattr(t, "_transcribe_chunk", fake_chunk)

    result = t.transcribe("dummy.mp4", job_dir=tmp_path, job_id="trans-job")
    assert captured["job_id"] == "trans-job", (
        "chunked audio extraction must run under the job's proc registry")
    assert result["segments"], "merged transcript lost the chunk segment"
    assert result["language"] == "en"
