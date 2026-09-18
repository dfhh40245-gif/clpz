# Task 21 — Establish measurable clip quality and performance

Task: 21 (media quality benchmarks)
Commit: 76e4b0a (baseline; tasks 01–21 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-18
OS/device and hardware: Windows 11 dev machine (x64), developer workstation — see machine profile in the baseline JSON
Runtime/tool/model versions: Python 3.12.14; faster-whisper tiny (cached local model); bundled FFmpeg 9.0.1 / ffprobe 9.0.1

## Original reproduction

Prior evidence was one short successful speech fixture (`docs/audit_pipeline.py`), with no thresholds, no per-stage timings, no negative fixtures, and no machine-readable baseline. No general quality or performance claim was supportable.

## Changed files

- `scripts/benchmark_quality.py` — new benchmark harness: deterministic local fixture generation (SHA-256 recorded per fixture), explicit pre-declared thresholds, real pipeline execution (create → start_uploaded_job → terminal stage), output probing (streams/duration), full-decode error counting, frame extraction, ASS caption word coverage, per-stage timings and peak RSS, machine-readable JSON report, exit code 1 on any failed check.
- `docs/foundation/evidence/task-21-baseline.json` — first measured baseline (this machine).

## Design decisions

- Fixtures are **generated locally** (FFmpeg lavfi + Windows TTS via the existing `generate_video.py`), so no licensing exposure; hashes in the report make runs comparable.
- Thresholds are **defined before measuring** in the `THRESHOLDS` dict and copied into every report; changes require an owner decision.
- Negative fixtures (silence, two-tone non-speech, no audio) assert **graceful structured failure** (`final_stage=error` with a non-null `error_code`), not clip production.
- Human editorial ratings are declared NOT RUN, not fabricated.

## Measured baseline (2026-09-18, quick profile)

Command: `python scripts/benchmark_quality.py --quick --json docs/foundation/evidence/task-21-baseline.json` — **exit 0, 28/28 checks pass, 5 fixtures**:

| Fixture | Outcome | Key metrics |
|---|---|---|
| speech_short_portrait (9:16 TTS speech) | done | clip duration Δ0.06s; A/V Δ0.06s; caption coverage 0.667; decode errors 0; RSS 253 MB; timings transcribe 5.4s / render 3.4s |
| rotated_portrait (rotate=90 metadata) | done | clip duration Δ0.006s; A/V Δ0.029s; caption coverage 1.0; decode errors 0; RSS 257 MB |
| silence_landscape | graceful error | code=TRANSCRIPTION_FAILED; RSS 205 MB |
| two_tone_portrait (non-speech tones) | graceful error | code=TRANSCRIPTION_FAILED; RSS 205 MB |
| no_audio | graceful error | code=TRANSCRIPTION_FAILED; RSS 189 MB |

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Repeatable commands, provenance/hashes, machine specs, thresholds, results | `python scripts/benchmark_quality.py --quick` | report with all of these | all present, exit 0 | PASS | task-21-baseline.json |
| Decode exported media; inspect frames/audio; no placeholders | harness probes output, full decode, frame extract | real decodable media | speech + rotated outputs decode with 0 errors and extract frames | PASS | task-21-baseline.json |
| Long-video cancellation/low-disk/low-RAM graceful failure | long-video + resource-constrained runs | recoverable state | NOT RUN on this machine (long run + constrained-env harness variants not yet executed) | NOT RUN | — |
| Regression baseline comparable; untested languages/hardware explicit | diff future JSON against baseline | comparable | baseline recorded; report explicitly lists unverified languages/hardware | PASS (with declared NOT RUN scope) | task-21-baseline.json |

## Remaining blockers

- Long-video (≥1 h), multi-language, multi-speaker (real conversations), VFR, and low-RAM/low-disk runs need the owner's licensed fixtures and target hardware; the harness supports them (add fixture makers) but they are **not yet measured**.
- Human editorial quality ratings require an owner panel; objective checks only in this baseline.
- Whisper model provenance is Systran/faster-whisper-tiny (local cache); larger models untested here.

Rollback/recovery: no stored-data changes; delete `scripts/benchmark_quality.py` and the baseline JSON to revert.
Reviewer: —
