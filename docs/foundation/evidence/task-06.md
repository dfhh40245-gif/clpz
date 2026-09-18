# Task 06 — Fix mute, speed, trim, and text export

Task: 06 (export correctness)
Commit: 76e4b0a (baseline; tasks 01–06 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14, FFmpeg 9.0.1 / ffprobe 9.0.1 (bundled, actually executed)

## Scope and policy decisions

- Output validation gained an explicit `expect_audio` flag: normal renders
  keep the strict audio requirement; an intentionally muted export with no
  audio stream is valid. No audio requirement was weakened elsewhere.
- Speed handling factors the tempo into atempo stages within FFmpeg's
  accepted [0.5, 100] range, keeping trim semantics on the source timeline
  (trim arguments stay before `-i`).
- Edit renders now run into unique per-request temporary outputs, are
  validated, and only then promoted to the user's clips folder; failures
  delete the temp file and leave the original untouched.

## Original reproduction

From `docs/foundation/evidence/current-probes.json` (rerun before changes):
- `export_muted`: HTTP **500** — "Edited output invalid: No audio stream found."
- `export_quarter_speed`: HTTP **500** — FFmpeg rejects `atempo=0.25`
  ("Value 0.250000 for parameter 'tempo' out of range [0.5 - 100]").

## Files changed

- `backend/jobs.py`: `_validate_output(..., expect_audio=True)` — muted
  exports validate without an audio stream (dimensions/codec/duration checks
  and frame decode still enforced); audio checks are skipped only for the
  intentionally-absent stream.
- `backend/main.py` (`edit_clip`): correct atempo chain across the accepted
  0.25–4 range (`<0.5 → 0.5 × speed/0.5`, `>2 → 2.0 × speed/2.0`); unique
  temp output per request (`clip_<i>_edited_<uuid>.mp4`) promoted after
  validation; failure paths clean the temp file; response reports whether
  audio is present.
- `backend/tests/test_export_media.py` (new): 20 fixture-based media tests
  using real FFmpeg/ffprobe.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Generate a local video with audio; export at 0.25, 0.5, 1, 2, and 4 speed, muted and unmuted | `pytest tests/test_export_media.py -q` (generated 4s 1080x1920 sine-tone MP4) | all speeds render muted/unmuted | 20 passed: speed matrix 0.25/0.5/1/2/4 with real renders; muted + unmuted validation both directions asserted; quarter-speed no longer produces invalid `atempo=0.25` | PASS | test output below |
| ffprobe verifies expected dimensions, codecs, audio presence, and duration within a frame/encoder tolerance; decode actual frames | same file (`_probe`, `_decode_ok`) | h264 + aac, duration ≈ source/speed, decodes | durations within tolerance for every speed (e.g. 4.0s source → 1.0s at 4×, 16s at 0.25×); every output frame-decoded; muted output has video-only streams | PASS | backend/tests/test_export_media.py |
| Trim plus speed plus mute plus text succeeds; invalid ranges and nonfinite numbers return 4xx | same file + `TestInvalidEditInputs` | valid combo renders; invalid → 4xx | trim 1–3s @2× yields ~1s output (source-timeline semantics verified with real media); pydantic rejects trim_start>trim_end, speed 0.1/5.0, non-finite (existing remediation tests cover HTTP 4xx/404 for the same model) | PASS | backend/tests/test_export_media.py, backend/tests/test_remediation.py |
| Two exports of the same clip cannot corrupt or overwrite each other's output; cancellation/failure leaves the original intact | `TestConcurrentExports` + failure-path code review/test | unique outputs, original preserved | 4 concurrent renders produced 4 distinct valid files (unique temp names asserted); render failure deletes only the temp file; `src_path` is never written | PASS | backend/tests/test_export_media.py |

Full fast suite after changes: **173 passed, 1 skipped, 9 deselected**.
Probe scenarios rerun through the endpoint on this machine's FFmpeg:
muted export → 200; 0.25× export → 200 (validated output).

## Migration and rollback

No schema/stored-data change. Old `_edited.mp4` outputs stay valid; new
outputs carry a unique temp name only during rendering. Rollback = revert
`backend/jobs.py` + `backend/main.py`; the two 500 defects return with it.

## Remaining blockers

- Text overlay rendering was exercised at the filter-construction level and
  via existing editor-validation tests; a pixel-level visual diff of drawn
  text was not performed (task 18 owns preview/export parity evidence).
- Hardware-specific FFmpeg behavior beyond this machine's bundled 9.0.1 build
  is untested (task 21 owns the hardware matrix).

## Next unblocked task

Task 07 (transcript integrity).
