# Task 15 — Connect purchases to accounts and entitlements

**Owner update (2026-09-18):** Dodo Payments replaces Gumroad for future subscriptions and credit packs. Read `docs/foundation/DODO_PAYMENTS_MIGRATION.md` and `DECISIONS.md` D13 before implementing this task. The Gumroad-specific paths and instructions below describe the old starting state and historical obligations; build new checkout and fulfillment against Dodo's verified contract. Prices and other commercial terms remain unconfirmed, and checkout must stay closed.

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

