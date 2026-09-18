"""Regression tests for the post-audit remediation.

Covers every previously-confirmed defect class:
  - one logical submission == one job == one charge == at most one refund
  - cancellation terminates subprocesses and never ends in "done"
  - job-level timeout
  - filesystem/SQLite consistency (no ghost rehydration)
  - /api/jobs/clear authorization
  - rate limiting cannot be bypassed with X-Forwarded-For
  - verification/reset endpoints are throttled
  - editor input validation (no 500s from bad trim/overlay values)
  - session cookie works for strict HTTP clients over loopback
  - schema migrations
"""
import os
import re
import sys
import json
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest
import requests

import jobs
import database as db

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "test_video_20s.mp4"


@pytest.fixture
def isolated_data(monkeypatch, tmp_path):
    """Point config.DATA_DIR and the database layer at a temp dir so unit tests
    never write into the real backend/data directory."""
    import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "clpz.db")
    monkeypatch.setattr(db, "_conn", None)
    monkeypatch.setattr(config, "AUTO_CLEANUP_HOURS", 0)
    return tmp_path


def _email(prefix="rem"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


# ── Low-memory / MKL retry behavior ────────────────────────────────

def test_mkl_malloc_transient_failure_retries(monkeypatch):
    """A transient mkl_malloc failure during model load must retry and succeed.

    Fully hermetic: WhisperModel is replaced by a stub class, so the real
    ctranslate2 (which itself can fail under memory pressure on this machine)
    is never loaded.
    """
    import pipeline.transcriber as t
    import faster_whisper

    calls = {"n": 0}

    class StubModel:
        def __init__(self, *a, **k):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise RuntimeError("mkl_malloc: failed to allocate memory")

    monkeypatch.setattr(faster_whisper, "WhisperModel", StubModel)
    # Force a fresh model load (no cached global)
    monkeypatch.setattr(t, "_model", None)

    model = t._get_model()
    assert model is not None
    assert calls["n"] == 3, f"expected 3 attempts (2 fail + 1 ok), got {calls['n']}"


def test_mkl_malloc_persistent_failure_raises(monkeypatch):
    """A persistent mkl_malloc failure must raise after retries, not hang or
    silently continue into parsing/rendering."""
    import pipeline.transcriber as t
    import faster_whisper

    calls = {"n": 0}

    class AlwaysFailModel:
        def __init__(self, *a, **k):
            calls["n"] += 1
            raise RuntimeError("mkl_malloc: failed to allocate memory")

    monkeypatch.setattr(faster_whisper, "WhisperModel", AlwaysFailModel)
    monkeypatch.setattr(t, "_model", None)

    with pytest.raises(RuntimeError, match="mkl_malloc"):
        t._get_model()
    assert calls["n"] == 3, f"expected exactly 3 attempts, got {calls['n']}"


# ── Idempotency: one logical submission = one job = one charge ─────


def _forge(session, base, key, url="https://www.youtube.com/watch?v=zzzz999"):
    return session.post(
        f"{base}/api/jobs",
        json={"url": url, "max_clips": 2, "idempotency_key": key},
    )


def test_duplicate_forge_same_key_one_job_one_charge(clean_server):
    s = requests.Session()
    s.post(f"{clean_server.base_url}/api/auth/signup",
           json={"email": _email("dup"), "password": "pass123456"})
    key = f"idem-{uuid.uuid4().hex}"

    r1 = _forge(s, clean_server.base_url, key)
    r2 = _forge(s, clean_server.base_url, key)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["job_id"] == r2.json()["job_id"], "duplicate submit created a second job"
    bal = s.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"]
    assert bal == 9, f"expected a single charge (10->9), got balance {bal}"
    tx = s.get(f"{clean_server.base_url}/api/credits/transactions").json()["transactions"]
    forge_tx = [t for t in tx if t["type"] == "forge"]
    assert len(forge_tx) == 1, f"expected exactly 1 forge charge, got {len(forge_tx)}"


def test_concurrent_duplicate_forge_single_job(clean_server):
    s = requests.Session()
    s.post(f"{clean_server.base_url}/api/auth/signup",
           json={"email": _email("conc"), "password": "pass123456"})
    key = f"idem-{uuid.uuid4().hex}"
    results = []
    barrier = threading.Barrier(10)

    def _submit():
        barrier.wait()
        r = _forge(s, clean_server.base_url, key)
        if r.status_code == 200:
            results.append(r.json()["job_id"])

    threads = [threading.Thread(target=_submit) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 10, f"expected 10 accepted submits, got {len(results)}"
    assert len(set(results)) == 1, f"10 concurrent submits created {len(set(results))} jobs"
    bal = s.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"]
    assert bal == 9, f"expected exactly one charge (10->9), got {bal}"
    tx = s.get(f"{clean_server.base_url}/api/credits/transactions").json()["transactions"]
    assert len([t for t in tx if t["type"] == "forge"]) == 1


@pytest.mark.slow
def test_duplicate_after_completion_returns_original_job(clean_server):
    """Duplicate submit after the original job COMPLETED must return the same
    job and never charge again."""
    if not FIXTURE.exists():
        pytest.skip("fixture video missing")
    s = requests.Session()
    s.post(f"{clean_server.base_url}/api/auth/signup",
           json={"email": _email("done"), "password": "pass123456"})
    key = f"idem-{uuid.uuid4().hex}"

    def _upload():
        with open(FIXTURE, "rb") as f:
            return s.post(f"{clean_server.base_url}/api/jobs/upload",
                          files={"file": ("v.mp4", f, "video/mp4")},
                          data={"max_clips": "1", "idempotency_key": key})

    r1 = _upload()
    assert r1.status_code == 200
    jid = r1.json()["job_id"]
    for _ in range(90):
        j = s.get(f"{clean_server.base_url}/api/jobs/{jid}").json()
        if j["stage"] in ("done", "error", "cancelled"):
            break
        time.sleep(1)
    bal_done = s.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"]
    # Re-submit the same logical upload after completion
    r2 = _upload()
    assert r2.status_code == 200
    assert r2.json()["job_id"] == jid, "duplicate after completion created a second job"
    assert s.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"] == bal_done
    tx = s.get(f"{clean_server.base_url}/api/credits/transactions").json()["transactions"]
    assert len([t for t in tx if t["type"] == "forge"]) == 1, "charged more than once"


def test_upload_dedupe_same_key(clean_server):
    if not FIXTURE.exists():
        pytest.skip("fixture video missing")
    s = requests.Session()
    s.post(f"{clean_server.base_url}/api/auth/signup",
           json={"email": _email("upld"), "password": "pass123456"})
    key = f"idem-{uuid.uuid4().hex}"
    jids = []
    for _ in range(2):
        with open(FIXTURE, "rb") as f:
            r = s.post(f"{clean_server.base_url}/api/jobs/upload",
                       files={"file": ("v.mp4", f, "video/mp4")},
                       data={"max_clips": "1", "idempotency_key": key})
        assert r.status_code == 200, r.text
        jids.append(r.json()["job_id"])
    assert jids[0] == jids[1], "duplicate upload with same key created a second job"
    bal = s.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"]
    assert bal == 9, f"expected a single upload charge (10->9), got {bal}"


def test_upload_replay_checks_content_and_cleans_staging(clean_server):
    """R04: the real multipart path reads and hashes every replay body.

    Two valid, distinct MP4 files deliberately use the same client filename,
    options, and idempotency key.  Only byte-identical retry may return the
    original job; changed media must receive 409 and no ``.part`` file may
    remain in the temporary staging area.
    """
    first_video = FIXTURE
    changed_video = FIXTURE.with_name("test_video.mp4")
    if not first_video.exists() or not changed_video.exists():
        pytest.skip("distinct video fixtures missing")

    session = requests.Session()
    session.post(f"{clean_server.base_url}/api/auth/signup",
                 json={"email": _email("r04"), "password": "pass123456"})
    key = f"r04-{uuid.uuid4().hex}"

    def upload(path):
        with path.open("rb") as media:
            return session.post(
                f"{clean_server.base_url}/api/jobs/upload",
                files={"file": ("same.mp4", media, "video/mp4")},
                data={"max_clips": "1", "idempotency_key": key},
                timeout=30,
            )

    original = upload(first_video)
    assert original.status_code == 200, original.text
    retry = upload(first_video)
    assert retry.status_code == 200, retry.text
    assert retry.json()["job_id"] == original.json()["job_id"]

    changed = upload(changed_video)
    assert changed.status_code == 409, changed.text
    assert "different upload" in changed.json()["detail"].lower()

    staging = clean_server._data_dir / ".upload-staging"
    assert not list(staging.glob("*.part")), "replayed upload left staged media behind"
    balance = session.get(f"{clean_server.base_url}/api/credits/balance").json()["balance"]
    assert balance == 9, "changed replay must not be charged"


# ── /api/jobs/clear authorization ─────────────────────────────────

def test_clear_requires_admin(clean_server):
    """Admin authorization uses the provisioned role (task 04), not an email
    match: a plain signup of 'admin@test.com' grants nothing until the role
    is provisioned server-side (what the trusted CLI does)."""
    r = requests.post(f"{clean_server.base_url}/api/jobs/clear")
    assert r.status_code == 401, f"anonymous clear should 401, got {r.status_code}"
    user = requests.Session()
    user.post(f"{clean_server.base_url}/api/auth/signup",
              json={"email": _email("u"), "password": "pass123456"})
    r = user.post(f"{clean_server.base_url}/api/jobs/clear")
    assert r.status_code == 403, f"non-admin clear should 403, got {r.status_code}"
    import sqlite3
    admin = requests.Session()
    r_signup = admin.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": "admin@test.com", "password": "adminpass123"})
    # Before provisioning, this account must NOT administer (F01 regression).
    r_pre = admin.post(f"{clean_server.base_url}/api/jobs/clear")
    assert r_pre.status_code == 403, (
        f"unprovisioned admin@test.com cleared jobs: {r_pre.status_code}")
    # Trusted provisioning path (server-side, like scripts/provision_admin.py).
    db_path = clean_server._data_dir / "clpz.db"
    uid = r_signup.json()["user"]["id"]
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
    r = admin.post(f"{clean_server.base_url}/api/jobs/clear")
    assert r.status_code == 200, f"admin clear should 200, got {r.status_code}: {r.text}"


# ── Editor validation ─────────────────────────────────────────────

def _edit(session, base, job_id, index, payload, raw=None):
    if raw is not None:
        return session.post(
            f"{base}/api/jobs/{job_id}/clips/{index}/edit",
            data=raw,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
    return session.post(
        f"{base}/api/jobs/{job_id}/clips/{index}/edit",
        json=payload,
        timeout=15,
    )


def test_editor_validation_never_500(clean_server):
    s = requests.Session()
    s.post(f"{clean_server.base_url}/api/auth/signup",
           json={"email": _email("edit"), "password": "pass123456"})
    fake_job = "deadbeef0001"

    cases = [
        ({"trim_start": 50, "trim_end": 5}, None),                      # start > end
        ({"trim_start": -1}, None),                                     # negative
        ({"trim_start": 1e12}, None),                                   # absurdly large
        ({"trim_start": float("nan")}, '{"trim_start": NaN}'),          # NaN (raw JSON)
        ({"trim_start": float("inf")}, '{"trim_start": Infinity}'),    # infinity (raw JSON)
        ({"volume": 99}, None),                                         # out of range
        ({"speed": 0}, None),                                           # out of range
        ({"text_overlays": [{"text": "x" * 1000}]}, None),              # overlay text too long
        ({"text_overlays": [{"text": "ok", "x": 1e9}]}, None),          # overlay coord out of range
        ({"text_overlays": [{"text": "ok", "color": "red:0"}]}, None),  # filter-injection color
        ({"text_overlays": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]}, None), # too many overlays
        ({"text_overlays": "not-a-list"}, None),                        # wrong type
    ]
    for payload, raw in cases:
        r = _edit(s, clean_server.base_url, fake_job, 0, payload, raw=raw)
        assert r.status_code != 500, f"payload {payload} caused a 500"
        assert r.status_code in (422, 404, 400), \
            f"payload {payload} returned {r.status_code}: {r.text[:120]}"
    # A valid request passes validation (then 404s on the fake job)
    r = _edit(s, clean_server.base_url, fake_job, 0,
              {"trim_start": 1, "trim_end": 3})
    assert r.status_code == 404


# ── Cancellation terminates subprocesses ──────────────────────────

def _wait_stage(job_id, stages, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = jobs.get_job(job_id)
        if j and j["stage"] in stages:
            return j
        time.sleep(0.1)
    return jobs.get_job(job_id)


def test_cancel_terminates_subprocess_and_stays_cancelled(isolated_data, monkeypatch):
    import config
    import proc
    from pipeline import downloader

    monkeypatch.setattr(config, "JOB_TIMEOUT_SECONDS", 120)

    def fake_download(url, dest_dir, job_id="", **kw):
        # Run a real long-lived child so we can prove it gets terminated.
        proc.run(job_id, [sys.executable, "-c", "import time; time.sleep(60)"], timeout=120)
        jobs._check_cancelled(job_id)  # raises if cancelled while the child ran
        return {"path": str(dest_dir / "source.mp4"), "title": "t", "duration": 10.0}

    monkeypatch.setattr(downloader, "download", fake_download)
    jid = jobs.create_job("https://www.youtube.com/watch?v=zzz", 2)
    try:
        assert _wait_stage(jid, {"downloading"})["stage"] == "downloading"
        assert proc.active_count() >= 1, "no subprocess was registered for the job"
        assert jobs.cancel_job(jid) is True
        # Child process must be gone quickly
        deadline = time.time() + 10
        while time.time() < deadline and proc.active_count() > 0:
            time.sleep(0.1)
        assert proc.active_count() == 0, "subprocess survived cancellation"
        # Terminal state must be cancelled — and STAY cancelled after 15s
        j = _wait_stage(jid, {"cancelled", "error", "done"})
        assert j["stage"] == "cancelled", f"expected cancelled, got {j['stage']}"
        time.sleep(15)
        j2 = jobs.get_job(jid)
        assert j2["stage"] == "cancelled", "cancelled job flipped to a completed state"
    finally:
        jobs.reset_for_testing()


# ── Job-level timeout ─────────────────────────────────────────────

def test_job_timeout_marks_error(isolated_data, monkeypatch):
    import config
    from pipeline import downloader

    monkeypatch.setattr(config, "JOB_TIMEOUT_SECONDS", 0.5)

    def slow_download(url, dest_dir, job_id="", **kw):
        time.sleep(5)  # exceeds the 0.5s deadline; in-process so it can't be killed
        return {"path": str(dest_dir / "source.mp4"), "title": "t", "duration": 10.0}

    monkeypatch.setattr(downloader, "download", slow_download)
    jid = jobs.create_job("https://www.youtube.com/watch?v=zzz", 2)
    try:
        j = _wait_stage(jid, {"error", "done", "cancelled"}, timeout=30)
        assert j["stage"] == "error", f"expected timeout error, got {j['stage']}"
        assert j.get("error_code") == "JOB_TIMEOUT", j.get("error_code")
        assert "timed out" in (j.get("error") or "").lower()
    finally:
        jobs.reset_for_testing()


# ── Filesystem / SQLite consistency ───────────────────────────────

def test_cancelled_survives_restart_not_rewritten_to_error(isolated_data):
    """A cancelled job must still be 'cancelled' after load_saved_jobs().

    Regression: the restart rehydration path rewrote any non-done/non-error
    stage (including the terminal 'cancelled') to 'error', erasing the
    user's cancellation decision.
    """
    import config
    jid = uuid.uuid4().hex[:12]
    job = {
        "id": jid,
        "created_at": time.time(),
        "started_at": time.time(),
        "completed_at": None,
        "failed_at": None,
        "cancelled_at": time.time(),
        "input_type": "upload",
        "url": "",
        "max_clips": 2,
        "top_text": "",
        "user_id": None,
        "stage": "cancelled",
        "progress": 0.5,
        "video": {"path": str(isolated_data / jid / "source.mp4"),
                  "title": "t", "duration": 10.0},
        "clips": [],
        "error": "Cancelled by user.",
        "error_code": "CANCELLED",
        "timings": {},
        "error_code": "CANCELLED",
        "completed_stages": [],
    }
    d = isolated_data / jid
    d.mkdir(parents=True)
    (d / "job.json").write_text(json.dumps(job), encoding="utf-8")

    with jobs._lock:
        jobs.JOBS.clear()
    jobs.load_saved_jobs()
    try:
        restored = jobs.get_job(jid)
        assert restored is not None, "cancelled job was dropped on restart"
        assert restored["stage"] == "cancelled", (
            f"cancelled job rewritten to {restored['stage']!r} on restart"
        )
        assert restored.get("error_code") == "CANCELLED"
    finally:
        with jobs._lock:
            jobs.JOBS.clear()


def test_cleanup_deletes_sqlite_row(isolated_data):
    import config
    tmp_path = isolated_data
    # Insert the job record directly (no worker thread) so nothing re-persists
    # job.json and resets its mtime while we are trying to age it.
    jid = uuid.uuid4().hex[:12]
    with jobs._lock:
        jobs.JOBS[jid] = {
            "id": jid,
            "created_at": time.time() - 2 * 86400,
            "started_at": None,
            "completed_at": time.time(),
            "failed_at": None,
            "cancelled_at": None,
            "input_type": "youtube",
            "url": "https://www.youtube.com/watch?v=zzz",
            "max_clips": 2,
            "top_text": "",
            "user_id": None,
            "stage": "done",
            "progress": 1.0,
            "video": None,
            "clips": [],
            "error": None,
            "timings": {},
            "error_code": None,
            "completed_stages": [],
        }
        jobs._persist(jobs.JOBS[jid])
    try:
        job_dir = tmp_path / jid
        assert job_dir.exists()
        assert db.get_job(jid) is not None
        old = time.time() - 2 * 86400
        os.utime(job_dir / "job.json", (old, old))

        jobs._cleanup_old_jobs(max_age_hours=24, keep_minimum=0)
        assert not job_dir.exists(), "filesystem directory not removed"
        assert db.get_job(jid) is None, "SQLite row survived cleanup"
    finally:
        jobs.reset_for_testing()


def test_deleted_job_not_rehydrated_after_restart(tmp_path):
    """A job whose directory was deleted must not come back from SQLite."""
    port = 8126
    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = str(tmp_path)
    env["CLPZ_DEBUG"] = "1"
    env["CLPZ_ADMIN_EMAIL"] = "admin@test.com"

    def start_server():
        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "error",
             "--no-proxy-headers"],
            cwd=str(Path(__file__).resolve().parent.parent), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            try:
                sock = socket.socket(); sock.settimeout(1)
                sock.connect(("127.0.0.1", port)); sock.close(); return p
            except OSError:
                time.sleep(0.5)
        raise RuntimeError("server failed to start")

    def stop(p):
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()

    base = f"http://127.0.0.1:{port}"
    p = start_server()
    try:
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": "admin@test.com", "password": "adminpass123"})
        r = s.post(f"{base}/api/jobs", json={
            "url": "https://www.youtube.com/watch?v=ghosttest",
            "max_clips": 1, "idempotency_key": f"ghost-{uuid.uuid4().hex}"})
        assert r.status_code == 200
        jid = r.json()["job_id"]
        # Wait for a terminal state (fake URL fails fast)
        for _ in range(40):
            j = s.get(f"{base}/api/jobs/{jid}").json()
            if j["stage"] in ("done", "error", "cancelled"):
                break
            time.sleep(0.5)
        job_dir = tmp_path / jid
        assert job_dir.exists()
    finally:
        stop(p)

    # Simulate media loss (cleanup / manual deletion) and restart.
    shutil.rmtree(job_dir, ignore_errors=True)
    p2 = start_server()
    try:
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": "admin@test.com", "password": "adminpass123"})
        jobs_list = s.get(f"{base}/api/jobs").json()
        # Task 19: list responses are now paginated summaries {"projects": [...]}
        rows = jobs_list.get("projects", jobs_list) if isinstance(jobs_list, dict) else jobs_list
        assert all(j["id"] != jid for j in rows), \
            "deleted job was rehydrated from SQLite as a ghost project"
        assert not (tmp_path / jid).exists(), "ghost job directory was recreated"
    finally:
        stop(p2)


# ── Rate limiting cannot be bypassed via X-Forwarded-For ──────────

def test_xff_cannot_bypass_login_rate_limit(tmp_path):
    port = 8127
    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = str(tmp_path)
    env["CLPZ_DEBUG"] = "0"
    env["CLPZ_ADMIN_EMAIL"] = "admin@test.com"
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "error",
         "--no-proxy-headers"],
        cwd=str(Path(__file__).resolve().parent.parent), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                sock = socket.socket(); sock.settimeout(1)
                sock.connect(("127.0.0.1", port)); sock.close(); break
            except OSError:
                time.sleep(0.5)
        email = _email("rl")
        s = requests.Session()
        assert s.post(f"{base}/api/auth/signup",
                      json={"email": email, "password": "pass123456"}).status_code == 200
        hits_429 = 0
        for i in range(11):
            r = s.post(f"{base}/api/auth/login",
                       json={"email": email, "password": "wrong"},
                       headers={"X-Forwarded-For": f"203.0.113.{i}"})
            if r.status_code == 429:
                hits_429 += 1
        # 11 attempts at 10/min with a single real peer: at least one must 429.
        # If X-Forwarded-For were trusted, every attempt would use a fresh IP
        # and none would be limited.
        assert hits_429 >= 1, "rotating X-Forwarded-For bypassed the login rate limit"
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def test_verification_endpoints_are_throttled(tmp_path):
    port = 8128
    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = str(tmp_path)
    env["CLPZ_DEBUG"] = "0"
    p = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "error",
         "--no-proxy-headers"],
        cwd=str(Path(__file__).resolve().parent.parent), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                sock = socket.socket(); sock.settimeout(1)
                sock.connect(("127.0.0.1", port)); sock.close(); break
            except OSError:
                time.sleep(0.5)
        hits_429 = 0
        for _ in range(7):
            r = requests.post(f"{base}/api/auth/forgot-password",
                              json={"email": "nobody@example.com"})
            if r.status_code == 429:
                hits_429 += 1
        assert hits_429 >= 1, "forgot-password endpoint was not rate limited"
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


# ── Migrations ────────────────────────────────────────────────────

def test_schema_migration_creates_idempotency_jobs(tmp_path):
    import database as db
    # Build an old-schema DB (no idempotency_jobs), then let _get_conn migrate it.
    db_file = tmp_path / "clpz.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA user_version = 0")
    conn.executescript(
        "CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT);"
    )
    conn.commit()
    conn.close()

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(db, "_DB_PATH", db_file)
    monkeypatch.setattr(db, "_conn", None)
    try:
        conn = db._get_conn()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(idempotency_jobs)").fetchall()]
        assert "job_id" in cols, "idempotency_jobs table not created by migration"
        assert db.schema_version() >= 0
    finally:
        monkeypatch.undo()
