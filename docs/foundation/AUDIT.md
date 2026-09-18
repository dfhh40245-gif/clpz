# CLPZ current audit — 17 September 2026

**Assessment: a working development base with concrete release blockers and incomplete commercial integration.** This is an evidence-based repair plan, not a numerical quality score or certification.

Reviewed the current tracked project (199 files), the supplied architecture diagram, and the 8 September audit. Baseline commit: **76e4b0a**. Ignored prototype folders were not treated as shipping code. Existing application source was left unchanged; this foundation and its evidence were added.

## Checks actually performed

| Check | Current result | Limit |
|---|---|---|
| React TypeScript + Vite production build | PASS | Used existing node_modules, not a clean npm install |
| Existing frontend tests | 3 PASS | They exercise vanilla workspace behavior, not the complete React or website journey |
| React lint | 9 warnings, no errors | Includes hooks/dependency/purity warnings |
| Next.js production build | PASS | Existing node_modules and local build environment; not live auth/payment validation |
| Website ESLint | PASS | Does not prove functional completeness |
| Backend non-slow suite | 110 passed, 2 failed, 1 skipped, 9 deselected | Fresh Python 3.12 venv with extra undeclared test/multipart dependencies |
| Credit exhaustion test, isolated retry | FAIL again: 200 instead of expected 402 | Test starts real failing jobs; refund race is a plausible explanation, not established credit bypass |
| Bundled downloader | yt-dlp.exe --version exits 1, no stdout/stderr | Root cause not established; Python module reports 2026.08.19 successfully |
| Python dependency consistency | pip check PASS | Audit environment only; not a vulnerability scan or lockfile |
| Real FFmpeg editor fixture | Normal edit PASS; mute and 0.25× FAIL | Generated one-second source, not a full speech-quality benchmark |
| Security/retry/refund/backup probes | Defects reproduced below | Isolated fake accounts/temp data; no live account/provider mutation |
| Installed launcher layout probe | Wrong child path reproduced with mocked Popen | No real installed EXE launched |
| OAuth callback guard expression | External-origin URL passes current check | URL logic reproduced in Node, not a live OAuth attack |
| Android/device/installer/cloud-role tests | NOT RUN | No acceptance claimed |

See [baseline checks](evidence/baseline-checks.json), [isolated probe results](evidence/current-probes.json), and [repeatable commands](VERIFY.md).

## Confirmed defects and source-level findings

“Reproduced” means exercised here. “Source” means the implementation shows the issue, but its end-to-end impact was not exercised. “Gap” means missing/incomplete capability, not evidence of a breach.

