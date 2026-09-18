# Task 09 — Scope retries and duplicate requests correctly

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P0 before relying on credits.
Prerequisites: task 02, task 03, task 08.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

An anonymous caller replaying another user's key receives the same job ID, although ownership checks still prevent reading it. Keys are globally mapped and not bound to operation/payload.

## Inspect these files

- backend/jobs.py
- backend/database.py
- backend/main.py
- frontend/clpz.html
- frontend-app/src/lib/api.ts

## Implementation steps

1. Use a durable unique scope such as principal/local-workspace, operation, and key plus a canonical payload fingerprint; define the local identity lifetime so restart behavior is intentional.
2. Same scoped key and same request returns the original durable result; changed content returns 409. Upload fingerprints must distinguish differing media without buffering full files into RAM.
3. Tie job insertion, charge, and idempotency mapping to a recoverable atomic workflow. Do not evict active operations in cleanup.
4. Define rejected/cancelled/retried upload behavior and keep a stable key in the UI until that logical request is resolved.

## Acceptance checks — all required for this task

- [ ] Same key across different users and URL/upload operations does not deduplicate unrelated work.
- [ ] Same key with changed URL/options/file returns 409 rather than a different or stale job.
- [ ] Concurrent identical submissions create one job and one debit across restart.
- [ ] Invalid uploads and cleanup do not trap users in unrecoverable dedupe results or permit duplicate charges.

## Deliverables and handoff

Scoped schema/migration, request fingerprint contract, client behavior, and concurrency/restart tests.

Create or update docs/foundation/evidence/task-09.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

