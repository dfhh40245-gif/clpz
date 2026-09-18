# Task 12 — Repair installed Windows startup and shutdown

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1 release blocker.
Prerequisites: task 02, task 03.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Assembly puts the server in clpz_server/clpz_server.exe but _spawn_server checks only the install root, then falls back to absent backend source. Watchdog replacement is not stored in the handle used on close. setdefault allows inherited debug=1.

## Inspect these files

- desktop/frozen_launcher.py
- desktop/server.py
- backend/clpz_server.py
- packaging/build_windows.py
- packaging/clpz_launcher.spec
- backend/tests/test_desktop.py

## Implementation steps

1. Use a single explicit package-layout contract for locating the installed server, binaries, frontends and models. A frozen launcher must never fall back to running itself as a Python interpreter.
2. Keep the active child handle under coordinated ownership after watchdog replacement; shut down the replacement and descendants on close.
3. Force production security settings in frozen mode while keeping developer opt-in separate. Use validated application readiness rather than a listening port alone.
4. Capture startup errors in user-accessible logs and a useful dialog. Handle occupied ports, missing runtime assets, non-ASCII/spaced paths and writable per-user data directories.

## Acceptance checks — all required for this task

- [ ] A staged install-layout test chooses clpz_server/clpz_server.exe exactly; missing assets fail clearly.
- [ ] Run the installed build on a Windows account without Python; UI reaches /app.
- [ ] Kill the backend, observe one managed replacement, close the window, and verify neither process remains.
- [ ] Inherited CLPZ_DEBUG=1 cannot expose development endpoints in the frozen app; unrelated listeners cannot masquerade as readiness.

## Deliverables and handoff

Fixed launcher lifecycle, package-layout tests, and clean-machine startup/restart/shutdown evidence.

Create or update docs/foundation/evidence/task-12.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

