# Task 20 — Make Android preview reliable and accurately described

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + addition.
Priority: P1 for Android launch.
Prerequisites: task 01, task 02, task 14, task 16.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Android suggestions are fixed timeline positions, not semantic analysis. The workflow publishes a debug APK before its downstream interface checks finish. Local project persistence/export exist but device lifecycle and production signing were not verified.

## Inspect these files

- mobile-android/app/src/main/java/com/clpz/mobile/MainActivity.kt
- mobile-android/app/src/main/java/com/clpz/mobile/ProjectStore.kt
- mobile-android/app/src/main/java/com/clpz/mobile/VideoExporter.kt
- mobile-android/app/src/main/java/com/clpz/mobile/VideoEffects.kt
- mobile-android/app/src/androidTest/java/com/clpz/mobile/StudioFlowTest.kt
- .github/workflows/android-apk.yml
- mobile-android/README.md

## Implementation steps

1. Label automatic suggestions as timeline drafts unless genuine analysis is separately implemented and evaluated. Do not assume an Android-to-local-FastAPI connection or add hosted video upload without a product decision.
2. Test and harden project persistence and source URI permissions across process death, revoked/moved files, rotation, duplicate saves, cancellation and low disk.
3. Validate exported trim, mute, aspect ratio and caption styles on real media/devices; expose useful recoverable export failures.
4. Make publication depend on required successful build/test jobs; separate preview and production channels, use a maintained Gradle wrapper/checksum and release signing strategy, and preserve the signing identity for upgrades. Keep keys outside source/APKs.

## Acceptance checks — all required for this task

- [ ] Import/save/kill/reopen/export succeeds on the supported minimum and a current Android version.
- [ ] Source permission loss or missing media is recoverable; repeated saves do not duplicate project IDs.
- [ ] Cancel/delete during export cleans partial files and does not report success.
- [ ] A deliberately failed interface test prevents publication; signed upgrades preserve local projects and authentication as specified.

## Deliverables and handoff

Android stability changes, accurate feature scope, device/emulator report and gated release pipeline.

Create or update docs/foundation/evidence/task-20.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.

