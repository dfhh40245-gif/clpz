"""Pytest configuration for CLPZ test suite."""
import os
import sys
import time
import uuid
import socket
import subprocess
import shutil
import pytest
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = BACKEND_DIR / "test_data"


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests for easy category filtering."""
    for item in items:
        # E2E and EndToEnd tests are slow
        if "e2e" in item.nodeid or "EndToEnd" in item.nodeid:
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.integration)
        # Tests that need the running server
        elif any(cls in item.nodeid for cls in ["test_auth", "test_credits", "test_admin",
                                                "test_upload", "test_desktop"]):
            item.add_marker(pytest.mark.integration)
        # Network-dependent tests
        if "youtube" in item.nodeid.lower() or "yt" in item.nodeid.lower():
            item.add_marker(pytest.mark.network)


class TestServer:
    __test__ = False  # pytest: not a test class despite the name

    def __init__(self, port=8100):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._proc = None
        self._data_dir = None

    def start(self):
        self._data_dir = TEST_DATA_DIR
        self._data_dir.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["CLIPFORGE_DATA"] = str(self._data_dir)
        env["CLPZ_DEBUG"] = "1"
        env["CLPZ_ADMIN_EMAIL"] = "admin@test.com"
        env["CLPZ_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{self.port}"
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "error"],
            cwd=str(BACKEND_DIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for _ in range(30):
            try:
                s = socket.socket(); s.settimeout(1); s.connect(("127.0.0.1", self.port)); s.close(); return
            except (ConnectionRefusedError, OSError):
                time.sleep(0.5)
        if self._proc:
            self._proc.kill()
            out, err = self._proc.communicate(timeout=5)
            raise RuntimeError(f"Server failed: {err.decode()[:300]}")
        raise RuntimeError("Server failed to start")

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try: self._proc.wait(timeout=5)
            except: self._proc.kill()
            self._proc = None

    def clean_db(self):
        """Fast cleanup: wipe all tables + reset in-memory jobs."""
        if not self._data_dir:
            return
        # Reset in-memory job state via API FIRST (before touching SQLite)
        try:
            _s = requests.Session()
            _s.post(f"{self.base_url}/api/jobs/reset", timeout=2)
        except Exception:
            pass
        db_path = self._data_dir / "clpz.db"
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path), timeout=10)
            try:
                for t in ["credit_transactions", "credits", "sessions", "jobs", "idempotency_keys", "verification_codes"]:
                    try: conn.execute(f"DELETE FROM {t}")
                    except: pass
                conn.execute("DELETE FROM users")
                conn.commit()
            finally:
                conn.close()

        # Clean legacy JSON files
        for f in ["users.json", "credits.json", "sessions.json", "credit_transactions.json"]:
            p = self._data_dir / f
            if p.exists():
                p.write_text("{}" if "transaction" not in f else "[]")


@pytest.fixture(scope="session")
def server():
    srv = TestServer(port=8100)
    srv.start()
    yield srv
    srv.stop()
    if srv._data_dir.exists():
        shutil.rmtree(srv._data_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_server(server):
    """Clean DB before and after each test."""
    server.clean_db()
    yield server
    server.clean_db()


def _unique_email(prefix="user"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture(scope="function")
def admin_session(clean_server):
    s = requests.Session()
    email = "admin@test.com"  # Must match CLPZ_ADMIN_EMAIL
    r = s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "adminpass123"})
    if r.status_code != 200:
        r = s.post(f"{clean_server.base_url}/api/auth/login",
                    json={"email": email, "password": "adminpass123"})
    assert r.status_code == 200, f"Admin auth failed: {r.text}"
    s._admin_email = email
    return s


@pytest.fixture(scope="function")
def user_session(clean_server):
    s = requests.Session()
    email = _unique_email("user")
    r = s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "userpass123"})
    assert r.status_code == 200, f"User signup failed: {r.text}"
    s._user_email = email
    return s
