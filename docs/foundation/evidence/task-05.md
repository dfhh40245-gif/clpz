# Task 05 — Make failed jobs resume safely

Task: 05 (pipeline resume)
Commit: 76e4b0a (baseline; tasks 01–05 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14; FFmpeg/ffprobe used via existing `_validate_output` path only (stubbed in the hermetic resume tests)

## Original reproduction

`docs/foundation/probe_current.py` → `retry_after_analysis`:
```
"stage": "error",
"error": "cannot access local variable 'transcript' where it is not associated with a value"
```
`backend/jobs.py::_run_pipeline` skipped assigning `transcript` when the
completed-stage markers claimed parse+analyze were done, then used it in
`analyzer.find_clips` and caption rendering → `UnboundLocalError` (finding F05).

## Fix design

Stage markers are now treated as **claims requiring valid artifacts**:

- Resume path (parse+analyze claimed complete): rebuild the transcript from
  the persisted SRT (+ optional `words.json`) via `srt_parser.parse_srt`,
  validate it has segments, and only then continue to analysis/render.
  Completed stages are reused — transcription is NOT rerun when its artifact
  is valid (guarded by test).
- A claimed `transcribe` stage whose `transcript.srt` artifact is missing or
  corrupt invalidates that claim and reruns transcription (the stage-2 skip
  condition already requires `srt_path.exists()`); a claimed parse with a
  corrupt SRT fails with a precise, recoverable error naming the artifact.
- Existing contracts preserved: durable job/attempt state, retry returns the
  original job, cancellation still wins over completion, refunds remain wired
  to the failure path (atomicity is task 08's scope).

## Files changed

- `backend/jobs.py`: resume branch in `_run_pipeline` reconstructs and
  validates `transcript` before analysis/rendering; no other behavior change.
- `backend/tests/test_resume.py` (new): 9 hermetic regression tests stubbing
  cutter/captions/analyzer/validation and recording stage invocations.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Inject one failure after download, transcription, parsing, analysis, and a partial render; each resume completes or returns a precise recoverable error | `pytest tests/test_resume.py -q` | resume completes or precise error | 9 passed: resume after transcribe; after transcribe+parse; after parse+analyze (F05) all complete; interrupted-worker restart completes; missing SRT invalidates the claim and recovers | PASS | test output below |
| Missing/invalid words.json, SRT, and source media are handled predictably with no unbound variables | same file | controlled result, no UnboundLocalError | corrupt `words.json` → controlled fallback; missing SRT → claim invalidated + rerun; missing source media → clean `error` with `error_code`; no unbound-variable paths remain | PASS | backend/tests/test_resume.py |
| Restart an interrupted job and confirm consistent state, stable clip identity, and no duplicate worker | `test_interrupted_job_restart_keeps_state` | done, stable ids, single run | clip id `{job}-clip-0` stable; exactly one analyze invocation recorded (no duplicate worker) | PASS | backend/tests/test_resume.py |
| Completed clips are not lost and cancelled jobs do not become done accidentally | same file, last two tests | kept + cancelled | pre-done clip preserved through resume; cancelled job ends `cancelled` even when cancelled before resume | PASS | backend/tests/test_resume.py |

Full fast suite after changes: **153 passed, 1 skipped, 9 deselected**.
Also reran the audit probe semantics manually: the exact F05 scenario now
reaches `done` with clips rendered instead of `UnboundLocalError`.

## Migration and rollback

No schema or stored-data change; `job.json`/SQLite formats are unchanged and
older interrupted jobs resume under the new logic. Rollback = revert
`backend/jobs.py`; the F05 crash would return with it (no data corruption
either way).

## Remaining blockers

- A real end-to-end resume against a live Whisper transcription run was not
  performed here (the resume tests stub the model deterministically; the slow
  e2e suite covers real media). The un-stubbed `transcribe` path is exercised
  by `test_upload.py` slow tests, not in this fast suite run.

## Next unblocked task

Task 06 (export correctness) and task 07 (transcript integrity).
