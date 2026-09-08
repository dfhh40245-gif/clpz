"""Gumroad webhook integration for CLPZ.

Verifies Gumroad ping webhooks (HMAC-SHA256 signature over the raw body),
records each payment exactly once (idempotent via the `payments` table's
unique (provider, external_id) constraint), and grants/refunds credits
through the existing server-authoritative credit ledger.

Invariant: ONE Gumroad transaction -> ONE payment record -> ONE credit grant.
Duplicate webhook deliveries are safe no-ops.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

import config
import credits as credits_mod
import database as db

log = logging.getLogger("gumroad")

PROVIDER = "gumroad"


def _webhook_secret() -> str:
    return os.getenv("GUMROAD_WEBHOOK_SECRET", "")


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verify the X-Gumroad-Signature header against the raw request body.

    Gumroad signs webhook payloads with HMAC-SHA256 using the webhook
    secret configured in the Gumroad dashboard. If no secret is configured
    server-side, verification is disabled (dev mode) — never enable that
    in production.
    """
    secret = _webhook_secret()
    if not secret:
        # No secret configured: only accept when the server is in debug mode.
        return bool(config.DEBUG)
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def _parse_payload(raw_body: bytes) -> dict | None:
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _product_allowed(product_id: str) -> bool:
    """Return True if the product is one CLPZ grants entitlements for."""
    allowed = os.getenv("GUMROAD_PRODUCT_IDS", "")
    if not allowed:
        return True  # No restriction configured -> accept all products.
    return product_id in {p.strip() for p in allowed.split(",") if p.strip()}


def _resolve_user(data: dict) -> str | None:
    """Map a Gumroad sale to a CLPZ user id.

    Matching order:
      1. A `clpz_user_id` custom field on the sale (set when the buyer
         started checkout from an authenticated CLPZ session).
      2. The buyer's email address (must match a verified CLPZ account).
    Returns None when no account can be matched — the webhook is then
    recorded as unlinked and no credits are granted.
    """
    sale = data.get("sale") or {}
    custom = sale.get("custom_fields") or {}
    if isinstance(custom, dict):
        uid = custom.get("clpz_user_id")
    else:
        uid = None
    if uid and db.get_user_by_id(str(uid)):
        return str(uid)
    email = (sale.get("email") or "").strip().lower()
    if not email:
        return None
    user = db.get_user_by_email(email)
    return user["id"] if user else None


def _credits_for_product(product_id: str) -> int:
    """Credits granted per purchase. Defaults to the configured cost base."""
    mapping = os.getenv("GUMROAD_PRODUCT_CREDITS", "")
    for entry in mapping.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        pid, amt = entry.split(":", 1)
        if pid.strip() == product_id and amt.strip().isdigit():
            return int(amt.strip())
    return int(os.getenv("GUMROAD_DEFAULT_CREDITS", "100"))


def process_webhook(data: dict) -> dict:
    """Process a verified Gumroad webhook payload. Idempotent.

    Returns a summary dict: {event, created, payment_id, user_id, credits}
    """
    event = data.get("event", "")
    sale = data.get("sale") or {}
    external_id = str(sale.get("id") or "").strip()
    product_id = str(sale.get("product_id") or sale.get("permalink") or "").strip()

    if event == "ping":
        return {"event": "ping", "created": False, "payment_id": None, "user_id": None, "credits": 0}

    if event in ("sale", "subscription_created", "subscription_renewed",
                 "subscription_updated", "subscription_ended", "subscription_cancelled",
                 "refund", "chargeback", "dispute_won", "dispute_lost"):
        pass
    else:
        log.info("gumroad: ignoring unhandled event %r", event)
        return {"event": event, "created": False, "payment_id": None, "user_id": None, "credits": 0}

    if not external_id:
        log.warning("gumroad: payload missing sale.id")
        return {"event": event, "created": False, "payment_id": None, "user_id": None, "credits": 0}

    # ── Idempotency guard: record the payment first ─────────────────
    # If this external id was already recorded, NO credit mutation happens.
    user_id = _resolve_user(data)
    amount_cents = int(sale.get("amount", 0) or 0)
    currency = sale.get("currency", "usd") or "usd"
    is_reversal = event in ("refund", "chargeback", "dispute_lost")
    is_cancellation = event in ("subscription_cancelled", "subscription_ended")
    status = "refunded" if is_reversal else ("cancelled" if is_cancellation else "paid")

    created, payment_id = db.record_payment(
        user_id=user_id,
        provider=PROVIDER,
        external_id=external_id,
        product_id=product_id,
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        raw_json=json.dumps(data),
    )

    if not created:
        # Already recorded. A reversal event for an existing payment must
        # still transition status and reverse credits exactly once — but
        # only if this is the first time we see the reversal.
        existing = db.get_payment(PROVIDER, external_id)
        if existing and status == "refunded" and existing["status"] != "refunded":
            changed = db.update_payment_status(PROVIDER, external_id, "refunded")
            if changed and existing.get("user_id"):
                db.subtract_credits(existing["user_id"], _credits_for_product(product_id),
                                    related_id=external_id,
                                    reason=f"Gumroad refund {external_id}")
                log.info("gumroad: reversed credits for refunded sale %s", external_id)
                return {"event": event, "created": False, "payment_id": payment_id,
                        "user_id": existing["user_id"], "credits": 0}
        log.info("gumroad: duplicate webhook for sale %s (idempotent no-op)", external_id)
        return {"event": event, "created": False, "payment_id": payment_id,
                "user_id": user_id, "credits": 0}

    # ── Entitlement / credit mutation (only for newly created payments) ──
    if not user_id:
        log.warning("gumroad: sale %s recorded but no CLPZ account matched; no credits granted",
                    external_id)
        return {"event": event, "created": True, "payment_id": payment_id,
                "user_id": None, "credits": 0}

    if not _product_allowed(product_id):
        log.warning("gumroad: sale %s product %r not in allowed list; no credits granted",
                    external_id, product_id)
        return {"event": event, "created": True, "payment_id": payment_id,
                "user_id": user_id, "credits": 0}

    if status == "paid":
        amount = _credits_for_product(product_id)
        credits_mod.add_credits(user_id, amount, txn_type="purchase",
                                description=f"Gumroad purchase {external_id}")
        log.info("gumroad: granted %d credits to %s for sale %s", amount, user_id, external_id)
        return {"event": event, "created": True, "payment_id": payment_id,
                "user_id": user_id, "credits": amount}

    # Refund / cancellation: reverse the original grant, but never below zero.
    if status == "refunded":
        db.subtract_credits(user_id, _credits_for_product(product_id),
                            related_id=external_id, reason=f"Gumroad refund {external_id}")
        log.info("gumroad: reversed credits for refunded sale %s", external_id)
    return {"event": event, "created": True, "payment_id": payment_id,
            "user_id": user_id, "credits": 0}