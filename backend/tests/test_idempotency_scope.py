"""Task 09 — Scoped idempotency tests.

Acceptance checks under test:
- same key across different users and URL/upload operations does not
  deduplicate unrelated work (F09: cross-owner replay)
- same key with changed URL/options returns 409, not a different/stale job
- concurrent identical submissions create one job and one debit, and the
  mapping survives restart
- rejected uploads and cleanup never trap the key or double-charge
"""
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import credits as credits_mod
import database as db
import jobs as jobs_mod
from tests.test_remediation import isolated_data  # noqa: F401  (fixture)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "test_video_20s.mp4"


@pytest.fixture(autouse=True)
def isolated_worker_queue():
    """Each idempotency case gets a fresh pending-job budget."""
    jobs_mod.reset_for_testing()
    yield
    jobs_mod.reset_for_testing()


def _user_with_credits(prefix="idem", credits=10):
    uid = uuid.uuid4().hex
    db.create_user(uid, f"{prefix}_{uuid.uuid4().hex[:8]}@test.com", "h", "s")
    if credits:
        db.add_credits(uid, credits, txn_type="purchase")
    return uid


# ── Scope separation ───────────────────────────────────────────────

def test_same_key_different_users_no_cross_dedupe(isolated_data):
    """The F09 repro: user B replaying user A's key must create B's own job,
    not return A's job id."""
    uid_a = _user_with_credits("a09")
    uid_b = _user_with_credits("b09")

    url = "https://www.youtube.com/watch?v=aaaa"
    jid_a, new_a, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=uid_a, idempotency_key="shared-key")
    jid_b, new_b, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=uid_b, idempotency_key="shared-key")
    assert new_a and new_b, "both submissions should create their own jobs"
    assert jid_a != jid_b, "cross-owner key reuse deduplicated unrelated work"

    # Anonymous vs user: also distinct scopes.
    jid_anon, new_anon, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=None, idempotency_key="shared-key")
    assert new_anon
    assert jid_anon not in (jid_a, jid_b)


def test_same_user_same_key_same_payload_replays(isolated_data):
    uid = _user_with_credits("r09")
    url = "https://www.youtube.com/watch?v=bbbb"
    j1, new1, _ = jobs_mod.create_job_idempotent(
        url, 2, "hello", user_id=uid, idempotency_key="k1")
    j2, new2, _ = jobs_mod.create_job_idempotent(
        url, 2, "hello", user_id=uid, idempotency_key="k1")
    assert new1 and not new2
    assert j1 == j2


def test_same_user_same_key_changed_url_conflicts(isolated_data):
    uid = _user_with_credits("c09")
    jobs_mod.create_job_idempotent(
        "https://www.youtube.com/watch?v=cccc", 2, "", user_id=uid,
        idempotency_key="k-conf")
    with pytest.raises(jobs_mod.IdempotencyConflict):
        jobs_mod.create_job_idempotent(
            "https://www.youtube.com/watch?v=other", 2, "", user_id=uid,
            idempotency_key="k-conf")


def test_same_user_same_key_changed_options_conflicts(isolated_data):
    uid = _user_with_credits("o09")
    jobs_mod.create_job_idempotent(
        "https://www.youtube.com/watch?v=dddd", 2, "", user_id=uid,
        idempotency_key="k-opt")
    with pytest.raises(jobs_mod.IdempotencyConflict):
        jobs_mod.create_job_idempotent(
            "https://www.youtube.com/watch?v=dddd", 3, "", user_id=uid,
            idempotency_key="k-opt")
    with pytest.raises(jobs_mod.IdempotencyConflict):
        jobs_mod.create_job_idempotent(
            "https://www.youtube.com/watch?v=dddd", 2, "different text",
            user_id=uid, idempotency_key="k-opt")


def test_fingerprint_is_stable_and_distinct(isolated_data):
    f1 = jobs_mod.canonical_fingerprint("forge", "u", "2", "")
    f2 = jobs_mod.canonical_fingerprint("forge", "u", "2", "")
    f3 = jobs_mod.canonical_fingerprint("forge", "u", "3", "")
    f4 = jobs_mod.canonical_fingerprint("upload", "u", "2", "")
    assert f1 == f2 and f1 != f3 and f1 != f4


# ── Concurrency & restart ──────────────────────────────────────────

def test_concurrent_same_key_creates_one_job_one_charge(isolated_data):
    uid = _user_with_credits("cc09")
    url = "https://www.youtube.com/watch?v=conc"
    results = []
    barrier = threading.Barrier(10)

    def submit():
        barrier.wait()
        try:
            jid, is_new, _ = jobs_mod.create_job_idempotent(
                url, 2, "", user_id=uid, idempotency_key="conc-key")
            results.append((jid, is_new))
        except jobs_mod.IdempotencyConflict:
            pass

    threads = [threading.Thread(target=submit) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    ids = {jid for jid, _ in results}
    assert len(ids) == 1, f"concurrent submits created {len(ids)} jobs"
    assert any(is_new for _, is_new in results), "one submit must be the creator"
    assert db.get_credit_balance(uid) == 9, "exactly one debit expected"


def test_mapping_survives_restart(isolated_data):
    """The scoped mapping is durable: a 'restart' (fresh DB connection and
    reloaded jobs) still replays the original job id."""
    uid = _user_with_credits("rs09")
    url = "https://www.youtube.com/watch?v=restart"
    j1, _, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=uid, idempotency_key="restart-key")

    # Simulate restart: drop in-memory jobs and close the DB connection.
    with jobs_mod._lock:
        jobs_mod.JOBS.clear()
    db.close()
    db._conn = None

    j2, is_new, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=uid, idempotency_key="restart-key")
    assert not is_new
    assert j1 == j2, "scoped mapping did not survive restart"


