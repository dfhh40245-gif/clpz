# Task 08 — Make local credit operations atomic

Task: 08 (atomic local ledger)
Commit: 76e4b0a (baseline; tasks 01–08 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14, SQLite (bundled python sqlite3, WAL mode)

## Scope and policy decisions

- Local credits are declared **desktop development/legacy accounting**
  (decision register D2/D3 in docs/foundation/DECISIONS.md); they are not
  authoritative paid cloud entitlements. Cloud grants remain in the Supabase
  schema (tasks 14/15). The module docstring states this.
- Charging rule unchanged (D4): failed jobs refund the local debit;
  user-initiated cancellation does not. The previously *disconnected*
  low-disk failure path now refunds like every other failure.
- The local Gumroad webhook is **retained but made atomic** (task step 4,
  first option): payment fulfillment (grant + marker) is one transaction,
  and the intended grant amount is persisted at record time so reversals
  reverse what was actually granted, not a recomputed configuration value.

## Original reproduction

`docs/foundation/probe_current.py` → `duplicate_refund`:
`probe_error: "NameError", message: "name 'get_credit_balance' is not defined"`
(backend/credits.py called the undefined `get_credit_balance` on the
zero-amount path). Guard+mutate pairs (`has_signup_bonus` → `add_credits`,
`has_refund_for_job` → `refund_credits`, `record_payment` → `add_credits`)
were separate commits, so concurrent callers could double-grant or
double-refund, and a crash between record and fulfill left a paid sale
permanently unfulfilled. F10 additionally: reversal recomputed
`_credits_for_product()` at refund time, so a later config change would
reverse the wrong amount.

## Files changed

- `backend/database.py` — migration v2 (`payments.credits_granted INTEGER`,
  `payments.credits_reversed INTEGER NOT NULL DEFAULT 0`); new atomic ops:
  `grant_signup_bonus_once`, `refund_once`, `check_and_charge_idempotent`
  (charge + replay record in ONE commit), `fulfill_payment_credits`,
  `reverse_payment_credits` (reversal + marker + actual-delta ledger entry
  in ONE commit), `reconcile_ledger`; `subtract_credits` now logs the
  ACTUAL clamped delta so the ledger reconciles; `record_payment` accepts
  and persists `credits_granted`.
- `backend/credits.py` — rewritten on the atomic API; NameError fixed;
  refund/bonus/charge delegate to single-transaction ops; new
  `credits.reconcile()` wrapper.
- `backend/gumroad.py` — record→fulfill is atomic; crash-recovery replay
  completes a recorded-but-unfulfilled paid sale exactly once; no-grant
  outcomes recorded pre-fulfilled with 0 so replays never grant
  retroactively; reversal uses the persisted grant amount; cross-owner
  reversal attempts are refused (ValueError from the DB layer).
- `backend/jobs.py` — low-disk failure path refunds (was silently
  returning with the charge kept).
- `scripts/reconcile_ledger.py` — NEW: reconciliation CLI (exit 0 clean /
  1 mismatch / 2 environment error).
- `backend/tests/test_ledger_atomicity.py` — NEW: 14 tests.

## Checks

| Acceptance item | Command / steps | Expected | Actual | Status |
|---|---|---|---|---|
| Duplicate/zero refund correct, no exception | `pytest tests/test_ledger_atomicity.py -q` | balance stable, 1 refund txn | first=31 second=31 zero=31 (manual repro); tests pass | PASS |
| Concurrent bonus/debit/refund: exactly permitted entries, no negative | 8-thread bonus barrier, 10-thread oversell, 6-thread refund, mixed ops | 1 bonus txn; exactly 5/10 charges succeed; 1 refund; balance ≥ 0; ledger reconciles | all pass (`test_concurrent_*`) | PASS |
| Crash between record and fulfillment recoverable; replay completes once | injected exception in `fulfill_payment_credits`; replay webhook | payment row `credits_granted IS NULL`; replay grants 100 once; further replays no-op | pass (`test_crash_between_payment_record_and_fulfillment_recovers_once`) | PASS |
| Charge + replay record one transaction | `_safe_commit` crash injection at charge commit | both rolled back (no charge, no cache entry); retry succeeds once; replay cached | pass (`test_charge_and_replay_record_are_one_transaction`) | PASS |
| Reversal uses persisted amount, never recomputed | grant 120, change mapping to 999, refund | exactly 120 reversed; duplicate refund no-op | pass (`test_reversal_uses_persisted_grant_not_current_config`) | PASS |
| Ledger totals reconcile to balances | `python scripts/reconcile_ledger.py` | exit 0 clean; exit 1 + delta report on tampered balance | verified both paths (delta=949 detected) | PASS |
| fail/cancel/retry/low-disk paths match policy | code review + suite | failure refunds; cancel does not; low-disk refunds now | suite green; `jobs.py` low-disk refunds | PASS |
| No regressions elsewhere | `pytest tests -m "not slow" -q` (backend) | all green | **203 passed, 1 skipped, 9 deselected** | PASS |

Exact commands and exit codes: commands as listed; the full-suite run
returned exit 0 in 127.71 s. `test_credits.py` + `test_gumroad.py`
(18 tests) pass unchanged against the atomic API — public behavior
compatible.

## Migration and rollback

- Migration v2 (`ALTER TABLE payments ADD COLUMN credits_granted INTEGER;
  ADD COLUMN credits_reversed INTEGER NOT NULL DEFAULT 0`) applies
  automatically via `PRAGMA user_version` ordering on first run of any
  release with this change. Legacy payment rows keep NULL
  `credits_granted`: their original amount is unknown, so a reversal falls
  back to the configured product mapping (previous behavior) and records
  the actual amount reversed.
- Rollback: previous code ignores the two new columns; no data conversion
  is required. Downgrade is safe; re-upgrade re-applies nothing (version
  marker prevents duplication).
- No balance backfill is performed: existing balances are treated as
  reconciled history. Run `scripts/reconcile_ledger.py` after upgrade to
  audit; mismatches are reported with per-user deltas, never auto-fixed.

## Remaining blockers

- Cloud-side credit/entitlement semantics (expiry, rollover, spend order)
  are owner decisions D2/D5/D6 — task 14/15, untouched here.
- The Gumroad webhook remains a **local legacy path**; it is not live
  provider certification (no real delivery tested, per audit limits).
- `payments.user_id` is not FK-constrained for unlinked-buyer rows (by
  design, audit trail); reversal cross-owner protection is enforced in
  `reverse_payment_credits`.

Artifact name and SHA-256: n/a (no packaged artifact).
Reviewer: pending owner review.
