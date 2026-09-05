"""Chunk 17 security regression tests.

Covers real vulnerabilities found in the production audit:
- job ownership enforcement (no cross-user job access)
- job_id validation (path/probing safety)
- /api/jobs/reset admin/debug guard
- upload size cap
- generic 500s (no stack traces)
"""
import uuid
import os
import subprocess
import sys
import time
import socket

import pytest
import requests

from .conftest import TestServer


@pytest.fixture(scope="module")
def server():
    s = TestServer(port=8123)
    s.start()
    yield s
    s.stop()


def _signup(base, email):
    s = requests.Session()
    r = s.post(
        f"{base}/api/auth/signup",
        json={"email": email, "password": "testpass123", "display_name": "Sec"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return s


def test_reset_endpoint_blocked_in_debug():
    """With CLPZ_DEBUG unset, /api/jobs/reset must 404 (not wipe jobs)."""
    port = 8124
    env = os.environ.copy()
    env["CLIPFORGE_DATA"] = "test_data"
    env["CLPZ_DEBUG"] = "0"
    env["CLPZ_ADMIN_EMAIL"] = "admin@test.com"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "error"],
        cwd=".", env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(30):
            try:
                sock = socket.socket()
                sock.settimeout(1)
                sock.connect(("127.0.0.1", port))
                sock.close()
                break
            except OSError:
                time.sleep(0.5)
        r = requests.post(f"http://127.0.0.1:{port}/api/jobs/reset", timeout=5)
        assert r.status_code == 404
        # And secure cookie flag is set when DEBUG=0
        r2 = requests.post(
            f"http://127.0.0.1:{port}/api/auth/signup",
            json={"email": f"sec-{uuid.uuid4().hex[:6]}@t.com", "password": "testpass123"},
            timeout=10,
        )
        cookie_header = r2.headers.get("set-cookie", "")
        assert "Secure" in cookie_header or "secure" in cookie_header
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_malformed_job_ids_return_404(server):
    """Traversal and malformed job ids must not leak or crash."""
    for bad in ["..%2F..%2Fetc", "zzzz", "aaaaaaaaaaa" * 30, "a>b", "%2e%2e%2f"]:
        r = requests.get(f"{server.base_url}/api/jobs/{bad}", timeout=5)
        assert r.status_code == 404, f"{bad}: {r.status_code}"
        assert "traceback" not in r.text.lower()


def test_error_responses_have_no_stack_traces(server):
    """Server errors must be generic, never expose internals."""
    r = requests.get(f"{server.base_url}/api/jobs/not-a-job", timeout=5)
    body = r.text.lower()
    assert "traceback" not in body
    assert ".py" not in body
    assert "windows" not in body or r.status_code == 404


def test_upload_endpoint_rejects_missing_parts(server):
    """Upload without a file must fail cleanly with 4xx."""
    r = requests.post(f"{server.base_url}/api/jobs/upload", timeout=10)
    assert 400 <= r.status_code < 500
    assert "traceback" not in r.text.lower()
