"""Pytest configuration for CLPZ test suite (hermetic harness, task 02).

Hermetic guarantees:
- Every pytest run gets a UNIQUE temporary data directory and a UNIQUE free
  port. Multiple parallel checkouts never collide, and no user's real
  application database (backend/data, %LOCALAPPDATA%/CLPZ) is ever touched.
- Server readiness is an explicit authenticated HTTP probe, not a bare
  listening-port check.
- The spawned server process is always cleaned up, even on failure.
- Ledger tests can gate the worker pool via CLPZ_TEST_WORKERS=0 so charges and
  refunds are observed deterministically (jobs stay queued). Legitimate refund
  logic stays enabled — tests never disable it.
"""
import os
import sys
import time
import uuid
import socket
import shutil
import tempfile
import subprocess
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

# R02: the hermetic suite stubs transcription in-process, so supervised
# child-process transcription must be off for every test in this run.
# Env var covers spawned test servers; the module patch covers tests that
# import config directly in the pytest process (before other modules read it).
os.environ.setdefault("TRANSCRIBE_SUPERVISED", "0")
import config as _clpz_config  # noqa: E402
_clpz_config.TRANSCRIBE_SUPERVISED = False

# Isolated per-run data dir: unique under the system temp path, never the
# repo's backend/data or the desktop's real user data.
RUN_ID = uuid.uuid4().hex[:8]
TEST_DATA_DIR = Path(tempfile.gettempdir()) / f"clpz-tests-{RUN_ID}"


