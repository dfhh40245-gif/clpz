# Task 10 — Make projects durable and backups restorable

Task: 10 (durability)
Commit: 76e4b0a (baseline; tasks 01–10 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64), NTFS
Runtime/tool/model versions: Python 3.12.14, SQLite (WAL)

## Scope and policy decisions

- **Authority contract implemented** (task step 1, per ADR-0001): SQLite
  `clpz.db` is the AUTHORITATIVE job/project record; `job.json` is a derived
  restart-recovery snapshot. Write order: SQLite first, snapshot second.
  This matches the existing ghost-project protection (filesystem is
  authoritative for media) — the store decision is now documented in code.
- **Failure semantics** (step 2): authoritative-store failures now RAISE
  (logged with job id); snapshot failures log and continue (the SQLite
  record is intact). Snapshot writes use temp-file + `os.replace`, so a
  crash mid-write can never leave a torn `job.json`.
- **Backup model** (step 3): versioned `VACUUM INTO` snapshots (timestamp +
  random suffix; no fixed `.db.bak` destination) plus per-project archives
  with a SHA-256 manifest covering source media, transcript, word timings,
  rendered clips and thumbnails.
- **Restore model** (step 4): restore goes to a NEW directory with
  validation; the live store is never overwritten in place by tooling.

## Original reproduction

`docs/foundation/probe_current.py` → `second_backup`:
`backup_database()` always targeted `<db>.db.bak`; the second run failed
(`VACUUM INTO` refuses to overwrite) and the path was interpolated into SQL
via f-string (apostrophe in path = broken SQL). `jobs._persist` swallowed
BOTH file and SQLite errors (`except OSError: pass` /
`except Exception: pass`), so a failed commit was reported as durable
success (F11).

## Files changed

- `backend/jobs.py` — `_persist` rewritten (atomic snapshot, error
  propagation, SQLite-first order); terminal pipeline handler no longer
  lets a persist failure skip the refund; NEW `backup_project()` archive
  with checksummed manifest (schema_version 1).
- `backend/database.py` — `backup_database(dest_dir)` versioned +
  apostrophe-safe SQL quoting; NEW `backup_schema_version()`,
  `validate_backup()` (quick_check + schema compatibility), `restore_database()`
  (validate → copy to new dir → WAL checkpoint → re-validate; never touches
  the live store).
- `docs/foundation/BACKUP_RESTORE.md` — NEW operator runbook.
- `backend/tests/test_durability.py` — NEW: 11 tests.

## Checks

| Acceptance item | Command / steps | Expected | Actual | Status |
|---|---|---|---|---|
| Two backups succeed, distinct destinations; spaces/quotes paths work | `pytest tests/test_durability.py -q` | 2 files, no collision; weird paths OK | `test_two_backups_succeed_distinct_destinations`, `test_backup_path_with_spaces_and_quotes` pass | PASS |
| Restore to separate directory; counts/checksums match | restore test + independent sqlite3 reopen | data equal; live file untouched | balance 42 == txn sum; `db._DB_PATH.read_bytes()` unchanged | PASS |
| Injected write failure: prior data survives, useful failure | `save_job` monkeypatched to raise `OperationalError` | exception propagates; committed stage 'done' intact; snapshot untorn | `test_persist_failure_propagates_and_prior_data_survives` pass | PASS |
| Legacy JSON/SQLite migration: no ghosts, no lost outputs | legacy job.json + stale DB row → `load_saved_jobs()` | legacy loaded; media-less row dropped from JOBS and DB | `test_legacy_json_install_migrates_once_no_ghosts` pass | PASS |
| Restore refuses incompatible/corrupt backups | future-schema and corrupt-file fixtures | restore rejected, nothing written | `test_restore_rejects_incompatible_schema` pass | PASS |
| Full suite regression | `pytest tests -m "not slow" -q` | all green | **225 passed, 1 skipped, 9 deselected** | PASS |

Restore decode caveat: restored-clip *playback* was verified to the extent
of checksum-identical copies plus SQLite reopen; a full decode of restored
media in a fresh install is part of the end-to-end journey (task 22).

## Migration and rollback

- No schema migration is added by this task (DB version stays 3 from task 09).
- Existing installations: no data conversion; backups begin accumulating
  under `<data>/backups/` and `project-backups/` when the new functions are
  used. `job.json` snapshots rewrite opportunistically in the new atomic
  format on the next persist.
- Rollback: previous code ignores the new directories; `_persist`'s old
  swallow-errors behavior returns on downgrade (defect F11 un-fixed but not
  corrupted data). Restore tooling is additive.

## Remaining blockers

- No scheduled/automatic backup policy exists (owner decision; the runbook
  documents manual operation). Disk-space growth from backups is unmanaged.
- End-to-end restore-then-decode on a clean install is deferred to the
  task 22 acceptance run.
- Windows file-locking while the app is running: `VACUUM INTO` works live,
  but overwriting the live `clpz.db` must only be done with the app stopped
  (documented in the runbook).

Artifact name and SHA-256: n/a (no packaged artifact).
Reviewer: pending owner review.

## R03 remediation — 2026-09-18

SQLite is now the recovery authority as well as the write authority. Startup
loads committed rows first, records interrupted jobs back to SQLite, and
atomically refreshes derived `job.json` snapshots. It does not import JSON on
ordinary restarts. Versioned schema migration v4 adds `jobs.edit_versions`,
copies legacy edit histories into existing SQLite rows without copying stale
status, and imports JSON-only projects once during upgrade. The previous
unversioned JSON import was removed so a leftover snapshot cannot recreate a
later committed deletion. A failed migration rolls back its DDL and closes the
connection; the next startup can retry.

| Check | Actual result | Status |
|---|---|---|
| Conflicting SQLite/JSON status and edit history, then close/reopen | committed SQLite `cancelled` status and edits recovered; snapshot refreshed | PASS |
| Snapshot write failure after SQLite commit, then close/reopen | committed state and edit history recovered | PASS |
| Missing JSON snapshot | SQLite row recovered and snapshot regenerated | PASS |
| Committed row deletion with stale snapshot | deleted project stayed deleted | PASS |
| v3 to v4 migration with stale JSON status | status stayed committed; legacy edit history imported | PASS |
| Injected failure during v4 DDL, then retry | schema marker and column rolled back; retry reached v4 | PASS |
| `pytest tests -m 'not slow' -q --tb=short` before the final transaction hardening | 278 passed, 2 skipped, 9 deselected | PASS |
| Focused durability/remediation/resume/library suites after transaction hardening | 48 passed, 1 skipped, 1 deselected | PASS |

The v4 migration is additive. Existing version 3 databases upgrade in place;
back up the database before deploying this change. A manual editor browser
restart and installed-app recovery run remain NOT RUN.
