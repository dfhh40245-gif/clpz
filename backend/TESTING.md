# CLPZ Test Suite

## Quick Start

```bash
# Full documented check (backend + React + website; Node/npm are required):
python scripts/check.py

# Focused backend check (explicitly records React/website as skipped):
python scripts/check.py --fast

# Or directly:
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -m "not slow" -q
```

## Hermetic guarantees (task 02)

- Every run gets a **unique temporary data directory** (`%TEMP%/clpz-tests-<id>/`)
  and a **unique free port**. Parallel checkouts never collide and no user's
  real database (`backend/data`, `%LOCALAPPDATA%/CLPZ`) is ever touched.
- Readiness is an **authenticated HTTP probe** (`/api/auth/me` returns 200/401),
  not a bare listening-port check — an unrelated listener fails the probe.
- The spawned server is **always cleaned up**, even on failure.
- Ledger tests use `CLPZ_TEST_WORKERS=0` (a dedicated `gated_server` fixture)
  so charges/refunds are observed deterministically. **Refund logic is never
  disabled** — with zero workers, no job ever starts, so no refund can race.
- Rate-limit/UX tests run in their own short-lived server (`CLPZ_DEBUG=0`)
  on their own unique port.

## Test Commands

### Fast tests (recommended for development)
```bash
python -m pytest tests/ -m "not slow" -q
```

### Full local tests (including network-triggered jobs)
```bash
python -m pytest tests/test_edge_cases.py -v -q
```
Runs edge case tests that create background YouTube jobs (network-dependent).

### Slow / E2E tests (requires sufficient RAM)
```bash
python -m pytest tests/test_upload.py::TestUploadEndToEnd -v
```
Upload → transcribe → render → validate MP4. Requires ~2GB free RAM.

### By category
```bash
python -m pytest -m "not slow"    # Exclude e2e/slow tests
python -m pytest -m "slow"        # Only e2e/slow tests
python -m pytest -m "integration" # Tests requiring the full server
python -m pytest -m "network"     # Tests requiring external network
```

## Notes

- Tests spin up their own server on a unique port with an isolated SQLite
  data dir under the system temp directory
- DB is cleaned before and after each test
- Session-scoped server avoids startup overhead per test
- `CLPZ_DEBUG=1` enables high rate limits for testing; throttling tests
  spawn a separate `CLPZ_DEBUG=0` server
- The insufficient-credit test pins `CLPZ_TEST_WORKERS=0` for a known balance
  (10) and asserts 402 — a refund race is structurally impossible there
