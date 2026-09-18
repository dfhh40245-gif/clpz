"""Credit system tests for CLPZ."""
import os
import shutil
import sys
import threading
import uuid
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import TestServer  # noqa: E402


def _email(prefix="test"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


# ── Deterministic ledger server (task 02) ─────────────────────────

@pytest.fixture(scope="module")
def gated_server():
    """A dedicated server whose worker pool is pinned to zero workers.

    Jobs stay 'queued', so a failing download can never complete and race an
    asynchronous refund into the balance mid-test. Legitimate refund logic
    remains enabled (it simply cannot fire for a job that never starts).
    This is the task-02 harness requirement, not a product behavior change.
    """
    prev = os.environ.get("CLPZ_TEST_WORKERS")
    prev_depth = os.environ.get("MAX_QUEUE_DEPTH")
    os.environ["CLPZ_TEST_WORKERS"] = "0"
    # This fixture tests credit exhaustion after ten accepted jobs; its
    # worker gate must have enough queue room to reach that assertion.
    os.environ["MAX_QUEUE_DEPTH"] = "12"
    try:
        srv = TestServer()  # picks a unique free port + unique temp data dir
        srv.start()
        yield srv
        srv.stop()
        shutil.rmtree(srv._data_dir, ignore_errors=True)
    finally:
        if prev is None:
            os.environ.pop("CLPZ_TEST_WORKERS", None)
        else:
            os.environ["CLPZ_TEST_WORKERS"] = prev
        if prev_depth is None:
            os.environ.pop("MAX_QUEUE_DEPTH", None)
        else:
            os.environ["MAX_QUEUE_DEPTH"] = prev_depth


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
    def test_successful_deduction(self, gated_server):
        gated_server.clean_db()
        try:
            s = requests.Session()
            s.headers.update({"X-CLPZ-Capability": gated_server.capability_token})
            email = _email("deduct")
            s.post(f"{gated_server.base_url}/api/auth/signup",
                   json={"email": email, "password": "pass123456"})
            r = s.post(f"{gated_server.base_url}/api/jobs",
                       json={"url": "https://youtube.com/watch?v=test1", "max_clips": 1,
                             "idempotency_key": f"ded_{uuid.uuid4().hex[:8]}"})
            assert r.status_code == 200
            r = s.get(f"{gated_server.base_url}/api/credits/balance")
            assert r.json()["balance"] == 9
        finally:
            gated_server.clean_db()

    def test_insufficient_credits(self, gated_server):
        """Exhaustion must 402 from a KNOWN balance with workers gated off,
        so no asynchronous refund can race the assertion."""
        gated_server.clean_db()
        try:
            s = requests.Session()
            s.headers.update({"X-CLPZ-Capability": gated_server.capability_token})
            email = _email("poor")
            s.post(f"{gated_server.base_url}/api/auth/signup",
                   json={"email": email, "password": "pass123456"})
            r = s.get(f"{gated_server.base_url}/api/credits/balance")
            assert r.json()["balance"] == 10, "expected known starting balance"
            for i in range(10):
                resp = s.post(f"{gated_server.base_url}/api/jobs",
                              json={"url": f"https://youtube.com/watch?v=v{i}", "max_clips": 1,
                                    "idempotency_key": f"poor_{i}_{uuid.uuid4().hex[:4]}"})
                assert resp.status_code == 200, f"charge {i + 1} failed: {resp.status_code}"
            r = s.post(f"{gated_server.base_url}/api/jobs",
                       json={"url": "https://youtube.com/watch?v=over", "max_clips": 1,
                             "idempotency_key": f"poor_over_{uuid.uuid4().hex[:4]}"})
            assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:200]}"
        finally:
            gated_server.clean_db()


class TestIdempotency:
    def test_duplicate_request_no_double_charge(self, clean_server):
        s = requests.Session()
        s.headers.update({"X-CLPZ-Capability": clean_server.capability_token})
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
    def test_concurrent_charges_are_safe(self, gated_server):
        """5 concurrent charges on a known 10-credit balance with workers gated:
        exactly 5 charges succeed (balance 5) and the ledger shows 5 debits."""
        gated_server.clean_db()
        try:
            s = requests.Session()
            s.headers.update({"X-CLPZ-Capability": gated_server.capability_token})
            s.post(f"{gated_server.base_url}/api/auth/signup",
                   json={"email": _email("conc"), "password": "pass123456"})
            results = []

            def charge(i):
                r = s.post(f"{gated_server.base_url}/api/jobs",
                           json={"url": f"https://youtube.com/watch?v=c{i}", "max_clips": 1,
                                 "idempotency_key": f"conc_{i}_{uuid.uuid4().hex[:4]}"})
                results.append(r.status_code)

            threads = [threading.Thread(target=charge, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            bal = s.get(f"{gated_server.base_url}/api/credits/balance").json()["balance"]
            assert 0 <= bal <= 10
            # Exactly 5 of 10 credits were consumed by the 5 accepted jobs.
            assert bal == 5, f"expected balance 5 after 5 accepted charges, got {bal}"
            assert results.count(200) == 5, f"expected 5 accepted jobs, got {results}"
        finally:
            gated_server.clean_db()


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
