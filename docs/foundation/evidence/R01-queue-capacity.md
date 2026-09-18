# R01 — bounded pending jobs

Date: 2026-09-18

## Contract

`MAX_QUEUE_DEPTH` limits admitted jobs that have **not yet acquired** an execution worker. Active jobs are limited separately by `MAX_CONCURRENT_JOBS`. A full pending queue rejects a new forge, upload, or retry with HTTP 503 before charging for new work. A duplicate idempotency key returns its existing job even when the queue is full.

Each reservation belongs to a unique job ID. `_run` retains it throughout the semaphore wait, releases it only after acquiring a worker, and releases the worker slot in `finally` after completion or failure. Cancellation and pre-start failures discard the reservation by ID; repeated cleanup cannot decrement another job's reservation. The upload insufficient-credit path also releases its reservation.

## Reproduction and verification

- `tests/test_worker_bounds.py::test_queue_full_refuses_before_charge` holds all worker slots, submits two real jobs at depth 2, verifies a third is rejected without a debit, cancels one job, and verifies the rejected key can submit after capacity returns. It also checks duplicate replay while full.
- `tests/test_worker_bounds.py::test_http_queue_saturation_and_cancel` starts the actual API with zero workers and depth 2. It verifies two 200 responses, 503 on the third, unchanged balance on rejection, capacity restored by cancellation, and 503 again when full.
- `tests/test_worker_bounds.py::test_reservation_and_worker_slot_release_on_terminal` verifies both successful and error terminal paths release the worker slot and reservation.
- `tests/test_worker_bounds.py::test_creation_failure_releases_reservation` injects pre-start persistence failure for forge and upload, then checks no reservation remains.
- `tests/test_worker_bounds.py::test_upload_cancel_and_start_failure_release_reservations` covers an upload that is cancelled before it starts and an exception during upload worker setup.
- `tests/test_worker_bounds.py::test_mapping_failure_cancels_refunds_and_releases` covers a post-charge mapping error: the job is cancelled, its credit is refunded, its replay key is cleared for that user, and its queue place is released.
- `tests/test_worker_bounds.py::test_charge_exception_releases_reservation` covers a charging exception for both forge and upload.
- `tests/test_worker_bounds.py::test_charge_commit_then_exception_refunds_and_releases` simulates a successful ledger commit followed by a lost response; the job-specific debit is refunded, its replay key is cleared for that user, and its queue place is released.
- `tests/test_worker_bounds.py::test_depth_bound_enforced_and_self_heals` verifies double release is harmless.
- The idempotency test module now resets its worker queue per case. Its former accumulated waiting jobs correctly hit the newly enforced cap, which revealed the missing test isolation.

Focused verification: `python -m pytest tests/test_worker_bounds.py tests/test_credits.py tests/test_idempotency_scope.py tests/test_upload.py tests/test_ledger_atomicity.py -m 'not slow' -q --tb=short` from `backend` — **61 passed, 1 deselected** (2026-09-18). The credit-exhaustion fixture explicitly uses depth 12 so its ten held submissions can test 402 after exhausting credits.

Backend fast suite: `python -m pytest tests -m 'not slow' -q --tb=short` from `backend` — **291 passed, 2 skipped, 9 deselected** (2026-09-18). `py_compile` for the touched Python modules and `git diff --check` also exited 0.
