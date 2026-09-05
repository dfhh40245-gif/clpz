"""Unified credits provider for CLPZ.

Routes to Supabase database (web) or local SQLite (desktop/dev)
based on configuration.

Desktop mode: local credits, server-authoritative within the process.
Web mode: Supabase PostgreSQL, server-authoritative via RLS.
"""
from __future__ import annotations

import supabase_config
import credits
import config


def is_supabase_mode() -> bool:
    """Check if we're using Supabase credits (web mode)."""
    return supabase_config.is_configured()


# ── Balance ─────────────────────────────────────────────────────────

def get_balance(user_id: str) -> int:
    """Get current credit balance."""
    if is_supabase_mode():
        return _get_balance_supabase(user_id)
    return credits.get_balance(user_id)


def _get_balance_supabase(user_id: str) -> int:
    """Get balance from Supabase."""
    client = supabase_config.get_supabase_client()
    if not client:
        return 0

    result = client.table("credits").select("balance").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0].get("balance", 0)
    return 0


# ── Charge ──────────────────────────────────────────────────────────

def check_and_charge(user_id: str, amount: int, idempotency_key: str = "") -> tuple[bool, int]:
    """Check if user has enough credits and deduct.

    Returns:
        (success: bool, remaining_balance: int)
    """
    if is_supabase_mode():
        return _check_and_charge_supabase(user_id, amount, idempotency_key)
    return credits.check_and_charge(user_id, amount, idempotency_key)


def _check_and_charge_supabase(user_id: str, amount: int, idempotency_key: str) -> tuple[bool, int]:
    """Atomic check-and-deduct via Supabase RPC or transaction."""
    client = supabase_config.get_supabase_client()
    if not client:
        return False, 0

    # Use Supabase RPC for atomic operation
    try:
        result = client.rpc("check_and_deduct_credits", {
            "p_user_id": user_id,
            "p_amount": amount,
            "p_idempotency_key": idempotency_key,
        }).execute()

        if result.data:
            data = result.data
            if isinstance(data, dict):
                return data.get("success", False), data.get("remaining", 0)
            elif isinstance(data, list) and data:
                return data[0].get("success", False), data[0].get("remaining", 0)
    except Exception:
        pass

    # Fallback: manual transaction (less atomic)
    return _manual_charge_supabase(client, user_id, amount, idempotency_key)


def _manual_charge_supabase(client, user_id: str, amount: int, idempotency_key: str) -> tuple[bool, int]:
    """Manual charge via Supabase (fallback)."""
    try:
        # Check idempotency
        if idempotency_key:
            existing = client.table("credit_transactions").select("id").eq("idempotency_key", idempotency_key).execute()
            if existing.data:
                # Already charged — return current balance
                balance = _get_balance_supabase(user_id)
                return True, balance

        # Get current balance
        result = client.table("credits").select("balance").eq("user_id", user_id).execute()
        if not result.data:
            return False, 0

        balance = result.data[0]["balance"]
        if balance < amount:
            return False, balance

        # Deduct
        new_balance = balance - amount
        client.table("credits").update({"balance": new_balance}).eq("user_id", user_id).execute()

        # Record transaction
        client.table("credit_transactions").insert({
            "user_id": user_id,
            "amount": -amount,
            "type": "forge",
            "reason": "Clip generation",
            "idempotency_key": idempotency_key,
        }).execute()

        return True, new_balance
    except Exception:
        return False, 0


# ── Refund ──────────────────────────────────────────────────────────

def refund(user_id: str, amount: int, reason: str = "") -> int:
    """Refund credits. Returns new balance."""
    if is_supabase_mode():
        return _refund_supabase(user_id, amount, reason)
    return credits.refund(user_id, amount, reason)


def _refund_supabase(user_id: str, amount: int, reason: str) -> int:
    """Refund via Supabase."""
    client = supabase_config.get_supabase_client()
    if not client:
        return 0

    try:
        # Get current balance
        result = client.table("credits").select("balance").eq("user_id", user_id).execute()
        if not result.data:
            return 0

        balance = result.data[0]["balance"]
        new_balance = balance + amount
        client.table("credits").update({"balance": new_balance}).eq("user_id", user_id).execute()

        client.table("credit_transactions").insert({
            "user_id": user_id,
            "amount": amount,
            "type": "refund",
            "reason": reason,
        }).execute()

        return new_balance
    except Exception:
        return 0


# ── Transactions ────────────────────────────────────────────────────

def get_transactions(user_id: str) -> list[dict]:
    """Get transaction history for a user."""
    if is_supabase_mode():
        return _get_transactions_supabase(user_id)
    return credits.get_transactions(user_id)


def _get_transactions_supabase(user_id: str) -> list[dict]:
    """Get transactions from Supabase."""
    client = supabase_config.get_supabase_client()
    if not client:
        return []

    result = client.table("credit_transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(50).execute()
    return result.data or []


# ── Admin ───────────────────────────────────────────────────────────

def add_credits(user_id: str, amount: int, reason: str = "", admin_id: str = "") -> int:
    """Admin: add credits. Returns new balance."""
    if is_supabase_mode():
        return _add_credits_supabase(user_id, amount, reason, admin_id)
    return credits.add_credits(user_id, amount, reason)


def _add_credits_supabase(user_id: str, amount: int, reason: str, admin_id: str) -> int:
    """Admin add via Supabase."""
    client = supabase_config.get_supabase_client()
    if not client:
        return 0

    try:
        result = client.table("credits").select("balance").eq("user_id", user_id).execute()
        if not result.data:
            return 0

        balance = result.data[0]["balance"]
        new_balance = balance + amount
        client.table("credits").update({"balance": new_balance}).eq("user_id", user_id).execute()

        client.table("credit_transactions").insert({
            "user_id": user_id,
            "amount": amount,
            "type": "admin_grant",
            "reason": reason or f"Admin grant by {admin_id}",
            "admin_id": admin_id,
        }).execute()

        return new_balance
    except Exception:
        return 0


def remove_credits(user_id: str, amount: int, reason: str = "", admin_id: str = "") -> int:
    """Admin: remove credits. Returns new balance."""
    if is_supabase_mode():
        return _remove_credits_supabase(user_id, amount, reason, admin_id)
    return credits.remove_credits(user_id, amount, reason)


def _remove_credits_supabase(user_id: str, amount: int, reason: str, admin_id: str) -> int:
    """Admin remove via Supabase."""
    client = supabase_config.get_supabase_client()
    if not client:
        return 0

    try:
        result = client.table("credits").select("balance").eq("user_id", user_id).execute()
        if not result.data:
            return 0

        balance = result.data[0]["balance"]
        if balance < amount:
            return balance  # Can't remove more than they have

        new_balance = balance - amount
        client.table("credits").update({"balance": new_balance}).eq("user_id", user_id).execute()

        client.table("credit_transactions").insert({
            "user_id": user_id,
            "amount": -amount,
            "type": "admin_removal",
            "reason": reason or f"Admin removal by {admin_id}",
            "admin_id": admin_id,
        }).execute()

        return new_balance
    except Exception:
        return 0
