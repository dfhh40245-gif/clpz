# Task 16 — Connect desktop and mobile to shared accounts

**R08 correction (2026-09-18):** The older local SQLite device-link work
below did not establish Supabase identity and must not be cited as proof of
cloud authorization. A separate Supabase-verified website ↔ Windows flow now
exists; see `R08-cloud-identity.md`. Staging, Android, paid usage, and offline
acceptance remain **NOT RUN/OPEN**. No scope deferral was approved.

Task: 16 (shared identity/entitlements)
Commit: 76e4b0a (baseline; tasks 01–16 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64); Android device/emulator not available

## Original reproduction

AUDIT.md F20: "Desktop local identity/credits are separate from Supabase
identity used by website/Android; shared entitlement handoff is missing."
Source inspection confirmed no device-link/handoff code existed anywhere in
the repository.

## Scope and policy decisions

- **Protocol implemented (desktop-side authority)**: a one-use, expiring,
  state-bound exchange —
  1. The desktop app generates a random `state` and shows it.
  2. The signed-in OWNER (website or local web session, `Depends(get_current_user)`)
     POSTs `/api/auth/device-link {state}` and receives a single-use `code`
     (TTL 5 minutes, `DEVICE_LINK_TTL_SECONDS`).
  3. The desktop POSTs `/api/auth/device-link/redeem {code, state}` once and
     receives a normal HttpOnly session cookie.
  No long-lived credentials travel in links; redemption is rate limited
  separately (`devicelink:<ip>`) and returns one uniform 401 for
  used/expired/wrong-state/unknown so failures are not distinguishable.
- **Atomicity/replay**: redemption is
  `UPDATE ... SET used_at WHERE code=? AND state=? AND used_at IS NULL AND expires_at > now`
  — SQLite serializes it, so a raced duplicate redemption updates zero rows
  (verified by a two-thread race test). State binding means a code intercepted
  without the state cannot redeem; the state never leaves the two devices.
- **Ledger authority**: local credits remain server-authoritative through the
  ledger; the new test proves a direct balance-column tamper is *detectable*
  by reconciliation (balance ≠ Σ ledger), matching the task's "never trust a
  desktop-reported balance" for the local-release scope. Cloud-side balance
  authority is migration 0002's bucket model (task 14).
- **Business policies (offline grace, clock rollback, multi-device limits)**
  remain OWNER-OPEN per DECISIONS.md; none were silently chosen. The local
  protocol and tests are delivered with those blockers explicit, exactly as
  the prompt directs.
- Media stays local: no media upload path was added (ownership contract,
  ARCHITECTURE.md).

## Files changed

- `backend/database.py`: `device_link_codes` table (baseline DDL) +
  `create_device_link_code` / `redeem_device_link_code`.
- `backend/main.py`: `POST /api/auth/device-link` (authenticated mint) and
  `POST /api/auth/device-link/redeem` (rate-limited single-use exchange).
- `backend/tests/test_shared_identity.py` (new): 7 regression tests.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Same account sees same access on website/desktop/Android | needs Supabase project + Android device | shared identity | Desktop handoff protocol implemented and tested at the API/DB layer; website/Android share Supabase already; live cross-device run not performed | **NOT RUN end-to-end** | tests/test_shared_identity.py |
| Copied/replayed/expired callback cannot sign in; wrong state fails | `pytest tests/test_shared_identity.py` | all fail closed | replay/wrong-state/expired/unknown all rejected; race yields exactly one winner | PASS (protocol layer) | test output |
| Editing local SQLite cannot mint cloud credits; reserve/settle idempotent | `...::test_local_db_edit_cannot_mint_ledger_grants` + task 08 tests | tamper detectable; grants only via audited paths | balance-vs-ledger divergence proven; grant/reverse exactly-once from task 08 | PASS (protocol layer) | test output |
| Offline/expiry/revocation/restart/sign-out per approved policy | policy record | as approved | Policies are OWNER-OPEN (D-decisions); nothing silently chosen; sign-out destroys sessions (pre-existing) | **BLOCKED** on owner decisions | DECISIONS.md |

## Migration and rollback

`device_link_codes` is created by the baseline `CREATE TABLE IF NOT EXISTS`
DDL (fresh databases) — no destructive migration needed for existing DBs.
Rollback: remove the two endpoints and two helpers; table is inert.

## Remaining blockers

- Owner decisions D9–D11 (offline allowance, multi-device policy, paid
  scope) before cloud entitlement enforcement can be claimed.
- A configured Supabase staging project + Android device to verify the full
  three-surface journey (ACCEPTANCE gate 16 procedure).
- The website `/account` form now accepts the Windows state and issues a
  one-time Supabase-backed code (R08); live staging validation is NOT RUN.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
