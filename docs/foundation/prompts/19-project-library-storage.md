# Task 19 — Add safe project deletion and scalable library browsing

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P2 before larger libraries.
Prerequisites: task 03, task 09, task 10, task 11, task 18.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

List requests copy all jobs and include detailed clip/word data. Metadata backfill can run media tools while serving reads. Search is client-side and there is no ordinary per-project delete/storage workflow.

## Inspect these files

- backend/main.py
- backend/jobs.py
- backend/database.py
- frontend/clpz.html
- frontend-app/src/lib/api.ts

## Implementation steps

1. Add paginated lightweight summaries with search/sort, separate detail queries, and storage usage summaries. Preserve compatibility or version the client change.
2. Move metadata backfill to controlled background work so GET requests never launch surprise render/probe workloads.
3. Provide a project deletion workflow with explicit scope: project working files versus separately exported user files. Coordinate deletion with active workers and ledger/idempotency retention.
4. Keep retention user-controlled, validate resolved deletion paths against the managed data root, and offer recovery/trash policy where practical. Do not delete external source files or user exports by default.

## Acceptance checks — all required for this task

- [ ] Seed a large synthetic library and measure bounded summary size and query latency without FFmpeg calls in GET.
- [ ] Pagination remains stable under new jobs and respects ownership.
- [ ] Delete while queued/running/restarting does not recreate ghost jobs or delete outside the data root.
- [ ] The user can see disk usage and remove a project while preserving original imported/external and separately exported files per the stated policy.

## Deliverables and handoff

Library API/UI, background backfill, storage/deletion contract and scale/race tests.

Create or update docs/foundation/evidence/task-19.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

