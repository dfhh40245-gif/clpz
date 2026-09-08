"""Regression tests for the Gumroad webhook integration.

Invariants under test:
  - invalid signature -> rejected (403)
  - one Gumroad sale -> one payment record -> one credit grant
  - duplicate webhook delivery -> idempotent no-op (no double grant)
  - refund reverses the original grant
  - unlinked buyer (no CLPZ account) -> payment recorded, NO credits granted
  - product allowlist blocks out-of-scope products
"""

import hashlib
import hmac
import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db
import gumroad
from tests.test_remediation import isolated_data  # reuse the temp-dir fixture


def _email(prefix="gm"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


def _mkuser():
    user = db.create_user(uuid.uuid4().hex, _email(), "hash", "salt", display_name="Tester")
    return user["id"]


def _sale_payload(event="sale", sale_id=None, email=None, product_id="clpz-pro",
                  custom_fields=None, amount=2900):
    sale = {
        "id": sale_id or f"sale_{uuid.uuid4().hex[:10]}",
        "email": email or "buyer@test.com",
        "product_id": product_id,
        "permalink": product_id,
        "amount": amount,
        "currency": "usd",
    }
    if custom_fields is not None:
        sale["custom_fields"] = custom_fields
    return {"event": event, "sale": sale}


def _signed(body: bytes, secret: str):
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"x-gumroad-signature": sig}


# ── Signature verification ─────────────────────────────────────────

def test_invalid_signature_rejected(monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(gumroad.config, "DEBUG", False)
    body = json.dumps(_sale_payload()).encode()
    assert gumroad.verify_signature(body, "deadbeef") is False
    assert gumroad.verify_signature(body, None) is False


def test_valid_signature_accepted(monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(gumroad.config, "DEBUG", False)
    body = json.dumps(_sale_payload()).encode()
    sig = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
    assert gumroad.verify_signature(body, sig) is True


def test_signature_verification_disabled_only_in_debug(monkeypatch):
    """Without a configured secret, verification is refused outside debug."""
    monkeypatch.delenv("GUMROAD_WEBHOOK_SECRET", raising=False)
    monkeypatch.setattr(gumroad.config, "DEBUG", False)
    assert gumroad.verify_signature(b"{}", None) is False
    monkeypatch.setattr(gumroad.config, "DEBUG", True)
    assert gumroad.verify_signature(b"{}", None) is True


# ── Idempotent credit grant ─────────────────────────────────────────

def test_sale_grants_credits_once(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GUMROAD_PRODUCT_IDS", "clpz-pro")
    monkeypatch.setenv("GUMROAD_DEFAULT_CREDITS", "100")
    uid = _mkuser()
    payload = _sale_payload(email="buyer@test.com", product_id="clpz-pro")
    # make the sale email match the user
    payload["sale"]["email"] = db.get_user_by_id(uid)["email"]

    r1 = gumroad.process_webhook(payload)
    assert r1["created"] is True
    assert r1["credits"] == 100
    assert db.get_credit_balance(uid) == 100

    # Duplicate delivery (same sale id) -> no-op
    r2 = gumroad.process_webhook(payload)
    assert r2["created"] is False
    assert r2["credits"] == 0
    assert db.get_credit_balance(uid) == 100
    assert len(db.get_user_payments(uid)) == 1


def test_custom_field_user_id_mapping(isolated_data, monkeypatch):
    """A clpz_user_id custom field must map even without email match."""
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    uid = _mkuser()
    payload = _sale_payload(
        email="someone-else@example.com",
        custom_fields={"clpz_user_id": uid},
    )
    r = gumroad.process_webhook(payload)
    assert r["user_id"] == uid
    assert db.get_credit_balance(uid) > 0


def test_unlinked_buyer_gets_no_credits(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    payload = _sale_payload(email="nobody@example.com")
    r = gumroad.process_webhook(payload)
    assert r["created"] is True
    assert r["user_id"] is None
    assert r["credits"] == 0
    # Payment is still recorded (audit trail), but no credits were granted
    assert db.get_payment("gumroad", payload["sale"]["id"]) is not None


def test_product_allowlist_blocks(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GUMROAD_PRODUCT_IDS", "clpz-pro,clpz-premium")
    uid = _mkuser()
    payload = _sale_payload(product_id="some-other-product")
    payload["sale"]["email"] = db.get_user_by_id(uid)["email"]
    r = gumroad.process_webhook(payload)
    assert r["created"] is True
    assert r["credits"] == 0
    assert db.get_credit_balance(uid) == 0


# ── Refunds ─────────────────────────────────────────────────────────

def test_refund_reverses_grant(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GUMROAD_DEFAULT_CREDITS", "100")
    uid = _mkuser()
    payload = _sale_payload(email=db.get_user_by_id(uid)["email"])
    sale_id = payload["sale"]["id"]

    gumroad.process_webhook(payload)
    assert db.get_credit_balance(uid) == 100

    refund = _sale_payload(event="refund", sale_id=sale_id,
                           email=db.get_user_by_id(uid)["email"])
    r = gumroad.process_webhook(refund)
    # The payment already existed (created=False), but the reversal still
    # transitioned status and reversed the credits.
    assert r["created"] is False
    assert r["credits"] == 0
    # balance goes back to 0 (never below zero)
    assert db.get_credit_balance(uid) == 0
    assert db.get_payment("gumroad", sale_id)["status"] == "refunded"


def test_duplicate_refund_is_noop(isolated_data, monkeypatch):
    monkeypatch.setenv("GUMROAD_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("GUMROAD_DEFAULT_CREDITS", "100")
    uid = _mkuser()
    payload = _sale_payload(email=db.get_user_by_id(uid)["email"])
    sale_id = payload["sale"]["id"]
    gumroad.process_webhook(payload)

    refund = _sale_payload(event="refund", sale_id=sale_id,
                           email=db.get_user_by_id(uid)["email"])
    gumroad.process_webhook(refund)
    bal = db.get_credit_balance(uid)
    # A second refund delivery must not reverse again
    gumroad.process_webhook(refund)
    assert db.get_credit_balance(uid) == bal