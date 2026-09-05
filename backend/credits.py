"""Server-authoritative credit system for CLPZ.

Every credit mutation goes through this module. Credits are stored in
SQLite via database.py with an immutable transaction log.

All operations are protected by the database lock to prevent
double-spending and race conditions.

Idempotency:
- check_and_charge accepts an idempotency_key parameter
- If the same key is used twice, the second call returns the cached result
- This prevents duplicate charges from double-clicks or network retries

Refund safety:
- Each refund is tied to a specific related_id (job_id)
- A job can only be refunded once — duplicate refunds are prevented
"""
from __future__ import annotations

import config
import database as db

# ── Configurable pricing ──────────────────────────────────────────
COST_PER_FORGE = int(config.COST_PER_FORGE)
SIGNUP_BONUS = int(config.SIGNUP_BONUS)


# ── Public API ────────────────────────────────────────────────────

def ensure_signup_bonus(user_id: str) -> int:
    """Grant the signup bonus exactly once. Returns current balance.

    Idempotent: calling multiple times for the same user only grants
    the bonus once.
    """
    if db.has_signup_bonus(user_id):
        return db.get_credit_balance(user_id)

    # Check if user exists
    if db.get_user_by_id(user_id) is None:
        return 0

    # Grant bonus
    new_bal = db.add_credits(user_id, SIGNUP_BONUS, "signup_bonus",
                             f"Welcome! {SIGNUP_BONUS} free clips.")
    return new_bal


def get_balance(user_id: str) -> int:
    """Return current credit balance (always >= 0)."""
    return db.get_credit_balance(user_id)


def check_and_charge(user_id: str, amount: int, related_id: str = "",
                     idempotency_key: str = "") -> tuple[bool, int]:
    """Atomically check balance and deduct credits.

    Returns (success, remaining_balance).
    If balance is insufficient, no deduction occurs and success=False.

    If idempotency_key is provided and was already used, returns the
    cached result without deducting again.
    """
    # Check idempotency
    if idempotency_key:
        cached = db.check_idempotency(idempotency_key)
        if cached is not None:
            return cached.get("success", False), cached.get("remaining", 0)

    success, remaining = db.check_and_charge(user_id, amount, related_id=related_id)

    # Save idempotency result
    if idempotency_key:
        db.save_idempotency(
            idempotency_key, user_id, "forge",
            {"success": success, "remaining": remaining}
        )

    return success, remaining


def refund(user_id: str, amount: int, related_id: str = "", reason: str = "") -> int:
    """Refund credits (e.g. on pipeline failure). Returns new balance.

    Safety: If related_id is provided, checks if a refund was already
    issued for that related_id. Prevents double refunds.
    """
    if amount <= 0:
        return get_credit_balance(user_id)

    # Prevent double refund: check if we already refunded for this related_id
    if related_id:
        existing_refund = db.has_refund_for_job(related_id)
        if existing_refund:
            # Already refunded — return current balance without refunding again
            return get_credit_balance(user_id)

    return db.refund_credits(user_id, amount, related_id=related_id, reason=reason)


def add_credits(user_id: str, amount: int, txn_type: str = "purchase",
                description: str = "") -> int:
    """Add credits (purchase, admin adjustment, etc.). Returns new balance."""
    return db.add_credits(user_id, amount, txn_type=txn_type, description=description)


def get_transactions(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent transactions for a user (newest first)."""
    return db.get_transactions(user_id, limit=limit)
