# Task 04 — Fix local admin and account recovery security

Task: 04 (account security)
Commit: 76e4b0a (baseline; tasks 01–04 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14, fastapi 0.141.1, SQLite (WAL) via Python 3.12 stdlib

## Scope and policy decisions

- Admin authorization now derives exclusively from the server-side
  `users.role` attribute, set only by the trusted provisioning CLI
  (`scripts/provision_admin.py`). `CLPZ_ADMIN_EMAIL` no longer grants
  anything (kept only for launcher env compatibility). This follows the task
  instruction to replace email-string authorization with trusted
  provisioning; task 16 may later replace local roles with cloud identity.
- Local auth routes remain enabled (per DECISIONS.md D11: SQLite accounts are
  a local-only feature until task 16), with the security fixes below applied.
- Password hashing adopts PBKDF2-SHA256 at 600,000 iterations in a versioned
  modular format, per the OWASP guidance cited by the audit; legacy hashes
  upgrade transparently on successful verification (migration-on-success,
  never a bulk rewrite of existing hashes).

## Original reproduction

From `docs/foundation/evidence/current-probes.json` (rerun on this machine
before changes):
- `admin_bootstrap`: signup with `foundation-owner@example.com` →
  `email_verified=false`, `GET /api/admin/users` = **200** (F01).
- `password_reset_throttle`: 15 wrong current-password attempts → fifteen
  **401**s, never 429 (F03).
- `backend/auth.py`: unversioned PBKDF2-SHA256 at 100,000 iterations (F04).
- `backend/email_service.py:70`: console fallback printed codes with debug
  off and returned `True` — reporting success without delivery (F04).

## Files changed

- `backend/auth.py`: versioned hash format `pbkdf2_sha256$<iter>$<salt>$<hash>`
  at 600k iterations; `needs_hash_upgrade` / `rehash_password`; legacy-format
  verification retained; transparent upgrade in `authenticate_user`;
  bounded password length (128 chars).
- `backend/database.py`: migration v1 adds `users.role` ('user' default);
  `set_user_role` / `get_user_role`.
- `backend/main.py`: single `_is_admin()` predicate used by `require_admin`,
  job-ownership override, and the jobs list; `ADMIN_EMAIL` neutered; the
  `/api/auth/reset` path is throttled by both peer and account buckets.
- `backend/email_service.py`: console fallback only with `CLPZ_DEBUG=1`,
  always returns `False` (a console print is not delivery); production
  failure returns `False` and logs without the code.
- `scripts/provision_admin.py` (new): trusted CLI to grant/revoke the admin
  role by user id or email against a chosen data dir.
- `backend/tests/test_account_security.py` (new): 13 regression tests.
- `backend/tests/conftest.py`: `admin_session` fixture provisions the role
  server-side (the trusted path) instead of relying on the email bootstrap.
- `backend/tests/test_remediation.py`: `test_clear_requires_admin` now also
  asserts an unprovisioned `admin@test.com` gets 403 before provisioning.

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| An attacker registering the configured owner email gets neither admin endpoints nor ownership bypass | `pytest tests/test_account_security.py::TestAdminBootstrap -q` | 401/403 | `test_owner_email_registration_grants_nothing` passes: signup 200 (unverified) then `/api/admin/users` 403, `/api/admin/stats` 403; remediation test also asserts unprovisioned `admin@test.com` gets 403 on `/api/jobs/clear` | PASS | test output below |
| Verified normal users remain non-admin; only the trusted provisioned identity can administer | same file, `TestAdminBootstrap` | verified non-provisioned → 403; provisioned → 200 | `test_verified_normal_user_stays_non_admin` and `test_provisioned_role_grants_admin` pass; CLI grant/revoke covered by `TestProvisionCLI` | PASS | backend/tests/test_account_security.py |
| Repeated reset guesses reach 429; spoofed forwarding headers do not evade limits | same file, `TestResetThrottling` | 429 within 15 attempts | `test_repeated_wrong_current_password_reaches_429` passes (429 observed); `test_xff_cannot_evade_reset_throttle` passes (per-account bucket throttles rotating XFF) | PASS | test output below |
| Old valid passwords still work through migration; debug-off logs/responses contain no reset codes; mail failures do not falsely report successful delivery | same file, `TestPasswordHashMigration` + `TestCodeDisclosure` | auth survives upgrade; no leak; truthful False | legacy-hash login succeeds and stored hash upgraded to `pbkdf2_sha256$600000$…`; debug-off forgot-password response contains no code; `send_verification_email` returns False without Resend in production and False (labeled debug print) in debug | PASS | backend/tests/test_account_security.py |

Full fast suite after changes: **144 passed, 1 skipped, 9 deselected**.

## Migration and rollback

- Schema: migration v1 (`ALTER TABLE users ADD COLUMN role …`) is applied
  idempotently via the existing `PRAGMA user_version` mechanism; existing
  databases upgrade in place, all rows default to `role='user'`. No data is
  rewritten. Rollback of the migration is not required for correctness; the
  previous code ignores the column.
- Operator action: after deploying, grant the owner account with
  `python -m scripts.provision_admin <email>` — this replaces the old
  CLPZ_ADMIN_EMAIL behavior. Documented in PRODUCTION_CONFIG.md.
- Rollback of the code = revert the listed files; legacy hash verification
  keeps working either way, so no stored credential becomes unreadable.

## Remaining blockers

- Local mail delivery (Resend) could not be exercised live: no API key is
  configured here, so the "delivery succeeds truthfully" path is verified at
  the unit level (truthful False on failure; HTTP path returns 200 with the
  generic message) — actual provider delivery remains untested.
- Shared/cloud admin concepts are out of scope here (task 14/16).

## Next unblocked task

Task 05 (pipeline resume) — prerequisite 02 satisfied; 03/04 also done.
