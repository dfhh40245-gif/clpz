"""Authentication tests for CLPZ."""
import pytest
import requests
import uuid


def _email(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


class TestSignup:
    def test_successful_signup(self, clean_server):
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": _email("new"), "password": "pass123456"})
        assert r.status_code == 200
        data = r.json()
        assert "user" in data
        assert data["credits"] == 10
        assert data["email_verified"] is False

    def test_duplicate_email_rejected(self, clean_server):
        email = _email("dup")
        requests.post(f"{clean_server.base_url}/api/auth/signup",
                      json={"email": email, "password": "pass123456"})
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": email, "password": "pass123456"})
        assert r.status_code in (400, 409)

    def test_invalid_email_rejected(self, clean_server):
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": "not-an-email", "password": "pass123456"})
        assert r.status_code == 400

    def test_short_password_rejected(self, clean_server):
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": _email("short"), "password": "123"})
        assert r.status_code == 400

    def test_session_cookie_set(self, clean_server):
        s = requests.Session()
        r = s.post(f"{clean_server.base_url}/api/auth/signup",
                    json={"email": _email("cookie"), "password": "pass123456"})
        assert "clpz_session" in s.cookies.get_dict()


class TestLogin:
    def test_successful_login(self, clean_server):
        email = _email("login")
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        s.post(f"{clean_server.base_url}/api/auth/logout")
        r = s.post(f"{clean_server.base_url}/api/auth/login",
                    json={"email": email, "password": "pass123456"})
        assert r.status_code == 200

    def test_wrong_password(self, clean_server):
        email = _email("wrong")
        requests.post(f"{clean_server.base_url}/api/auth/signup",
                      json={"email": email, "password": "pass123456"})
        r = requests.post(f"{clean_server.base_url}/api/auth/login",
                          json={"email": email, "password": "wrongpass"})
        assert r.status_code == 401

    def test_nonexistent_user(self, clean_server):
        r = requests.post(f"{clean_server.base_url}/api/auth/login",
                          json={"email": _email("ghost"), "password": "pass123456"})
        assert r.status_code == 401


class TestLogout:
    def test_logout_invalidates_session(self, clean_server):
        s = requests.Session()
        email = _email("logout")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r.status_code == 200
        s.post(f"{clean_server.base_url}/api/auth/logout")
        r = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r.status_code == 401


class TestAuthMe:
    def test_returns_user_info(self, clean_server):
        s = requests.Session()
        email = _email("me")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["user"]["email"] == email
        assert "credits" in r.json()["user"]

    def test_unauthenticated_returns_401(self, clean_server):
        r = requests.get(f"{clean_server.base_url}/api/auth/me")
        assert r.status_code == 401


class TestBearerToken:
    def test_bearer_auth_works(self, clean_server):
        s = requests.Session()
        email = _email("bearer")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        token = s.cookies.get("clpz_session", "")
        r = requests.get(f"{clean_server.base_url}/api/auth/me",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["user"]["email"] == email


class TestEmailVerification:
    def test_request_verification(self, clean_server):
        s = requests.Session()
        email = _email("verify")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/auth/request-verification",
                    json={"email": email})
        assert r.status_code == 200

    def test_wrong_code_rejected(self, clean_server):
        s = requests.Session()
        email = _email("wrongcode")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/auth/verify-email",
                    json={"email": email, "code": "000000"})
        assert r.status_code == 400

    def test_correct_code_verifies(self, clean_server):
        s = requests.Session()
        email = _email("correctcode")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/auth/request-verification",
                    json={"email": email})
        code = r.json().get("code", "")
        assert len(code) == 6
        r = s.post(f"{clean_server.base_url}/api/auth/verify-email",
                    json={"email": email, "code": code})
        assert r.status_code == 200
        r = s.get(f"{clean_server.base_url}/api/auth/me")
        assert r.json()["user"]["email_verified"] is True


class TestPasswordReset:
    def test_forgot_password(self, clean_server):
        s = requests.Session()
        email = _email("forgot")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/auth/forgot-password",
                    json={"email": email})
        assert r.status_code == 200

    def test_reset_with_code(self, clean_server):
        s = requests.Session()
        email = _email("reset")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        s.post(f"{clean_server.base_url}/api/auth/logout")
        r = s.post(f"{clean_server.base_url}/api/auth/forgot-password",
                    json={"email": email})
        code = r.json().get("code", "")
        r = s.post(f"{clean_server.base_url}/api/auth/reset-with-code",
                    json={"email": email, "code": code, "new_password": "newpass123"})
        assert r.status_code == 200
        r = s.post(f"{clean_server.base_url}/api/auth/login",
                    json={"email": email, "password": "newpass123"})
        assert r.status_code == 200

    def test_wrong_reset_code(self, clean_server):
        s = requests.Session()
        email = _email("wrongreset")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/auth/reset-with-code",
                    json={"email": email, "code": "000000", "new_password": "newpass123"})
        assert r.status_code == 400


class TestRateLimiting:
    def test_rate_limit_triggers(self, clean_server):
        # In debug mode, rate limits are high (1000/min)
        # This test verifies the rate limiter endpoint exists and works
        import os
        if os.getenv("CLPZ_DEBUG", "1") == "1":
            pytest.skip("Rate limit test skipped in debug mode (limits are high)")
        s = requests.Session()
        for i in range(12):
            r = s.post(f"{clean_server.base_url}/api/auth/login",
                        json={"email": _email("rl"), "password": "wrong"})
        assert r.status_code == 429
