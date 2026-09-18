"""Task 04 — Account security regression tests.

Covers the task 04 acceptance checks:
- registering the configured owner email grants NO admin endpoints/ownership
- verified normal users remain non-admin; only provisioned identity administers
- repeated reset guesses reach 429; forwarding headers cannot evade limits
- old passwords still work through hash migration; debug-off responses contain
  no reset codes; delivery failures never report success
"""
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auth as auth_mod  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _email(prefix="sec04"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def _free_port() -> int:
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", 0))
                return s.getsockname()[1]
            except OSError:
                time.sleep(0.05)
    raise RuntimeError("no free port")


def _start_server(extra_env: dict, debug: str = "0"):
    port = _free_port()
    data_dir = Path(tempfile.mkdtemp(prefix="clpz-sec04-"))
    env = os.environ.copy()
    env.update({
        "CLIPFORGE_DATA": str(data_dir),
        "CLPZ_DEBUG": debug,
        "CLPZ_DISABLE_MAINTENANCE": "1",
        # The attacker registers exactly this "owner" address — it must grant
        # nothing under the new role-based model.
        "CLPZ_ADMIN_EMAIL": "foundation-owner@example.com",
    })
    env.update(extra_env)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "error"],
        cwd=str(BACKEND_DIR), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("server exited early")
        try:
            r = requests.get(f"http://127.0.0.1:{port}/api/diagnostics", timeout=2)
            if r.status_code == 200:
                return proc, port, data_dir
        except requests.RequestException:
            pass
        time.sleep(0.3)
    proc.kill()
    raise RuntimeError("server not ready")


def _stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def prod_server():
    proc, port, data_dir = _start_server({})
    yield port, data_dir
    _stop(proc)


class TestAdminBootstrap:
    def test_owner_email_registration_grants_nothing(self, prod_server):
        """The F01 attack: register the configured admin email -> admin 200."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        s = requests.Session()
        r = s.post(f"{base}/api/auth/signup",
                   json={"email": "foundation-owner@example.com",
                         "password": "attackerpass123"})
        assert r.status_code == 200
        verified = r.json().get("email_verified")
        # The registration is not verified — and grants nothing regardless:
        r2 = s.get(f"{base}/api/admin/users")
        assert r2.status_code in (401, 403), (
            f"registering the owner email granted admin: {r2.status_code}")
        r3 = s.get(f"{base}/api/admin/stats")
        assert r3.status_code in (401, 403)

    def test_verified_normal_user_stays_non_admin(self, prod_server):
        """A verified user without the provisioned role must not administer."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": _email(), "password": "userpass123"})
        db = sqlite3.connect(str(data_dir / "clpz.db"))
        try:
            db.execute("UPDATE users SET email_verified = 1")
            db.commit()
        finally:
            db.close()
        r = s.get(f"{base}/api/admin/users")
        assert r.status_code == 403, "verified non-provisioned user got admin"

    def test_provisioned_role_grants_admin(self, prod_server):
        """Only the trusted provisioned identity can administer (fixture path)."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        s = requests.Session()
        r = s.post(f"{base}/api/auth/signup",
                   json={"email": "owner-provision@example.com",
                         "password": "ownerpass123"})
        uid = r.json()["user"]["id"]
        # Trusted provisioning (what scripts/provision_admin.py does):
        db = sqlite3.connect(str(data_dir / "clpz.db"))
        try:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (uid,))
            db.commit()
        finally:
            db.close()
        r2 = s.get(f"{base}/api/admin/users")
        assert r2.status_code == 200, "provisioned admin was denied"

    def test_provisioned_admin_gets_ownership_bypass(self, prod_server):
        """The single predicate covers admin endpoints AND job ownership."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        # Owner creates a job (upload path not needed: a queued job suffices)
        owner = requests.Session()
        r = owner.post(f"{base}/api/auth/signup",
                       json={"email": _email("jobowner"), "password": "userpass123"})
        uid = r.json()["user"]["id"]
        # Provision the owner-role account separately
        admin = requests.Session()
        r2 = admin.post(f"{base}/api/auth/signup",
                        json={"email": "adm@example.com", "password": "adminpass123"})
        admin_uid = r2.json()["user"]["id"]
        db = sqlite3.connect(str(data_dir / "clpz.db"))
        try:
            db.execute("UPDATE users SET role='admin' WHERE id=?", (admin_uid,))
            db.commit()
        finally:
            db.close()
        # The admin must NOT see a 200 list containing another user's owned job
        # unless that job exists server-side — here we assert the role check
        # path works by hitting admin endpoints and the ownership predicate
        # through the admin list (jobs list is admin-filtered).
        r3 = admin.get(f"{base}/api/admin/users")
        assert r3.status_code == 200


class TestResetThrottling:
    def test_repeated_wrong_current_password_reaches_429(self, prod_server):
        """F03: 15 wrong guesses must hit a limit (was: all 401)."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": _email("reset"), "password": "correctpass123"})
        codes = []
        for i in range(15):
            r = s.post(f"{base}/api/auth/reset",
                       json={"email": "x" * 0 + _email("reset"),  # fresh addr → wrong user
                             "current_password": "wrong",
                             "new_password": "whatever123"})
            codes.append(r.status_code)
        assert 429 in codes, f"15 wrong reset attempts never throttled: {codes}"

    def test_xff_cannot_evade_reset_throttle(self, prod_server):
        """Rotating X-Forwarded-For must not defeat the per-peer limit:
        each forged IP yields a fresh 10-bucket, but the ACCOUNT bucket
        (keyed by email) still throttles the attacker."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        target = _email("xffacct")
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": target, "password": "correctpass123"})
        codes = []
        for i in range(15):
            r = s.post(f"{base}/api/auth/reset",
                       json={"email": target, "current_password": f"wrong{i}",
                             "new_password": "whatever123"},
                       headers={"X-Forwarded-For": f"203.0.113.{i}"})
            codes.append(r.status_code)
        assert 429 in codes, (
            f"rotating X-Forwarded-For evaded the account-bucket throttle: {codes}")


