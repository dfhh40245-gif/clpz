# Task 16 — Connect desktop and mobile to shared accounts

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition.
Priority: P1 for commercial release.
Prerequisites: task 01, task 03, task 04, task 14, task 15.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Website and Android use Supabase, but desktop uses local SQLite sessions. There is no implemented website-to-desktop account/entitlement handoff; editable local credits cannot enforce paid cloud balances.

## Inspect these files

- desktop/app.py
- desktop/frozen_launcher.py
- backend/auth.py
- backend/main.py
- frontend/clpz.html
- mobile-android/app/src/main/java/com/clpz/mobile/AuthRepository.kt
- website/app/auth/callback/route.ts
- website/app/account/page.tsx

## Implementation steps

1. Design shared cloud identity and a secure desktop sign-in handoff with verified callback binding, expiring one-use exchange/state and replay protection. Prefer supported browser auth flows and do not pass long-lived credentials in links.
2. Keep processing/media local; cache only the minimum identity/entitlement data needed, store refresh credentials in platform-protected storage, and clear them on sign-out.
3. Implement server-authoritative entitlement and any usage-reservation/settlement API required by the chosen commercial model; never trust a desktop-reported balance.
4. Define offline grace, expiration/revocation, clock rollback, multi-device use and failed-job accounting. If these business choices are unresolved, finish the local protocol/tests with explicit blockers rather than silently choosing a paid policy.

## Acceptance checks — all required for this task

- [ ] The same cloud account sees the same purchased access on website, desktop and Android where supported.
- [ ] A copied/replayed/expired callback cannot sign another installation in; wrong state/issuer/audience fails.
- [ ] Editing local SQLite cannot mint cloud credits; duplicate reserve/settle operations are idempotent.
- [ ] Offline, expiry, revocation, restart and sign-out behave exactly as the approved policy and never upload media.

## Deliverables and handoff

Identity/entitlement protocol, secure client storage/handoff, local/cloud tests, and owner policy record.

Create or update docs/foundation/evidence/task-16.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

