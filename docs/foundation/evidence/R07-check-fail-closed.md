# R07 — check aggregator fails closed; explicit modes behave as documented

Date: 2026-09-18

## Contract

- Default full-scope `scripts/check.py` requires npm **before any work**: when
  Node/npm is missing, `doctor` (full scope) records a required failure and
  the aggregator exits 1 — a missing tool can no longer silently narrow the
  requested check.
- `--backend-only` and `--fast` are explicit modes that run doctor + backend
  non-slow tests and record frontend/website as explicit `SKIP` lines in the
  report, separate from passes.
- `scripts/doctor.py::check_node` marks `node>=22+npm` as a **required** check
  in full scope; the exit code reflects it.

## Reproduction of the original defect

Review probe: with npm missing, the default all-components check exited zero
without running any React or website checks, so "doctor/check green" covered
only a subset. `--fast` did not skip npm steps when npm was available.

## Tests (`backend/tests/test_check_scopes.py`)

- `test_full_scope_stops_when_doctor_fails`.
- `test_fast_scope_explicitly_records_frontend_skips`.
- `test_full_scope_marks_missing_node_as_required` — the review's scenario.

## Results (2026-09-18, this machine — node/npm NOT on PATH)

- `python scripts/check.py` (full scope) → **exit 1**, `[FAIL] doctor`,
  report shows the failure; verified directly (previously masked by a pipe in
  one shell invocation, rerun without a pipe to capture the true code).
- `python scripts/check.py --backend-only` → **exit 0** with
  `[PASS] doctor`, `[PASS] backend-fast-tests`, and explicit
  `[SKIP] frontend-app` / `[SKIP] website` lines.
- `python scripts/doctor.py --json` (default scope) → exit 0; full-scope
  doctor fails on missing npm as required.
- Backend fast suite: **312 passed, 2 skipped, 9 deselected** (2026-09-18,
  this machine, exit 0).

Note: Broad Python minimum requirements remain unpinned in the repo docs;
task 02's lockfile (`backend/requirements.lock`) exists, but the
fresh-machine locked-install run is still NOT RUN (see ACCEPTANCE.md Clean
setup row and task-22 blockers).
