# Task 22 — Run end-to-end acceptance and prepare operations

Task: 22 (release acceptance — final gate)
Commit: 76e4b0a (baseline; tasks 01–22 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-18
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14 (`.venv`), bundled FFmpeg 9.0.1, faster-whisper tiny; Node/npm NOT installed on this machine (JS checks rely on earlier task evidence)

## What was run for this gate

| Check | Command | Result |
|---|---|---|
| Backend fast suite | `pytest tests -m "not slow" -q` (in backend/) | **312 passed, 2 skipped, 9 deselected** (2026-09-18 re-audit, exit 0; earlier runs during implementation were 268 and 294 before R03/R04/R05/R07/R08 fixes landed) |
| doctor | `python scripts/doctor.py --json` | exit 0 (all required checks pass) |
| check aggregator (full scope) | `python scripts/check.py` | **exit 1 on this machine (npm absent)** — fail-closed per R07; `--backend-only` exits 0 (doctor PASS, backend-fast-tests PASS, frontend/website explicitly SKIP). Earlier full-scope PASS claims were invalid because npm checks were silently skipped; corrected. |
| Flaky test fix verification | `pytest tests/test_worker_bounds.py tests/test_remediation.py -q` ×2 | 27 passed ×2 |
| Quality benchmark (task 21 baseline) | `python scripts/benchmark_quality.py --quick` | 28/28 checks PASS, exit 0 |
| Secret scan (value-based patterns: JWTs, sbp_/sk_/bearer, private keys) | inline scan over source files | 0 hits |
| Support bundle privacy assertions | `pytest backend/tests/test_support_bundle.py -q` | only allowlisted fields; JSON/header/multiline/URL/provider-token samples excluded | **9 passed** (re-verified in the 2026-09-18 audit) |

## Flaky defect found and fixed during the gate

`test_cancel_terminates_subprocess_and_stays_cancelled` failed intermittently when run after `test_worker_bounds`. Root cause: `proc.active_count()` counted **dead-but-unregistered** children (a killed process remains registered until the spawning thread's `communicate()` returns), making a successful kill look like an orphaned process. Fixed in `backend/proc.py`: `active_count()` prunes exited processes. Verified with two consecutive clean pair-runs and two full-suite runs.

## Acceptance matrix status (see ACCEPTANCE.md for per-gate definitions)

- **Verified locally on this machine** (development artifacts, not a packaged installer): tasks 02–13, 15 (backend portion), 16 (desktop handoff logic), 17 (callback guard fix + typecheck), 18 (backend edit-version persistence), 19 (library APIs), 21 (objective benchmark).
- **Implemented but NOT RUN end-to-end** (need external prerequisites): task 14 cloud role tests (no local Postgres/Supabase staging), task 20 device tests (no Android SDK/emulator/keystore), long-video/multilingual quality runs (task 21 remaining scope).
- **Owner-dependent**: payment lifecycle with a real provider (task 15 acceptance), shared identity on real devices (task 16 device journey), production signing identity (task 20), installer verification on a clean Windows machine (tasks 12/13 install runs).
- **NO go** for a paid/full-feature release until the BLOCKED rows above are run. A **free Windows local milestone** is defensible *if* the owner explicitly defers cloud billing and Android and the product copy keeps those paths labeled — that is a scope decision (DECISIONS.md D1), not a passed test.

## Operations deliverables added

- `scripts/support_bundle.py` — allowlisted support bundle: machine profile, approved environment-setting presence (values withheld), typed job summaries (error codes/timings), and log presence/size metadata only. It contains no URL/media fields, error text, transcripts, or log tails. See `evidence/R06-support-bundle-privacy.md`.
- `docs/foundation/BACKUP_RESTORE.md` (from task 10) — tested backup/restore runbook for the local data store.
- `scripts/reconcile_ledger.py` (task 08) — operator reconciliation with nonzero exit on mismatch.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Every in-scope row has procedure/expected/actual/evidence for exact commit | review evidence/task-01..21 | complete | complete for development artifacts; **installer artifacts never built/run on this machine** | PARTIAL | evidence/*.md |
| No open P0/P1 blocker in chosen release scope | review DECISIONS.md D1 + matrix | none open in scope | local free-release scope: code-level P0/P1s fixed and tested; **blocked items are external** (staging Supabase, devices, clean-machine installer) | BLOCKED (external prerequisites) | task-14/20 evidence |
| Independent person follows setup/release/restore runbooks without undocumented steps | fresh-machine run of VERIFY.md + BACKUP_RESTORE.md | no undocumented steps | NOT RUN — requires a second machine/person | NOT RUN | — |
| Final report distinguishes verified local / staging / manual / deferrals; no 100% claims | this document | honest separation | done — see matrix status above | PASS | this file |

## Remaining blockers (exact prerequisites — audited 2026-09-18)

| # | Check (gate/task) | Exact prerequisite | Exact procedure |
|---|---|---|---|
| 1 | Reproducible setup + full check on a fresh machine (Clean setup / 02) | A clean supported Windows 10/11 machine or VM with Node.js ≥22 + npm; Python 3.12; nothing else preinstalled | Clone → venv from `backend/requirements.lock` → `pip check` → `npm ci` in `frontend-app/` and `website/` → `python scripts/check.py` (full scope must exit 0 — it now fails closed without npm) |
| 2 | Installer build + execute bundled tools + offline install (Windows lifecycle 12, Release assets 13) | Same machine as #1 plus PyInstaller and Inno Setup | `python packaging/build_windows.py` → verify the produced installer's bundled `ffmpeg/ffprobe/yt-dlp` execute → install offline → task 12 lifecycle: install without Python, start, kill server, restart, close, uninstall retaining promised data |
| 3 | Independent-operator dry run (Operational release / 22) | A second person and the machine from #1/#2 | That person follows `docs/foundation/VERIFY.md` + `BACKUP_RESTORE.md` cold, restore + rollback + support bundle + hash check, with no undocumented steps |
| 4 | Cloud role tests (Cloud schema / 14) | Disposable local PostgreSQL with fixture roles/users | Apply migration 0002 → run `supabase/tests/local_role_tests.sql` (RLS, grants, lifecycle, concurrent replay) |
| 5 | Device-identity SQL contract (Shared access / 16, R08) | Same disposable PostgreSQL | Apply migration 0003 → run `supabase/tests/cloud_device_identity.sql` (replay, wrong state, expiry, role isolation, atomic session creation) |
| 6 | Staging migration + staging accounts (14/16/17) | A staging Supabase project (never production) | Apply 0002 + 0003 in order to staging; verify with real staging accounts |
| 7 | Browser journeys (Website journey / 17, R08) | Deployed preview site + staging Auth with email + Google OAuth configured | Signup/confirmation, login, password recovery/reset, device-link, account display, logout, expired-link feedback, malicious-callback rejection |
| 8 | Android device acceptance (Android release / 20) | Android Studio + SDK + JDK 17, a device/emulator, and a release keystore kept outside source | JVM + Robolectric tests, on-device import/edit/save/process-death/export/cancel, signed AAB build, signed upgrade with project retention, red CI gate blocks publication |
| 9 | Live payment lifecycle (Payment lifecycle / 15) | Provider sandbox account + test webhook signing secret + staging accounts | Purchase → entitlement → desktop sign-in → consume → failure/refund/retry → duplicate and reordered webhooks → crash replay; verify exactly-once access and single charging |
| 10 | Remaining media-quality runs (Media quality / 21) | Licensed real-world fixtures and target-hardware machines (low-RAM 8 GB, long-video) | Run `scripts/benchmark_quality.py` matrix for long-video, multilingual, and low-RAM profiles against pre-declared thresholds |
| 11 | Live Whisper multilingual runs (Transcript / 7) | Real model weights downloaded + target hardware | Run fixture set through the real model in supervised mode; compare against the synthetic-fixture results |
| 12 | Owner scope decisions (release rule) | Owner sign-off recorded in DECISIONS.md | D1 free-milestone deferral, D2/D3/D7 paid/offline policy, remaining D-items — a planning baseline is not approval |

Rollback/recovery: all task 22 additions are new files (`scripts/support_bundle.py`, this evidence file); delete to revert. No stored-data or schema changes in this task.
Reviewer: —
