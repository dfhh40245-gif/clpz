"""Task 08 — Atomic local credit ledger tests.

Acceptance checks under test:
- duplicate or zero-amount refund returns the correct balance, no exception
- concurrent bonus/debit/refund produce exactly the permitted ledger entries,
  never a negative balance
- crash injection between record and fulfillment leaves a recoverable
  operation; replay completes it exactly once
- ledger totals reconcile to balances
"""
import sys
import threading
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import credits as credits_mod
import database as db
import gumroad
from tests.test_remediation import isolated_data  # noqa: F401  (fixture)


def _mkuser(email_prefix="led"):
    u = db.create_user(uuid.uuid4().hex, f"{email_prefix}_{uuid.uuid4().hex[:8]}@test.com",
                       "hash", "salt")
    return u["id"]


# ── Duplicate / zero-amount refunds ────────────────────────────────

def test_duplicate_refund_returns_balance_no_exception(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 50, txn_type="purchase", description="seed")
    bal1 = credits_mod.refund(uid, 10, related_id="job-dup", reason="fail A")
    assert bal1 == 60
    # Duplicate (same related_id): no second refund, no exception.
    bal2 = credits_mod.refund(uid, 10, related_id="job-dup", reason="fail A repeat")
    assert bal2 == 60
    # Zero/negative amount: no-op returning current balance, no exception.
    assert credits_mod.refund(uid, 0, related_id="job-zero") == 60
    assert credits_mod.refund(uid, -5, related_id="job-neg") == 60
    # Only one refund ledger entry for the related_id exists.
    refunds = [t for t in db.get_transactions(uid, limit=100)
               if t["type"] == "refund" and t["related_id"] == "job-dup"]
    assert len(refunds) == 1


def test_zero_amount_refund_matches_reference_balance(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 7, txn_type="purchase")
    before = db.get_credit_balance(uid)
    after = credits_mod.refund(uid, 0, related_id="z")
    assert after == before == 7


# ── Concurrency: bonus / debit / refund ────────────────────────────

