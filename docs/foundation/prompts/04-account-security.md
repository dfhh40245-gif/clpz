# Task 04 — Fix local admin and account recovery security

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P0 for account-enabled use.
Prerequisites: task 01, task 02, task 03.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Registering the configured admin email grants admin access before email verification. Fifteen wrong current-password reset attempts were not throttled. Email fallback prints codes with debug off; local hashing is unversioned PBKDF2-SHA256 at 100,000 iterations.

## Inspect these files

- backend/main.py
- backend/auth.py
- backend/database.py
- backend/email_service.py
- backend/tests/test_admin.py
- backend/tests/test_auth.py

## Implementation steps

1. Replace email-string authorization with trusted provisioning of an immutable user ID/role and verified identity. Apply one admin predicate to both admin endpoints and the job-ownership override. Provide a trusted local maintenance/provisioning command, not a public bootstrap route.
2. Throttle every password/code verification path by appropriate account and client identifiers; define cooldown and session revocation behavior.
3. Use versioned password hashes and a migration-on-success path based on current official password-storage guidance, with bounded input lengths and compatibility tests. If local auth is being retired, disable its exposed routes explicitly and provide a migration plan.
4. Permit development code output only with explicit debug settings. Production delivery failures must be surfaced truthfully without leaking codes, provider secrets, or whether an unrelated account exists.

## Acceptance checks — all required for this task

- [ ] An attacker registering the configured owner email gets neither admin endpoints nor ownership bypass.
- [ ] Verified normal users remain non-admin; only the trusted provisioned identity can administer.
- [ ] Repeated reset guesses reach 429; spoofed forwarding headers do not evade limits.
- [ ] Old valid passwords still work through migration; debug-off logs/responses contain no reset codes; mail failures do not falsely report successful delivery.

## Deliverables and handoff

Admin migration/provisioning instructions, account security fixes, and production-mode auth regression suite.

Create or update docs/foundation/evidence/task-04.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

