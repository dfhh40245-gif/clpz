# Task 09 — Scope retries and duplicate requests correctly

Task: 09 (request idempotency)
Commit: 76e4b0a (baseline; tasks 01–09 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14, SQLite (WAL)

## Scope and policy decisions

- **Scope contract** (task step 1): every idempotency mapping is keyed by
  `(scope, key)` where scope = `user:<account_id>` for logged-in callers or
  `anon` for the anonymous desktop workspace. Identity lifetime is
  intentional: local accounts are per-machine (D11), and anonymous work
  belongs to the local workspace. Keys are additionally bound to the
  operation ("forge"/"upload") and a canonical SHA-256 payload fingerprint,
  so a shared key *string* can never merge unrelated work.
- **Fingerprint contract** (step 2): forge requests fingerprint
  (operation, url, max_clips, top_text) joined with a unit separator.
  Uploads fingerprint (operation, filename, max_clips, top_text) at claim
  time; after streaming, the file CONTENT digest (SHA-256 read in 1 MiB
  chunks, never buffered whole) is recorded on the mapping. Same scoped key
  + changed options → HTTP 409; exact same request → original job, no
  second charge.
- **Rejection/cleanup behavior** (step 4): an invalid/rejected/oversized
  upload deletes BOTH the scoped job mapping and the credit-level replay
  cache, then refunds. The vanilla UI keeps ONE stable idempotency key per
  logical submission across retries, resets it when the user picks a new
  file/edits the URL, and clears it on 409 so users are never trapped.
- Cleanup no longer evicts mappings for active jobs regardless of age.

## Original reproduction

`docs/foundation/probe_current.py` → `cross_owner_replay`: anonymous replay
of another account's key returned HTTP 200 with the SAME job id
(`same_job: true`; read access still 404). Keys were globally mapped
(`backend/jobs.py` `create_job_idempotent`/`create_upload_job_idempotent`,
`backend/database.py` `idempotency_jobs` with `key TEXT PRIMARY KEY`), not
bound to principal/operation/payload.

## Files changed

- `backend/database.py` — migration v3: `idempotency_jobs` rebuilt with
  `PRIMARY KEY (scope, key)`, new `scope`/`fingerprint` columns, legacy rows
  migrated (`INSERT OR REPLACE` dedupes repeated legacy keys; pre-migration
  rows keep `scope=''` and never match scoped lookups). Fresh-schema DDL
  creates the scoped table directly. Migration framework hardened: entries
  are now **idempotent functions** and a version marker ahead of the list
  (possible only from unshipped dev iterations) re-converges instead of
  failing. Scoped lookups `get_job_id_for_idempotency(scope, key)`,
  `get_idempotency_fingerprint(scope, key)`;
  `save_idempotency_job(..., scope, fingerprint)`;
  `cleanup_old_idempotency(active_job_ids)` protects active jobs.
- `backend/jobs.py` — `IdempotencyConflict`, `idempotency_scope()`,
  `canonical_fingerprint()`, `file_fingerprint()` (bounded 1 MiB chunks);
  both `create_*_idempotent` functions are scope- and fingerprint-aware;
  conflict raises map to 409 upstream.
- `backend/main.py` — `/api/jobs` and `/api/jobs/upload` catch
  `IdempotencyConflict` → HTTP 409; upload rejection/oversize/stream-failure
  paths clear the job mapping AND the credit replay cache (found via test:
  otherwise a retry replays the old charge result and creates a job for
  free); post-stream content digest recorded on the mapping.
- `frontend/clpz.html` — stable per-submission key (kept across retries of
  the same logical request), reset on new file/URL edit, cleared on 409;
  `api()` now attaches `err.status`.
- `backend/tests/test_idempotency_scope.py` — NEW: 11 tests.

## Checks

| Acceptance item | Command / steps | Expected | Actual | Status |
|---|---|---|---|---|
| Same key across users/operations never dedupes unrelated work | `pytest tests/test_idempotency_scope.py -q` + manual F09 repro | each principal gets its own job | user B own job=True new=True; anon own job=True | PASS |
| Same key + changed URL/options/file → 409 | changed-url/options tests + `IdempotencyConflict`→409 mapping | 409, no stale job | conflict raised; main.py maps to 409 | PASS |
| Concurrent identical submissions: one job, one debit, across restart | 10-thread barrier test + restart test (JOBS cleared, DB connection reset) | 1 job id, 1 debit, replay after restart returns original | `test_concurrent_same_key_creates_one_job_one_charge`, `test_mapping_survives_restart` | PASS |
| Rejected uploads and cleanup never trap users / double-charge | oversize/invalid-upload paths clear mapping+cache then refund; cleanup keeps active mappings | retry with same key works; charged exactly once; active mapping survives cleanup | upload-recovery test passes; `test_cleanup_does_not_evict_active_job_mapping` passes | PASS |
| Full suite regression | `pytest tests -m "not slow" -q` (backend) | all green | **214 passed, 1 skipped, 9 deselected** | PASS |

Manual F09 end-to-end verification (isolated temp data dir): user B with
user A's key → own new job; same owner + changed URL with same key →
`IdempotencyConflict` (HTTP 409); exact same request → original job, not new.

## Migration and rollback

- Migration v3 rebuilds `idempotency_jobs` with `PRIMARY KEY (scope, key)`
  and adds `scope`/`fingerprint`. Data preserved (legacy rows keep their
  job mapping under `scope=''`; they age out via the existing 24h TTL and
  can never be replayed cross-scope). Fresh databases get the scoped table
  from the initial schema; all migration paths verified to converge
  (legacy v0, drifted version marker, fresh).
- Rollback: previous code reads `idempotency_jobs.key` directly; the
  rebuilt table still has a `key` column so SELECTs work, but the old
  code's `INSERT OR REPLACE` would restore per-key-only uniqueness. Downgrade
  therefore loses the scoped guarantee (back to F09) but not data. No
  schema reversal is required for a re-upgrade; migrations are idempotent.
- `user_version` ends at 3 after migration.

## Remaining blockers

- Upload CONTENT-fingerprint *conflict* (same key, genuinely different
  media bytes) is recorded on the mapping but the claim-time comparison is
  options-only by design: the content digest is unknown before the body is
  streamed. A full content-level replay check would require a client-side
  digest header; deferred until the frontend can precompute one.
- The React app (`/new`) does not send idempotency keys; only the vanilla
  `/app` workspace does (unchanged scope decision from task 03).
- Live multi-user behavior is covered by in-process and server-subprocess
  tests on one machine; no distributed deployment exists to verify.

Artifact name and SHA-256: n/a (no packaged artifact).
Reviewer: pending owner review.
