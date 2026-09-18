# Task 02 — Make setup and automated checks reproducible

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + foundation.
Priority: P1.
Prerequisites: task 01.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

python-multipart and test dependencies are absent from the backend manifest; CI suppresses install failures and falls back to other dependencies. Website is not in main CI. The insufficient-credit test starts real failing background downloads and can race refunds.

## Inspect these files

- backend/requirements.txt
- requirements_desktop.txt
- backend/tests/conftest.py
- backend/tests/test_credits.py
- backend/TESTING.md
- .github/workflows/ci.yml
- frontend-app/package.json
- website/package.json
- package.json

## Implementation steps

1. Declare runtime, test, and desktop-build dependencies separately; resolve tested Python 3.12 environments with documented lock/update commands and platform-specific constraints where necessary. Preserve npm lockfiles and use npm ci.
2. Add a prerequisite/doctor command and one documented check command. Check Python, Node supported by the actual manifests, FFmpeg/ffprobe/downloader execution, free disk, dependency consistency, model status, and data path without exposing secrets.
3. Make tests hermetic: unique temporary data and ports, explicit server readiness and child cleanup, fake downloader/worker for ledger tests. Do not satisfy the insufficient-credit test by disabling legitimate refunds.
4. Remove CI dependency fallbacks; include backend checks, React build/tests/lint, website build/lint/tests, and artifact evidence on failure. Test configurations must not contact live account or payment services.

## Acceptance checks — all required for this task

- [ ] A clean checkout installs from committed manifests with no extra manual pip packages and passes pip check.
- [ ] Force a dependency-install failure and verify CI stops instead of substituting dependencies.
- [ ] Credit exhaustion is tested from a known balance with workers controlled; repeat the targeted concurrency tests without refund races.
- [ ] A deliberately occupied test port causes a safe failure or isolated alternative; no test reuses or deletes a user's application database.

## Deliverables and handoff

Complete manifests/locks, safe test harness, doctor/check scripts, CI updates, and exact fresh-machine commands.

Create or update docs/foundation/evidence/task-02.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