| ID | Finding and impact | Evidence/location | Fix prompt |
|---|---|---|---|
| F01 | Admin access is granted by matching an unverified email. A fresh registration using the configured admin address accessed admin users with HTTP 200. This is unsafe bootstrap, not bypass of an existing owner's password. | Reproduced; backend/main.py require_admin and _check_job_access | 04 |
| F02 | Untrusted Host and cross-origin anonymous cancellation accepted (200). Debug-off still allows anonymous jobs. Loopback reduces exposure, but hosted and desktop modes are not an enforced server boundary. | Reproduced; backend/main.py middleware/create_job | 03 |
| F03 | Current-password reset has no limiter: 15 wrong guesses all returned 401, never 429. | Reproduced; backend/main.py:376 | 04 |
| F04 | Local password hashes lack versioned parameters; email fallback logs codes without checking debug and may report success without actual delivery. | Source; backend/auth.py:23, backend/email_service.py:70 | 04 |
| F05 | Resume after parse+analyze references an unassigned transcript and fails. | Reproduced; backend/jobs.py:761 | 05 |
| F06 | Intentional muted export is rejected for missing audio; quarter-speed export sends invalid atempo=0.25. Both return HTTP 500. | Real media reproduction; backend/main.py:1217 and :1279, backend/jobs.py:186 | 06 |
| F07 | Overlapping chunks duplicate words/segments; language is not returned from chunk transcription. | Reproduced 2 expected words → 4; backend/pipeline/transcriber.py:229 | 07 |
| F08 | Duplicate or zero-value refund references undefined get_credit_balance. Bonus/refund guards and mutations are not one transaction. | Duplicate NameError reproduced; backend/credits.py:82 | 08 |
| F09 | Idempotency keys are global, not bound to principal/operation/payload. Anonymous replay returns another account's job ID, although read access remains 404. | Reproduced; backend/jobs.py:102 and :455, backend/database.py | 09 |
| F10 | Legacy local payment recording and credit fulfillment commit separately; reversal recomputes configured grant amounts. Low-disk and retry paths need a consistent charge lifecycle. | Source; backend/gumroad.py:139, backend/jobs.py:688; old fault evidence exists but not rerun here | 08 |
| F11 | Persistence errors are swallowed; job.json and SQLite are independently written; repeated backup fails because the destination already exists. | Backup reproduced; backend/jobs.py:172, backend/database.py:1012 | 10 |
| F12 | Cooperative deadlines cannot interrupt a stuck in-process model. Some probes/audio extraction/edits bypass proc.py. Queue threads are unbounded and edit renders bypass the main slot control. | Source; backend/jobs.py:664, backend/pipeline/transcriber.py:117, backend/main.py:1191 | 11 |
| F13 | Upload copied-byte cap applies after multipart parsing; synchronous probe runs inside async handler. Concurrent edits use the same output pathname. | Source; backend/main.py:669 and :1203 | 06, 11 |
| F14 | Packaged child lives under clpz_server/, but launcher searches the root and falls back to absent source. Watchdog does not transfer replacement ownership to close cleanup; debug setdefault preserves inherited debug=1. | Layout reproduced; lifecycle/debug source findings; desktop/frozen_launcher.py:79/:95/:126 | 12 |
| F15 | Bundled yt-dlp fails its executable smoke check. Downloader prefers that file over the working installed Python module. | Reproduced; backend/bin/yt-dlp.exe, backend/pipeline/downloader.py:33 | 13 |
| F16 | Release command does not rebuild UI or compile Inno installer; audit accepts absent/empty trees; existing-spec invocation includes --specpath. | Source; packaging/build_windows.py:35/:83/:125 | 13 |
| F17 | Supabase grant_credits replay checks external_ref+txn_type rather than key/user; globally unique key and concurrent behavior need redesign. Single-active-subscription/credit-expiry promises need actual rules. | Source; supabase/migrations/0001_initial_schema.sql:196 | 14 |
| F18 | Website Ping only upserts payment fields: no user link, credit grant or entitlement. Single-permalink validation does not cover all advertised products. Blind upsert permits an old paid event to overwrite a later refunded status. | Source/gap; website/app/api/gumroad/ping/route.ts:5 | 15 |
| F19 | Coming-soon payment UI is not a hard gate: the checkout bridge changes links to checkout when configured URLs exist. Current live configuration was not inspected. | Source; website/app/buy/page.tsx, website/components/gumroad-checkout-bridge.tsx | 15 |
| F20 | Desktop local identity/credits are separate from Supabase identity used by website/Android; shared entitlement handoff is missing. | Source/gap; backend/auth.py, mobile AuthRepository.kt, website/lib/supabase | 16 |
| F21 | Callback next=/\untrusted.example passes startsWith checks but new URL resolves it to https://untrusted.example/. This permits an external redirect after successful code exchange; token disclosure was not demonstrated. | Node expression reproduction; website/app/auth/callback/route.ts:8 | 17 |
| F22 | Website lacks password recovery/account entitlements UI; download sources/configuration need consistency and staging validation. Current Next.js build is healthy. | Gap; website/app/login/auth-form.tsx, app/account/page.tsx, download routes, Vercel configs | 17 |
| F23 | Active editor has draft/preview improvements, but text overlays are not composited into preview and edit versions are not durable backend projects. React workspace files are unrouted; legacy React auth controls/labels remain unfinished. | Source/partial; frontend/clpz.html:574/:624, frontend-app/src/App.tsx and LoginForm.tsx | 18 |
| F24 | Job library returns full copied details; GET can trigger legacy metadata backfill. No ordinary safe per-project storage/deletion workflow. | Source/gap; backend/main.py:656, backend/jobs.py:1024 | 19 |
| F25 | Android suggestions use start/middle/end positions, not semantic analysis. Workflow publishes debug APK before downstream interface checks. | Source; ProjectStore.kt:62, .github/workflows/android-apk.yml | 20 |
| F26 | Complete manifests/locks and deterministic CI are missing. Backend install fallback hides failures; website is omitted from main CI; fixed test data/ports complicate isolation. | Source/current setup; requirements and .github/workflows/ci.yml | 02 |
| F27 | Quality, clean-device packaging, cloud roles/provider lifecycle, restoration and supported-hardware performance are not currently established by release evidence. | Verification gap; current and historical tests cover only part of these | 21, 22 |
| F28 | Architecture/docs describe an older product: README says no Supabase; diagram has wrong pipeline order and missing installed/cloud paths. | Source/document mismatch | 01 |

