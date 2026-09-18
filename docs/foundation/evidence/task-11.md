# Task 11 — Bounded media workers and cancellation

**Correction (2026-09-18, R01):** The original admission implementation below released a reservation before its worker acquired an execution slot, so its pending bound was ineffective. R01 is now fixed and verified; the current contract and results are in [R01-queue-capacity.md](R01-queue-capacity.md). The original task-11 evidence is retained as a historical record.

Task: 11 (bounded media workers)
Commit: 76e4b0a (baseline; tasks 01–11 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14; FFmpeg exercised only via stubbed/registry tests (no real Whisper render run — see Remaining blockers)

## Scope and policy decisions

- **Admission bound**: `MAX_QUEUE_DEPTH=8` (env-overridable). A saturated queue
  refuses new forge/upload submissions **before** charging (HTTP 503 +
  `jobs.QueueFullError`). Queued-but-not-started work is counted at submit and
  the reservation retires when the worker thread starts — no second semaphore
  to deadlock against `_slots`.
- **Edit renders** (F12: previously bypassed all slot control) get their own
  budget `EDIT_RENDER_CONCURRENCY` (default: same as pipeline workers), a
  bounded wait `EDIT_QUEUE_WAIT_SECONDS=5` (HTTP 503 on exhaustion), and a
  hard deadline `EDIT_RENDER_DEADLINE_SECONDS=300` mapped to HTTP 504.
- **Watchdog**: background thread sweeps an in-flight edit registry every 5 s,
  force-fails renders past their deadline (kills registered subprocesses via
  proc.py, deletes partial output so no truncated file is promoted). Started
  from main.py at startup, idempotent.
- **proc.py coverage** (F12: some media calls bypassed it): transcriber
  ffprobe + chunk audio extraction and `start_uploaded_job`'s ffprobe now run
  through `proc_mod.run(job_id, ...)` with bounded timeouts, so cancellation
  and shutdown terminate them. In-process Whisper remains uninterruptible
  mid-inference by design; the job-level absolute deadline
  (`JOB_TIMEOUT_SECONDS`) is still the safety net that converts a hang into a
  controlled failure. This limitation is documented, not hidden.
- **Upload/webhook bounds** (F13): the Gumroad webhook now rejects bodies over
  `WEBHOOK_MAX_BYTES` (1 MiB) **before** JSON parsing. (The upload
  copied-byte cap already applied during streaming from earlier tasks.)
- Cancellation semantics unchanged: cancelled jobs stay cancelled with a
  cooperative reason, refund nothing (user chose to cancel).

## Original reproduction

AUDIT.md F12/F13: "Cooperative deadlines cannot interrupt a stuck in-process
model. Some probes/audio extraction/edits bypass proc.py. Queue threads are
unbounded and edit renders bypass the main slot control"; upload cap applied
after multipart parsing, sync probe inside async handler, concurrent edits
sharing one output pathname (the shared-pathname half was fixed in task 06
with unique temp outputs).

## Files changed

- `backend/jobs.py`: `MAX_QUEUE_DEPTH` admission (`try_acquire_slot`,
  `_release_admission`, `queue_depth`), `QueueFullError`,
  `EDIT_RENDER_*` constants + `_edit_semaphore`, edit registry +
  `note_edit_started`/`note_edit_finished`, `_watchdog_sweep`/
  `_watchdog_loop`/`start_watchdog`, `RenderTimeoutError`, wired admission
  into `create_job_idempotent`/`create_upload_job_idempotent` (reject before
  charge; release on failure paths), worker retires reservation in `_run`,
  `reset_for_testing` resets all bounds, `start_uploaded_job` ffprobe via
  proc.py, transcribe call passes `job_id`.
- `backend/pipeline/transcriber.py`: `transcribe(..., job_id="")`;
  `_get_duration` and `_extract_audio_chunk` routed through proc.py with
  bounded timeouts.
- `backend/main.py`: startup calls `jobs.start_watchdog()`; forge/upload
  endpoints map `QueueFullError` → 503; `edit_clip` acquires the edit
  semaphore with bounded wait (503), registers with the watchdog, enforces
  `EDIT_RENDER_DEADLINE_SECONDS` via `subprocess.run(timeout=...)`, maps
  timeout → 504, releases the semaphore in `finally`; webhook body cap
  before parse (413).
- `backend/tests/test_worker_bounds.py` (new): 11 regression tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Queue bound refuses before charge | `pytest tests/test_worker_bounds.py::test_queue_full_refuses_before_charge` | QueueFullError; balance + ledger untouched; key not consumed | As expected | PASS | test output |
| Bound self-heals | `...::test_depth_bound_enforced_and_self_heals`, `...::test_admission_release_frees_depth_after_worker_starts` | depth refused at bound; returns to 0 after worker start | As expected | PASS | test output |
| Edit budget bounded | `...::test_edit_semaphore_bounds_concurrent_renders` | extra acquires time out (503 path) | As expected | PASS | test output |
| Wedged render force-failed | `...::test_watchdog_sweep_kills_deadline_exceeded_render` | subprocess killed, partial output removed, registry cleared | As expected | PASS | test output |
| Healthy renders untouched | `...::test_watchdog_leaves_healthy_renders_alone` | no kill before deadline or after completion | As expected | PASS | test output |
| Deadline maps to 504 | `...::test_edit_deadline_error_maps_to_504` | endpoint enforces EDIT_RENDER_DEADLINE_SECONDS → 504 | As expected | PASS | test output |
| Stubborn child terminated | `...::test_proc_kill_survives_stubborn_child` | SIGTERM-ignoring child killed via proc registry | As expected | PASS | test output |
| Cancel reason retained | `...::test_cancelled_job_records_reason` | terminal `cancelled` + reason; depth released | As expected | PASS | test output |
| Webhook cap ordering | `...::test_job_cancelled_after_webhook_sig_check` | size cap before `_parse_payload` | As expected | PASS | test output |
| Audio extraction via proc.py | `...::test_transcriber_extraction_uses_proc_registry` | chunked extraction runs under job's proc registry | As expected | PASS | test output |
| No regressions | `pytest tests -m "not slow" -q` | all pass | **236 passed, 1 skipped, 9 deselected** | PASS | test output |

## Migration and rollback

No schema changes. Rollback = revert the five files; no persisted state is
affected. New env vars are optional with safe defaults.

## Remaining blockers

- **NOT RUN end-to-end**: no real long-video run exercising a genuinely hung
  Whisper/ffmpeg against the live watchdog on real media (this machine's
  suite stubs heavy stages for hermeticity). The watchdog's kill path is
  verified against a real stubborn subprocess, and the pipeline deadline
  path is covered by existing `test_job_timeout_marks_error`.
- F12's in-process Whisper interruption remains a documented design
  limitation (absolute job deadline is the mitigation), per audit wording.
- Multi-minute soak test of queue saturation under concurrent real renders
  was not run.

## Artifact name and SHA-256

N/A (no release artifact produced).

## Reviewer

Pending owner review.
