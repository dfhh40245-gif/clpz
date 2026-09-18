# Task 07 — Fix chunk overlap and transcript validation

Task: 07 (transcript integrity)
Commit: 76e4b0a (baseline; tasks 01–07 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14 (no live Whisper run; see Remaining blockers)

## Scope and policy decisions

- Overlap reconciliation is **interval-scoped**: two word entries are the
  same transcription of one token only when their normalized text matches AND
  their midpoints sit within 0.6 s. A global same-text dedupe was rejected
  because it erases genuine repeated speech.
- Every word/segment entry is validated (finite, ordered, nonnegative,
  nonempty text) — at chunk level, at merge level, and in `words.json` loading.
- Non-ASCII languages keep their captions: fallback tokenization uses Unicode
  word characters instead of `[A-Za-z0-9]`.

## Original reproduction

From `docs/foundation/evidence/current-probes.json` (rerun before changes):
- `overlap`: two identical overlapping 2-word chunks merged to **4 words /
  2 segments** (expected 2/1) — finding F07.
- Language dropped in `_transcribe_chunk` (chunk results hardcoded to
  `language="unknown"`).
- `srt_parser._segment_words` recognized only ASCII alphanumerics, dropping
  every token of a non-ASCII subtitle.

## Files changed

- `backend/pipeline/transcriber.py`: interval-scoped overlap reconciliation
  (`_same_transcribed_copy` + word/segment dedupe passes); per-entry
  validation (`_validate_timed_entries`) applied at chunk and merge level;
  language detection carried from the first chunk that provides one and
  passed explicitly to subsequent chunks.
- `backend/pipeline/srt_parser.py`: `_load_words_json` validates EVERY entry
  and falls back to SRT estimation when none are valid; non-finite timestamp
  rejection; Unicode-aware fallback tokenization.
- `backend/tests/test_transcript_integrity.py` (new): 16 tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Identical overlap produces one copy; jittered overlaps merge; deliberate repeated words remain; empty chunks work | `pytest tests/test_transcript_integrity.py -q` | 2 words/1 segment for the probe case | identical overlap → 2 words/1 segment (probe case now correct); jittered overlap merges; `yeah, yeah` repetition survives; empty chunks tolerated; language carried | PASS | test output below |
| Boundary words and segment timing remain ordered and within source duration | `TestOrderingAndBounds` | sorted, bounded | words/segments sorted by start; entries beyond source duration dropped | PASS | backend/tests/test_transcript_integrity.py |
| Malformed later word entries, NaN, reverse timestamps, and Unicode fixtures produce a controlled result | `TestMalformedInputs` + `TestSrtParser` | controlled, no crash | malformed later entries dropped while valid ones survive; NaN/reverse/negative rejected; Unicode (Café naïve déjà, Привет мир) kept in fallback tokenization; millisecond carry preserved; reversed SRT block skipped | PASS | backend/tests/test_transcript_integrity.py |
| A real multi-chunk speech fixture is transcribed and its boundary captions are inspected; synthetic unit tests alone do not certify speech accuracy | NOT RUN — requires live Whisper + a licensed speech fixture | boundary captions inspected | **NOT RUN**: no live model run or licensed fixture on this machine; synthetic/unit coverage only, per the check's own warning | NOT RUN | — |

Full fast suite after changes: **189 passed, 1 skipped, 9 deselected**.

## Migration and rollback

No stored-data migration: transcripts already written (SRT + words.json) are
read with the stricter validation, which tolerates everything the old writer
produced for healthy input. Rollback = revert the two pipeline files.

## Remaining blockers

- **Real-fixture check NOT RUN** (no speech fixture catalog / live model run
  here). The acceptance item that requires inspecting boundary captions of a
  real multi-chunk transcription stays open; it belongs with task 21's
  fixture harness.
- Languages supported by Whisper are not asserted end-to-end; fallback
  tokenization is Unicode-generic, but font coverage for specific scripts is
  a task 21/18 concern.

## Next unblocked task

Task 08 (atomic local ledger).
