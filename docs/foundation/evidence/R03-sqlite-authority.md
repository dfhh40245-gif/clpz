# R03 — SQLite is the recovery authority; edit_versions persisted

Date: 2026-09-18

## Contract

- `load_saved_jobs()` restores **committed SQLite state only**. The JSON
  snapshot is a derived copy with exactly one reader: one-time migration v4,
  which imports legacy JSON edit history into the schema and is guarded
  against re-running (no ghost resurrection, rollback on failure).
- A failed database read stops startup instead of silently promoting
  possibly-stale JSON to authority.
- Terminal rows whose project directory is missing are deleted as broken
  ghosts, together with their idempotency mappings.
- `edit_versions` is persisted in the authoritative schema: `jobs.edit_versions
  TEXT NOT NULL DEFAULT '[]'` (migration `_migrate_v4_edit_versions`,
  `backend/database.py`), written by `db.save_job`, restored by
  `db.get_all_jobs`.

## Reproduction of the original defect

Review probe: saved a done JSON snapshot, committed `cancelled` to SQLite,
cleared in-memory jobs and reloaded — recovered state said `done` while SQLite
said `cancelled`. A job with an edit version persisted to SQLite had no
`edit_versions` column value.

## Tests (`backend/tests/test_durability.py`)

- `test_restart_prefers_committed_sqlite_over_conflicting_snapshot` — the
  review's exact scenario: SQLite `cancelled` wins over a stale done JSON
  snapshot; `edit_versions` round-trips.
- `test_snapshot_failure_after_commit_recovers_sqlite` — snapshot write
  failure after a successful DB commit still recovers committed state.
- `test_restart_recovers_without_json_snapshot` — real-restart recovery with
  no JSON present.
- `test_restart_does_not_resurrect_deleted_job_from_snapshot`.
- `test_v4_migration_imports_only_legacy_edit_history` and
  `test_failed_v4_migration_rolls_back_and_retries` — the one-time migration
  and its rollback.
- `test_legacy_json_install_migrates_once_no_ghosts`.

## Results

- Focused: `python -m pytest tests/test_durability.py -q --tb=short` from
  `backend/` → **17 passed** (2026-09-18, this machine).
- Included in the full fast suite: **312 passed, 2 skipped, 9 deselected**
  (2026-09-18, this machine, exit 0).
- `py_compile` clean for `backend/database.py`, `backend/jobs.py`.
