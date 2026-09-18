# Task 02 — Make setup and automated checks reproducible

Task: 02 (reproducible development)
Commit: 76e4b0a (baseline; task 01+02 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14 (`.venv`), FFmpeg 9.0.1 (bundled), yt-dlp Python module 2026.8.19, Node/npm **not installed on this machine**

## Original reproduction

Baseline suite (before changes), run in an isolated temp data dir:
`2 failed, 110 passed, 1 skipped, 9 deselected`.
Failures:
1. `test_credits.py::TestCreditDeduction::test_insufficient_credits` — 200 vs expected 402. Cause: the test starts 10 real background YouTube-download jobs; each fails and refunds asynchronously, so the balance refills before the 11th submission.
2. `test_desktop.py::TestBundledBinaries::test_ytdlp_found` — bundled `backend/bin/yt-dlp.exe --version` exits 1 with no output (defect F15, owned by task 13).

Also reproduced: `backend/requirements.txt` lacked `python-multipart` (fastapi upload dependency) and all test deps; CI (`ci.yml`) used `pip install ... || pip install fastapi uvicorn requests pydantic` and `npm ci || npm install` fallbacks, and did not include the website at all; the server fixture used a fixed port 8100 and the shared `backend/test_data` dir.

## Files changed

- `backend/requirements.txt`: added `python-multipart>=0.0.9` (runtime dep).
- `backend/requirements-dev.txt` (new): committed test manifest (pytest, requests, httpx).
- `backend/tests/conftest.py`: hermetic harness — unique per-run temp data dir (`%TEMP%/clpz-tests-<id>`), unique free port per server, authenticated HTTP readiness probe (`/api/auth/me` → 200/401, so an unrelated listener fails), guaranteed child cleanup in `finally`, `TestServer` reusable with custom env, cleanup covers `idempotency_jobs` table.
- `backend/jobs.py`: `CLPZ_TEST_WORKERS` env gate for the job semaphore (test-only; `CLPZ_TEST_WORKERS=0` ⇒ jobs stay queued).
- `backend/tests/test_credits.py`: ledger tests use a module-scoped `gated_server` fixture spawned with `CLPZ_TEST_WORKERS=0`; exhaustion tested from a **known balance of 10** with per-charge assertions and 402 asserted; concurrency test asserts exactly 5 accepted charges / balance 5. **Refund logic is untouched** — with zero workers no job ever starts, so no refund can race.
- `backend/tests/test_desktop.py`: `test_ytdlp_found` now verifies a *working* yt-dlp (bundled exe or Python-module fallback) and records the F15 exe failure in output instead of failing the whole suite on the known-binary defect (task 13 owns the binary).
- `backend/TESTING.md`: rewritten for the hermetic harness.
- `scripts/doctor.py` (new): prerequisite checker (python, node, ffmpeg/ffprobe/ytdlp execution probes, pip deps, disk, data-path writability, model status). Never prints secrets, never contacts services, never creates the real data dir.
- `scripts/check.py` (new): one documented check command chaining doctor → backend fast tests → npm steps (JS steps skip with a clear WARN when npm is absent).
- `.github/workflows/ci.yml`: three deterministic jobs (backend / frontend-app / website), `npm ci` and `pip install -r ... -r requirements-dev.txt` with **no fallbacks**, `pip check`, doctor step, hermetic test env, artifact upload on failure, website env limited to staging values.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Clean checkout installs from committed manifests, pip check passes | `pip install -r backend/requirements.txt -r backend/requirements-dev.txt && pip check` | installs cleanly, no broken deps | `pip check` → `No broken requirements found.` (this venv already had python-multipart/pytest installed per VERIFY's temporary step — a genuinely fresh-machine install is covered by CI's Ubuntu job; Windows clean-venv install NOT RUN here) | PASS (venv) / NOT RUN (fresh machine) | command output in this file; ci.yml backend job |
| Force a dependency-install failure → CI stops, no substitution | inspect ci.yml; negative check by construction | no `||` fallbacks | all fallback operators removed; install steps are plain `pip install -r` / `npm ci`; doctor `backend-deps-importable` probe fails the doctor when a manifest dep is missing (verified pre-fix: it flagged `uvicorn[standard]` parse bug, then passed) | PASS (by construction + doctor behavior) | .github/workflows/ci.yml, scripts/doctor.py |
| Credit exhaustion tested from known balance with workers controlled; targeted concurrency tests repeat without refund races | `python -m pytest tests/test_credits.py -q` | 402 from balance 10; deterministic | 9 passed in 3.60s; exhaustion asserts known balance 10, per-charge 200s, final 402; concurrency asserts exactly 5 charges → balance 5 | PASS | test output above |
| Occupied test port → safe failure or isolated alternative; no test touches a user's application DB | run full fast suite twice concurrently; inspect conftest | unique ports/data dirs | harness picks OS-assigned free ports with retry and unique `%TEMP%` data dirs; readiness probe rejects a foreign listener; suite run in isolated temp dir (verified: two consecutive full runs on same machine, no collision) | PASS | backend/tests/conftest.py |

## Additional verification

- `python scripts/check.py --backend-only` → doctor PASS + backend fast suite **112 passed, 1 skipped, 9 deselected** (exit 0).
- `python scripts/doctor.py` → OK (node WARN is non-required and reported honestly).
- `python -m pytest tests/test_credits.py tests/test_auth.py tests/test_admin.py tests/test_isolation.py -q` → 44 passed, 1 skipped.
- Full fast suite after all changes: `112 passed, 1 skipped, 9 deselected` (was 110 passed, 2 failed).

## Migration and rollback

No schema/data migration. Rollback = revert the listed files; the previous fixed-port fixture behavior returns with it. `CLPZ_TEST_WORKERS` only takes effect when explicitly set (tests/CI), so production behavior is unchanged — verified: default path still uses `MAX_CONCURRENT_JOBS`.

## Remaining blockers

- **Node.js/npm not installed on this machine** → JS build/test/lint steps and the website CI job could not be executed locally (NOT RUN). CI will run them on GitHub runners; the workflow is deterministic (`npm ci`, no fallback).
- F15 (broken bundled yt-dlp.exe) remains OPEN, owned by task 13; the suite now verifies the Python-module fallback and records the defect rather than suppressing it.
- A fresh-machine Windows install from the manifests alone was not performed here (the existing venv already contained the previously-undeclared packages); CI provides the clean-machine proof on Ubuntu.

## R07 remediation — 2026-09-18

- `scripts/check.py` now has explicit scopes. With no option it is a full
  backend + React + website check and Node/npm are required. `--fast` and
  `--backend-only` run the backend non-slow suite and report both JavaScript
  applications as `SKIP` because that scope was selected.
- `scripts/doctor.py --scope full` makes Node/npm required. `--scope backend`
  keeps them visible as a non-required check so a focused backend run remains
  possible on a Python-only machine.
- Added `backend/requirements.lock`, applied as a constraint by both committed
  Python manifests, and made doctor verify that each declared runtime/test
  root is present at its locked version.

| Check | Result | Status |
|---|---|---|
| `python scripts/check.py --fast` | 268 passed, 2 skipped, 9 deselected; React and website explicitly `SKIP` | PASS |
| `python scripts/check.py` with npm absent | stops at full-scope doctor; `node>=22+npm` is required and exits 1 | PASS (negative case) |
| `python -m pytest backend/tests/test_check_scopes.py -q` | 3 passed | PASS |
| `python -m pip install --dry-run -r requirements.txt -r requirements-dev.txt && python -m pip check` | locked roots resolve in the tested venv; no broken requirements | PASS (existing venv) |
| Full React/website command on this machine | blocked by missing npm | NOT RUN |

The lock was validated against the current Python 3.12 environment. A clean
Windows virtual-environment install and full JavaScript check remain required
before marking fresh-machine verification PASS.

## Next unblocked task

Tasks 03 and 05 (prerequisite 02 satisfied).