def _free_port() -> int:
    """Ask the OS for a free loopback port and release it immediately.

    There is an inherent TOCTOU window; retries handle the rare collision.
    """
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]
            except OSError:
                time.sleep(0.1)
    raise RuntimeError("could not find a free port")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests for easy category filtering."""
    for item in items:
        if "e2e" in item.nodeid or "EndToEnd" in item.nodeid:
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.integration)
        elif any(cls in item.nodeid for cls in ["test_auth", "test_credits", "test_admin",
                                                "test_upload", "test_desktop"]):
            item.add_marker(pytest.mark.integration)
        if "youtube" in item.nodeid.lower() or "yt" in item.nodeid.lower():
            item.add_marker(pytest.mark.network)


class TestServer:
    __test__ = False  # pytest: not a test class despite the name

    def __init__(self, port=None):
        self.port = port or _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._proc = None
        self._data_dir = None
        self._logs = []

    def start(self):
        # Fresh unique data dir per TestServer instance (used by the session
        # fixture; per-test isolation is provided by clean_db()).
        self._data_dir = TEST_DATA_DIR / f"srv-{uuid.uuid4().hex[:8]}"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["CLIPFORGE_DATA"] = str(self._data_dir)
        env["CLPZ_DEBUG"] = "1"
        env["CLPZ_DISABLE_MAINTENANCE"] = "1"
        env["CLPZ_ADMIN_EMAIL"] = "admin@test.com"
        env["CLPZ_ALLOWED_ORIGINS"] = f"http://127.0.0.1:{self.port}"
        env["CLPZ_FORCE_SECURE_COOKIES"] = "0"
        # The test harness acts as the "desktop UI": pre-set the capability
        # token so harness requests (POSTs) pass the local boundary, exactly
        # like the real launcher does in production.
        self.capability_token = "test-capability-" + uuid.uuid4().hex
        env["CLPZ_CAPABILITY_TOKEN"] = self.capability_token
        # Test-worker gate: CLPZ_TEST_WORKERS=0 pins the job semaphore to 0
        # effective workers (jobs stay queued) for deterministic ledger tests.
        workers = os.environ.get("CLPZ_TEST_WORKERS")
        if workers is not None:
            env["CLPZ_TEST_WORKERS"] = workers
        self._logs = [
            open(self._data_dir / "server_stdout.log", "ab"),
            open(self._data_dir / "server_stderr.log", "ab"),
        ]
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "error",
             "--no-proxy-headers"],
            cwd=str(BACKEND_DIR), env=env,
            stdout=self._logs[0], stderr=self._logs[1],
        )
        self._wait_ready()

    def post(self, path: str, **kwargs):
        """POST with the launch capability header (like the desktop UI)."""
        headers = kwargs.pop("headers", None) or {}
        headers["X-CLPZ-Capability"] = self.capability_token
        return requests.post(f"{self.base_url}{path}", headers=headers, **kwargs)

    def _wait_ready(self):
        """Readiness = HTTP 200/401 from the auth endpoint, not just an open port.

        An unrelated listener answering on this port fails the probe because it
        will not answer /api/auth/me with a status in (200, 401).
        """
        deadline = time.monotonic() + 45
        last_err = ""
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                tail = self._stderr_tail()
                raise RuntimeError(f"Test server exited early (rc={self._proc.returncode}).\n{tail}")
            try:
                r = requests.get(f"{self.base_url}/api/auth/me", timeout=2)
                if r.status_code in (200, 401):
                    return
                last_err = f"status {r.status_code}"
            except requests.RequestException as exc:
                last_err = str(exc)[:200]
            time.sleep(0.3)
        self.stop()
        raise RuntimeError(f"Server failed readiness probe within 45s ({last_err}).\n"
                           f"{self._stderr_tail()}")

    def _stderr_tail(self) -> str:
        try:
            self._logs[1].flush()
            return (self._data_dir / "server_stderr.log").read_text(
                encoding="utf-8", errors="replace")[-800:]
        except Exception:
            return ""

    def stop(self):
        if self._proc:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    self._proc.kill()
                    try:
                        self._proc.wait(timeout=3)
                    except Exception:
                        pass
            self._proc = None
        for f in self._logs:
            try:
                f.close()
            except Exception:
                pass
        self._logs = []

    def clean_db(self):
        """Fast cleanup: wipe all tables + reset in-memory jobs."""
        if not self._data_dir:
            return
        try:
            _s = requests.Session()
            _s.post(f"{self.base_url}/api/jobs/reset", timeout=5)
        except Exception:
            pass
        db_path = self._data_dir / "clpz.db"
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path), timeout=10)
            try:
                for t in ["credit_transactions", "credits", "sessions", "jobs",
                          "idempotency_keys", "idempotency_jobs",
                          "verification_codes"]:
                    try:
                        conn.execute(f"DELETE FROM {t}")
                    except Exception:
                        pass
                conn.execute("DELETE FROM users")
                conn.commit()
            finally:
                conn.close()
        for f in ["users.json", "credits.json", "sessions.json",
                  "credit_transactions.json"]:
            p = self._data_dir / f
            if p.exists():
                p.write_text("{}" if "transaction" not in f else "[]")


@pytest.fixture(scope="session")
def server():
    srv = TestServer()
    try:
        srv.start()
        yield srv
    finally:
        # ALWAYS stop the child and remove the per-run data dir.
        srv.stop()
        shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


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
    """Admin session via TRUSTED PROVISIONING (task 04).

    Admin is no longer granted by matching CLPZ_ADMIN_EMAIL at signup — that
    was the F01 defect. Instead the account is created normally, then the
    role is granted server-side directly in the test server's database
    (equivalent to scripts/provision_admin.py, which is what a machine owner
    runs). HTTP routes can never do this.
    """
    import sqlite3
    s = requests.Session()
    email = "admin@test.com"
    r = s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "adminpass123"})
    if r.status_code != 200:
        r = s.post(f"{clean_server.base_url}/api/auth/login",
                   json={"email": email, "password": "adminpass123"})
    assert r.status_code == 200, f"Admin auth failed: {r.text}"
    # Provision the role directly in the server's data dir (trusted path).
    db_path = clean_server._data_dir / "clpz.db"
    uid = r.json()["user"]["id"]
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (uid,))
        conn.commit()
    finally:
        conn.close()
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
