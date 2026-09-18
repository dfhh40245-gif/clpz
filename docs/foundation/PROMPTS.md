# CLPZ implementation prompts

Generated from the audited foundation on 17 September 2026. These are proposed implementation instructions, not completed work. Copy **one task** at a time into a coding agent with this repository open. See [START HERE](README.md) for order and [AUDIT](AUDIT.md) for evidence. Each task is also available as a separate file under prompts/.

- [Task 01: Define one product and architecture contract](prompts/01-product-contract.md)
- [Task 02: Make setup and automated checks reproducible](prompts/02-reproducible-development.md)
- [Task 03: Protect the desktop's local API](prompts/03-desktop-api-boundary.md)
- [Task 04: Fix local admin and account recovery security](prompts/04-account-security.md)
- [Task 05: Make failed jobs resume safely](prompts/05-pipeline-resume.md)
- [Task 06: Fix mute, speed, trim, and text export](prompts/06-export-correctness.md)
- [Task 07: Fix chunk overlap and transcript validation](prompts/07-transcript-integrity.md)
- [Task 08: Make local credit operations atomic](prompts/08-atomic-local-ledger.md)
- [Task 09: Scope retries and duplicate requests correctly](prompts/09-request-idempotency.md)
- [Task 10: Make projects durable and backups restorable](prompts/10-durable-projects-backups.md)
- [Task 11: Bound heavy work and make cancellation reliable](prompts/11-bounded-media-workers.md)
- [Task 12: Repair installed Windows startup and shutdown](prompts/12-desktop-launcher.md)
- [Task 13: Produce verified Windows installers and media tools](prompts/13-release-build-toolchain.md)
- [Task 14: Finish and test the cloud data foundation](prompts/14-cloud-schema.md)
- [Task 15: Connect purchases to accounts and entitlements](prompts/15-payment-fulfillment.md)
- [Task 16: Connect desktop and mobile to shared accounts](prompts/16-shared-identity-entitlements.md)
- [Task 17: Complete the website account and download journey](prompts/17-website-account-download.md)
- [Task 18: Finish the desktop editor without losing existing work](prompts/18-editor-project-contract.md)
- [Task 19: Add safe project deletion and scalable library browsing](prompts/19-project-library-storage.md)
- [Task 20: Make Android preview reliable and accurately described](prompts/20-android-readiness.md)
- [Task 21: Establish measurable clip quality and performance](prompts/21-media-quality-benchmarks.md)
- [Task 22: Run end-to-end acceptance and prepare operations](prompts/22-release-acceptance.md)

---

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


---

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


---

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


---

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


---

# Task 05 — Make failed jobs resume safely

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

When parse and analyze are completed, _run_pipeline skips assigning transcript but uses it in analyzer.find_clips and caption rendering. A saved-stage probe reproduces UnboundLocalError.

## Inspect these files

- backend/jobs.py
- backend/main.py
- backend/pipeline/srt_parser.py
- backend/tests/test_remediation.py

## Implementation steps

1. Always reconstruct and validate transcript state from persisted SRT/word artifacts when resuming. Treat stage markers as claims requiring valid artifacts.
2. Reuse valid completed stages and clips; invalidate only the dependent stages when artifacts are missing, corrupt, or use an incompatible schema.
3. Define durable job/attempt/stage transitions and retry response behavior. Preserve successful outputs and cancellation state; reject simultaneous retries for one job.
4. Coordinate accounting hooks with tasks 08/09 without inventing a new paid retry policy. Do not solve the crash by blindly rerunning expensive successful work.

## Acceptance checks — all required for this task

- [ ] Inject one failure after download, transcription, parsing, analysis, and a partial render; each resume completes or returns a precise recoverable error.
- [ ] Missing/invalid words.json, SRT, and source media are handled predictably with no unbound variables.
- [ ] Restart an interrupted job and confirm consistent state, stable clip identity, and no duplicate worker.
- [ ] Completed clips are not lost and cancelled jobs do not become done accidentally.

## Deliverables and handoff

Resume/state contract, artifact validation, retry implementation, and stage-by-stage regression evidence.

Create or update docs/foundation/evidence/task-05.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 06 — Fix mute, speed, trim, and text export

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

A normal real FFmpeg edit passes; muted export returns 500 because validation requires audio; speed 0.25 returns 500 because atempo=0.25 is invalid for the bundled FFmpeg.

## Inspect these files

- backend/main.py
- backend/jobs.py
- backend/pipeline/cutter.py
- backend/tests/test_remediation.py

## Implementation steps

1. Make output validation aware of intentionally absent audio without weakening audio requirements for normal renders.
2. Compose valid audio-tempo stages across the full accepted 0.25–4 speed range and keep trim semantics on the source timeline.
3. Audit text filter quoting for apostrophes, percent signs, backslashes, colons, commas, brackets, Unicode and line breaks; prefer robust text-file/filter construction rather than shell interpolation.
4. Render into unique temporary outputs, validate before promotion, clean failed files, and preserve the original. Handle simultaneous exports without writing the same path; later integrate with the bounded worker service.

## Acceptance checks — all required for this task

- [ ] Generate a local video with audio; export at 0.25, 0.5, 1, 2, and 4 speed, muted and unmuted.
- [ ] ffprobe verifies expected dimensions, codecs, audio presence, and duration within a frame/encoder tolerance; decode actual frames.
- [ ] Trim plus speed plus mute plus text succeeds; invalid ranges and nonfinite numbers return 4xx.
- [ ] Two exports of the same clip cannot corrupt or overwrite each other's output; cancellation/failure leaves the original intact.

## Deliverables and handoff

Correct rendering/validation and fixture-based media tests, including decoded output checks.

Create or update docs/foundation/evidence/task-06.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 07 — Fix chunk overlap and transcript validation

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P1.
Prerequisites: task 02, task 05.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Merging two identical overlapping two-word chunks returns four words and two segments. Language metadata is dropped in _transcribe_chunk. SRT fallback tokenization only recognizes ASCII alphanumerics.

## Inspect these files

- backend/pipeline/transcriber.py
- backend/pipeline/srt_parser.py
- backend/pipeline/captions.py
- backend/pipeline/analyzer.py
- backend/tests/test_pipeline.py

## Implementation steps

1. Reconcile complete overlap intervals after ordering/alignment; preserve genuine repeated speech rather than globally deduplicating words.
2. Carry language/confidence metadata where available and validate every word/segment, not only the first JSON entry.
3. Validate finite ordered timestamps, nonnegative durations, source bounds, and SRT millisecond carry. Distinguish precise timings from fallback estimates.
4. Support the languages agreed in task 01 in fallback tokenization and font coverage; document unsupported scripts instead of silently producing empty captions.

## Acceptance checks — all required for this task

- [ ] Identical overlap produces one copy; jittered overlaps merge; deliberate repeated words remain; empty chunks work.
- [ ] Boundary words and segment timing remain ordered and within source duration.
- [ ] Malformed later word entries, NaN, reverse timestamps, and Unicode fixtures produce a controlled result.
- [ ] A real multi-chunk speech fixture is transcribed and its boundary captions are inspected; synthetic unit tests alone do not certify speech accuracy.

## Deliverables and handoff

Transcript schema, overlap algorithm, language handling, and deterministic plus real-fixture checks.

Create or update docs/foundation/evidence/task-07.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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


---

# Task 09 — Scope retries and duplicate requests correctly

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix.
Priority: P0 before relying on credits.
Prerequisites: task 02, task 03, task 08.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

An anonymous caller replaying another user's key receives the same job ID, although ownership checks still prevent reading it. Keys are globally mapped and not bound to operation/payload.

## Inspect these files

- backend/jobs.py
- backend/database.py
- backend/main.py
- frontend/clpz.html
- frontend-app/src/lib/api.ts

## Implementation steps

1. Use a durable unique scope such as principal/local-workspace, operation, and key plus a canonical payload fingerprint; define the local identity lifetime so restart behavior is intentional.
2. Same scoped key and same request returns the original durable result; changed content returns 409. Upload fingerprints must distinguish differing media without buffering full files into RAM.
3. Tie job insertion, charge, and idempotency mapping to a recoverable atomic workflow. Do not evict active operations in cleanup.
4. Define rejected/cancelled/retried upload behavior and keep a stable key in the UI until that logical request is resolved.

## Acceptance checks — all required for this task

- [ ] Same key across different users and URL/upload operations does not deduplicate unrelated work.
- [ ] Same key with changed URL/options/file returns 409 rather than a different or stale job.
- [ ] Concurrent identical submissions create one job and one debit across restart.
- [ ] Invalid uploads and cleanup do not trap users in unrecoverable dedupe results or permit duplicate charges.

## Deliverables and handoff

Scoped schema/migration, request fingerprint contract, client behavior, and concurrency/restart tests.

Create or update docs/foundation/evidence/task-09.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 10 — Make projects durable and backups restorable

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + addition.
Priority: P1.
Prerequisites: task 02, task 05, task 08, task 09.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

_persist swallows both file and database errors. Startup loads job.json while SQLite is also written. backup_database always uses the same filename and its second run fails.

## Inspect these files

- backend/jobs.py
- backend/database.py
- backend/config.py
- desktop/server.py
- backend/clpz_server.py

## Implementation steps

1. Choose the authoritative job/project store in the architecture contract; treat other snapshots as derived and reconcile existing installations through a migration.
2. Use atomic file replacement and explicit persistence failure handling. A failed commit must not be reported as durable success.
3. Implement versioned database backups with SQLite-safe snapshotting and a manifest for source media, transcripts, edit versions and outputs. Bind SQL values safely, including paths containing apostrophes.
4. Provide a documented restore-to-new-directory workflow with validation before switching active data, schema compatibility checks and recovery/rollback. Never overwrite the only working copy.

## Acceptance checks — all required for this task

- [ ] Two backups succeed with distinct destinations; backup paths containing spaces/quotes work.
- [ ] Restore to a separate directory, reopen projects and decode exported media; compare counts/checksums.
- [ ] Inject write failure/crash during a save: prior committed data survives and the UI receives a useful failure.
- [ ] Old JSON/SQLite installations migrate once with no ghost projects, lost outputs, or silent state disagreement.

## Deliverables and handoff

Persistence migration, backup/restore tools, recovery runbook, and crash/restore evidence.

Create or update docs/foundation/evidence/task-10.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 11 — Bound heavy work and make cancellation reliable

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + foundation.
Priority: P1.
Prerequisites: task 02, task 05, task 06, task 09, task 10.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Deadlines are checked between stages; a stuck in-process model can retain a job slot. Queue threads are unbounded. Upload parsing precedes the copied-byte cap, synchronous probes run in an async handler, and edits bypass the job semaphore.

## Inspect these files

- backend/jobs.py
- backend/main.py
- backend/proc.py
- backend/pipeline/transcriber.py
- backend/pipeline/downloader.py
- backend/pipeline/cutter.py

## Implementation steps

1. Introduce bounded admission and worker execution shared by jobs and edits. Keep the HTTP loop responsive; return an explicit queue-full response before charging/admitting work.
2. Run uninterruptible heavy stages in supervised worker processes or an equivalent mechanism that can enforce real deadlines. Propagate cancellation to FFmpeg, ffprobe, transcription and descendants.
3. Limit incoming body bytes before full multipart parsing; also count streamed bytes when Content-Length is missing or false. Validate file/media constraints and reserve disk safely.
4. Use temporary outputs, per-clip coordination, deterministic cleanup, and durable progress/error transitions. Avoid process-kill implementations that can terminate unrelated user processes.

## Acceptance checks — all required for this task

- [ ] A deliberately stuck transcription worker is stopped within the configured deadline plus documented cleanup allowance; another queued job can proceed.
- [ ] Cancellation works during download, audio extraction, transcription and edit rendering; no child or temp output remains.
- [ ] Oversized/lying/chunked requests are rejected with bounded memory/disk use.
- [ ] Concurrent imports/edits stay within configured limits and health/status requests remain responsive under load.

## Deliverables and handoff

Worker/admission design, implementation, resource settings, and measured cancellation/load tests.

Create or update docs/foundation/evidence/task-11.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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


---

# Task 13 — Produce verified Windows installers and media tools

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + addition.
Priority: P1 release blocker.
Prerequisites: task 02, task 12.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The bundled yt-dlp executable exits 1 on --version, while python -m yt_dlp works in the audit venv. The build does not rebuild React or invoke Inno Setup, passes --specpath with existing specs, and package audit can report clean on an absent/empty output.

## Inspect these files

- packaging/build_windows.py
- packaging/clpz_server.spec
- packaging/clpz_launcher.spec
- packaging/clpz_installer.iss
- packaging/RELEASE_SHA256.txt
- backend/bin/yt-dlp.exe
- backend/pipeline/downloader.py
- docs/RELEASE.md

## Implementation steps

1. Diagnose the bundled downloader on a clean Windows machine; use a verified supported standalone artifact or a packaged module strategy, with provenance, checksum and version. Do not blindly replace binaries or depend on the developer's Python path.
2. Create one release command that builds required UI, freezes both executables using valid spec-mode options, assembles assets, bundles offline model/VAD files, and invokes Inno Setup.
3. Fail missing/empty package audits and missing binaries/models/fonts. Execute all bundled tools' version/smoke checks; do not accept file existence alone.
4. Centralize versioning; generate artifact hashes, dependency/native-tool notices and a release manifest. Separate assembly from signing/publishing and use explicit destinations. Document signing prerequisites without inventing certificates.

## Acceptance checks — all required for this task

- [ ] A clean build needs no stale dist or manually copied outputs and yields the documented installer filename.
- [ ] Package checks fail if output is missing or one required asset/tool fails.
- [ ] Install and process a local speech fixture offline on a machine with no Python; every bundled executable works.
- [ ] Install, upgrade and uninstall retain user projects according to the documented policy; release hashes correspond to the actual tested files.

## Deliverables and handoff

Reproducible release command, verified tool/model acquisition, installer, manifest, and clean-machine procedure.

Create or update docs/foundation/evidence/task-13.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 14 — Finish and test the cloud data foundation

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Fix + foundation.
Priority: P0 before paid cloud launch.
Prerequisites: task 01, task 02, task 08, task 09.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

PUBLIC execution is now revoked in source, but no applied-role test was run. grant_credits checks external_ref plus txn_type rather than the supplied key/user; idempotency_key is globally unique. The promised subscription lifecycle is not fully constrained.

## Inspect these files

- supabase/migrations/0001_initial_schema.sql
- supabase/README.md
- website/lib/supabase-admin.ts
- website/lib/supabase/server.ts

## Implementation steps

1. Add forward migrations for already-created databases; do not rely on editing migration 0001 to repair deployed projects.
2. Make cloud ledger replay scope and payload conflict behavior transaction-safe. Use locking/unique constraints so concurrent calls return a defined result instead of misgranting or failing unpredictably.
3. Test real database roles: anon, authenticated user A, user B, and service role. Preserve restricted RPC execution and RLS on user/business tables.
4. Define subscription status/uniqueness, entitlement lifecycle and payment relationships; align profile metadata with website full_name/display_name fields. Review profile mutation and delete/account-lifecycle behavior. Use only a disposable/local database until deployment is separately authorized.
5. Model expiring subscription credits separately from never-expiring purchased credits if the current advertised 60-day rollover policy is retained. Define spend order, expiry, renewal and refund allocation; a single undifferentiated balance is insufficient.

## Acceptance checks — all required for this task

- [ ] Fresh migration and upgrade from the previous schema both succeed and retain data.
- [ ] Anon and normal users cannot grant credits or write payments/entitlements; A cannot read B's rows.
- [ ] Concurrent same-key grants apply once; different users/references are not incorrectly suppressed; changed payloads are rejected.
- [ ] Subscription and profile constraints are demonstrated with SQL assertions, including invalid state transitions and role-based access.

## Deliverables and handoff

Forward migrations, local database test harness, role/concurrency tests, and migration/rollback instructions.

Create or update docs/foundation/evidence/task-14.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

# Task 15 — Connect purchases to accounts and entitlements

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P0 before accepting payment.
Prerequisites: task 01, task 02, task 14.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The current website webhook upserts payment fields but never associates a user or grants credits/entitlements. One configured product permalink is accepted despite multiple checkout products. Replayed paid events can overwrite a later refund status. The /buy page says coming soon, but GumroadCheckoutBridge rewrites links to live checkout whenever URLs are configured; this is not an explicit launch gate.

## Inspect these files

- website/app/api/checkout-link/route.ts
- website/app/api/gumroad/ping/route.ts
- website/app/buy/page.tsx
- website/components/gumroad-checkout-bridge.tsx
- website/lib/supabase-admin.ts
- backend/gumroad.py
- supabase/migrations/0001_initial_schema.sql

## Implementation steps

1. Verify the current provider contract from official documentation and captured sandbox deliveries; do not reuse the local signed-JSON assumption for the website's form-based Ping route.
2. Create server-controlled checkout/account association and product-to-entitlement mapping for every advertised plan. Verify buyer/account association; an arbitrary client-supplied user ID is not sufficient.
3. Persist a durable webhook inbox and implement atomic or reliably retryable fulfillment, with dedupe and ordered state transitions for purchases, renewals, refunds/disputes and cancellations. Store original granted amounts and product versions.
4. Add reconciliation for unlinked/failed events and provider redelivery, redacted diagnostics and a support resolution path. Use the owner-approved refund/offline/credit policies; do not execute live charges during development.
5. Add a fail-closed checkout feature gate until lifecycle acceptance passes, independent of configured URLs. Reconcile displayed prices/credits/rollover promises with provider products and database rules.

## Acceptance checks — all required for this task

- [ ] A sandbox purchase grants only the intended account/product once; anonymous/unlinked purchases remain recoverable.
- [ ] Duplicates, concurrent deliveries, old paid events after refunds, and crashes between receipt/grant produce correct final state.
- [ ] All offered products are tested; malformed/unauthorized events fail without fulfillment.
- [ ] Reconciliation finds and resolves an intentionally interrupted delivery; the provider event and database ledger can be traced without exposing secrets.

## Deliverables and handoff

Provider contract fixtures, payment/account mapping, fulfillment/reconciliation implementation, and lifecycle evidence.

Create or update docs/foundation/evidence/task-15.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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


---

# Task 17 — Complete the website account and download journey

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P1.
Prerequisites: task 01, task 02, task 14, task 15, task 16.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

The current website builds and lints successfully, and its Google action exists. Account page only offers downloads; password recovery is absent from the form. Download destinations and Vercel build-root instructions differ across files. A local Node URL probe shows that next=/\\untrusted.example passes the callback guard but resolves to an external origin; this is a confirmed validation defect, not a demonstrated stolen session.

## Inspect these files

- website/app/login/auth-form.tsx
- website/app/login/google-button.tsx
- website/app/auth/callback/route.ts
- website/app/account/page.tsx
- website/app/download/route.ts
- website/app/download/android/route.ts
- website/.env.example
- website/vercel.json
- vercel.json

## Implementation steps

1. Complete confirmation, login/logout, expired session, password reset/recovery and provider-error states with accessible feedback.
2. Show real subscription/credits/entitlements from the cloud contract. Do not display a successful purchase merely because the browser returned from checkout.
3. Resolve one deployment-root convention with deterministic installs and validated configuration; make missing config and unavailable downloads understandable.
4. Choose one release source per platform, validate URLs and artifact versions/hashes, distinguish Android preview from stable Windows, and test redirect safety including slash/backslash-encoded callback variants.
5. Fix callback redirects by resolving against the approved origin and checking the normalized destination origin/path, rather than relying on startsWith alone. Test the URL logic without requiring real OAuth credentials.

## Acceptance checks — all required for this task

- [ ] New user confirmation, Google sign-in, forgotten password, logout and expired callback all have browser-test coverage.
- [ ] Account data is isolated by user and updates after verified fulfillment.
- [ ] Download links resolve to the intended tested artifact in staging; a missing artifact produces useful UI.
- [ ] Keyboard/mobile-width/accessibility checks pass; both build and production serving work using the documented root/settings.
- [ ] Backslash, double-slash, encoded and absolute external next values cannot redirect outside the site after OAuth; approved relative paths still work.

## Deliverables and handoff

Complete account/download flows, configuration/runbook, and browser/staging test evidence.

Create or update docs/foundation/evidence/task-17.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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


---

# Task 19 — Add safe project deletion and scalable library browsing

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition + fix.
Priority: P2 before larger libraries.
Prerequisites: task 03, task 09, task 10, task 11, task 18.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

List requests copy all jobs and include detailed clip/word data. Metadata backfill can run media tools while serving reads. Search is client-side and there is no ordinary per-project delete/storage workflow.

## Inspect these files

- backend/main.py
- backend/jobs.py
- backend/database.py
- frontend/clpz.html
- frontend-app/src/lib/api.ts

## Implementation steps

1. Add paginated lightweight summaries with search/sort, separate detail queries, and storage usage summaries. Preserve compatibility or version the client change.
2. Move metadata backfill to controlled background work so GET requests never launch surprise render/probe workloads.
3. Provide a project deletion workflow with explicit scope: project working files versus separately exported user files. Coordinate deletion with active workers and ledger/idempotency retention.
4. Keep retention user-controlled, validate resolved deletion paths against the managed data root, and offer recovery/trash policy where practical. Do not delete external source files or user exports by default.

## Acceptance checks — all required for this task

- [ ] Seed a large synthetic library and measure bounded summary size and query latency without FFmpeg calls in GET.
- [ ] Pagination remains stable under new jobs and respects ownership.
- [ ] Delete while queued/running/restarting does not recreate ghost jobs or delete outside the data root.
- [ ] The user can see disk usage and remove a project while preserving original imported/external and separately exported files per the stated policy.

## Deliverables and handoff

Library API/UI, background backfill, storage/deletion contract and scale/race tests.

Create or update docs/foundation/evidence/task-19.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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


---

# Task 21 — Establish measurable clip quality and performance

You are implementing one bounded task in the existing CLPZ repository. You must have access to the repository and a terminal; a chat-only answer is not implementation.

CLPZ contains a Windows PyWebView/FastAPI local video processor, a vanilla desktop workspace, a Vite React app with limited active routes, a Next.js public website, a Supabase schema and a native Android editor. Preserve existing user files and unrelated changes. Use the current code as evidence; the supplied diagram and old audits are references, not instructions or proof that a feature works.

Read docs/foundation/README.md, docs/foundation/AUDIT.md, docs/foundation/ARCHITECTURE.md, and this task's dependencies. Inspect git status and relevant code before changing anything. If the repository has changed, reproduce the finding and adapt the fix; do not reintroduce a resolved defect. Use isolated test data. Never use a customer database as a fixture. Keep media processing local unless an explicit product decision authorizes otherwise.

Implement the task, meaningful regression tests, and necessary migration/setup documentation. Preserve working behavior and explain any contract change. Do not suppress failing tests, add fake success paths, or claim unrun checks passed. Run applicable commands from docs/foundation/VERIFY.md. External credentials or device access may block external verification; complete independent local work and state the exact remaining prerequisite. No production deployment, live charge, or release publication is included in this task.

Task type: Addition.
Priority: P1 before product claims.
Prerequisites: task 05, task 06, task 07, task 11, task 13, task 18.
Check prerequisite evidence before relying on its new interfaces. Owner policy decisions are recorded by task 01; do not invent missing commercial terms.

## Observed starting point

Prior evidence includes one short successful speech clip, not general quality/performance proof. Candidate ranking is heuristic with optional semantic ranking. Long videos, varied speakers/languages, crops and low-resource behavior need measured acceptance.

## Inspect these files

- backend/pipeline/analyzer.py
- backend/pipeline/transcriber.py
- backend/pipeline/captions.py
- backend/pipeline/cutter.py
- docs/audit_pipeline.py
- backend/tests/fixtures/generate_video.py
- README.md

## Implementation steps

1. Create a licensed/local fixture catalog: short and long speech, silence, multiple speakers, screen-share/facecam, portrait/landscape, variable frame rate, rotation metadata and agreed languages.
2. Measure timing per stage, peak RAM/disk, output validity, A/V sync, caption timing, crop subject retention and candidate completeness/nonduplication.
3. Define machine/hardware profiles and explicit pass thresholds before comparing outcomes; distinguish objective checks from human editorial ratings.
4. Evaluate optional semantic dependencies, fallback behavior and model/license provenance. Fix demonstrated quality failures within scope and align marketing claims with measured capability; do not promise viral performance or perfect transcription.

## Acceptance checks — all required for this task

- [ ] Publish repeatable commands, fixture provenance/hashes, machine specs, thresholds and results.
- [ ] Decode exported media and inspect representative frames/audio; no placeholder outputs pass.
- [ ] Long-video cancellation/low-disk/low-RAM cases fail gracefully and retain recoverable project state.
- [ ] A regression baseline makes future quality/speed changes comparable; untested languages/hardware remain explicitly unverified.

## Deliverables and handoff

Fixture/benchmark harness, quality rubric, measured report and supported-capability statement.

Create or update docs/foundation/evidence/task-21.md with:
- Original reproduction and observed behavior.
- Changed files, design choices, and compatibility/migration notes.
- Exact commands, exit codes, test counts and relevant artifact paths.
- One PASS / FAIL / BLOCKED / NOT RUN entry for each acceptance check.
- Rollback/recovery instructions for migrations or stored-data changes.
- Any prerequisite needed from the owner and the next unblocked task.

End with a concise account of what changed, what was verified, and what remains. A task is complete only when its in-scope acceptance checks pass with evidence; a mocked provider test is not proof of live provider integration.


---

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