def test_concurrent_signup_bonus_grants_exactly_once(isolated_data):
    uid = _mkuser()
    results = []
    barrier = threading.Barrier(8)

    def grant():
        barrier.wait()
        results.append(credits_mod.ensure_signup_bonus(uid))

    threads = [threading.Thread(target=grant) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    bonus_txns = [t for t in db.get_transactions(uid, limit=100)
                  if t["type"] == "signup_bonus"]
    assert len(bonus_txns) == 1, f"expected 1 bonus txn, got {len(bonus_txns)}"
    assert credits_mod.get_balance(uid) == credits_mod.SIGNUP_BONUS
    assert all(r == credits_mod.SIGNUP_BONUS for r in results)


def test_concurrent_charges_never_oversell(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 10, txn_type="purchase")  # exactly 5 charges of 2
    results = []
    barrier = threading.Barrier(10)

    def charge():
        barrier.wait()
        results.append(credits_mod.check_and_charge(uid, 2))

    threads = [threading.Thread(target=charge) for _ in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    successes = [r for r in results if r[0]]
    assert len(successes) == 5, f"expected exactly 5 successful charges, got {len(successes)}"
    assert credits_mod.get_balance(uid) == 0
    rep = db.reconcile_ledger()
    assert rep["ok"], rep


def test_concurrent_refunds_single_mutation(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 20, txn_type="purchase")
    barrier = threading.Barrier(6)

    def refund():
        barrier.wait()
        credits_mod.refund(uid, 5, related_id="job-conc", reason="r")

    threads = [threading.Thread(target=refund) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert credits_mod.get_balance(uid) == 25
    refunds = [t for t in db.get_transactions(uid, limit=100)
               if t["type"] == "refund" and t["related_id"] == "job-conc"]
    assert len(refunds) == 1


def test_concurrent_mixed_ops_no_negative_balance(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 30, txn_type="purchase")
    barrier = threading.Barrier(9)

    def mixed(i):
        barrier.wait()
        if i % 3 == 0:
            credits_mod.ensure_signup_bonus(uid)
        elif i % 3 == 1:
            credits_mod.check_and_charge(uid, 3, related_id=f"job-{i}")
        else:
            credits_mod.refund(uid, 3, related_id=f"job-refund-{i}")

    threads = [threading.Thread(target=mixed, args=(i,)) for i in range(9)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    bal = credits_mod.get_balance(uid)
    assert bal >= 0
    rep = db.reconcile_ledger()
    assert rep["ok"], rep


# ── Crash injection: record→fulfill / charge→replay-record ─────────

def test_crash_between_payment_record_and_fulfillment_recovers_once(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    uid = _mkuser()
    sale_id = f"sale_{uuid.uuid4().hex[:10]}"
    payload = {"event": "sale", "sale": {
        "id": sale_id, "email": db.get_user_by_id(uid)["email"],
        "product_id": "clpz-pro", "permalink": "clpz-pro",
        "amount": 2900, "currency": "usd",
    }}

    # Inject a crash AFTER the payment row is recorded but BEFORE the grant
    # commits: monkeypatch the atomic fulfill to raise on first use.
    calls = {"n": 0}
    real_fulfill = db.fulfill_payment_credits

    def crashing_fulfill(*a, **kw):
        if calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("injected crash: process died before grant")
        return real_fulfill(*a, **kw)

    monkeypatch.setattr(db, "fulfill_payment_credits", crashing_fulfill)

    with pytest.raises(RuntimeError):
        gumroad.process_webhook(payload)

    # Recovery: the recorded-but-unfulfilled payment exists with a NULL grant.
    pay = db.get_payment("gumroad", sale_id)
    assert pay is not None
    assert pay["credits_granted"] is None

    # Replay completes it exactly once.
    r = gumroad.process_webhook(payload)
    assert r["credits"] == 100  # GUMROAD_DEFAULT_CREDITS default
    assert db.get_credit_balance(uid) == 100
    assert db.get_payment("gumroad", sale_id)["credits_granted"] == 100

    # A further replay grants nothing more.
    gumroad.process_webhook(payload)
    assert db.get_credit_balance(uid) == 100
    grants = [t for t in db.get_transactions(uid, limit=100) if t["amount"] == 100]
    assert len(grants) == 1


def test_charge_and_replay_record_are_one_transaction(isolated_data, monkeypatch):
    """A crash at the charge's commit cannot lose the replay record:
    with check_and_charge_idempotent they are the same commit, so an
    injected failure rolls BOTH back (no charge, no record)."""
    uid = _mkuser()
    db.add_credits(uid, 100, txn_type="purchase")
    key = f"idem_{uuid.uuid4().hex[:8]}"

    # Inject the crash exactly at the commit point of the charge txn.
    # Restore the commit explicitly afterwards (monkeypatch.undo() would also
    # undo the isolated_data fixture's patches and point the assertions at
    # the wrong database).
    orig_safe_commit = db._safe_commit

    def crashing_safe_commit(conn):
        raise RuntimeError("injected crash at commit")

    monkeypatch.setattr(db, "_safe_commit", crashing_safe_commit)

    with pytest.raises(RuntimeError):
        credits_mod.check_and_charge(uid, 10, related_id="job-crash", idempotency_key=key)

    monkeypatch.setattr(db, "_safe_commit", orig_safe_commit)
    # Rolled back: no charge happened...
    assert db.get_credit_balance(uid) == 100
    # ...no ledger entry exists...
    led = [t for t in db.get_transactions(uid, limit=100) if t["related_id"] == "job-crash"]
    assert led == []
    # ...and no replay record was persisted either.
    assert db.check_idempotency(key) is None
    # A retry with the same key then succeeds cleanly once.
    ok, remaining = credits_mod.check_and_charge(uid, 10, related_id="job-crash", idempotency_key=key)
    assert ok and remaining == 90
    # And replays return the cached result without double-charging.
    ok2, rem2 = credits_mod.check_and_charge(uid, 10, related_id="job-crash", idempotency_key=key)
    assert ok2 and rem2 == 90
    assert db.get_credit_balance(uid) == 90


# ── Payment reversal amount persistence ────────────────────────────

def test_reversal_uses_persisted_grant_not_current_config(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GUMROAD_PRODUCT_IDS", "clpz-pro")
    monkeypatch.setenv("GUMROAD_PRODUCT_CREDITS", "clpz-pro:120")
    uid = _mkuser()
    sale_id = f"sale_{uuid.uuid4().hex[:10]}"
    payload = {"event": "sale", "sale": {
        "id": sale_id, "email": db.get_user_by_id(uid)["email"],
        "product_id": "clpz-pro", "permalink": "clpz-pro",
        "amount": 2900, "currency": "usd",
    }}
    gumroad.process_webhook(payload)
    assert db.get_credit_balance(uid) == 120

    # Operator LATER changes the mapping; a refund must reverse what was
    # actually granted (120), not the new configured amount.
    monkeypatch.setenv("GUMROAD_PRODUCT_CREDITS", "clpz-pro:999")
    refund_payload = {"event": "refund", "sale": dict(payload["sale"], id=sale_id)}
    gumroad.process_webhook(refund_payload)
    assert db.get_credit_balance(uid) == 0  # exactly the granted 120 reversed
    assert db.get_payment("gumroad", sale_id)["credits_reversed"] == 120

    # Duplicate refund: still zero, no negative balance.
    gumroad.process_webhook(refund_payload)
    assert db.get_credit_balance(uid) == 0


def test_reversal_never_below_zero(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    uid = _mkuser()
    sale_id = f"sale_{uuid.uuid4().hex[:10]}"
    payload = {"event": "sale", "sale": {
        "id": sale_id, "email": db.get_user_by_id(uid)["email"],
        "product_id": "clpz-pro", "permalink": "clpz-pro",
        "amount": 2900, "currency": "usd",
    }}
    gumroad.process_webhook(payload)
    assert db.get_credit_balance(uid) == 100

    # User spent some credits before the refund.
    credits_mod.check_and_charge(uid, 40, related_id="spend")
    assert db.get_credit_balance(uid) == 60

    refund_payload = {"event": "refund", "sale": dict(payload["sale"], id=sale_id)}
    gumroad.process_webhook(refund_payload)
    assert db.get_credit_balance(uid) == 0  # clamped, not negative
    rep = db.reconcile_ledger()
    assert rep["ok"], rep


# ── Reconciliation ─────────────────────────────────────────────────

def test_reconcile_ok_on_clean_ledger(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 50, txn_type="purchase")
    credits_mod.ensure_signup_bonus(uid)
    credits_mod.check_and_charge(uid, 10, related_id="r1")
    credits_mod.refund(uid, 10, related_id="r1", reason="fail")
    rep = db.reconcile_ledger()
    assert rep["ok"], rep


def test_reconcile_detects_tampered_balance(isolated_data):
    uid = _mkuser()
    db.add_credits(uid, 50, txn_type="purchase")
    db.set_credit_balance(uid, 999)  # direct tampering
    rep = db.reconcile_ledger()
    assert not rep["ok"]
    entry = next(u for u in rep["users"] if u["user_id"] == uid)
    assert entry["delta"] == 949


def test_subtract_credits_clamped_ledger_reconciles(isolated_data):
    """The clamped-subtraction path must log the ACTUAL delta so the
    ledger still equals the balance afterwards."""
    uid = _mkuser()
    db.add_credits(uid, 10, txn_type="purchase")
    new_bal = db.subtract_credits(uid, 40, related_id="rev1", reason="reversal")
    assert new_bal == 0
    rep = db.reconcile_ledger()
    assert rep["ok"], rep


def test_migrate_legacy_payments_schema(isolated_data):
    """Fresh DBs apply migration v2 (credits_granted/credits_reversed)."""
    assert db.schema_version() >= 2
    uid = _mkuser()
    # Legacy-style insert path still works and records intent explicitly.
    created, pid = db.record_payment(uid, "gumroad", "ext-legacy", credits_granted=None)
    assert created
    pay = db.get_payment("gumroad", "ext-legacy")
    assert pay["credits_granted"] is None
