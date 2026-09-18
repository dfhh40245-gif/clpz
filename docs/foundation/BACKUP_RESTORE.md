# Backup and restore runbook (CLPZ desktop)

Task 10 deliverable. All paths are relative to the application data
directory (`CLIPFORGE_DATA`; default `backend/data` for development,
`%LOCALAPPDATA%/CLPZ` when installed).

## What exists where

| Data | Authority | Backup form |
|---|---|---|
| Job/project records | SQLite `clpz.db` | `backups/clpz-<timestamp>-<id>.db` via `db.backup_database()` |
| job.json | Derived snapshot (restart recovery only) | included in project archives |
| Source media, transcripts, rendered clips, thumbnails | Filesystem `data/<job_id>/` | `project-backups/<job_id>-<timestamp>/` + `manifest.json` (SHA-256 per file) |

SQLite is the authoritative job store; `job.json` is a derived snapshot
replaced atomically (temp file + `os.replace`). Persist failures are logged
and, for the authoritative store, raised — a failed commit is never reported
as success.

## Backing up

```powershell
# From the repo root (dev), with the app stopped or running:
& .\.venv\Scripts\python.exe -c "
import sys; sys.path.insert(0, 'backend')
import os
os.environ.setdefault('CLIPFORGE_DATA', r'<data-dir>')
import database as db, jobs
b = db.backup_database()                      # versioned DB snapshot
print('DB backup:', b)
print('project archive:', jobs.backup_project('<job_id>'))
"
```

- Each run creates a NEW timestamped file; backups never overwrite each other.
- `VACUUM INTO` snapshots are consistent even while the app is writing.
- Destination paths may contain spaces and apostrophes.

## Restoring

1. **Validate, then restore to a NEW directory** (the live store is never
   touched):

   ```powershell
   & .\.venv\Scripts\python.exe -c "
   import sys; sys.path.insert(0, 'backend')
   import database as db
   print(db.validate_backup(r'<data-dir>\backups\clpz-XXXX.db'))
   print(db.restore_database(r'<data-dir>\backups\clpz-XXXX.db'))
   "
   ```

2. `restore_database` copies the backup to `<data>/restored-<timestamp>/clpz.db`,
   checkpoints WAL and re-runs integrity + schema checks. It refuses backups
   whose schema is NEWER than the running application or that fail
   `PRAGMA quick_check`.

3. **Switch over only after review:** stop the app, point `CLIPFORGE_DATA`
   at the restored directory (or copy `clpz.db` over the live one while
   stopped), start the app, open the Projects screen and spot-check playback
   of a restored clip. Keep the displaced live file until validation passes.

4. **Rollback:** restore the displaced live `clpz.db` (that is why step 3
   keeps it). Media directories are never modified by restore.

## Crash recovery

- A persistence failure during a save leaves the last committed state
  intact (SQLite transactional; job.json atomic replace) and surfaces an
  error instead of fake success.
- A crashed upload frees its idempotency key and refunds the charge
  (task 09); a recorded-but-unfulfilled payment completes exactly once on
  replay (task 08).
- If `clpz.db` is lost entirely, restore from the newest backup; projects
  whose media directories still exist are rehydrated at startup. Media-less
  rows are dropped, never shown as ghost projects.

## Reconciliation after any recovery

```powershell
& .\.venv\Scripts\python.exe scripts\reconcile_ledger.py --data-dir <data-dir>
```

Exit 0 = ledger consistent; exit 1 = mismatches listed (never auto-fixed).
