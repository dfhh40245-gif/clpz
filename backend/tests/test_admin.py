"""Admin system tests for CLPZ."""
import pytest
import requests


class TestAdminAuthorization:
    def test_normal_user_blocked(self, clean_server, user_session):
        r = user_session.get(f"{clean_server.base_url}/api/admin/users")
        assert r.status_code == 403

    def test_unauthenticated_blocked(self, clean_server):
        r = requests.get(f"{clean_server.base_url}/api/admin/users")
        assert r.status_code == 401

    def test_admin_can_access(self, clean_server, admin_session):
        r = admin_session.get(f"{clean_server.base_url}/api/admin/users")
        assert r.status_code == 200


class TestAdminStats:
    def test_stats_returns_data(self, clean_server, admin_session):
        r = admin_session.get(f"{clean_server.base_url}/api/admin/stats")
        assert r.status_code == 200
        data = r.json()
        assert "users" in data
        assert data["users"] >= 1


class TestAdminUsers:
    def test_list_users(self, clean_server, admin_session):
        r = admin_session.get(f"{clean_server.base_url}/api/admin/users")
        assert r.status_code == 200
        data = r.json()
        assert "users" in data
        assert len(data["users"]) >= 1

    def test_search_users(self, clean_server, admin_session):
        email = admin_session._admin_email
        r = admin_session.get(f"{clean_server.base_url}/api/admin/users/search?q={email[:5]}")
        assert r.status_code == 200
        assert len(r.json()["users"]) >= 1

    def test_search_empty(self, clean_server, admin_session):
        r = admin_session.get(f"{clean_server.base_url}/api/admin/users/search?q=zzzznonexistent")
        assert r.status_code == 200
        assert r.json()["users"] == []


class TestAdminCredits:
    def test_add_credits(self, clean_server, admin_session, user_session):
        r = user_session.get(f"{clean_server.base_url}/api/auth/me")
        user_id = r.json()["user"]["id"]
        r = admin_session.post(f"{clean_server.base_url}/api/admin/credits/add",
                               params={"user_id": user_id, "amount": 5, "reason": "Test grant"})
        assert r.status_code == 200
        assert r.json()["new_balance"] == 15

    def test_remove_credits(self, clean_server, admin_session, user_session):
        r = user_session.get(f"{clean_server.base_url}/api/auth/me")
        user_id = r.json()["user"]["id"]
        r = admin_session.post(f"{clean_server.base_url}/api/admin/credits/remove",
                               params={"user_id": user_id, "amount": 3, "reason": "Test removal"})
        assert r.status_code == 200
        assert r.json()["new_balance"] == 7

    def test_remove_too_many(self, clean_server, admin_session, user_session):
        r = user_session.get(f"{clean_server.base_url}/api/auth/me")
        user_id = r.json()["user"]["id"]
        r = admin_session.post(f"{clean_server.base_url}/api/admin/credits/remove",
                               params={"user_id": user_id, "amount": 100, "reason": "Over removal"})
        assert r.status_code == 400


class TestAdminTransactions:
    def test_view_user_transactions(self, clean_server, admin_session, user_session):
        r = user_session.get(f"{clean_server.base_url}/api/auth/me")
        user_id = r.json()["user"]["id"]
        r = admin_session.get(f"{clean_server.base_url}/api/admin/transactions/{user_id}")
        assert r.status_code == 200
        assert len(r.json()["transactions"]) > 0


class TestAdminJobs:
    def test_list_jobs(self, clean_server, admin_session):
        r = admin_session.get(f"{clean_server.base_url}/api/admin/jobs")
        assert r.status_code == 200
        assert "jobs" in r.json()


class TestAdminPage:
    def test_admin_page_accessible(self, clean_server):
        r = requests.get(f"{clean_server.base_url}/admin")
        assert r.status_code == 200
        assert "CLPZ Admin" in r.text