Task prompts are indexed in [README.md](README.md). Grouping related findings into a bounded task avoids separate incompatible fixes to the same state/ledger/API boundary.

## What improved since the 8 September audit

- The migration now explicitly revokes grant_credits execution from PUBLIC as well as anon/authenticated. **Do not report the missing PUBLIC revoke as a current source defect.** Applied database permissions remain unverified.
- A separate Next.js website now builds successfully. The old React/Vercel root finding is not proof that the current Next.js root is blank. Local React still uses /new and is a separate surface.
- The vanilla editor now saves/reloads localStorage drafts and synchronizes speed, mute, trim playback, and keyboard actions. Remaining parity/persistence issues should be fixed without discarding those changes.
- The current website has an implemented Google sign-in action and improved labels. Inactive controls in the old React form must not be confused with the current public form.
- Current public payment pages describe credit plans as coming soon. The configurable bridge still needs an explicit launch gate.
- Fresh audit Python dependencies pass pip check. The old environment's Click conflict should not be copied as a current result.

## Foundation and additions

The additions needed are concrete product infrastructure: a tested local service boundary, durable project/edit schema, bounded worker lifecycle, scoped submission/ledger operations, restorable backups, a real release command, transactional cloud fulfillment, secure shared identity, complete account recovery, safe library management, and evidence-based release acceptance.

There is no need to start by replacing the frontend or inventing a hosted media service. Stabilize the existing Windows workflow first. Keep Android scope and cloud billing independently verifiable.

## Audit limits

No live Supabase role/migration validation, real payment deliveries, live OAuth exploit, clean npm install, full new speech-transcription run, long-video benchmark, native PyWebView UI session, packaged installer install/upgrade/uninstall, Android compilation/emulator/device execution, full accessibility review, exhaustive security review, or dependency/native-binary vulnerability scan was performed.

The short editor media probe validates specific export failures; it does not validate transcription quality. The existing backend suite itself creates fake YouTube jobs, so “fast” is not equivalent to hermetic/offline. Its credit test failure is not sufficient evidence of a production credit bypass.

Existing ignored prototype directories, local credentials and unrelated personal files were outside product scope. No cloud configuration, live payments or production deployment was changed.

## Official references used to shape the tasks

- Restrict SECURITY DEFINER execution and test actual role permissions; PostgreSQL gives newly created functions PUBLIC execute permission by default. [PostgreSQL CREATE FUNCTION](https://www.postgresql.org/docs/16/sql-createfunction.html), [Supabase database functions](https://supabase.com/docs/guides/database/functions).
- Existing .spec files encode build options; use supported spec-mode options in the release command. [PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html).
- Use versioned, adaptive password hashing and migration rather than silently changing a fixed work factor for all existing hashes. [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

Payment payload/authentication assumptions still require current provider documentation and actual test deliveries; this audit does not certify a Gumroad webhook contract.

