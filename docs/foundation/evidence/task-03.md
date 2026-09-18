# Task 03 — Protect the desktop's local API

Task: 03 (desktop API boundary)
Commit: 76e4b0a (baseline; tasks 01–03 changes are uncommitted working tree)
Tester: Buffy (Codebuff agent)
Date: 2026-09-17
OS/device and hardware: Windows 11 dev machine (x64)
Runtime/tool/model versions: Python 3.12.14, FFmpeg 9.0.1 (bundled), fastapi 0.141.1, uvicorn 0.53.0

## Original reproduction

From `docs/foundation/evidence/current-probes.json` (rerun on this machine
before changes):
- `local_boundary.untrusted_origin_cancel` = **200** — a cancel POST with
  `Origin: https://untrusted.example` was accepted.
- `local_boundary.untrusted_host_list` = **200** — `GET /api/jobs` with
  `Host: untrusted.example` was accepted.
- Anonymous job creation was permitted regardless of debug mode; loopback
  binding was the only protection.

## Design

New `backend/capability.py` implements the boundary as middleware
(`LocalBoundaryMiddleware` in `backend/main.py`, runs before CORS):

1. **Host validation** — the Host header must be a loopback form (any port)
   or an explicit allowlist entry (`CLPZ_ALLOWED_HOSTS`). Foreign hosts get
   HTTP 421.
2. **Origin classification** — no Origin header ⇒ native request (desktop
   webview, tests, curl): allowed through the origin stage. Origin present ⇒
   must be same-origin (or a loopback alias) or the mutation is rejected 403.
3. **Per-launch capability** — a 256-bit token generated per launch (or
   pre-set by the launcher via `CLPZ_CAPABILITY_TOKEN`), compared with
   `hmac.compare_digest`. Required for POST/PUT/PATCH/DELETE outside
   `/api/auth/`. Delivered ONLY by server-side injection into the `/app` and
   `/admin` HTML (`<meta name="clpz-capability">`) — never in URLs, API
   responses, or logs. All three frontends (`frontend/clpz.html`,
   `frontend/auth.html`, `frontend/admin.html`, `frontend-app/src/lib/api.ts`)
   read the meta tag and send `X-CLPZ-Capability` on mutations.
4. **Read-only routes stay open** — video playback, thumbnails, pages,
   diagnostics work with protection enabled (video Range playback intact).
5. **Production refuses insecure modes** — startup raises SystemExit when
   `CLPZ_REQUIRE_CAPABILITY=0` without `CLPZ_DEBUG=1`.
6. **Debug convenience** — `CLPZ_DEBUG=1` servers relax ONLY the capability
   requirement (Host/Origin still enforced) so scripts/tests keep working.
   Production always enforces the token.

Launchers (`desktop/server.py`, `desktop/frozen_launcher.py`) now force
`CLPZ_DEBUG=0` (the frozen launcher ignores inherited debug; developer opt-in
is `--clpz-debug`), keep the gate on, and rotate a fresh token each launch.

## Files changed

- `backend/capability.py` (new): token lifecycle, Host/Origin checks, request decision logic.
- `backend/main.py`: middleware wiring, startup gate, token injection into `/app` + `/admin`.
- `frontend/clpz.html`, `frontend/auth.html`, `frontend/admin.html`, `frontend-app/src/lib/api.ts`: capability header on mutations.
- `desktop/server.py`, `desktop/frozen_launcher.py`: forced production settings + per-launch token rotation.
- `backend/tests/conftest.py`: harness pre-sets the token (acts as the desktop UI).
- `backend/tests/test_boundary.py` (new): 19 unit + end-to-end boundary tests.
- `backend/tests/test_security.py`: fixed port → free port, isolated temp data dir, sends valid capability to test the reset route's 404 (not the boundary's 403).

## Checks

| Acceptance item | command/manual steps | expected | actual | status | evidence |
|---|---|---|---|---|---|
| Untrusted Host/Origin mutations fail; missing/stale capability fails; approved same-origin actions work | `pytest tests/test_boundary.py -q` | 421/403/403 as described | 19 passed: untrusted host 421 e2e; cross-origin cancel 403 e2e; missing token 403 e2e; stale token fails after rotation (unit); same-origin passes | PASS | test output below |
| Token rotation invalidates the prior launch; no token appears in logs or error text | unit: rotate then replay old token; inspect all middleware reject reasons | stale fails; reasons are short fixed strings | `test_token_rotation_invalidates_previous` passes; reject reasons (`untrusted-host`, `cross-origin-browser-request`, `missing-or-stale-capability`) contain no token material; server never logs the token | PASS | backend/tests/test_boundary.py, backend/capability.py |
| Desktop import, video Range playback, thumbnails, export, and restart work with protection enabled | e2e: media GETs without token; full suite green incl. upload/credit/admin flows | reads OK; mutations with token OK | `test_video_range_playback_works_with_protection` passes; full fast suite 131 passed (uploads, exports, admin) with protection active | PASS | test output below |
| No normal launcher binds 0.0.0.0; the desktop query parameter alone cannot enable privileged behavior | static check + e2e | no 0.0.0.0 anywhere; `?desktop=1` gives no privileges | `test_no_launcher_binds_0000` passes over all 3 launcher files; `test_desktop_query_param_alone_cannot_authorize` passes (page 200, POST without token 403) | PASS | backend/tests/test_boundary.py |

Full fast suite after changes: **131 passed, 1 skipped, 9 deselected** (was 110/2F before tasks 02–03).

## Migration and rollback

No schema/data migration. Rollback = revert the listed files; the middleware
and startup gate disappear with `capability.py`. Clients that cached no token
are unaffected because the boundary is server-side only.

## Remaining blockers

- A real installed-EXE launch on a Python-free Windows account (task 12's
  clean-machine check) was NOT RUN here; the boundary is verified against
  uvicorn servers (dev + production-mode) and mocked launcher layouts.
- The token reaches the UI via HTML injection; PyWebView-specific URL-scheme
  edge cases could not be exercised without a GUI session.

## R05 remediation — 2026-09-18

Direct `uvicorn main:app` startup previously had no launcher process to supply
`CLPZ_CAPABILITY_TOKEN`; production mutations consequently failed even though
the local page was usable. `capability.initialize_token()` now preserves a
launcher-provided token or creates one exactly once when an entry point imports
`main`. This covers direct Uvicorn and the packaged `clpz_server` entry, while
the development and frozen desktop launchers continue to supply their own fresh
per-launch token. `/app`, `/admin`, `/auth.html`, and the server-rendered
React entry page inject the active token in local HTML only.

| Check | Result | Status |
|---|---|---|
| `pytest backend/tests/test_boundary.py -q --tb=short` | 21 passed | PASS |
| Fresh direct Uvicorn process with `CLPZ_CAPABILITY_TOKEN` removed | `/app` contained a generated capability; mutation without it returned 403; the page-supplied token passed the boundary | PASS |
| Launcher token lifecycle unit check | supplied token is retained; absent token is generated once | PASS |
| Frozen/PyWebView installed launch | no GUI/clean installed EXE run in this change | NOT RUN |

## Next unblocked task

Task 04 (account security).
