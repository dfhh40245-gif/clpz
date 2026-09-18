# Task 01 — Define one product and architecture contract

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Foundation.
Priority: First.
Prerequisites: none.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The diagram omits Supabase and the packaged launcher. The real pipeline transcribes before candidate analysis. The desktop opens the vanilla /app workspace; the React router only exposes landing/auth/done. Website and Android use Supabase while desktop accounts are SQLite.

## Inspect these files

- README.md
- docs/PRODUCTION_CONFIG.md
- docs/RELEASE.md
- desktop/app.py
- desktop/frozen_launcher.py
- frontend-app/src/App.tsx
- website/app/page.tsx
- mobile-android/README.md

## Implementation steps

1. Document current and intended architectures separately, including entry points, routes, data stores, trust boundaries, and dev versus installed paths.
2. Use the conservative baseline: Windows local processing and existing /app workspace are the first release; Next.js is the public site; Supabase owns cloud identity/business data; Android remains a separately labeled preview. Do not implement hosted video processing or migrate UI frameworks in this task.
3. Create an architecture decision record and a capabilities matrix: works, incomplete, untested, planned. Correct README and environment documentation against code.
4. Record owner decisions for paid feature versus usage-credit model, offline allowance, refund/retry charging, minimum hardware, Android release scope, and supported languages. Do not invent prices or commercially bind a choice. Dependent billing work may use fixtures until decisions are recorded.

## Acceptance checks — all required for this task

- [ ] Every diagram box maps to an existing file or an explicitly proposed component.
- [ ] The document names one shipping desktop UI and one authoritative store per data category.
- [ ] A new contributor can locate all three products and distinguish local anonymous use from cloud account access.
- [ ] All unresolved business choices have an owner and identify which later tasks they block.

## Deliverables and handoff

Architecture decision record, updated architecture diagram, route/data ownership table, product decisions, and corrected setup overview.

Create or update docs/foundation/evidence/task-01.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

