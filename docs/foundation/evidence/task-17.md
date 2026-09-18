# Task 17 — Complete the website account and download journey

**R08 correction (2026-09-18):** Password recovery/reset, cloud account
display, and device-link UI have since been implemented; see
`R08-cloud-identity.md`. Build, lint, and local contract tests are recorded
there. Real email confirmation, OAuth, browser accessibility, staging account
isolation, and artifact download checks remain **NOT RUN**.

Task: 17 (website account/download journey)
Commit: 76e4b0a (baseline; tasks 01–17 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64); tsc 6.0.3 via deno node-compat (npm not installed on this machine)

## Original reproduction

AUDIT.md F21: "Callback next=/\untrusted.example passes startsWith checks
but new URL resolves it to https://untrusted.example/. This permits an
external redirect after successful code exchange."

Reproduced with `docs/foundation/probe_f21_redirect.py` (WHATWG resolution
approximation):

```
payload='/\\untrusted.example'   guard_pass=True  resolved=https://untrusted.example  off_origin=True
```

F22: website lacks password recovery/account entitlements UI; download
sources/configuration need consistency.

## Scope and policy decisions

- **F21 fix strategy**: validate the CANONICALIZED URL, not the raw string.
  `safeNextPath` rejects backslashes and control characters outright, then
  resolves the candidate against a placeholder origin and requires the
  result to stay inside that origin. A value that resolves to a path
  (`/account`, `/download`) passes; `/\untrusted.example`,
  `//untrusted.example`, and absolute-URL values fall back to `/account`.
  The actual redirect re-bases the proven path-only value onto the real
  request origin, so the check is deploy-origin independent.
- Post-exchange code remains single-use at the provider; failed exchanges
  redirect to `/login?error=oauth` unchanged.
- Account/download surface work (F22) is shared with tasks 15/16 (account
  page device-link form, entitlement display) and remains listed there;
  this task's deliverable is the security-critical callback guard plus the
  documented journey status.

## Files changed

- `website/app/auth/callback/route.ts`: canonical-validation guard.
- `docs/foundation/probe_f21_redirect.py` (new): reproducible probe.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Malicious `next` cannot redirect off-origin | `python docs/foundation/probe_f21_redirect.py` (before) + guard code (after) | `/\untrusted.example` rejected | guard rejects backslash + canonical cross-origin values → fallback `/account` | PASS (static + probe) | probe output; route code |
| Legitimate same-origin next still works | canonical check on `/account`, `/download?x=1` | allowed | path-only values pass unchanged | PASS (static) | route code |
| Confirm/reset/login/logout/download journey end-to-end | live staging site + Supabase staging | complete journey | not executed — no staging deployment or npm on this machine | **NOT RUN** | — |
| Google OAuth + email confirm on staging | live provider | working flow | **NOT RUN** (owner prerequisite: staging deploy) | **NOT RUN** | — |

## Migration and rollback

No data changes. Rollback = revert `website/app/auth/callback/route.ts`
(restore the defective guard).

## Remaining blockers

- Staging deployment (Vercel preview) + disposable Supabase project to run
  the full journey (confirm, reset, login, logout, account, download) and a
  live malicious-callback probe.
- Password recovery/reset and cloud entitlement/device-link UI were added in
  R08; staging browser and provider validation remain NOT RUN.

## Artifact name and SHA-256

N/A.

## Reviewer

Pending owner review.
