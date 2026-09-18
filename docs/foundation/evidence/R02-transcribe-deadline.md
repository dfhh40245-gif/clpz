# R02 — enforceable transcription hard deadline

Date: 2026-09-18

## Contract

Whisper no longer runs as an in-process synchronous call in production.
`pipeline.transcriber.transcribe_supervised()` executes the transcription in a
dedicated child interpreter (spawned via `subprocess.Popen`; the child runs the
real entry point `transcriber._child_main`, which loads the model, runs one
transcription and exits), supervised by the worker thread:

- `TRANSCRIBE_DEADLINE_SECONDS` (default 3600, env-tunable) is a hard deadline
  for the transcription stage. At expiry the child is force-terminated
  (terminate → kill, 5s each) and `TranscribeTimeoutError` is raised, mapped in
  `_classify_error` to the distinct code `TRANSCRIBE_TIMEOUT` (so it is no
  longer conflated with the whole-job `JOB_TIMEOUT`).
- The parent never imports/loads the model, so the worker thread stays
  responsive and the semaphore slot is released in `_run`'s `finally` when the
  job fails. `_payload_paths`/`_cleanup_paths` remove the supervision
  exchange files in every path, including timeouts and shutdown interrupts
  (BaseException → kill child → cleanup → re-raise).
- The child inherits the full parent environment (a whitelist broke
  `Path.home()`/`PATH` for `config.py`/`shutil.which`), with `PYTHONPATH`
  prepended for dev and `CLIPFORGE_MODEL_DIR` explicitly defaulted to `""` so
  the job directory can never be mistaken for a bundled-model directory.
- The whole-job `JOB_TIMEOUT_SECONDS` deadline and `_check_stop` remain as a
  backstop for stages that are not individually supervised.
- `clpz_server.py` gained `multiprocessing.freeze_support()` before `main()`
  so the frozen exe can host spawned children (guards the future migration to
  multiprocessing; today's child is a plain `sys.executable` subprocess and
  also works under `python -m uvicorn` direct start).
- `TRANSCRIBE_SUPERVISED=0` (env) restores the legacy in-process call. The
  hermetic test suite sets this in `tests/conftest.py` (existing tests stub
  `transcriber.transcribe` in-process); `test_transcribe_deadline.py` flips it
  back on because it exercises the real boundary.

## Reproduction of the original defect

Review probe: `JOB_TIMEOUT_SECONDS=0.05` + a controlled blocking transcription
function → after 0.25s the worker was still alive and the job still
"transcribing"; only the injected function could release it. The render
watchdog covers edit re-renders, not transcription; a configured expiry alone
cannot interrupt a synchronous in-process call.

## Tests (`backend/tests/test_transcribe_deadline.py`)

All three run the real parent-side supervision loop, deadline, kill and
cleanup unmodified. Only the child command is redirected via the
`_child_command` seam to controlled wrappers, routed per job ID through the
payload filename prefix; wrappers run the real `_child_main` with only
`transcribe` stubbed (hang forever / instant success), so no Whisper model is
ever downloaded.

- `test_stuck_child_terminated_at_deadline` — a stuck child (stub blocks
  10^6s) is armed, then force-terminated; the job errors with
  `TRANSCRIBE_TIMEOUT` in well under `deadline + 15s` tolerance (observed
  ~2.2s with a 2.0s deadline).
- `test_worker_released_and_next_job_runs` — the stuck job fails with
  `TRANSCRIBE_TIMEOUT`, the queued follow-up job runs to `done` (its child
  succeeds through the same real supervision path), both worker threads
  finish, and the worker slot is immediately re-acquirable.
- `test_supervised_deadline_uses_configured_seconds` — configuration surface.

## Results

- Focused module, 4 consecutive runs: `3 passed` each (4.9–5.8s).
- Full fast suite from `backend`:
  `python -m pytest tests -m 'not slow' -q --tb=short` →
  **294 passed, 2 skipped, 9 deselected** in 327.8s (2026-09-18), i.e. the
  prior 291 + 3 new R02 tests, no regressions.
- `py_compile` clean for `pipeline/transcriber.py`, `jobs.py`, `config.py`,
  `clpz_server.py`, `tests/conftest.py`, `tests/test_transcribe_deadline.py`.

## Files changed

- `backend/pipeline/transcriber.py` — supervised boundary: `transcribe_supervised`,
  `_supervised_transcribe`, `_child_main`, `_child_command`, `_kill_process_tree`,
  `_relay_progress`, `TranscribeTimeoutError`, `__main__` block.
- `backend/jobs.py` — call site uses `transcribe_supervised`;
  `_classify_error` returns `TRANSCRIBE_TIMEOUT` for the deadline error;
  stale in-process comment updated.
- `backend/config.py` — `TRANSCRIBE_SUPERVISED`, `TRANSCRIBE_DEADLINE_SECONDS`.
- `backend/clpz_server.py` — `multiprocessing.freeze_support()` at entry.
- `backend/tests/conftest.py` — suite-wide `TRANSCRIBE_SUPERVISED=0` default.
- `backend/tests/test_transcribe_deadline.py` — new regression tests.

## Remaining notes

- Progress from the child is relayed to the job record best-effort via a
  progress file polled every 0.25s.
- The frozen-launcher path (task 12 lifecycle) inherits this fix via
  `clpz_server.py`; an on-machine installer run is still pending owner
  resources and remains recorded in `evidence/task-22.md`.
