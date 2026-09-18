# Task 21 — Establish measurable clip quality and performance

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition.
Priority: P1 before product claims.
Prerequisites: task 05, task 06, task 07, task 11, task 13, task 18.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Prior evidence includes one short successful speech clip, not general quality/performance proof. Candidate ranking is heuristic with optional semantic ranking. Long videos, varied speakers/languages, crops and low-resource behavior need measured acceptance.

## Inspect these files

- backend/pipeline/analyzer.py
- backend/pipeline/transcriber.py
- backend/pipeline/captions.py
- backend/pipeline/cutter.py
- docs/audit_pipeline.py
- backend/tests/fixtures/generate_video.py
- README.md

## Implementation steps

1. Create a licensed/local fixture catalog: short and long speech, silence, multiple speakers, screen-share/facecam, portrait/landscape, variable frame rate, rotation metadata and agreed languages.
2. Measure timing per stage, peak RAM/disk, output validity, A/V sync, caption timing, crop subject retention and candidate completeness/nonduplication.
3. Define machine/hardware profiles and explicit pass thresholds before comparing outcomes; distinguish objective checks from human editorial ratings.
4. Evaluate optional semantic dependencies, fallback behavior and model/license provenance. Fix demonstrated quality failures within scope and align marketing claims with measured capability; do not promise viral performance or perfect transcription.

## Acceptance checks — all required for this task

- [ ] Publish repeatable commands, fixture provenance/hashes, machine specs, thresholds and results.
- [ ] Decode exported media and inspect representative frames/audio; no placeholder outputs pass.
- [ ] Long-video cancellation/low-disk/low-RAM cases fail gracefully and retain recoverable project state.
- [ ] A regression baseline makes future quality/speed changes comparable; untested languages/hardware remain explicitly unverified.

## Deliverables and handoff

Fixture/benchmark harness, quality rubric, measured report and supported-capability statement.

Create or update docs/foundation/evidence/task-21.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