# ── Upload behavior ────────────────────────────────────────────────

def test_idempotent_upload_requires_content_fingerprint(isolated_data):
    """Only the staged HTTP path may create an upload replay mapping (R04)."""
    with pytest.raises(ValueError, match="content_fingerprint"):
        jobs_mod.create_upload_job_idempotent(
            "video.mp4", 1, "", user_id=None, idempotency_key="missing-content"
        )


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture video missing")
def test_upload_replay_after_partial_failure_is_recoverable(isolated_data, monkeypatch):
    """A crashed upload (mapping saved, file never streamed) leaves the key
    recoverable: the hard-delete path removes the mapping so the retry
    creates a fresh job without trapping the user."""
    uid = _user_with_credits("up09")
    jid, is_new, _ = jobs_mod.create_upload_job_idempotent(
        "video.mp4", 1, "", user_id=uid, idempotency_key="up-key",
        content_fingerprint="recoverable-content")
    assert is_new

    # Simulate the crash-cleanup path used by the upload endpoint when the
    # body never arrives / is invalid: cancel, delete BOTH the job mapping
    # and the credit-level replay cache, then refund (task 09).
    jobs_mod.cancel_job(jid)
    db.delete_idempotency_job_by_key("up-key")
    db.delete_idempotency("up-key")
    from credits import refund
    refund(uid, config.COST_PER_FORGE, related_id=jid, reason="upload rejected")

    # Retry with the SAME key now creates a NEW job — no trap.
    jid2, is_new2, _ = jobs_mod.create_upload_job_idempotent(
        "video.mp4", 1, "", user_id=uid, idempotency_key="up-key",
        content_fingerprint="recoverable-content")
    assert is_new2 and jid2 != jid
    assert db.get_credit_balance(uid) == 10 - config.COST_PER_FORGE  # charged exactly once now


def test_content_fingerprint_detects_different_media(isolated_data, tmp_path):
    """Two uploads with the same key but different file content produce
    different content fingerprints (dedupe stays option-scoped at claim
    time, content digest is recorded for the durable contract)."""
    f1 = tmp_path / "a.mp4"
    f2 = tmp_path / "b.mp4"
    f1.write_bytes(b"media-one" * 1000)
    f2.write_bytes(b"media-two" * 1000)
    fp1 = jobs_mod.file_fingerprint(f1)
    fp2 = jobs_mod.file_fingerprint(f2)
    assert fp1 != fp2
    # Bounded memory: reading a large file in chunks must not blow up; verify
    # chunking yields the same digest as a one-shot hash of the same bytes.
    import hashlib
    assert fp1 == hashlib.sha256(f1.read_bytes()).hexdigest()


# ── Cleanup safety ─────────────────────────────────────────────────

def test_cleanup_does_not_evict_active_job_mapping(isolated_data, monkeypatch):
    uid = _user_with_credits("cl09")
    url = "https://www.youtube.com/watch?v=clean"
    jid, _, _ = jobs_mod.create_job_idempotent(
        url, 2, "", user_id=uid, idempotency_key="active-key")

    # Force the mapping to look ancient.
    with db._write() as conn:
        conn.execute("UPDATE idempotency_jobs SET created_at = ? WHERE key = 'active-key'",
                     (time.time() - 100000,))
        conn.commit()

    # With the job still active, cleanup must keep the mapping.
    db.cleanup_old_idempotency(active_job_ids={jid})
    assert db.get_job_id_for_idempotency(jobs_mod.idempotency_scope(uid), "active-key") == jid

    # Without active protection (job finished/gone), the old mapping goes.
    db.cleanup_old_idempotency(active_job_ids=set())
    assert db.get_job_id_for_idempotency(jobs_mod.idempotency_scope(uid), "active-key") is None


def test_legacy_unscoped_rows_never_match(isolated_data):
    """Pre-migration rows (scope='') must never be replayed by the scoped
    lookup — old data cannot dedupe new submissions."""
    with db._write() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_jobs (key, job_id, user_id, created_at, scope, fingerprint) "
            "VALUES ('legacy-key', 'legacy-job', NULL, ?, '', '')",
            (time.time(),),
        )
        conn.commit()
    assert db.get_job_id_for_idempotency("anon", "legacy-key") is None
    assert db.get_job_id_for_idempotency("user:someone", "legacy-key") is None
