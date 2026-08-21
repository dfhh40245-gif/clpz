"""Server-authoritative credit system for CLPZ.

Every credit mutation goes through this module.  Credits are stored in
``data/credits.json`` with an immutable transaction log in
``data/credit_transactions.json``.

All operations are protected by a single lock to prevent double-spending
and race conditions on a single-process deployment.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

import config

_CREDITS_FILE = config.DATA_DIR / "credits.json"
_TXNS_FILE = config.DATA_DIR / "credit_transactions.json"

_lock = threading.Lock()

# ── Configurable pricing ──────────────────────────────────────────
# Cost per clip-generation job.  Change here and nowhere else.
COST_PER_FORGE = int(config.COST_PER_FORGE)

# Free credits granted on signup (once per account, enforced server-side).
SIGNUP_BONUS = int(config.SIGNUP_BONUS)


# ── Internal helpers ──────────────────────────────────────────────

def _load_credits() -> dict:
    """Load the credits map.  Returns {user_id: balance}."""
    if not _CREDITS_FILE.exists():
        return {}
    try:
        return json.loads(_CREDITS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_credits(data: dict) -> None:
    _CREDITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CREDITS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_txns() -> list[dict]:
    if not _TXNS_FILE.exists():
        return []
    try:
        return json.loads(_TXNS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_txns(txns: list[dict]) -> None:
    _TXNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TXNS_FILE.write_text(json.dumps(txns, indent=2), encoding="utf-8")


def _log_txn(
    user_id: str,
    amount: int,
    txn_type: str,
    description: str = "",
    related_id: str = "",
) -> dict:
    """Append an immutable transaction record and return it."""
    txn = {
        "id": secrets.token_hex(8),
        "user_id": user_id,
        "amount": amount,
        "type": txn_type,
        "description": description,
        "related_id": related_id,
        "created_at": time.time(),
    }
    txns = _load_txns()
    txns.append(txn)
    _save_txns(txns)
    return txn


# ── Public API ────────────────────────────────────────────────────

def ensure_signup_bonus(user_id: str) -> int:
    """Grant the signup bonus exactly once.  Returns current balance.

    Idempotent: calling multiple times for the same user only grants
    the bonus once.
    """
    with _lock:
        credits = _load_credits()
        balance = credits.get(user_id)

        if balance is None:
            # First time — grant bonus
            credits[user_id] = SIGNUP_BONUS
            _save_credits(credits)
            _log_txn(
                user_id,
                SIGNUP_BONUS,
                "signup_bonus",
                f"Welcome! {SIGNUP_BONUS} free clips.",
            )
            return SIGNUP_BONUS

        # Already exists — check if bonus was ever granted
        txns = _load_txns()
        already_bonus = any(
            t["user_id"] == user_id and t["type"] == "signup_bonus"
            for t in txns
        )
        if not already_bonus:
            credits[user_id] = balance + SIGNUP_BONUS
            _save_credits(credits)
            _log_txn(
                user_id,
                SIGNUP_BONUS,
                "signup_bonus",
                f"Welcome! {SIGNUP_BONUS} free clips.",
            )
            return credits[user_id]

        return balance


def get_balance(user_id: str) -> int:
    """Return current credit balance (always >= 0)."""
    with _lock:
        credits = _load_credits()
        return max(0, credits.get(user_id, 0))


def check_and_charge(user_id: str, amount: int, related_id: str = "") -> tuple[bool, int]:
    """Atomically check balance and deduct ``amount`` credits.

    Returns (success, remaining_balance).
    If balance is insufficient, no deduction occurs and success=False.
    """
    if amount <= 0:
        return True, get_balance(user_id)

    with _lock:
        credits = _load_credits()
        current = max(0, credits.get(user_id, 0))

        if current < amount:
            return False, current

        new_balance = current - amount
        credits[user_id] = new_balance
        _save_credits(credits)
        _log_txn(
            user_id,
            -amount,
            "forge",
            f"Forge clip generation ({amount} credit{'s' if amount != 1 else ''})",
            related_id=related_id,
        )
        return True, new_balance


def refund(user_id: str, amount: int, related_id: str = "", reason: str = "") -> int:
    """Refund credits (e.g. on pipeline failure).  Returns new balance."""
    if amount <= 0:
        return get_balance(user_id)

    with _lock:
        credits = _load_credits()
        current = max(0, credits.get(user_id, 0))
        new_balance = current + amount
        credits[user_id] = new_balance
        _save_credits(credits)
        _log_txn(
            user_id,
            amount,
            "refund",
            reason or "Refund for failed processing",
            related_id=related_id,
        )
        return new_balance


def add_credits(user_id: str, amount: int, txn_type: str = "purchase", description: str = "") -> int:
    """Add credits (purchase, admin adjustment, etc.).  Returns new balance."""
    if amount <= 0:
        return get_balance(user_id)

    with _lock:
        credits = _load_credits()
        current = max(0, credits.get(user_id, 0))
        new_balance = current + amount
        credits[user_id] = new_balance
        _save_credits(credits)
        _log_txn(
            user_id,
            amount,
            txn_type,
            description or f"Credits added ({amount})",
        )
        return new_balance


def get_transactions(user_id: str, limit: int = 50) -> list[dict]:
    """Return recent transactions for a user (newest first)."""
    with _lock:
        txns = _load_txns()
    user_txns = [t for t in txns if t["user_id"] == user_id]
    user_txns.sort(key=lambda t: t["created_at"], reverse=True)
    return user_txns[:limit]
