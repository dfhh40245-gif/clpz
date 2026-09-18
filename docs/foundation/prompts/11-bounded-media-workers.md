# Task 11 — Bound heavy work and make cancellation reliable

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + foundation.
Priority: P1.
Prerequisites: task 02, task 05, task 06, task 09, task 10.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Deadlines are checked between stages; a stuck in-process model can retain a job slot. Queue threads are unbounded. Upload parsing precedes the copied-byte cap, synchronous probes run in an async handler, and edits bypass the job semaphore.

## Inspect these files

- backend/jobs.py
- backend/main.py
- backend/proc.py
- backend/pipeline/transcriber.py
- backend/pipeline/downloader.py
- backend/pipeline/cutter.py

## Implementation steps

1. Introduce bounded admission and worker execution shared by jobs and edits. Keep the HTTP loop responsive; return an explicit queue-full response before charging/admitting work.
2. Run uninterruptible heavy stages in supervised worker processes or an equivalent mechanism that can enforce real deadlines. Propagate cancellation to FFmpeg, ffprobe, transcription and descendants.
3. Limit incoming body bytes before full multipart parsing; also count streamed bytes when Content-Length is missing or false. Validate file/media constraints and reserve disk safely.
4. Use temporary outputs, per-clip coordination, deterministic cleanup, and durable progress/error transitions. Avoid process-kill implementations that can terminate unrelated user processes.

## Acceptance checks — all required for this task

- [ ] A deliberately stuck transcription worker is stopped within the configured deadline plus documented cleanup allowance; another queued job can proceed.
- [ ] Cancellation works during download, audio extraction, transcription and edit rendering; no child or temp output remains.
- [ ] Oversized/lying/chunked requests are rejected with bounded memory/disk use.
- [ ] Concurrent imports/edits stay within configured limits and health/status requests remain responsive under load.

## Deliverables and handoff

Worker/admission design, implementation, resource settings, and measured cancellation/load tests.

Create or update docs/foundation/evidence/task-11.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

