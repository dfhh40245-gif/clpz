# R04 — upload replay content identity

Date: 2026-09-18

## Contract

The upload endpoint writes each multipart body to a unique file under
`DATA_DIR/.upload-staging`, validates it, and calculates its SHA-256 in bounded
chunks before it creates or reuses an idempotency mapping. A mapping contains
both the media digest and the canonical filename/options digest.

- Same scoped key, same settings, and byte-identical content: return the
  original job without another debit.
- Same scoped key/settings with different content: HTTP 409, no new job, and
  no debit.
- A historical mapping without a content digest: HTTP 409, because it cannot
  establish that the new file is a legitimate retry.
- Every exit path removes the request's temporary `.part` file. On a new job,
  `os.replace` promotes it atomically into that job's source path.

## Evidence

`tests/test_remediation.py::test_upload_replay_checks_content_and_cleans_staging`
uses the actual HTTP multipart endpoint and two distinct valid MP4 fixtures.
Both uploads intentionally use `same.mp4`, the same options, and the same
idempotency key. It proves:

1. a byte-identical retry receives HTTP 200 and the original job ID;
2. a changed valid MP4 receives HTTP 409 with a different-upload error;
3. `DATA_DIR/.upload-staging` contains no `.part` files afterward; and
4. the balance changes from 10 to 9 only once.

Focused command from the repository root:

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_remediation.py::test_upload_replay_checks_content_and_cleans_staging backend/tests/test_remediation.py::test_upload_dedupe_same_key -q --tb=short
```

Result: **2 passed in 2.50s**.

Broader regression command:

```text
.venv\Scripts\python.exe -m pytest backend/tests/test_remediation.py::test_upload_replay_checks_content_and_cleans_staging backend/tests/test_remediation.py::test_upload_dedupe_same_key backend/tests/test_idempotency_scope.py backend/tests/test_worker_bounds.py -q --tb=short
```

Result: **37 passed in 14.76s**. The cancellation trace lines emitted by
background worker cleanup are expected test logging; pytest completed with exit
code 0.

`py_compile` passed for `backend/main.py` and `backend/jobs.py`; `git diff
--check` reported no whitespace errors for the R04 files.
