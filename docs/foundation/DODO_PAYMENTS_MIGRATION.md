# Dodo Payments migration foundation

Owner direction, 2026-09-18: use **Dodo Payments instead of Gumroad** for future CLPZ subscriptions and credit packs. This selects a provider; it does not confirm plan prices, credit expiry, rollout timing, or permission to open checkout. Keep `CHECKOUT_ENABLED` closed until sandbox lifecycle acceptance is complete.

Owner clarified the customer behavior: **buying or renewing adds credits; using a paid feature deducts credits**. The current advertised prices are not approved; the owner expects to review a modest increase after studying Dodo fees. Do not create final priced products or revise public price copy yet.

## Verified provider contract

- Dodo supports subscription and one-time products with attached custom-unit credit entitlements, expiry, rollover, and overage controls. Configure CLPZ credits as integer custom units only after the product terms are confirmed. [Credit-based billing](https://docs.dodopayments.com/features/credit-based-billing)
- Create hosted checkout sessions **server-side** from an allowlisted product cart, then redirect to the returned checkout URL. The authenticated account must be bound to a server-created pending order or customer mapping; a browser-supplied user ID or email is not proof of ownership. [Checkout integration](https://docs.dodopayments.com/developer-resources/integration-guide), [metadata](https://docs.dodopayments.com/api-reference/metadata)
- Verify `webhook-id`, `webhook-timestamp`, and `webhook-signature` against the **raw body** using Dodo's SDK/Standard Webhooks implementation. Persist the provider event ID before fulfillment, handle duplicates and delivery out of order, and acknowledge only after durable acceptance or a recoverable retry state. [Webhooks](https://docs.dodopayments.com/developer-resources/webhooks), [event guide](https://docs.dodopayments.com/developer-resources/webhooks/intents/webhook-events-guide)
- Dodo's documented migration CLI lists Lemon Squeezy, Stripe, Polar, and Paddle; it does **not** list Gumroad. Existing Gumroad customers, refunds, or subscriptions need an explicit manual transition plan. [Migration guide](https://docs.dodopayments.com/migrate-to-dodo)
- Dodo also exposes an idempotent credit/debit ledger-entry API. Whether to use that as the **live** spend authority is a separate technical choice: paid local jobs would need a reliable online debit and failure refund path. For now, the working design uses CLPZ's server ledger for immediate job admission and applies only verified Dodo purchase/renewal events as grants, with reconciliation; do not create a second independent spend balance. [Ledger-entry API](https://docs.dodopayments.com/api-reference/credit-entitlements/create-ledger-entry)
- Dodo's public Standard card pricing currently lists **4% + $0.40** per transaction, with a **0.5% subscription** surcharge and **1.5% international** surcharge where applicable. These are planning inputs, not approved CLPZ prices; confirm the actual merchant agreement, payment methods, and regional fees before setting prices. [Dodo pricing](https://dodopayments.com/pricing)

At that public standard domestic-card rate, the **currently displayed, unapproved** prices imply approximately these processing fees before other possible charges:

| Existing advertised offer | Illustrated Dodo fee | Proceeds after illustrated fee |
|---|---:|---:|
| $7 monthly Creator | $0.72 (4% + 0.5% + $0.40) | $6.28 |
| $4 one-time pack | $0.56 (4% + $0.40) | $3.44 |
| $11 one-time pack | $0.84 (4% + $0.40) | $10.16 |

This arithmetic is **not** a price recommendation or a payout forecast. International/payment-method surcharges, refunds, currency conversion, taxes, and CLPZ's own costs may change the economics. The owner will select final prices after review.

## Current CLPZ boundaries

| Surface | Current state | Migration work |
|---|---|---|
| Website checkout | `website/app/api/checkout-link/route.ts` maps plans to Gumroad URLs; `GumroadCheckoutBridge` rewrites plan links; `/buy` says coming soon | Use authenticated, server-created Dodo sessions and a server-owned plan-to-product map. Keep the existing fail-closed launch gate. |
| Website payment receipt | `website/app/api/gumroad/ping/route.ts` processes Gumroad Ping into Supabase rows | Add a separate signed Dodo webhook inbox and deterministic fulfillment/reversal. Never grant on a checkout return URL. |
| Local backend | `backend/main.py` and `backend/gumroad.py` expose a separate Gumroad webhook and local SQLite credit ledger | Do not make local editable credits authoritative for commercial entitlements. Preserve the old route only as long as historical Gumroad events require it. |
| Cloud identity and credits | Supabase has payments, subscriptions, entitlements, credit accounts, and credit buckets; R08 identity handoff remains open | Finish account identity and choose one authority for spend/credit balance before wiring payment fulfillment. |
| Product/legal copy | Homepage advertises $7/120 monthly, $4/50, $11/200, 60-day rollover, nonexpiring packs; legal/health pages name Gumroad | Confirm terms, then align Dodo products, database behavior, pricing copy, privacy/terms, and health reporting. |

## Implementation order

1. Confirm the technical credit authority and product terms in `DECISIONS.md`. Working design: CLPZ's server ledger decides the immediate debit for a paid job; a verified Dodo purchase/renewal grants credits once. If a later design makes Dodo authoritative for deductions, prove synchronous admission, failed-job refund, offline behavior, and reconciliation first. Do not run two independent spend authorities.
2. Create Dodo **test-mode** products for the approved Creator subscription and each pack. Record product IDs and a versioned plan-to-grant mapping in server configuration. Keep API/webhook keys outside source.
3. Finish R08's verified account identity. On authenticated checkout request, create a pending order tied to the server-side account, select only an allowlisted product ID, create a Dodo checkout session, and store Dodo customer/session IDs. A checkout redirect is not a purchase confirmation.
4. Verify signed Dodo webhooks and persist a durable, deduplicated inbox. Apply purchase/renewal, subscription active/on-hold/cancelled, refund, and dispute transitions with a recoverable fulfillment worker. Reconcile missed, duplicate, delayed, and out-of-order events against provider state.
5. Grant or reverse the exact approved entitlement/credit amount for the linked account with transaction-safe idempotency. Preserve the original product version and grant allocation for later refunds. Keep old Gumroad payment records identifiable; retire its checkout link and historical webhook only after migration accounting is reconciled.
6. Replace Gumroad UI bridge and references only after test-mode purchase/renewal/cancellation/refund/credit consumption work end to end. Keep `CHECKOUT_ENABLED` closed until the owner reviews the evidence and explicitly opens it.

## Acceptance evidence required

- Unauthenticated checkout and unknown plan fail closed. An account cannot direct a purchase or webhook grant to another account.
- Every advertised product is tested in Dodo test mode. Matching provider product IDs and server policy determine grants; client metadata is never sufficient.
- Invalid/missing/replayed signatures are rejected. Duplicate, concurrent, delayed, and reordered deliveries yield one correct final entitlement and credit allocation.
- Subscription renewal, on-hold, cancellation, refund, dispute, expired credit, purchased credit, and account recovery have explicit expected states and tests.
- Crash between inbox receipt and grant is replayable; reconciliation finds an intentionally interrupted event.
- Checkout stays closed without approved terms, verified account mapping, sandbox lifecycle evidence, and production credentials. A clean return-page redirect does not count as fulfillment.

## Decisions and external prerequisites

- **Working technical choice:** CLPZ/Supabase is the immediate spend authority and Dodo is the billing/grant provider. Owner specified add-on-purchase and deduct-on-use behavior, not a storage system; validate this design against sandbox events before treating it as final.
- **Pending owner choice:** final prices, monthly grant, 60-day rollover, pack expiry, exact paid-operation charge unit, retry/refund treatment, and offline behavior (`DECISIONS.md` D2–D7). Owner expects a price increase after fee review; no new numbers have been selected.
- **External:** approved Dodo merchant/test account, test-mode API key/webhook key, configured products, verified webhook endpoint, and sandbox lifecycle events. Do not put keys in the repository.
- **Migration audit:** establish whether there are live Gumroad purchasers/subscriptions before deleting historical routes or data. The Dodo CLI does not document Gumroad import.

This file is the new provider foundation for task 15 and the commercial portion of R08. It does not mark either task complete or authorize live payments.
