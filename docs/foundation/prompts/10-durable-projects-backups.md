# Task 10 — Make projects durable and backups restorable

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + addition.
Priority: P1.
Prerequisites: task 02, task 05, task 08, task 09.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

_persist swallows both file and database errors. Startup loads job.json while SQLite is also written. backup_database always uses the same filename and its second run fails.

## Inspect these files

- backend/jobs.py
- backend/database.py
- backend/config.py
- desktop/server.py
- backend/clpz_server.py

## Implementation steps

1. Choose the authoritative job/project store in the architecture contract; treat other snapshots as derived and reconcile existing installations through a migration.
2. Use atomic file replacement and explicit persistence failure handling. A failed commit must not be reported as durable success.
3. Implement versioned database backups with SQLite-safe snapshotting and a manifest for source media, transcripts, edit versions and outputs. Bind SQL values safely, including paths containing apostrophes.
4. Provide a documented restore-to-new-directory workflow with validation before switching active data, schema compatibility checks and recovery/rollback. Never overwrite the only working copy.

## Acceptance checks — all required for this task

- [ ] Two backups succeed with distinct destinations; backup paths containing spaces/quotes work.
- [ ] Restore to a separate directory, reopen projects and decode exported media; compare counts/checksums.
- [ ] Inject write failure/crash during a save: prior committed data survives and the UI receives a useful failure.
- [ ] Old JSON/SQLite installations migrate once with no ghost projects, lost outputs, or silent state disagreement.

## Deliverables and handoff

Persistence migration, backup/restore tools, recovery runbook, and crash/restore evidence.

Create or update docs/foundation/evidence/task-10.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

