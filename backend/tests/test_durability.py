"""Task 10 — Durable projects and restorable backups tests.

Acceptance checks under test:
- two backups succeed with distinct destinations; paths with spaces/quotes work
- restore to a separate directory; reopened data matches (counts/checksums)
- injected write failure during save: prior committed data survives,
  failures are not reported as durable success
- legacy JSON/SQLite installations migrate once, no ghost projects
"""
import json
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import database as db
import jobs as jobs_mod
from tests.test_remediation import isolated_data  # noqa: F401  (fixture)


# ── Versioned backups ──────────────────────────────────────────────

def test_two_backups_succeed_distinct_destinations(isolated_data):
    """The F11 repro: the second backup must not fail because the
    destination already exists."""
    db.create_user(uuid.uuid4().hex, "bk@test.com", "h", "s")  # ensure DB exists
    b1 = db.backup_database()
    b2 = db.backup_database()
    assert b1 is not None and b2 is not None
    assert b1 != b2, "backups must use distinct versioned destinations"
    assert b1.exists() and b2.exists()


def test_backup_path_with_spaces_and_quotes(isolated_data, tmp_path):
    db.create_user(uuid.uuid4().hex, "bq@test.com", "h", "s")
    weird = tmp_path / "dir with spaces & 'quotes'"
    weird.mkdir()
    b = db.backup_database(dest_dir=weird)
    assert b is not None and b.exists()
    # The backup is a readable SQLite database.
    conn = sqlite3.connect(str(b))
    try:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_backup_validates_schema_and_integrity(isolated_data):
    db.create_user(uuid.uuid4().hex, "bv@test.com", "h", "s")
    b = db.backup_database()
    report = db.validate_backup(b)
    assert report["integrity"] == "ok"
    assert report["compatible"] is True
    assert report["schema_version"] == db.schema_version()


def test_validate_rejects_corrupt_or_missing_backup(isolated_data, tmp_path):
    db.create_user(uuid.uuid4().hex, "bc@test.com", "h", "s")
    # Missing file
    r_missing = db.validate_backup(tmp_path / "nope.db")
    assert not r_missing["exists"] and r_missing["error"]
    # Corrupt file (valid SQLite header, garbage body)
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    r_corrupt = db.validate_backup(corrupt)
    assert r_corrupt["integrity"] != "ok" or r_corrupt["error"]


# ── Restore to a separate directory ────────────────────────────────

def test_restore_to_separate_directory_preserves_data(isolated_data, tmp_path):
    """Restore into a fresh directory; row counts and a checksummed row
    survive; the LIVE database file is untouched."""
    uid = uuid.uuid4().hex
    db.create_user(uid, "rs@test.com", "h", "s")
    db.add_credits(uid, 42, txn_type="purchase")
    live_before = db._DB_PATH.read_bytes()

    b = db.backup_database()
    target = tmp_path / "restored-here"
    report = db.restore_database(b, target)
    assert report["ok"], report
    assert report["restored_path"] == str(target / "clpz.db")
    assert Path(report["restored_path"]).exists()
    # Live data unchanged (never overwritten).
    assert db._DB_PATH.read_bytes() == live_before

    # Reopen the restored copy independently and compare counts/values.
    conn = sqlite3.connect(str(target / "clpz.db"))
    try:
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bal = conn.execute("SELECT balance FROM credits WHERE user_id = ?", (uid,)).fetchone()[0]
        txn_sum = conn.execute("SELECT SUM(amount) FROM credit_transactions WHERE user_id = ?", (uid,)).fetchone()[0]
    finally:
        conn.close()
    assert users == 1
    assert bal == 42 == txn_sum


def test_restore_rejects_incompatible_schema(isolated_data, tmp_path):
    db.create_user(uuid.uuid4().hex, "ri@test.com", "h", "s")
    # Forge a "backup" claiming a future schema version.
    future = tmp_path / "future.db"
    conn = sqlite3.connect(str(future))
    conn.execute("CREATE TABLE t (x)")
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()
    report = db.restore_database(future, tmp_path / "out")
    assert not report["ok"] and "newer" in report["error"]
    assert not (tmp_path / "out" / "clpz.db").exists()


# ── Persistence failure handling ───────────────────────────────────

def test_persist_failure_propagates_and_prior_data_survives(isolated_data):
    """A failed SQLite commit must not be reported as durable success, and
    the previously committed job state must survive intact."""
    uid = uuid.uuid4().hex
    job = {
        "id": uuid.uuid4().hex[:12],
        "created_at": time.time(),
        "stage": "done",
        "progress": 100.0,
        "user_id": None,
        "clips": [],
    }
    jobs_mod.JOBS[job["id"]] = job
    jobs_mod._persist(job)  # first save commits
    committed = json.loads((config.DATA_DIR / job["id"] / "job.json").read_text(encoding="utf-8"))
    assert committed["stage"] == "done"

    # Inject a write failure (disk-full style) on the next persist.
    orig_save = db.save_job

    def failing_save(j):
        raise sqlite3.OperationalError("database or disk is full")

    jobs_mod.db.save_job = failing_save
    try:
        with pytest.raises(sqlite3.OperationalError):
            job["stage"] = "error"
            jobs_mod._persist(job)
    finally:
        jobs_mod.db.save_job = orig_save

    # Prior committed data survives: DB row still 'done'.
    row = db.get_job(job["id"])
    assert row is not None and row["stage"] == "done"
    # job.json snapshot: atomic replace means the snapshot still holds the
    # last successfully written content ('done'), never a torn write.
    snapshot = json.loads((config.DATA_DIR / job["id"] / "job.json").read_text(encoding="utf-8"))
    assert snapshot["stage"] == "done"


