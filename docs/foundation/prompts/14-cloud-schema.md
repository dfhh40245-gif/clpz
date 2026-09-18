# Task 14 — Finish and test the cloud data foundation

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + foundation.
Priority: P0 before paid cloud launch.
Prerequisites: task 01, task 02, task 08, task 09.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

PUBLIC execution is now revoked in source, but no applied-role test was run. grant_credits checks external_ref plus txn_type rather than the supplied key/user; idempotency_key is globally unique. The promised subscription lifecycle is not fully constrained.

## Inspect these files

- supabase/migrations/0001_initial_schema.sql
- supabase/README.md
- website/lib/supabase-admin.ts
- website/lib/supabase/server.ts

## Implementation steps

1. Add forward migrations for already-created databases; do not rely on editing migration 0001 to repair deployed projects.
2. Make cloud ledger replay scope and payload conflict behavior transaction-safe. Use locking/unique constraints so concurrent calls return a defined result instead of misgranting or failing unpredictably.
3. Test real database roles: anon, authenticated user A, user B, and service role. Preserve restricted RPC execution and RLS on user/business tables.
4. Define subscription status/uniqueness, entitlement lifecycle and payment relationships; align profile metadata with website full_name/display_name fields. Review profile mutation and delete/account-lifecycle behavior. Use only a disposable/local database until deployment is separately authorized.
5. Model expiring subscription credits separately from never-expiring purchased credits if the current advertised 60-day rollover policy is retained. Define spend order, expiry, renewal and refund allocation; a single undifferentiated balance is insufficient.

## Acceptance checks — all required for this task

- [ ] Fresh migration and upgrade from the previous schema both succeed and retain data.
- [ ] Anon and normal users cannot grant credits or write payments/entitlements; A cannot read B's rows.
- [ ] Concurrent same-key grants apply once; different users/references are not incorrectly suppressed; changed payloads are rejected.
- [ ] Subscription and profile constraints are demonstrated with SQL assertions, including invalid state transitions and role-based access.

## Deliverables and handoff

Forward migrations, local database test harness, role/concurrency tests, and migration/rollback instructions.

Create or update docs/foundation/evidence/task-14.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

