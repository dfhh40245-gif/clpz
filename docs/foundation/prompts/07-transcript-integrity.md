# Task 07 — Fix chunk overlap and transcript validation

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02, task 05.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Merging two identical overlapping two-word chunks returns four words and two segments. Language metadata is dropped in _transcribe_chunk. SRT fallback tokenization only recognizes ASCII alphanumerics.

## Inspect these files

- backend/pipeline/transcriber.py
- backend/pipeline/srt_parser.py
- backend/pipeline/captions.py
- backend/pipeline/analyzer.py
- backend/tests/test_pipeline.py

## Implementation steps

1. Reconcile complete overlap intervals after ordering/alignment; preserve genuine repeated speech rather than globally deduplicating words.
2. Carry language/confidence metadata where available and validate every word/segment, not only the first JSON entry.
3. Validate finite ordered timestamps, nonnegative durations, source bounds, and SRT millisecond carry. Distinguish precise timings from fallback estimates.
4. Support the languages agreed in task 01 in fallback tokenization and font coverage; document unsupported scripts instead of silently producing empty captions.

## Acceptance checks — all required for this task

- [ ] Identical overlap produces one copy; jittered overlaps merge; deliberate repeated words remain; empty chunks work.
- [ ] Boundary words and segment timing remain ordered and within source duration.
- [ ] Malformed later word entries, NaN, reverse timestamps, and Unicode fixtures produce a controlled result.
- [ ] A real multi-chunk speech fixture is transcribed and its boundary captions are inspected; synthetic unit tests alone do not certify speech accuracy.

## Deliverables and handoff

Transcript schema, overlap algorithm, language handling, and deterministic plus real-fixture checks.

Create or update docs/foundation/evidence/task-07.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

