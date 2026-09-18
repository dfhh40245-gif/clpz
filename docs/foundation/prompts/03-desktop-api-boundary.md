# Task 03 — Protect the desktop's local API

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P0 before wider exposure.
Prerequisites: task 01, task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Anonymous jobs are permitted regardless of debug mode. Probes accepted an untrusted Host and a cancel POST from an untrusted Origin. Loopback binding helps but is not an application authorization boundary.

## Inspect these files

- backend/main.py
- backend/config.py
- desktop/server.py
- desktop/frozen_launcher.py
- backend/clpz_server.py
- frontend/clpz.html
- frontend-app/src/lib/api.ts

## Implementation steps

1. Make local desktop mode explicit on the server and bind it to loopback. Do not silently turn the media backend into a hosted service.
2. Validate Host and browser Origin for relevant routes and protect local API access with a per-launch capability. Design its bootstrap so it reaches only the intended UI, is not leaked through URLs/logs, and still supports video/image/range requests.
3. Distinguish same-origin browser requests, authenticated cloud calls if any, and native requests with no Origin. CORS alone is insufficient. Keep the private no-account workflow usable.
4. Enforce access checks across list/detail/upload/cancel/retry/edit/save/delete/admin routes, including anonymous local jobs and any new routes. Production startup must reject unsupported insecure modes.

## Acceptance checks — all required for this task

- [ ] Untrusted Host/Origin mutations fail; missing or stale capability fails; approved same-origin actions work.
- [ ] Token rotation invalidates the prior launch, and no token appears in logs or error text.
- [ ] Desktop import, video Range playback, thumbnails, export, and restart work with protection enabled.
- [ ] No normal launcher binds 0.0.0.0, and the desktop query parameter alone cannot enable privileged behavior.

## Deliverables and handoff

Documented local security boundary, launch/UI integration, and production-mode negative and positive regression tests.

Create or update docs/foundation/evidence/task-03.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

