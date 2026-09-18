# Task 18 — Finish the desktop editor without losing existing work

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P1.
Prerequisites: task 01, task 02, task 06, task 07, task 10, task 11.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The active editor already has localStorage drafts and speed/mute/trim preview support. Text overlays are listed rather than rendered over the preview; drafts/exports are not durable backend edit versions. React workspace components are not routed.

## Inspect these files

- frontend/clpz.html
- frontend-app/src/App.tsx
- frontend-app/src/pages/app/Editor.tsx
- frontend-app/src/lib/api.ts
- backend/main.py
- backend/jobs.py

## Implementation steps

1. Extend the shipping UI chosen in task 01. Preserve its working drafts, keyboard controls and visual design; do not build the same feature in two separate workspaces.
2. Create a versioned edit/project schema and API covering source range, speed, volume, mute, overlays and supported caption/crop controls. Keep original media immutable.
3. Render overlays/captions at the correct preview coordinates and synchronize all controls, undo/redo, trim playback and saved versions. Clearly show any intentional preview/export limitation such as volume amplification.
4. Persist and reopen edit versions, expose resulting exports with their version/metadata, and validate schema migrations for existing localStorage drafts. Add functional client-contract tests instead of checking for strings in source.
5. Inventory remaining React login/animation code: if retained, connect or remove inactive reset/Google controls, associate labels, release WebGL resources and respect reduced motion/hidden pages; if retired, remove routes/assets through a documented migration rather than maintaining a second public account system.

## Acceptance checks — all required for this task

- [ ] Edit, close, restart, reopen and export: the same choices are restored and output matches preview within stated rendering tolerances.
- [ ] Text punctuation/Unicode and resized preview coordinate mapping remain correct.
- [ ] Undo/redo and keyboard focus work; malformed/stale drafts recover without destroying a valid project.
- [ ] No navigation opens an unrouted React editor; API response/types match runtime behavior.

## Deliverables and handoff

Versioned project/edit contract, preview and persistence integration, migration, and visual plus functional evidence.

Create or update docs/foundation/evidence/task-18.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