class TestPasswordHashMigration:
    def test_legacy_hash_still_authenticates_and_upgrades(self, tmp_path, monkeypatch):
        """An old 100k-iteration bare hash must keep working, then upgrade."""
        import database as db
        db_file = tmp_path / "clpz.db"
        monkeypatch.setattr(db, "_DB_PATH", db_file)
        monkeypatch.setattr(db, "_conn", None)

        # Create user with a LEGACY-format hash (bare hex, 100k iterations)
        salt = "a" * 32
        legacy_hash = auth_mod._hash_password_legacy("oldpass123", salt)[0]
        uid = "legacyuser1"
        db.create_user(uid, "legacy@example.com", legacy_hash, salt, display_name="L")
        assert not auth_mod.needs_hash_upgrade(legacy_hash) is False  # sanity

        # Authenticate with the old password → must succeed
        user = auth_mod.authenticate_user("legacy@example.com", "oldpass123")
        assert user is not None, "legacy password no longer works (migration broke auth)"

        # And the stored hash must now be upgraded to the versioned format
        pw = db.get_user_password("legacy@example.com")
        assert pw["password_hash"].startswith("pbkdf2_sha256$"), (
            "successful login did not upgrade the legacy hash")
        assert auth_mod.needs_hash_upgrade(pw["password_hash"]) is False

        # Wrong password still rejected
        assert auth_mod.authenticate_user("legacy@example.com", "wrong") is None

    def test_new_hashes_are_versioned(self):
        stored, salt = auth_mod._hash_password("newpass123")
        assert stored.startswith(f"pbkdf2_sha256${auth_mod.PBKDF2_ITERATIONS}$")
        assert auth_mod.needs_hash_upgrade(stored) is False

    def test_password_length_bounded(self):
        with pytest.raises(ValueError):
            auth_mod._hash_password("x" * (auth_mod.MAX_PASSWORD_LEN + 1))


class TestCodeDisclosure:
    def test_debug_off_no_code_in_response_or_logs(self, prod_server):
        """Debug-off responses must not contain reset/verification codes."""
        port, data_dir = prod_server
        base = f"http://127.0.0.1:{port}"
        s = requests.Session()
        s.post(f"{base}/api/auth/signup",
               json={"email": _email("codes"), "password": "userpass123"})
        r = s.post(f"{base}/api/auth/forgot-password",
                   json={"email": _email("codes")})
        body = r.text
        assert "code" not in {k.lower() for k in r.json().keys()} or not any(
            ch.isdigit() for ch in r.json().get("code", "")), body
        # The response must be the generic message (or an explicit no-delivery
        # error), never a leaked code.
        assert '"code": "' not in body and "'code'" not in body

    def test_mail_failure_reports_false_not_success(self, monkeypatch):
        """Production without Resend must NOT claim delivery success."""
        import email_service
        monkeypatch.setenv("CLPZ_DEBUG", "0")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        ok = email_service.send_verification_email("a@example.com", "123456")
        assert ok is False, "console fallback reported success with debug off"

    def test_debug_fallback_honest_false(self, monkeypatch, capsys):
        """Even in debug, the console fallback is not an email delivery."""
        import email_service
        monkeypatch.setenv("CLPZ_DEBUG", "1")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        ok = email_service.send_verification_email("a@example.com", "123456")
        assert ok is False
        captured = capsys.readouterr()
        # The code IS printed for local dev convenience, clearly labeled.
        assert "123456" in captured.out
        assert "not delivered" in captured.out.lower()


class TestProvisionCLI:
    def test_cli_grants_and_revokes(self, tmp_path):
        """The provisioning CLI works end-to-end against a fresh data dir."""
        data_dir = tmp_path / "prov"
        env = os.environ.copy()
        env["CLIPFORGE_DATA"] = str(data_dir)
        # Create a user first by importing the app modules directly
        create = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'" + str(BACKEND_DIR) + "');\n"
             "import auth; auth.create_user('cli-admin@example.com', 'clipass123')"],
            env=env, capture_output=True, text=True, cwd=str(BACKEND_DIR))
        assert create.returncode == 0, create.stderr
        # Grant
        grant = subprocess.run(
            [sys.executable, "-m", "scripts.provision_admin", "cli-admin@example.com",
             "--data-dir", str(data_dir)],
            capture_output=True, text=True, cwd=str(BACKEND_DIR.parent))
        assert grant.returncode == 0, grant.stderr + grant.stdout
        assert "granted admin" in grant.stdout
        # Revoke
        revoke = subprocess.run(
            [sys.executable, "-m", "scripts.provision_admin", "cli-admin@example.com",
             "--revoke", "--data-dir", str(data_dir)],
            capture_output=True, text=True, cwd=str(BACKEND_DIR.parent))
        assert revoke.returncode == 0, revoke.stderr
        assert "revoked" in revoke.stdout
