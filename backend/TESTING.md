# CLPZ Test Suite

## Quick Start

```bash
cd backend
pip install pytest requests
python -m pytest tests/ -m "not slow" -v -q
```

## Test Commands

### Fast tests (recommended for development)
```bash
python -m pytest tests/ -m "not slow" -v -q
```
~23 seconds. Runs: auth, credits, admin, pipeline unit, desktop, edge cases (non-network).

### Full local tests (including network-triggered jobs)
```bash
python -m pytest tests/test_edge_cases.py -v -q
```
~2 minutes. Runs edge case tests that create background YouTube jobs.

### Slow / E2E tests (requires sufficient RAM)
```bash
python -m pytest tests/test_upload.py::TestUploadEndToEnd -v
```
~20-30 seconds. Upload → transcribe → render → validate MP4. Requires ~2GB free RAM.

### YouTube E2E (requires network + yt-dlp)
Run manually. Downloads a real YouTube video and processes through the full pipeline.

### By file
```bash
python -m pytest tests/test_auth.py -v        # Authentication (19 tests)
python -m pytest tests/test_credits.py -v     # Credits (9 tests)
python -m pytest tests/test_admin.py -v       # Admin (13 tests)
python -m pytest tests/test_pipeline.py -v    # Pipeline unit (9 tests)
python -m pytest tests/test_desktop.py -v     # Desktop (19 tests)
python -m pytest tests/test_edge_cases.py -v  # Edge cases (15 tests)
python -m pytest tests/test_upload.py -v      # Upload (5 tests)
```

### By category
```bash
python -m pytest -m "not slow"    # Exclude e2e/slow tests
python -m pytest -m "slow"        # Only e2e/slow tests
python -m pytest -m "integration" # Tests requiring the full server
python -m pytest -m "network"     # Tests requiring external network
```

## Test Count

| File | Tests | Category |
|------|-------|----------|
| test_auth.py | 19 | integration |
| test_credits.py | 9 | integration |
| test_admin.py | 13 | integration |
| test_pipeline.py | 9 | fast + integration |
| test_desktop.py | 19 | integration |
| test_edge_cases.py | 15 | fast + slow |
| test_upload.py | 5 | integration + slow |
| **Total** | **89** | |

- Fast suite: **80 tests, ~23 seconds**
- Slow suite: **8 tests, ~2 minutes**

## CI

GitHub Actions runs the fast suite on every push/PR.
See `.github/workflows/ci.yml`.

## Notes

- Tests use a dedicated server on port 8100 with isolated SQLite data
- DB is cleaned before and after each test
- Session-scoped server avoids startup overhead per test
- `CLPZ_DEBUG=1` enables high rate limits for testing
- Rate limit test is skipped in debug mode (by design)
- E2E upload test requires sufficient RAM (~2GB free) for Whisper
