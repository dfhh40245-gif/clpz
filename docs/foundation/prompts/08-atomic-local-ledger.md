# Task 08 — Make local credit operations atomic

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P0 before relying on credits.
Prerequisites: task 01, task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Duplicate refund calls raise NameError. Bonus/refund/idempotency checks and mutations span separate calls. Payment recording and credit grant are separate commits; low-disk/retry paths need accounting consistency.

## Inspect these files

- backend/credits.py
- backend/database.py
- backend/jobs.py
- backend/gumroad.py
- backend/tests/test_credits.py
- backend/tests/test_gumroad.py

## Implementation steps

1. Define local credits as development/legacy accounting unless task 01 explicitly requires them; they must not become authoritative paid cloud entitlements.
2. Implement operation-key uniqueness and one database transaction per bonus/charge/refund, including the cached replay result. Scope operations to the correct user/job/attempt.
3. Specify charge lifecycle and connect all failure paths, including low disk, upload rejection, partial rendering, cancellation, restart and retry. Use the owner-approved charging rule.
4. If the local webhook is retained, atomically record payment fulfillment or use a durable retryable inbox. Persist original product/user/credit amounts for reversals; if retired, disable it explicitly.

## Acceptance checks — all required for this task

- [ ] A duplicate or zero-amount refund returns the correct balance without exception.
- [ ] Concurrent bonus, debit, and refund calls create exactly the permitted ledger entries, with no negative balances.
- [ ] Crash injection between record and fulfillment leaves a recoverable operation, and replay completes it once.
- [ ] Ledger totals reconcile to balances; fail/cancel/retry/low-disk paths match the documented charging policy.

## Deliverables and handoff

Migration, transactional ledger API, fault/concurrency tests, and accounting reconciliation command.

Create or update docs/foundation/evidence/task-08.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

