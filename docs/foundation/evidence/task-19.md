# Task 19 — Safe project deletion and scalable library browsing

Task: 19 (project library/storage)
Commit: 76e4b0a (baseline; tasks 01–19 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)

## Original reproduction

AUDIT.md F24: "Job library returns full copied details; GET can trigger
legacy metadata backfill. No ordinary safe per-project storage/deletion
workflow." Confirmed by source: `list_jobs` deep-copied every job including
caption word arrays, `_job_payload` invoked `ensure_clip_metadata`
(ffprobe + thumbnail generation) on every read, and no delete endpoint or
storage report existed.

## Scope and policy decisions

- **List contract (versioned by shape, same URL)**: `GET /api/jobs` now
  returns `{projects, total, page, per_page}` where each project is a
  bounded summary — id, created_at, stage, progress, input_type, url,
  title, error, error_code, `clip_count`/`clip_total`. No clip arrays or
  word-level data. Query params: `page`, `per_page` (1–100), `q` (title/URL
  substring search), `sort=newest|oldest`.
- **Backfill control**: `_job_payload(backfill=False)` is the default; the
  per-job detail endpoint (`GET /api/jobs/{id}`) passes `backfill=True`.
  List GETs can no longer launch ffprobe/thumbnail work (F24).
- **Deletion scope (explicit policy)**: `DELETE /api/jobs/{id}` removes the
  project's MANAGED working directory (source downloads/uploads,
  transcripts, rendered clips, edit versions) plus the job record and its
  idempotency mappings. NEVER touched: files exported to the user's Videos
  folder, external URLs, credit ledger transactions (financial record), and
  anything resolving outside the data root. Ownership enforced (owner or
  admin; anonymous local jobs deletable locally). A running job must be
  cancelled first (409); a queued job is cancelled atomically before
  removal so no worker can resurrect a ghost. The response states the
  policy to the user.
- **Storage report**: `GET /api/jobs/storage` returns total + per-project
  byte usage and the data root.
- **UI**: the Projects grid consumes the paginated summaries, opens projects
  via the detail endpoint on demand, shows a per-project delete button with
  a confirmation dialog stating the scope, and the dashboard renders from
  summaries (clip counts) without downloading word data.
- Retention remains user-controlled (AUTO_CLEANUP_HOURS default 0, from the
  baseline); no automatic deletion was added.

## Files changed

- `backend/main.py`: paginated `list_jobs`, `storage_summary`, `delete_project`,
  `_job_payload(backfill=...)`, detail endpoint backfill=True.
- `frontend/clpz.html`: summary-driven dashboard + projects grid, delete
  button + confirmation, detail-on-open shim.
- `backend/tests/test_isolation.py`: updated for the paginated shape.
- `backend/tests/test_remediation.py`: ghost-rehydration test updated for the
  paginated shape.
- `backend/tests/test_library.py` (new): 8 regression tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Bounded summaries, no FFmpeg in GET | `tests/test_library.py::test_list_never_launches_media_backfill` + `test_summary_is_bounded` | no backfill calls in list; counts only | ensure_clip_metadata asserted never called on list path | PASS | test output |
| Pagination stable under new jobs, ownership respected | `...::test_ownership_filter_unit` + HTTP isolation suite | owner filter precedes paging | ownership/visibility unit-verified; `test_list_jobs_hides_other_users_jobs` green with new shape | PASS | test output |
| Delete scope/race: no ghosts, nothing outside data root | `...::test_delete_queued_job_cancels_first`, `...::test_delete_running_job_conflicts`, `...::test_delete_refuses_path_outside_data_root`, `...::test_delete_removes_managed_files_only`, `test_deleted_job_not_rehydrated_after_restart` | managed-only removal; traversal refused; running protected | As expected | PASS | test output |
| Storage usage visible; exports/external preserved per policy | `GET /api/jobs/storage` + `...::test_delete_removes_managed_files_only` | usage shown; user files survive | endpoint implemented; export survival asserted | PASS | test output |
| Large synthetic library latency | seed 500+ synthetic jobs, time list | bounded size/latency | summaries bound payload size by construction; dedicated 500-job latency benchmark NOT RUN | **PARTIAL** | test file |
| UI end-to-end (delete confirm, storage view) | manual browser session | working flow | code paths unit-tested; browser session NOT RUN | **NOT RUN (visual)** | — |

## Migration and rollback

No schema change. Rollback = revert `backend/main.py` + `frontend/clpz.html`;
the old unpaginated list shape returns. The UI change is compatible with the
old shape via `resp.projects || resp` fallback in the interim.

## Remaining blockers

- 500+ job latency benchmark (synthetic seeding) for the scale gate.
- Browser-automation run of the delete confirmation and storage display.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
