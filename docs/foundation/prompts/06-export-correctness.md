# Task 06 — Fix mute, speed, trim, and text export

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

A normal real FFmpeg edit passes; muted export returns 500 because validation requires audio; speed 0.25 returns 500 because atempo=0.25 is invalid for the bundled FFmpeg.

## Inspect these files

- backend/main.py
- backend/jobs.py
- backend/pipeline/cutter.py
- backend/tests/test_remediation.py

## Implementation steps

1. Make output validation aware of intentionally absent audio without weakening audio requirements for normal renders.
2. Compose valid audio-tempo stages across the full accepted 0.25–4 speed range and keep trim semantics on the source timeline.
3. Audit text filter quoting for apostrophes, percent signs, backslashes, colons, commas, brackets, Unicode and line breaks; prefer robust text-file/filter construction rather than shell interpolation.
4. Render into unique temporary outputs, validate before promotion, clean failed files, and preserve the original. Handle simultaneous exports without writing the same path; later integrate with the bounded worker service.

## Acceptance checks — all required for this task

- [ ] Generate a local video with audio; export at 0.25, 0.5, 1, 2, and 4 speed, muted and unmuted.
- [ ] ffprobe verifies expected dimensions, codecs, audio presence, and duration within a frame/encoder tolerance; decode actual frames.
- [ ] Trim plus speed plus mute plus text succeeds; invalid ranges and nonfinite numbers return 4xx.
- [ ] Two exports of the same clip cannot corrupt or overwrite each other's output; cancellation/failure leaves the original intact.

## Deliverables and handoff

Correct rendering/validation and fixture-based media tests, including decoded output checks.

Create or update docs/foundation/evidence/task-06.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

