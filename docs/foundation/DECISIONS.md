# CLPZ — Owner decision register

Recorded 2026-09-17 (task 01). Decisions here are **conservative baselines**,
not invented commercial terms: every entry either adopts what the code already
does, or marks the choice as OPEN with the tasks it blocks. The owner must
confirm/override entries marked OPEN before dependent work claims completion.

| # | Decision | Baseline adopted for planning | Status | Blocks |
|---|---|---|---|---|
| D1 | Next release | Free Windows local release; cloud billing and Android disabled/labeled | **Planning baseline only**; owner has not approved a release-scope deferral | 12, 13, 22 scope |
| D2 | Paid model | Existing displayed offers (Creator $7/mo, 50/200-credit packs) are **not final**; owner expects to review a modest increase after studying Dodo fees | OPEN — owner confirms prices, grants, expiry, refund/retry rules before checkout opens | 15, 16 |
| D3 | Credit consumption unit | Owner confirms the behavior: a verified purchase/renewal adds credits and paid usage deducts credits. Desktop currently costs 1 credit/forge (`COST_PER_FORGE`); the exact cloud charge unit and ledger authority remain open | PARTIAL — define the cloud operation and one authoritative spend ledger before task 15 ships | 15, 16 |
| D4 | Refund/retry charging | Failed/cancelled jobs refund the local debit (current code intends this; atomicity fixed in task 08). Cloud refund policy follows the provider, pending D2 | PARTIAL (local only) | 15 |
| D5 | 60-day subscription rollover | Advertised on the website; **not implemented anywhere** | OPEN — owner confirms before task 14 expiry modeling | 14, 15 |
| D6 | Non-expiring purchased credits | Advertised; cloud schema must model them separately from subscription credits once confirmed | OPEN (same as D5) | 14 |
| D7 | Offline allowance | No offline cloud-entitlement enforcement exists yet. Baseline: unlimited offline for the **free local** release; cloud offline grace undefined | OPEN before task 16 | 16 |
| D8 | Minimum hardware | Unmeasured. Baseline: the dev machine class (see VERIFY.md prereqs); 8 GB RAM note in PRODUCTION_CONFIG preserved | OPEN — task 21 measures and defines profiles | 21, README claims |
| D9 | Android release scope | Separately labeled preview, not a 1.0 deliverable (ADR-0001) | **Adopted** | 20 |
| D10 | Supported languages | Whisper models are multilingual; fallback tokenization is ASCII-only today. Baseline: English first; task 07 fixes tokenization; no language list is promised yet | OPEN — owner lists languages before 21/README claims | 21 |
| D11 | Local account database fate | Keep SQLite accounts as local-only feature (dev/legacy) until task 16 decision; no retirement in this cycle | **Adopted** | 04, 16 |
| D12 | Shipping desktop UI | Vanilla `/app` (ADR-0002) | **Adopted** | 18 |
| D13 | Commercial payment provider | Owner selected Dodo Payments to replace Gumroad for future subscriptions and credit packs on 2026-09-18; see `DODO_PAYMENTS_MIGRATION.md` | **Adopted for implementation planning**; checkout remains closed and historical Gumroad obligations must be audited | 15, 16, 17 |

## Notes

- **Adopted** = the owner-provided foundation documents already state this
  (ACCEPTANCE.md release rule; ARCHITECTURE.md owner decisions table). Task 01
  records them so later tasks can cite a single register.
- **OPEN** = a real business choice. Dependent tasks may build **fixtures and
  negative tests** but must not ship or advertise the feature until resolved.
  This register is the single source of truth; do not restate terms in code or
  marketing copy.
- Prices/credit amounts above are quoted only because the public website
  already displays them; recording them here neither confirms them nor
  authorizes charging (no live charge, deployment or release is authorized in
  this task).
