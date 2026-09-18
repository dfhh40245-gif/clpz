# Task 15 — Connect purchases to accounts and entitlements

Task: 15 (payment fulfillment lifecycle)
Commit: 76e4b0a (baseline; tasks 01–15 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64); website TypeScript checked via tsc 6.0.3 (deno node-compat runtime; npm not installed)

## Original reproduction

AUDIT.md F18/F19: "Website Ping only upserts payment fields: no user link,
credit grant or entitlement. Single-permalink validation does not cover all
advertised products. Blind upsert permits an old paid event to overwrite a
later refunded status." "Coming-soon payment UI is not a hard gate: the
checkout bridge changes links to checkout when configured URLs exist."

Reproduced by source inspection of
`website/app/api/gumroad/ping/route.ts` (single upsert, no account
association, no ordered transitions) and
`website/app/api/checkout-link/route.ts` (URL configured ⇒ live link).

## Scope and policy decisions

- **Ping route rewritten** with the task 15 contract:
  1. *Webhook inbox first*: every delivery is receipted into
     `webhook_events` (migration 0002 §5) keyed
     `(provider, external_id, event_state)` BEFORE any fulfillment decision;
     `processed` flips only after completion, so a crash leaves a durable
     row for provider redelivery.
  2. *Ordered state transitions*: a stale paid event can never overwrite a
     later refund/dispute — reversal states are terminal, disputed only
     moves to refunded, and stale deliveries are acknowledged
     (`ignored: stale_event`) without downgrading state.
  3. *Account association*: buyer email is matched against `profiles.email`
     (provider-verified identity); arbitrary client-supplied user ids are
     never accepted. Unlinked sales are recorded (never dropped) and remain
     recoverable via reconciliation — `linked: false` in the response.
  4. *Fulfillment exactly once*: the grant amount comes from the SERVER's
     product map (`GUMROAD_PRODUCTS=permalink:plan:credits,...`), never from
     the payload; a `credit_transactions` probe on
     `external_ref=gumroad:<sale_id>` makes redelivery idempotent. Failed
     ledger writes return 500 (provider retries) instead of a fake 200.
  5. *Entitlements*: creator plan grants/revokes the `creator` entitlement
     row; credit packs grant ledger + balance. Refund/dispute revokes.
  6. *Multi-product*: every advertised plan has an explicit rule; unknown
     permalinks are rejected 400 (not silently upserted).
- **Fail-closed checkout gate (F19)**: `/api/checkout-link` now returns 503
  unless `CHECKOUT_ENABLED=1` is set by the owner, INDEPENDENT of configured
  URLs. The /buy page copy states the gate explicitly. Configured URLs alone
  can no longer open checkout.
- **Backend lifecycle (task 08 legacy)**: the desktop's local Gumroad
  simulation already has atomic `fulfill_payment_credits`/
  `reverse_payment_credits` with crash-recovery replay (implemented with
  task 08; tests in test_gumroad.py / test_ledger_atomicity.py).
- No live charges: all work is code + schema; sandbox verification is
  owner-gated.

## Files changed

- `website/app/api/gumroad/ping/route.ts`: full rewrite (inbox, ordered
  transitions, association, idempotent fulfillment, multi-product).
- `website/app/api/checkout-link/route.ts`: fail-closed `CHECKOUT_ENABLED` gate.
- `website/app/buy/page.tsx`: copy states the gate truthfully.
- `supabase/migrations/0002_cloud_foundation.sql`: §5 `webhook_events` table
  (RLS on, service-role only, dedupe identity).
- `supabase/tests/local_role_tests.sql`: T8 inbox assertions.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Sandbox purchase grants intended account/product once; unlinked purchases recoverable | needs sandbox delivery + disposable Supabase/Postgres | exactly-once grant | Code implements; **not executed** (no sandbox provider access / local Postgres) | **NOT RUN** | route code, harness T4/T8 |
| Duplicates, concurrent deliveries, old-paid-after-refund, crash between receipt/grant | needs live/redelivery simulation | correct final state | Ordered-transition guard + inbox + priorGrant probe implemented; TypeScript compiles | **NOT RUN end-to-end** | route code; tsc exit 0 |
| All offered products tested; malformed/unauthorized events fail | needs sandbox + all product permalinks | no fulfillment on bad events | product-map covers all 3 plans; 400/401 paths implemented | **NOT RUN** | route code |
| Reconciliation finds/resolves interrupted delivery; traceable without secrets | needs redelivery | recovery | inbox `processed=false` + retry path implemented; diagnostics log codes only | **NOT RUN** | route code |
| TypeScript validity of changed website code | `tsc --noEmit` via deno node-compat | no errors | exit 0 | PASS | command output |
| Fail-closed gate | source: CHECKOUT_ENABLED must equal "1" | closed by default | As implemented | PASS (code) | checkout-link/route.ts |
| Inbox is service-role only | harness T8 | clients see nothing; service role functional | SQL written; **not executed** | **BLOCKED** (same Postgres prerequisite as task 14) | harness T8 |

## Migration and rollback

- Deploy: apply migration 0002 (adds `webhook_events`; no destructive
  change). Set `GUMROAD_PRODUCTS` (all three plans) before opening checkout;
  `CHECKOUT_ENABLED=1` only after lifecycle acceptance passes.
- Rollback: revert the three website files; `webhook_events` can be dropped
  (additive). Legacy single-permalink config still works via the fallback
  rule in `productRules()`.

## Remaining blockers

- **Gumroad sandbox/test deliveries** against a disposable Supabase project
  (owner prerequisite) to convert the NOT RUN rows into evidence.
- **Disposable local PostgreSQL** for the schema harness (same prerequisite
  as task 14).
- Live provider contract verification (Gumroad Ping field semantics) against
  official docs + captured sandbox payloads; the route keeps the documented
  form-field contract but real payloads must confirm it.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
