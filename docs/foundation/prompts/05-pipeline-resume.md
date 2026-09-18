# Task 05 — Make failed jobs resume safely

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

When parse and analyze are completed, _run_pipeline skips assigning transcript but uses it in analyzer.find_clips and caption rendering. A saved-stage probe reproduces UnboundLocalError.

## Inspect these files

- backend/jobs.py
- backend/main.py
- backend/pipeline/srt_parser.py
- backend/tests/test_remediation.py

## Implementation steps

1. Always reconstruct and validate transcript state from persisted SRT/word artifacts when resuming. Treat stage markers as claims requiring valid artifacts.
2. Reuse valid completed stages and clips; invalidate only the dependent stages when artifacts are missing, corrupt, or use an incompatible schema.
3. Define durable job/attempt/stage transitions and retry response behavior. Preserve successful outputs and cancellation state; reject simultaneous retries for one job.
4. Coordinate accounting hooks with tasks 08/09 without inventing a new paid retry policy. Do not solve the crash by blindly rerunning expensive successful work.

## Acceptance checks — all required for this task

- [ ] Inject one failure after download, transcription, parsing, analysis, and a partial render; each resume completes or returns a precise recoverable error.
- [ ] Missing/invalid words.json, SRT, and source media are handled predictably with no unbound variables.
- [ ] Restart an interrupted job and confirm consistent state, stable clip identity, and no duplicate worker.
- [ ] Completed clips are not lost and cancelled jobs do not become done accidentally.

## Deliverables and handoff

Resume/state contract, artifact validation, retry implementation, and stage-by-stage regression evidence.

Create or update docs/foundation/evidence/task-05.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

