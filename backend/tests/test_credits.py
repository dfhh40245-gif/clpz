"""Credit system tests for CLPZ."""
import pytest
import requests
import uuid
import threading


def _email(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


class TestSignupBonus:
    def test_new_user_gets_bonus(self, clean_server):
        r = requests.post(f"{clean_server.base_url}/api/auth/signup",
                          json={"email": _email("bonus"), "password": "pass123456"})
        assert r.json()["credits"] == 10

    def test_bonus_is_idempotent(self, clean_server):
        s = requests.Session()
        email = _email("idem")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r1 = s.post(f"{clean_server.base_url}/api/auth/login",
                     json={"email": email, "password": "pass123456"})
        r2 = s.post(f"{clean_server.base_url}/api/auth/login",
                     json={"email": email, "password": "pass123456"})
        assert r1.json()["credits"] == r2.json()["credits"] == 10


class TestCreditBalance:
    def test_balance_returns_correctly(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("bal"), "password": "pass123456"})
        r = s.get(f"{clean_server.base_url}/api/credits/balance")
        assert r.status_code == 200
        assert r.json()["balance"] == 10

    def test_unauthenticated_returns_401(self, clean_server):
        r = requests.get(f"{clean_server.base_url}/api/credits/balance")
        assert r.status_code == 401


class TestCreditDeduction:
    def test_successful_deduction(self, clean_server):
        s = requests.Session()
        email = _email("deduct")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        r = s.post(f"{clean_server.base_url}/api/jobs",
                    json={"url": "https://youtube.com/watch?v=test1", "max_clips": 1,
                          "idempotency_key": f"ded_{uuid.uuid4().hex[:8]}"})
        assert r.status_code == 200
        r = s.get(f"{clean_server.base_url}/api/credits/balance")
        assert r.json()["balance"] == 9

    def test_insufficient_credits(self, clean_server):
        s = requests.Session()
        email = _email("poor")
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": email, "password": "pass123456"})
        for i in range(10):
            s.post(f"{clean_server.base_url}/api/jobs",
                   json={"url": f"https://youtube.com/watch?v=v{i}", "max_clips": 1,
                         "idempotency_key": f"poor_{i}_{uuid.uuid4().hex[:4]}"})
        r = s.post(f"{clean_server.base_url}/api/jobs",
                    json={"url": "https://youtube.com/watch?v=over", "max_clips": 1,
                          "idempotency_key": f"poor_over_{uuid.uuid4().hex[:4]}"})
        assert r.status_code == 402


class TestIdempotency:
    def test_duplicate_request_no_double_charge(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("idemp"), "password": "pass123456"})
        key = f"idemp_{uuid.uuid4().hex[:8]}"
        r1 = s.post(f"{clean_server.base_url}/api/jobs",
                     json={"url": "https://youtube.com/watch?v=dup", "max_clips": 1,
                           "idempotency_key": key})
        r2 = s.post(f"{clean_server.base_url}/api/jobs",
                     json={"url": "https://youtube.com/watch?v=dup", "max_clips": 1,
                           "idempotency_key": key})
        assert r1.status_code == 200
        assert r2.status_code == 200
        r = s.get(f"{clean_server.base_url}/api/credits/balance")
        assert r.json()["balance"] == 9


class TestConcurrentDeduction:
    def test_concurrent_charges_are_safe(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("conc"), "password": "pass123456"})
        results = []

        def charge(i):
            r = s.post(f"{clean_server.base_url}/api/jobs",
                        json={"url": f"https://youtube.com/watch?v=c{i}", "max_clips": 1,
                              "idempotency_key": f"conc_{i}_{uuid.uuid4().hex[:4]}"})
            results.append(r.status_code)

        threads = [threading.Thread(target=charge, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        r = s.get(f"{clean_server.base_url}/api/credits/balance")
        bal = r.json()["balance"]
        assert 0 <= bal <= 10


class TestTransactionHistory:
    def test_transactions_recorded(self, clean_server):
        s = requests.Session()
        s.post(f"{clean_server.base_url}/api/auth/signup",
               json={"email": _email("txn"), "password": "pass123456"})
        r = s.get(f"{clean_server.base_url}/api/credits/transactions")
        assert r.status_code == 200
        txns = r.json()["transactions"]
        assert len(txns) >= 1
        assert any(t["type"] == "signup_bonus" for t in txns)
