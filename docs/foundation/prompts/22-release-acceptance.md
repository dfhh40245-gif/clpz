# Task 22 — Run end-to-end acceptance and prepare operations

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Verification + foundation.
Priority: Final gate.
Prerequisites: task 01, task 02, task 03, task 04, task 05, task 06, task 07, task 08, task 09, task 10, task 11, task 12, task 13, task 14, task 15, task 16, task 17, task 18, task 19, task 20, task 21.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Passing builds and a small test suite do not prove a working paid product, safe update, restored project, or clean-device installer. No full current release acceptance has been performed.

## Inspect these files

- docs/foundation/ACCEPTANCE.md
- docs/RELEASE.md
- docs/DEPLOYMENT.md
- docs/PRODUCTION_CONFIG.md
- website/app/api/health/route.ts
- backend/clpz_server.py
- .github/workflows/ci.yml
- .github/workflows/android-apk.yml

## Implementation steps

1. Run the release-scope acceptance matrix on the actual artifacts, not just development source; trace every task to evidence and recorded decisions.
2. Test Windows install/import/transcribe/edit/export/restart/upgrade/uninstall/restore and the cloud signup/purchase/fulfill/revoke/offline journey where in scope. Verify Android separately; defer it explicitly if not in this release.
3. Add redacted diagnostic bundles, job/event correlation, support runbooks for failed processing/payments, and tested release rollback. Keep credentials, raw media and transcripts out of default support bundles.
4. Verify dependency/native-binary provenance, secret scans, artifact hashes/signatures and download URLs; record outstanding risks and unverified external steps honestly. Prepare release notes and staging evidence; do not publish or charge customers as an incidental verification step.

## Acceptance checks — all required for this task

- [ ] Every in-scope acceptance row has command/manual procedure, expected result, actual result and evidence for the exact commit/artifact hash.
- [ ] No open P0/P1 blocker in the chosen release scope; an unavailable service/device is BLOCKED, not PASS.
- [ ] An independent person follows the setup/release/restore runbooks without undocumented steps.
- [ ] The final report distinguishes verified local behavior, staging/provider evidence, manual checks and approved deferrals; it never claims universal 100% correctness.

## Deliverables and handoff

Completed acceptance matrix, release evidence bundle, support/rollback runbooks and explicit go/no-go recommendation.

Create or update docs/foundation/evidence/task-22.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

