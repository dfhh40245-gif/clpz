# Release acceptance matrix

Status on 18 September 2026: **NOT ACCEPTED**. Tasks 01–22 have been implemented with evidence in evidence/task-XX.md (baseline 76e4b0a + uncommitted working tree; backend fast suite 312 passed, 2 skipped, 9 deselected on this machine). Several gates remain BLOCKED on external prerequisites (staging Supabase, clean Windows packaging machine, Android SDK/keystore, provider sandbox) — see evidence/task-22.md. A skipped test or unavailable external account is never a pass.

“Pass” needs the exact commit, environment and artifact version plus evidence. Use PASS / FAIL / BLOCKED / NOT RUN. A skipped test or unavailable external account is never a pass. A deliberate scope deferral needs an owner, reason and an accurate product-facing capability statement.

| Gate | Test procedure | Expected result | Owning tasks | Current release evidence |
|---|---|---|---|---|
| Product contract | Trace every advertised capability to its implementation and owner decision | No contradictory UI/data/business promises | 01 | PASS (local docs/ADR/decisions; Android scope labeled timeline-drafts) |
| Clean setup | Clone on a fresh supported machine; install locked dependencies; execute doctor/check | No undeclared manual fixes; checks report real failures | 02 | PARTIAL (full-scope check now fails closed without npm — verified exit 1 on this machine; `--backend-only` green. Fresh-machine locked install NOT RUN; no Node on this machine so React/website checks rely on earlier evidence) |
| Local boundary | Try trusted/untrusted Host/Origin/capability and normal playback/upload | Untrusted blocked; local workflow works | 03 | PASS (capability gate + Host/Origin tests) |
| Account/admin | Register owner email without verification; try admin; brute-force reset | No privilege grant; throttling; no leaked codes | 04 | PASS (provisioned admin, 429 throttle, hash migration tested) |
| Resume | Inject failure at each pipeline stage; restart/retry | Valid state and reusable completed artifacts | 05 | PASS (stage-failure resume tests) |
| Export | Render combinations of trim, speed, mute and text; inspect/decode media | Correct streams/timing/content; original preserved | 06 | PASS (real FFmpeg matrix incl. mute/0.25×) |
| Transcript | Overlap/jitter/repeated words/Unicode/malformed timing fixtures | No duplicate overlap or discarded valid speech | 07 | PASS (fixture tests; live Whisper multilingual NOT RUN) |
| Ledger | Concurrent grants/refunds; injected crash; reconcile totals | Exactly one permitted mutation and recoverable state | 08 | PASS (atomic txn + crash tests + reconcile CLI) |
| Submission | Same/changed payload and key across users/operations/restart | Correct replay or conflict, never cross-owner reuse | 09 | PASS (scoped keys, composite PK, 409 conflicts) |
| Durability | Interrupt save; back up twice; restore to empty directory | Last committed state intact; usable restored media | 10 | PASS (atomic persist, versioned backups, restore tests) |
| Resource control | Hang worker; cancel every stage; overload queue/upload | Hard deadline/limits and responsive API | 11 | PASS locally (queue admission tests, edit-render watchdog, supervised transcription killed at hard deadline with real child processes; full end-to-end NOT RUN) |
| Windows lifecycle | Install without Python; start; kill server; restart; close | Correct child path and no orphan replacement | 12 | PARTIAL (layout/ownership unit tests PASS; real installer lifecycle NOT RUN) |
| Release assets | Build from scratch; execute bundled tools; install offline | Verified complete versioned installer | 13 | PARTIAL (build command hardened, yt-dlp replaced + verified; full from-scratch installer build BLOCKED: no Node/Inno on this machine) |
| Cloud schema | Fresh/upgrade migration with actual database roles | RLS, grants, lifecycle and concurrent replay correct | 14 | BLOCKED (migration 0002 + role-test harness ready; needs staging Supabase/Postgres) |
| Payment lifecycle | Test purchase/renewal/refund/dispute/reordered duplicate/crash | Right account/access exactly once; replay recoverable | 15 | PARTIAL (backend fulfillment atomic + website inbox/gate implemented; live provider NOT RUN) |
| Shared access | Sign in on desktop/mobile; tamper local DB; test expiry/offline | Cloud authority and approved offline behavior | 16 | PARTIAL (Supabase-verified website handoff, Windows DPAPI credential and online account contract implemented; staging SQL/device journey NOT RUN; paid/offline policy OPEN) |
| Website journey | Confirm/reset/login/logout/account/download; malicious callback next | Complete accessible journey and same-origin redirects | 17 | PARTIAL (recovery/reset, device-link and account access UI implemented; build/lint/local contracts PASS; real email/OAuth/browser/download journey NOT RUN) |
| Editor versions | Preview/edit/undo/save/restart/export and compare | Persistent choices and output/preview agreement | 18 | PARTIAL (overlay preview + durable edit versions implemented; full parity matrix NOT RUN) |
| Library/storage | Large library, delete active project, restart | Bounded reads; safe deletion; no ghost projects | 19 | PASS (pagination, scoped delete, traversal refusal tests) |
| Android release | Device lifecycle and export; failed CI gate; upgrade signed APK | Stable on-device workflow; no failed-build publication | 20 | PARTIAL (fail-closed CI, store hardening, cancel contract implemented; device tests BLOCKED: no SDK/keystore) |
| Media quality | Agreed licensed fixtures on supported hardware | Predefined quality/resource thresholds met | 21 | PARTIAL (28/28 objective checks PASS on 5 generated fixtures; long-video/multilingual/low-RAM NOT RUN) |
| Operational release | Restore/rollback/support bundle/download hashes | Independent operator can recover and diagnose safely | 22 | PARTIAL (redacted support bundle + restore runbook tested locally; independent-operator dry run NOT RUN) |

## Evidence required for every task

Copy this into evidence/task-XX.md and fill actual values:

```text
Task:
Commit:
Tester:
Date:
OS/device and hardware:
Runtime/tool/model versions:
Scope and policy decisions:
Original reproduction:
Files changed:
Checks:
  Acceptance item | command/manual steps | expected | actual | status | evidence
Migration and rollback:
Remaining blockers:
Artifact name and SHA-256 (if relevant):
Reviewer:
```

## Full user journeys

1. **Local Windows:** install → open → import consented speech file → generate clips → play → edit trim/text/audio → export → verify output → close → restart → reopen → back up → restore → upgrade → uninstall while retaining promised data.
2. **Commercial account, if in scope:** signup/confirm → sign in → checkout with verified account association → provider event → transaction/entitlement → desktop sign-in → consume approved operation → failure/refund/retry → offline/expiry → sign out. Include duplicate/reordered events.
3. **Android, if in scope:** install → auth → import persistent URI → create timeline draft → edit → save → process death/reopen → export/share → cancel → signed update with project retention.

## Release rule

Do not publish a paid/full-feature claim with unresolved in-scope P0/P1 tasks. A free Windows milestone may explicitly defer cloud billing and Android, provided those paths stay disabled/labeled and no advertised feature implies they work. Deferral is a scope decision, not a successful test.

Before go/no-go, review the exact packaged artifact. Tests against development files cannot certify an installer produced from stale assets.
