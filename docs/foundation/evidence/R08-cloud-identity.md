# R08 — verified cloud identity and account journey

Date: 2026-09-18. All work remains uncommitted; no deployment or charge.

## Contract and implementation

The older `/api/auth/device-link` endpoints use local SQLite sessions. They
remain local/legacy only. The new `/api/cloud/*` flow is separate:

1. The Windows app generates a random state and shows it to the user. It never
   puts a long-lived credential in the browser URL.
2. On `/account`, the signed-in website calls Supabase `auth.getUser()` before
   issuing a five-minute random code bound to that state and user. This is a
   live Auth-server identity check, not a browser-supplied user ID. [Supabase
   getUser](https://supabase.com/docs/reference/javascript/auth-getuser).
3. Migration 0003 stores only SHA-256 code/state hashes. A service-role-only
   SQL function atomically consumes the code and creates a 30-day device
   session. Wrong state, expiry, and replay return no user ID. The SQL function
   has an explicit empty search path and revoked client execution. [Supabase
   function guidance](https://supabase.com/docs/guides/database/functions).
4. Windows exchanges code+state with the configured HTTPS website, checks
   issuer, audience, token format and UUID, then protects the opaque device
   credential with Windows DPAPI. Restart can reload it under the same Windows
   account. Cloud account reads always go online to the website, which reads
   Supabase balances/subscriptions/entitlements. No cloud balance is copied to
   local SQLite and no media is sent to the website.
5. Windows cloud sign-out revokes the server session before deleting the local
   encrypted credential. If revocation cannot be confirmed, it reports failure
   and keeps the credential for retry. Website recovery sends a Supabase reset
   email; the callback establishes a session before the reset form updates the
   password. The account page shows current cloud data or a clear unavailable
   state.

Commercial checkout, cloud credit spending, and offline entitlement policy are
not inferred from this identity integration. DECISIONS.md D2/D3/D7 remain open.

## Local verification

| Check | Command | Result |
|---|---|---|
| Website build/TypeScript | `node node_modules/next/dist/bin/next build` in `website/` | PASS; new routes compiled |
| Website lint | `node node_modules/eslint/bin/eslint.js .` in `website/` | PASS |
| Website contract | `node --experimental-strip-types --test tests/cloud-contract.mjs` in `website/` | 3 passed |
| Windows/backend contract | `..\.venv\Scripts\python.exe -m pytest tests/test_cloud_identity_contract.py -q --tb=short` in `backend/` | 7 passed; two dependency deprecation warnings |
| Full backend fast suite | `..\.venv\Scripts\python.exe -m pytest tests -m "not slow" -q --tb=short` in `backend/` | 312 passed, 2 skipped, 9 deselected; exit 0 |
| Runtime dependencies | `..\.venv\Scripts\python.exe -m pip check` in `backend/` | No broken requirements found |
| DPAPI round trip | `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'backend'); import cloud_identity; x=b'hello'; print(cloud_identity._dpapi(cloud_identity._dpapi(x, protect=True), protect=False)==x)"` from repository root | `True` on this Windows account |

Python contract tests exercise the local FastAPI capability boundary, code
exchange request shape, issuer/audience rejection, one-use local state,
encrypted persistence across in-process restart, live account refresh, and
remote revocation. The Node contract covers random code/state, origin
validation and per-user account reads. These tests mock the website/Supabase
boundary; they are not proof that migration 0003 ran or that external Auth
email/OAuth works.

`requests` was added to `backend/requirements.txt` because it is now a
runtime dependency for desktop cloud calls; it was already pinned in
`backend/requirements.lock`. An initial full-suite invocation from the
repository root had one harness failure: `test_reset_endpoint_blocked_in_debug`
starts a Uvicorn child with `cwd="."`, so the child could not import `main`
from that directory. The documented `backend/` invocation passed as shown
above. Whole-tree `git diff --check` also reports pre-existing trailing
whitespace in `backend/pipeline/transcriber.py` (R02 work); R08 files have no
whitespace errors.

## Staging-dependent acceptance

| Check | Status | Exact prerequisite and procedure |
|---|---|---|
| Apply 0003 after 0001/0002 and run `supabase/tests/cloud_device_identity.sql` | **NOT RUN** | Disposable local PostgreSQL with fixture roles/users; check replay, wrong state, expiry, role isolation and atomic session creation. Apply 0003 separately to staging and verify with staging accounts. |
| Browser signup/confirmation, Google OAuth, recovery/reset, sign-out and expired-link feedback | **NOT RUN** | Configured staging Supabase Auth email/OAuth plus deployed preview site and browser automation. |
| Account isolation and updated entitlement after a verified purchase | **NOT RUN** | Staging accounts and provider sandbox; payment/provider acceptance is separate task 15. |
| Windows installed app ↔ website ↔ Android same-user journey, restart and revocation | **NOT RUN** | Built installer, staging site, Android device, and signed-in test account. |
| Paid offline/expiry/revocation and cloud credit reserve/settle | **OPEN** | Owner decisions D2/D3/D7 and payment implementation; no paid usage claim. |

The full commercial release remains **NO GO**. No owner-approved deferral is
asserted for either identity or payment scope.
