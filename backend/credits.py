"""Server-authoritative credit system for CLPZ.

Every credit mutation goes through this module. Credits are stored in
SQLite via database.py with an immutable transaction log.

Atomicity (task 08):
- Each bonus/charge/refund is ONE database transaction that includes its
  own duplicate guard, so concurrent callers can never both mutate.
- check_and_charge persists the cached replay result in the SAME commit
  as the charge, so a crash can never leave a charge without a replay
  record (or vice versa).

Scope note (decision register D2/D3): these local credits are the
desktop's development/legacy accounting. They are NOT authoritative paid
cloud entitlements; cloud grants live in the Supabase schema (task 14/15).

Refund safety:
- Each refund is tied to a specific related_id (job id).
- refund() performs the guard and the mutation in one transaction
  (db.refund_once): a job can only be refunded once, even under
  concurrency or repeated calls.
"""
from __future__ import annotations

import os

import config
import database as db

# ── Experimental local mode ───────────────────────────────────────
# CLPZ_UNLIMITED=1 turns the local ledger into an unlimited pass:
# every charge succeeds without touching balances and every balance
# reads as generously funded. Nothing is written to the ledger in this
# mode, so reconciliation and cloud entitlements stay meaningful.
# Intended for local experiments ONLY — never enable it on a shared
# server or in a packaged build.
UNLIMITED = os.getenv("CLPZ_UNLIMITED", "0") == "1"
UNLIMITED_BALANCE = 999_999

# ── Configurable pricing ──────────────────────────────────────────
COST_PER_FORGE = int(config.COST_PER_FORGE)
SIGNUP_BONUS = int(config.SIGNUP_BONUS)


# ── Public API ────────────────────────────────────────────────────

def ensure_signup_bonus(user_id: str) -> int:
    """Grant the signup bonus exactly once. Returns current balance.

    Atomic: the eligibility check and the grant commit as one transaction
    (db.grant_signup_bonus_once), so concurrent calls for the same user
    grant the bonus exactly once.
    """
    # Check if user exists
    if db.get_user_by_id(user_id) is None:
        return 0

    _, new_bal = db.grant_signup_bonus_once(user_id, SIGNUP_BONUS)
    return new_bal


def get_balance(user_id: str) -> int:
    """Return current credit balance (always >= 0)."""
    if UNLIMITED:
        return UNLIMITED_BALANCE
    return db.get_credit_balance(user_id)


def check_and_charge(user_id: str, amount: int, related_id: str = "",
                     idempotency_key: str = "") -> tuple[bool, int]:
    """Atomically check balance and deduct credits.

    Returns (success, remaining_balance).
    If balance is insufficient, no deduction occurs and success=False.

    If idempotency_key is provided and was already used, returns the
    cached result without deducting again. The cached result is stored in
    the same transaction as the charge itself.
    """
    if UNLIMITED:
        # Unlimited mode: approve every charge without a ledger write.
        return True, UNLIMITED_BALANCE

    # Replay path: a completed operation returns its original result.
    if idempotency_key:
        cached = db.check_idempotency(idempotency_key)
        if cached is not None:
            return cached.get("success", False), cached.get("remaining", 0)

    if idempotency_key:
        success, remaining = db.check_and_charge_idempotent(
            user_id, amount, related_id=related_id,
            key=idempotency_key, operation="forge",
        )
        return success, remaining

    success, remaining = db.check_and_charge(user_id, amount, related_id=related_id)
    return success, remaining


def refund(user_id: str, amount: int, related_id: str = "", reason: str = "") -> int:
    """Refund credits (e.g. on pipeline failure). Returns new balance.

    Atomic per related_id: the duplicate-refund guard and the mutation are
    one transaction (db.refund_once), so duplicate or concurrent refund
    calls return the correct balance without exceptions and never refund
    twice.
    """
    if UNLIMITED:
        # Unlimited mode: refund nothing — balances never moved.
        return get_balance(user_id)
    _, new_bal = db.refund_once(user_id, amount, related_id=related_id, reason=reason)
    return new_bal


def add_credits(user_id: str, amount: int, txn_type: str = "purchase",
                description: str = "") -> int:
    """Add credits (purchase, admin adjustment, etc.). Returns new balance."""
    if UNLIMITED:
        return get_balance(user_id)
    return db.add_credits(user_id, amount, txn_type=txn_type, description=description)


def get_transactions(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent transactions for a user (newest first)."""
    return db.get_transactions(user_id, limit=limit)


def reconcile() -> dict:
    """Reconcile every ledger against its balance (task 08 acceptance).

    For each user with credit rows: balance must equal the sum of that
    user's transaction amounts (subscriptions are out of scope locally).
    Returns a report dict with per-user deltas and an overall ok flag.
    """
    return db.reconcile_ledger()
