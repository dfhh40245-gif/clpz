"""Chunk 19: user isolation regression tests.

User A must never be able to read or modify User B's jobs, clips, credits,
or account.  Covers:

- per-job access (status / stream / ass / cancel / save) — 404 for others
- GET /api/jobs listing scope (owned jobs never leak across accounts)
- anonymous desktop jobs staying visible without login (private mode)
- credits: balance/transactions scoped to caller, admin-only mutation
"""
import uuid

import requests


def _email(prefix="iso"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def _signup(base, email):
    s = requests.Session()
    r = s.post(
        f"{base}/api/auth/signup",
        json={"email": email, "password": "pass123456"},
    )
    assert r.status_code == 200, r.text
    return s


def _create_job(session, base, tag):
    r = session.post(
        f"{base}/api/jobs",
        json={
            "url": f"https://youtube.com/watch?v=iso_{tag}",
            "max_clips": 1,
            "idempotency_key": f"iso_{tag}_{uuid.uuid4().hex[:8]}",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["job_id"]


class TestJobIsolation:
    def test_user_b_cannot_access_user_a_job(self, clean_server):
        base = clean_server.base_url
        a = _signup(base, _email("a"))
        b = _signup(base, _email("b"))
        job_id = _create_job(a, base, "secret")

        # Owner can read it.
        assert a.get(f"{base}/api/jobs/{job_id}").status_code == 200

        # User B must get 404 (never 403) so job ids cannot be probed.
        assert b.get(f"{base}/api/jobs/{job_id}").status_code == 404
        # Unauthenticated callers are blocked too.
        assert requests.get(f"{base}/api/jobs/{job_id}").status_code == 404

        # B is blocked on every owned-job endpoint, not just status.
        assert b.get(f"{base}/api/jobs/{job_id}/clips/0/stream").status_code == 404
        assert b.get(f"{base}/api/jobs/{job_id}/clips/0/ass").status_code == 404
        assert b.post(f"{base}/api/jobs/{job_id}/cancel").status_code == 404
        assert b.post(f"{base}/api/jobs/{job_id}/clips/0/save").status_code == 404

    def test_list_jobs_hides_other_users_jobs(self, clean_server):
        base = clean_server.base_url
        a = _signup(base, _email("lista"))
        b = _signup(base, _email("listb"))
        job_a = _create_job(a, base, "lista")
        job_b = _create_job(b, base, "listb")

        # Task 19: list returns paginated summaries {"projects": [...]}
        ids_a = {j["id"] for j in a.get(f"{base}/api/jobs").json()["projects"]}
        ids_b = {j["id"] for j in b.get(f"{base}/api/jobs").json()["projects"]}
        assert job_a in ids_a
        assert job_b in ids_b
        assert job_a not in ids_b
        assert job_b not in ids_a

    def test_anonymous_jobs_stay_visible_without_login(self, clean_server):
        base = clean_server.base_url
        # Desktop/private mode: anonymous job creation + listing without auth.
        anon = requests.Session()
        job_id = _create_job(anon, base, "anon")
        assert job_id in {j["id"] for j in requests.get(f"{base}/api/jobs").json()["projects"]}
        # Still visible to a signed-in user (shared local jobs).
        u = _signup(base, _email("viewer"))
        assert job_id in {j["id"] for j in u.get(f"{base}/api/jobs").json()["projects"]}
        # And the anonymous owner can still read it by id.
        assert anon.get(f"{base}/api/jobs/{job_id}").status_code == 200


class TestCreditIsolation:
    def test_credits_scoped_and_admin_only_mutation(self, clean_server, user_session):
        base = clean_server.base_url
        victim = user_session  # normal (non-admin) user
        attacker = _signup(base, _email("atk"))
        attacker_id = attacker.get(f"{base}/api/auth/me").json()["user"]["id"]
        victim_id = victim.get(f"{base}/api/auth/me").json()["user"]["id"]

        v_balance = victim.get(f"{base}/api/credits/balance").json()["balance"]
        assert v_balance == 10

        # A normal user cannot grant credits to themselves (admin bypass).
        r = attacker.post(
            f"{base}/api/admin/credits/add",
            params={"user_id": attacker_id, "amount": 50, "reason": "self grant"},
        )
        assert r.status_code == 403, f"admin add: {r.status_code} {r.text}"
        # Nor remove credits from anyone.
        r = attacker.post(
            f"{base}/api/admin/credits/remove",
            params={"user_id": victim_id, "amount": 5},
        )
        assert r.status_code == 403, f"admin remove: {r.status_code} {r.text}"

        # All remaining admin data endpoints are blocked for normal users.
        blocked = [
            f"/api/admin/users",
            f"/api/admin/stats",
            f"/api/admin/transactions/{victim_id}",
            f"/api/admin/users/search?q=vic",
            f"/api/admin/jobs",
        ]
        for path in blocked:
            assert attacker.get(f"{base}{path}").status_code == 403, path

        # The attacker's balance was never increased.
        assert attacker.get(f"{base}/api/credits/balance").json()["balance"] == 10
        # The victim's balance is untouched by the attacker's attempts.
        assert victim.get(f"{base}/api/credits/balance").json()["balance"] == v_balance

        # Transactions come back only for the calling account.
        txns = attacker.get(f"{base}/api/credits/transactions").json()["transactions"]
        assert txns, "expected at least the signup bonus transaction"
        assert all(t["type"] == "signup_bonus" for t in txns)