def test_job_json_snapshot_atomic_replacement(isolated_data):
    """The snapshot writes to a temp file then os.replace — no torn reads."""
    job = {
        "id": uuid.uuid4().hex[:12],
        "created_at": time.time(),
        "stage": "queued",
        "progress": 0.0,
        "user_id": None,
        "clips": [],
    }
    jobs_mod.JOBS[job["id"]] = job
    jobs_mod._persist(job)
    job_file = config.DATA_DIR / job["id"] / "job.json"
    assert job_file.exists()
    assert not (config.DATA_DIR / job["id"] / "job.json.tmp").exists()
    for i in range(5):
        job["progress"] = float(i)
        jobs_mod._persist(job)
        data = json.loads(job_file.read_text(encoding="utf-8"))
        assert data["progress"] == float(i)


def test_restart_prefers_committed_sqlite_over_conflicting_snapshot(isolated_data):
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "created_at": time.time(), "stage": "done",
           "progress": 100.0, "clips": [], "edit_versions": [{"version": "v1"}]}
    jobs_mod._persist(job)
    stale = dict(job, stage="done", edit_versions=[])
    job["stage"] = "cancelled"
    job["edit_versions"] = [{"version": "v1"}, {"version": "v2"}]
    db.save_job(job)
    snapshot = config.DATA_DIR / job_id / "job.json"
    snapshot.write_text(json.dumps(stale), encoding="utf-8")

    jobs_mod.JOBS.clear()
    db.close()  # force a real SQLite reopen rather than a same-connection read
    jobs_mod.load_saved_jobs()

    recovered = jobs_mod.JOBS[job_id]
    assert recovered["stage"] == "cancelled"
    assert recovered["edit_versions"] == job["edit_versions"]
    assert json.loads(snapshot.read_text(encoding="utf-8"))["stage"] == "cancelled"
    assert db.get_job(job_id)["edit_versions"] == job["edit_versions"]


def test_snapshot_failure_after_commit_recovers_sqlite(isolated_data, monkeypatch):
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "created_at": time.time(), "stage": "done",
           "clips": [], "edit_versions": [{"version": "first"}]}
    jobs_mod._persist(job)
    snapshot = config.DATA_DIR / job_id / "job.json"
    before = snapshot.read_bytes()

    def no_snapshot(_job):
        raise OSError("synthetic snapshot disk error")

    monkeypatch.setattr(jobs_mod, "_write_job_snapshot", no_snapshot)
    job["stage"] = "cancelled"
    job["edit_versions"].append({"version": "second"})
    jobs_mod._persist(job)  # committed SQLite write still succeeds
    assert snapshot.read_bytes() == before
    jobs_mod.JOBS.clear()
    db.close()
    jobs_mod.load_saved_jobs()

    assert jobs_mod.JOBS[job_id]["stage"] == "cancelled"
    assert [v["version"] for v in jobs_mod.JOBS[job_id]["edit_versions"]] == ["first", "second"]


def test_restart_does_not_resurrect_deleted_job_from_snapshot(isolated_data):
    job_id = uuid.uuid4().hex[:12]
    jobs_mod._persist({"id": job_id, "created_at": time.time(),
                       "stage": "done", "clips": []})
    snapshot = config.DATA_DIR / job_id / "job.json"
    assert snapshot.exists()
    db.delete_job(job_id)  # crash before derived snapshot cleanup
    jobs_mod.JOBS.clear()
    db.close()

    db.migrate_from_json()
    jobs_mod.load_saved_jobs()

    assert db.get_job(job_id) is None
    assert job_id not in jobs_mod.JOBS


def test_restart_recovers_without_json_snapshot(isolated_data):
    job_id = uuid.uuid4().hex[:12]
    edit = {"version": "sqlite-only", "speed": 0.5}
    jobs_mod._persist({"id": job_id, "created_at": time.time(),
                       "stage": "done", "clips": [], "edit_versions": [edit]})
    (config.DATA_DIR / job_id / "job.json").unlink()
    jobs_mod.JOBS.clear()
    db.close()

    jobs_mod.load_saved_jobs()

    assert jobs_mod.JOBS[job_id]["edit_versions"] == [edit]
    assert (config.DATA_DIR / job_id / "job.json").exists()


