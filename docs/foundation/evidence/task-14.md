# Task 14 — Finish and test the cloud data foundation

Task: 14 (cloud schema)
Commit: 76e4b0a (baseline; tasks 01–14 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: SQL written and statically reviewed; **no local PostgreSQL/Docker available on this machine** (psql, Postgres, docker all absent — checked)

## Original reproduction

AUDIT.md F17: "Supabase grant_credits replay checks external_ref+txn_type
rather than key/user; globally unique key and concurrent behavior need
redesign. Single-active-subscription/credit-expiry promises need actual
rules." Source review of `supabase/migrations/0001_initial_schema.sql`
confirmed: the replay guard ignored `p_idempotency_key` entirely (a grant
with the same `external_ref`+`txn_type` for a DIFFERENT user returned the
caller's balance without granting — silent mis-suppression), two racing
same-key calls could both pass the `exists()` check and double-grant, and no
subscription lifecycle rules existed.

## Scope and policy decisions

- **Forward migration only**: 0001 is untouched; all changes ship as
  `0002_cloud_foundation.sql`, idempotent-by-construction (guarded DO blocks
  / `IF NOT EXISTS`), so a partially applied 0002 converges on re-run.
- **Replay semantics (matching the task 09 local contract)**: same key +
  identical payload (user, amount, txn_type, external_ref) → idempotent
  no-op returning current balance; same key + ANY different payload →
  rejected with `unique_violation` (409 semantics). Different users with
  different keys are never suppressed.
- **Concurrency**: `pg_advisory_xact_lock(hashtext(key))` serializes
  same-key calls; a dedicated unique partial index on
  `credit_transactions(idempotency_key) where key is not null` makes racing
  inserts physically unable to double-commit.
- **Credit buckets**: `credit_buckets` models the advertised terms —
  `subscription` grants (60-day expiry, matching the advertised rollover)
  vs `purchased` (never expire). `spend_credits` enforces the defined spend
  order (soonest expiry first, then purchased FIFO) and keeps the legacy
  `credit_accounts.balance` in sync for existing readers. Owner confirmation
  of the 60-day window is still open (DECISIONS.md D8) — the interval is a
  single constant in the SQL.
- **Subscriptions**: status domain (`active|past_due|canceled|expired`),
  partial unique index enforcing single active per user, trigger guarding
  transitions (canceled/expired cannot resurrect).
- **Profiles**: added `full_name` (website alignment) and a display_name
  length guard.
- Privilege model preserved: both RPCs re-revoked from anon/authenticated/
  PUBLIC and granted to service_role only.

## Files changed

- `supabase/migrations/0002_cloud_foundation.sql` (new): all of the above.
- `supabase/tests/local_role_tests.sql` (new): 7-assertion role/concurrency
  harness runnable against any disposable local PostgreSQL.
- `supabase/README.md`: migration-order instructions, 0002 summary, harness usage.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Fresh migration + upgrade retain data | apply 0001 then 0002 on disposable Postgres; T7 | both succeed; rows retained | SQL written; **not executed** — no local Postgres/Docker on this machine | **BLOCKED** | supabase/tests/local_role_tests.sql (T7) |
| Anon/normal users cannot grant credits or write payments/entitlements; A cannot read B | T1, T2, T3 | blocked by RLS/revokes | SQL written; **not executed** | **BLOCKED** | harness T1–T3 |
| Concurrent same-key grants apply once; different payloads rejected; distinct keys independent | T4 (+ advisory lock design) | defined no-op/reject/independent | SQL written; **not executed** | **BLOCKED** | harness T4 |
| Subscription + profile constraints incl. invalid transitions and role access | T5, spend-order T6 | constraints enforced | SQL written; **not executed** | **BLOCKED** | harness T5–T6 |

Static self-review performed: function signatures match 0001's grant_credits
(so the revokes cover the replaced body); revokes appear AFTER the function
body (PostgreSQL grants PUBLIC execute on newly created functions by
default — the trailing revoke is what removes it); the harness's `auth.uid()`
GUC emulation matches Supabase's claim-reading behavior.

## Migration and rollback

- Deploy: run 0002 after 0001 (README §2). 0002 is re-runnable.
- Rollback: 0002's additive objects (credit_buckets, spend_credits) can be
  dropped; the replaced grant_credits body and constraint objects do not
  remove data. No destructive change ships.

## Remaining blockers

- **A disposable local PostgreSQL (or `supabase start`)** is required to run
  the harness and claim the acceptance checks. Exact prerequisite:
  PostgreSQL 15+ (or Docker Desktop) installed, then
  `psql -v ON_ERROR_STOP=1 -f supabase/tests/local_role_tests.sql`.
- Live Supabase project role verification (staging) remains owner-gated.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
