# R05 — direct backend startup initializes a capability token

Date: 2026-09-18

## Contract

`backend/main.py::_startup_capability_gate` calls
`capability.initialize_token()` at import time. Every supported backend entry
point imports `main` (direct `python -m uvicorn main:app --app-dir backend`,
`clpz_server.py serve`, both desktop launchers), so a direct start with debug
off and no launcher token now receives a fresh local token for its process
instead of serving mutations that all fail with 403.

`initialize_token()` preserves an already-active token: a desktop launcher
that set `CLPZ_CAPABILITY_TOKEN` before import keeps its token; only a process
without one gets a generated value. Rotation behavior is unchanged.

## Reproduction of the original defect

Review probe: started the app in a fresh temporary data environment with debug
off and `CLPZ_CAPABILITY_TOKEN` absent — `current_token()` was `None` and a
valid create request received 403.

## Tests (`backend/tests/test_boundary.py`)

- `test_initializer_preserves_launcher_token_and_creates_when_absent` — the
  review's scenario: absent token is created once; a pre-set launcher token is
  preserved and rotation keeps working.
- `test_token_rotation_invalidates_previous`,
  `test_capability_missing_or_stale_fails_when_required`,
  `test_valid_token_passes`, `test_token_not_in_error_text` — gate behavior
  is intact (not disabled to make the fix pass).

## Results

- Focused: `python -m pytest tests/test_boundary.py -q --tb=short` from
  `backend/` → **all passed** (2026-09-18, this machine; part of the 59-test
  focused run across R-fix modules: 59 passed).
- Included in the full fast suite: **312 passed, 2 skipped, 9 deselected**
  (2026-09-18, this machine, exit 0).
- `py_compile` clean for `backend/main.py`, `backend/capability.py`.

Note: the launcher paths (PyWebView dev launcher, frozen launcher) are covered
by their own test modules; a manual double-click launch was not performed on
this machine (recorded in task-12 evidence as NOT RUN).