def test_v4_migration_imports_only_legacy_edit_history(isolated_data):
    """Upgrade a v3 DB: preserve committed status while importing JSON edits."""
    job_id = uuid.uuid4().hex[:12]
    job = {"id": job_id, "created_at": time.time(), "stage": "cancelled",
           "clips": []}
    db.save_job(job)
    snapshot = config.DATA_DIR / job_id / "job.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(dict(job, stage="done",
                                        edit_versions=[{"version": "legacy"}])),
                        encoding="utf-8")
    conn = db._get_conn()
    conn.execute("ALTER TABLE jobs DROP COLUMN edit_versions")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    db.close()

    upgraded = db.get_job(job_id)
    assert db.schema_version() == 4
    assert upgraded["stage"] == "cancelled"
    assert upgraded["edit_versions"] == [{"version": "legacy"}]
    db.close()
    assert db.get_job(job_id)["edit_versions"] == [{"version": "legacy"}]


def test_failed_v4_migration_rolls_back_and_retries(isolated_data, monkeypatch):
    db.save_job({"id": uuid.uuid4().hex[:12], "created_at": time.time(),
                 "stage": "done", "clips": []})
    conn = db._get_conn()
    conn.execute("ALTER TABLE jobs DROP COLUMN edit_versions")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    db.close()
    real_migration = db._MIGRATIONS[3]

    def fail_after_column(connection):
        connection.execute("ALTER TABLE jobs ADD COLUMN edit_versions TEXT NOT NULL DEFAULT '[]'")
        raise RuntimeError("synthetic migration interruption")

    migrations = list(db._MIGRATIONS)
    migrations[3] = fail_after_column
    monkeypatch.setattr(db, "_MIGRATIONS", migrations)
    with pytest.raises(RuntimeError, match="synthetic migration interruption"):
        db._get_conn()
    assert db._conn is None
    with sqlite3.connect(str(db._DB_PATH)) as raw:
        assert raw.execute("PRAGMA user_version").fetchone()[0] == 3
        assert "edit_versions" not in {r[1] for r in raw.execute("PRAGMA table_info(jobs)")}

    migrations[3] = real_migration
    assert db.schema_version() == 4


# ── Project archive with manifest ──────────────────────────────────

def test_backup_project_creates_manifest_with_checksums(isolated_data):
    job_id = uuid.uuid4().hex[:12]
    d = config.DATA_DIR / job_id
    d.mkdir(parents=True)
    (d / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    (d / "clip_0.mp4").write_bytes(b"\x00\x01" * 512)
    (d / "source.mp4").write_bytes(b"source-bytes" * 64)
    job = {
        "id": job_id, "created_at": time.time(), "stage": "done",
        "input_type": "upload", "user_id": None, "clips": [],
        "video": {"path": str(d / "source.mp4"), "title": "T"},
    }
    jobs_mod.JOBS[job_id] = job

    out = jobs_mod.backup_project(job_id)
    assert out["ok"], out
    backup_dir = Path(out["path"])
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    names = {f["name"] for f in manifest["files"]}
    assert {"transcript.srt", "clip_0.mp4", "source.mp4"} <= names
    # Checksums are real SHA-256 of the copied files.
    import hashlib
    for f in manifest["files"]:
        content = (backup_dir / f["name"]).read_bytes()
        assert f["sha256"] == hashlib.sha256(content).hexdigest()
        assert f["size"] == len(content)
    # Original project files untouched (copy, not move).
    assert (d / "source.mp4").exists()
    # Manifest is staged atomically.
    assert not (backup_dir / "manifest.json.tmp").exists()


def test_backup_project_missing_job(isolated_data):
    out = jobs_mod.backup_project("does-not-exist")
    assert not out["ok"] and "not found" in out["error"]


# ── Legacy installation migration ──────────────────────────────────

def test_legacy_json_install_migrates_once_no_ghosts(isolated_data, tmp_path):
    """A legacy data dir with job.json snapshots only: startup loading keeps
    real projects and does not resurrect media-less DB rows (no ghosts)."""
    # Legacy project on disk, no DB row.
    legacy_id = uuid.uuid4().hex[:12]
    d = config.DATA_DIR / legacy_id
    d.mkdir(parents=True)
    legacy_job = {
        "id": legacy_id, "created_at": time.time(), "stage": "done",
        "input_type": "upload", "user_id": None, "clips": [
            {"index": 0, "status": "done", "file": str(d / "clip_0.mp4")},
        ],
        "video": {"path": str(d / "source.mp4"), "title": "Legacy"},
    }
    (d / "job.json").write_text(json.dumps(legacy_job), encoding="utf-8")
    (d / "clip_0.mp4").write_bytes(b"\x00" * 128)
    (d / "source.mp4").write_bytes(b"\x01" * 128)

    # A stale DB row whose media is gone.
    ghost_id = uuid.uuid4().hex[:12]
    db.save_job({"id": ghost_id, "created_at": time.time(), "stage": "done",
                 "user_id": None, "clips": []})

    jobs_mod.load_saved_jobs()

    with jobs_mod._lock:
        ids = set(jobs_mod.JOBS.keys())
    assert legacy_id in ids, "legacy JSON project was not loaded"
    assert ghost_id not in ids, "media-less DB row was resurrected as a ghost"
    # The ghost row was cleaned from SQLite too.
    assert db.get_job(ghost_id) is None
